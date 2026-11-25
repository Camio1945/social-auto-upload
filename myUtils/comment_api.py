"""评论管理接口：抖音评论同步、聚合查询与已处理标记。"""
import asyncio
import sqlite3
import threading
from pathlib import Path

from flask import Blueprint, jsonify, request

from conf import BASE_DIR
from db.createTable import ensure_comment_tables
from myUtils.comment_platforms import DOUYIN_TYPE, PLATFORMS
from myUtils.comment_query import build_comment_query, load_comment_rows
from myUtils.comment_store import mark_handled, mark_liked, now_str, save_result
from myUtils.douyin_comment import MAX_COMMENT_PAGES, CommentNotFoundError

comment_bp = Blueprint("comment", __name__)

DB_PATH = Path(BASE_DIR / "db" / "database.db")
REPLY_MAX_LENGTH = 200

# 同步任务状态：同一时间只允许一个同步任务
_sync_lock = threading.Lock()
_sync_state = {
    "running": False,
    "type": None,
    "phase": "",
    "current": 0,
    "total": 0,
    "message": "",
    "error": None,
    "truncated": [],
    "startedAt": None,
    "finishedAt": None,
}

# 回复与点赞都是写操作，共用一个锁，避免并发打开浏览器
_write_lock = threading.Lock()


def _connect():
    return sqlite3.connect(DB_PATH, timeout=30)


def _ensure_schema():
    """后端启动时确保评论相关表存在，避免依赖手动执行建库脚本。"""
    with _connect() as conn:
        ensure_comment_tables(conn.cursor())
        conn.commit()


def _update_state(**kwargs):
    with _sync_lock:
        _sync_state.update(kwargs)


def _resolve_account(account_id, platform_type=DOUYIN_TYPE):
    """按 id 取指定平台账号；未指定时取该平台第一个账号。"""
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        if account_id:
            row = conn.execute(
                "SELECT id, filePath, userName FROM user_info WHERE id = ? AND type = ?",
                (account_id, platform_type),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id, filePath, userName FROM user_info WHERE type = ? ORDER BY id LIMIT 1",
                (platform_type,),
            ).fetchone()
    return dict(row) if row else None


def _on_progress(info):
    _update_state(
        phase=info["phase"],
        current=info["current"],
        total=info["total"],
        message=info["message"],
    )


def _sync_worker(account, platform_type):
    platform = PLATFORMS[platform_type]
    try:
        account_file = Path(BASE_DIR / "cookiesFile" / account["filePath"])
        result = asyncio.run(platform["fetch"](account_file, _on_progress))
        processed = save_result(account["id"], platform_type, result)
        truncated = result.get("truncatedPosts") or []
        message = f"同步完成，处理评论 {processed} 条"
        if truncated:
            message += f"；{len(truncated)} 个作品评论超过 {MAX_COMMENT_PAGES} 页已截断"
        _update_state(
            running=False,
            phase="done",
            message=message,
            truncated=truncated,
            finishedAt=now_str(),
        )
    except Exception as exc:
        print(f"同步{platform['name']}评论失败: {exc}")
        _update_state(
            running=False,
            phase="error",
            message=f"同步失败: {exc}",
            error=str(exc),
            finishedAt=now_str(),
        )


@comment_bp.route('/syncComments', methods=['POST'])
def sync_comments():
    data = request.get_json(silent=True) or {}
    platform_type = data.get("type", DOUYIN_TYPE)
    platform = PLATFORMS.get(platform_type)
    if not platform:
        return jsonify({"code": 400, "msg": "暂不支持该平台的评论同步", "data": None}), 400

    account = _resolve_account(data.get("accountId"), platform_type)
    if not account:
        return jsonify({
            "code": 404,
            "msg": f"未找到{platform['name']}账号，请先在账号管理中登录",
            "data": None,
        }), 404

    with _sync_lock:
        if _sync_state["running"]:
            return jsonify({"code": 200, "msg": "同步任务已在进行中", "data": None}), 200
        _sync_state.update(
            running=True,
            type=platform_type,
            phase="starting",
            current=0,
            total=0,
            message="正在启动同步",
            error=None,
            truncated=[],
            startedAt=now_str(),
            finishedAt=None,
        )

    threading.Thread(
        target=_sync_worker, args=(account, platform_type), daemon=True
    ).start()
    return jsonify({"code": 200, "msg": "同步任务已启动", "data": None}), 200


@comment_bp.route('/getCommentSyncStatus', methods=['GET'])
def get_sync_status():
    with _sync_lock:
        state = dict(_sync_state)
    return jsonify({"code": 200, "msg": None, "data": state}), 200


@comment_bp.route('/getComments', methods=['GET'])
def get_comments():
    """返回评论列表与作品列表；作品列表用于前端筛选和显示未处理数。"""
    platform_type = request.args.get('type', default=DOUYIN_TYPE, type=int)
    handled = request.args.get('handled', default='')
    post_id = request.args.get('postId', type=int)
    limit = request.args.get('limit', default=500, type=int)
    sql, params = build_comment_query(platform_type, handled, post_id, limit)

    try:
        comments, posts = load_comment_rows(platform_type, sql, params)
        return jsonify({
            "code": 200,
            "msg": None,
            "data": {"comments": comments, "posts": posts},
        }), 200
    except Exception as exc:
        print(f"获取评论失败: {exc}")
        return jsonify({"code": 500, "msg": f"获取评论失败: {exc}", "data": None}), 500


