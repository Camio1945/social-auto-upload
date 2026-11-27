"""视频号评论采集与操作：复用登录 Cookie 直连创作者中心评论接口。

评论页内容在闭合 shadow DOM 中，页面控件无法定位，因此这里只借用
patchright 的请求上下文（自动携带登录 Cookie）调用未签名的接口。
"""
import asyncio
import json
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from patchright.async_api import async_playwright

from conf import get_browser_options
from myUtils.douyin_comment import CommentNotFoundError
from utils.base_social_media import set_init_script

API_BASE = (
    "https://channels.weixin.qq.com/micro/interaction/cgi-bin/mmfinderassistant-bin"
)
COMMENT_REFERER = "https://channels.weixin.qq.com/micro/interaction/comment"
# 单个作品最多翻 20 页评论，与前端提示文案保持一致
MAX_COMMENT_PAGES = 20


def _format_time(timestamp):
    """视频号时间戳是秒（评论里是秒字符串），统一转成本地时间字符串。"""
    try:
        return datetime.fromtimestamp(int(timestamp)).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return None


def _now_ms():
    return str(int(time.time() * 1000))


def _first_media(desc):
    media = (desc or {}).get("media") or []
    return media[0] if media else {}


def _work_title(desc):
    """作品标题优先取正文首段，没有正文时退回短标题。"""
    title = ((desc or {}).get("description") or "").strip()
    if title:
        return title.replace("\n", " ").strip()
    shorts = (desc or {}).get("shortTitle") or [{}]
    return (shorts[0].get("shortTitle") or "").strip()


def normalize_work(item):
    desc = item.get("desc") or {}
    media = _first_media(desc)
    return {
        "platformPostId": str(item.get("exportId") or ""),
        "title": _work_title(desc),
        "coverUrl": media.get("coverUrl") or media.get("thumbUrl") or "",
        "shareUrl": "",
        "commentCount": int(item.get("commentCount") or 0),
        "publishedAt": _format_time(item.get("createTime")),
    }


def normalize_comment(item):
    return {
        "platformCommentId": str(item.get("commentId") or ""),
        "authorId": "",
        "authorName": item.get("commentNickname") or "",
        "authorAvatar": item.get("commentHeadurl") or "",
        "content": item.get("commentContent") or "",
        "likeCount": int(item.get("commentLikeCount") or 0),
        "replyCount": len(item.get("levelTwoComment") or []),
        "ipLabel": "",
        "platformCreatedAt": _format_time(item.get("commentCreatetime")),
        "userDigged": 1 if int(item.get("likeFlag") or 0) else 0,
    }


def _filter_comments(raw_items, finder_id):
    """只保留一级评论，并过滤掉账号自己发出的评论。"""
    result = []
    for item in raw_items:
        comment = normalize_comment(item)
        if not comment["platformCommentId"]:
            continue
        if finder_id and item.get("username") == finder_id:
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


class WechatAuthError(RuntimeError):
    """登录态明确失效（接口正常返回但缺少 finderUsername），与请求异常区分。"""


class WechatCommentClient:
    """基于登录 Cookie 的直连接口客户端；写操作前都会先读远端状态。"""

    def __init__(self, context):
        self._context = context
        self._headers = {}
        self.finder_id = ""

    async def _init_headers(self):
        cookies = await self._context.cookies()
        uin = next((c["value"] for c in cookies if c["name"] == "wxuin"), "")
        self._headers = {
            "content-type": "application/json",
            "origin": "https://channels.weixin.qq.com",
            "referer": COMMENT_REFERER,
            "x-wechat-uin": uin,
        }

    async def post(self, path, body):
        payload = {
            "timestamp": _now_ms(),
            "_log_finder_uin": "",
            "_log_finder_id": self.finder_id,
            "rawKeyBuff": "",
            "pluginSessionId": None,
            "reqScene": 7,
        }
        payload.update(body)
        response = await self._context.request.post(
            API_BASE + path, headers=self._headers, data=json.dumps(payload)
        )
        if not response.ok:
            raise RuntimeError(f"视频号接口请求失败：HTTP {response.status}")
        data = await response.json()
        if data.get("errCode") not in (0, None):
            message = data.get("errMsg") or f"errCode={data.get('errCode')}"
            raise RuntimeError(f"视频号接口返回异常：{message}")
        return data.get("data") or {}

    async def connect(self):
        await self._init_headers()
        data = await self.post("/auth/auth_data", {})
        finder_id = (data.get("finderUser") or {}).get("finderUsername") or ""
        if not finder_id:
            raise WechatAuthError("视频号登录态无效，请重新登录后再试")
        self.finder_id = finder_id
        return self

    async def list_works(self, max_pages=MAX_COMMENT_PAGES):
        works, last_buff = [], ""
        for _ in range(max_pages):
            data = await self.post("/post/post_list", {
                "pageSize": 10,
                "onlyUnread": False,
                "needAllCommentCount": True,
                "userpageType": 13,
                "forMcn": False,
                "lastBuff": last_buff,
                "scene": 7,
            })
            works.extend(data.get("list") or [])
            last_buff = data.get("lastBuff") or ""
            if not data.get("continueFlag") or not last_buff:
                break
        return works

    async def list_comments(self, export_id, max_pages=MAX_COMMENT_PAGES):
        """返回 (评论列表, 是否因翻页上限被截断)。"""
        comments, last_buff = [], ""
        for _ in range(max_pages):
            data = await self.post("/comment/comment_list", {
                "lastBuff": last_buff,
                "exportId": export_id,
                "commentSelection": False,
                "forMcn": False,
                "scene": 7,
            })
            comments.extend(data.get("comment") or [])
            last_buff = data.get("lastBuff") or ""
            if not data.get("downContinueFlag") or not last_buff:
                return comments, False
        return comments, True

    async def like_comment(self, export_id, comment_id):
        """点赞接口是切换式：调用前必须确认远端 likeFlag 为 0。"""
        return await self.post("/comment/like_comment", {
            "commentId": comment_id,
            "scene": 1,
            "exportId": export_id,
        })

    async def create_comment(self, export_id, comment, text):
        comment_id = str(comment.get("commentId") or "")
        return await self.post("/comment/create_comment", {
            "replyCommentId": comment_id,
            "rootCommentId": comment_id,
            "content": text,
            "clientId": str(uuid.uuid4()),
            "comment": comment,
            "exportId": export_id,
        })


