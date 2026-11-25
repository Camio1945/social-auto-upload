"""抖音评论采集：打开创作者中心页面，拦截作品列表与评论列表接口的原始响应。

不解析 DOM，也不复刻签名：签名由页面自身的脚本生成，这里只读取接口返回的 JSON。
"""
import asyncio
import time
from datetime import datetime

from patchright.async_api import async_playwright

from conf import get_browser_options
from utils.base_social_media import set_init_script

WORK_LIST_KEY = "janus/douyin/creator/pc/work_list"
COMMENT_LIST_KEY = "comment/list/select"
REPLY_API_KEY = "comment/multi_publish"
COMMENT_ITEM_XPATH = "xpath=ancestor::*[.//button[normalize-space(.)='回复']][1]"
WORK_MANAGE_URL = "https://creator.douyin.com/creator-micro/content/manage"
WORK_DETAIL_URL = (
    "https://creator.douyin.com/creator-micro/work-management/work-detail/"
    "{aweme_id}?enter_from=content&tabKey=commentManagement"
)

# 单个作品最多翻 20 页；连续几轮滚动没有新数据就认为到底了
MAX_COMMENT_PAGES = 20
SCROLL_IDLE_ROUNDS = 3
SCROLL_JS = '''
() => {
  const nodes = Array.from(document.querySelectorAll('div, section, main, ul'));
  let scrolled = 0;
  for (const el of nodes) {
    const style = getComputedStyle(el);
    if (/(auto|scroll)/.test(style.overflowY) && el.scrollHeight > el.clientHeight + 40) {
      el.scrollTop = el.scrollHeight;
      scrolled += 1;
    }
  }
  return scrolled;
}
'''


def _format_time(timestamp):
    """平台时间戳（秒）转本地时间字符串，跨库排序与展示都用这个格式。"""
    try:
        return datetime.fromtimestamp(int(timestamp)).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return None


def _first_url(image):
    if not isinstance(image, dict):
        return ""
    urls = image.get("url_list") or []
    return urls[0] if urls else ""


def normalize_work(item):
    """把作品原始 JSON 转成入库字段；接口里封面字段名存在大小写两种写法。"""
    stats = item.get("statistics") or {}
    return {
        "platformPostId": str(item.get("aweme_id") or ""),
        "title": item.get("desc") or "",
        "coverUrl": _first_url(item.get("Cover") or item.get("cover")),
        "shareUrl": item.get("share_url") or "",
        "commentCount": int(stats.get("comment_count") or 0),
        "publishedAt": _format_time(item.get("create_time")),
    }


def normalize_comment(item):
    """把评论原始 JSON 转成入库字段。"""
    user = item.get("user") or {}
    return {
        "platformCommentId": str(item.get("cid") or ""),
        "authorId": str(user.get("uid") or ""),
        "authorName": user.get("nickname") or "",
        "authorAvatar": _first_url(user.get("avatar_thumb")) or _first_url(user.get("avatar_large")),
        "content": item.get("text") or "",
        "likeCount": int(item.get("digg_count") or 0),
        "replyCount": int(item.get("reply_comment_total") or 0),
        "ipLabel": item.get("ip_label") or "",
        "platformCreatedAt": _format_time(item.get("create_time")),
    }


class CommentNotFoundError(Exception):
    """目标评论未出现在作品页面上。"""


def _report(progress, phase, current, total, message):
    if progress:
        progress({
            "phase": phase,
            "current": current,
            "total": total,
            "message": message,
        })


async def _collect_work_list(page, timeout=25):
    """收集所有 work_list 响应并合并：页面会先发一条 count=1 的预取请求。"""
    works = {}
    done = asyncio.Event()
    lock = asyncio.Lock()

    async def on_response(response):
        if WORK_LIST_KEY not in response.url:
            return
        try:
            payload = await response.json()
        except Exception:
            return
        items = payload.get("aweme_list") or []
        async with lock:
            for item in items:
                aweme_id = str(item.get("aweme_id") or "")
                if aweme_id:
                    works[aweme_id] = item
            if items and payload.get("has_more") is False:
                done.set()

    handler = lambda response: asyncio.create_task(on_response(response))
    page.on("response", handler)
    try:
        await page.goto(WORK_MANAGE_URL, wait_until="domcontentloaded", timeout=60000)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and not done.is_set():
            try:
                await page.mouse.wheel(0, 1500)
            except Exception:
                pass
            try:
                await asyncio.wait_for(done.wait(), timeout=2)
            except asyncio.TimeoutError:
                continue
    finally:
        page.remove_listener("response", handler)
    return list(works.values())


async def _wait_signal(event, timeout):
    try:
        await asyncio.wait_for(event.wait(), timeout=timeout)
        return True
    except asyncio.TimeoutError:
        return False


async def _expand_comments(page):
    """尽量触发评论区加载更多：滚动可滚动容器，并点击可能出现的「加载更多」。"""
    try:
        await page.evaluate(SCROLL_JS)
    except Exception:
        pass
    for text in ("加载更多", "查看更多", "展开更多"):
        try:
            button = page.get_by_text(text, exact=True).first
            if await button.count() and await button.is_visible():
                await button.click(timeout=2000)
        except Exception:
            continue


