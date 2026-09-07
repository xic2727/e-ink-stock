# 📈 树莓派 7.5 英寸墨水屏 A 股实时监控看板 (800×480)

基于**树莓派 3B**与**微雪 7.5 英寸 V2 电子墨水屏**打造的 A 股低功耗、护眼桌面盯盘面板。配备现代化 **Streamlit Web 控制台**，支持多股票管理、分时折线走势图、防残影局部刷新与自定义数据 API 无缝接入。

---

## 🌟 核心功能特性

1. **800×480 像素级墨水屏排版**：
   * **模式一：主力聚焦 + 侧边栏列表（推荐默认）**：左侧展示主力个股的高清分时折线图、当前价格（反色大号高亮）、今开昨收、最高最低、量价明细；右侧纵向排列 3~4 支自选股票卡片。支持主力股票自动定时轮换。
   * **模式二：双股双走势并列对比**：横向分割，双大图同时紧盯两支核心重仓标的。
   * **模式三：4~6 支股票网格全览**：全维度量价指标紧凑排版。
2. **局部刷新与防残影保护**：
   * 严格遵循微雪 `epd7in5_V2_old` 驱动规范，开盘期间每 1 分钟通过局部刷新 (`display_Partial`) 更新数字和走势图，**无黑白全屏闪烁**。
   * 内置**防残影计数器**：每进行 20 次局部刷新自动触发一次全屏复位，彻底清除电子墨水残影。
   * **双稳态休眠**：下午 15:00 收盘后与周末自动调用 `epd.sleep()` 释放驱动电压，屏幕画面永久保持且 0 功耗。
3. **Streamlit 现代化 Web 控制台**：
   * **1:1 屏幕实时预览**：无论是否在墨水屏旁，通过浏览器即可随时查看墨水屏当前完整显示位图。
   * **自选股池管理**：支持随时添加、删除、设置主力焦点股票。
   * **一键运维控制**：支持手动“立即局刷”、“全屏除残影”、“屏幕清白”与“休眠”。
4. **可插拔 API 适配器**：
   * 内置高仿真 A 股模拟数据与分时图生成器（开箱即用，无需外部 API 即可完整测试）。
   * 提供 `services/custom_stock_api.py` 适配层，在控制台填入您提供的股票实时行情 URL 和折线图 URL 即可无缝切换真实数据。

---

## 📂 项目结构

```text
e-ink-stock/
├── app.py                      # Streamlit Web 控制中心
├── daemon.py                   # 开盘期间每分钟自动刷新的常驻后台守护进程
├── config.json                 # 用户自选股列表与系统配置
├── requirements.txt            # Python 依赖清单
├── latest_preview.png          # 800x480 最新渲染画面预览图
│
├── core/                       # 核心业务引擎
│   ├── models.py               # 数据结构 (StockQuote, LayoutMode 等)
│   ├── epd_controller.py       # 墨水屏硬件与虚拟 (Mock) 控制器
│   ├── layout_renderer.py      # 800x480 单色位图排版引擎 (Pillow)
│   ├── image_processor.py      # 折线图反色、二值化与抖动优化
│   ├── font_manager.py         # 跨平台中文字体自适应载入
│   └── scheduler.py            # A股交易时段判断与单次刷新执行器
│
├── services/                   # 数据与图表服务层
│   ├── base_api.py             # API 抽象接口基类
│   ├── custom_stock_api.py     # 【对接用户接口】外部行情与折线图适配器
│   └── mock_stock_api.py       # 内置真实感仿真数据与分时图引擎
│
├── scripts/
│   └── setup_raspberry_pi.sh   # 树莓派环境与 SPI 一键初始化脚本
│
└── tests/
    └── test_renderer.py        # 离线渲染效果测试脚本
```

---

## 🚀 快速启动指南

### 1. 本地测试与预览（Windows / macOS / PC）
系统原生支持虚拟墨水屏模式，无需树莓派或物理墨水屏硬件即可调试：

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 测试渲染生成 3 种模式效果图
python tests/test_renderer.py

# 3. 启动 Streamlit 控制台
streamlit run app.py
```
启动后在浏览器打开 `http://localhost:8501`，即可在“🖥️ 屏幕实时预览”中查看效果。

---

### 2. 部署到树莓派 3B

1. **连线**：将 7.5 寸墨水屏 HAT 排线插入树莓派 3B 的 40-pin GPIO 接口。
2. **运行一键安装脚本**：
   ```bash
   chmod +x scripts/setup_raspberry_pi.sh
   ./scripts/setup_raspberry_pi.sh
   ```
3. **启动控制台与后台刷新**：
   * **启动 Web 控制台**：
     ```bash
     streamlit run app.py --server.port 8501 --server.address 0.0.0.0 &
     ```
     在局域网手机或电脑输入 `http://<树莓派IP>:8501` 即可管理。
   * **启动开盘自动刷新守护进程**：
     ```bash
     python3 daemon.py &
     ```

---

## 🔌 对接您的自定义 API

在 Streamlit 的 **“🔌 API 数据接口配置”** 面板中，切换到 `custom` 模式并填入接口：

1. **股票实时行情接口**：
   * 配置示例：`https://api.yourdomain.com/stocks/quote?codes={codes}`
   * 或在 `services/custom_stock_api.py` 的 `get_stock_quotes` 方法中直接解析您特有的 JSON 结构。
2. **股票分时折线图接口**：
   * 配置示例：`https://api.yourdomain.com/stocks/chart/{code}.png`
   * 支持直接返回图片二进制流、包含 Base64 字符串的 JSON 或图片下载链接。
   * 系统会自动通过 `ImageProcessor` 对接收到的彩色图表进行白底增强、对比度强化与单色二值化，确保在墨水屏上线条锐利清晰。
