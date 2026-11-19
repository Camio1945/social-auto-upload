"""账号接口：账号列表、状态校验、删除与编辑。"""
import sqlite3
from pathlib import Path

from flask import Blueprint, jsonify, request

from conf import BASE_DIR
from myUtils.auth import check_cookie

account_bp = Blueprint("account", __name__)


def account_exists(platform_type, user_name, exclude_id=None):
    """判断同一名称在同一平台是否已有账号（可排除指定账号 id）。"""
    sql = "SELECT 1 FROM user_info WHERE type = ? AND userName = ?"
    params = [platform_type, user_name]
    if exclude_id is not None:
        sql += " AND id <> ?"
        params.append(exclude_id)
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        return conn.execute(sql, params).fetchone() is not None


def user_name_exists(user_name):
    """判断名称是否已在 user_name 表中维护。"""
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        return conn.execute(
            "SELECT 1 FROM user_name WHERE userName = ?", (user_name,)
        ).fetchone() is not None


def update_user_info_record(user_id, platform_type, user_name):
    """更新账号信息；返回受影响行数，违反唯一约束时抛出 IntegrityError。"""
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "UPDATE user_info SET type = ?, userName = ? WHERE id = ?",
            (platform_type, user_name, user_id),
        )
        conn.commit()
        return cursor.rowcount


def remove_cookie_file(record):
    """删除账号关联的 Cookie 文件，失败时只记录日志。"""
    if not record.get('filePath'):
        return
    cookie_file_path = Path(BASE_DIR / "cookiesFile" / record['filePath'])
    if not cookie_file_path.exists():
        return
    try:
        cookie_file_path.unlink()
        print(f"✅ Cookie文件已删除: {cookie_file_path}")
    except Exception as e:
        print(f"⚠️ 删除Cookie文件失败: {e}")


@account_bp.route("/getAccounts", methods=['GET'])
def getAccounts():
    """快速获取所有账号信息，不进行cookie验证"""
    try:
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
            SELECT * FROM user_info''')
            rows = cursor.fetchall()
            rows_list = [list(row) for row in rows]

            print("\n📋 当前数据表内容（快速获取）：")
            for row in rows:
                print(row)

            return jsonify({
                "code": 200,
                "msg": None,
                "data": rows_list
            }), 200
    except Exception as e:
        print(f"获取账号列表时出错: {str(e)}")
        return jsonify({
            "code": 500,
            "msg": f"获取账号列表失败: {str(e)}",
            "data": None
        }), 500


@account_bp.route("/getValidAccounts", methods=['GET'])
async def getValidAccounts():
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        cursor = conn.cursor()
        cursor.execute('''
        SELECT * FROM user_info''')
        rows = cursor.fetchall()
        rows_list = [list(row) for row in rows]
        print("\n📋 当前数据表内容：")
        for row in rows:
            print(row)
        for row in rows_list:
            flag = await check_cookie(row[1], row[2])
            if not flag:
                row[4] = 0
                cursor.execute('''
                UPDATE user_info 
                SET status = ? 
                WHERE id = ?
                ''', (0, row[0]))
                conn.commit()
                print("✅ 用户状态已更新")
        for row in rows:
            print(row)
        return jsonify({
            "code": 200,
            "msg": None,
            "data": rows_list
        }), 200


@account_bp.route('/deleteAccount', methods=['GET'])
def delete_account():
    account_id = request.args.get('id')

    if not account_id or not account_id.isdigit():
        return jsonify({
            "code": 400,
            "msg": "Invalid or missing account ID",
            "data": None
        }), 400

    account_id = int(account_id)

    try:
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM user_info WHERE id = ?", (account_id,))
            record = cursor.fetchone()
            if not record:
                return jsonify({
                    "code": 404,
                    "msg": "account not found",
                    "data": None
                }), 404

            record = dict(record)
            remove_cookie_file(record)

            cursor.execute("DELETE FROM user_info WHERE id = ?", (account_id,))
            conn.commit()

        return jsonify({
            "code": 200,
            "msg": "account deleted successfully",
            "data": None
        }), 200
    except Exception as e:
        return jsonify({
            "code": 500,
            "msg": f"delete failed: {str(e)}",
            "data": None
        }), 500


@account_bp.route('/updateUserinfo', methods=['POST'])
def updateUserinfo():
    data = request.get_json() or {}
    user_id = data.get('id')
    platform_type = data.get('type')
    user_name = data.get('userName')

    if not user_id or not platform_type or not user_name:
        return jsonify({"code": 400, "msg": "参数不完整", "data": None}), 400

    # 同一名称在同一平台只能有一个账号
    if account_exists(platform_type, user_name, exclude_id=user_id):
        return jsonify({
            "code": 409,
            "msg": "该名称已在此平台添加过账号",
            "data": None
        }), 409

    try:
        updated = update_user_info_record(user_id, platform_type, user_name)
        if updated == 0:
            return jsonify({"code": 404, "msg": "账号不存在", "data": None}), 404
        return jsonify({
            "code": 200,
            "msg": "account update successfully",
            "data": None
        }), 200
    except sqlite3.IntegrityError:
        return jsonify({
            "code": 409,
            "msg": "该名称已在此平台添加过账号",
            "data": None
        }), 409
    except Exception as e:
        return jsonify({
            "code": 500,
            "msg": "update failed!",
            "data": None
        }), 500
