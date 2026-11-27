"""视频号登录态保活：定时用无窗口浏览器访问一次平台页面，降低会话失效频率。

微信网页会话有不活跃过期时间，长时间不访问就会被判失效。这里按配置的间隔在
后台跑一次真实页面访问让服务端续期，访问后把浏览器里的最新 Cookie 原子写回
账号文件——只访问不回写，本地会一直拿着旧会话，保活等于白做。
"""
import asyncio
import json
import os
import random
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from conf import BASE_DIR, get_browser_options
from myUtils.auth import resolve_cookie_path

TENCENT_TYPE = 2
PLATFORM_URL = "https://channels.weixin.qq.com/platform"
DEFAULT_INTERVAL_MINUTES = 60
MIN_INTERVAL_MINUTES = 10
MAX_INTERVAL_MINUTES = 1440
TICK_SECONDS = 60
JITTER_RATIO = 0.1
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
PAGE_TIMEOUT_MS = 45000

CONFIG_KEYS = (
    "keepalive_enabled",
    "keepalive_interval_minutes",
    "keepalive_last_run_at",
    "keepalive_last_result",
    "keepalive_last_message",
    "keepalive_last_cookie_write_at",
    "keepalive_next_run_at",
)

_job_lock = threading.Lock()
_started = False
_table_ready = False
_table_lock = threading.Lock()


def _connect():
    return sqlite3.connect(Path(BASE_DIR / "db" / "database.db"), timeout=30)


def _ensure_table():
    """建表只做一次：调度线程每分钟都会读配置，不该每次都执行 DDL。"""
    global _table_ready
    if _table_ready:
        return
    with _table_lock:
        if _table_ready:
            return
        with _connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS app_config (key TEXT PRIMARY KEY, value TEXT)"
            )
            conn.commit()
        _table_ready = True


def _get_many(keys):
    _ensure_table()
    placeholders = ",".join("?" * len(keys))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT key, value FROM app_config WHERE key IN ({placeholders})",
            tuple(keys),
        ).fetchall()
    return dict(rows)


def _get(key, default=""):
    return _get_many([key]).get(key, default)


def _set(**items):
    _ensure_table()
    with _connect() as conn:
        conn.executemany(
            "INSERT INTO app_config (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            [(key, str(value)) for key, value in items.items()],
        )
        conn.commit()


def _parse_interval(value):
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        raise ValueError("保活间隔必须是整数分钟") from None
    if not MIN_INTERVAL_MINUTES <= minutes <= MAX_INTERVAL_MINUTES:
        raise ValueError(
            f"保活间隔需在 {MIN_INTERVAL_MINUTES}~{MAX_INTERVAL_MINUTES} 分钟之间"
        )
    return minutes


def _interval_from(value):
    try:
        return _parse_interval(value)
    except ValueError:
        return DEFAULT_INTERVAL_MINUTES


def _as_bool(value):
    """入参可能是 JSON 布尔，也可能是字符串，按语义统一转换。"""
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def load_config():
    values = _get_many(CONFIG_KEYS)
    return {
        "enabled": values.get("keepalive_enabled", "0") == "1",
        "intervalMinutes": _interval_from(values.get("keepalive_interval_minutes")),
        "lastRunAt": values.get("keepalive_last_run_at"),
        "lastResult": values.get("keepalive_last_result"),
        "lastMessage": values.get("keepalive_last_message"),
        "lastCookieWriteAt": values.get("keepalive_last_cookie_write_at"),
        "nextRunAt": values.get("keepalive_next_run_at"),
    }


def update_config(enabled=None, interval_minutes=None):
    """只更新传入的字段；改动后清空下次执行时间，让新配置立即生效。"""
    config = load_config()
    new_enabled = config["enabled"] if enabled is None else _as_bool(enabled)
    if interval_minutes is None:
        new_interval = config["intervalMinutes"]
    else:
        new_interval = _parse_interval(interval_minutes)
    _set(
        keepalive_enabled="1" if new_enabled else "0",
        keepalive_interval_minutes=new_interval,
        keepalive_next_run_at="",
    )
    return load_config()


def _parse_time(value):
    try:
        return datetime.strptime(value, TIME_FORMAT)
    except (TypeError, ValueError):
        return None


def _is_due():
    next_at = _parse_time(_get("keepalive_next_run_at"))
    return next_at is None or datetime.now() >= next_at


def _next_run_at(now):
    """加一点随机抖动，避免每天固定整点访问看起来像机器人。"""
    interval = load_config()["intervalMinutes"]
    jitter = 1 + random.uniform(-JITTER_RATIO, JITTER_RATIO)
    return now + timedelta(minutes=interval * jitter)


def _load_state(cookie_path):
    with cookie_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _write_state_atomic(cookie_path, state):
    """原子替换，避免发布/评论流程刚好读到写了一半的 Cookie 文件。"""
    temp_path = cookie_path.with_name(cookie_path.name + ".tmp")
    temp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp_path, cookie_path)


