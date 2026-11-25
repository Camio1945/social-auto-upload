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
WORK_MANAGE_URL = "https://creator.douyin.com/creator-micro/content/manage"
WORK_DETAIL_URL = (
    "https://creator.douyin.com/creator-micro/work-management/work-detail/"
    "{aweme_id}?enter_from=content&tabKey=commentManagement"
)


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


async def _collect_comments(page, aweme_id, timeout=25):
    """打开作品详情页，捕获该作品的评论列表响应；失败时返回空。"""
    result = {}
    done = asyncio.Event()

    async def on_response(response):
        if COMMENT_LIST_KEY not in response.url or done.is_set():
            return
        if f"aweme_id={aweme_id}" not in response.url:
            return
        try:
            result["payload"] = await response.json()
        except Exception:
            return
        done.set()

    handler = lambda response: asyncio.create_task(on_response(response))
    page.on("response", handler)
    try:
        await page.goto(
            WORK_DETAIL_URL.format(aweme_id=aweme_id),
            wait_until="domcontentloaded",
            timeout=60000,
        )
        try:
            await asyncio.wait_for(done.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass
    finally:
        page.remove_listener("response", handler)
    return result.get("payload") or {}


async def fetch_douyin_comments(account_file, progress=None):
    """采集账号下所有作品与一级评论。

    返回 {"works": [...], "comments": {platformPostId: [...]}}，已过滤自己发出的评论。
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
            for index, work in enumerate(targets, start=1):
                _report(progress, "comments", index - 1, total,
                        f"正在同步作品 {index}/{total}")
                try:
                    payload = await _collect_comments(page, work["platformPostId"])
                except Exception as exc:
                    print(f"⚠️ 作品 {work['platformPostId']} 评论采集失败: {exc}")
                    payload = {}

                normalized = []
                for item in payload.get("comments") or []:
                    comment = normalize_comment(item)
                    if not comment["platformCommentId"]:
                        continue
                    if self_uid and comment["authorId"] == self_uid:
                        continue
                    normalized.append(comment)
                comments[work["platformPostId"]] = normalized
                _report(progress, "comments", index, total, f"已同步 {index}/{total}")
                await asyncio.sleep(1)

            return {"works": works, "comments": comments}
        finally:
            await browser.close()
