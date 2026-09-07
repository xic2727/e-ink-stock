#!/bin/bash
# ==============================================================================
# 树莓派 3B + 7.5 寸墨水屏 A 股监控看板 一键环境安装脚本
# ==============================================================================

set -e

echo "=== 1. 开启树莓派硬件 SPI 接口 ==="
sudo raspi-config nonint do_spi 0
echo "SPI 接口已开启。"

echo "=== 2. 安装系统底层依赖与中文字体 (文泉驿微米黑) ==="
sudo apt-get update
sudo apt-get install -y \
    python3-pip \
    python3-dev \
    python3-pil \
    python3-numpy \
    python3-spidev \
    fonts-wqy-microhei \
    fonts-wqy-zenhei \
    libopenjp2-7 \
    libtiff5

echo "=== 3. 安装 Python 依赖 ==="
pip3 install -r requirements.txt

echo "=== 4. 测试墨水屏硬件与渲染 ==="
python3 tests/test_renderer.py

echo "=== 环境配置完成！==="
echo "启动 Streamlit 控制台: streamlit run app.py --server.port 8501 --server.address 0.0.0.0"
echo "启动后台刷新守护进程: python3 daemon.py"
