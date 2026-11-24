"""Cookie 有效性校验：统一复用各平台 uploader 中维护的 cookie_auth 实现。

历史上这里维护着一份独立的校验逻辑（旧版选择器、明文 Playwright、有头浏览器），
与真正用于发布的 uploader 实现逐渐分叉，导致账号状态页出现难以解释的「异常」。现在只做分发。
"""
from pathlib import Path

from conf import BASE_DIR


def _load_checkers():
    """延迟导入，避免后端启动时就加载 patchright 和全部平台模块。"""
    from uploader.douyin_uploader.main import cookie_auth as douyin_auth
    from uploader.ks_uploader.main import cookie_auth as ks_auth
    from uploader.tencent_uploader.main import cookie_auth as tencent_auth
    from uploader.xiaohongshu_uploader.main import cookie_auth as xhs_auth

    # 平台类型：1 小红书 2 视频号 3 抖音 4 快手
    return {1: xhs_auth, 2: tencent_auth, 3: douyin_auth, 4: ks_auth}


def resolve_cookie_path(file_path) -> Path:
    """file_path 可能是绝对路径，也可能是 cookiesFile 目录下的文件名。"""
    path = Path(file_path)
    if path.is_absolute():
        return path
    return Path(BASE_DIR) / "cookiesFile" / path


async def check_cookie(platform_type, file_path):
    """返回 Cookie 是否仍然有效；平台不支持、文件缺失或校验异常时返回 False。"""
    try:
        checker = _load_checkers().get(int(platform_type))
    except (TypeError, ValueError):
        return False
    if checker is None:
        return False

    cookie_path = resolve_cookie_path(file_path)
    if not cookie_path.exists():
        return False

    try:
        return bool(await checker(str(cookie_path)))
    except Exception as exc:
        print(f"⚠️ Cookie 校验出错（type={platform_type}, file={cookie_path.name}）: {exc}")
        return False
