#!/bin/bash
# ==============================================================================
# 墨水屏看板 Web 控制台与守护进程停止脚本
# ==============================================================================

cd "$(dirname "$0")"

STOPPED=0

# 1. 停止 Streamlit Web 服务
if [ -f "streamlit.pid" ]; then
    PID=$(cat streamlit.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "🛑 正在停止 Streamlit (PID: $PID)..."
        kill $PID
        STOPPED=1
    fi
    rm -f streamlit.pid
fi

# 兜底：查找并结束残留的 streamlit 进程
ST_PIDS=$(pgrep -f "streamlit run app.py" 2>/dev/null || true)
if [ -n "$ST_PIDS" ]; then
    echo "🛑 停止运行中的 Streamlit 进程: $ST_PIDS"
    kill $ST_PIDS 2>/dev/null || true
    STOPPED=1
fi

# 2. 停止 daemon.py 守护进程（如果存在）
if [ -f "eink_daemon.pid" ]; then
    PID=$(cat eink_daemon.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "🛑 正在停止后台刷新守护服务 (PID: $PID)..."
        kill $PID
        STOPPED=1
    fi
    rm -f eink_daemon.pid
fi

DAEMON_PIDS=$(pgrep -f "python3 daemon.py" 2>/dev/null || true)
if [ -n "$DAEMON_PIDS" ]; then
    echo "🛑 停止运行中的守护进程: $DAEMON_PIDS"
    kill $DAEMON_PIDS 2>/dev/null || true
    STOPPED=1
fi

if [ $STOPPED -eq 1 ]; then
    echo "✅ 相关看板服务已成功停止。"
else
    echo "ℹ️ 当前没有正在运行的看板服务。"
fi
