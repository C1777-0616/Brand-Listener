# Brand Listener Docker 部署指南

## 前置条件

在 Linux 服务器上需要安装：
- Docker
- Docker Compose

### 安装 Docker（Ubuntu/Debian）

```bash
# 更新包管理器
sudo apt-get update
sudo apt-get install -y docker.io docker-compose

# 启动 Docker 服务
sudo systemctl start docker
sudo systemctl enable docker

# 验证安装
docker --version
docker-compose --version
```

---

## 部署步骤

### 1. 准备服务器目录

在服务器上创建项目目录和数据目录：

```bash
# 创建主目录
sudo mkdir -p /srv/competitor
sudo mkdir -p /srv/competitor/data
sudo mkdir -p /srv/competitor/logs

# 设置权限（让当前用户可写）
sudo chown -R $(whoami):$(whoami) /srv/competitor
chmod -R 755 /srv/competitor
```

### 2. 上传代码到服务器

在本机上执行以下命令，将项目上传到服务器：

```bash
# 从 Windows 本机（使用 Git Bash 或 WSL）
scp -r "Brand Listener" user@server_ip:/srv/competitor/code

# 或使用 rsync（更快，可续传）
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='data' --exclude='logs' \
  "Brand Listener/" user@server_ip:/srv/competitor/code/
```

**预期结构：**
```
/srv/competitor/
├── code/                 # 项目代码
│   ├── server.py
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── requirements.txt
│   ├── .env.example
│   ├── src/
│   └── ...
├── data/                 # 容器内数据目录（由 Docker volume 挂载）
└── logs/                 # 容器内日志目录（由 Docker volume 挂载）
```

### 3. 配置 .env 文件

在服务器上创建 `.env` 文件：

```bash
cd /srv/competitor/code
cp .env.example .env
```

编辑 `.env` 文件，填入真实配置：

```bash
nano .env
```

**需要配置的关键项：**

```env
# API 配置
PORT=8000
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=False

# 数据目录
DATA_DIR=/app/data
LOG_DIR=/app/logs

# XHS API Token（从小红书 API 服务商获取）
XHS_API_TOKEN=your_real_token_here

# XHS Cookie（可选，用于 OCR）
XHS_COOKIES=your_real_cookies_here

# 监听的小红书账号或搜索关键词
XHS_MONITOR_TARGETS=["account1", "account2"]
XHS_SEARCH_KEYWORDS=["牙膏", "电动牙刷"]
```

### 4. 构建镜像并启动容器

在 `/srv/competitor/code` 目录下执行：

```bash
# 构建 Docker 镜像（首次执行）
docker-compose build

# 启动服务（后台运行）
docker-compose up -d --build

# 验证容器启动
docker-compose ps
```

预期输出：
```
NAME        COMMAND              SERVICE     STATUS      PORTS
competitor  python server.py     competitor  Up 10s      0.0.0.0:8000->8000/tcp
```

---

## 访问和验证

### 5. 验证服务可访问

```bash
# 在服务器上本地测试
curl http://localhost:8000/competitor

# 从其他机器测试（用服务器 IP 替换 server_ip）
curl http://server_ip:8000/competitor
```

预期返回 HTML 页面（不是错误）。

### 6. 查看日志

```bash
# 实时查看日志
docker-compose logs -f competitor

# 查看指定行数的日志
docker-compose logs --tail=100 competitor

# 查看本地日志文件
tail -f /srv/competitor/logs/brand_listener.log
```

### 7. 验证数据持久化

```bash
# 检查数据目录
ls -la /srv/competitor/data/

# 预期文件：
# - entries_store.json（条目仓库）
# - latest_result.json（最新结果缓存）
# - exports/（导出目录）

# 检查日志目录
ls -la /srv/competitor/logs/
# 预期文件：
# - brand_listener.log
```

---

## 常用操作

### 重启服务

```bash
cd /srv/competitor/code
docker-compose restart competitor
```

### 停止服务

```bash
cd /srv/competitor/code
docker-compose down
```

### 删除所有数据（慎用）

```bash
docker-compose down -v  # 删除容器和 volume
rm -rf /srv/competitor/data/*
```

### 查看容器进程

```bash
docker ps  # 查看运行中的容器
docker-compose ps  # 查看 docker-compose 管理的服务
```

### 进入容器调试

```bash
docker-compose exec competitor bash
# 然后可以执行任何命令，如：
# ls /app/data
# cat /app/logs/brand_listener.log
```

### 更新代码后重新部署

```bash
cd /srv/competitor/code

# 拉取最新代码
git pull  # 如果使用 git，或用 rsync 上传新代码

# 重新构建镜像并启动
docker-compose up -d --build

# 查看日志确保启动成功
docker-compose logs -f competitor
```

