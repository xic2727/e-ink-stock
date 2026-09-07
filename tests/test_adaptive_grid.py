import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.scheduler import MarketScheduler
from core.models import LayoutMode

def test_adaptive():
    print("Testing Adaptive Multi-Stock Grid (up to 16 stocks)...")
    scheduler = MarketScheduler()

    # 16 支核心 A 股代码
    all_codes = [
        ("000938", "紫光股份"),
        ("600519", "贵州茅台"),
        ("300750", "宁德时代"),
        ("000001", "平安银行"),
        ("002594", "比亚迪"),
        ("601318", "中国平安"),
        ("600036", "招商银行"),
        ("002415", "海康威视"),
        ("601888", "中国中免"),
        ("300059", "东方财富"),
        ("002475", "立讯精密"),
        ("600900", "长江电力"),
        ("000333", "美的集团"),
        ("601166", "兴业银行"),
        ("600276", "恒瑞医药"),
        ("000858", "五粮液"),
    ]
    print(f"Available test stock codes: {len(all_codes)}")

    test_counts = [4, 6, 8, 9, 12, 16]
    for count in test_counts:
        # 构造指定数量的自选股配置
        selected = all_codes[:count]
        test_stocks = [{"code": code, "name": name, "enabled": True} for code, name in selected]
        
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
