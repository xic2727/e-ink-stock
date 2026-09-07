from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from PIL import Image
from core.models import StockQuote, StockIndex

class BaseStockAPI(ABC):
    """
    股票行情与分时图 API 抽象基类。
    用户对接自身 API 时，只需继承该类并实现相应方法即可。
    """

    @abstractmethod
    def get_stock_quotes(self, codes: List[str]) -> List[StockQuote]:
        """
        批量或单次获取股票实时行情数据。
        :param codes: 股票代码列表，如 ["600519", "300750"]
        :return: 股票行情对象列表
        """
        pass

    @abstractmethod
    def get_market_indices(self) -> List[StockIndex]:
        """
        获取核心大盘指数（如上证指数、深证成指、创业板指）。
        :return: 指数对象列表
        """
        pass

    @abstractmethod
    def get_stock_chart_image(self, code: str, width: int = 500, height: int = 280) -> Optional[Image.Image]:
        """
        获取指定股票的分时走势图图片。
        用户的接口可以返回图片 URL、Base64 字符串或二进制图片，适配器负责将其转为 PIL.Image 对象返回。
        :param code: 股票代码
        :param width: 预期展示区域宽度
        :param height: 预期展示区域高度
        :return: PIL.Image 对象（RGB/RGBA/L 均可，后续会有图像二值化处理器统一优化）
        """
        pass
