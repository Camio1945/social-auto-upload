# -*- coding: utf-8 -*-
"""小红书发布器的公共基类：参数校验、拟人输入、位置/声明设置与发布提交。"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime

from patchright.async_api import Page

from conf import DEBUG_MODE, LOCAL_CHROME_HEADLESS, LOCAL_CHROME_PATH
from uploader.base_video import BaseVideoUploader
from uploader.xiaohongshu_uploader.browser import (
    XHS_PUBLISH_SUCCESS_URL_PATTERN,
    XIAOHONGSHU_PUBLISH_STRATEGY_IMMEDIATE,
    XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED,
    _build_xhs_creator_url,
    _msg,
    _raise_if_login_required,
)
from uploader.xiaohongshu_uploader.human_behavior import human_browse
from uploader.xiaohongshu_uploader.human_behavior import human_click
from uploader.xiaohongshu_uploader.human_behavior import human_pause
from uploader.xiaohongshu_uploader.human_behavior import human_type
from uploader.xiaohongshu_uploader.session import ensure_publish_quota
from uploader.xiaohongshu_uploader.session import record_publish
from utils.log import xiaohongshu_logger


async def _js_click_by_text(page: Page, text: str) -> bool:
    """用 JS 找到文字完全匹配的最内层元素并点击它及其祖先（绕过 span pointer-events:none / 遮罩拦截）。

    小红书很多可点项文字在 <span class="d-text"> 里，pointer-events 常被禁用，
    Playwright 常规 click 会超时。用原生 click 冒泡触发 Vue 事件更可靠。
    """
    return await page.evaluate(
        """(t) => {
            const nodes = [...document.querySelectorAll('*')].filter(
                e => e.children.length === 0 && (e.textContent || '').trim() === t
            );
            if (!nodes.length) return false;
            let el = nodes[nodes.length - 1];
            for (let i = 0; i < 4 && el; i++) { try { el.click(); } catch (e) {} el = el.parentElement; }
            return true;
        }""",
        text,
    )


class XiaoHongShuBaseUploader(BaseVideoUploader):
    def __init__(
        self,
        publish_date: datetime | int,
        account_file,
        publish_strategy: str = XIAOHONGSHU_PUBLISH_STRATEGY_IMMEDIATE,
        debug: bool = DEBUG_MODE,
        headless: bool = LOCAL_CHROME_HEADLESS,
    ):
        self.publish_date = publish_date
        self.account_file = str(account_file)
        self.publish_strategy = publish_strategy
        self.debug = debug
        self.date_format = "%Y年%m月%d日 %H:%M"
        self.local_executable_path = LOCAL_CHROME_PATH
        self.headless = headless

    async def validate_base_args(self):
        if not os.path.exists(self.account_file):
            raise RuntimeError(f"cookie文件不存在，请先完成小红书登录: {self.account_file}")
        if self.publish_strategy not in {
            XIAOHONGSHU_PUBLISH_STRATEGY_IMMEDIATE,
            XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED,
        }:
            raise ValueError(f"不支持的发布策略: {self.publish_strategy}")

        ensure_publish_quota(self.account_file)

        if self.publish_strategy == XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED:
            self.publish_date = self.validate_publish_date(self.publish_date)
        else:
            self.publish_date = 0

    async def warm_up_before_publish(self, page: Page) -> None:
        """发布前先回创作中心停留浏览，补齐真人导航链和停留时长。"""
        try:
            await page.goto(_build_xhs_creator_url("/"), wait_until="domcontentloaded")
            await _raise_if_login_required(page)
            await human_browse(page, 10, 25)
        except RuntimeError:
            raise
        except Exception as exc:
            xiaohongshu_logger.warning(_msg("🌱", f"发布前浏览预热失败，继续发布: {exc}"))

    async def submit_publish(self, page: Page, label: str, max_attempts: int = 20) -> None:
        """随机停顿后点击发布，失败按真人节奏重试，最多 max_attempts 次。"""
        for _ in range(max_attempts):
            try:
                await human_pause(1500, 4000)
                if self.publish_strategy == XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED:
                    button = page.locator('button:has-text("定时发布")').first
                else:
                    button = page.locator('button:has-text("发布")').first
                await human_click(page, button)
                await page.wait_for_url(XHS_PUBLISH_SUCCESS_URL_PATTERN, timeout=5000)
                xiaohongshu_logger.success(_msg("🥳", f"{label}发布成功，小人开心收工"))
                record_publish(self.account_file)
                return
            except Exception:
                xiaohongshu_logger.info(_msg("🏃", f"小人正在冲刺发布{label}"))
                if self.debug:
                    await page.screenshot(full_page=True)
                await human_pause(1500, 3500)
        raise RuntimeError(f"{label}发布重试 {max_attempts} 次仍未成功，请检查发布页状态")

    async def set_schedule_time_xiaohongshu(self, page: Page, publish_date: datetime):
        xiaohongshu_logger.info(_msg("🕒", f"小人准备设置定时发布时间: {publish_date.strftime(self.date_format)}"))
        await page.locator(".custom-switch-card").filter(has_text="定时发布").locator(".d-switch").click()
        await asyncio.sleep(1)
        publish_date_hour = publish_date.strftime("%Y-%m-%d %H:%M")
        time_input = page.locator(".d-datepicker-input-filter input.d-text")
        await time_input.fill(str(publish_date_hour))
        await asyncio.sleep(1)

    async def _wait_for_location_dropdown(self, page: Page) -> None:
        dropdown_selector = "div.d-popover.d-popover-default.d-dropdown.--size-min-width-large"
        await page.wait_for_timeout(2000)
        try:
            await page.wait_for_selector(dropdown_selector, timeout=3000)
        except Exception:
            xiaohongshu_logger.warning(_msg("😵", "位置下拉列表没按预期出现，小人继续按旧逻辑查找"))
        await page.wait_for_timeout(4000)

    async def _find_location_option(self, page: Page, location: str):
        prefix = (
            '//div[contains(@class, "d-popover") and contains(@class, "d-dropdown")]'
            '//div[contains(@class, "d-options-wrapper")]'
            '//div[contains(@class, "d-grid") and contains(@class, "d-options")]'
        )
        option = await page.wait_for_selector(
            f'{prefix}//div[contains(@class, "name") and text()="{location}"]',
            timeout=3000,
        )
        if option:
            return option
        return await page.wait_for_selector(
            f'{prefix}/div[1]//div[contains(@class, "name") and text()="{location}"]',
            timeout=2000,
        )

    async def _log_location_candidates(self, page: Page) -> None:
        try:
            all_options = await page.query_selector_all(
                '//div[contains(@class, "d-popover") and contains(@class, "d-dropdown")]'
                '//div[contains(@class, "d-options-wrapper")]'
                '//div[contains(@class, "d-grid") and contains(@class, "d-options")]'
                "/div"
            )
            xiaohongshu_logger.debug(_msg("🧍", f"位置下拉里一共找到 {len(all_options)} 个选项"))
            for i, option in enumerate(all_options[:3]):
                option_text = await option.inner_text()
                xiaohongshu_logger.debug(_msg("🧾", f"候选位置 {i + 1}: {option_text.strip()[:50]}"))
        except Exception as inner_e:
            xiaohongshu_logger.debug(_msg("😵", f"读取位置候选列表失败: {inner_e}"))

    async def set_location(self, page: Page, location: str = "青岛市"):
        if not location:
            return True

        xiaohongshu_logger.info(_msg("📍", f"小人准备设置位置: {location}"))
        loc_ele = await page.wait_for_selector("div.d-text.d-select-placeholder.d-text-ellipsis.d-text-nowrap")
        await loc_ele.click()
        await page.wait_for_timeout(1000)
        await page.keyboard.type(location)
        await self._wait_for_location_dropdown(page)

        try:
            location_option = await self._find_location_option(page, location)
            await location_option.scroll_into_view_if_needed()
            await location_option.click()
            xiaohongshu_logger.success(_msg("🥳", f"位置已经设置成 {location}"))
            return True
        except Exception as e:
            xiaohongshu_logger.error(_msg("😢", f"设置位置失败: {e}"))
            await self._log_location_candidates(page)
            return False

    async def fill_title(self, page: Page) -> None:
        title_container = page.locator('input[placeholder*="填写标题"]')
        await title_container.fill(self.title[:20])

    async def fill_desc(self, page: Page) -> None:
        if not getattr(self, "desc", ""):
            return

        desc = page.locator('p[data-placeholder*="输入正文描述"]')
        await human_click(page, desc)
        await page.keyboard.press("Backspace")
        await page.keyboard.press("Control+KeyA")
        await page.keyboard.press("Delete")
        await human_type(page, self.desc)
        await page.keyboard.press("Enter")

    async def fill_tags(self, page: Page) -> None:
        if not getattr(self, "tags", None):
            return

        # 小红书标签上限为 10 个，超过会导致死循环卡住发布
        max_tags = 10
        if len(self.tags) > max_tags:
            xiaohongshu_logger.warning(
                _msg("🏷️", f"标签数量 {len(self.tags)} 超过小红书上限 {max_tags}，只取前 {max_tags} 个")
            )
            self.tags = self.tags[:max_tags]

        if not getattr(self, "desc", ""):
            desc = page.locator('p[data-placeholder*="输入正文描述"]')
            await human_click(page, desc)

        for tag in self.tags:  # 循环处理所有 tags
            # 话题候选下拉框依赖小红书联想接口实时返回，网络抖动/无匹配时会等不到。
            # 标签是可选增强项：等不到候选框就跳过该标签继续，不让整条发布因此失败。
            try:
                await human_type(page, "#" + tag, min_delay=60, max_delay=200)
                await page.locator("#creator-editor-topic-container").wait_for(
                    state="visible",
                    timeout=6000,
                )
                first_item = page.locator("#creator-editor-topic-container .item").first
                await first_item.wait_for(state="visible", timeout=4000)
                await human_click(page, first_item)
            except Exception as exc:
                xiaohongshu_logger.warning(_msg("🏷️", f"话题『{tag}』未出现候选，跳过该标签继续发布: {exc}"))
                # 清掉已键入但未成词的 "#tag" 文本，避免它残留进正文
                for _ in range(len("#" + tag)):
                    await page.keyboard.press("Backspace")
                continue

    async def fill_meta(self, page: Page) -> None:
        await self.fill_title(page)
        await self.fill_desc(page)
        await self.fill_tags(page)

    async def check_original_declaration(self, page: Page) -> None:
        """设置「来源转载」声明，填写转载来源。

        流程（对应 codegen 录制）：
          点「添加内容类型声明」→ 点包含「来源转载」的 div
          → 填 placeholder「请输入媒体名称」→ 点 button「确认」。
        容错：任一步失败记 warning 跳过、继续发布，不中断。
        """
        source = getattr(self, "repost_source", "") or ""
        try:
            # 1. 点「添加内容类型声明」
            trigger = page.get_by_text("添加内容类型声明", exact=False).first
            try:
                await trigger.scroll_into_view_if_needed(timeout=5000)
            except Exception:
                pass
            await trigger.click(force=True)
            await page.wait_for_timeout(1500)

            # 2. 选「来源转载」选项
            import re as _re

            repost_option = page.locator("#publish-container div").filter(has_text=_re.compile(r"^来源转载$")).last
            if await repost_option.count():
                await repost_option.click(force=True)
            else:
                await _js_click_by_text(page, "来源转载")
            await page.wait_for_timeout(1500)

            # 3. 填写媒体名称
            source_input = page.get_by_placeholder("请输入媒体名称").first
            await source_input.wait_for(state="visible", timeout=8000)
            await source_input.click()
            await source_input.fill(source)
            await page.wait_for_timeout(500)

            # 4. 点「确认」按钮
            confirm = page.get_by_role("button", name="确认").first
            try:
                await confirm.wait_for(state="visible", timeout=5000)
                await confirm.click()
            except Exception:
                await _js_click_by_text(page, "确认")

            await page.wait_for_timeout(1000)
            xiaohongshu_logger.success(_msg("🧾", f"来源转载已声明（来源：{source}）"))
        except Exception as exc:
            xiaohongshu_logger.warning(_msg("⚠️", f"设置来源转载失败，跳过继续发布: {exc}"))
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass
