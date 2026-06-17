# Brand Listener Docker 部署改造总结

## 📋 改造概览

本次改造将 Brand Listener 项目从本地开发环境改造为 **可在 Linux 服务器上通过 Docker 直接部署**的形式。不需要在本机执行 `docker build`，所有 Docker 镜像构建都在服务器上进行。

---

## ✅ 已完成的改造

### 1. 修改项目代码

#### **文件：server.py**

**修改内容：**
- 第 19-26 行：新增环境变量支持
  - 从 `DATA_DIR` 环境变量读取数据目录（默认 `/app/data`）
  - 从 `LOG_DIR` 环境变量读取日志目录（默认 `/app/logs`）
  - 启动时自动创建目录

**修改前：**
```python
_root = Path(__file__).parent
sys.path.insert(0, str(_root))
```

**修改后：**
```python
_root = Path(__file__).parent
sys.path.insert(0, str(_root))

# 从环境变量读取数据和日志目录，支持容器部署
_DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
_LOG_DIR = Path(os.getenv("LOG_DIR", "/app/logs"))
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_LOG_DIR.mkdir(parents=True, exist_ok=True)
```

- 第 587-593 行：更新数据路径定义
  - `exports_dir` 从 `_root / "data" / "exports"` → `_DATA_DIR / "exports"`
  - `FOLO_DIR` 改为从环境变量读取，默认 `D:/wmz/FOLO`
  - `_RESULT_CACHE_PATH` 从 `_root / "data"` → `_DATA_DIR`
  - `_STORE_PATH` 从 `_root / "data"` → `_DATA_DIR`

**修改前：**
```python
exports_dir = _root / "data" / "exports"
FOLO_DIR = Path("D:/wmz/FOLO")
_RESULT_CACHE_PATH = _root / "data" / "latest_result.json"
_STORE_PATH = _root / "data" / "entries_store.json"
```

**修改后：**
```python
exports_dir = _DATA_DIR / "exports"
FOLO_DIR = Path(os.getenv("FOLO_DIR", "D:/wmz/FOLO"))
_RESULT_CACHE_PATH = _DATA_DIR / "latest_result.json"
_STORE_PATH = _DATA_DIR / "entries_store.json"
```

#### **文件：src/utils/config.py**

**修改内容：**
- 第 62-63 行：`FOLO_EXPORT_PATH` 默认改为从 `DATA_DIR` 环境变量组成
- 第 72-74 行：
  - `API_HOST` 默认改为 `0.0.0.0`（之前为默认值，现在显式配置）
  - `API_RELOAD` 在 Docker 环境默认改为 `False`（避免热重载导致频繁重启）
- 第 77-78 行：`LOG_FILE` 默认改为从 `LOG_DIR` 环境变量组成
- 新增 79-81 行：定义 `DATA_DIR` 和 `LOG_DIR` 变量

**修改前：**
```python
FOLO_EXPORT_PATH = get_env_var("FOLO_EXPORT_PATH", "./data/exports")
API_HOST = get_env_var("API_HOST", "0.0.0.0")
API_PORT = get_env_int("API_PORT", 8000)
API_RELOAD = get_env_bool("API_RELOAD", True)
LOG_FILE = get_env_var("LOG_FILE", "./logs/brand_listener.log")
```

**修改后：**
```python
FOLO_EXPORT_PATH = get_env_var("FOLO_EXPORT_PATH", os.getenv("DATA_DIR", "/app/data") + "/exports")
API_HOST = get_env_var("API_HOST", "0.0.0.0")
API_PORT = get_env_int("API_PORT", 8000)
API_RELOAD = get_env_bool("API_RELOAD", False)
LOG_FILE = get_env_var("LOG_FILE", os.getenv("LOG_DIR", "/app/logs") + "/brand_listener.log")

# Data and Log Directories
DATA_DIR = get_env_var("DATA_DIR", "/app/data")
LOG_DIR = get_env_var("LOG_DIR", "/app/logs")
```

---

### 2. 创建 Docker 配置文件

#### **文件：Dockerfile**

新建文件，基于 Python 3.11-slim 镜像，包含：
- 安装系统依赖（gcc, g++, make, curl）
- 复制并安装 Python 依赖（requirements.txt）
- 复制应用代码
- 创建数据和日志目录
- 设置环境变量默认值
- 暴露 8000 端口
- 启动命令：`python server.py`

#### **文件：docker-compose.yml**

