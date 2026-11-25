# -*- coding: utf-8 -*-
"""小红书视频发布流程。"""

from __future__ import annotations

import asyncio
from datetime import datetime

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

VIDEO_UPLOAD_SUCCESS_KEYWORDS = (
    "上传成功",
    "分辨率",
    "重新上传",
    "编辑封面",
    "已上传",
    "已选择",
    "100%",
)


class XiaoHongShuVideo(XiaoHongShuBaseUploader):
    def __init__(
        self,
        title,
        file_path,
        tags,
        publish_date: datetime | int,
        account_file,
        thumbnail_path=None,
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
        self.title = title
        self.file_path = file_path
        self.tags = tags or []
        self.thumbnail_path = thumbnail_path
        self.desc = desc or ""

    async def validate_upload_args(self):
        await self.validate_base_args()
        if not self.title or not str(self.title).strip():
            raise ValueError("视频模式下，title 是必须的")

        self.file_path = str(self.validate_video_file(self.file_path))
        if self.thumbnail_path:
            self.thumbnail_path = str(self.validate_image_file(self.thumbnail_path))

    async def handle_upload_error(self, page: Page):
        xiaohongshu_logger.warning(_msg("😵", "视频上传摔了一跤，小人马上重新上传"))
        await page.locator('div.progress-div [class^="upload-btn-input"]').set_input_files(self.file_path)

    async def _open_cover_modal(self, page: Page) -> None:
        cover_section = page.locator("text=设置封面").first
        try:
            await cover_section.scroll_into_view_if_needed(timeout=5000)
        except Exception:
            pass
        await page.wait_for_timeout(2000)

        upload_cover = page.locator("div.upload-cover").first
        if not await upload_cover.count():
            upload_cover = page.locator("div.cover-plugin-preview div.default.pointer").first
        await upload_cover.click(force=True)
        await page.wait_for_timeout(3000)

    async def _upload_cover_image(self, page: Page, thumbnail_path: str) -> None:
        upload_tab = page.get_by_text("上传封面", exact=True).first
        await upload_tab.wait_for(state="visible", timeout=10000)
        await upload_tab.click()
        await page.wait_for_timeout(2000)

        file_input = page.locator('div.upload-wrapper input[type="file"][accept*="image"]').first
        if not await file_input.count():
            file_input = page.locator('input[type="file"][accept*="image"]').last
        await file_input.set_input_files(thumbnail_path)
        await page.wait_for_timeout(4000)  # 等图片加载+裁剪渲染

    async def _confirm_cover(self, page: Page) -> None:
        modal_footer = page.locator("div.d-modal-footer")
        confirm = modal_footer.get_by_text("确定", exact=True).first
        if not await confirm.count():
            confirm = page.get_by_role("button", name="确定").first
        await confirm.wait_for(state="visible", timeout=10000)
        await confirm.click()

        modal = page.locator("div.d-modal")
        try:
            await modal.first.wait_for(state="hidden", timeout=15000)
        except Exception:
            pass

    async def set_thumbnail(self, page: Page, thumbnail_path: str):
        if not thumbnail_path:
            return

        xiaohongshu_logger.info(_msg("🖼️", "小人准备设置封面"))
        # 封面设置为增强步骤：失败时记 warning 跳过、继续发布（用视频首帧兜底）。
        try:
            await self._open_cover_modal(page)
            await self._upload_cover_image(page, thumbnail_path)
            await self._confirm_cover(page)
            xiaohongshu_logger.success(_msg("🥳", "封面已经设置完成"))
        except Exception as exc:
            xiaohongshu_logger.warning(_msg("🖼️", f"封面设置失败，跳过该步骤继续发布（用视频首帧）：{exc}"))
            try:
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(500)
            except Exception:
                pass

    async def _preview_shows_upload_success(self, page: Page, preview_new) -> bool:
        all_text = await preview_new.inner_text()
        if any(keyword in all_text for keyword in VIDEO_UPLOAD_SUCCESS_KEYWORDS):
            return True

        for stage in await preview_new.query_selector_all("div.stage"):
            text_content = await page.evaluate("(element) => element.textContent", stage)
            if "上传成功" in text_content or "分辨率" in text_content:
                return True
        return False

    async def _title_input_ready(self, page: Page) -> bool:
        title_container = page.locator('input[placeholder*="填写标题"]')
        return await title_container.count() > 0 and await title_container.is_visible()

    async def _wait_for_video_uploaded(self, page: Page) -> None:
        while True:
            try:
                upload_input = await page.wait_for_selector("input.upload-input", timeout=3000)
                preview_new = await upload_input.query_selector(
                    'xpath=following-sibling::div[contains(@class, "preview-new")]'
                )
                if preview_new:
                    if await self._preview_shows_upload_success(page, preview_new):
                        xiaohongshu_logger.success(_msg("🥳", "视频已经传完啦"))
                        return
                    if self.debug:
                        all_text = await preview_new.inner_text()
                        normalized_text = all_text.strip().replace("\n", " ")
                        xiaohongshu_logger.debug(_msg("🧍", f"预览区域内容: {normalized_text}"))
                    xiaohongshu_logger.debug(_msg("🧍", "还没看到上传成功标识，小人继续等一会"))
                elif await self._title_input_ready(page):
                    xiaohongshu_logger.success(_msg("🥳", "虽然没看到预览区，但标题框出来了，小人继续"))
                    return
                else:
                    xiaohongshu_logger.debug(_msg("🧍", "还没拿到预览区域，小人继续等一会"))
            except Exception as e:
                xiaohongshu_logger.debug(_msg("😵", f"上传状态还没稳定下来，小人继续观察: {e}"))
            await asyncio.sleep(2)

    async def upload_video_content(self, page: Page) -> None:
        xiaohongshu_logger.info(_msg("🏃", f"小人开始搬运视频: {self.title}.mp4"))
        xiaohongshu_logger.info(_msg("🧭", "小人先回创作中心逛一会，再赶往视频发布页"))
        await self.warm_up_before_publish(page)
        publish_url = _build_xhs_creator_url("/publish/publish?from=homepage&target=video")
        await page.goto(publish_url)
        await _raise_if_login_required(page)
        await page.wait_for_url(publish_url)
        await page.locator("div[class^='upload-content'] input[class='upload-input']").set_input_files(self.file_path)
        await self._wait_for_video_uploaded(page)

        xiaohongshu_logger.info(_msg("✍️", "小人开始填标题、描述和话题"))
        await self.fill_meta(page)
        await self.set_thumbnail(page, self.thumbnail_path)
        await self.check_original_declaration(page)

        if self.publish_strategy == XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED and self.publish_date != 0:
            await self.set_schedule_time_xiaohongshu(page, self.publish_date)

        await self.submit_publish(page, "视频")

    async def upload(self, playwright: Playwright) -> None:
        xiaohongshu_logger.info(_msg("🧍", "小人先检查 cookie、视频文件、封面和发布时间"))
        await self.validate_upload_args()
        xiaohongshu_logger.info(_msg("🥳", "上传前检查通过"))
        context = await open_xhs_context(playwright, self.account_file, headless=self.headless)

        try:
            page = await _get_context_page(context)
            await self.upload_video_content(page)
            await context.storage_state(path=self.account_file)
            xiaohongshu_logger.success(_msg("🥳", "cookie 更新完毕"))
        finally:
            await context.close()

    async def xiaohongshu_upload_video(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)

    async def main(self):
        await self.xiaohongshu_upload_video()
