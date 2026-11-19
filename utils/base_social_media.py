from pathlib import Path
from typing import List

from conf import BASE_DIR

SOCIAL_MEDIA_DOUYIN = "douyin"
SOCIAL_MEDIA_TENCENT = "tencent"
SOCIAL_MEDIA_TIKTOK = "tiktok"
SOCIAL_MEDIA_BILIBILI = "bilibili"
SOCIAL_MEDIA_KUAISHOU = "kuaishou"


def get_supported_social_media() -> List[str]:
    return [SOCIAL_MEDIA_DOUYIN, SOCIAL_MEDIA_TENCENT, SOCIAL_MEDIA_TIKTOK, SOCIAL_MEDIA_KUAISHOU]


def get_cli_action() -> List[str]:
    return ["upload", "login", "watch"]


async def set_init_script(context, enable_stealth: bool = True):
    """注入 stealth 脚本。

    enable_stealth=False 时不注入：实测 stealth 会让抖音发布页的
    byte-uploader 创建 blob: Worker 被页面 CSP 拦截，视频一直卡在
    「0% 文件解析中」，60s 后报 1003000 上传失败。
    """
    if not enable_stealth:
        return context
    stealth_js_path = Path(BASE_DIR / "utils/stealth.min.js")
    await context.add_init_script(path=stealth_js_path)
    return context