---

## 网络访问

### 访问路径

- **前端应用**：`http://server_ip:8000/competitor`
- **API 文档**：`http://server_ip:8000/docs`
- **API 文档（ReDoc）**：`http://server_ip:8000/redoc`

### 配置反向代理（可选）

如果需要通过子域名或特定路径访问，可以配置 Nginx：

```nginx
# /etc/nginx/sites-available/competitor
server {
    listen 80;
    server_name competitor.example.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

启用配置：
```bash
sudo ln -s /etc/nginx/sites-available/competitor /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## 故障排查

### 问题 1：容器无法启动

```bash
# 查看启动错误
docker-compose logs competitor

# 常见原因：
# - Python 依赖缺失：重新运行 docker-compose build
# - 端口被占用：修改 docker-compose.yml 中的 ports
# - 权限问题：检查数据目录权限
```

### 问题 2：无法连接到容器内的应用

```bash
# 确保防火墙开放 8000 端口
sudo ufw allow 8000/tcp

# 检查容器网络
docker network ls
docker network inspect competitor_default
```

### 问题 3：数据目录权限问题

```bash
# 修复权限
sudo chown -R $(whoami):$(whoami) /srv/competitor/data
sudo chown -R $(whoami):$(whoami) /srv/competitor/logs
chmod -R 755 /srv/competitor
```

### 问题 4：磁盘空间不足

```bash
# 清理 Docker 无用镜像和容器
docker system prune -a

# 检查磁盘使用
du -sh /srv/competitor/*
```

---

## 定期维护

### 备份数据

```bash
# 定期备份数据
tar -czf /backup/competitor-data-$(date +%Y%m%d).tar.gz /srv/competitor/data/

# 定期备份日志
tar -czf /backup/competitor-logs-$(date +%Y%m%d).tar.gz /srv/competitor/logs/
```

### 查看容器资源占用

```bash
docker stats competitor
```

### 更新 Docker 镜像

```bash
cd /srv/competitor/code
docker pull python:3.11-slim  # 更新基础镜像
docker-compose build --no-cache  # 重新构建
docker-compose up -d --build  # 重启服务
```

---

## 监控和告警

### 简单的监控脚本

创建 `/srv/competitor/monitor.sh`：

```bash
#!/bin/bash

# 检查服务是否运行
if ! docker-compose -f /srv/competitor/code/docker-compose.yml ps | grep "Up"; then
  echo "Service is down! Attempting to restart..."
  cd /srv/competitor/code
  docker-compose up -d
fi

# 检查数据目录大小
DATA_SIZE=$(du -sh /srv/competitor/data | cut -f1)
echo "Data directory size: $DATA_SIZE"

# 检查日志大小
LOG_SIZE=$(du -sh /srv/competitor/logs | cut -f1)
echo "Logs directory size: $LOG_SIZE"
```

设置定时任务：
```bash
# 每 5 分钟运行一次
*/5 * * * * /srv/competitor/monitor.sh >> /var/log/competitor_monitor.log 2>&1
```

---

## 常见配置场景

### 场景 1：启用 OCR（需要 XHS Cookie）

1. 从浏览器获取 XHS Cookie
2. 设置环境变量：
```env
XHS_COOKIES=bi=xxx; webBd=xxx; ...
OCR_ENABLED=True
```
3. 重启容器

### 场景 2：监听多个小红书账号

```env
XHS_MONITOR_TARGETS=["usmile_official", "colgate_china", "oral_b_china"]
```

### 场景 3：自定义数据保留策略

修改 `server.py` 中的 `_fetch_and_store_comments()` 函数：
- `max_per_run`：每次拉取的最大评论条数
- `max_pages`：每篇帖子最多拉取页数
- `thirty_days_ago`：数据保留期限

---

## 安全建议

1. **.env 文件安全**
   - 不要将 .env 提交到 Git
   - 限制文件权限：`chmod 600 .env`
   - 定期轮换 API Token 和 Cookie

2. **防火墙配置**
   - 只允许必要的端口访问
   - 考虑使用反向代理隐藏内部 IP

3. **日志和数据**
   - 定期备份关键数据
   - 清理敏感信息（如 Cookie、Token）
   - 定期轮换日志文件

4. **容器镜像**
   - 使用官方镜像或信任来源
   - 定期更新基础镜像

---

## 支持和反馈

如有问题，请：

1. 检查日志：`docker-compose logs competitor`
2. 查看本部署指南的故障排查部分
3. 提交 Issue 或联系技术支持
