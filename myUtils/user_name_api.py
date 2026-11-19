"""名称管理接口：维护 user_name 表，user_info.userName 外键引用该表。"""
import sqlite3
from pathlib import Path

from flask import Blueprint, jsonify, request

from conf import BASE_DIR

user_name_bp = Blueprint("user_name", __name__)
DB_FILE = Path(BASE_DIR / "db" / "database.db")


def _connect():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    # SQLite 默认不校验外键，需按连接开启
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _respond(code, msg=None, data=None, status=200):
    return jsonify({"code": code, "msg": msg, "data": data}), status


def _normalize_name(raw):
    return raw.strip() if isinstance(raw, str) else ""


def _row_to_dict(row):
    return {"id": row["id"], "userName": row["userName"]}


@user_name_bp.route("/getUserNames", methods=["GET"])
def get_user_names():
    """获取全部名称，按 id 排序。"""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, userName FROM user_name ORDER BY id"
        ).fetchall()
        return _respond(200, None, [_row_to_dict(row) for row in rows])
    except Exception as e:
        return _respond(500, f"获取名称列表失败: {e}", None, 500)
    finally:
        conn.close()


@user_name_bp.route("/addUserName", methods=["POST"])
def add_user_name():
    """新增名称。"""
    payload = request.get_json(silent=True) or {}
    user_name = _normalize_name(payload.get("userName"))
    if not user_name:
        return _respond(400, "名称不能为空", None, 400)

    conn = _connect()
    try:
        cursor = conn.execute(
            "INSERT INTO user_name (userName) VALUES (?)", (user_name,)
        )
        conn.commit()
        return _respond(200, "名称添加成功", {
            "id": cursor.lastrowid,
            "userName": user_name,
        })
    except sqlite3.IntegrityError:
        return _respond(409, "名称已存在", None, 409)
    except Exception as e:
        return _respond(500, f"添加名称失败: {e}", None, 500)
    finally:
        conn.close()


@user_name_bp.route("/updateUserName", methods=["POST"])
def update_user_name():
    """修改名称，并同步更新引用该名称的账号。"""
    payload = request.get_json(silent=True) or {}
    name_id = payload.get("id")
    user_name = _normalize_name(payload.get("userName"))
    if not isinstance(name_id, int) or not user_name:
        return _respond(400, "参数无效", None, 400)

    conn = _connect()
    try:
        row = conn.execute(
            "SELECT userName FROM user_name WHERE id = ?", (name_id,)
        ).fetchone()
        if not row:
            return _respond(404, "名称不存在", None, 404)

        old_name = row["userName"]
        conn.execute(
            "UPDATE user_name SET userName = ? WHERE id = ?", (user_name, name_id)
        )
        conn.execute(
            "UPDATE user_info SET userName = ? WHERE userName = ?",
            (user_name, old_name),
        )
        conn.commit()
        return _respond(200, "名称更新成功", {
            "id": name_id,
            "userName": user_name,
        })
    except sqlite3.IntegrityError:
        conn.rollback()
        return _respond(409, "名称已存在", None, 409)
    except Exception as e:
        conn.rollback()
        return _respond(500, f"更新名称失败: {e}", None, 500)
    finally:
        conn.close()


@user_name_bp.route("/deleteUserName", methods=["GET"])
def delete_user_name():
    """删除名称；仍被账号引用时拒绝删除。"""
    name_id = request.args.get("id", type=int)
    if not name_id:
        return _respond(400, "参数无效", None, 400)

    conn = _connect()
    try:
        row = conn.execute(
            "SELECT userName FROM user_name WHERE id = ?", (name_id,)
        ).fetchone()
        if not row:
            return _respond(404, "名称不存在", None, 404)

        user_name = row["userName"]
        used = conn.execute(
            "SELECT COUNT(*) FROM user_info WHERE userName = ?", (user_name,)
        ).fetchone()[0]
        if used:
            return _respond(409, f"该名称仍被 {used} 个账号使用，无法删除", None, 409)

        conn.execute("DELETE FROM user_name WHERE id = ?", (name_id,))
        conn.commit()
        return _respond(200, "名称删除成功", None)
    except Exception as e:
        conn.rollback()
        return _respond(500, f"删除名称失败: {e}", None, 500)
    finally:
        conn.close()
