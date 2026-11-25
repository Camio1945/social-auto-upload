"""抖音评论采集：打开创作者中心页面，拦截作品列表与评论列表接口的原始响应。

不解析 DOM，也不复刻签名：签名由页面自身的脚本生成，这里只读取接口返回的 JSON。
"""
import asyncio
import re
import time
from contextlib import asynccontextmanager
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
# 正文里的 emoji 在页面上会拆成图片或占位符，定位前先剔除再取前缀
EMOJI_PATTERN = re.compile(r"\[[^\]]{1,8}\]|[\U00010000-\U0010FFFF]|[\u2600-\u27BF]")
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


def _text_probes(content):
    """生成用于文本定位的候选前缀，优先使用剔除 emoji 后的短前缀。"""
    text = (content or "").strip()
    cleaned = EMOJI_PATTERN.sub("", text).strip()
    probes = []
    for probe in (cleaned[:10], text[:20], text):
        probe = probe.strip()
        if len(probe) >= 2 and probe not in probes:
            probes.append(probe)
    return probes


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
    avatar = _first_url(user.get("avatar_thumb")) or _first_url(user.get("avatar_large"))
    return {
        "platformCommentId": str(item.get("cid") or ""),
        "authorId": str(user.get("uid") or ""),
        "authorName": user.get("nickname") or "",
        "authorAvatar": avatar,
        "content": item.get("text") or "",
        "likeCount": int(item.get("digg_count") or 0),
        "replyCount": int(item.get("reply_comment_total") or 0),
        "ipLabel": item.get("ip_label") or "",
        "platformCreatedAt": _format_time(item.get("create_time")),
        "userDigged": 1 if item.get("user_digged") else 0,
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


@asynccontextmanager
async def _browser_page(account_file):
    """统一的浏览器上下文：加载登录态并注入 stealth 脚本。"""
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


async def _goto_comment_page(page, platform_post_id):
    await page.goto(
        WORK_DETAIL_URL.format(aweme_id=platform_post_id),
        wait_until="domcontentloaded",
        timeout=60000,
    )


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


def _comment_response_handler(collected, state, changed, aweme_id):
    """构造评论列表响应处理器：合并每页评论并更新 has_more。"""

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

    return on_response


async def _scroll_comment_pages(page, changed, collected, state, aweme_id, max_pages):
    """滚动评论区直到没有更多数据、没有新内容或达到页数上限。"""
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


async def _collect_comments(page, aweme_id, max_pages=MAX_COMMENT_PAGES):
    """打开作品详情页并滚动翻页，返回 (评论列表, 是否被截断)。"""
    collected = {}
    state = {"has_more": 1}
    changed = asyncio.Event()
    on_response = _comment_response_handler(collected, state, changed, aweme_id)
    handler = lambda response: asyncio.create_task(on_response(response))
    page.on("response", handler)
    try:
        await _goto_comment_page(page, aweme_id)
        if not await _wait_signal(changed, timeout=25):
            return [], False
        await _scroll_comment_pages(page, changed, collected, state, aweme_id, max_pages)
    finally:
        page.remove_listener("response", handler)
    return list(collected.values()), state["has_more"] not in (0, False)


async def _comment_item(page, content, author):
    """按正文定位评论项；同一作者存在多条相似评论时拒绝猜测。"""
    ambiguous = False
    for probe in _text_probes(content):
        matched = {}
        nodes = page.get_by_text(probe, exact=False)
        for index in range(min(await nodes.count(), 8)):
            item = nodes.nth(index).locator(COMMENT_ITEM_XPATH)
            if not await item.count():
                continue
            item = item.first
            if author and author not in await item.inner_text():
                continue
            key = await item.evaluate(
                "el => {"
                "  if (!el.dataset.sauKey) {"
                "    el.dataset.sauKey = Math.random().toString(36).slice(2);"
                "  }"
                "  return el.dataset.sauKey;"
                "}"
            )
            matched.setdefault(key, item)
        if len(matched) == 1:
            return next(iter(matched.values()))
        if len(matched) > 1:
            ambiguous = True
    if ambiguous:
        raise CommentNotFoundError("存在多条相似评论，无法精确定位，请到平台手动处理")
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


async def _submit_reply(page, item):
    """点击发送并捕获 multi_publish 响应。"""
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


async def reply_douyin_comment(account_file, platform_post_id, content, author, text,
                               max_pages=MAX_COMMENT_PAGES):
    """通过页面 UI 回复指定评论，返回 multi_publish 接口的原始响应。"""
    async with _browser_page(account_file) as page:
        await _goto_comment_page(page, platform_post_id)
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
        return await _submit_reply(page, item)


async def _wait_like_active(button):
    """等待红心进入已赞状态；超时后再补查一次，避免误判失败。"""
    try:
        await button.locator("[class*='active-']").first.wait_for(timeout=5000)
        return True
    except Exception:
        await asyncio.sleep(2)
        return await button.locator("[class*='active-']").count() > 0


async def like_douyin_comment(account_file, platform_post_id, content, author,
                              max_pages=MAX_COMMENT_PAGES):
    """通过页面 UI 给指定评论点赞；已点赞时直接返回，不会取消赞。"""
    async with _browser_page(account_file) as page:
        await _goto_comment_page(page, platform_post_id)
        await asyncio.sleep(6)
        item = await _locate_comment_item(page, content, author, max_pages)
        if item is None:
            raise CommentNotFoundError("未在页面上找到目标评论")

        button = item.locator("[class*='operations-'] button").first
        if await button.count() == 0:
            raise CommentNotFoundError("未找到点赞按钮")
        if await button.locator("[class*='active-']").count() > 0:
            return {"clicked": False, "liked": True}
        await button.click()
        return {"clicked": True, "liked": await _wait_like_active(button)}


def _filter_own_comments(raw_comments, self_uid):
    normalized = []
    for item in raw_comments:
        comment = normalize_comment(item)
        if not comment["platformCommentId"]:
            continue
        if self_uid and comment["authorId"] == self_uid:
            continue
        normalized.append(comment)
    return normalized


async def _sync_single_work(page, work, index, total, progress, self_uid,
                            comments, truncated_posts):
    platform_post_id = work["platformPostId"]
    _report(progress, "comments", index - 1, total, f"正在同步作品 {index}/{total}")
    try:
        raw_comments, truncated = await _collect_comments(page, platform_post_id)
    except Exception as exc:
        print(f"⚠️ 作品 {platform_post_id} 评论采集失败: {exc}")
        raw_comments, truncated = [], False
    if truncated:
        truncated_posts.append(platform_post_id)
    comments[platform_post_id] = _filter_own_comments(raw_comments, self_uid)
    _report(progress, "comments", index, total, f"已同步 {index}/{total}")
    await asyncio.sleep(1)


async def fetch_douyin_comments(account_file, progress=None):
    """采集账号下所有作品与一级评论，返回作品、评论与截断作品列表。"""
    async with _browser_page(account_file) as page:
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
            await _sync_single_work(
                page, work, index, total, progress, self_uid, comments, truncated_posts
            )
        return {
            "works": works,
            "comments": comments,
            "truncatedPosts": truncated_posts,
        }
