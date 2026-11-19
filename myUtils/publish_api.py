"""发布与登录接口：扫码登录、视频发布、Cookie 上传下载。"""
import asyncio
import json
import sqlite3
import threading
import time
from pathlib import Path
from queue import Queue

from flask import Blueprint, Response, jsonify, request, send_from_directory

from conf import BASE_DIR
from myUtils.account_api import account_exists, user_name_exists
from myUtils.login import get_tencent_cookie, douyin_cookie_gen, get_ks_cookie, xiaohongshu_cookie_gen
from myUtils.postVideo import post_video_tencent, post_video_DouYin, post_video_ks, post_video_xhs

publish_bp = Blueprint("publish", __name__)

active_queues = {}

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


def dispatch_publish(args):
    """按平台调用对应的发布函数；平台不支持时返回 False。"""
    platform_type = args['type']
    match platform_type:
        case 1:
            post_video_xhs(args['title'], args['file_list'], args['tags'], args['account_list'],
                           args['category'])
        case 2:
            post_video_tencent(args['title'], args['file_list'], args['tags'], args['account_list'],
                               args['category'], args['is_draft'])
        case 3:
            post_video_DouYin(args['title'], args['file_list'], args['tags'], args['account_list'],
                              args['category'], args['thumbnail'], args['product_link'],
                              args['product_title'])
        case 4:
            post_video_ks(args['title'], args['file_list'], args['tags'], args['account_list'],
                          args['category'])
        case _:
            return False
    return True


def validate_cookie_file():
    """校验上传的 Cookie 文件；返回 (file, 错误响应或 None)。"""
    if 'file' not in request.files:
        return None, (jsonify({"code": 400, "msg": "没有找到Cookie文件", "data": None}), 400)
    file = request.files['file']
    if file.filename == '':
        return None, (jsonify({"code": 400, "msg": "Cookie文件名不能为空", "data": None}), 400)
    if not file.filename.endswith('.json'):
        return None, (jsonify({"code": 400, "msg": "Cookie文件必须是JSON格式", "data": None}), 400)
    return file, None


def find_cookie_path(account_id):
    """根据账号 id 查询 Cookie 文件名。"""
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        conn.row_factory = sqlite3.Row
        result = conn.execute(
            'SELECT filePath FROM user_info WHERE id = ?', (account_id,)
        ).fetchone()
    return result['filePath'] if result else None


# SSE 登录接口
@publish_bp.route('/login')
def login():
    # 1 小红书 2 视频号 3 抖音 4 快手
    type = request.args.get('type')
    # 账号名
    id = (request.args.get('id') or '').strip()

    # 同一名称在同一平台只能有一个账号
    try:
        platform_type = int(type)
    except (TypeError, ValueError):
        return jsonify({"code": 400, "msg": "平台类型无效", "data": None}), 400

    if not id:
        return jsonify({"code": 400, "msg": "账号名称不能为空", "data": None}), 400

    # 名称必须先存在于 user_name 中
    if not user_name_exists(id):
        return jsonify({"code": 400, "msg": "名称不存在，请先在名称管理中添加", "data": None}), 400

    if account_exists(platform_type, id):
        return jsonify({
            "code": 409,
            "msg": "该名称已在此平台添加过账号",
            "data": None
        }), 409

    # 模拟一个用于异步通信的队列
    status_queue = Queue()
    active_queues[id] = status_queue

    def on_close():
        print(f"清理队列: {id}")
        del active_queues[id]

    # 启动异步任务线程
    thread = threading.Thread(target=run_async_function, args=(type, id, status_queue), daemon=True)
    thread.start()
    response = Response(sse_stream(status_queue,), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'  # 关键：禁用 Nginx 缓冲
    response.headers['Content-Type'] = 'text/event-stream'
    response.headers['Connection'] = 'keep-alive'
    return response


@publish_bp.route('/postVideo', methods=['POST'])
def postVideo():
    data = request.get_json()
    if not data:
        return jsonify({"code": 400, "msg": "请求数据不能为空", "data": None}), 400

    args = build_publish_args(data)

    # 参数校验
    if not args['file_list']:
        return jsonify({"code": 400, "msg": "文件列表不能为空", "data": None}), 400
    if not args['account_list']:
        return jsonify({"code": 400, "msg": "账号列表不能为空", "data": None}), 400
    if not args['type']:
        return jsonify({"code": 400, "msg": "平台类型不能为空", "data": None}), 400
    if not args['title']:
        return jsonify({"code": 400, "msg": "标题不能为空", "data": None}), 400

    print("File List:", args['file_list'])
    print("Account List:", args['account_list'])

    # 先写入发布中记录，结束后再更新状态（记录失败不影响发布）
    log_id = log_publish_start(args)
    try:
        if not dispatch_publish(args):
            finish_publish_log(log_id, PUBLISH_LOG_FAILED, f"不支持的平台类型: {args['type']}")
            return jsonify({
                "code": 400,
                "msg": f"不支持的平台类型: {args['type']}",
                "data": None
            }), 400
        finish_publish_log(log_id, PUBLISH_LOG_SUCCESS)
        return jsonify({
            "code": 200,
            "msg": "发布任务已提交",
            "data": None
        }), 200
    except Exception as e:
        print(f"发布视频时出错: {str(e)}")
        finish_publish_log(log_id, PUBLISH_LOG_FAILED, str(e))
        return jsonify({
            "code": 500,
            "msg": f"发布失败: {str(e)}",
            "data": None
        }), 500


@publish_bp.route('/postVideoBatch', methods=['POST'])
def postVideoBatch():
    data_list = request.get_json()

    if not isinstance(data_list, list):
        return jsonify({"code": 400, "msg": "Expected a JSON array", "data": None}), 400

    for data in data_list:
        args = build_publish_args(data)
        print("File List:", args['file_list'])
        print("Account List:", args['account_list'])
        log_id = log_publish_start(args)
        try:
            if not dispatch_publish(args):
                finish_publish_log(log_id, PUBLISH_LOG_FAILED, f"不支持的平台类型: {args['type']}")
                continue
            finish_publish_log(log_id, PUBLISH_LOG_SUCCESS)
        except Exception as e:
            print(f"批量发布时出错: {e}")
            finish_publish_log(log_id, PUBLISH_LOG_FAILED, str(e))

    return jsonify({
        "code": 200,
        "msg": None,
        "data": None
    }), 200


@publish_bp.route('/getPublishLogs', methods=['GET'])
def get_publish_logs():
    """按时间倒序返回发布记录。"""
    limit = request.args.get('limit', default=200, type=int)
    try:
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                'SELECT * FROM publish_log ORDER BY id DESC LIMIT ?', (limit,)
            ).fetchall()
        data = [deserialize_publish_log(dict(row)) for row in rows]
        return jsonify({"code": 200, "msg": None, "data": data}), 200
    except Exception as e:
        print(f"获取发布记录失败: {e}")
        return jsonify({
            "code": 500,
            "msg": f"获取发布记录失败: {e}",
            "data": None
        }), 500


