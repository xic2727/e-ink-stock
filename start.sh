#!/bin/bash
# ==============================================================================
# 墨水屏看板 Web 控制台快捷启动脚本
# ==============================================================================

# 确保切换到项目根目录
cd "$(dirname "$0")"

# 1. 检查是否存在 Python 虚拟环境并自动激活
if [ -d "venv" ] && [ -f "venv/bin/activate" ]; then
    echo "⚡ 激活虚拟环境 (venv)..."
    source venv/bin/activate
elif [ -d ".venv" ] && [ -f ".venv/bin/activate" ]; then
    echo "⚡ 激活虚拟环境 (.venv)..."
    source .venv/bin/activate
fi

# 2. 获取树莓派局域网 IP 地址
LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -z "$LAN_IP" ]; then
    LAN_IP="127.0.0.1"
fi

PORT=8501

echo "================================================================"
echo "  🚀 正在启动 7.5 寸墨水屏股票看板 Web 控制台..."
echo "  🌐 局域网访问地址: http://${LAN_IP}:${PORT}"
echo "  💻 本地访问地址:   http://localhost:${PORT}"
echo "  按 Ctrl+C 可停止前台运行"
echo "================================================================"

# 3. 优先使用 streamlit 命令，若不存在则回退至 python3 -m streamlit
if command -v streamlit &> /dev/null; then
    CMD="streamlit"
else
    CMD="python3 -m streamlit"
fi

# 4. 判断是否以后台模式启动（支持 ./start.sh -d 或 ./start.sh --daemon）
if [ "$1" = "-d" ] || [ "$1" = "--daemon" ]; then
    LOG_FILE="streamlit.log"
    echo "📌 已以后台模式启动，日志输出至 ${LOG_FILE}"
    nohup $CMD run app.py --server.port $PORT --server.address 0.0.0.0 > "$LOG_FILE" 2>&1 &
    PID=$!
    echo $PID > streamlit.pid
    echo "✅ 服务已在后台启动 (PID: $PID)"
    echo "💡 停止服务命令: ./stop.sh"
else
    exec $CMD run app.py --server.port $PORT --server.address 0.0.0.0
fi
