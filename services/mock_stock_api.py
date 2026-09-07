import random
import time
import math
from datetime import datetime
from typing import List, Optional, Dict
from PIL import Image, ImageDraw, ImageFont
from core.models import StockQuote, StockIndex
from services.base_api import BaseStockAPI

class MockStockAPI(BaseStockAPI):
    """
    内置仿真模拟股票数据与分时折线图生成器。
    用于在未配置真实外部 API 时进行全流程效果验证与排版调试。
    """
    
    DEFAULT_STOCKS = {
        "600519": {"name": "贵州茅台", "base": 1685.00, "vol_base": 2.8},
        "300750": {"name": "宁德时代", "base": 218.60, "vol_base": 18.5},
        "000001": {"name": "平安银行", "base": 11.35, "vol_base": 85.0},
        "002594": {"name": "比亚迪", "base": 248.50, "vol_base": 12.2},
        "601318": {"name": "中国平安", "base": 46.80, "vol_base": 45.0},
        "000002": {"name": "万科Ａ", "base": 8.12, "vol_base": 90.0},
        "600036": {"name": "招商银行", "base": 33.50, "vol_base": 55.0},
        "601899": {"name": "紫金矿业", "base": 16.20, "vol_base": 78.0},
        "601138": {"name": "工业富联", "base": 22.80, "vol_base": 65.0},
        "300059": {"name": "东方财富", "base": 14.50, "vol_base": 120.0},
        "000858": {"name": "五粮液", "base": 138.00, "vol_base": 15.0},
        "600900": {"name": "长江电力", "base": 29.20, "vol_base": 30.0},
        "601088": {"name": "中国神华", "base": 41.50, "vol_base": 25.0},
        "600030": {"name": "中信证券", "base": 19.80, "vol_base": 80.0},
        "002475": {"name": "立讯精密", "base": 38.60, "vol_base": 42.0},
        "300760": {"name": "迈瑞医疗", "base": 265.00, "vol_base": 8.5}
    }

    def __init__(self):
        # 记录基准模拟数据状态
        self._cache = {}
        self._init_cache()

    def _init_cache(self):
        for code, info in self.DEFAULT_STOCKS.items():
            base = info["base"]
            pct = round(random.uniform(-3.5, 3.5), 2)
            price = round(base * (1 + pct / 100.0), 2)
            amt = round(price - base, 2)
            high = round(max(price, base) * (1 + random.uniform(0.002, 0.015)), 2)
            low = round(min(price, base) * (1 - random.uniform(0.002, 0.015)), 2)
            open_p = round(base * (1 + random.uniform(-0.01, 0.01)), 2)
            vol = round(info["vol_base"] * random.uniform(0.8, 1.3), 2)
            turnover = round(vol * price * 100 / 10000, 2) # 万元/亿元模拟
            
            self._cache[code] = StockQuote(
                code=code,
                name=info["name"],
                price=price,
                change_pct=pct,
                change_amt=amt,
                open_price=open_p,
                prev_close=base,
                high_price=high,
                low_price=low,
                volume=vol,
                turnover=turnover,
                update_time=datetime.now().strftime("%H:%M:%S")
            )

    def get_stock_quotes(self, codes: List[str]) -> List[StockQuote]:
        results = []
        now_str = datetime.now().strftime("%H:%M:%S")
        for code in codes:
            if code in self._cache:
                q = self._cache[code]
                # 微幅随机波动模拟实时跳动
                drift = round(random.uniform(-0.2, 0.2), 2)
                new_price = round(max(0.01, q.price + drift), 2)
                q.price = new_price
                q.change_amt = round(new_price - q.prev_close, 2)
                q.change_pct = round((q.change_amt / q.prev_close) * 100, 2)
                q.high_price = max(q.high_price, new_price)
                q.low_price = min(q.low_price, new_price)
                q.update_time = now_str
                results.append(q)
            else:
                # 针对用户自定义输入的新代码提供动态默认值
                results.append(StockQuote(
                    code=code,
                    name=f"股票{code}",
                    price=25.80,
                    change_pct=1.25,
                    change_amt=0.32,
                    open_price=25.50,
                    prev_close=25.48,
                    high_price=26.10,
                    low_price=25.30,
                    volume=15.0,
                    turnover=3870.0,
                    update_time=now_str
                ))
        return results

    def get_market_indices(self) -> List[StockIndex]:
        indices = [
            StockIndex("上证指数", "000001", 3132.45, 0.42, 13.15),
            StockIndex("深证成指", "399001", 10245.80, -0.28, -28.90),
            StockIndex("创业板指", "399006", 2048.12, 0.65, 13.24)
        ]
        return indices

    def get_stock_chart_image(self, code: str, width: int = 500, height: int = 280) -> Optional[Image.Image]:
        """
        动态绘制标准的 A 股分时走势图（白色背景，纯黑折线与昨收虚线，含下方成交量柱状图）。
        """
        img = Image.new('RGB', (width, height), (255, 255, 255))
        draw = ImageDraw.Draw(img)

        # 边框与刻度参考线
        margin_top = 20
        margin_bottom = 25
        margin_left = 45
        margin_right = 45
        plot_w = width - margin_left - margin_right
        plot_h = height - margin_top - margin_bottom

        # 主折线图区域 (70%) 与 成交量区域 (25%)
        chart_h = int(plot_h * 0.72)
        vol_h = int(plot_h * 0.22)
        vol_top = margin_top + chart_h + 10

        # 外框
        draw.rectangle([margin_left, margin_top, margin_left + plot_w, margin_top + chart_h], outline=(150, 150, 150), width=1)
        draw.rectangle([margin_left, vol_top, margin_left + plot_w, vol_top + vol_h], outline=(180, 180, 180), width=1)

        # 昨收基准中轴虚线
        mid_y = margin_top + chart_h // 2
        for x in range(margin_left, margin_left + plot_w, 6):
            draw.line([(x, mid_y), (min(x + 3, margin_left + plot_w), mid_y)], fill=(120, 120, 120), width=1)

        # 模拟生成 241 个分时数据点（A股 9:30-11:30, 13:00-15:00 共 240 分钟）
        random.seed(int(code) if code.isdigit() else 42)
        current = 0.0
        points = []
        vol_points = []
        num_points = 240
        for i in range(num_points):
            step = random.uniform(-0.15, 0.16)
            current += step
            points.append(current)
            vol_points.append(abs(random.gauss(10, 5)))

        max_val = max(max(points), abs(min(points)), 0.5)
        scale_y = (chart_h / 2 - 4) / max_val
        max_vol = max(vol_points) if vol_points else 1
        scale_vol = (vol_h - 2) / max_vol

        # 绘制分时折线
        prev_xy = None
        for i, val in enumerate(points):
            px = margin_left + int(i * plot_w / num_points)
            py = mid_y - int(val * scale_y)
            if prev_xy:
                draw.line([prev_xy, (px, py)], fill=(0, 0, 0), width=2)
            prev_xy = (px, py)

            # 绘制成交量竖线
            vy = vol_top + vol_h - int(vol_points[i] * scale_vol)
            draw.line([(px, vol_top + vol_h), (px, vy)], fill=(80, 80, 80), width=1)

        # 标注 9:30, 11:30/13:00, 15:00 时间刻度
        try:
            # 尝试载入默认字体
            font = ImageFont.load_default()
        except:
            font = None
        
        draw.text((margin_left, margin_top + chart_h + 1), "09:30", fill=(100, 100, 100), font=font)
        draw.text((margin_left + plot_w // 2 - 25, margin_top + chart_h + 1), "11:30/13:00", fill=(100, 100, 100), font=font)
        draw.text((margin_left + plot_w - 30, margin_top + chart_h + 1), "15:00", fill=(100, 100, 100), font=font)

        # 标注左右涨跌幅刻度
        draw.text((5, margin_top - 2), f"+{max_val:.1f}%", fill=(0, 0, 0), font=font)
        draw.text((5, mid_y - 5), " 0.0%", fill=(100, 100, 100), font=font)
        draw.text((5, margin_top + chart_h - 10), f"-{max_val:.1f}%", fill=(0, 0, 0), font=font)

        return img
