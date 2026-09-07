import os
import json
import time
import logging
import threading
from datetime import datetime, time as dtime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image

from core.models import MarketStatus, SystemState, LayoutMode
from core.layout_renderer import LayoutRenderer
from core.epd_controller import EPDController
from services.mock_stock_api import MockStockAPI
from services.custom_stock_api import CustomStockAPI
from services.tencent_stock_api import TencentStockAPI

logger = logging.getLogger(__name__)

# 定义标准北京时区 (UTC+8)
CHINA_TZ = timezone(timedelta(hours=8))

def get_china_now() -> datetime:
    """
    获取标准的北京时间 (UTC+8)。
    彻底避免因树莓派系统默认处于 UTC 时区而导致的市场时段和刷新时间节点误判。
    """
    return datetime.now(timezone.utc).astimezone(CHINA_TZ)

class MarketScheduler:
    """
    A 股市场时间感知与行情刷新调度器。
    管理自选股轮播、时段判断、数据拉取与刷屏。
    支持前台单次刷新及后台常驻单例自动定时调度。
    """

    # ---- 后台自动定时刷新守护服务 (单例模式状态) ----
    _bg_thread: Optional[threading.Thread] = None
    _bg_stop_event = threading.Event()
    _bg_lock = threading.Lock()
    _last_refresh_ts: float = 0.0
    _last_refreshed_minute: int = -1
    _last_status: Optional[MarketStatus] = None
    _next_refresh_desc: str = "等待调度启动"

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

    def get_market_status(self, dt: Optional[datetime] = None) -> MarketStatus:
        """
        判断指定时间（默认为当前北京时间）的 A 股市场交易状态。
        严格解析 config.json 中设定的 morning_start, morning_end, afternoon_start, afternoon_end。
        """
        # 如果配置未启用仅交易日刷新，则始终返回交易中（方便开发、演示与非交易时段测试）
        mkt_cfg = self.config.get("market_hours", {})
        if not mkt_cfg.get("trading_days_only", True):
            return MarketStatus.TRADING

        now = dt if dt is not None else get_china_now()
        weekday = now.weekday() # 0 = 周一, 4 = 周五, 5 = 周六, 6 = 周日
        if weekday >= 5:
            return MarketStatus.WEEKEND_HOLIDAY

        current_t = now.time()

        # 解析用户配置的时间节点
        def _parse_time(t_str: Any, def_h: int, def_m: int) -> dtime:
            try:
                parts = str(t_str).strip().split(":")
                return dtime(int(parts[0]), int(parts[1]))
            except Exception:
                return dtime(def_h, def_m)

        t_open1 = _parse_time(mkt_cfg.get("morning_start", "09:25"), 9, 25)
        t_close1 = _parse_time(mkt_cfg.get("morning_end", "11:30"), 11, 30)
        t_open2 = _parse_time(mkt_cfg.get("afternoon_start", "13:00"), 13, 0)
        t_close2 = _parse_time(mkt_cfg.get("afternoon_end", "15:00"), 15, 0)
        t_pre = dtime(9, 15)

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
        self.state.update_time_str = get_china_now().strftime("%H:%M:%S")

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

        return img

    # ==================== 后台自动定时刷新守护服务 ====================

    @classmethod
    def is_external_daemon_running(cls) -> bool:
        """检查外部独立常驻守护进程 daemon.py 是否正在运行"""
        pid_file = "eink_daemon.pid"
        if os.path.exists(pid_file):
            try:
                with open(pid_file, "r", encoding="utf-8") as f:
                    pid = int(f.read().strip())
                if os.name == 'nt':
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    SYNCHRONIZE = 0x00100000
                    h_proc = kernel32.OpenProcess(SYNCHRONIZE, 0, pid)
                    if h_proc != 0:
                        kernel32.CloseHandle(h_proc)
                        return True
                else:
                    os.kill(pid, 0)
                    return True
            except (OSError, ValueError):
                return False
        return False

    @classmethod
    def is_background_running(cls) -> bool:
        """后台刷新服务是否处于活动状态（内置线程或外部守护进程）"""
        return (cls._bg_thread is not None and cls._bg_thread.is_alive()) or cls.is_external_daemon_running()

    @classmethod
    def get_background_status(cls) -> Dict[str, Any]:
        """获取后台刷新运行状态及诊断信息"""
        external = cls.is_external_daemon_running()
        internal = cls._bg_thread is not None and cls._bg_thread.is_alive()
        beijing_now = get_china_now()
        
        last_str = datetime.fromtimestamp(cls._last_refresh_ts, CHINA_TZ).strftime("%H:%M:%S") if cls._last_refresh_ts > 0 else "尚未刷新"

        return {
            "is_running": external or internal,
            "mode": "外部常驻守护进程 (daemon.py)" if external else ("内置调度线程 (Streamlit 驱动)" if internal else "未启动"),
            "beijing_time": beijing_now.strftime("%Y-%m-%d %H:%M:%S"),
            "last_refresh_time": last_str,
            "next_refresh_desc": cls._next_refresh_desc,
            "last_status": cls._last_status.value if cls._last_status else "待检测"
        }

    @classmethod
    def start_background_service(cls, config_path: str = "config.json"):
        """启动内置后台自动刷新线程（单例保证）"""
        with cls._bg_lock:
            if cls.is_external_daemon_running():
                logger.info("External daemon.py is already running. Skipping internal thread start.")
                return
            if cls._bg_thread is not None and cls._bg_thread.is_alive():
                return
            cls._bg_stop_event.clear()
            cls._bg_thread = threading.Thread(
                target=cls._run_background_loop,
                args=(config_path,),
                daemon=True,
                name="EInkStockSchedulerThread"
            )
            cls._bg_thread.start()
            logger.info("MarketScheduler internal background thread started.")

    @classmethod
    def stop_background_service(cls):
        """停止内置后台自动刷新线程"""
        with cls._bg_lock:
            if cls._bg_thread is not None:
                cls._bg_stop_event.set()
                cls._bg_thread = None
                cls._next_refresh_desc = "服务已暂停"
                logger.info("MarketScheduler internal background thread stopped.")

    @classmethod
    def _run_background_loop(cls, config_path: str):
        """
        后台定时刷新主循环：
        1. 毫秒级感知精准北京时间 (UTC+8)；
        2. 时段切换节点（开市、集合竞价、午休、收盘）触发专属事件动作；
        3. 周期性刷新严格对齐整分时间节点（例如每分钟 02 秒，留出数据源同步时间）。
        """
        scheduler = MarketScheduler(config_path)
        logger.info("E-Ink Market Scheduler loop started.")

        # 启动时执行一次首刷同步
        try:
            scheduler.refresh_once(force_full_refresh=False)
            cls._last_refresh_ts = time.time()
            cls._last_refreshed_minute = get_china_now().minute
            cls._last_status = scheduler.get_market_status()
        except Exception as e:
            logger.error(f"Initial background refresh error: {e}")

        while not cls._bg_stop_event.is_set():
            try:
                cfg = scheduler.load_config()
                sys_cfg = cfg.get("system", {})
                mkt_cfg = cfg.get("market_hours", {})

                interval = max(5, int(sys_cfg.get("partial_refresh_interval_sec", 60)))
                trading_only = mkt_cfg.get("trading_days_only", True)

                beijing_now = get_china_now()
                current_status = scheduler.get_market_status(beijing_now)

                # A. 检查市场时段状态转换时间节点
                if current_status != cls._last_status:
                    logger.info(f"Market status transition: {cls._last_status} -> {current_status}")
                    if current_status in (MarketStatus.TRADING, MarketStatus.PRE_MARKET):
                        logger.info(f"Market opened ({current_status.value}), executing opening silent partial refresh...")
                        scheduler.refresh_once(force_full_refresh=False)
                        cls._last_refresh_ts = time.time()
                        cls._last_refreshed_minute = beijing_now.minute
                    elif current_status == MarketStatus.NOON_BREAK:
                        logger.info("Midday market break, executing full refresh to clear ghosting...")
                        scheduler.refresh_once(force_full_refresh=True)
                        cls._last_refresh_ts = time.time()
                    elif current_status in (MarketStatus.POST_MARKET, MarketStatus.WEEKEND_HOLIDAY):
                        logger.info("Market closed, executing final full refresh & sleeping screen...")
                        scheduler.refresh_once(force_full_refresh=True)
                        if sys_cfg.get("auto_sleep_outside_market", True):
                            scheduler.epd.sleep()
                        cls._last_refresh_ts = time.time()
                    cls._last_status = current_status

                # B. 判断当前时间节点是否需要执行周期刷新
                now_ts = time.time()
                should_refresh = False

                if not trading_only:
                    # 演示/调试模式：全天候按时间节点刷新
                    if interval >= 60:
                        # 整分节点对齐：在每分钟的 02 秒触发（让交易所和腾讯行情生成最新 tick）
                        if beijing_now.minute != cls._last_refreshed_minute and beijing_now.second >= 2:
                            should_refresh = True
                    else:
                        if now_ts - cls._last_refresh_ts >= interval:
                            should_refresh = True
                    cls._next_refresh_desc = f"每 {interval} 秒刷新 (全天调试模式)"
                else:
                    # 正式交易模式：仅在开市时段（交易中或集合竞价）按节点刷新
                    if current_status in (MarketStatus.TRADING, MarketStatus.PRE_MARKET):
                        if interval >= 60:
                            if beijing_now.minute != cls._last_refreshed_minute and beijing_now.second >= 2:
                                should_refresh = True
                        else:
                            if now_ts - cls._last_refresh_ts >= interval:
                                should_refresh = True
                        cls._next_refresh_desc = f"下个整分节点 (:02 秒) 局部刷新"
                    elif current_status == MarketStatus.NOON_BREAK:
                        cls._next_refresh_desc = f"午间休市中 (等待 13:00 开市节点)"
                    elif current_status == MarketStatus.WEEKEND_HOLIDAY:
                        cls._next_refresh_desc = "周末休市中 (墨水屏保持休眠)"
                    else:
                        cls._next_refresh_desc = f"已收盘 (等待明日开市节点)"

                if should_refresh:
                    logger.info(f"Executing scheduled refresh at {beijing_now.strftime('%H:%M:%S')} (status: {current_status.value})...")
                    scheduler.refresh_once(force_full_refresh=False)
                    cls._last_refresh_ts = time.time()
                    cls._last_refreshed_minute = beijing_now.minute

            except Exception as e:
                logger.error(f"Error in background scheduler tick: {e}", exc_info=True)

            # 睡眠 1 秒以支持秒级节点精准对齐
            cls._bg_stop_event.wait(1.0)

        logger.info("E-Ink Market Scheduler loop stopped.")
