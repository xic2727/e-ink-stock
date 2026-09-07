import os
import json
import time
import logging
from datetime import datetime, time as dtime
from typing import Dict, Any, Optional, Tuple
from PIL import Image

from core.models import MarketStatus, SystemState, LayoutMode
from core.layout_renderer import LayoutRenderer
from core.epd_controller import EPDController
from services.mock_stock_api import MockStockAPI
from services.custom_stock_api import CustomStockAPI
from services.tencent_stock_api import TencentStockAPI

logger = logging.getLogger(__name__)

class MarketScheduler:
    """
    A 股市场时间感知与行情刷新调度器。
    管理自选股轮播、时段判断、数据拉取与刷屏。
    """

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self.load_config()
        
        self.renderer = LayoutRenderer()
        self.epd = EPDController(self.config)
        self.state = SystemState()
        self._init_api()
        
        self.cycle_count = 0
        self.last_rendered_image: Optional[Image.Image] = None

    def load_config(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_config(self, new_config: Dict[str, Any]):
        self.config = new_config
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(new_config, f, ensure_ascii=False, indent=2)
        self._init_api()

    def _init_api(self):
        provider = self.config.get("api", {}).get("provider", "tencent")
        if provider == "tencent":
            self.api = TencentStockAPI()
        elif provider == "custom":
            self.api = CustomStockAPI(self.config)
        else:
            self.api = MockStockAPI()

    def get_market_status(self) -> MarketStatus:
        """
        判断当前时间的 A 股市场交易状态。
        """
        # 如果配置未启用仅交易日刷新，则始终返回交易中（方便开发与演示）
        if not self.config.get("market_hours", {}).get("trading_days_only", True):
            return MarketStatus.TRADING

        now = datetime.now()
        weekday = now.weekday() # 0 = 周一, 6 = 周日
        if weekday >= 5:
            return MarketStatus.WEEKEND_HOLIDAY

        current_t = now.time()
        t_pre = dtime(9, 15)
        t_open1 = dtime(9, 30)
        t_close1 = dtime(11, 30)
        t_open2 = dtime(13, 0)
        t_close2 = dtime(15, 0)

        if current_t < t_pre:
            return MarketStatus.POST_MARKET
        elif t_pre <= current_t < t_open1:
            return MarketStatus.PRE_MARKET
        elif t_open1 <= current_t <= t_close1:
            return MarketStatus.TRADING
        elif t_close1 < current_t < t_open2:
            return MarketStatus.NOON_BREAK
        elif t_open2 <= current_t <= t_close2:
            return MarketStatus.TRADING
        else:
            return MarketStatus.POST_MARKET

    def refresh_once(
        self,
        force_full_refresh: bool = False,
        override_layout: Optional[LayoutMode] = None,
        override_stocks: Optional[List[dict]] = None
    ) -> Image.Image:
        """
        执行单次完整刷新流程：拉取数据 -> 渲染画布 -> 推送墨水屏。
        """
        # 实时重新读取配置以防前端修改
        self.config = self.load_config()
        if override_stocks is not None:
            self.config["stocks"] = override_stocks
        self.state.market_status = self.get_market_status()

        # 获取启用的自选股票代码列表
        stock_configs = [s for s in self.config.get("stocks", []) if s.get("enabled", True)]
        codes = [s["code"] for s in stock_configs]

        # 1. 调用 API 拉取股票数据与大盘指数
        quotes = self.api.get_stock_quotes(codes) if codes else []
        indices = self.api.get_market_indices() if self.config.get("display", {}).get("show_indices", True) else []

        # 2. 确定当前主力股票索引与轮播
        display_cfg = self.config.get("display", {})
        if override_layout is not None:
            layout_mode = override_layout
        else:
            layout_mode = LayoutMode(display_cfg.get("layout_mode", LayoutMode.FOCUS_AND_LIST))
        
        auto_rotate = display_cfg.get("auto_rotate_focus", True)
        rotate_cycles = display_cfg.get("rotate_interval_cycles", 3)

        if auto_rotate and len(quotes) > 1:
            self.cycle_count += 1
            if self.cycle_count >= rotate_cycles:
                self.cycle_count = 0
                self.state.current_focus_index = (self.state.current_focus_index + 1) % len(quotes)
        else:
            # 根据配置的主力代码查找索引
            pref_code = display_cfg.get("focus_stock_code", "")
            for i, q in enumerate(quotes):
                if q.code == pref_code:
                    self.state.current_focus_index = i
                    break

        focus_idx = self.state.current_focus_index if quotes else 0
        if focus_idx >= len(quotes):
            focus_idx = 0
            self.state.current_focus_index = 0

        # 3. 获取大盘走势图与大盘数据 (若为 TencentStockAPI)
        market_index_data = None
        market_chart_img = None
        if hasattr(self.api, "fetch_index_data"):
            market_index_data = self.api.fetch_index_data("sh000001")
            if market_index_data and hasattr(self.api, "generate_index_chart"):
                market_chart_img = self.api.generate_index_chart(market_index_data, width=500, height=230)

        # 4. 渲染 800x480 单色位图
        self.state.last_refresh_time = time.time()
        self.state.update_time_str = datetime.now().strftime("%H:%M:%S")

        img = self.renderer.render(
            stocks=quotes,
            indices=indices,
            state=self.state,
            chart_images={},
            market_index_data=market_index_data,
            market_chart_img=market_chart_img,
            layout_mode=layout_mode,
            focus_index=focus_idx,
            config=self.config
        )
        self.last_rendered_image = img

        # 5. 推送至墨水屏硬件（或虚拟预览）
        if force_full_refresh:
            self.epd.display_full(img)
        else:
            self.epd.display_partial(img)

        # 6. 处理非开盘时段自动休眠
        if self.config.get("system", {}).get("auto_sleep_outside_market", True):
            if self.state.market_status in (MarketStatus.POST_MARKET, MarketStatus.WEEKEND_HOLIDAY):
                self.epd.sleep()

        return img
