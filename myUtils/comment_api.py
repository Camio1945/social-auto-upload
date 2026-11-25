"""评论管理接口：抖音评论同步、聚合查询与已处理标记。"""
import asyncio
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, request

from conf import BASE_DIR
from db.createTable import ensure_comment_tables
from myUtils.douyin_comment import fetch_douyin_comments

comment_bp = Blueprint("comment", __name__)

DB_PATH = Path(BASE_DIR / "db" / "database.db")
DOUYIN_TYPE = 3

# 同步任务状态：同一时间只允许一个同步任务
_sync_lock = threading.Lock()
_sync_state = {
    "running": False,
    "phase": "",
    "current": 0,
    "total": 0,
    "message": "",
    "error": None,
    "startedAt": None,
    "finishedAt": None,
}


def _connect():
    return sqlite3.connect(DB_PATH, timeout=30)


def _now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _ensure_schema():
    """后端启动时确保评论相关表存在，避免依赖手动执行建库脚本。"""
    with _connect() as conn:
        ensure_comment_tables(conn.cursor())
        conn.commit()


def _update_state(**kwargs):
    with _sync_lock:
        _sync_state.update(kwargs)


def _resolve_account(account_id):
    """按 id 取抖音账号；未指定时取该平台第一个账号。"""
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        if account_id:
            row = conn.execute(
                "SELECT id, filePath, userName FROM user_info WHERE id = ? AND type = ?",
                (account_id, DOUYIN_TYPE),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id, filePath, userName FROM user_info WHERE type = ? ORDER BY id LIMIT 1",
                (DOUYIN_TYPE,),
            ).fetchone()
    return dict(row) if row else None


def _upsert_post(conn, account_id, work, synced_at):
    conn.execute(
        '''
        INSERT INTO platform_post
            (accountId, type, platformPostId, title, coverUrl, shareUrl,
             commentCount, publishedAt, lastSyncedAt)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(type, platformPostId) DO UPDATE SET
            accountId = excluded.accountId,
            title = excluded.title,
            coverUrl = excluded.coverUrl,
            shareUrl = excluded.shareUrl,
            commentCount = excluded.commentCount,
            publishedAt = excluded.publishedAt,
            lastSyncedAt = excluded.lastSyncedAt
        ''',
        (
            account_id, DOUYIN_TYPE, work["platformPostId"], work["title"],
            work["coverUrl"], work["shareUrl"], work["commentCount"],
            work["publishedAt"], synced_at,
        ),
    )
    row = conn.execute(
        "SELECT id FROM platform_post WHERE type = ? AND platformPostId = ?",
        (DOUYIN_TYPE, work["platformPostId"]),
    ).fetchone()
    return row[0]


def _upsert_comment(conn, post_id, comment, fetched_at):
    """只更新远端字段；isHandled / handledAt 不在此处出现，保证本地状态不被同步覆盖。"""
    conn.execute(
        '''
        INSERT INTO comment
            (postId, type, platformCommentId, authorId, authorName, authorAvatar,
             content, likeCount, replyCount, ipLabel, platformCreatedAt, fetchedAt)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(type, platformCommentId) DO UPDATE SET
            postId = excluded.postId,
            authorId = excluded.authorId,
            authorName = excluded.authorName,
            authorAvatar = excluded.authorAvatar,
            content = excluded.content,
            likeCount = excluded.likeCount,
            replyCount = excluded.replyCount,
            ipLabel = excluded.ipLabel,
            platformCreatedAt = excluded.platformCreatedAt,
            fetchedAt = excluded.fetchedAt
        ''',
        (
            post_id, DOUYIN_TYPE, comment["platformCommentId"], comment["authorId"],
            comment["authorName"], comment["authorAvatar"], comment["content"],
            comment["likeCount"], comment["replyCount"], comment["ipLabel"],
            comment["platformCreatedAt"], fetched_at,
        ),
    )


def _save_result(account_id, result):
    """把采集结果写入数据库，返回处理的评论条数。"""
    synced_at = _now_str()
    processed = 0
    with _connect() as conn:
        for work in result["works"]:
            post_id = _upsert_post(conn, account_id, work, synced_at)
            for item in result["comments"].get(work["platformPostId"], []):
                _upsert_comment(conn, post_id, item, synced_at)
                processed += 1
        conn.commit()
    return processed


def _on_progress(info):
    _update_state(
        phase=info["phase"],
        current=info["current"],
        total=info["total"],
        message=info["message"],
    )


def _sync_worker(account):
    try:
        account_file = Path(BASE_DIR / "cookiesFile" / account["filePath"])
        result = asyncio.run(fetch_douyin_comments(account_file, _on_progress))
        processed = _save_result(account["id"], result)
        _update_state(
            running=False,
            phase="done",
            message=f"同步完成，处理评论 {processed} 条",
            finishedAt=_now_str(),
        )
    except Exception as exc:
        print(f"同步抖音评论失败: {exc}")
        _update_state(
            running=False,
            phase="error",
            message=f"同步失败: {exc}",
            error=str(exc),
            finishedAt=_now_str(),
        )


@comment_bp.route('/syncComments', methods=['POST'])
def sync_comments():
    data = request.get_json(silent=True) or {}
    account = _resolve_account(data.get("accountId"))
    if not account:
        return jsonify({"code": 404, "msg": "未找到抖音账号，请先在账号管理中登录", "data": None}), 404

    with _sync_lock:
        if _sync_state["running"]:
            return jsonify({"code": 200, "msg": "同步任务已在进行中", "data": None}), 200
        _sync_state.update(
            running=True,
            phase="starting",
            current=0,
            total=0,
            message="正在启动同步",
            error=None,
            startedAt=_now_str(),
            finishedAt=None,
        )

    threading.Thread(target=_sync_worker, args=(account,), daemon=True).start()
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

    sql = '''
        SELECT c.*, p.title AS postTitle, p.coverUrl AS postCoverUrl,
               p.shareUrl AS postShareUrl, p.publishedAt AS postPublishedAt
        FROM comment c
        JOIN platform_post p ON p.id = c.postId
        WHERE c.type = ?
    '''
    params = [platform_type]
    if handled in ('0', '1'):
        sql += ' AND c.isHandled = ?'
        params.append(int(handled))
    if post_id:
        sql += ' AND c.postId = ?'
        params.append(post_id)
    sql += ' ORDER BY c.platformCreatedAt DESC, c.id DESC LIMIT ?'
    params.append(limit)

    posts_sql = '''
        SELECT p.id, p.platformPostId, p.title, p.coverUrl, p.shareUrl,
               p.commentCount, p.publishedAt, p.lastSyncedAt,
               COUNT(c.id) AS savedCount,
               SUM(CASE WHEN c.isHandled = 0 THEN 1 ELSE 0 END) AS unhandledCount
        FROM platform_post p
        LEFT JOIN comment c ON c.postId = p.id
        WHERE p.type = ?
        GROUP BY p.id
        ORDER BY p.publishedAt DESC, p.id DESC
    '''

    try:
        with _connect() as conn:
            conn.row_factory = sqlite3.Row
            comments = [dict(row) for row in conn.execute(sql, params).fetchall()]
            posts = [dict(row) for row in conn.execute(posts_sql, (platform_type,)).fetchall()]
        for post in posts:
            post['unhandledCount'] = post['unhandledCount'] or 0
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
    handled_at = _now_str() if handled else None
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


_ensure_schema()
