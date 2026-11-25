"""小红书评论采集：创作平台取笔记列表，公开笔记页拦截评论接口。

创作服务平台没有网页版评论管理入口，因此作品信息取自笔记管理接口，
评论则在带 xsec_token 的公开笔记页上采集。
"""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

from myUtils.douyin_comment import CommentNotFoundError

NOTE_MANAGER_URL = "https://creator.xiaohongshu.com/new/note-manager"
POSTED_API_KEY = "creator/note/user/posted"
COMMENT_API_KEY = "sns/web/v2/comment/page"
NOTE_PAGE_URL = (
    "https://www.xiaohongshu.com/explore/{note_id}"
    "?xsec_token={token}&xsec_source=pc_creatormng"
)
REPLY_API_KEY = "/comment/post"
# 单个作品最多翻 20 页评论，与前端提示文案保持一致
MAX_COMMENT_PAGES = 20
SCROLL_IDLE_ROUNDS = 3


def _format_time(timestamp):
    """评论时间戳是毫秒；作品时间由创作平台直接返回可读字符串。"""
    try:
        return datetime.fromtimestamp(int(timestamp) / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return None


def _work_time(value):
    text = str(value or "").strip()
    if not text:
        return None
    # 创作平台返回 "2026-11-25 20:59"，补秒后与其他平台格式一致
    return f"{text}:00" if len(text) == 16 else text


def _first_image(note):
    images = note.get("images_list") or []
    return (images[0] or {}).get("url") if images else ""


def normalize_work(note):
    note_id = str(note.get("id") or "")
    token = note.get("xsec_token") or ""
    return {
        "platformPostId": note_id,
        "title": (note.get("display_title") or "").strip(),
        "coverUrl": _first_image(note) or "",
        "shareUrl": NOTE_PAGE_URL.format(note_id=note_id, token=token),
        "commentCount": int(note.get("comments_count") or 0),
        "publishedAt": _work_time(note.get("time")),
    }


def normalize_comment(item):
    user = item.get("user_info") or {}
    return {
        "platformCommentId": str(item.get("id") or ""),
        "authorId": str(user.get("user_id") or ""),
        "authorName": user.get("nickname") or "",
        "authorAvatar": user.get("image") or "",
        "content": item.get("content") or "",
        "likeCount": int(item.get("like_count") or 0),
        "replyCount": int(item.get("sub_comment_count") or 0),
        "ipLabel": item.get("ip_location") or "",
        "platformCreatedAt": _format_time(item.get("create_time")),
        "userDigged": 1 if item.get("liked") else 0,
    }


def _filter_comments(raw_items, self_id):
    """只保留一级评论，并过滤掉账号自己发出的评论。"""
    result = []
    for item in raw_items:
        comment = normalize_comment(item)
        if not comment["platformCommentId"]:
            continue
        if self_id and comment["authorId"] == self_id:
            continue
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


@asynccontextmanager
async def _xhs_page(account_file):
    """用登录 Cookie 的独立上下文，避免和发布流程争用持久化 profile。"""
    from patchright.async_api import async_playwright

    from conf import get_browser_options

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(**get_browser_options())
        context = await browser.new_context(storage_state=str(account_file))
        try:
            page = await context.new_page()
            yield page
        finally:
            await browser.close()


async def _collect_works(page, rounds=10, wait=2):
    """滚动笔记管理页，合并分页返回的笔记列表。"""
    collected = {}

    async def on_response(response):
        if POSTED_API_KEY not in response.url:
            return
        try:
            payload = await response.json()
        except Exception:
            return
        for note in (payload.get("data") or {}).get("notes") or []:
            note_id = str(note.get("id") or "")
            if note_id:
                collected[note_id] = note

    handler = lambda response: asyncio.create_task(on_response(response))
    page.on("response", handler)
    try:
        await page.goto(NOTE_MANAGER_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(6)
        idle = 0
        for _ in range(rounds):
            before = len(collected)
            await page.mouse.wheel(0, 1500)
            await asyncio.sleep(wait)
            if len(collected) <= before:
                idle += 1
                if idle >= 2:
                    break
            else:
                idle = 0
    finally:
        page.remove_listener("response", handler)
    return list(collected.values())


def _comment_response_handler(state, note_id):
    async def on_response(response):
        if COMMENT_API_KEY not in response.url or note_id not in response.url:
            return
        try:
            payload = await response.json()
        except Exception:
            return
        data = payload.get("data") or {}
        state["self_id"] = data.get("user_id") or state["self_id"]
        for item in data.get("comments") or []:
            item_id = str(item.get("id") or "")
            if item_id:
                state["comments"][item_id] = item
        state["has_more"] = bool(data.get("has_more"))
        state["changed"].set()

    return on_response


async def _scroll_comment_pages(page, state, max_pages):
    """滚动评论区加载更多，连续无新数据即停止。"""
    pages = 1
    idle = 0
    while pages < max_pages and state["has_more"]:
        before = len(state["comments"])
        state["changed"].clear()
        await page.mouse.wheel(0, 1400)
        try:
            await asyncio.wait_for(state["changed"].wait(), timeout=6)
        except asyncio.TimeoutError:
            pass
        if len(state["comments"]) > before:
            pages += 1
            idle = 0
            await asyncio.sleep(1)
            continue
        idle += 1
        if idle >= SCROLL_IDLE_ROUNDS:
            break
    return pages >= max_pages and state["has_more"]


async def _collect_comments(page, work, max_pages=MAX_COMMENT_PAGES):
    """打开公开笔记页，返回 (评论列表, 自身用户 id, 是否截断)。"""
    note_id = work["platformPostId"]
    state = {
        "comments": {},
        "self_id": "",
        "has_more": True,
        "changed": asyncio.Event(),
    }
    handler = lambda response: asyncio.create_task(
        _comment_response_handler(state, note_id)(response)
    )
    page.on("response", handler)
    try:
        await page.goto(work["shareUrl"], wait_until="domcontentloaded", timeout=60000)
        try:
            await asyncio.wait_for(state["changed"].wait(), timeout=20)
        except asyncio.TimeoutError:
            pass
        truncated = await _scroll_comment_pages(page, state, max_pages)
    finally:
        page.remove_listener("response", handler)
    return list(state["comments"].values()), state["self_id"], truncated


async def _sync_work(page, work, index, total, progress, comments, truncated):
    note_id = work["platformPostId"]
    _report(progress, "comments", index - 1, total, f"正在同步笔记 {index}/{total}")
    try:
        raw_items, self_id, is_truncated = await _collect_comments(page, work)
    except Exception as exc:
        print(f"⚠️ 笔记 {note_id} 评论采集失败: {exc}")
        raw_items, self_id, is_truncated = [], "", False
    if is_truncated:
        truncated.append(note_id)
    comments[note_id] = _filter_comments(raw_items, self_id)
    _report(progress, "comments", index, total, f"已同步 {index}/{total}")
    await asyncio.sleep(1)


async def fetch_xiaohongshu_comments(account_file, progress=None):
    """采集账号下所有笔记与一级评论，返回作品、评论与截断作品列表。"""
    async with _xhs_page(account_file) as page:
        _report(progress, "works", 0, 0, "正在获取小红书笔记列表")
        raw_notes = await _collect_works(page)
        works = [normalize_work(note) for note in raw_notes]
        targets = [work for work in works if work["commentCount"] > 0]
        total = len(targets)
        comments = {}
        truncated = []
        for index, work in enumerate(targets, start=1):
            await _sync_work(page, work, index, total, progress, comments, truncated)
        return {
            "works": works,
            "comments": comments,
            "truncatedPosts": truncated,
        }


async def _locate_comment(page, comment_id, max_pages=MAX_COMMENT_PAGES):
    """评论项带 id=comment-xxx；不在首批时滚动评论区继续找。"""
    locator = page.locator(f"#comment-{comment_id}")
    for _ in range(max_pages):
        if await locator.count():
            return locator.first
        await page.mouse.wheel(0, 1400)
        await asyncio.sleep(2)
    raise CommentNotFoundError("未在评论列表中找到该评论")


async def _is_liked(item):
    """小红书用 use 图标的 href 区分状态：#liked 为已赞，其余为未赞。"""
    icon = item.locator(".like-wrapper svg use").first
    if await icon.count() == 0:
        return False
    href = await icon.get_attribute("href") or ""
    return "liked" in href


async def _wait_liked(item):
    for _ in range(10):
        if await _is_liked(item):
            return True
        await asyncio.sleep(0.5)
    return False


async def _open_note_page(page, note_url):
    await page.goto(note_url, wait_until="domcontentloaded", timeout=60000)
    await asyncio.sleep(8)


async def like_xiaohongshu_comment(account_file, note_url, platform_comment_id,
                                   content="", author="", max_pages=0):
    """给指定评论点赞；已点赞时直接返回，不会取消赞。"""
    async with _xhs_page(account_file) as page:
        await _open_note_page(page, note_url)
        item = await _locate_comment(page, platform_comment_id)
        if await _is_liked(item):
            return {"clicked": False, "liked": True}
        await item.locator(".like-wrapper").first.click()
        return {"clicked": True, "liked": await _wait_liked(item)}


async def _wait_reply_result(done, timeout=20):
    try:
        await asyncio.wait_for(done.wait(), timeout=timeout)
        return True
    except asyncio.TimeoutError:
        return False


async def reply_xiaohongshu_comment(account_file, note_url, platform_comment_id,
                                    text, content="", author="", max_pages=0):
    """在公开笔记页回复一级评论；以评论发布接口的返回为准。"""
    async with _xhs_page(account_file) as page:
        result = {}
        done = asyncio.Event()

        async def on_response(response):
            if REPLY_API_KEY not in response.url or done.is_set():
                return
            try:
                result["payload"] = await response.json()
            except Exception:
                return
            done.set()

        handler = lambda response: asyncio.create_task(on_response(response))
        page.on("response", handler)
        try:
            await _open_note_page(page, note_url)
            item = await _locate_comment(page, platform_comment_id)
            await item.locator(".reply").first.click()
            await asyncio.sleep(1)
            editor = page.locator("p.content-input").first
            await editor.click()
            await page.keyboard.type(text)
            await asyncio.sleep(1)
            await page.locator("button.btn.submit").first.click()
            await _wait_reply_result(done)
        finally:
            page.remove_listener("response", handler)

        payload = result.get("payload") or {}
        if payload.get("code") == 0 and payload.get("success"):
            return {"result": 1}
        message = payload.get("msg") or "回复状态未确认，请到平台确认"
        return {"result": 0, "message": message}
