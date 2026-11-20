"""发布记录的构建与状态维护。"""
import json
import sqlite3
from pathlib import Path

from conf import BASE_DIR

# 发布记录状态
PUBLISH_LOG_PENDING = 0
PUBLISH_LOG_SUCCESS = 1
PUBLISH_LOG_FAILED = 2


def build_publish_args(data):
    """把前端发布数据解析为统一的参数字典。"""
    category = data.get('category')
    if category == 0:
        category = None
    return {
        'file_list': data.get('fileList', []),
        'account_list': data.get('accountList', []),
        'type': data.get('type'),
        'title': data.get('title'),
        'user_name': (data.get('userName') or '').strip(),
        'tags': data.get('tags'),
        'category': category,
        'product_link': data.get('productLink', ''),
        'product_title': data.get('productTitle', ''),
        'thumbnail': data.get('thumbnail', ''),
        'is_draft': data.get('isDraft', False),
    }


def create_publish_log(args):
    """发布前写入一条"发布中"记录，返回记录 id。"""
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        cursor = conn.execute('''
            INSERT INTO publish_log (userName, type, title, fileList, accountList, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            args['user_name'], args['type'], args['title'],
            json.dumps(args['file_list'], ensure_ascii=False),
            json.dumps(args['account_list'], ensure_ascii=False),
            PUBLISH_LOG_PENDING
        ))
        conn.commit()
        return cursor.lastrowid


def finish_publish_log(log_id, status, message=None):
    """发布结束后更新记录状态；更新失败不影响发布结果。"""
    if log_id is None:
        return
    try:
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.execute(
                'UPDATE publish_log SET status = ?, message = ? WHERE id = ?',
                (status, message, log_id)
            )
            conn.commit()
    except Exception as e:
        print(f"更新发布记录失败: {e}")


def log_publish_start(args):
    """写入发布中记录；写入失败时返回 None，不阻断发布。"""
    try:
        return create_publish_log(args)
    except Exception as e:
        print(f"写入发布记录失败: {e}")
        return None


def deserialize_publish_log(item):
    """把数据库中的 JSON 字段还原为列表；损坏数据按空列表处理。"""
    for field in ('fileList', 'accountList'):
        try:
            item[field] = json.loads(item[field]) if item[field] else []
        except (TypeError, ValueError):
            item[field] = []
    return item
