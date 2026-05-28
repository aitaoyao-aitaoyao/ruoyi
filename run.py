#!/usr/bin/env python3
"""
LightPress CMS — 一键启动/停止脚本

启动:
    python run.py

停止:
    python run.py --stop

访问地址:
    接口文档:        http://127.0.0.1:8000/docs
    管理界面:        http://127.0.0.1:8000/static/index.html
    种子数据(demo):  python seed_data.py --reset
"""
import os
import sys
import signal
import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PID_FILE = ROOT / ".lightpress.pid"  # PID 文件用于判断服务是否在运行


def get_pid():
    """读取 PID 文件，获取正在运行的服务进程 ID。无文件时返回 None。"""
    if PID_FILE.exists():
        return int(PID_FILE.read_text().strip())
    return None


def stop():
    """停止正在运行的 LightPress 服务。

    通过 PID 文件找到进程，发送 SIGTERM 信号优雅终止，然后清理 PID 文件。
    如果进程已经不存在（比如手动 kill 过），只清理残留的 PID 文件。
    """
    pid = get_pid()
    if pid is None:
        print("未找到正在运行的 LightPress 进程（不存在 .lightpress.pid 文件）。")
        return
    try:
        os.kill(pid, signal.SIGTERM)
        PID_FILE.unlink()
        print(f"LightPress (pid={pid}) 已停止。")
    except ProcessLookupError:
        PID_FILE.unlink()
        print("LightPress 进程已退出，已清理残留的 PID 文件。")
    except PermissionError:
        print(f"无法终止进程 pid={pid}：权限不足。")


def start():
    """启动 LightPress 服务。

    使用 subprocess.Popen 后台启动 uvicorn，记录 PID 以便后续停止。
    如果已有实例在运行，不重复启动，直接提示访问地址。
    按 Ctrl+C 可关闭服务。
    """
    pid = get_pid()
    if pid is not None:
        try:
            # 发送信号 0（空信号）来检测进程是否存活
            os.kill(pid, 0)
            print(f"LightPress 已在运行中 (pid={pid})。")
            print(f"  接口文档:  http://127.0.0.1:{port}/docs")
            print(f"  管理界面:  http://127.0.0.1:{port}/static/index.html")
            return
        except ProcessLookupError:
            # PID 文件存在但进程已死，清理旧文件后继续启动
            PID_FILE.unlink()

    python = sys.executable
    port = os.environ.get("PORT", "8000")
    cmd = [python, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", port]
    print("正在启动 LightPress CMS...")
    print(f"  接口文档:  http://127.0.0.1:{port}/docs")
    print(f"  管理界面:  http://127.0.0.1:{port}/static/index.html")
    print("按 Ctrl+C 停止服务。\n")

    # 后台启动 uvicorn 进程，不等待其完成
    proc = subprocess.Popen(cmd, cwd=str(ROOT))
    PID_FILE.write_text(str(proc.pid))

    try:
        proc.wait()  # 阻塞等待直到进程退出
    except KeyboardInterrupt:
        print("\n正在停止...")
        proc.terminate()
        proc.wait()
    finally:
        if PID_FILE.exists():
            PID_FILE.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LightPress CMS 启动/停止管理工具")
    parser.add_argument("--stop", action="store_true", help="停止正在运行的服务")
    args = parser.parse_args()

    os.chdir(str(ROOT))
    if args.stop:
        stop()
    else:
        start()