@comment_bp.route('/markCommentHandled', methods=['POST'])
def mark_comment_handled():
    data = request.get_json(silent=True) or {}
    comment_id = data.get("id")
    if not isinstance(comment_id, int):
        return jsonify({"code": 400, "msg": "评论 id 无效", "data": None}), 400

    handled = 1 if data.get("handled") else 0
    handled_at = now_str() if handled else None
    try:
        with _connect() as conn:
            cursor = conn.execute(
                "UPDATE comment SET isHandled = ?, handledAt = ? WHERE id = ?",
                (handled, handled_at, comment_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return jsonify({"code": 404, "msg": "评论不存在", "data": None}), 404
        return jsonify({
            "code": 200,
            "msg": None,
            "data": {"id": comment_id, "isHandled": handled, "handledAt": handled_at},
        }), 200
    except Exception as exc:
        print(f"更新评论状态失败: {exc}")
        return jsonify({"code": 500, "msg": f"更新评论状态失败: {exc}", "data": None}), 500


def _validate_reply_text(text):
    """回复只允许单行纯文本：不换行、不 @ 人、不超过 200 字。"""
    text = (text or "").strip()
    if not text:
        return None, "回复内容不能为空"
    if len(text) > REPLY_MAX_LENGTH:
        return None, f"回复内容不能超过 {REPLY_MAX_LENGTH} 个字符"
    if "\n" in text or "\r" in text:
        return None, "回复内容不能换行"
    if "@" in text:
        return None, "回复内容暂不支持 @ 用户"
    return text, None


def _load_comment_target(comment_id):
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            '''
            SELECT c.id, c.type, c.platformCommentId, c.content, c.authorName,
                   c.userDigged, p.platformPostId, p.shareUrl
            FROM comment c
            JOIN platform_post p ON p.id = c.postId
            WHERE c.id = ?
            ''',
            (comment_id,),
        ).fetchone()
    return dict(row) if row else None


def _account_file(account):
    return Path(BASE_DIR / "cookiesFile" / account["filePath"])


def _run_reply(platform, account, target, text):
    payload = asyncio.run(platform["reply"](_account_file(account), target, text))
    return platform["parse_reply"](payload)


def _run_like(platform, account, target):
    result = asyncio.run(platform["like"](_account_file(account), target))
    return result.get("liked")


@comment_bp.route('/replyComment', methods=['POST'])
def reply_comment():
    """通过页面 UI 回复评论，成功后自动标记已处理。"""
    data = request.get_json(silent=True) or {}
    comment_id = data.get("id")
    if not isinstance(comment_id, int):
        return jsonify({"code": 400, "msg": "评论 id 无效", "data": None}), 400

    text, error = _validate_reply_text(data.get("text"))
    if error:
        return jsonify({"code": 400, "msg": error, "data": None}), 400

    target = _load_comment_target(comment_id)
    if not target:
        return jsonify({"code": 404, "msg": "评论不存在", "data": None}), 404
    platform = PLATFORMS.get(target["type"])
    if not platform:
        return jsonify({"code": 400, "msg": "暂不支持该平台的评论回复", "data": None}), 400

    account = _resolve_account(None, target["type"])
    if not account:
        return jsonify({
            "code": 404,
            "msg": f"未找到{platform['name']}账号，请先在账号管理中登录",
            "data": None,
        }), 404
    if not _write_lock.acquire(blocking=False):
        return jsonify({"code": 409, "msg": "已有操作正在执行，请稍后重试", "data": None}), 409

    try:
        ok, message = _run_reply(platform, account, target, text)
        if not ok:
            return jsonify({"code": 502, "msg": message, "data": None}), 502
        handled_at = mark_handled(comment_id)
        return jsonify({
            "code": 200,
            "msg": "回复成功",
            "data": {"id": comment_id, "isHandled": 1, "handledAt": handled_at},
        }), 200
    except CommentNotFoundError as exc:
        return jsonify({"code": 404, "msg": str(exc), "data": None}), 404
    except Exception as exc:
        print(f"回复评论失败: {exc}")
        return jsonify({"code": 500, "msg": f"回复失败: {exc}", "data": None}), 500
    finally:
        _write_lock.release()


@comment_bp.route('/likeComment', methods=['POST'])
def like_comment():
    """给指定评论点赞；已点赞的评论直接返回，不会取消赞。"""
    data = request.get_json(silent=True) or {}
    comment_id = data.get("id")
    if not isinstance(comment_id, int):
        return jsonify({"code": 400, "msg": "评论 id 无效", "data": None}), 400

    target = _load_comment_target(comment_id)
    if not target:
        return jsonify({"code": 404, "msg": "评论不存在", "data": None}), 404
    platform = PLATFORMS.get(target["type"])
    if not platform:
        return jsonify({"code": 400, "msg": "暂不支持该平台的评论点赞", "data": None}), 400
    if target["userDigged"]:
        payload = {"id": comment_id, "userDigged": 1}
        return jsonify({"code": 200, "msg": "该评论已点赞", "data": payload}), 200

    account = _resolve_account(None, target["type"])
    if not account:
        message = f"未找到{platform['name']}账号，请先在账号管理中登录"
        return jsonify({"code": 404, "msg": message, "data": None}), 404
    if not _write_lock.acquire(blocking=False):
        return jsonify({"code": 409, "msg": "已有操作正在执行，请稍后重试", "data": None}), 409

    try:
        if not _run_like(platform, account, target):
            return jsonify({
                "code": 502,
                "msg": "点赞状态未确认，请先同步评论后再试",
                "data": None,
            }), 502
        mark_liked(comment_id)
        return jsonify({
            "code": 200, "msg": "点赞成功",
            "data": {"id": comment_id, "userDigged": 1},
        }), 200
    except CommentNotFoundError as exc:
        return jsonify({"code": 404, "msg": str(exc), "data": None}), 404
    except Exception as exc:
        print(f"点赞评论失败: {exc}")
        return jsonify({"code": 500, "msg": f"点赞失败: {exc}", "data": None}), 500
    finally:
        _write_lock.release()


_ensure_schema()
