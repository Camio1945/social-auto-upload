# -*- coding: utf-8 -*-
"""小红书上传器对外入口，具体实现按职责拆分在同目录模块中。

- browser: 域名、持久化浏览器上下文、登录态检查
- login: 扫码登录、cookie 校验、登录结果
- base: 公共基类（校验、拟人输入、发布提交）
- video / note: 视频与图文发布流程
"""

from __future__ import annotations

from uploader.xiaohongshu_uploader.base import XiaoHongShuBaseUploader
from uploader.xiaohongshu_uploader.browser import (
    XHS_CREATOR_BASE_URL_ENV,
    XHS_DEFAULT_CREATOR_BASE_URL,
    XHS_LOGIN_BOX_SELECTOR,
    XHS_LOGIN_SWITCH_SELECTOR,
    XHS_PUBLISH_SUCCESS_URL_PATTERN,
    XIAOHONGSHU_PUBLISH_STRATEGY_IMMEDIATE,
    XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED,
    _build_xhs_creator_url,
    _get_context_page,
    _msg,
    _raise_if_login_required,
    open_xhs_context,
)
from uploader.xiaohongshu_uploader.login import (
    _find_xhs_qrcode_locator,
    cookie_auth,
    xiaohongshu_cookie_gen,
    xiaohongshu_setup,
)
from uploader.xiaohongshu_uploader.note import XiaoHongShuNote
from uploader.xiaohongshu_uploader.video import XiaoHongShuVideo

__all__ = [
    "XHS_CREATOR_BASE_URL_ENV",
    "XHS_DEFAULT_CREATOR_BASE_URL",
    "XHS_LOGIN_BOX_SELECTOR",
    "XHS_LOGIN_SWITCH_SELECTOR",
    "XHS_PUBLISH_SUCCESS_URL_PATTERN",
    "XIAOHONGSHU_PUBLISH_STRATEGY_IMMEDIATE",
    "XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED",
    "XiaoHongShuBaseUploader",
    "XiaoHongShuNote",
    "XiaoHongShuVideo",
    "_build_xhs_creator_url",
    "_find_xhs_qrcode_locator",
    "_get_context_page",
    "_msg",
    "_raise_if_login_required",
    "cookie_auth",
    "open_xhs_context",
    "xiaohongshu_cookie_gen",
    "xiaohongshu_setup",
]
