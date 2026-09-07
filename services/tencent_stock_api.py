import json
import logging
import urllib.request
import urllib.error
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from PIL import Image, ImageDraw, ImageFont

from core.models import StockQuote, StockIndex
from core.font_manager import FontManager
from services.base_api import BaseStockAPI

logger = logging.getLogger(__name__)

class TencentStockAPI(BaseStockAPI):
    """
    腾讯证券官方实时行情与大盘分时走势图服务。
    1. 股票/基金智能搜索: proxy.finance.qq.com
    2. 个股极速实时行情: sqt.gtimg.cn
    3. 大盘分时分钟数据与走势图本地绘制: web.ifzq.gtimg.cn
    """

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Referer': 'https://gu.qq.com/',
        'Origin': 'https://gu.qq.com'
    }

    @staticmethod
    def format_market_code(code: str) -> str:
        """根据 6 位数字代码自动补全市场前缀 (sh / sz / bj)"""
        code = code.strip().lower()
        if code.startswith(('sh', 'sz', 'bj')):
            return code
        if code.startswith(('60', '68', '90', '11')):
            return f"sh{code}"
        elif code.startswith(('00', '30', '20', '12')):
            return f"sz{code}"
        elif code.startswith(('43', '83', '87', '92')):
            return f"bj{code}"
        return f"sz{code}"

    def search_stock(self, query: str) -> List[Dict[str, str]]:
        """
        调用腾讯 Smartbox 搜索接口查询股票代码或股票简称
        """
        url = f"https://proxy.finance.qq.com/cgi/cgi-bin/smartbox/search?stockFlag=1&fundFlag=1&app=official_website&query={urllib.parse.quote(query)}"
        results = []
        try:
            req = urllib.request.Request(url, headers=self.HEADERS)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                stocks = data.get('stock', [])
                for s in stocks:
                    code_full = s.get('code', '') # 如 sz000938
                    market = code_full[:2].upper() if len(code_full) >= 2 else "SZ"
                    clean_code = code_full[2:] if len(code_full) >= 2 else code_full
                    results.append({
                        "code": clean_code,
                        "market_code": code_full,
                        "name": s.get('name', ''),
                        "type": s.get('type', ''),
                        "market": market
                    })
        except Exception as e:
            logger.error(f"Search stock error: {e}")
        return results

    def get_stock_quotes(self, codes: List[str]) -> List[StockQuote]:
        """
        批量拉取多支股票的最新实时行情 (单次 GET 请求，极其高效)
        """
        if not codes:
            return []

        formatted_codes = [self.format_market_code(c) for c in codes]
        q_param = ",".join(formatted_codes)
        url = f"https://sqt.gtimg.cn/utf8/?q={q_param}&fmt=json"

        quotes = []
        try:
            req = urllib.request.Request(url, headers=self.HEADERS)
            with urllib.request.urlopen(req, timeout=8) as resp:
                content = resp.read().decode('utf-8')
                data = json.loads(content)

            for code_key in formatted_codes:
                if code_key in data:
                    qt = data[code_key]
                    if len(qt) > 35:
                        name = qt[1]
                        code = qt[2]
                        price = self._safe_float(qt[3])
                        prev_close = self._safe_float(qt[4])
                        open_p = self._safe_float(qt[5])
                        vol = self._safe_float(qt[6]) # 手
                        time_str = qt[30] if len(qt) > 30 else ""
                        change_amt = self._safe_float(qt[31]) if len(qt) > 31 else 0.0
                        change_pct = self._safe_float(qt[32]) if len(qt) > 32 else 0.0
                        high_p = self._safe_float(qt[33]) if len(qt) > 33 else price
                        low_p = self._safe_float(qt[34]) if len(qt) > 34 else price
                        turnover = self._safe_float(qt[37]) if len(qt) > 37 else 0.0 # 万元

                        # 格式化时间
                        if len(time_str) >= 14:
                            fmt_time = f"{time_str[8:10]}:{time_str[10:12]}:{time_str[12:14]}"
                        else:
                            fmt_time = datetime.now().strftime("%H:%M:%S")

                        quotes.append(StockQuote(
                            code=code,
                            name=name,
                            price=price,
                            change_pct=change_pct,
                            change_amt=change_amt,
                            open_price=open_p,
                            prev_close=prev_close,
                            high_price=high_p,
                            low_price=low_p,
                            volume=vol,
                            turnover=turnover,
                            update_time=fmt_time
                        ))
        except Exception as e:
            logger.error(f"Error fetching quotes from Tencent: {e}")

        return quotes

    def fetch_index_data(self, index_code: str = "sh000001") -> Optional[Dict[str, Any]]:
        """
        获取大盘指数（默认上证指数 sh000001）的实时点位与分钟走势数据
        """
        url = f"https://web.ifzq.gtimg.cn/appstock/app/minute/query?code={index_code}"
        try:
            req = urllib.request.Request(url, headers=self.HEADERS)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))

            if data.get('code') != 0:
                logger.error(f"Tencent Index API error: {data.get('msg')}")
                return None

            stock_data = data['data'][index_code]
            qt = stock_data['qt'][index_code]

            # 提取分钟数据点
            minute_prices = []
            if 'data' in stock_data and 'data' in stock_data['data']:
                for item in stock_data['data']['data']:
                    parts = item.split()
                    if len(parts) >= 2:
                        minute_prices.append((int(parts[0]), float(parts[1])))

            # 提取大盘行情字段
            current_price = self._safe_float(qt[3])
            yesterday_close = self._safe_float(qt[4])
            open_price = self._safe_float(qt[5])
            volume = self._safe_float(qt[6])  # 手
            turnover = self._safe_float(qt[37]) if len(qt) > 37 else 0.0  # 万元
            change_amt = self._safe_float(qt[31]) if len(qt) > 31 else 0.0
            change_pct = self._safe_float(qt[32]) if len(qt) > 32 else 0.0
            high_price = self._safe_float(qt[33]) if len(qt) > 33 else current_price
            low_price = self._safe_float(qt[34]) if len(qt) > 34 else current_price

            # 涨跌平家数 (若接口提供)
            zhishu = stock_data.get('zhishu') or data.get('zhishu') or []
            up_count = self._safe_int(zhishu[1]) if len(zhishu) > 1 else 0
            flat_count = self._safe_int(zhishu[2]) if len(zhishu) > 2 else 0
            down_count = self._safe_int(zhishu[3]) if len(zhishu) > 3 else 0

            return {
                'code': index_code,
                'name': qt[1] if len(qt) > 1 else "上证指数",
                'current_price': current_price,
                'open_price': open_price,
                'yesterday_close': yesterday_close,
                'change_pct': change_pct,
                'change_amt': change_amt,
                'high_price': high_price,
                'low_price': low_price,
                'volume': volume,
                'turnover': turnover,
                'up_count': up_count,
                'flat_count': flat_count,
                'down_count': down_count,
                'minute_prices': minute_prices,
                'update_time': datetime.now().strftime('%H:%M:%S')
            }
        except Exception as e:
            logger.error(f"Error fetching index data: {e}")
            return None

    def get_market_indices(self) -> List[StockIndex]:
        """拉取核心指数 (上证指数, 深证成指, 创业板指)"""
        url = "https://sqt.gtimg.cn/utf8/?q=sh000001,sz399001,sz399006&fmt=json"
        indices = []
        try:
            req = urllib.request.Request(url, headers=self.HEADERS)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            for code, name in [("sh000001", "上证指数"), ("sz399001", "深证成指"), ("sz399006", "创业板指")]:
                if code in data:
                    qt = data[code]
                    pts = self._safe_float(qt[3])
                    pct = self._safe_float(qt[32]) if len(qt) > 32 else 0.0
                    amt = self._safe_float(qt[31]) if len(qt) > 31 else 0.0
                    indices.append(StockIndex(name=name, code=code[2:], points=pts, change_pct=pct, change_amt=amt))
        except Exception as e:
            logger.error(f"Failed to fetch market indices: {e}")
        return indices

    def generate_index_chart(self, index_data: Dict[str, Any], width: int = 500, height: int = 240) -> Optional[Image.Image]:
        """
        参考用户提供的代码，本地绘制高清晰度大盘分时走势图（含昨收虚线、刻度、时间标尺与最新价光标）。
        1-bit 单色优化，专为 800x480 墨水屏设计。
        """
        if not index_data:
            return None

        prices = index_data.get('minute_prices', [])
        yesterday_close = index_data.get('yesterday_close', 0.0)

        if len(prices) < 2 or yesterday_close <= 0:
            return None

        img = Image.new('1', (width, height), 255)  # 纯白底
        draw = ImageDraw.Draw(img)

        # 边框与安全边距
        pad_top = 18
        pad_bottom = 22
        pad_left = 50
        pad_right = 50
        plot_w = width - pad_left - pad_right
        plot_h = height - pad_top - pad_bottom

        # 绘制外边框
        draw.rectangle([pad_left, pad_top, pad_left + plot_w, pad_top + plot_h], outline=0, width=1)

        # A股交易时段映射: 9:30-11:30 (120分) + 13:00-15:00 (120分) = 240分钟
        def time_to_x(t):
            hour = t // 100
            minute = t % 100
            if hour < 12:  # 上午 9:30-11:30
                trading_minute = (hour - 9) * 60 + (minute - 30)
            else:          # 下午 13:00-15:00
                trading_minute = 120 + (hour - 13) * 60 + minute
            return pad_left + int(trading_minute / 240.0 * (plot_w - 1))

        # 价格范围对称计算，使昨收虚线严格居中
        all_prices = [p for _, p in prices]
        max_diff = max(abs(max(all_prices) - yesterday_close), abs(yesterday_close - min(all_prices)), yesterday_close * 0.003)
        pmax = yesterday_close + max_diff * 1.1
        pmin = yesterday_close - max_diff * 1.1

        def price_to_y(p):
            return pad_top + int((pmax - p) / (pmax - pmin) * (plot_h - 1))

        # 1. 昨收基准水平虚线 (严格居中)
        y_close = price_to_y(yesterday_close)
        for x in range(pad_left, pad_left + plot_w, 4):
            draw.line([(x, y_close), (min(x + 2, pad_left + plot_w), y_close)], fill=0, width=1)

        # 2. 中午 11:30/13:00 分界虚线
        mid_x = pad_left + plot_w // 2
        for y in range(pad_top, pad_top + plot_h, 4):
            draw.line([(mid_x, y), (mid_x, min(y + 2, pad_top + plot_h))], fill=0, width=1)

        # 3. 绘制分时走势折线
        points = [(time_to_x(t), price_to_y(p)) for t, p in prices]
        for i in range(1, len(points)):
            draw.line([points[i - 1], points[i]], fill=0, width=2)

        # 4. 在最新分时点绘制高亮方块标尺
        last_x, last_y = points[-1]
        draw.rectangle([last_x - 2, last_y - 2, last_x + 2, last_y + 2], fill=0)

        # 5. 标注刻度字体
        f_axis = FontManager.load(11, bold=False)

        # 时间刻度 (09:30, 11:30/13:00, 15:00)
        draw.text((pad_left, pad_top + plot_h + 3), "09:30", font=f_axis, fill=0)
        draw.text((mid_x - 28, pad_top + plot_h + 3), "11:30/13:00", font=f_axis, fill=0)
        draw.text((pad_left + plot_w - 30, pad_top + plot_h + 3), "15:00", font=f_axis, fill=0)

        # 左右价格与涨跌幅刻度
        max_pct = (pmax - yesterday_close) / yesterday_close * 100.0
        draw.text((2, pad_top - 2), f"+{max_pct:.2f}%", font=f_axis, fill=0)
        draw.text((2, y_close - 6), f" {yesterday_close:.0f}", font=f_axis, fill=0)
        draw.text((2, pad_top + plot_h - 10), f"-{max_pct:.2f}%", font=f_axis, fill=0)

        draw.text((pad_left + plot_w + 4, pad_top - 2), f"{pmax:.1f}", font=f_axis, fill=0)
        draw.text((pad_left + plot_w + 4, y_close - 6), " 0.00%", font=f_axis, fill=0)
        draw.text((pad_left + plot_w + 4, pad_top + plot_h - 10), f"{pmin:.1f}", font=f_axis, fill=0)

        return img

    def get_stock_chart_image(self, code: str, width: int = 500, height: int = 280) -> Optional[Image.Image]:
        """
        兼容基类接口，直接返回大盘走势图
        """
        index_data = self.fetch_index_data("sh000001")
        if index_data:
            return self.generate_index_chart(index_data, width, height)
        return None

    @staticmethod
    def _safe_float(val: Any, default: float = 0.0) -> float:
        if val is None or val == '':
            return default
        try:
            return float(val)
        except:
            return default

    @staticmethod
    def _safe_int(val: Any, default: int = 0) -> int:
        if val is None or val == '':
            return default
        try:
            return int(float(val))
        except:
            return default
