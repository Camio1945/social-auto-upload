# -*- coding: utf-8 -*-
"""小红书扫码登录、cookie 校验与登录结果封装。"""

from __future__ import annotations

import asyncio
import inspect
import os
from pathlib import Path

from patchright.async_api import Page
from patchright.async_api import async_playwright

from conf import LOCAL_CHROME_HEADLESS
from uploader.xiaohongshu_uploader.browser import (
    XHS_LOGIN_BOX_SELECTOR,
    XHS_LOGIN_SWITCH_SELECTOR,
    _build_xhs_creator_url,
    _get_context_page,
    _msg,
    open_xhs_context,
)
from utils.login_qrcode import build_login_qrcode_path
from utils.login_qrcode import decode_qrcode_from_path
from utils.login_qrcode import print_terminal_qrcode
from utils.login_qrcode import remove_qrcode_file
from utils.login_qrcode import save_data_url_image
from utils.log import xiaohongshu_logger


async def _emit_qrcode_callback(qrcode_callback, payload: dict):
    if not qrcode_callback:
        return

    callback_result = qrcode_callback(payload)
    if inspect.isawaitable(callback_result):
        await callback_result


def _build_login_result(
    success: bool,
    status: str,
    message: str,
    account_file: str,
    qrcode: dict | None = None,
    current_url: str = "",
) -> dict:
    return {
        "success": success,
        "status": status,
        "message": message,
        "account_file": str(account_file),
        "qrcode": qrcode,
        "current_url": current_url,
    }


async def _open_xhs_qrcode_panel(page: Page) -> None:
    login_box = page.locator(XHS_LOGIN_BOX_SELECTOR).first
    await login_box.wait_for(state="visible", timeout=30000)

    scan_text = login_box.locator("div:has-text('扫一扫')").first
    if await scan_text.count():
        return

    switch_img = login_box.locator(XHS_LOGIN_SWITCH_SELECTOR).first
    await switch_img.wait_for(state="visible", timeout=10000)
    await switch_img.click()
    await login_box.locator("div:has-text('扫一扫')").first.wait_for(state="visible", timeout=10000)


async def _find_xhs_qrcode_locator(page: Page):
    await _open_xhs_qrcode_panel(page)

    qrcode_img = (
        page.locator(".login-box-container")
        .get_by_text("APP扫一扫登录")
        .filter(visible=True)
        .locator("xpath=..//following-sibling::div//img")
        .nth(0)
    )

    if await qrcode_img.count():
        return qrcode_img

    raise RuntimeError("未在扫一扫登录区域找到小红书二维码图片")


async def _extract_xhs_qrcode_src(page: Page) -> str:
    qrcode_img = await _find_xhs_qrcode_locator(page)
    await qrcode_img.wait_for(state="visible", timeout=30000)
    qrcode_src = await qrcode_img.get_attribute("src")
    if not qrcode_src:
        raise RuntimeError("未获取到小红书登录二维码地址")
    return qrcode_src


async def _save_xhs_qrcode(
    page: Page,
    account_file: str,
    previous_qrcode_path: Path | None = None,
    qrcode_callback=None,
) -> dict:
    qrcode_src = await _extract_xhs_qrcode_src(page)
    qrcode_path = build_login_qrcode_path(account_file, suffix="xhs_login_qrcode")
    qrcode_img = await _find_xhs_qrcode_locator(page)

    if qrcode_src.startswith("data:image/"):
        save_data_url_image(qrcode_src, qrcode_path)
    else:
        qrcode_path.parent.mkdir(parents=True, exist_ok=True)
        await qrcode_img.screenshot(path=str(qrcode_path))

    if previous_qrcode_path and previous_qrcode_path != qrcode_path:
        if remove_qrcode_file(previous_qrcode_path):
            xiaohongshu_logger.info(_msg("🧹", f"临时二维码文件已清理: {previous_qrcode_path}"))

    xiaohongshu_logger.info(_msg("🖼️", f"二维码已经准备好啦，已保存到: {qrcode_path}"))
    qrcode_content = decode_qrcode_from_path(qrcode_path)
    if qrcode_content:
        print_terminal_qrcode(qrcode_content, qrcode_path, "小红书APP")
    else:
        xiaohongshu_logger.warning(_msg("😵", f"终端没法完整显示二维码，请打开 {qrcode_path} 扫码"))

    qrcode_info = {
        "image_path": str(qrcode_path),
        "image_data_url": qrcode_src,
    }
    await _emit_qrcode_callback(qrcode_callback, qrcode_info)
    return qrcode_info


async def _is_xhs_login_completed(page: Page) -> bool:
    if page.url.startswith(_build_xhs_creator_url("/login")):
        return False

    login_box = page.locator(XHS_LOGIN_BOX_SELECTOR).first
    if not await login_box.count():
        return True

    try:
        return not await login_box.is_visible()
    except Exception:
        return True


