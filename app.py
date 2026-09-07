import os
import json
import time
from datetime import datetime
import streamlit as st
from PIL import Image

from core.scheduler import MarketScheduler
from core.models import LayoutMode, MarketStatus

# 页面配置
st.set_page_config(
    page_title="墨水屏 A 股行情监控看板",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 样式增强
st.markdown("""
<style>
    .main-metric {
        background-color: #f0f2f6;
        border-radius: 8px;
        padding: 12px 18px;
        margin-bottom: 10px;
    }
    .status-badge {
        font-weight: bold;
        padding: 4px 8px;
        border-radius: 4px;
    }
</style>
""", unsafe_allow_html=True)

# 初始化或获取调度器实例 (缓存于 session_state)
if "scheduler" not in st.session_state:
    st.session_state.scheduler = MarketScheduler()

scheduler: MarketScheduler = st.session_state.scheduler

# ----------------- 侧边栏：快速操作与系统状态 -----------------
with st.sidebar:
    st.title("📟 墨水屏看板控制台")
    
    # 状态指示卡片
    market_stat = scheduler.get_market_status()
    st.info(f"**市场状态**：{market_stat.value}  \n**硬件模式**：{'🔌 树莓派 SPI 墨水屏' if scheduler.epd.is_hardware_available else '💻 虚拟/Mock 屏幕'}")
    
    st.subheader("⚡ 硬件与刷新控制")
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🔄 立即局刷", use_container_width=True, help="拉取最新数据并执行墨水屏局部刷新"):
            with st.spinner("正在刷新..."):
                scheduler.refresh_once(force_full_refresh=False)
                st.toast("局部刷新完成！", icon="✅")
    with col_btn2:
        if st.button("🧹 全屏除残影", use_container_width=True, help="执行全屏闪烁复位，清除电子墨水残影"):
            with st.spinner("正在清除残影..."):
                scheduler.refresh_once(force_full_refresh=True)
                st.toast("全屏复位完成！残影已清除", icon="✨")

    col_btn3, col_btn4 = st.columns(2)
    with col_btn3:
        if st.button("🌙 屏幕休眠", use_container_width=True):
            scheduler.epd.sleep()
            st.toast("墨水屏已休眠（画面保持，关闭电压）", icon="💤")
    with col_btn4:
        if st.button("☀️ 屏幕清白", use_container_width=True):
            scheduler.epd.clear()
            st.toast("墨水屏已完全清白", icon="⚪")

    st.divider()
    st.caption("提示：在开盘时段（9:30-11:30, 13:00-15:00），后台常驻进程 `daemon.py` 将自动每分钟局部更新一次。")

# ----------------- 主界面 Tabs -----------------
tab_preview, tab_stocks, tab_display, tab_schedule, tab_api = st.tabs([
    "🖥️ 屏幕实时预览",
    "⭐ 自选股票管理",
    "🎨 显示布局设置",
    "⏰ 交易时钟与调度",
    "🔌 API 数据接口配置"
])

# ==================== Tab 1: 屏幕实时预览 ====================
with tab_preview:
    st.header("800×480 墨水屏画面 1:1 实时预览")
    
    # 获取预览图片
    preview_file = "latest_preview.png"
    if not os.path.exists(preview_file):
        # 初始自动生成一张
        scheduler.refresh_once()

    if os.path.exists(preview_file):
        img = Image.open(preview_file)
        st.image(img, caption=f"当前墨水屏展示画面 (分辨率: 800x480 单色位图) - 局部刷新计数: {scheduler.epd.partial_count}/{scheduler.epd.max_partial}", use_container_width=True)
    else:
        st.warning("暂无预览图像，请点击侧边栏的【立即局刷】生成第一帧画面。")

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric("上次刷新时间", scheduler.state.update_time_str or "尚未刷新")
    with col_m2:
        st.metric("局刷累计次数", f"{scheduler.epd.partial_count} 次")
    with col_m3:
        st.metric("防残影阈值", f"{scheduler.epd.max_partial} 次")
    with col_m4:
        st.metric("屏幕休眠状态", "休眠中 💤" if scheduler.epd.is_sleeping else "工作唤醒 ⚡")

# ==================== Tab 2: 自选股票管理 ====================
with tab_stocks:
    st.header("自选股票池管理")
    
    config = scheduler.load_config()
    stocks = config.get("stocks", [])
    
    # 1. 腾讯 Smartbox 智能搜索与快捷添加
    st.subheader("🔍 搜索并快捷添加股票 (腾讯 Smartbox 驱动)")
    col_q1, col_q2 = st.columns([4, 1])
    with col_q1:
        search_query = st.text_input("输入股票代码、拼音或名称", placeholder="例如: 000938 或 紫光股份 或 茅台", label_visibility="collapsed")
    with col_q2:
        do_search = st.button("🔍 搜索股票", use_container_width=True)

    if search_query.strip():
        from services.tencent_stock_api import TencentStockAPI
        searcher = TencentStockAPI()
        search_results = searcher.search_stock(search_query.strip())
        if search_results:
            st.write(f"找到 {len(search_results)} 个匹配项：")
            for s_idx, item in enumerate(search_results[:5]):
                col_r1, col_r2, col_r3, col_r4 = st.columns([2, 2, 2, 1])
                with col_r1:
                    st.write(f"**{item['name']}**")
                with col_r2:
                    st.code(item['market_code'])
                with col_r3:
                    st.caption(f"板块: {item['type']} ({item['market']})")
                with col_r4:
                    if st.button("➕ 添加", key=f"add_{item['market_code']}_{s_idx}"):
                        if any(s["code"] == item["code"] for s in stocks):
                            st.warning("该股票已在自选池中！")
                        else:
                            stocks.append({
                                "code": item["code"],
                                "name": item["name"],
                                "market": item["market"],
                                "enabled": True
                            })
                            config["stocks"] = stocks
                            scheduler.save_config(config)
                            st.success(f"已添加：{item['name']} ({item['code']})")
                            st.rerun()
        else:
            if do_search:
                st.warning("未查询到匹配标的，请确认输入是否准确。")

    # 2. 手动添加备用折叠面板
    with st.expander("✍️ 手动精确录入代码", expanded=False):
        col_a1, col_a2, col_a3, col_a4 = st.columns([2, 2, 2, 1])
        with col_a1:
            new_code = st.text_input("股票代码", placeholder="例如: 000938")
        with col_a2:
            new_name = st.text_input("股票简称", placeholder="例如: 紫光股份")
        with col_a3:
            new_market = st.selectbox("市场板块", ["SZ (深市)", "SH (沪市)", "BJ (北交所)"])
        with col_a4:
            st.write("")
            st.write("")
            if st.button("手动添加", type="primary", use_container_width=True):
                if new_code.strip() and new_name.strip():
                    stocks.append({
                        "code": new_code.strip(),
                        "name": new_name.strip(),
                        "market": new_market.split()[0],
                        "enabled": True
                    })
                    config["stocks"] = stocks
                    scheduler.save_config(config)
                    st.success(f"已添加股票：{new_name} ({new_code})")
                    st.rerun()

    st.subheader("当前自选股票列表")
    current_focus = config.get("display", {}).get("focus_stock_code", "")

    for idx, s in enumerate(stocks):
        with st.container():
            col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns([1, 2, 2, 2, 2])
            with col_s1:
                st.write(f"**#{idx+1}**")
            with col_s2:
                is_focus = (s["code"] == current_focus)
                badge = " 🏆 [主力焦点]" if is_focus else ""
                st.write(f"**{s['name']}** ({s['code']}){badge}")
            with col_s3:
                enabled = st.checkbox("启用展示", value=s.get("enabled", True), key=f"en_{s['code']}_{idx}")
                if enabled != s.get("enabled", True):
                    s["enabled"] = enabled
                    scheduler.save_config(config)
                    st.rerun()
            with col_s4:
                if not is_focus:
                    if st.button("设为主力", key=f"set_focus_{s['code']}_{idx}"):
                        config["display"]["focus_stock_code"] = s["code"]
                        scheduler.save_config(config)
                        st.toast(f"已将 {s['name']} 设为默认主力股票", icon="🎯")
                        st.rerun()
            with col_s5:
                if st.button("🗑️ 删除", key=f"del_{s['code']}_{idx}"):
                    stocks.pop(idx)
                    config["stocks"] = stocks
                    scheduler.save_config(config)
                    st.success("已删除该股票")
                    st.rerun()
            st.divider()

# ==================== Tab 3: 显示布局设置 ====================
with tab_display:
    st.header("墨水屏 800×480 布局与视觉选项")
    
    config = scheduler.load_config()
    disp = config.get("display", {})

    layout_choices = {
        "focus_and_list": "模式一：主力聚焦 + 侧边栏自选股列表 (推荐，含大折线图)",
        "dual_compare": "模式二：双股双折线图并列对比 (适合紧盯两支核心标的)",
        "grid_overview": "模式三：自适应多股网格看板 (支持 1 ~ 16 支股票动态自适应排版)"
    }
    
    current_layout = disp.get("layout_mode", "focus_and_list")
    selected_layout = st.radio(
        "选择墨水屏排版模式",
        options=list(layout_choices.keys()),
        format_func=lambda k: layout_choices[k],
        index=list(layout_choices.keys()).index(current_layout) if current_layout in layout_choices else 0
    )

    st.subheader("轮播与指标选项")
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        auto_rotate = st.toggle("开启主力股票自动轮播", value=disp.get("auto_rotate_focus", True))
        rotate_cycles = st.slider("主力股票轮播周期 (每 N 次刷新切换下一支)", min_value=1, max_value=10, value=disp.get("rotate_interval_cycles", 3))
    with col_d2:
        show_indices = st.toggle("顶部显示大盘指数栏 (上证/深证/创业板)", value=disp.get("show_indices", True))
        contrast_boost = st.slider("折线图二值化对比度增强", min_value=1.0, max_value=2.5, value=float(disp.get("chart_contrast_boost", 1.4)), step=0.1)

    if st.button("💾 保存显示配置并立即应用", type="primary"):
        disp["layout_mode"] = selected_layout
        disp["auto_rotate_focus"] = auto_rotate
        disp["rotate_interval_cycles"] = rotate_cycles
        disp["show_indices"] = show_indices
        disp["chart_contrast_boost"] = contrast_boost
        config["display"] = disp
        scheduler.save_config(config)
        scheduler.refresh_once()
        st.success("显示配置已更新，并已重新渲染墨水屏！")
        st.rerun()

# ==================== Tab 4: 交易时钟与调度 ====================
with tab_schedule:
    st.header("交易时钟与定时刷新机制")
    
    config = scheduler.load_config()
    sys_cfg = config.get("system", {})
    mkt_cfg = config.get("market_hours", {})

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.subheader("开盘刷新策略")
        refresh_interval = st.number_input("开盘时段刷新频率 (秒)", min_value=10, max_value=600, value=int(sys_cfg.get("partial_refresh_interval_sec", 60)), step=10)
        max_partial = st.number_input("自动全屏除残影阈值 (次)", min_value=5, max_value=100, value=int(sys_cfg.get("max_partial_refreshes_before_full", 20)), step=5, help="每进行 N 次局部刷新后，自动执行一次全刷闪烁，消除电子墨水残影")
        trading_days_only = st.toggle("仅在交易日及开盘时段刷新", value=mkt_cfg.get("trading_days_only", True), help="关闭后将在任何时间均定时刷新，适合离线调试或周末演示")
    
    with col_t2:
        st.subheader("闭市低功耗保护")
        auto_sleep = st.toggle("闭市及周末后墨水屏自动深度休眠", value=sys_cfg.get("auto_sleep_outside_market", True), help="墨水屏依靠双稳态保持画面，休眠时关闭电极电压，防止元器件老化")
        st.info("""
        **A 股标准交易时段设置：**
        * 早盘：09:25 ~ 11:30 (含集合竞价)
        * 午盘：13:00 ~ 15:00
        * 闭市保护：15:01 执行收盘盘点全刷，随后自动进入 Deep Sleep
        """)

    if st.button("💾 保存调度配置"):
        sys_cfg["partial_refresh_interval_sec"] = refresh_interval
        sys_cfg["max_partial_refreshes_before_full"] = max_partial
        sys_cfg["auto_sleep_outside_market"] = auto_sleep
        mkt_cfg["trading_days_only"] = trading_days_only
        config["system"] = sys_cfg
        config["market_hours"] = mkt_cfg
        scheduler.save_config(config)
        st.success("调度配置保存成功！")

# ==================== Tab 5: API 数据接口配置 ====================
with tab_api:
    st.header("股票实时数据与折线图 API 对接")
    
    config = scheduler.load_config()
    api_cfg = config.get("api", {})

    provider_map = {
        "tencent": "tencent (腾讯证券官方直连 - 推荐，免配置开箱即用)",
        "mock": "mock (内置高仿真数据与模拟走势图)",
        "custom": "custom (用户自定义外部 API 接口)"
    }
    
    current_p = api_cfg.get("provider", "tencent")
    provider_keys = list(provider_map.keys())
    p_idx = provider_keys.index(current_p) if current_p in provider_keys else 0

    selected_provider_key = st.selectbox(
        "数据源提供者",
        provider_keys,
        format_func=lambda k: provider_map[k],
        index=p_idx
    )

    if selected_provider_key == "tencent":
        st.success("🟢 已启用腾讯证券直连：支持个股极速实时行情 (sqt.gtimg.cn)、智能搜索 (Smartbox) 以及大盘指数分时走势图 (web.ifzq.gtimg.cn)，完全无需鉴权与 Token！")
    elif selected_provider_key == "mock":
        st.info("🔵 运行于内置仿真模式：生成高仿真 A 股随机游走价格与行情。")

    is_custom = (selected_provider_key == "custom")
    custom_quote = st.text_input("股票实时数据 API 地址 (GET)", value=api_cfg.get("custom_quote_url", ""), placeholder="例如: https://sqt.gtimg.cn/utf8/?q={codes}&fmt=json", disabled=not is_custom)
    custom_chart = st.text_input("备用图表 API 地址 (可选)", value=api_cfg.get("custom_chart_url", ""), placeholder="例如: https://api.yourdomain.com/chart/{code}.png", disabled=not is_custom)
    custom_token = st.text_input("API Token / 访问密钥 (可选)", value=api_cfg.get("custom_token", ""), type="password", disabled=not is_custom)

    col_api_btn1, col_api_btn2 = st.columns([1, 3])
    with col_api_btn1:
        if st.button("💾 保存 API 配置", type="primary"):
            api_cfg["provider"] = selected_provider_key
            api_cfg["custom_quote_url"] = custom_quote
            api_cfg["custom_chart_url"] = custom_chart
            api_cfg["custom_token"] = custom_token
            config["api"] = api_cfg
            scheduler.save_config(config)
            st.success("API 配置已保存！")
            st.rerun()

    with col_api_btn2:
        if st.button("🧪 测试实时数据与大盘走势图"):
            with st.spinner("正在请求数据与绘制分时图..."):
                try:
                    test_quotes = scheduler.api.get_stock_quotes(["000938", "600519"])
                    st.success("✅ 股票行情接口请求成功！")
                    st.write(f"测试股票：{test_quotes[0].name} ({test_quotes[0].code}) - 最新价: {test_quotes[0].price} 涨跌: {test_quotes[0].change_pct:+.2f}%")
                    
                    if hasattr(scheduler.api, "fetch_index_data"):
                        idx_data = scheduler.api.fetch_index_data("sh000001")
                        if idx_data:
                            chart_img = scheduler.api.generate_index_chart(idx_data, width=480, height=220)
                            if chart_img:
                                st.image(chart_img, caption="本地根据分钟数据绘制的大盘走势图 (1-bit 单色)", width=480)
                except Exception as e:
                    st.error(f"API 测试异常：{e}")
