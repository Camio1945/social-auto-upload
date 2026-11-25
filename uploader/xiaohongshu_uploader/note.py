# -*- coding: utf-8 -*-
"""小红书图文发布流程。"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from patchright.async_api import Page
from patchright.async_api import Playwright
from patchright.async_api import async_playwright

from conf import DEBUG_MODE, LOCAL_CHROME_HEADLESS
from uploader.xiaohongshu_uploader.base import XiaoHongShuBaseUploader
from uploader.xiaohongshu_uploader.browser import (
    XIAOHONGSHU_PUBLISH_STRATEGY_IMMEDIATE,
    XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED,
    _build_xhs_creator_url,
    _get_context_page,
    _msg,
    _raise_if_login_required,
    open_xhs_context,
)
from utils.log import xiaohongshu_logger


class XiaoHongShuNote(XiaoHongShuBaseUploader):
    def __init__(
        self,
        image_paths,
        note,
        tags,
        publish_date: datetime | int,
        account_file,
        title: str | None = None,
        desc: str | None = None,
        publish_strategy: str = XIAOHONGSHU_PUBLISH_STRATEGY_IMMEDIATE,
        debug: bool = DEBUG_MODE,
        headless: bool = LOCAL_CHROME_HEADLESS,
    ):
        super().__init__(
            publish_date=publish_date,
            account_file=account_file,
            publish_strategy=publish_strategy,
            debug=debug,
            headless=headless,
        )
        self.image_paths = image_paths
        self.note = note or ""
        self.tags = tags or []
        self.desc = desc if desc is not None else self.note
        self.title = title or ((self.desc or self.note)[:20] if (self.desc or self.note) else "")

    async def validate_upload_args(self):
        await self.validate_base_args()
        if not self.image_paths:
            raise ValueError("图文模式下，图片是必须的")
        if not self.title or not str(self.title).strip():
            raise ValueError("图文模式下，title 是必须的")

        if isinstance(self.image_paths, (str, Path)):
            self.image_paths = [self.image_paths]

        normalized_image_paths = []
        for image_path in self.image_paths:
            normalized_image_paths.append(str(self.validate_image_file(image_path)))
        self.image_paths = normalized_image_paths

    async def upload_note_content(self, page: Page) -> None:
        xiaohongshu_logger.info(_msg("🏃", f"小人开始搬运图文，共 {len(self.image_paths)} 张图片"))
        xiaohongshu_logger.info(_msg("🧭", "小人先回创作中心逛一会，再赶往图文发布页"))
        await self.warm_up_before_publish(page)
        publish_url = _build_xhs_creator_url("/publish/publish?from=homepage&target=image")
        await page.goto(publish_url)
        await _raise_if_login_required(page)
        await page.wait_for_url(publish_url)

        upload_input = page.locator('input[type="file"][accept*="image"]').first
        if not await upload_input.count():
            upload_input = page.locator("div[class^='upload-content'] input[class='upload-input']").first

        await upload_input.wait_for(state="attached", timeout=30000)
        xiaohongshu_logger.info(_msg("📤", "小人正在上传图片"))
        await upload_input.set_input_files(self.image_paths)

        while True:
            try:
                title_container = page.locator('input[placeholder*="填写标题"]').first
                await title_container.wait_for(state="visible", timeout=3000)
                xiaohongshu_logger.success(_msg("🥳", "图文素材已经传完，可以开始填写内容了"))
                break
            except Exception:
                xiaohongshu_logger.debug(_msg("🧍", "图文素材还在上传，小人继续等一会"))
                await asyncio.sleep(1)

        xiaohongshu_logger.info(_msg("✍️", "小人开始填标题、描述和话题"))
        await self.fill_meta(page)
        await self.check_original_declaration(page)

        if self.publish_strategy == XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED and self.publish_date != 0:
            await self.set_schedule_time_xiaohongshu(page, self.publish_date)

        await self.submit_publish(page, "图文")

    async def upload(self, playwright: Playwright) -> None:
        xiaohongshu_logger.info(_msg("🧍", "小人先检查 cookie、图片和发布时间"))
        await self.validate_upload_args()
        xiaohongshu_logger.info(_msg("🥳", "图文上传前检查通过"))
        context = await open_xhs_context(playwright, self.account_file, headless=self.headless)

        try:
            page = await _get_context_page(context)
            await self.upload_note_content(page)
            await context.storage_state(path=self.account_file)
            xiaohongshu_logger.success(_msg("🥳", "cookie 更新完毕"))
        finally:
            await context.close()

    async def xiaohongshu_upload_note(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)

    async def main(self):
        await self.xiaohongshu_upload_note()