def _sync_cookie_file(cookie_path, state):
    if not state or not state.get("cookies"):
        return False
    try:
        if _load_state(cookie_path) == state:
            return False
    except (OSError, ValueError):
        pass
    _write_state_atomic(cookie_path, state)
    print(f"🍪 视频号保活已回写 Cookie: {cookie_path.name}")
    return True


async def _open_platform_page(context):
    """真实访问一次页面（与人工使用路径一致），加载失败不阻塞后续判定。"""
    page = await context.new_page()
    try:
        await page.goto(PLATFORM_URL, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
    except Exception as exc:
        print(f"⚠️ 视频号保活页面加载异常（改以接口结果判定）: {exc}")
    finally:
        await page.close()


async def _touch_account(cookie_path):
    """访问页面并回写 Cookie；只有远端明确判定无登录态才算失效。"""
    from myUtils.wechat_comment import WechatAuthError, WechatCommentClient
    from patchright.async_api import async_playwright
    from utils.base_social_media import set_init_script

    options = {**get_browser_options(), "headless": True}
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**options)
        try:
            context = await browser.new_context(storage_state=str(cookie_path))
            context = await set_init_script(context)
            await _open_platform_page(context)
            try:
                await WechatCommentClient(context).connect()
            except WechatAuthError as exc:
                return False, str(exc), False
            state = await context.storage_state()
            wrote = _sync_cookie_file(cookie_path, state)
            message = "登录态有效，Cookie 已刷新" if wrote else "登录态有效，Cookie 无变化"
            return True, message, wrote
        finally:
            await browser.close()


def _tencent_accounts():
    """视频号账号全部参与保活，避免多账号时只维护最早的一条。"""
    with _connect() as conn:
        return conn.execute(
            "SELECT id, filePath, userName FROM user_info WHERE type = ? ORDER BY id",
            (TENCENT_TYPE,),
        ).fetchall()


def _write_status(account_id, valid):
    with _connect() as conn:
        conn.execute(
            "UPDATE user_info SET status = ?, lastCheckedAt = ? WHERE id = ?",
            (1 if valid else 0, datetime.now().strftime(TIME_FORMAT), account_id),
        )
        conn.commit()


def _run_account(account):
    """保活单个账号，返回 (result, message)，result 为 ok/invalid/error。"""
    account_id, file_path, user_name = account
    cookie_path = resolve_cookie_path(file_path)
    if not cookie_path.exists():
        _write_status(account_id, False)
        return "invalid", f"{user_name}：Cookie 文件不存在，请重新登录"
    try:
        valid, message, wrote = asyncio.run(_touch_account(cookie_path))
    except Exception as exc:
        # 网络/浏览器异常不代表登录态失效，保留账号原状态不动
        return "error", f"{user_name}：{exc}"
    _write_status(account_id, valid)
    if valid and wrote:
        _set(keepalive_last_cookie_write_at=datetime.now().strftime(TIME_FORMAT))
    print(f"{'✅' if valid else '❌'} 视频号保活 {user_name}: {message}")
    return ("ok" if valid else "invalid"), f"{user_name}：{message}"


def _merge_outcomes(results):
    message = "；".join(text for _, text in results)
    for failed in ("error", "invalid"):
        if any(result == failed for result, _ in results):
            return {"result": failed, "message": message}
    return {"result": "ok", "message": message}


def _run_accounts():
    accounts = _tencent_accounts()
    if not accounts:
        return {"result": "skipped", "message": "没有可用的视频号账号"}
    return _merge_outcomes([_run_account(account) for account in accounts])


def _record(outcome):
    now = datetime.now()
    _set(
        keepalive_last_run_at=now.strftime(TIME_FORMAT),
        keepalive_last_result=outcome["result"],
        keepalive_last_message=outcome["message"][:300],
        keepalive_next_run_at=_next_run_at(now).strftime(TIME_FORMAT),
    )


def _safe_record(outcome):
    """记录失败不应该让调用方（接口/调度线程）收到异常。"""
    try:
        _record(outcome)
    except Exception as exc:
        print(f"⚠️ 保活结果写入失败: {exc}")


def run_once():
    """执行一次保活；返回 {"result": ok|invalid|busy|skipped|error, "message": str}。"""
    if not _job_lock.acquire(blocking=False):
        return {"result": "busy", "message": "上一次保活仍在执行"}
    try:
        try:
            outcome = _run_accounts()
        except Exception as exc:
            outcome = {"result": "error", "message": f"保活失败: {exc}"}
        _safe_record(outcome)
        return outcome
    finally:
        _job_lock.release()


def _busy_elsewhere():
    try:
        from myUtils.comment_api import is_busy
        return is_busy()
    except Exception:
        return False


def _tick():
    if not load_config()["enabled"]:
        return
    if _busy_elsewhere() or not _is_due():
        return
    run_once()


def _loop():
    while True:
        try:
            _tick()
        except Exception as exc:
            print(f"⚠️ 视频号保活调度出错: {exc}")
        time.sleep(TICK_SECONDS)


def start_scheduler():
    """后端启动时调用；重复调用只会有第一个生效。"""
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=_loop, name="wechat-keepalive", daemon=True).start()
    print("🫀 视频号保活调度已启动")
