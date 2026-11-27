"""账号接口：账号列表、状态校验、删除、编辑与打开发布页。"""
import asyncio
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, request

from conf import BASE_DIR
from myUtils.auth import check_cookie

account_bp = Blueprint("account", __name__)

DB_PATH = Path(BASE_DIR / "db" / "database.db")
LAST_CHECKED_COLUMN = "lastCheckedAt"

# 各平台的发布页地址：用已保存的 Cookie 直接拉起浏览器供人工操作
PUBLISH_URLS = {
    2: "https://channels.weixin.qq.com/platform/post/create",
    3: "https://creator.douyin.com/creator-micro/content/upload",
    4: "https://cp.kuaishou.com/article/publish/video",
}

# 同一账号只允许一个浏览器窗口，窗口关闭后自动释放
_open_lock = threading.Lock()
_open_accounts = set()


def _connect():
    return sqlite3.connect(DB_PATH, timeout=30)


def ensure_last_checked_column():
    """为老库补上 lastCheckedAt 字段（幂等），用于展示「上次校验时间」。"""
    with _connect() as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(user_info)")]
        if columns and LAST_CHECKED_COLUMN not in columns:
            conn.execute(f"ALTER TABLE user_info ADD COLUMN {LAST_CHECKED_COLUMN} TEXT")
            conn.commit()
            print("✅ user_info 已添加 lastCheckedAt 字段")


def _now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _fetch_account_rows():
    # 小红书（type=1）已停用，历史账号不再展示
    with _connect() as conn:
        return [list(row) for row in conn.execute(
            "SELECT * FROM user_info WHERE type <> 1"
        ).fetchall()]


def _write_status(account_id, valid, checked_at):
    """状态写回是双向的：有效写 1、失效写 0，避免「异常」变成无法恢复的粘性状态。"""
    with _connect() as conn:
        conn.execute(
            "UPDATE user_info SET status = ?, lastCheckedAt = ? WHERE id = ?",
            (1 if valid else 0, checked_at, account_id),
        )
        conn.commit()


def mark_account_valid(user_name, platform_type):
    """发布成功后把对应账号标记为正常并刷新校验时间（失败不影响发布结果）。"""
    if not user_name or not platform_type:
        return
    try:
        ensure_last_checked_column()
        with _connect() as conn:
            conn.execute(
                "UPDATE user_info SET status = 1, lastCheckedAt = ? "
                "WHERE userName = ? AND type = ?",
                (_now_str(), user_name, platform_type),
            )
            conn.commit()
    except Exception as exc:
        print(f"⚠️ 更新账号状态失败: {exc}")


async def _verify_row(row):
    """校验单行并回写状态；校验过程抛错时保留原状态，不误报异常。"""
    platform_type, file_path = row[1], row[2]
    try:
        valid = await check_cookie(platform_type, file_path)
    except Exception as exc:
        print(f"⚠️ 校验账号 {row[3]}（type={platform_type}）时出错: {exc}")
        return row

    checked_at = _now_str()
    _write_status(row[0], valid, checked_at)
    row[4] = 1 if valid else 0
    if len(row) > 5:
        row[5] = checked_at
    print(f"{'✅' if valid else '❌'} {row[3]}（type={platform_type}）Cookie {'有效' if valid else '失效'}")
    return row



def account_exists(platform_type, user_name, exclude_id=None):
    """判断同一名称在同一平台是否已有账号（可排除指定账号 id）。"""
    sql = "SELECT 1 FROM user_info WHERE type = ? AND userName = ?"
    params = [platform_type, user_name]
    if exclude_id is not None:
        sql += " AND id <> ?"
        params.append(exclude_id)
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        return conn.execute(sql, params).fetchone() is not None


def get_account_record(account_id):
    """按 id 查询账号记录，不存在时返回 None。"""
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM user_info WHERE id = ?", (account_id,)
        ).fetchone()
    return dict(row) if row else None


def user_name_exists(user_name):
    """判断名称是否已在 user_name 表中维护。"""
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        return conn.execute(
            "SELECT 1 FROM user_name WHERE userName = ?", (user_name,)
        ).fetchone() is not None


def update_user_info_record(user_id, platform_type, user_name):
    """更新账号信息；返回受影响行数，违反唯一约束时抛出 IntegrityError。"""
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "UPDATE user_info SET type = ?, userName = ? WHERE id = ?",
            (platform_type, user_name, user_id),
        )
        conn.commit()
        return cursor.rowcount


def remove_cookie_file(record):
    """删除账号关联的 Cookie 文件，失败时只记录日志。"""
    if not record.get('filePath'):
        return
    cookie_file_path = Path(BASE_DIR / "cookiesFile" / record['filePath'])
    if not cookie_file_path.exists():
        return
    try:
        cookie_file_path.unlink()
        print(f"✅ Cookie文件已删除: {cookie_file_path}")
    except Exception as e:
        print(f"⚠️ 删除Cookie文件失败: {e}")


async def _open_publish_page(cookie_path, url):
    """用已保存的 Cookie 打开有头浏览器，直到用户关闭窗口。"""
    from patchright.async_api import async_playwright

    from conf import get_browser_options
    from utils.base_social_media import set_init_script

    async with async_playwright() as pw:
        options = {**get_browser_options(), "headless": False}
        browser = await pw.chromium.launch(**options)
        try:
            context = await browser.new_context(
                storage_state=str(cookie_path), no_viewport=True
            )
            context = await set_init_script(context)
            page = await context.new_page()
            closed = asyncio.Event()
            page.on("close", lambda _: closed.set())
            browser.on("disconnected", lambda _: closed.set())
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await closed.wait()
        finally:
            await browser.close()


