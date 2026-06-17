# 使用官方 Python 镜像作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制 requirements.txt
COPY requirements.txt /app/

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . /app/

# 创建数据和日志目录
RUN mkdir -p /app/data /app/logs

# 设置环境变量默认值
ENV PORT=8000 \
    DATA_DIR=/app/data \
    LOG_DIR=/app/logs \
    API_HOST=0.0.0.0 \
    API_PORT=8000 \
    API_RELOAD=False \
    LOG_LEVEL=INFO

# 暴露端口
EXPOSE 8000

# 启动应用
CMD ["python", "server.py"]