新建文件，定义 `competitor` 服务：
- 容器名：`competitor`
- 端口映射：`8000:8000`
- 环境变量：从 `.env` 文件读取
- 数据卷挂载：
  - `/srv/competitor/data:/app/data`
  - `/srv/competitor/logs:/app/logs`
- 重启策略：`unless-stopped`

#### **文件：.dockerignore**

新建文件，排除不需要复制到镜像的文件：
- `.git`, `__pycache__`, `*.pyc`
- `data`, `logs`, `*.log`
- `node_modules`, `dist`, `build`
- `.env`, `.vscode`, `.idea` 等开发文件

---

### 3. 创建配置示例文件

#### **文件：.env.example**

新建文件，提供环境变量模板，包含：
- API 配置（PORT, API_HOST, API_PORT, API_RELOAD）
- 数据和日志目录（DATA_DIR, LOG_DIR）
- 日志级别（LOG_LEVEL）
- FOLO 配置（导出路径、轮询间隔）
- XHS API 配置（Token, Cookie, 监听目标, 搜索关键词）
- OCR 配置

**关键特性：**
- 不包含任何真实的敏感信息
- 包含详细的注释说明
- 所有配置都有默认值

---

### 4. 创建部署文档

#### **文件：SERVER_DEPLOY.md**

新建完整的部署指南（约 400 行），包含：

1. **前置条件**
   - Docker 和 Docker Compose 安装步骤（Ubuntu/Debian）

2. **部署步骤（7 个）**
   - 准备服务器目录
   - 上传代码到服务器
   - 配置 .env 文件
   - 构建镜像并启动容器
   - 验证服务可访问
   - 查看日志
   - 验证数据持久化

3. **常用操作**
   - 重启服务
   - 停止服务
   - 查看日志
   - 进入容器调试
   - 更新代码后重新部署

4. **网络访问**
   - 访问路径（前端、API 文档）
   - 反向代理配置示例（Nginx）

5. **故障排查**
   - 容器无法启动
   - 无法连接
   - 权限问题
   - 磁盘空间不足

6. **定期维护**
   - 数据备份
   - 日志备份
   - 容器监控
   - 镜像更新

7. **监控和告警**
   - 简单的监控脚本示例
   - 定时任务配置

8. **常见配置场景**
   - 启用 OCR
   - 监听多个小红书账号
   - 自定义数据保留策略

9. **安全建议**
   - .env 文件安全
   - 防火墙配置
   - 日志和数据安全
   - 容器镜像安全

---

## 📦 需要上传到服务器的文件

```
Brand Listener/
├── Dockerfile                  [新建]
├── docker-compose.yml          [新建]
├── .dockerignore               [新建]
├── .env.example                [新建]
├── SERVER_DEPLOY.md            [新建]
├── server.py                   [修改]
├── requirements.txt            [保持不变]
├── src/
│   └── utils/
│       └── config.py           [修改]
├── frontend/                   [保持不变]
├── langgraph/                  [保持不变]
├── agents/                     [保持不变]
└── [其他源代码文件]            [保持不变]
```

**简单方法（推荐）：**
```bash
# 在本机执行（Git Bash 或 WSL）
cd d:\wmz\Brand Listener
rsync -avz --exclude='.git' --exclude='__pycache__' \
  --exclude='*.pyc' --exclude='data' --exclude='logs' \
  "Brand Listener/" user@server_ip:/srv/competitor/code/
```

---

## 🚀 服务器上需要执行的命令

### 初次部署

```bash
# 1. 连接服务器
ssh user@server_ip

# 2. 创建目录
sudo mkdir -p /srv/competitor/{data,logs}
sudo chown -R $(whoami):$(whoami) /srv/competitor
chmod -R 755 /srv/competitor

# 3. 进入项目目录
cd /srv/competitor/code

# 4. 创建 .env 文件（从 .env.example 复制，然后编辑）
cp .env.example .env
nano .env  # 填入真实的 API Token 和 Cookie

# 5. 构建镜像并启动
docker-compose up -d --build

# 6. 查看启动日志
docker-compose logs -f competitor

# 7. 验证服务
curl http://localhost:8000/competitor
```

### 日常操作

```bash
# 查看日志
docker-compose logs -f competitor

# 重启服务
docker-compose restart competitor

# 停止服务
docker-compose down

# 查看容器状态
docker-compose ps

# 进入容器调试
docker-compose exec competitor bash
```

---

## 🔧 技术细节

### 环境变量配置