async def _collect_comments(page, aweme_id, max_pages=MAX_COMMENT_PAGES):
    """打开作品详情页并滚动翻页，汇总该作品所有一级评论的原始数据。

    签名由页面自行生成，这里只监听每页的 comment/list/select 响应；
    返回 (评论列表, 是否被截断)。仍有下一页却因页数上限或加载失败停止时视为截断。
    """
    collected = {}
    state = {"has_more": 1}
    changed = asyncio.Event()

    async def on_response(response):
        if COMMENT_LIST_KEY not in response.url:
            return
        if f"aweme_id={aweme_id}" not in response.url:
            return
        try:
            payload = await response.json()
        except Exception:
            return
        for item in payload.get("comments") or []:
            cid = str(item.get("cid") or "")
            if cid and cid not in collected:
                collected[cid] = item
        state["has_more"] = payload.get("has_more")
        changed.set()

    handler = lambda response: asyncio.create_task(on_response(response))
    page.on("response", handler)
    try:
        await page.goto(
            WORK_DETAIL_URL.format(aweme_id=aweme_id),
            wait_until="domcontentloaded",
            timeout=60000,
        )
        if not await _wait_signal(changed, timeout=25):
            return [], False

        pages = 1
        idle_rounds = 0
        while pages < max_pages and state["has_more"] not in (0, False):
            before = len(collected)
            changed.clear()
            await _expand_comments(page)
            if await _wait_signal(changed, timeout=8) and len(collected) > before:
                pages += 1
                idle_rounds = 0
                await asyncio.sleep(1)
                continue
            idle_rounds += 1
            if idle_rounds >= SCROLL_IDLE_ROUNDS:
                print(f"⚠️ 作品 {aweme_id} 翻页无新数据，停止在第 {pages} 页")
                break
    finally:
        page.remove_listener("response", handler)
    truncated = state["has_more"] not in (0, False)
    return list(collected.values()), truncated


async def _comment_item(page, content, author):
    """按正文定位评论项，返回包含「回复」按钮的最近容器；找不到返回 None。"""
    text = (content or "").strip()
    probes = [(text, True), (text[:20], False)]
    for probe, exact in probes:
        if not probe:
            continue
        nodes = page.get_by_text(probe, exact=exact)
        for index in range(min(await nodes.count(), 5)):
            item = nodes.nth(index).locator(COMMENT_ITEM_XPATH)
            if not await item.count():
                continue
            item = item.first
            if author and author not in await item.inner_text():
                continue
            return item
    return None


async def _locate_comment_item(page, content, author, max_pages=MAX_COMMENT_PAGES):
    """目标评论可能不在第一页，滚动查找最多 max_pages 页。"""
    for _ in range(max_pages):
        item = await _comment_item(page, content, author)
        if item is not None:
            return item
        await _expand_comments(page)
        await asyncio.sleep(2)
    return None


async def reply_douyin_comment(account_file, platform_post_id, content, author, text,
                               max_pages=MAX_COMMENT_PAGES):
    """通过页面 UI 回复指定评论，返回 multi_publish 接口的原始响应。

    走页面自身的输入框和发送按钮，签名与风控参数都由页面生成。
    """
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(**get_browser_options())
        context = await browser.new_context(
            storage_state=str(account_file),
            no_viewport=True,
        )
        context = await set_init_script(context)
        page = await context.new_page()
        try:
            await page.goto(
                WORK_DETAIL_URL.format(aweme_id=platform_post_id),
                wait_until="domcontentloaded",
                timeout=60000,
            )
            await asyncio.sleep(6)
            item = await _locate_comment_item(page, content, author, max_pages)
            if item is None:
                raise CommentNotFoundError("未在页面上找到目标评论")

            await item.get_by_role("button", name="回复", exact=True).first.click()
            await asyncio.sleep(1)
            editor = item.locator("[contenteditable='true']:visible, textarea:visible").first
            await editor.click()
            await editor.fill(text)
            await asyncio.sleep(1)

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
                await item.get_by_role("button", name="发送", exact=True).first.click()
                await _wait_signal(done, timeout=20)
            finally:
                page.remove_listener("response", handler)
            return result.get("payload") or {}
        finally:
            await browser.close()


async def fetch_douyin_comments(account_file, progress=None):
    """采集账号下所有作品与一级评论。

    返回 {"works": [...], "comments": {platformPostId: [...]}, "truncatedPosts": [...]}，
    已过滤自己发出的评论。
    """
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(**get_browser_options())
        context = await browser.new_context(
            storage_state=str(account_file),
            no_viewport=True,
        )
        context = await set_init_script(context)
        page = await context.new_page()
        try:
            _report(progress, "works", 0, 0, "正在获取作品列表")
            raw_works = await _collect_work_list(page)
            works = [normalize_work(item) for item in raw_works]
            self_uid = ""
            if raw_works:
                self_uid = str((raw_works[0].get("author") or {}).get("uid") or "")

            targets = [item for item in works if item["commentCount"] > 0]
            total = len(targets)
            comments = {}
            truncated_posts = []
            for index, work in enumerate(targets, start=1):
                _report(progress, "comments", index - 1, total,
                        f"正在同步作品 {index}/{total}")
                try:
                    raw_comments, truncated = await _collect_comments(
                        page, work["platformPostId"])
                except Exception as exc:
                    print(f"⚠️ 作品 {work['platformPostId']} 评论采集失败: {exc}")
                    raw_comments, truncated = [], False
                if truncated:
                    truncated_posts.append(work["platformPostId"])

                normalized = []
                for item in raw_comments:
                    comment = normalize_comment(item)
                    if not comment["platformCommentId"]:
                        continue
                    if self_uid and comment["authorId"] == self_uid:
                        continue
                    normalized.append(comment)
                comments[work["platformPostId"]] = normalized
                _report(progress, "comments", index, total, f"已同步 {index}/{total}")
                await asyncio.sleep(1)

            return {
                "works": works,
                "comments": comments,
                "truncatedPosts": truncated_posts,
            }
        finally:
            await browser.close()
