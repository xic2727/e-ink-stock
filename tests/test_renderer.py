import os
import sys

# 将项目根目录加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.scheduler import MarketScheduler
from core.models import LayoutMode

def test_pipeline():
    print("Testing e-ink stock rendering pipeline...")
    scheduler = MarketScheduler()
    
    # 强制生成模式一
    img1 = scheduler.refresh_once(force_full_refresh=True, override_layout=LayoutMode.FOCUS_AND_LIST)
    img1.save("test_mode_1.png")
    print(f"Generated test_mode_1.png (Size: {img1.size}, Mode: {img1.mode})")

    # 强制生成模式二
    img2 = scheduler.refresh_once(force_full_refresh=True, override_layout=LayoutMode.DUAL_COMPARE)
    img2.save("test_mode_2.png")
    print(f"Generated test_mode_2.png (Size: {img2.size}, Mode: {img2.mode})")

    # 强制生成模式三
    img3 = scheduler.refresh_once(force_full_refresh=True, override_layout=LayoutMode.GRID_OVERVIEW)
    img3.save("test_mode_3.png")
    print(f"Generated test_mode_3.png (Size: {img3.size}, Mode: {img3.mode})")

    print("All layout modes tested successfully!")

if __name__ == "__main__":
    test_pipeline()
