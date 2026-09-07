import io
import base64
import logging
from typing import List, Optional, Dict, Any
import requests
from PIL import Image
from core.models import StockQuote, StockIndex
from services.base_api import BaseStockAPI
from services.mock_stock_api import MockStockAPI

logger = logging.getLogger(__name__)

class CustomStockAPI(BaseStockAPI):
    """
    用户自定义 API 适配器。
    用于对接用户提供的股票实时数据与折线图图片 API。
    若用户尚未配置或外部接口请求异常，将优雅回退至仿真数据保证系统不崩溃。
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config.get("api", {})
        self.quote_url = self.config.get("custom_quote_url", "").strip()
        self.chart_url = self.config.get("custom_chart_url", "").strip()
        self.token = self.config.get("custom_token", "").strip()
        self.timeout = self.config.get("request_timeout_sec", 5)
        self.mock_fallback = MockStockAPI()

    def get_stock_quotes(self, codes: List[str]) -> List[StockQuote]:
        """
        根据用户配置的 API 地址拉取实时股票数据。
        如果接口未配置，直接使用 Mock 回退。
        """
        if not self.quote_url:
            return self.mock_fallback.get_stock_quotes(codes)

        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            # 示例：通过 GET 请求拉取，将 codes 用逗号拼接传入
            # 用户可在此处调整请求参数名（如 params={"codes": ",".join(codes)}）
            resp = requests.get(
                self.quote_url,
                params={"codes": ",".join(codes)},
                headers=headers,
                timeout=self.timeout
            )
            if resp.status_code == 200:
                data = resp.json()
                # 预留用户 JSON 数据解析逻辑：
                # 假设返回格式为 {"data": [{"code": "...", "name": "...", "price": ...}, ...]}
                quotes = []
                items = data.get("data", data) if isinstance(data, dict) else data
                if isinstance(items, list):
                    for item in items:
                        quotes.append(StockQuote(
                            code=str(item.get("code", "")),
                            name=str(item.get("name", "")),
                            price=float(item.get("price", 0.0)),
                            change_pct=float(item.get("change_pct", item.get("pct_chg", 0.0))),
                            change_amt=float(item.get("change_amt", item.get("change", 0.0))),
                            open_price=float(item.get("open", 0.0)),
                            prev_close=float(item.get("prev_close", item.get("pre_close", 0.0))),
                            high_price=float(item.get("high", 0.0)),
                            low_price=float(item.get("low", 0.0)),
                            volume=float(item.get("volume", item.get("vol", 0.0))),
                            turnover=float(item.get("turnover", item.get("amount", 0.0))),
                            update_time=str(item.get("time", ""))
                        ))
                    if quotes:
                        return quotes
            logger.warning(f"Custom quote API returned status {resp.status_code}, falling back to mock")
        except Exception as e:
            logger.error(f"Error fetching quotes from custom API: {e}")

        # 失败回退
        return self.mock_fallback.get_stock_quotes(codes)

    def get_market_indices(self) -> List[StockIndex]:
        """获取三大核心指数"""
        # 可与自选股一起拉取或调用专属指数接口，此处默认返回大盘基准
        return self.mock_fallback.get_market_indices()

    def get_stock_chart_image(self, code: str, width: int = 500, height: int = 280) -> Optional[Image.Image]:
        """
        拉取股票分时折线图图片。
        支持二进制流、Base64 字符串或 URL 下载。
        """
        if not self.chart_url:
            return self.mock_fallback.get_stock_chart_image(code, width, height)

        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            target_url = self.chart_url.replace("{code}", code)
            resp = requests.get(target_url, params={"code": code}, headers=headers, timeout=self.timeout)
            if resp.status_code == 200:
                content_type = resp.headers.get("Content-Type", "")
                if "image" in content_type:
                    # 返回的是直接图片二进制流
                    img = Image.open(io.BytesIO(resp.content))
                    return img
                elif "json" in content_type:
                    # 返回的是 JSON 包含 Base64 或图片链接
                    jdata = resp.json()
                    b64_str = jdata.get("image_base64") or jdata.get("base64")
                    if b64_str:
                        if "," in b64_str:
                            b64_str = b64_str.split(",", 1)[1]
                        img_bytes = base64.b64decode(b64_str)
                        return Image.open(io.BytesIO(img_bytes))
                    img_url = jdata.get("image_url") or jdata.get("url")
                    if img_url:
                        img_resp = requests.get(img_url, timeout=self.timeout)
                        return Image.open(io.BytesIO(img_resp.content))
        except Exception as e:
            logger.error(f"Error fetching chart from custom API for {code}: {e}")

        # 异常或未就绪时回退
        return self.mock_fallback.get_stock_chart_image(code, width, height)