| 环境变量 | 默认值 | 用途 |
|---------|-------|------|
| `PORT` | 8000 | 服务端口 |
| `DATA_DIR` | /app/data | 数据存储目录 |
| `LOG_DIR` | /app/logs | 日志存储目录 |
| `API_HOST` | 0.0.0.0 | 监听地址（0.0.0.0 支持外部访问） |
| `API_PORT` | 8000 | API 服务端口 |
| `API_RELOAD` | False | 热重载（Docker 关闭，本地开发打开） |
| `LOG_LEVEL` | INFO | 日志级别 |
| `XHS_API_TOKEN` | - | 小红书 API Token |
| `XHS_COOKIES` | - | 小红书 Cookie |

### 数据持久化

- 所有应用数据保存在 `/srv/competitor/data`
- 宿主机目录通过 Docker Volume 挂载到容器内 `/app/data`
- 容器重启或销毁后，数据不会丢失

### 日志输出

- 日志同时写入：
  - 文件：`/srv/competitor/logs/brand_listener.log`
  - 控制台：`docker-compose logs` 可查看

---

## ✨ 改造的好处

1. **环境一致性**
   - 开发、测试、生产环境完全一致
   - 无需在服务器上配置 Python 环境

2. **快速部署**
   - 只需上传代码和配置文件
   - 服务器上执行 3 条命令即可启动

3. **容易扩展**
   - 可以轻松添加其他服务（数据库、Redis 等）
   - 支持 Kubernetes 部署

4. **自动重启**
   - 容器崩溃自动重启（restart: unless-stopped）
   - 服务器重启后自动恢复

5. **隔离和安全**
   - 应用隔离在容器内，不影响服务器其他服务
   - 敏感信息存储在 .env，不进入镜像

---

## ⚠️ 注意事项

1. **.env 文件安全**
   - 不要将 .env 提交到 Git
   - 在 `.gitignore` 中添加：`/.env`
   - 真实 Token 和 Cookie 只保存在服务器上

2. **首次启动耗时**
   - 首次执行 `docker-compose up -d --build` 需要 5-15 分钟
   - 期间会下载基础镜像、安装依赖、构建镜像

3. **磁盘空间**
   - Docker 镜像约 1-2 GB
   - 数据目录会随时间增长
   - 建议定期备份和清理日志

4. **FOLO 目录**
   - 如果需要本地 FOLO 文件，需要通过 `FOLO_DIR` 环境变量指向宿主机目录
   - 或使用挂载卷添加到 docker-compose.yml

---

## 📄 文件修改清单

| 文件 | 类型 | 修改内容 |
|------|------|--------|
| server.py | 修改 | 添加 DATA_DIR/LOG_DIR 环境变量，更新数据路径定义 |
| src/utils/config.py | 修改 | 添加 DATA_DIR/LOG_DIR 环境变量支持，改 API_RELOAD 默认值 |
| Dockerfile | 新建 | Python 3.11 镜像，安装依赖，启动应用 |
| docker-compose.yml | 新建 | 定义 competitor 服务，配置卷和环境变量 |
| .dockerignore | 新建 | 排除不需要的文件 |
| .env.example | 新建 | 环境变量模板 |
| SERVER_DEPLOY.md | 新建 | 部署文档 |

**未修改的文件：**
- requirements.txt（保持不变）
- 所有业务逻辑代码（前端、Agent、pipeline 等）
- 路由和访问路径（仍然是 /competitor）

---

## ✅ 验证清单

部署后请逐项验证：

- [ ] 容器成功启动（`docker-compose ps` 显示 Up）
- [ ] 能访问前端（`http://server_ip:8000/competitor`）
- [ ] 能查看日志（`docker-compose logs competitor`）
- [ ] 数据保存正确（`/srv/competitor/data` 中有文件）
- [ ] API 文档可访问（`http://server_ip:8000/docs`）
- [ ] 容器重启后数据不丢失
- [ ] 环境变量正确读取（查看启动日志）
- [ ] 性能和内存占用正常（`docker stats competitor`）

---

## 🎯 后续优化建议

1. **监控告警**
   - 添加 Prometheus + Grafana 监控
   - 配置容器崩溃告警

2. **日志管理**
   - 定期轮转日志文件
   - 使用 ELK Stack 集中管理日志

3. **性能优化**
   - 使用 Gunicorn + uvicorn 提高并发
   - 添加负载均衡器

4. **自动化**
   - GitHub Actions 自动构建镜像
   - 自动化部署流水线

5. **备份**
   - 定期备份数据目录
   - 数据库备份策略

---

**改造完成！现在可以将项目部署到任何 Linux 服务器上了。**
