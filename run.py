#!/usr/bin/env python3
"""财智管家 — 启动/停止/重启脚本

用法:
    python run.py start       启动服务
    python run.py stop        停止服务
    python run.py restart     重启服务
    python run.py status      查看状态
"""
import os
import sys
import signal
import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PID_FILE = ROOT / ".caizhiguanjia.pid"
PORT = os.environ.get("PORT", "8000")
HOST = os.environ.get("HOST", "0.0.0.0")


def get_pid():
    if PID_FILE.exists():
        try:
            return int(PID_FILE.read_text().strip())
        except ValueError:
            PID_FILE.unlink()
    return None


def is_running():
    pid = get_pid()
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        PID_FILE.unlink()
        return False


def stop():
    pid = get_pid()
    if pid is None:
        print("服务未运行。")
        return True
    try:
        os.kill(pid, signal.SIGTERM)
        PID_FILE.unlink()
        print(f"服务已停止 (pid={pid})。")
        return True
    except ProcessLookupError:
        PID_FILE.unlink()
        print("进程已退出，已清理。")
        return True
    except PermissionError:
        print(f"权限不足，无法终止 pid={pid}。")
        return False


def start():
    if is_running():
        pid = get_pid()
        print(f"服务已在运行中 (pid={pid})。")
        print(f"  前端:  http://localhost:{PORT}/static/finance.html")
        print(f"  API文档: http://localhost:{PORT}/docs")
        return

    python = sys.executable
    cmd = [python, "-m", "uvicorn", "app.main:app", "--host", HOST, "--port", PORT]
    print(f"正在启动财智管家...")
    print(f"  前端:  http://localhost:{PORT}/static/finance.html")
    print(f"  API文档: http://localhost:{PORT}/docs")
    print()

    proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    PID_FILE.write_text(str(proc.pid))
    print(f"服务已启动 (pid={proc.pid})。")


def restart():
    print("正在重启服务...")
    stop()
    start()


def status():
    if is_running():
        pid = get_pid()
        print(f"服务运行中 (pid={pid})")
        print(f"  前端:  http://localhost:{PORT}/static/finance.html")
        print(f"  API文档: http://localhost:{PORT}/docs")
    else:
        print("服务未运行。")


if __name__ == "__main__":
    os.chdir(str(ROOT))
    parser = argparse.ArgumentParser(description="财智管家 服务管理")
    parser.add_argument("action", nargs="?", default="start",
                        choices=["start", "stop", "restart", "status"],
                        help="start(启动) / stop(停止) / restart(重启) / status(状态)")
    args = parser.parse_args()

    actions = {"start": start, "stop": stop, "restart": restart, "status": status}
    actions[args.action]()
