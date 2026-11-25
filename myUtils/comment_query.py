"""评论列表查询：筛选条件拼装与评论/作品联表读取。"""
import sqlite3
from pathlib import Path

from conf import BASE_DIR

DB_PATH = Path(BASE_DIR / "db" / "database.db")

COMMENT_LIST_SQL = '''
    SELECT c.*, p.title AS postTitle, p.coverUrl AS postCoverUrl,
           p.shareUrl AS postShareUrl, p.publishedAt AS postPublishedAt
    FROM comment c
    JOIN platform_post p ON p.id = c.postId
    WHERE c.type = ?
'''

POST_LIST_SQL = '''
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


def build_comment_query(platform_type, handled, post_id, limit):
    """按筛选条件拼装评论查询，返回 (sql, params)。"""
    sql = COMMENT_LIST_SQL
    params = [platform_type]
    if handled in ('0', '1'):
        sql += ' AND c.isHandled = ?'
        params.append(int(handled))
    if post_id:
        sql += ' AND c.postId = ?'
        params.append(post_id)
    sql += ' ORDER BY c.platformCreatedAt DESC, c.id DESC LIMIT ?'
    params.append(limit)
    return sql, params


def load_comment_rows(platform_type, sql, params):
    """执行评论与作品查询，返回 (comments, posts)。"""
    with sqlite3.connect(DB_PATH, timeout=30) as conn:
        conn.row_factory = sqlite3.Row
        comments = [dict(row) for row in conn.execute(sql, params).fetchall()]
        posts = [dict(row) for row in conn.execute(POST_LIST_SQL, (platform_type,)).fetchall()]
    posts = [dict(post, unhandledCount=post['unhandledCount'] or 0) for post in posts]
    return comments, posts
