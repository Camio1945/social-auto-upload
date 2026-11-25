# -*- coding: utf-8 -*-
"""小红书创作中心的地址、浏览器持久化会话与登录态检查。"""

from __future__ import annotations

import json
import os
from pathlib import Path

from patchright.async_api import Page

from conf import get_browser_options
from uploader.xiaohongshu_uploader.session import profile_dir
from utils.log import xiaohongshu_logger

XHS_DEFAULT_CREATOR_BASE_URL = "https://creator.xiaohongshu.com"
XHS_CREATOR_BASE_URL_ENV = "SAU_XHS_CREATOR_BASE_URL"
XHS_PUBLISH_SUCCESS_URL_PATTERN = "**/publish/success?**"
XHS_LOGIN_BOX_SELECTOR = "div[class*='login-box']"
XHS_LOGIN_SWITCH_SELECTOR = "img.css-wemwzq"
XIAOHONGSHU_PUBLISH_STRATEGY_IMMEDIATE = "immediate"
XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED = "scheduled"


def _msg(emoji: str, text: str) -> str:
    return f"{emoji} {text}"


def _build_xhs_creator_url(path: str) -> str:
    base_url = (
        os.getenv(
            XHS_CREATOR_BASE_URL_ENV,
            XHS_DEFAULT_CREATOR_BASE_URL,
        )
        .strip()
        .rstrip("/")
    )
    if not base_url:
        base_url = XHS_DEFAULT_CREATOR_BASE_URL
    return f"{base_url}/{path.lstrip('/')}"


def _launch_options(headless: bool | None = None, extra_args: list[str] | None = None) -> dict:
    """统一使用本地 Chrome 启动，避免依赖未安装的 Playwright 内置 Chromium。"""
    options = get_browser_options()
    if headless is not None:
        options["headless"] = headless
    if extra_args:
        options["args"] = [*options.get("args", []), *extra_args]
    return options


async def _import_state_cookies(context, account_file: str) -> None:
    """首次创建 profile 时，把旧版 storage_state 里的 cookie 迁移进来。"""
    if not os.path.exists(account_file):
        return
    try:
        state = json.loads(Path(account_file).read_text(encoding="utf-8"))
    except Exception:
        return
    cookies = state.get("cookies") or []
    if not cookies:
        return
    try:
        await context.add_cookies(cookies)
    except Exception as exc:
        xiaohongshu_logger.warning(_msg("😵", f"导入旧 cookie 失败，忽略: {exc}"))


async def open_xhs_context(playwright, account_file: str, headless: bool | None = None):
    """为账号打开持久化浏览器上下文，登录和发布共用同一套设备指纹。

    注意：这里不再注入 stealth.min.js。patchright 自身已修补自动化特征，
    再叠加 puppeteer-extra 那套脚本反而会制造互相矛盾的指纹。
    """
    profile_path = profile_dir(account_file)
    # 登录页本身会种匿名 cookie，不能用“有没有 cookie”判断是否迁移过；
    # 只有 profile 目录为空（首次创建）时才导入旧 cookie。
    fresh_profile = not profile_path.exists() or not any(profile_path.iterdir())
    profile_path.mkdir(parents=True, exist_ok=True)
    context = await playwright.chromium.launch_persistent_context(
        user_data_dir=str(profile_path),
        no_viewport=True,
        permissions=["geolocation"],
        **_launch_options(headless=headless),
    )
    if fresh_profile:
        await _import_state_cookies(context, account_file)
    return context


async def _get_context_page(context):
    if context.pages:
        return context.pages[0]
    return await context.new_page()


async def _raise_if_login_required(page: Page) -> None:
    if page.url.startswith(_build_xhs_creator_url("/login")):
        raise RuntimeError("小红书登录态已失效，请重新登录后再发布")
