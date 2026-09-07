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
        chart_images: Optional[Dict[str, Image.Image]] = None,
        market_index_data: Optional[Dict[str, Any]] = None,
        market_chart_img: Optional[Image.Image] = None,
        layout_mode: LayoutMode = LayoutMode.FOCUS_AND_LIST,
        focus_index: int = 0,
        config: Optional[Dict[str, Any]] = None
    ) -> Image.Image:
        """
        根据指定布局模式渲染完整的 800x480 单色位图。
        """
        if chart_images is None:
            chart_images = {}

        # 创建 1-bit 单色纯白画布
        canvas = Image.new('1', (self.WIDTH, self.HEIGHT), 255)
        draw = ImageDraw.Draw(canvas)

        # 1. 绘制全局顶部状态栏 (高度 38px)
        self._render_header(draw, indices, state)

        # 2. 根据布局模式渲染内容区域
        if not stocks and not market_index_data:
            self._render_empty_state(draw)
            return canvas

        if layout_mode == LayoutMode.FOCUS_AND_LIST:
            self._render_focus_and_list(canvas, draw, stocks, chart_images, focus_index, market_index_data, market_chart_img, config)
        elif layout_mode == LayoutMode.DUAL_COMPARE:
            self._render_dual_compare(canvas, draw, stocks, chart_images, focus_index, market_index_data, market_chart_img, config)
        elif layout_mode == LayoutMode.GRID_OVERVIEW:
            self._render_grid_overview(canvas, draw, stocks, config)
        else:
            self._render_focus_and_list(canvas, draw, stocks, chart_images, focus_index, market_index_data, market_chart_img, config)

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
        market_index_data: Optional[Dict[str, Any]],
        market_chart_img: Optional[Image.Image],
        config: Optional[Dict[str, Any]]
    ):
        """
        模式一：大盘全景走势与情绪统计 (左侧 530px) + 自选股监控池 (右侧 270px)
        """
        split_x = 530
        draw.line([(split_x, 36), (split_x, self.HEIGHT)], fill=0, width=2)

        left_pad = 14
        top_y = 44

        # ---------------- 左侧大盘走势图核心区 ----------------
        if market_index_data:
            idx_name = market_index_data.get("name", "上证指数")
            idx_code = market_index_data.get("code", "sh000001")
            idx_price = market_index_data.get("current_price", 0.0)
            idx_pct = market_index_data.get("change_pct", 0.0)
            idx_amt = market_index_data.get("change_amt", 0.0)

            # 标题与代码
            draw.text((left_pad, top_y), idx_name, font=self.font_title, fill=0)
            name_bbox = draw.textbbox((left_pad, top_y), idx_name, font=self.font_title)
            draw.text((name_bbox[2] + 8, top_y + 6), f"({idx_code})", font=self.font_regular, fill=0)

            # 点位与涨跌徽标
            price_y = top_y + 30
            price_str = f"{idx_price:.2f}"
            draw.text((left_pad, price_y), price_str, font=self.font_large, fill=0)
            price_bbox = draw.textbbox((left_pad, price_y), price_str, font=self.font_large)
            self._draw_change_badge(draw, idx_pct, idx_amt, x=price_bbox[2] + 14, y=price_y + 6, font=self.font_badge, show_amt=True)

            # 指数关键指标
            info_y = price_y + 40
            open_p = market_index_data.get("open_price", 0.0)
            prev_c = market_index_data.get("yesterday_close", 0.0)
            high_p = market_index_data.get("high_price", 0.0)
            low_p = market_index_data.get("low_price", 0.0)
            vol = market_index_data.get("volume", 0.0)
            turn = market_index_data.get("turnover", 0.0)

            # 格式化手与亿元
            vol_str = f"{vol/100000000.0:.2f}亿手" if vol >= 100000000 else f"{vol/10000.0:.1f}万手"
            turn_str = f"{turn/10000.0:.1f}亿元" if turn >= 10000 else f"{turn:.0f}万元"

            line1 = f"今开: {open_p:.2f}  最高: {high_p:.2f}  最低: {low_p:.2f}  昨收: {prev_c:.2f}"
            draw.text((left_pad, info_y), line1, font=self.font_small, fill=0)

            # 涨跌平统计或成交额
            up_c = market_index_data.get("up_count", 0)
            flat_c = market_index_data.get("flat_count", 0)
            down_c = market_index_data.get("down_count", 0)
            if up_c > 0 or down_c > 0:
                line2 = f"成交: {vol_str} ({turn_str})  |  涨 {up_c}   平 {flat_c}   跌 {down_c}"
            else:
                line2 = f"成交量: {vol_str}     成交额: {turn_str}"
            draw.text((left_pad, info_y + 18), line2, font=self.font_small, fill=0)

            # 绘制大盘分时走势图
            chart_y = info_y + 38
            chart_w = split_x - left_pad * 2
            chart_h = self.HEIGHT - chart_y - 8

            if market_chart_img:
                # 缩放至精确区域并粘贴
                if market_chart_img.size != (chart_w, chart_h):
                    scaled_chart = market_chart_img.resize((chart_w, chart_h), Image.Resampling.LANCZOS).convert('1')
                else:
                    scaled_chart = market_chart_img
                canvas.paste(scaled_chart, (left_pad, chart_y))
            else:
                draw.rectangle([left_pad, chart_y, left_pad + chart_w, chart_y + chart_h], outline=0)
                draw.text((left_pad + chart_w // 2 - 50, chart_y + chart_h // 2 - 10), "大盘走势图绘制中...", font=self.font_regular, fill=0)

        elif stocks:
            # 兼容：无大盘数据时显示个股
            focus_stock = stocks[focus_idx] if 0 <= focus_idx < len(stocks) else stocks[0]
            draw.text((left_pad, top_y), focus_stock.name, font=self.font_title, fill=0)
            draw.text((left_pad, top_y + 32), f"{focus_stock.price:.2f}", font=self.font_large, fill=0)

        # ---------------- 右侧自选股侧边栏渲染 ----------------
        right_x = split_x + 12
        right_w = self.WIDTH - right_x - 12
        sidebar_y = 44

        draw.text((right_x, sidebar_y), f"自选股池 ({len(stocks)})", font=self.font_medium, fill=0)
        draw.line([(right_x, sidebar_y + 24), (self.WIDTH - 12, sidebar_y + 24)], fill=0, width=1)

        card_top = sidebar_y + 28
        max_display = min(5, len(stocks))
        card_h = (self.HEIGHT - card_top - 6) // max(1, max_display)

        for i in range(max_display):
            s = stocks[i]
            cy = card_top + i * card_h

            if i > 0:
                draw.line([(right_x, cy - 2), (self.WIDTH - 12, cy - 2)], fill=0, width=1)

            # 股票名与代码
            draw.text((right_x + 4, cy + 4), s.name[:6], font=self.font_medium, fill=0)
            draw.text((right_x + 4, cy + 28), s.code, font=self.font_small, fill=0)

            # 现价
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
        focus_idx: int,
        market_index_data: Optional[Dict[str, Any]],
        market_chart_img: Optional[Image.Image],
        config: Optional[Dict[str, Any]]
    ):
        """模式二：大盘分时走势 (左 400px) + 核心焦点股票深度指标 (右 400px)"""
        mid_x = self.WIDTH // 2
        draw.line([(mid_x, 36), (mid_x, self.HEIGHT)], fill=0, width=2)

        pad = 12
        # --- 左侧：大盘走势图 ---
        lx = pad
        ly = 44
        if market_index_data:
            draw.text((lx, ly), f"上证指数 (sh000001)", font=self.font_title, fill=0)
            idx_p = market_index_data.get("current_price", 0.0)
            idx_pct = market_index_data.get("change_pct", 0.0)
            idx_amt = market_index_data.get("change_amt", 0.0)
            draw.text((lx, ly + 32), f"{idx_p:.2f}", font=self.font_large, fill=0)
            p_bbox = draw.textbbox((lx, ly + 32), f"{idx_p:.2f}", font=self.font_large)
            self._draw_change_badge(draw, idx_pct, idx_amt, x=p_bbox[2] + 10, y=ly + 36, font=self.font_badge, show_amt=False)

            chart_w = mid_x - pad * 2
            chart_h = self.HEIGHT - ly - 80
            chart_y = ly + 72

            if market_chart_img:
                scaled = market_chart_img.resize((chart_w, chart_h), Image.Resampling.LANCZOS).convert('1')
                canvas.paste(scaled, (lx, chart_y))

        # --- 右侧：核心个股超详尽看板 ---
        rx = mid_x + pad
        ry = 44
        if stocks:
            s = stocks[focus_idx] if 0 <= focus_idx < len(stocks) else stocks[0]
            draw.text((rx, ry), f"{s.name} ({s.code})", font=self.font_title, fill=0)
            draw.text((rx, ry + 36), f"{s.price:.2f}", font=self.font_large, fill=0)
            p_bbox = draw.textbbox((rx, ry + 36), f"{s.price:.2f}", font=self.font_large)
            self._draw_change_badge(draw, s.change_pct, s.change_amt, x=p_bbox[2] + 12, y=ry + 42, font=self.font_badge, show_amt=True)

            vol_str = self._format_volume(s.volume)
            turn_str = self._format_turnover(s.turnover)

            draw.text((rx, ry + 95), f"今开: {s.open_price:.2f}     昨收: {s.prev_close:.2f}", font=self.font_regular, fill=0)
            draw.text((rx, ry + 125), f"最高: {s.high_price:.2f}     最低: {s.low_price:.2f}", font=self.font_regular, fill=0)
            draw.text((rx, ry + 155), f"成交量: {vol_str}   成交额: {turn_str}", font=self.font_regular, fill=0)
            draw.text((rx, ry + 185), f"报价时间: {s.update_time}", font=self.font_small, fill=0)

    def _render_grid_overview(
        self,
        canvas: Image.Image,
        draw: ImageDraw.Draw,
        stocks: List[StockQuote],
        config: Optional[Dict[str, Any]]
    ):
        """
        模式三：自适应多股网格看板 (支持 1 ~ 16 支股票动态自适应排版)
        - 1 支: 单股全景卡片
        - 2 支: 1行 x 2列 (每格 400x444)
        - 3~4 支: 2行 x 2列 (每格 400x222)
        - 5~6 支: 3行 x 2列 (每格 400x148)
        - 7~8 支: 4行 x 2列 (每格 400x111)
        - 9 支: 3行 x 3列 (每格 266x148)
        - 10~12 支: 4行 x 3列 (每格 266x111)
        - 13~16 支: 4行 x 4列 (每格 200x111)
        """
        count = min(16, len(stocks))
        if count == 0:
            self._render_empty_state(draw)
            return

        header_h = 36
        avail_w = self.WIDTH
        avail_h = self.HEIGHT - header_h

        # 动态自适应确定列数与行数
        if count <= 1:
            cols, rows = 1, 1
        elif count == 2:
            cols, rows = 2, 1
        elif count <= 4:
            cols, rows = 2, 2
        elif count <= 6:
            cols, rows = 2, 3
        elif count <= 8:
            cols, rows = 2, 4
        elif count == 9:
            cols, rows = 3, 3
        elif count <= 12:
            cols, rows = 3, 4
        else:  # 13 ~ 16
            cols, rows = 4, 4

        cell_w = avail_w // cols
        cell_h = avail_h // rows

        # 绘制网格分割线
        for c in range(1, cols):
            x = c * cell_w
            draw.line([(x, header_h), (x, self.HEIGHT)], fill=0, width=1)

        for r in range(1, rows):
            y = header_h + r * cell_h
            draw.line([(0, y), (self.WIDTH, y)], fill=0, width=1)

        # 预加载不同梯度的动态字体
        f_11 = FontManager.load(11, bold=False)
        f_12 = FontManager.load(12, bold=False)
        f_12_b = FontManager.load(12, bold=True)
        f_13_b = FontManager.load(13, bold=True)
        f_14_b = FontManager.load(14, bold=True)
        f_15_b = FontManager.load(15, bold=True)
        f_16_b = FontManager.load(16, bold=True)
        f_18_b = FontManager.load(18, bold=True)
        f_20_b = FontManager.load(20, bold=True)
        f_22_b = FontManager.load(22, bold=True)
        f_26_b = FontManager.load(26, bold=True)
        f_30_b = FontManager.load(30, bold=True)

        for i in range(count):
            s = stocks[i]
            col = i % cols
            row = i // cols
            cx = col * cell_w
            cy = header_h + row * cell_h

            if cols == 4:  # 13~16 支股票 (每格 200 x 111)
                pad_x = 8
                # 股票名与代码
                draw.text((cx + pad_x, cy + 5), s.name[:5], font=f_15_b, fill=0)
                draw.text((cx + pad_x + 68, cy + 8), s.code, font=f_11, fill=0)
                # 现价
                draw.text((cx + pad_x, cy + 27), f"{s.price:.2f}", font=f_18_b, fill=0)
                # 紧凑涨跌徽章
                self._draw_change_badge(draw, s.change_pct, s.change_amt, cx + pad_x, cy + 53, font=f_12_b, show_amt=False)
                # 最低/最高
                draw.text((cx + pad_x, cy + 78), f"高:{s.high_price:.1f} 低:{s.low_price:.1f}", font=f_11, fill=0)
                # 今开/昨收
                draw.text((cx + pad_x, cy + 93), f"开:{s.open_price:.1f} 昨:{s.prev_close:.1f}", font=f_11, fill=0)

            elif cols == 3 and rows == 4:  # 10~12 支股票 (每格 266 x 111)
                pad_x = 10
                draw.text((cx + pad_x, cy + 6), s.name[:6], font=f_16_b, fill=0)
                draw.text((cx + pad_x + 85, cy + 9), s.code, font=f_12, fill=0)
                # 现价与徽标同行
                draw.text((cx + pad_x, cy + 30), f"{s.price:.2f}", font=f_20_b, fill=0)
                p_bbox = draw.textbbox((cx + pad_x, cy + 30), f"{s.price:.2f}", font=f_20_b)
                self._draw_change_badge(draw, s.change_pct, s.change_amt, p_bbox[2] + 8, cy + 33, font=f_12_b, show_amt=False)
                # 量价指标
                draw.text((cx + pad_x, cy + 62), f"今开: {s.open_price:.2f}   昨收: {s.prev_close:.2f}", font=f_11, fill=0)
                draw.text((cx + pad_x, cy + 82), f"最高: {s.high_price:.2f}   最低: {s.low_price:.2f}", font=f_11, fill=0)

            elif cols == 3 and rows == 3:  # 9 支股票 (每格 266 x 148, 经典九宫格)
                pad_x = 12
                draw.text((cx + pad_x, cy + 8), s.name[:6], font=f_18_b, fill=0)
                draw.text((cx + pad_x + 95, cy + 12), s.code, font=f_12, fill=0)
                draw.text((cx + pad_x, cy + 36), f"{s.price:.2f}", font=f_26_b, fill=0)
                self._draw_change_badge(draw, s.change_pct, s.change_amt, cx + pad_x, cy + 74, font=f_13_b, show_amt=True)
                draw.text((cx + pad_x, cy + 104), f"今开:{s.open_price:.2f}  最高:{s.high_price:.2f}", font=f_12, fill=0)
                draw.text((cx + pad_x, cy + 124), f"昨收:{s.prev_close:.2f}  最低:{s.low_price:.2f}", font=f_12, fill=0)

            elif cols == 2 and rows == 4:  # 7~8 支股票 (每格 400 x 111)
                pad_x = 12
                # 左侧：股票名称与代码
                draw.text((cx + pad_x, cy + 8), s.name[:6], font=f_18_b, fill=0)
                draw.text((cx + pad_x, cy + 34), s.code, font=f_12, fill=0)
                self._draw_change_badge(draw, s.change_pct, s.change_amt, cx + pad_x, cy + 60, font=f_13_b, show_amt=False)
                # 中间：大号现价
                draw.text((cx + 145, cy + 22), f"{s.price:.2f}", font=f_30_b, fill=0)
                # 右侧：量价
                draw.text((cx + 265, cy + 18), f"今开: {s.open_price:.2f}", font=f_12, fill=0)
                draw.text((cx + 265, cy + 38), f"昨收: {s.prev_close:.2f}", font=f_12, fill=0)
                draw.text((cx + 265, cy + 58), f"最高: {s.high_price:.2f}", font=f_12, fill=0)
                draw.text((cx + 265, cy + 78), f"最低: {s.low_price:.2f}", font=f_12, fill=0)

            elif cols == 2 and rows == 3:  # 5~6 支股票 (每格 400 x 148)
                pad_x = 14
                draw.text((cx + pad_x, cy + 10), f"{s.name} ({s.code})", font=f_20_b, fill=0)
                draw.text((cx + pad_x, cy + 38), f"{s.price:.2f}", font=f_30_b, fill=0)
                p_bbox = draw.textbbox((cx + pad_x, cy + 38), f"{s.price:.2f}", font=f_30_b)
                self._draw_change_badge(draw, s.change_pct, s.change_amt, p_bbox[2] + 14, cy + 45, font=f_14_b, show_amt=True)
                vol_str = self._format_volume(s.volume)
                turn_str = self._format_turnover(s.turnover)
                draw.text((cx + pad_x, cy + 86), f"今开: {s.open_price:.2f}   最高: {s.high_price:.2f}   最低: {s.low_price:.2f}", font=f_12, fill=0)
                draw.text((cx + pad_x, cy + 110), f"昨收: {s.prev_close:.2f}   成交量: {vol_str}   成交额: {turn_str}", font=f_12, fill=0)

            else:  # 1~4 支股票 (原有大尺寸详细看板)
                pad_x = 16
                draw.text((cx + pad_x, cy + 12), f"{s.name} ({s.code})", font=self.font_title, fill=0)
                draw.text((cx + pad_x, cy + 44), f"{s.price:.2f}", font=self.font_large, fill=0)
                p_bbox = draw.textbbox((cx + pad_x, cy + 44), f"{s.price:.2f}", font=self.font_large)
                self._draw_change_badge(draw, s.change_pct, s.change_amt, x=p_bbox[2] + 16, y=cy + 50, font=self.font_badge, show_amt=True)
                vol_str = self._format_volume(s.volume)
                turn_str = self._format_turnover(s.turnover)
                draw.text((cx + pad_x, cy + 96), f"今开: {s.open_price:.2f}     昨收: {s.prev_close:.2f}", font=self.font_regular, fill=0)
                draw.text((cx + pad_x, cy + 122), f"最高: {s.high_price:.2f}     最低: {s.low_price:.2f}", font=self.font_regular, fill=0)
                draw.text((cx + pad_x, cy + 148), f"成交量: {vol_str}   成交额: {turn_str}", font=self.font_small, fill=0)

    def _draw_change_badge(
        self,
        draw: ImageDraw.Draw,
        pct: float,
        amt: float,
        x: int,
        y: int,
        font: ImageFont.ImageFont,
        show_amt: bool = True
    ):
        """
        绘制涨跌徽章：
        上涨：黑底白字反色块（黑白墨水屏上最醒目），显示 ▲ +X.XX%
        下跌：带黑边框的白底黑字块，显示 ▼ -X.XX%
        平盘：普通边框
        """
        sign = "+" if pct > 0 else ""
        arrow = "▲" if pct > 0 else ("▼" if pct < 0 else "")
        if show_amt:
            text = f" {arrow} {sign}{pct:.2f}% ({sign}{amt:.2f}) "
        else:
            text = f" {arrow} {sign}{pct:.2f}% "

        bbox = draw.textbbox((x, y), text, font=font)
        pad_x = 3
        pad_y = 2
        badge_rect = [bbox[0] - pad_x, bbox[1] - pad_y, bbox[2] + pad_x, bbox[3] + pad_y]

        if pct > 0:
            # 实体纯黑底，反色白字（代表上涨）
            draw.rectangle(badge_rect, fill=0)
            draw.text((x, y), text, font=font, fill=255)
        elif pct < 0:
            # 白底黑边框，黑字（代表下跌）
            draw.rectangle(badge_rect, outline=0, width=1, fill=255)
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