# Cookie文件上传API
@publish_bp.route('/uploadCookie', methods=['POST'])
def upload_cookie():
    try:
        file, error = validate_cookie_file()
        if error:
            return error

        account_id = request.form.get('id')
        platform = request.form.get('platform')
        if not account_id or not platform:
            return jsonify({
                "code": 400,
                "msg": "缺少账号ID或平台信息",
                "data": None
            }), 400

        file_path = find_cookie_path(account_id)
        if not file_path:
            return jsonify({
                "code": 500,
                "msg": "账号不存在",
                "data": None
            }), 404

        cookie_file_path = Path(BASE_DIR / "cookiesFile" / file_path)
        cookie_file_path.parent.mkdir(parents=True, exist_ok=True)
        file.save(str(cookie_file_path))

        return jsonify({
            "code": 200,
            "msg": "Cookie文件上传成功",
            "data": None
        }), 200
    except Exception as e:
        print(f"上传Cookie文件时出错: {str(e)}")
        return jsonify({
            "code": 500,
            "msg": f"上传Cookie文件失败: {str(e)}",
            "data": None
        }), 500


# Cookie文件下载API
@publish_bp.route('/downloadCookie', methods=['GET'])
def download_cookie():
    try:
        file_path = request.args.get('filePath')
        if not file_path:
            return jsonify({
                "code": 500,
                "msg": "缺少文件路径参数",
                "data": None
            }), 400

        # 验证文件路径的安全性，防止路径遍历攻击
        cookie_file_path = Path(BASE_DIR / "cookiesFile" / file_path).resolve()
        base_path = Path(BASE_DIR / "cookiesFile").resolve()

        if not cookie_file_path.is_relative_to(base_path):
            return jsonify({
                "code": 500,
                "msg": "非法文件路径",
                "data": None
            }), 400

        if not cookie_file_path.exists():
            return jsonify({
                "code": 500,
                "msg": "Cookie文件不存在",
                "data": None
            }), 404

        return send_from_directory(
            directory=str(cookie_file_path.parent),
            path=cookie_file_path.name,
            as_attachment=True
        )
    except Exception as e:
        print(f"下载Cookie文件时出错: {str(e)}")
        return jsonify({
            "code": 500,
            "msg": f"下载Cookie文件失败: {str(e)}",
            "data": None
        }), 500


# 包装函数：在线程中运行异步函数
def run_async_function(type, id, status_queue):
    match type:
        case '1':
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(xiaohongshu_cookie_gen(id, status_queue))
            loop.close()
        case '2':
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(get_tencent_cookie(id, status_queue))
            loop.close()
        case '3':
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(douyin_cookie_gen(id, status_queue))
            loop.close()
        case '4':
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(get_ks_cookie(id, status_queue))
            loop.close()


# SSE 流生成器函数
def sse_stream(status_queue):
    while True:
        if not status_queue.empty():
            msg = status_queue.get()
            yield f"data: {msg}\n\n"
        else:
            # 避免 CPU 占满
            time.sleep(0.1)
