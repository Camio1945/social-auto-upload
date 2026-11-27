"""视频号保活配置与手动触发接口。"""
from flask import Blueprint, jsonify, request

from myUtils import keepalive

keepalive_bp = Blueprint("keepalive", __name__)


@keepalive_bp.route("/keepalive/config", methods=["GET"])
def get_keepalive_config():
    return jsonify({"code": 200, "msg": None, "data": keepalive.load_config()}), 200


@keepalive_bp.route("/keepalive/config", methods=["POST"])
def update_keepalive_config():
    data = request.get_json(silent=True) or {}
    try:
        config = keepalive.update_config(
            enabled=data.get("enabled"),
            interval_minutes=data.get("intervalMinutes"),
        )
    except ValueError as exc:
        return jsonify({"code": 400, "msg": str(exc), "data": None}), 400
    return jsonify({"code": 200, "msg": None, "data": config}), 200


@keepalive_bp.route("/keepalive/run", methods=["POST"])
def run_keepalive():
    outcome = keepalive.run_once()
    return jsonify({"code": 200, "msg": None, "data": outcome}), 200
