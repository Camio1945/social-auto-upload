# -*- coding: utf-8 -*-
"""小红书账号的持久化 profile 路径与发布频次控制。"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from utils.log import xiaohongshu_logger

XHS_PUBLISH_LIMIT_ENV = "SAU_XHS_MAX_PUBLISH_PER_DAY"
XHS_DEFAULT_PUBLISH_LIMIT = 3
XHS_HISTORY_KEEP = 200


def profile_dir(account_file: str) -> Path:
    """每个账号独立的 Chrome 持久化目录，登录与发布共用同一设备身份。"""
    account_path = Path(account_file)
    return account_path.parent / "xhs_profiles" / account_path.stem


def _history_path(account_file: str) -> Path:
    account_path = Path(account_file)
    return account_path.parent / f"{account_path.stem}.xhs_publish_history.json"


def _daily_limit() -> int:
    raw = os.getenv(XHS_PUBLISH_LIMIT_ENV, "").strip()
    try:
        return max(1, int(raw)) if raw else XHS_DEFAULT_PUBLISH_LIMIT
    except ValueError:
        return XHS_DEFAULT_PUBLISH_LIMIT


def _load_history(account_file: str) -> list[str]:
    path = _history_path(account_file)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [str(item) for item in data] if isinstance(data, list) else []


def ensure_publish_quota(account_file: str) -> None:
    """超过当日发布上限直接拒绝，避免短时间内批量发布触发风控。"""
    limit = _daily_limit()
    today = datetime.now().strftime("%Y-%m-%d")
    used = sum(1 for item in _load_history(account_file) if item.startswith(today))
    if used >= limit:
        raise RuntimeError(
            f"小红书账号 {Path(account_file).stem} 今天已发布 {used} 篇，"
            f"达到上限 {limit} 篇；可用环境变量 {XHS_PUBLISH_LIMIT_ENV} 调整"
        )


def record_publish(account_file: str) -> None:
    path = _history_path(account_file)
    records = _load_history(account_file)
    records.append(datetime.now().isoformat(timespec="seconds"))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(records[-XHS_HISTORY_KEEP:], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        xiaohongshu_logger.warning(f"😵 记录发布次数失败，忽略: {exc}")
