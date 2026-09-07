import time
import signal
import sys
import logging
from datetime import datetime
from core.scheduler import MarketScheduler
from core.models import MarketStatus

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("eink_stock_daemon.log", encoding="utf-8")
    ]
)

logger = logging.getLogger("EInkDaemon")

def main():
    logger.info("=========================================")
    logger.info("Starting E-Ink Stock Daemon Service...")
    logger.info("=========================================")

    scheduler = MarketScheduler()

    # 注册退出信号处理
    def handle_exit(signum, frame):
        logger.info("Received termination signal. Sleeping EPD screen and exiting...")
        try:
            scheduler.epd.sleep()
        except Exception as e:
            logger.error(f"Error putting EPD to sleep on exit: {e}")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    last_status = None
    last_refresh_time = 0

    # 启动时先执行一次全屏初始化刷新
    logger.info("Performing initial full display update on start...")
    try:
        scheduler.refresh_once(force_full_refresh=True)
        last_refresh_time = time.time()
    except Exception as e:
        logger.error(f"Initial refresh failed: {e}")

    while True:
        try:
            cfg = scheduler.load_config()
            interval = cfg.get("system", {}).get("partial_refresh_interval_sec", 60)
            trading_only = cfg.get("market_hours", {}).get("trading_days_only", True)
            current_status = scheduler.get_market_status()

            # 检测市场时段状态转换
            if current_status != last_status:
                logger.info(f"Market status changed: {last_status} -> {current_status}")
                if current_status == MarketStatus.NOON_BREAK:
                    # 午间休市，执行一次全刷除残影
                    logger.info("Midday market close, refreshing full screen...")
                    scheduler.refresh_once(force_full_refresh=True)
                elif current_status == MarketStatus.POST_MARKET:
                    # 下午闭市，执行一次最终全刷后休眠
                    logger.info("Market closed for the day, executing final summary refresh and sleeping screen...")
                    scheduler.refresh_once(force_full_refresh=True)
                    scheduler.epd.sleep()
                last_status = current_status

            # 判断是否需要刷新
            now = time.time()
            should_refresh = False

            if not trading_only:
                # 无论何时均刷新（演示/调试模式）
                if now - last_refresh_time >= interval:
                    should_refresh = True
            else:
                # 仅在开盘时段（或盘前集合竞价）每分钟刷新
                if current_status in (MarketStatus.TRADING, MarketStatus.PRE_MARKET):
                    if now - last_refresh_time >= interval:
                        should_refresh = True

            if should_refresh:
                logger.info(f"Executing scheduled 1-min partial refresh ({current_status.value})...")
                scheduler.refresh_once(force_full_refresh=False)
                last_refresh_time = now

            # 睡眠 2 秒以避免 CPU 忙轮询
            time.sleep(2)

        except Exception as e:
            logger.error(f"Daemon loop encountered error: {e}", exc_info=True)
            time.sleep(5)

if __name__ == "__main__":
    main()
