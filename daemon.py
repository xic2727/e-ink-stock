import os
import time
import signal
import sys
import logging
from core.scheduler import MarketScheduler

PID_FILE = "eink_daemon.pid"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("eink_stock_daemon.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("EInkDaemon")

def write_pid():
    with open(PID_FILE, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))

def remove_pid():
    if os.path.exists(PID_FILE):
        try:
            os.remove(PID_FILE)
        except OSError:
            pass

def main():
    logger.info("=========================================")
    logger.info("Starting E-Ink Stock Standalone Daemon Service...")
    logger.info("=========================================")

    write_pid()
    scheduler = MarketScheduler()

    def handle_exit(signum, frame):
        logger.info("Received termination signal. Sleeping EPD screen and exiting...")
        remove_pid()
        MarketScheduler.stop_background_service()
        try:
            scheduler.epd.sleep()
        except Exception as e:
            logger.error(f"Error putting EPD to sleep on exit: {e}")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    try:
        # 在主线程中运行统一的时间节点对齐与刷新循环
        MarketScheduler._run_background_loop("config.json")
    except (KeyboardInterrupt, SystemExit):
        handle_exit(None, None)
    finally:
        remove_pid()

if __name__ == "__main__":
    main()
