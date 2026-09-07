import os
from typing import List, Optional, Tuple, Dict, Any
from PIL import Image, ImageDraw, ImageFont
from core.models import StockQuote, StockIndex, LayoutMode, MarketStatus, SystemState
from core.font_manager import FontManager
from core.image_processor import ImageProcessor

class LayoutRenderer:
    """
    800x480 墨水屏位图排版与渲染引擎。
    将股票数据、大盘指数与折线图生成为 1-bit 单色 PIL.Image (0:黑, 255:白)。
    """
    WIDTH = 800
    HEIGHT = 480

    def __init__(self):
        # 预加载常用字号
        self.font_title = FontManager.load(24, bold=True)
        self.font_large = FontManager.load(36, bold=True)
        self.font_medium = FontManager.load(18, bold=True)
        self.font_regular = FontManager.load(15, bold=False)
        self.font_small = FontManager.load(12, bold=False)
        self.font_badge = FontManager.load(14, bold=True)

    def render(
        self,
        stocks: List[StockQuote],
        indices: List[StockIndex],
        state: SystemState,
        chart_images: Dict[str, Image.Image],
        layout_mode: LayoutMode = LayoutMode.FOCUS_AND_LIST,
        focus_index: int = 0,
        config: Optional[Dict[str, Any]] = None
    ) -> Image.Image:
        """
        根据指定布局模式渲染完整的 800x480 单色位图。
        """
        # 创建 1-bit 单色纯白画布
        canvas = Image.new('1', (self.WIDTH, self.HEIGHT), 255)
        draw = ImageDraw.Draw(canvas)

        # 1. 绘制全局顶部状态栏 (高度 38px)
        self._render_header(draw, indices, state)

        # 2. 根据布局模式渲染内容区域
        if not stocks:
            self._render_empty_state(draw)
            return canvas

        if layout_mode == LayoutMode.FOCUS_AND_LIST:
            self._render_focus_and_list(canvas, draw, stocks, chart_images, focus_index, config)
        elif layout_mode == LayoutMode.DUAL_COMPARE:
            self._render_dual_compare(canvas, draw, stocks, chart_images, config)
        elif layout_mode == LayoutMode.GRID_OVERVIEW:
            self._render_grid_overview(canvas, draw, stocks, config)
        else:
            self._render_focus_and_list(canvas, draw, stocks, chart_images, focus_index, config)

        return canvas

    def _render_header(self, draw: ImageDraw.Draw, indices: List[StockIndex], state: SystemState):
        """绘制顶部状态栏：指数、时间、交易状态"""
        header_h = 36
        draw.rectangle([0, 0, self.WIDTH, header_h], fill=255)
        draw.line([(0, header_h), (self.WIDTH, header_h)], fill=0, width=2)

        # 左侧绘制核心指数（如上证、深证）
        x_offset = 12
        for idx in indices[:2]:
            arrow = "▲" if idx.change_pct > 0 else ("▼" if idx.change_pct < 0 else "-")
            sign = "+" if idx.change_pct > 0 else ""
            idx_str = f"{idx.name} {idx.points:.2f} {arrow}{sign}{idx.change_pct:.2f}%"
            draw.text((x_offset, 9), idx_str, font=self.font_small, fill=0)
            x_offset += 210

        # 右侧绘制时间和市场状态
        time_str = state.market_status.value
        clock_str = state.update_time_str if hasattr(state, 'update_time_str') else ""
        if not clock_str:
            import datetime
            clock_str = datetime.datetime.now().strftime("%H:%M:%S")

        status_text = f"[{time_str}] {clock_str}"
        draw.text((self.WIDTH - 165, 9), status_text, font=self.font_badge, fill=0)

    def _render_focus_and_list(
        self,
        canvas: Image.Image,
        draw: ImageDraw.Draw,
        stocks: List[StockQuote],
        chart_images: Dict[str, Image.Image],
        focus_idx: int,
        config: Optional[Dict[str, Any]]
    ):
        """
        模式一：主力聚焦 (左侧 530px) + 自选股侧边栏 (右侧 270px)
        """
        split_x = 530
        draw.line([(split_x, 36), (split_x, self.HEIGHT)], fill=0, width=2)

        # 确定主力股票
        if 0 <= focus_idx < len(stocks):
            focus_stock = stocks[focus_idx]
        else:
            focus_stock = stocks[0]

        # ---------------- 左侧主力股票渲染 ----------------
        left_pad = 14
        top_y = 44

        # 股票名称与代码
        name_str = focus_stock.name
        code_str = f"({focus_stock.code})"
        draw.text((left_pad, top_y), name_str, font=self.font_title, fill=0)
        # 获取名称文字宽度以放置代码
        name_bbox = draw.textbbox((left_pad, top_y), name_str, font=self.font_title)
        draw.text((name_bbox[2] + 8, top_y + 6), code_str, font=self.font_regular, fill=0)

        # 价格与涨跌幅
        price_y = top_y + 32
        price_str = f"{focus_stock.price:.2f}"
        draw.text((left_pad, price_y), price_str, font=self.font_large, fill=0)
        price_bbox = draw.textbbox((left_pad, price_y), price_str, font=self.font_large)

        # 涨跌幅徽章 (Badge)
        badge_x = price_bbox[2] + 16
        badge_y = price_y + 6
        self._draw_change_badge(
            draw,
            focus_stock.change_pct,
            focus_stock.change_amt,
            x=badge_x,
            y=badge_y,
            font=self.font_badge
        )

        # 核心财务与量价指标
        info_y = price_y + 44
        vol_str = self._format_volume(focus_stock.volume)
        turn_str = self._format_turnover(focus_stock.turnover)
        line1 = f"今开: {focus_stock.open_price:.2f}   最高: {focus_stock.high_price:.2f}   最低: {focus_stock.low_price:.2f}"
        line2 = f"昨收: {focus_stock.prev_close:.2f}   成交量: {vol_str}   成交额: {turn_str}"
        draw.text((left_pad, info_y), line1, font=self.font_small, fill=0)
        draw.text((left_pad, info_y + 18), line2, font=self.font_small, fill=0)

        # 分时折线图
        chart_w = split_x - left_pad * 2
        chart_h = self.HEIGHT - (info_y + 40) - 10
        chart_x = left_pad
        chart_y = info_y + 40

        chart_img = chart_images.get(focus_stock.code)
        if chart_img:
            # 二值化适配
            eink_chart = ImageProcessor.process_chart_for_eink(chart_img, (chart_w, chart_h))
            canvas.paste(eink_chart, (chart_x, chart_y))
        else:
            draw.rectangle([chart_x, chart_y, chart_x + chart_w, chart_y + chart_h], outline=0, width=1)
            draw.text((chart_x + chart_w // 2 - 50, chart_y + chart_h // 2 - 10), "折线图加载中...", font=self.font_regular, fill=0)

        # ---------------- 右侧自选股侧边栏渲染 ----------------
        right_x = split_x + 12
        right_w = self.WIDTH - right_x - 12
        sidebar_y = 44

        draw.text((right_x, sidebar_y), f"自选股池 ({len(stocks)})", font=self.font_medium, fill=0)
        draw.line([(right_x, sidebar_y + 24), (self.WIDTH - 12, sidebar_y + 24)], fill=0, width=1)

        card_top = sidebar_y + 30
        max_display = min(4, len(stocks))
        card_h = (self.HEIGHT - card_top - 10) // max_display

        # 剔除主力股票或包含主力股票展示
        for i in range(max_display):
            s = stocks[i]
            cy = card_top + i * card_h

            # 当前卡片外框或下划线
            if i > 0:
                draw.line([(right_x, cy - 2), (self.WIDTH - 12, cy - 2)], fill=0, width=1)

            # 标亮当前主力选中的卡片
            is_active = (i == focus_idx)
            if is_active:
                draw.rectangle([right_x - 4, cy, right_x - 1, cy + card_h - 6], fill=0)

            # 股票名与代码
            draw.text((right_x + 4, cy + 4), s.name[:6], font=self.font_medium, fill=0)
            draw.text((right_x + 4, cy + 28), s.code, font=self.font_small, fill=0)

            # 现价与涨跌幅
            price_txt = f"{s.price:.2f}"
            p_bbox = draw.textbbox((0, 0), price_txt, font=self.font_medium)
            p_w = p_bbox[2] - p_bbox[0]
            draw.text((self.WIDTH - 14 - p_w, cy + 4), price_txt, font=self.font_medium, fill=0)

            # 迷你涨跌标签
            arrow = "▲" if s.change_pct > 0 else ("▼" if s.change_pct < 0 else "")
            sign = "+" if s.change_pct > 0 else ""
            pct_txt = f"{arrow}{sign}{s.change_pct:.2f}%"
            self._draw_mini_badge(draw, s.change_pct, pct_txt, self.WIDTH - 14, cy + 28, font=self.font_badge)

    def _render_dual_compare(
        self,
        canvas: Image.Image,
        draw: ImageDraw.Draw,
        stocks: List[StockQuote],
        chart_images: Dict[str, Image.Image],
        config: Optional[Dict[str, Any]]
    ):
        """模式二：双股走势并列对比 (每边 400px)"""
        mid_x = self.WIDTH // 2
        draw.line([(mid_x, 36), (mid_x, self.HEIGHT)], fill=0, width=2)

        compare_stocks = stocks[:2]
        for i, stock in enumerate(compare_stocks):
            box_x = 0 if i == 0 else mid_x
            pad = 12
            x = box_x + pad
            y = 44

            draw.text((x, y), f"{stock.name} ({stock.code})", font=self.font_title, fill=0)
            draw.text((x, y + 32), f"{stock.price:.2f}", font=self.font_large, fill=0)
            
            p_bbox = draw.textbbox((x, y + 32), f"{stock.price:.2f}", font=self.font_large)
            self._draw_change_badge(draw, stock.change_pct, stock.change_amt, x=p_bbox[2] + 12, y=y + 36, font=self.font_badge)

            info = f"昨收:{stock.prev_close:.2f} 最高:{stock.high_price:.2f} 最低:{stock.low_price:.2f}"
            draw.text((x, y + 74), info, font=self.font_small, fill=0)

            chart_w = (mid_x - pad * 2)
            chart_h = self.HEIGHT - y - 110
            chart_y = y + 100

            chart_img = chart_images.get(stock.code)
            if chart_img:
                eink_chart = ImageProcessor.process_chart_for_eink(chart_img, (chart_w, chart_h))
                canvas.paste(eink_chart, (x, chart_y))
            else:
                draw.rectangle([x, chart_y, x + chart_w, chart_y + chart_h], outline=0)
                draw.text((x + chart_w // 2 - 40, chart_y + chart_h // 2), "暂无图表", font=self.font_small, fill=0)

    def _render_grid_overview(
        self,
        canvas: Image.Image,
        draw: ImageDraw.Draw,
        stocks: List[StockQuote],
        config: Optional[Dict[str, Any]]
    ):
        """模式三：多股网格看板 (2x2 或 2x3 格子)"""
        grid_cols = 2
        grid_rows = 2
        cell_w = self.WIDTH // grid_cols
        cell_h = (self.HEIGHT - 36) // grid_rows

        draw.line([(cell_w, 36), (cell_w, self.HEIGHT)], fill=0, width=2)
        draw.line([(0, 36 + cell_h), (self.WIDTH, 36 + cell_h)], fill=0, width=2)

        for i in range(min(4, len(stocks))):
            s = stocks[i]
            col = i % grid_cols
            row = i // grid_cols
            cx = col * cell_w + 16
            cy = 36 + row * cell_h + 12

            # 股票名称与代码
            draw.text((cx, cy), f"{s.name} ({s.code})", font=self.font_title, fill=0)
            
            # 价格与徽标
            draw.text((cx, cy + 34), f"{s.price:.2f}", font=self.font_large, fill=0)
            p_bbox = draw.textbbox((cx, cy + 34), f"{s.price:.2f}", font=self.font_large)
            self._draw_change_badge(draw, s.change_pct, s.change_amt, x=p_bbox[2] + 16, y=cy + 40, font=self.font_badge)

            # 详细数据网格
            vol_str = self._format_volume(s.volume)
            turn_str = self._format_turnover(s.turnover)
            draw.text((cx, cy + 82), f"今开: {s.open_price:.2f}     昨收: {s.prev_close:.2f}", font=self.font_regular, fill=0)
            draw.text((cx, cy + 106), f"最高: {s.high_price:.2f}     最低: {s.low_price:.2f}", font=self.font_regular, fill=0)
            draw.text((cx, cy + 130), f"成交量: {vol_str}   成交额: {turn_str}", font=self.font_small, fill=0)

    def _draw_change_badge(self, draw: ImageDraw.Draw, pct: float, amt: float, x: int, y: int, font: ImageFont.ImageFont):
        """
        绘制涨跌徽章：
        上涨：黑底白字反色块（黑白墨水屏上最醒目），显示 ▲ +X.XX% +X.XX
        下跌：带黑边框的白底黑字块，显示 ▼ -X.XX% -X.XX
        平盘：普通虚线框
        """
        sign = "+" if pct > 0 else ""
        arrow = "▲" if pct > 0 else ("▼" if pct < 0 else "")
        text = f" {arrow} {sign}{pct:.2f}% ({sign}{amt:.2f}) "

        bbox = draw.textbbox((x, y), text, font=font)
        pad_x = 4
        pad_y = 3
        badge_rect = [bbox[0] - pad_x, bbox[1] - pad_y, bbox[2] + pad_x, bbox[3] + pad_y]

        if pct > 0:
            # 实体纯黑底，反色白字（代表上涨）
            draw.rectangle(badge_rect, fill=0)
            draw.text((x, y), text, font=font, fill=255)
        elif pct < 0:
            # 白底黑边框，黑字（代表下跌）
            draw.rectangle(badge_rect, outline=0, width=2, fill=255)
            draw.text((x, y), text, font=font, fill=0)
        else:
            draw.rectangle(badge_rect, outline=0, width=1, fill=255)
            draw.text((x, y), text, font=font, fill=0)

    def _draw_mini_badge(self, draw: ImageDraw.Draw, pct: float, text: str, right_align_x: int, y: int, font: ImageFont.ImageFont):
        """自选股侧边栏的小徽标（右对齐）"""
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = right_align_x - w - 8
        rect = [x, y, right_align_x, y + h + 6]

        if pct > 0:
            draw.rectangle(rect, fill=0)
            draw.text((x + 4, y + 2), text, font=font, fill=255)
        else:
            draw.rectangle(rect, outline=0, width=1, fill=255)
            draw.text((x + 4, y + 2), text, font=font, fill=0)

    def _render_empty_state(self, draw: ImageDraw.Draw):
        draw.text((250, 220), "暂无股票代码，请在控制台添加自选股", font=self.font_title, fill=0)

    @staticmethod
    def _format_volume(vol: float) -> str:
        if vol >= 10000:
            return f"{vol / 10000:.2f}万手"
        return f"{vol:.1f}手"

    @staticmethod
    def _format_turnover(turn: float) -> str:
        if turn >= 10000:
            return f"{turn / 10000:.2f}亿元"
        return f"{turn:.1f}万元"