def _open_worker(account_id, cookie_path, url, user_name):
    """后台线程保持浏览器存活；窗口关闭后释放账号占用。"""
    try:
        asyncio.run(_open_publish_page(cookie_path, url))
    except Exception as exc:
        print(f"⚠️ 打开 {user_name} 的发布页失败: {exc}")
    finally:
        with _open_lock:
            _open_accounts.discard(account_id)


@account_bp.route("/openAccount", methods=['POST'])
def open_account():
    """使用账号已保存的 Cookie 打开平台发布页。"""
    data = request.get_json(silent=True) or {}
    account_id = data.get("id")
    if not isinstance(account_id, int):
        return jsonify({"code": 400, "msg": "账号 id 无效", "data": None}), 400

    record = get_account_record(account_id)
    if not record:
        return jsonify({"code": 404, "msg": "账号不存在", "data": None}), 404
    url = PUBLISH_URLS.get(record.get("type"))
    if not url:
        return jsonify({"code": 400, "msg": "暂不支持该平台", "data": None}), 400

    cookie_file_path = Path(BASE_DIR / "cookiesFile" / (record.get("filePath") or ""))
    if not record.get("filePath") or not cookie_file_path.exists():
        return jsonify({
            "code": 404,
            "msg": "Cookie 文件不存在，请先登录",
            "data": None,
        }), 404

    with _open_lock:
        if account_id in _open_accounts:
            return jsonify({"code": 409, "msg": "该账号的浏览器已打开", "data": None}), 409
        _open_accounts.add(account_id)

    threading.Thread(
        target=_open_worker,
        args=(account_id, cookie_file_path, url, record.get("userName") or ""),
        daemon=True,
    ).start()
    return jsonify({"code": 200, "msg": "已打开发布页", "data": None}), 200


@account_bp.route("/getAccounts", methods=['GET'])
def getAccounts():
    """快速获取所有账号信息，不进行cookie验证"""
    try:
        ensure_last_checked_column()
        rows_list = _fetch_account_rows()
        print("\n📋 当前数据表内容（快速获取）：")
        for row in rows_list:
            print(row)
        return jsonify({
            "code": 200,
            "msg": None,
            "data": rows_list
        }), 200
    except Exception as e:
        print(f"获取账号列表时出错: {str(e)}")
        return jsonify({
            "code": 500,
            "msg": f"获取账号列表失败: {str(e)}",
            "data": None
        }), 500


@account_bp.route("/getValidAccounts", methods=['GET'])
async def getValidAccounts():
    """逐个校验 Cookie，并把结果（正常/异常 + 上次校验时间）写回数据库。"""
    try:
        ensure_last_checked_column()
        rows = _fetch_account_rows()
        for row in rows:
            await _verify_row(row)
        return jsonify({
            "code": 200,
            "msg": None,
            "data": rows
        }), 200
    except Exception as e:
        print(f"校验账号状态时出错: {str(e)}")
        return jsonify({
            "code": 500,
            "msg": f"校验账号状态失败: {str(e)}",
            "data": None
        }), 500


@account_bp.route('/deleteAccount', methods=['GET'])
def delete_account():
    account_id = request.args.get('id')

    if not account_id or not account_id.isdigit():
        return jsonify({
            "code": 400,
            "msg": "Invalid or missing account ID",
            "data": None
        }), 400

    account_id = int(account_id)

    try:
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM user_info WHERE id = ?", (account_id,))
            record = cursor.fetchone()
            if not record:
                return jsonify({
                    "code": 404,
                    "msg": "account not found",
                    "data": None
                }), 404

            record = dict(record)
            remove_cookie_file(record)

            cursor.execute("DELETE FROM user_info WHERE id = ?", (account_id,))
            conn.commit()

        return jsonify({
            "code": 200,
            "msg": "account deleted successfully",
            "data": None
        }), 200
    except Exception as e:
        return jsonify({
            "code": 500,
            "msg": f"delete failed: {str(e)}",
            "data": None
        }), 500


@account_bp.route('/updateUserinfo', methods=['POST'])
def updateUserinfo():
    data = request.get_json() or {}
    user_id = data.get('id')
    platform_type = data.get('type')
    user_name = data.get('userName')

    if not user_id or not platform_type or not user_name:
        return jsonify({"code": 400, "msg": "参数不完整", "data": None}), 400

    # 同一名称在同一平台只能有一个账号
    if account_exists(platform_type, user_name, exclude_id=user_id):
        return jsonify({
            "code": 409,
            "msg": "该名称已在此平台添加过账号",
            "data": None
        }), 409

    try:
        updated = update_user_info_record(user_id, platform_type, user_name)
        if updated == 0:
            return jsonify({"code": 404, "msg": "账号不存在", "data": None}), 404
        return jsonify({
            "code": 200,
            "msg": "account update successfully",
            "data": None
        }), 200
    except sqlite3.IntegrityError:
        return jsonify({
            "code": 409,
            "msg": "该名称已在此平台添加过账号",
            "data": None
        }), 409
    except Exception as e:
        return jsonify({
            "code": 500,
            "msg": "update failed!",
            "data": None
        }), 500
