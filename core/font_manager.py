import os
import platform
import logging
from PIL import ImageFont

logger = logging.getLogger(__name__)

class FontManager:
    """
    跨平台中文字体与等宽英文字体载入管理器。
    支持 Windows、Raspberry Pi OS (Linux) 与本地项目资源目录自动发现。
    """
    _font_cache = {}

    @classmethod
    def get_font_path(cls) -> str:
        # 1. 检查本地项目 assets/fonts 目录
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        local_font_dir = os.path.join(project_root, "assets", "fonts")
        if os.path.exists(local_font_dir):
            for fname in os.listdir(local_font_dir):
                if fname.lower().endswith(('.ttf', '.ttc', '.otf')):
                    return os.path.join(local_font_dir, fname)

        # 2. 检查示例代码中的 picdir Font.ttc
        pic_font = os.path.join(os.path.dirname(project_root), "pic", "Font.ttc")
        if os.path.exists(pic_font):
            return pic_font

        # 3. 操作系统系统字体检测
        system = platform.system()
        if system == "Windows":
            win_candidates = [
                r"C:\Windows\Fonts\msyh.ttc",     # 微软雅黑
                r"C:\Windows\Fonts\msyhbd.ttc",   # 微软雅黑 Bold
                r"C:\Windows\Fonts\simhei.ttf",   # 黑体
                r"C:\Windows\Fonts\simsun.ttc",   # 宋体
            ]
            for p in win_candidates:
                if os.path.exists(p):
                    return p
        elif system == "Linux":
            linux_candidates = [
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",        # 文泉驿微米黑（树莓派常用）
                "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",           # 文泉驿正黑
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", # 思源黑体
                "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"
            ]
            for p in linux_candidates:
                if os.path.exists(p):
                    return p

        return ""

    @classmethod
    def load(cls, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        key = (size, bold)
        if key in cls._font_cache:
            return cls._font_cache[key]

        font_path = cls.get_font_path()
        if font_path and os.path.exists(font_path):
            try:
                font = ImageFont.truetype(font_path, size)
                cls._font_cache[key] = font
                return font
            except Exception as e:
                logger.warning(f"Failed to load font from {font_path}: {e}")

        # 兜底默认字体
        default_font = ImageFont.load_default()
        cls._font_cache[key] = default_font
        return default_font
