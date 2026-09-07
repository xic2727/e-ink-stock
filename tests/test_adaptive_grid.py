import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.scheduler import MarketScheduler
from core.models import LayoutMode

def test_adaptive():
    print("Testing Adaptive Multi-Stock Grid (up to 16 stocks)...")
    scheduler = MarketScheduler()

    all_codes = list(scheduler.api.DEFAULT_STOCKS.keys())
    print(f"Available mock stock codes: {len(all_codes)}")

    test_counts = [4, 6, 8, 9, 12, 16]
    for count in test_counts:
        # 构造指定数量的自选股配置
        selected_codes = all_codes[:count]
        test_stocks = [{"code": c, "name": scheduler.api.DEFAULT_STOCKS[c]["name"], "enabled": True} for c in selected_codes]
        
        img = scheduler.refresh_once(
            force_full_refresh=True,
            override_layout=LayoutMode.GRID_OVERVIEW,
            override_stocks=test_stocks
        )
        filename = f"test_grid_{count}_stocks.png"
        img.save(filename)
        print(f"-> Generated {filename} for {count} stocks (Size: {img.size})")

if __name__ == "__main__":
    test_adaptive()
