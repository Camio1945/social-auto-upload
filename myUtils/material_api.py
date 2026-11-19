"""素材文件接口：上传、查询、下载与删除视频文件。"""
import os
import re
import sqlite3
import uuid
from pathlib import Path

from flask import Blueprint, jsonify, request, send_from_directory

from conf import BASE_DIR

material_bp = Blueprint("material", __name__)

# 素材文件存放目录（videoFile 在 .gitignore 中，可能不存在，上传前需确保创建）
VIDEO_DIR = BASE_DIR / "videoFile"
_ILLEGAL_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def ensure_video_dir() -> Path:
    """确保素材目录存在，避免首次上传时 file.save 抛 FileNotFoundError。"""
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    return VIDEO_DIR


def safe_filename(name: str) -> str:
    """保留中文等 Unicode 字符，仅替换文件系统非法字符。"""
    name = os.path.basename(name.replace('\\', '/'))
    name = _ILLEGAL_FILENAME_CHARS.sub('_', name).strip().strip('.')
    return name


def resolve_upload_filename(file, custom_filename):
    """优先使用自定义文件名，并保留原文件扩展名。"""
    if custom_filename:
        return safe_filename(custom_filename + "." + file.filename.split('.')[-1])
    return safe_filename(file.filename)


def save_upload_record(filename, final_filename, filepath):
    """把上传结果写入 file_records 表。"""
    filesize = round(float(os.path.getsize(filepath)) / (1024 * 1024), 2)
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO file_records (filename, filesize, file_path)
            VALUES (?, ?, ?)
        ''', (filename, filesize, final_filename))
        conn.commit()


def remove_stored_file(record):
    """删除素材对应的实际文件，失败时只记录日志。"""
    file_path = Path(BASE_DIR / "videoFile" / record['file_path'])
    if not file_path.exists():
        print(f"⚠️ 实际文件不存在: {file_path}")
        return
    try:
        file_path.unlink()
        print(f"✅ 实际文件已删除: {file_path}")
    except Exception as e:
        print(f"⚠️ 删除实际文件失败: {e}")


@material_bp.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({
            "code": 400,
            "data": None,
            "msg": "No file part in the request"
        }), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({
            "code": 400,
            "data": None,
            "msg": "No selected file"
        }), 400
    try:
        uuid_v1 = uuid.uuid1()
        print(f"UUID v1: {uuid_v1}")
        safe_name = safe_filename(file.filename)
        if not safe_name:
            return jsonify({"code": 400, "data": None, "msg": "Invalid filename"}), 400
        filepath = Path(ensure_video_dir() / f"{uuid_v1}_{safe_name}")
        file.save(filepath)
        return jsonify({
            "code": 200,
            "msg": "File uploaded successfully",
            "data": f"{uuid_v1}_{safe_name}"
        }), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@material_bp.route('/getFile', methods=['GET'])
def get_file():
    # 获取 filename 参数
    filename = request.args.get('filename')

    if not filename:
        return jsonify({"code": 400, "msg": "filename is required", "data": None}), 400

    # 防止路径穿越攻击
    if '..' in filename or filename.startswith('/'):
        return jsonify({"code": 400, "msg": "Invalid filename", "data": None}), 400

    # 拼接完整路径
    file_path = str(Path(BASE_DIR / "videoFile"))
    return send_from_directory(file_path, filename)


@material_bp.route('/uploadSave', methods=['POST'])
def upload_save():
    if 'file' not in request.files:
        return jsonify({
            "code": 400,
            "data": None,
            "msg": "No file part in the request"
        }), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({
            "code": 400,
            "data": None,
            "msg": "No selected file"
        }), 400

    filename = resolve_upload_filename(file, request.form.get('filename', None))
    if not filename:
        return jsonify({"code": 400, "data": None, "msg": "Invalid filename"}), 400

    try:
        uuid_v1 = uuid.uuid1()
        print(f"UUID v1: {uuid_v1}")
        final_filename = f"{uuid_v1}_{filename}"
        filepath = Path(ensure_video_dir() / final_filename)
        file.save(filepath)
        save_upload_record(filename, final_filename, filepath)
        print("✅ 上传文件已记录")
        return jsonify({
            "code": 200,
            "msg": "File uploaded and saved successfully",
            "data": {
                "filename": filename,
                "filepath": final_filename
            }
        }), 200
    except Exception as e:
        print(f"Upload failed: {e}")
        return jsonify({
            "code": 500,
            "msg": f"upload failed: {e}",
            "data": None
        }), 500


@material_bp.route('/getFiles', methods=['GET'])
def get_all_files():
    try:
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM file_records")
            rows = cursor.fetchall()

            data = []
            for row in rows:
                row_dict = dict(row)
                if row_dict.get('file_path'):
                    # 从 file_path 中提取 UUID（文件名的第一部分）
                    row_dict['uuid'] = row_dict['file_path'].split('_', 1)[0]
                else:
                    row_dict['uuid'] = ''
                data.append(row_dict)

            return jsonify({
                "code": 200,
                "msg": "success",
                "data": data
            }), 200
    except Exception as e:
        return jsonify({
            "code": 500,
            "msg": "get file failed!",
            "data": None
        }), 500


@material_bp.route('/deleteFile', methods=['GET'])
def delete_file():
    file_id = request.args.get('id')

    if not file_id or not file_id.isdigit():
        return jsonify({
            "code": 400,
            "msg": "Invalid or missing file ID",
            "data": None
        }), 400

    try:
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM file_records WHERE id = ?", (file_id,))
            record = cursor.fetchone()
            if not record:
                return jsonify({
                    "code": 404,
                    "msg": "File not found",
                    "data": None
                }), 404

            record = dict(record)
            remove_stored_file(record)

            cursor.execute("DELETE FROM file_records WHERE id = ?", (file_id,))
            conn.commit()

        return jsonify({
            "code": 200,
            "msg": "File deleted successfully",
            "data": {
                "id": record['id'],
                "filename": record['filename']
            }
        }), 200
    except Exception as e:
        return jsonify({
            "code": 500,
            "msg": "delete failed!",
            "data": None
        }), 500
