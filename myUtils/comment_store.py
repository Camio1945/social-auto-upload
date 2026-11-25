"""评论入库与本地状态更新。"""
import sqlite3
from datetime import datetime
from pathlib import Path

from conf import BASE_DIR

DB_PATH = Path(BASE_DIR / "db" / "database.db")


def _connect():
    return sqlite3.connect(DB_PATH, timeout=30)


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _upsert_post(conn, platform_type, account_id, work, synced_at):
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
            account_id, platform_type, work["platformPostId"], work["title"],
            work["coverUrl"], work["shareUrl"], work["commentCount"],
            work["publishedAt"], synced_at,
        ),
    )
    row = conn.execute(
        "SELECT id FROM platform_post WHERE type = ? AND platformPostId = ?",
        (platform_type, work["platformPostId"]),
    ).fetchone()
    return row[0]


def _upsert_comment(conn, platform_type, post_id, comment, fetched_at):
    """只更新远端字段；isHandled / handledAt 不在此处出现，保证本地状态不被同步覆盖。"""
    conn.execute(
        '''
        INSERT INTO comment
            (postId, type, platformCommentId, authorId, authorName, authorAvatar,
             content, likeCount, replyCount, ipLabel, platformCreatedAt, fetchedAt, userDigged)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            fetchedAt = excluded.fetchedAt,
            userDigged = excluded.userDigged
        ''',
        (
            post_id, platform_type, comment["platformCommentId"], comment["authorId"],
            comment["authorName"], comment["authorAvatar"], comment["content"],
            comment["likeCount"], comment["replyCount"], comment["ipLabel"],
            comment["platformCreatedAt"], fetched_at, comment["userDigged"],
        ),
    )


def save_result(account_id, platform_type, result):
    """把采集结果写入数据库，返回处理的评论条数。"""
    synced_at = now_str()
    processed = 0
    with _connect() as conn:
        for work in result["works"]:
            post_id = _upsert_post(conn, platform_type, account_id, work, synced_at)
            for item in result["comments"].get(work["platformPostId"], []):
                _upsert_comment(conn, platform_type, post_id, item, synced_at)
                processed += 1
        conn.commit()
    return processed


def mark_handled(comment_id):
    handled_at = now_str()
    with _connect() as conn:
        conn.execute(
            "UPDATE comment SET isHandled = 1, handledAt = ? WHERE id = ?",
            (handled_at, comment_id),
        )
        conn.commit()
    return handled_at


def mark_liked(comment_id):
    with _connect() as conn:
        conn.execute("UPDATE comment SET userDigged = 1 WHERE id = ?", (comment_id,))
        conn.commit()