@asynccontextmanager
async def _wechat_client(account_file):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(**get_browser_options())
        context = await browser.new_context(storage_state=str(account_file))
        context = await set_init_script(context)
        try:
            yield await WechatCommentClient(context).connect()
        finally:
            await browser.close()


async def _find_comment(client, export_id, comment_id):
    """按 commentId 在远端一级评论里定位目标，找不到时抛错。"""
    raw_items, _ = await client.list_comments(export_id)
    for item in raw_items:
        if str(item.get("commentId")) == str(comment_id):
            return item
    raise CommentNotFoundError("未在评论列表中找到该评论")


async def _sync_work(client, work, index, total, progress, comments, truncated):
    post_id = work["platformPostId"]
    _report(progress, "comments", index - 1, total, f"正在同步作品 {index}/{total}")
    try:
        raw_items, is_truncated = await client.list_comments(post_id)
    except Exception as exc:
        print(f"⚠️ 作品 {post_id} 评论采集失败: {exc}")
        raw_items, is_truncated = [], False
    if is_truncated:
        truncated.append(post_id)
    comments[post_id] = _filter_comments(raw_items, client.finder_id)
    _report(progress, "comments", index, total, f"已同步 {index}/{total}")


async def fetch_wechat_comments(account_file, progress=None):
    """采集账号下所有作品与一级评论，返回作品、评论与截断作品列表。"""
    async with _wechat_client(account_file) as client:
        _report(progress, "works", 0, 0, "正在获取视频号作品列表")
        raw_works = await client.list_works()
        works = [normalize_work(item) for item in raw_works]
        targets = [item for item in works if item["commentCount"] > 0]
        total = len(targets)
        comments = {}
        truncated = []
        for index, work in enumerate(targets, start=1):
            await _sync_work(
                client, work, index, total, progress, comments, truncated
            )
            await asyncio.sleep(0.5)
        return {
            "works": works,
            "comments": comments,
            "truncatedPosts": truncated,
        }


async def like_wechat_comment(account_file, platform_post_id, platform_comment_id,
                              content="", author="", max_pages=0):
    """给指定评论点赞；远端已点赞时直接返回，不会取消赞。"""
    async with _wechat_client(account_file) as client:
        item = await _find_comment(client, platform_post_id, platform_comment_id)
        if int(item.get("likeFlag") or 0) == 1:
            return {"clicked": False, "liked": True}
        await client.like_comment(platform_post_id, platform_comment_id)
        refreshed = await _find_comment(client, platform_post_id, platform_comment_id)
        return {"clicked": True, "liked": int(refreshed.get("likeFlag") or 0) == 1}


async def reply_wechat_comment(account_file, platform_post_id, platform_comment_id,
                               text, content="", author="", max_pages=0):
    """调用创建评论接口回复一级评论；用二级评论数变化确认结果。"""
    async with _wechat_client(account_file) as client:
        item = await _find_comment(client, platform_post_id, platform_comment_id)
        before = len(item.get("levelTwoComment") or [])
        await client.create_comment(platform_post_id, item, text)
        refreshed = await _find_comment(client, platform_post_id, platform_comment_id)
        if len(refreshed.get("levelTwoComment") or []) > before:
            return {"result": 1}
        return {"result": 0, "message": "回复状态未确认，请到平台确认"}
