# -*- coding: utf-8 -*-
"""小红书发布用的人性化操作层。

风控不只看浏览器指纹，也看操作节奏：真人会有鼠标轨迹、打字间隔抖动和
浏览停留，而 locator.click() / keyboard.type() 是零轨迹、恒定间隔的。
这里提供一组尽力而为的拟人操作，失败时不阻断主流程。
"""

from __future__ import annotations

import asyncio
import random


async def human_pause(min_ms: int = 300, max_ms: int = 1200) -> None:
    await asyncio.sleep(random.uniform(min_ms, max_ms) / 1000)


async def _viewport_size(page) -> tuple[float, float]:
    try:
        size = await page.evaluate("() => [window.innerWidth, window.innerHeight]")
        if size and size[0] and size[1]:
            return float(size[0]), float(size[1])
    except Exception:
        pass
    return 1280.0, 800.0


async def human_mouse_move(page, target_x: float, target_y: float) -> None:
    """用二次贝塞尔曲线从随机起点移动到目标点，模拟真人鼠标轨迹。"""
    width, height = await _viewport_size(page)
    start_x = random.uniform(width * 0.25, width * 0.75)
    start_y = random.uniform(height * 0.25, height * 0.75)
    control_x = (start_x + target_x) / 2 + random.uniform(-120, 120)
    control_y = (start_y + target_y) / 2 + random.uniform(-120, 120)
    steps = random.randint(14, 26)
    try:
        await page.mouse.move(start_x, start_y)
        for step in range(1, steps + 1):
            t = step / steps
            x = (1 - t) ** 2 * start_x + 2 * (1 - t) * t * control_x + t * t * target_x
            y = (1 - t) ** 2 * start_y + 2 * (1 - t) * t * control_y + t * t * target_y
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.008, 0.028))
    except Exception:
        pass


async def human_click(page, locator) -> None:
    """先滚动到可视区，再移动鼠标、停顿、按随机延迟点击。"""
    try:
        await locator.scroll_into_view_if_needed(timeout=3000)
    except Exception:
        pass

    try:
        box = await locator.bounding_box()
    except Exception:
        box = None

    if not box:
        await locator.click()
        return

    x = box["x"] + box["width"] * random.uniform(0.35, 0.65)
    y = box["y"] + box["height"] * random.uniform(0.35, 0.65)
    await human_mouse_move(page, x, y)
    await human_pause(120, 420)
    await page.mouse.click(x, y, delay=random.randint(30, 110))


async def human_type(page, text: str, min_delay: int = 45, max_delay: int = 180) -> None:
    """分段输入，每段延迟随机，偶尔停顿，避免恒定 30ms 的机器节奏。"""
    if not text:
        return

    index = 0
    while index < len(text):
        chunk_size = random.randint(1, 3)
        chunk = text[index : index + chunk_size]
        await page.keyboard.type(chunk, delay=random.randint(min_delay, max_delay))
        index += chunk_size
        if random.random() < 0.07:
            await human_pause(300, 1200)


async def human_browse(page, min_seconds: int = 10, max_seconds: int = 25) -> None:
    """模拟真人浏览：随机滚动、移动鼠标、停顿。"""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + random.uniform(min_seconds, max_seconds)
    width, height = await _viewport_size(page)

    while loop.time() < deadline:
        action = random.random()
        try:
            if action < 0.5:
                await page.mouse.wheel(0, random.randint(120, 520))
            elif action < 0.8:
                await page.mouse.move(
                    random.uniform(0, width),
                    random.uniform(height * 0.2, height * 0.8),
                )
        except Exception:
            pass
        await human_pause(600, 2200)
