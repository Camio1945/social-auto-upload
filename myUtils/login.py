import asyncio
import sqlite3
import uuid
from pathlib import Path

from playwright.async_api import async_playwright

from conf import BASE_DIR, get_browser_options
from myUtils.auth import check_cookie
from utils.base_social_media import set_init_script

# 等待扫码登录的最长时间（秒）
LOGIN_TIMEOUT = 200


# 抖音：打开创作者中心，取二维码图片
async def _prepare_douyin(page):
    await page.goto("https://creator.douyin.com/")
    img_locator = page.get_by_role("img", name="二维码")
    return await img_locator.get_attribute("src")


# 视频号：二维码在 iframe 中
async def _prepare_tencent(page):
    await page.goto("https://channels.weixin.qq.com")
    iframe_locator = page.frame_locator("iframe").first
    img_locator = iframe_locator.get_by_role("img").first
    return await img_locator.get_attribute("src")


# 快手：进入扫码登录弹窗
async def _prepare_kuaishou(page):
    await page.goto("https://cp.kuaishou.com")
    await page.get_by_role("link", name="立即登录").click()
    await page.get_by_text("扫码登录").click()
    img_locator = page.get_by_role("img", name="qrcode")
    return await img_locator.get_attribute("src")


# 小红书：点击登录入口后取二维码
async def _prepare_xiaohongshu(page):
    await page.goto("https://creator.xiaohongshu.com/")
    await page.locator('img.css-wemwzq').click()
    img_locator = page.get_by_role("img").nth(2)
    return await img_locator.get_attribute("src")


async def _wait_for_redirect(page, original_url, status_queue):
    """等待主框架跳转，超时返回 False 并写入失败状态。"""
    url_changed = asyncio.Event()

    async def on_url_change():
        if page.url != original_url:
            url_changed.set()

    page.on(
        'framenavigated',
        lambda frame: asyncio.create_task(on_url_change()) if frame == page.main_frame else None
    )

    try:
        await asyncio.wait_for(url_changed.wait(), timeout=LOGIN_TIMEOUT)
        print("监听页面跳转成功")
        return True
    except asyncio.TimeoutError:
        print("监听页面跳转超时")
        status_queue.put("500")
        return False


def _remove_cookie(cookie_name):
    """删除指定 Cookie 文件，失败时只记录日志。"""
    cookie_path = Path(BASE_DIR / "cookiesFile" / cookie_name)
    try:
        if cookie_path.exists():
            cookie_path.unlink()
    except OSError as e:
        print(f"⚠️ 删除Cookie文件失败: {e}")


async def _save_cookie(context, platform_type):
    """保存并校验 Cookie；校验失败返回 None。"""
    cookie_name = f"{uuid.uuid1()}.json"
    cookies_dir = Path(BASE_DIR / "cookiesFile")
    cookies_dir.mkdir(exist_ok=True)
    await context.storage_state(path=cookies_dir / cookie_name)
    print(f"UUID v1: {cookie_name}")
    if await check_cookie(platform_type, cookie_name):
        return cookie_name
    _remove_cookie(cookie_name)
    return None


def _persist_account(platform_type, user_name, cookie_name, account_id=None):
    """写入账号记录：传 account_id 时更新该账号，否则新增记录。"""
    from myUtils.account_api import ensure_last_checked_column

    db_path = Path(BASE_DIR / "db" / "database.db")
    old_cookie = None
    ensure_last_checked_column()
    with sqlite3.connect(db_path) as conn:
        if account_id:
            row = conn.execute(
                'SELECT filePath FROM user_info WHERE id = ?', (account_id,)
            ).fetchone()
            old_cookie = row[0] if row else None
            conn.execute(
                "UPDATE user_info SET filePath = ?, status = 1, "
                "lastCheckedAt = datetime('now', 'localtime') WHERE id = ?",
                (cookie_name, account_id)
            )
        else:
            conn.execute(
                "INSERT INTO user_info (type, filePath, userName, status, lastCheckedAt) "
                "VALUES (?, ?, ?, 1, datetime('now', 'localtime'))",
                (platform_type, cookie_name, user_name)
            )
        conn.commit()
    print("✅ 用户状态已记录")
    if old_cookie and old_cookie != cookie_name:
        _remove_cookie(old_cookie)


async def _run_login(platform_type, user_name, status_queue, prepare, account_id=None):
    """通用扫码登录流程；account_id 存在时刷新该账号的 Cookie。"""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**get_browser_options())
        context = await browser.new_context(no_viewport=True)
        context = await set_init_script(context)
        page = await context.new_page()
        try:
            src = await prepare(page)
            original_url = page.url
            print("✅ 图片地址:", src)
            status_queue.put(src)

            if not await _wait_for_redirect(page, original_url, status_queue):
                return None

            cookie_name = await _save_cookie(context, platform_type)
            if not cookie_name:
                status_queue.put("500")
                return None

            _persist_account(platform_type, user_name, cookie_name, account_id)
            status_queue.put("200")
            return cookie_name
        finally:
            await page.close()
            await context.close()
            await browser.close()


# 抖音登录
async def douyin_cookie_gen(id, status_queue, account_id=None):
    return await _run_login(3, id, status_queue, _prepare_douyin, account_id)


# 视频号登录
async def get_tencent_cookie(id, status_queue, account_id=None):
    return await _run_login(2, id, status_queue, _prepare_tencent, account_id)


# 快手登录
async def get_ks_cookie(id, status_queue, account_id=None):
    return await _run_login(4, id, status_queue, _prepare_kuaishou, account_id)


# 小红书登录
async def xiaohongshu_cookie_gen(id, status_queue, account_id=None):
    return await _run_login(1, id, status_queue, _prepare_xiaohongshu, account_id)
