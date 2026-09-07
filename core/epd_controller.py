import os
import sys
import logging
from typing import Optional
from PIL import Image

logger = logging.getLogger(__name__)

class EPDController:
    """
    微雪 7.5 英寸 V2 墨水屏硬件控制器封装。
    具备防残影计数、局部/全屏刷新智能调度、屏幕休眠保护与跨平台虚拟调试（Mock）能力。
    """

    def __init__(self, config: dict):
        self.config = config.get("system", {})
        self.width = self.config.get("device_width", 800)
        self.height = self.config.get("device_height", 480)
        self.max_partial = self.config.get("max_partial_refreshes_before_full", 20)
        self.rotation = self.config.get("rotation", 180)
        self.partial_count = 0
        self.is_hardware_available = False
        self.epd = None
        self.last_image: Optional[Image.Image] = None
        self.is_sleeping = False
        self.is_part_initialized = False

        self._init_driver()

    def _apply_rotation(self, image: Image.Image) -> Image.Image:
        """根据硬件安装方向旋转画面（默认 180 度修正倒装）"""
        if self.rotation == 180:
            return image.rotate(180)
        elif self.rotation == 90:
            return image.rotate(90, expand=True)
        elif self.rotation == 270:
            return image.rotate(270, expand=True)
        return image

    def _init_driver(self):
        """尝试导入微雪驱动，若在非树莓派环境则无缝降级为虚拟屏幕模式"""
        # 兼容微雪常见的 lib 路径
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        lib_dir = os.path.join(root_dir, "lib")
        if os.path.exists(lib_dir):
            sys.path.append(lib_dir)

        try:
            from waveshare_epd import epd7in5_V2_old
            self.epd = epd7in5_V2_old.EPD()
            self.is_hardware_available = True
            logger.info("Waveshare EPD 7in5_V2 hardware driver loaded successfully.")
        except Exception as e:
            self.is_hardware_available = False
            logger.info(f"Waveshare hardware not detected ({e}). Running in Virtual/Mock EPD mode.")

    def display_full(self, image: Image.Image):
        """
        全屏完整刷新：消除残影，重置局部刷新计数器。
        刷新后自动将硬件底层切入局部模式（init_part），为后续无感局刷做好准备。
        """
        self.last_image = image
        self._save_preview(image)

        hw_image = self._apply_rotation(image)

        if self.is_hardware_available and self.epd:
            try:
                logger.info(f"Executing EPD Full Refresh (Clearing ghosting, Rotation: {self.rotation}°)...")
                self.epd.init()
                self.epd.display(self.epd.getbuffer(hw_image))
                self.partial_count = 0
                self.is_sleeping = False

                # 全刷完成后立即载入局部波形，使硬件就绪，后续局刷绝对零闪烁
                self.epd.init_part()
                self.is_part_initialized = True
                logger.info("EPD transitioned to partial mode ready for silent updates.")
            except Exception as e:
                logger.error(f"Hardware display_full error: {e}")
        else:
            logger.info(f"[Mock EPD] Executed Full Refresh (Rotation: {self.rotation}°).")
            self.partial_count = 0
            self.is_part_initialized = True

    def display_partial(self, image: Image.Image):
        """
        局部刷新：无全屏黑白闪烁反转，仅瞬间快速更新变动数值与走势图。
        """
        self.last_image = image
        self._save_preview(image)

        # 检查是否需要触发全屏除残影 (当 max_partial > 0 且达到阈值时)
        if self.max_partial > 0 and self.partial_count >= self.max_partial:
            logger.info(f"Partial refresh count reached limit ({self.max_partial}), triggering full refresh to clear ghosting.")
            self.display_full(image)
            return

        hw_image = self._apply_rotation(image)

        if self.is_hardware_available and self.epd:
            try:
                # 仅在初次启动或刚从深度休眠中唤醒时载入一次局部波形
                if not getattr(self, "is_part_initialized", False) or self.is_sleeping:
                    logger.info("Initializing EPD into partial mode (one-time setup or woke from sleep)...")
                    self.epd.init_part()
                    self.is_part_initialized = True
                    self.is_sleeping = False

                buf = self.epd.getbuffer(hw_image)
                self.epd.display_Partial(buf, 0, 0, self.width, self.height)
                self.partial_count += 1
                logger.info(f"EPD Silent Partial Refresh executed (Count: {self.partial_count}/{self.max_partial}, Rotation: {self.rotation}°)")
            except Exception as e:
                logger.error(f"Hardware display_partial error: {e}")
        else:
            self.partial_count += 1
            logger.info(f"[Mock EPD] Silent Partial Refresh executed (Count: {self.partial_count}/{self.max_partial}, Rotation: {self.rotation}°)")

    def clear(self):
        """全屏清白"""
        if self.is_hardware_available and self.epd:
            try:
                self.epd.init()
                self.epd.Clear()
                self.partial_count = 0
                self.is_sleeping = False
                self.is_part_initialized = False
            except Exception as e:
                logger.error(f"Hardware clear error: {e}")
        else:
            logger.info("[Mock EPD] Clear screen executed.")

    def sleep(self):
        """墨水屏进入深度休眠，释放电压以保护屏幕"""
        if self.is_hardware_available and self.epd and not self.is_sleeping:
            try:
                self.epd.sleep()
                self.is_sleeping = True
                self.is_part_initialized = False
                logger.info("EPD entered sleep mode.")
            except Exception as e:
                logger.error(f"Hardware sleep error: {e}")
        else:
            self.is_sleeping = True
            self.is_part_initialized = False
            logger.info("[Mock EPD] EPD sleep mode.")

    def _save_preview(self, image: Image.Image):
        """保存最新预览图片，供 Streamlit 和本地无屏时实时查看"""
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        preview_path = os.path.join(root_dir, "latest_preview.png")
        try:
            image.save(preview_path)
        except Exception as e:
            logger.debug(f"Could not save preview: {e}")
