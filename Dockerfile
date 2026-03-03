# 使用官方的 Python 3.9 精简版镜像作为基础
FROM python:3.9-slim

# 设置工作目录为 /app
WORKDIR /app

# 复制依赖文件到容器中
COPY requirements.txt .

# 安装 Python 依赖
# --no-cache-dir 选项可以减小最终镜像的体积
RUN pip install --no-cache-dir -r requirements.txt

# 将项目的所有文件复制到容器的 /app 目录
COPY . .

# 暴露应用运行的端口 (根据您的 uvicorn 命令调整，通常是 8000)
EXPOSE 8000

# 定义容器启动时执行的命令
# 请确保 'main:app' 与您项目中启动 FastAPI 的命令一致
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
