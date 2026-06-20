#!/usr/bin/env python3
"""财智管家 — 启动/停止/重启 + 数据库同步脚本

用法:
    python run.py start              启动服务
    python run.py stop               停止服务
    python run.py restart            重启服务
    python run.py status             查看状态
    python run.py sync-push          上传本地数据库到服务器
    python run.py sync-pull          从服务器下载数据库到本地

同步前请先停止服务(stop)，避免数据损坏。
服务器地址在脚本中配置 SERVER 变量。
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
# TODO: 改为你的服务器地址，格式 user@ip:path
SERVER = os.environ.get("SERVER", "root@你的服务器IP:/opt/caizhiguanjia")


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


def sync_push():
    """上传本地 app.db 到服务器"""
    if is_running():
        print("⚠ 请先停止服务: python run.py stop")
        return
    local_db = ROOT / "app.db"
    if not local_db.exists():
        print("本地 app.db 不存在。")
        return
    print(f"上传 {local_db} → {SERVER}/app.db")
    subprocess.run(["scp", str(local_db), f"{SERVER}/app.db"])


def sync_pull():
    """从服务器下载 app.db 到本地"""
    if is_running():
        print("⚠ 请先停止服务: python run.py stop")
        return
    print(f"下载 {SERVER}/app.db → {ROOT}/app.db")
    subprocess.run(["scp", f"{SERVER}/app.db", str(ROOT / "app.db")])


if __name__ == "__main__":
    os.chdir(str(ROOT))
    parser = argparse.ArgumentParser(description="财智管家 服务管理")
    parser.add_argument("action", nargs="?", default="start",
                        choices=["start", "stop", "restart", "status", "sync-push", "sync-pull"],
                        help="start(启动) / stop(停止) / restart(重启) / status(状态) / sync-push(上传DB) / sync-pull(下载DB)")
    args = parser.parse_args()

    actions = {"start": start, "stop": stop, "restart": restart, "status": status,
               "sync-push": sync_push, "sync-pull": sync_pull}
    actions[args.action]()
