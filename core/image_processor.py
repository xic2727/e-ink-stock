from PIL import Image, ImageEnhance, ImageOps
from typing import Tuple

class ImageProcessor:
    """
    针对 1-bit 单色墨水屏的图像处理管线：
    负责将任意彩色/灰度折线图转化为适合 800x480 墨水屏显示的纯黑白高清晰度位图。
    """

    @staticmethod
    def process_chart_for_eink(
        image: Image.Image,
        target_size: Tuple[int, int],
        contrast_factor: float = 1.4,
        use_dither: bool = True,
        threshold: int = 200
    ) -> Image.Image:
        """
        处理外部折线图图片：
        1. RGBA/P 转 RGB 并填白底
        2. 高质量缩放至 target_size
        3. 对比度与亮度优化
        4. 二值化（Floyd-Steinberg 误差扩散抖动 或 固定阈值切分）
        :return: 模式为 '1' 的二值 PIL 图像 (0: 黑色, 255: 白色)
        """
        # 1. 确保为 RGB 且背景为白
        if image.mode in ('RGBA', 'LA'):
            bg = Image.new('RGB', image.size, (255, 255, 255))
            bg.paste(image, mask=image.split()[-1])
            image = bg
        elif image.mode != 'RGB':
            image = image.convert('RGB')

        # 检查是否为深色/黑底图，若是则自动反色为白底黑线
        gray = image.convert('L')
        stat = gray.histogram()
        # 简单判断暗部像素是否占绝大多数
        dark_pixels = sum(stat[:100])
        total_pixels = image.width * image.height
        if dark_pixels / total_pixels > 0.6:
            image = ImageOps.invert(image)

        # 2. 缩放到目标尺寸
        image = image.resize(target_size, Image.Resampling.LANCZOS)

        # 3. 对比度增强
        if contrast_factor != 1.0:
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(contrast_factor)

        # 4. 转为单色二值图
        if use_dither:
            # 误差扩散抖动，保留灰度层次过渡
            eink_img = image.convert('1', dither=Image.Dither.FLOYDSTEINBERG)
        else:
            # 阈值直接二值化，线条极其锐利
            gray = image.convert('L')
            eink_img = gray.point(lambda p: 255 if p > threshold else 0, mode='1')

        return eink_img
