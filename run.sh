#!/bin/bash
# ===================================================
#  LightPress CMS + Finance Manager 一键启动脚本
# ===================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

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

# 2. 启动服务
echo ">>> 启动 FastAPI 服务 (端口 8000)..."
echo ""
echo "  ┌────────────────────────────────────────────┐"
echo "  │  访问地址:                                  │"
echo "  │                                            │"
echo "  │  财务管理平台:                              │"
echo "  │  http://127.0.0.1:8000/static/finance.html  │"
echo "  │                                            │"
echo "  │  CMS 管理后台:                              │"
echo "  │  http://127.0.0.1:8000/static/index.html    │"
echo "  │                                            │"
echo "  │  API 文档 (Swagger):                        │"
echo "  │  http://127.0.0.1:8000/docs                 │"
echo "  │                                            │"
echo "  │  API 健康检查:                              │"
echo "  │  http://127.0.0.1:8000/                     │"
echo "  └────────────────────────────────────────────┘"
echo ""
echo "  按 Ctrl+C 停止服务"
echo ""

python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
