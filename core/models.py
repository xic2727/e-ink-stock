from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List
import time

class LayoutMode(str, Enum):
    FOCUS_AND_LIST = "focus_and_list"      # 模式一: 主力聚焦 + 侧边栏自选股列表
    DUAL_COMPARE = "dual_compare"          # 模式二: 双股双折线图并列
    GRID_OVERVIEW = "grid_overview"        # 模式三: 4~6支股票网格看板

class MarketStatus(str, Enum):
    PRE_MARKET = "盘前准备"
    TRADING = "交易中"
    NOON_BREAK = "午间休市"
    POST_MARKET = "已收盘"
    WEEKEND_HOLIDAY = "休市中"

@dataclass
class StockQuote:
    code: str
    name: str
    price: float
    change_pct: float
    change_amt: float
    open_price: float = 0.0
    prev_close: float = 0.0
    high_price: float = 0.0
    low_price: float = 0.0
    volume: float = 0.0          # 成交量（手）
    turnover: float = 0.0        # 成交额（元）
    update_time: str = ""        # 格式 HH:MM:SS
    is_index: bool = False       # 是否是大盘指数

@dataclass
class StockIndex:
    name: str                    # 如 "上证指数", "深证成指", "创业板指"
    code: str
    points: float
    change_pct: float
    change_amt: float

@dataclass
class SystemState:
    last_refresh_time: float = field(default_factory=time.time)
    update_time_str: str = ""
    partial_refresh_count: int = 0
    total_refresh_count: int = 0
    current_focus_index: int = 0
    market_status: MarketStatus = MarketStatus.TRADING
    is_sleeping: bool = False
    last_error: Optional[str] = None
