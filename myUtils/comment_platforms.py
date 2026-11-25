"""评论平台适配：各平台采集、点赞、回复函数与响应解析。

comment_api 只依赖这里的 PLATFORMS 注册表，新增平台时改动集中在本文件。
"""
from myUtils.douyin_comment import (
    fetch_douyin_comments,
    like_douyin_comment,
    reply_douyin_comment,
)
from myUtils.kuaishou_comment import (
    fetch_kuaishou_comments,
    like_kuaishou_comment,
    reply_kuaishou_comment,
)
from myUtils.wechat_comment import (
    fetch_wechat_comments,
    like_wechat_comment,
    reply_wechat_comment,
)
from myUtils.xiaohongshu_comment import (
    fetch_xiaohongshu_comments,
    like_xiaohongshu_comment,
    reply_xiaohongshu_comment,
)

XHS_TYPE = 1
WECHAT_TYPE = 2
DOUYIN_TYPE = 3
KUAISHOU_TYPE = 4


def _parse_reply_result(payload):
    """解析抖音 multi_publish 响应，判断回复是否成功。"""
    if not payload:
        return False, "未收到回复响应，请稍后重试"
    if payload.get("status_code") not in (0, None):
        return False, f"平台返回异常状态：{payload.get('status_code')}"
    items = payload.get("comments") or []
    if not items:
        return False, "回复未成功，请稍后重试"
    code = items[0].get("code")
    if code not in (0, None):
        return False, f"回复失败，平台返回 code={code}"
    return True, ""


def _parse_flag_result(payload):
    """解析以 result=1 表示成功的平台响应（快手、视频号、小红书）。"""
    if not payload:
        return False, "未收到回复响应，请稍后重试"
    if payload.get("result") in (1, "1"):
        return True, ""
    message = payload.get("message") or "平台返回失败"
    return False, f"回复失败：{message}"


def _reply_douyin(account_file, target, text):
    return reply_douyin_comment(
        account_file,
        target["platformPostId"],
        target["content"],
        target["authorName"],
        text,
    )


def _reply_kuaishou(account_file, target, text):
    return reply_kuaishou_comment(
        account_file,
        target["platformPostId"],
        target["platformCommentId"],
        text,
    )


def _reply_wechat(account_file, target, text):
    return reply_wechat_comment(
        account_file,
        target["platformPostId"],
        target["platformCommentId"],
        text,
    )


def _reply_xhs(account_file, target, text):
    return reply_xiaohongshu_comment(
        account_file,
        target["shareUrl"],
        target["platformCommentId"],
        text,
    )


def _like_douyin(account_file, target):
    return like_douyin_comment(
        account_file,
        target["platformPostId"],
        target["content"],
        target["authorName"],
    )


def _like_kuaishou(account_file, target):
    return like_kuaishou_comment(
        account_file,
        target["platformPostId"],
        target["platformCommentId"],
    )


def _like_wechat(account_file, target):
    return like_wechat_comment(
        account_file,
        target["platformPostId"],
        target["platformCommentId"],
    )


def _like_xhs(account_file, target):
    return like_xiaohongshu_comment(
        account_file,
        target["shareUrl"],
        target["platformCommentId"],
    )


PLATFORMS = {
    XHS_TYPE: {
        "name": "小红书",
        "fetch": fetch_xiaohongshu_comments,
        "reply": _reply_xhs,
        "like": _like_xhs,
        "parse_reply": _parse_flag_result,
    },
    WECHAT_TYPE: {
        "name": "视频号",
        "fetch": fetch_wechat_comments,
        "reply": _reply_wechat,
        "like": _like_wechat,
        "parse_reply": _parse_flag_result,
    },
    DOUYIN_TYPE: {
        "name": "抖音",
        "fetch": fetch_douyin_comments,
        "reply": _reply_douyin,
        "like": _like_douyin,
        "parse_reply": _parse_reply_result,
    },
    KUAISHOU_TYPE: {
        "name": "快手",
        "fetch": fetch_kuaishou_comments,
        "reply": _reply_kuaishou,
        "like": _like_kuaishou,
        "parse_reply": _parse_flag_result,
    },
}
