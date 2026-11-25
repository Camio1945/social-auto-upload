"""快手评论采集与操作：通过创作者中心评论页拦截接口、操作页面控件。"""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

from patchright.async_api import async_playwright

from conf import get_browser_options
from myUtils.douyin_comment import CommentNotFoundError
from utils.base_social_media import set_init_script

COMMENT_PAGE_URL = "https://cp.kuaishou.com/article/comment"
PHOTO_LIST_KEY = "comment/photoList"
COMMENT_LIST_KEY = "comment/commentList"
COMMENT_ROW_SELECTOR = ".comment-content"
LIKE_ICON_SELECTOR = "[class*='icon-like']"
REPLY_ICON_SELECTOR = "[class*='icon-reply']"
LIKED_CLASS = "icon-like-active"


def _format_time_ms(timestamp):
    """快手时间戳是毫秒，统一转成本地时间字符串。"""
    try:
        return datetime.fromtimestamp(int(timestamp) / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return None


def normalize_work(item):
    photo_id = str(item.get("photoId") or "")
    return {
        "platformPostId": photo_id,
        "title": (item.get("title") or "").strip(),
        "coverUrl": item.get("cover") or "",
        "shareUrl": f"{COMMENT_PAGE_URL}?photoId={photo_id}",
        "commentCount": int(item.get("commentCount") or 0),
        "publishedAt": _format_time_ms(item.get("uploadTime")),
    }


def normalize_comment(item):
    return {
        "platformCommentId": str(item.get("commentId") or ""),
        "authorId": str(item.get("authorId") or ""),
        "authorName": item.get("authorName") or "",
        "authorAvatar": item.get("headurl") or "",
        "content": item.get("content") or "",
        "likeCount": int(item.get("likedCount") or 0),
        "replyCount": int(item.get("subCommentCount") or 0),
        "ipLabel": "",
        "platformCreatedAt": _format_time_ms(item.get("timestamp")),
        "userDigged": 1 if item.get("liked") else 0,
    }


def _filter_comments(raw_items, own_uid):
    """只保留一级评论，并过滤掉账号自己发出的评论。"""
    result = []
    for item in raw_items:
        if item.get("replyTo"):
            continue
        if own_uid and str(item.get("authorId")) == own_uid:
            continue
        comment = normalize_comment(item)
        if comment["platformCommentId"]:
            result.append(comment)
    return result


def _report(progress, phase, current, total, message):
    if progress:
        progress({
            "phase": phase,
            "current": current,
            "total": total,
            "message": message,
        })


async def _wait_signal(event, timeout):
    try:
        await asyncio.wait_for(event.wait(), timeout=timeout)
        return True
    except asyncio.TimeoutError:
        return False


@asynccontextmanager
async def _browser_page(account_file):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(**get_browser_options())
        context = await browser.new_context(
            storage_state=str(account_file),
            no_viewport=True,
        )
        context = await set_init_script(context)
        page = await context.new_page()
        try:
            yield page
        finally:
            await browser.close()


async def _own_user_id(context):
    cookies = await context.cookies()
    return next((c["value"] for c in cookies if c["name"] == "userId"), "")


async def _collect_photo_list(page):
    """打开评论页并点击「选择视频」，拦截作品列表接口。"""
    result = {}
    done = asyncio.Event()

    async def on_response(response):
        if PHOTO_LIST_KEY in response.url and not done.is_set():
            try:
                result["payload"] = await response.json()
            except Exception:
                return
            done.set()

    handler = lambda response: asyncio.create_task(on_response(response))
    page.on("response", handler)
    try:
        await page.goto(COMMENT_PAGE_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(4)
        await page.get_by_role("button", name="选择视频").first.click()
        await _wait_signal(done, timeout=15)
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass
    finally:
        page.remove_listener("response", handler)
    payload = result.get("payload")
    if payload is None:
        raise RuntimeError("未能获取快手作品列表，请检查登录状态或页面结构")
    return (payload.get("data") or {}).get("photoList") or []


async def _collect_photo_comments(page, photo_id):
    """按作品打开评论页，拦截该作品的评论列表接口。"""
    result = {}
    done = asyncio.Event()

    async def on_response(response):
        if COMMENT_LIST_KEY in response.url and not done.is_set():
            try:
                result["payload"] = await response.json()
            except Exception:
                return
            done.set()

    handler = lambda response: asyncio.create_task(on_response(response))
    page.on("response", handler)
    try:
        await page.goto(f"{COMMENT_PAGE_URL}?photoId={photo_id}",
                        wait_until="domcontentloaded", timeout=60000)
        await _wait_signal(done, timeout=20)
    finally:
        page.remove_listener("response", handler)
    payload = result.get("payload") or {}
    return (payload.get("data") or {}).get("list") or []


async def fetch_kuaishou_comments(account_file, progress=None):
    """采集账号下所有作品与一级评论，返回作品、评论与截断作品列表。"""
    async with _browser_page(account_file) as page:
        _report(progress, "works", 0, 0, "正在获取快手作品列表")
        raw_photos = await _collect_photo_list(page)
        works = [normalize_work(item) for item in raw_photos]
        own_uid = await _own_user_id(page.context)

        targets = [item for item in works if item["commentCount"] > 0]
        total = len(targets)
        comments = {}
        for index, work in enumerate(targets, start=1):
            photo_id = work["platformPostId"]
            _report(progress, "comments", index - 1, total, f"正在同步作品 {index}/{total}")
            raw_items = await _collect_photo_comments(page, photo_id)
            comments[photo_id] = _filter_comments(raw_items, own_uid)
            _report(progress, "comments", index, total, f"已同步 {index}/{total}")
            await asyncio.sleep(1)

        return {"works": works, "comments": comments, "truncatedPosts": []}


def _comment_index(raw_items, comment_id):
    for index, item in enumerate(raw_items):
        if str(item.get("commentId")) == str(comment_id) and not item.get("replyTo"):
            return index
    return -1


async def _find_comment_row(page, photo_id, comment_id):
    """返回目标评论对应的 DOM 行与原始数据（用于比较回复数）。"""
    raw_items = await _collect_photo_comments(page, photo_id)
    index = _comment_index(raw_items, comment_id)
    if index < 0:
        raise CommentNotFoundError("未在页面上找到目标评论")
    return page.locator(COMMENT_ROW_SELECTOR).nth(index), raw_items[index]


async def _wait_liked(like):
    for _ in range(10):
        if LIKED_CLASS in (await like.get_attribute("class") or ""):
            return True
        await asyncio.sleep(0.5)
    return False


async def like_kuaishou_comment(account_file, platform_post_id, platform_comment_id,
                                content="", author="", max_pages=0):
    """给指定评论点赞；已点赞时直接返回，不会取消赞。"""
    async with _browser_page(account_file) as page:
        row, _ = await _find_comment_row(page, platform_post_id, platform_comment_id)
        like = row.locator(LIKE_ICON_SELECTOR).first
        if LIKED_CLASS in (await like.get_attribute("class") or ""):
            return {"clicked": False, "liked": True}
        await like.click()
        return {"clicked": True, "liked": await _wait_liked(like)}


async def _submit_reply(page, row):
    """点击确认发送，等待请求完成；成功与否由后续评论列表校验。"""
    await row.locator(".sure-btn").first.click()
    await asyncio.sleep(3)


def _reply_count(raw_items, comment_id):
    for item in raw_items:
        if str(item.get("commentId")) == str(comment_id):
            return int(item.get("subCommentCount") or 0)
    return 0


async def reply_kuaishou_comment(account_file, platform_post_id, platform_comment_id,
                                 text, content="", author="", max_pages=0):
    """通过页面 UI 回复指定评论；用回复数变化确认结果，避免依赖未知响应结构。"""
    async with _browser_page(account_file) as page:
        row, item = await _find_comment_row(page, platform_post_id, platform_comment_id)
        before = int(item.get("subCommentCount") or 0)

        await row.locator(REPLY_ICON_SELECTOR).first.click()
        await asyncio.sleep(1)
        editor = row.locator(".comment-input").first
        await editor.click()
        await editor.fill(text)
        await asyncio.sleep(1)
        await _submit_reply(page, row)

        refreshed = await _collect_photo_comments(page, platform_post_id)
        if _reply_count(refreshed, platform_comment_id) > before:
            return {"result": 1}
        return {"result": 0, "message": "回复状态未确认，请到平台确认"}