async def cookie_auth(account_file):
    if not os.path.exists(account_file):
        return False

    async with async_playwright() as playwright:
        context = None
        try:
            # 校验也用同一份 profile，避免同一账号在几分钟内出现两套设备指纹。
            context = await open_xhs_context(playwright, account_file, headless=True)
            page = await _get_context_page(context)
            await page.goto(_build_xhs_creator_url("/publish/publish?from=homepage&target=video"))
            await page.wait_for_timeout(3000)

            if page.url.startswith(_build_xhs_creator_url("/login")):
                xiaohongshu_logger.info(_msg("🥹", "cookie 已失效，得重新登录一下"))
                return False

            login_box = page.locator(XHS_LOGIN_BOX_SELECTOR).first
            if await login_box.count():
                try:
                    if await login_box.is_visible():
                        xiaohongshu_logger.info(_msg("🥹", "页面仍然停留在登录二维码页，按 cookie 失效处理"))
                        return False
                except Exception:
                    return False

            await context.storage_state(path=account_file)
            xiaohongshu_logger.success(_msg("🥳", "cookie 有效"))
            return True
        except Exception as exc:
            xiaohongshu_logger.warning(_msg("😵", f"cookie 校验时出错，按失效处理: {exc}"))
            return False
        finally:
            if context is not None:
                await context.close()


async def xiaohongshu_setup(
    account_file,
    handle=False,
    return_detail=False,
    qrcode_callback=None,
    headless: bool = LOCAL_CHROME_HEADLESS,
):
    if not os.path.exists(account_file) or not await cookie_auth(account_file):
        if not handle:
            result = _build_login_result(False, "cookie_invalid", "cookie文件不存在或已失效", account_file)
            return result if return_detail else False
        xiaohongshu_logger.info(_msg("🥹", "cookie 失效了，准备打开浏览器重新登录"))
        result = await xiaohongshu_cookie_gen(
            account_file,
            qrcode_callback=qrcode_callback,
            headless=headless,
        )
        return result if return_detail else result["success"]

    result = _build_login_result(True, "cookie_valid", "cookie有效", account_file)
    return result if return_detail else True


async def _wait_for_scan(
    context,
    page: Page,
    account_file: str,
    qrcode_info: dict | None,
    poll_interval: int,
    max_checks: int,
) -> dict | None:
    for _ in range(max_checks):
        if await _is_xhs_login_completed(page):
            await asyncio.sleep(2)
            await context.storage_state(path=account_file)
            return _build_login_result(True, "success", "小红书扫码登录成功", account_file, qrcode_info, page.url)
        await asyncio.sleep(poll_interval)
    return None


async def _verify_login_result(result: dict, account_file: str, qrcode_info: dict | None) -> dict:
    """持久化 profile 同一时间只允许一个实例，必须关闭后再校验。"""
    if not result["success"]:
        return result

    verified = False
    try:
        verified = await cookie_auth(account_file)
    except Exception as exc:
        xiaohongshu_logger.warning(_msg("😵", f"登录态校验异常，按失败处理: {exc}"))
    if verified:
        return result

    return _build_login_result(
        False,
        "cookie_invalid",
        "小红书扫码流程结束，但 cookie 校验失败",
        account_file,
        qrcode_info,
    )


async def xiaohongshu_cookie_gen(
    account_file,
    qrcode_callback=None,
    poll_interval: int = 3,
    max_checks: int = 100,
    headless: bool = LOCAL_CHROME_HEADLESS,
):
    if headless:
        xiaohongshu_logger.info(_msg("🖼️", "小红书登录将以无头模式运行，小人会输出终端二维码并保存本地二维码图片"))

    Path(account_file).parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as playwright:
        context = None
        page = None
        qrcode_path = None
        qrcode_info = None
        result = _build_login_result(False, "failed", "小红书登录失败", account_file)
        try:
            context = await open_xhs_context(playwright, account_file, headless=headless)
            page = await _get_context_page(context)
            await page.goto(_build_xhs_creator_url("/login"))
            qrcode_info = await _save_xhs_qrcode(page, account_file, qrcode_callback=qrcode_callback)
            qrcode_path = Path(qrcode_info["image_path"])
            xiaohongshu_logger.info(_msg("🧍", "请扫码，小人正在耐心等待登录完成"))
            result = await _wait_for_scan(
                context, page, account_file, qrcode_info, poll_interval, max_checks
            ) or _build_login_result(False, "timeout", "等待小红书扫码登录超时", account_file, qrcode_info, page.url)
        except Exception as exc:
            current_url = page.url if page else ""
            result = _build_login_result(False, "failed", str(exc), account_file, current_url=current_url)
        finally:
            if remove_qrcode_file(qrcode_path):
                xiaohongshu_logger.info(_msg("🧹", f"临时二维码文件已清理: {qrcode_path}"))
            if context is not None:
                await context.close()

        result = await _verify_login_result(result, account_file, qrcode_info)
        if not result["success"]:
            xiaohongshu_logger.error(_msg("😢", f"登录失败: {result['message']}"))
        return result
