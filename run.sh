#!/bin/bash
# ===================================================
#  LightPress CMS + Finance Manager 一键启动/停止脚本
# ===================================================
#  用法:
#    ./run.sh             启动服务（默认）
#    ./run.sh --seed      启动服务并重新生成种子数据
#    ./run.sh stop        停止服务（释放 8000 端口）
#    ./run.sh restart     重启服务
# ===================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
PORT="${PORT:-8000}"

# ---- 停止服务 ----
stop_server() {
    echo ">>> 检查端口 ${PORT} 占用..."
    local PIDS=$(lsof -t -i:${PORT} 2>/dev/null || true)
    if [ -z "$PIDS" ]; then
        echo "    端口 ${PORT} 未被占用"
    else
        echo "    正在终止占用端口 ${PORT} 的进程: $PIDS"
        kill -9 $PIDS 2>/dev/null || true
        sleep 1
        echo "    端口 ${PORT} 已释放"
    fi
}

# ---- 启动服务 ----
start_server() {
    echo ""
    echo "  ╔══════════════════════════════════════════╗"
    echo "  ║   LightPress CMS + 个人财务管理平台      ║"
    echo "  ╚══════════════════════════════════════════╝"
    echo ""

    # 0. 检查依赖
    echo ">>> 检查 python-dateutil 依赖..."
    python3 -c "import dateutil" 2>/dev/null || {
        echo "安装 python-dateutil ..."
        python3 -m pip install python-dateutil -q
    }

    # 1. 初始化种子数据（首次运行或 --seed 参数时）
    if [ "$1" = "--seed" ] || [ ! -f app.db ]; then
        echo ">>> 生成种子数据..."
        python3 seed_finance_data.py 2>/dev/null || true
        echo ""
    fi

    # 2. 先释放端口
    stop_server

    # 3. 启动服务
    echo ">>> 启动 FastAPI 服务 (端口 ${PORT})..."
    echo ""
    echo "  ┌────────────────────────────────────────────┐"
    echo "  │  访问地址:                                  │"
    echo "  │                                            │"
    echo "  │  财务管理平台:                              │"
    echo "  │  http://127.0.0.1:${PORT}/static/finance.html │"
    echo "  │                                            │"
    echo "  │  CMS 管理后台:                              │"
    echo "  │  http://127.0.0.1:${PORT}/static/index.html   │"
    echo "  │                                            │"
    echo "  │  API 文档 (Swagger):                        │"
    echo "  │  http://127.0.0.1:${PORT}/docs               │"
    echo "  │                                            │"
    echo "  │  API 健康检查:                              │"
    echo "  │  http://127.0.0.1:${PORT}/                   │"
    echo "  └────────────────────────────────────────────┘"
    echo ""
    echo "  按 Ctrl+C 停止服务"
    echo ""

    # 捕获 Ctrl+C 信号，退出时自动释放端口
    trap stop_server EXIT SIGINT SIGTERM

    python3 -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --reload
}

# ---- 主逻辑 ----
case "${1:-start}" in
    stop)
        stop_server
        ;;
    restart)
        stop_server
        sleep 1
        start_server "${2:-}"
        ;;
    *)
        start_server "$1"
        ;;
esac
