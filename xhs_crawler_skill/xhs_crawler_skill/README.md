# 小红书爬虫技能使用指南

**版本**: 2.6.0  
**更新时间**: 2026-04-13  
**API 服务**: Proxy API  
**自动升级**: ✅ 已启用

## 🆕 版本 2.6.0 新特性

**核心改进**:
- ✅ **笔记详情链接修复**：完整提取带 xsec_token 的笔记链接，可直接访问
- ✅ **数据结构解析优化**：正确处理 note_list 嵌套结构
- ✅ **URL 解码处理**：先解码再提取 xsec_token，确保链接完整可用
- ✅ **双源 token 提取**：优先从 mini_program_info，降级从 qq_mini_program_info 获取

**修复问题**:
- 🐛 修复笔记链接缺少 xsec_token 导致无法访问的问题
- 🐛 修复 API 数据结构变化导致解析失败的问题

**链接格式**:
```
https://www.xiaohongshu.com/explore/笔记 ID?xsec_token=xxxxx
```

## 🆕 版本 2.5.0 新特性

**核心改进**:
- ✅ **修复 API 响应处理**：支持嵌套的 code/data 结构（外层 200，内层 0）
- ✅ **评论采集优化**：完整采集主评论和子评论，确保数量与 API 参考一致
- ✅ **短链转化修复**：正确处理 API 嵌套响应，提取笔记 ID 更准确
- ✅ **错误处理增强**：优化 301、429 等错误码的重试机制
- ✅ **Excel 导出优化**：所有功能默认导出 Excel，包含完整数据验证

**工作流程固定**:
- ✅ AI 自动调用 CLI 脚本执行任务
- ✅ 所有功能必须导出 Excel 表格
- ✅ 必须返回 JSON 响应结果
- ✅ 不生成测试/总结文档
- ✅ 执行后自动清理临时文件

## 📁 Excel 导出位置说明

**所有功能导出的 Excel 表格默认保存到技能根目录**：

```
d:\Openclaw_skill\.trae\skills\xhs_crawler_skill\
├── search_关键词_排序方式.xlsx    # 搜索笔记导出
├── note_笔记 ID_detail.xlsx       # 笔记详情导出
├── comments_笔记 ID.xlsx          # 评论采集导出
├── user_notes_用户 ID.xlsx        # 用户笔记导出
└── all_comments_笔记 ID.xlsx      # 全部评论（含子评论）导出
```

**自定义输出路径**：
- 所有 CLI 工具支持 `-o` 或 `--output` 参数指定输出路径
- 不指定 `-o` 参数时，自动保存到技能根目录
- 支持相对路径和绝对路径

## 🚀 快速开始

### 第一步：安装依赖

```bash
pip install -r requirements.txt
```

### 第二步：获取并配置 API Token

**获取 API Token：**
- **微信联系：Tin240421**（推荐，获取 API Key + 使用指导）
- 或访问 AI 牛马平台注册账号并创建应用

**配置 Token：**
```bash
# 复制配置示例
cp .env.example .env

# 编辑 .env 文件，填入你的 API Token
XHS_API_TOKEN=sk-your-token-here
```

### 第三步：使用 CLI 工具

```bash
# 笔记搜索
python cli_search.py -k "Python 编程"

# 笔记详情
python cli_detail.py -n 69c260a90000000021010226

# 评论采集（含子评论）
python cli_comments.py -n 69c260a90000000021010226 --all --sub-comments -o comments.xlsx

# 用户笔记
python cli_user_notes.py -u 5b83d9b2bced640001784c33 --all

# 分享链接转化
python cli_share_link.py -u "https://www.xiaohongshu.com/explore/xxx"
```

## 📋 CLI 命令详解

### 1. 笔记搜索 (cli_search.py)

```bash
python cli_search.py -k "关键词" [选项]

选项:
  -p, --page        页码 (默认：1)
  -s, --sort        排序方式 (general, popularity_descending, time_descending, ...)
  -t, --type        笔记类型 (_0:通用，_1:视频，_2:普通)
  --time            时间范围 (一天内，一周内，半年内)
  -o, --output      输出文件路径 (JSON 格式)
```

### 2. 笔记详情 (cli_detail.py)

```bash
python cli_detail.py -n 笔记 ID [选项]

选项:
  -o, --output      输出文件路径 (JSON 格式)
```

### 3. 评论采集 (cli_comments.py)

```bash
python cli_comments.py -n 笔记 ID [选项]

选项:
  --all             采集所有评论（自动分页）
  --pages           最大页数
  --sort            排序方式 (latest, normal)
  --sub-comments    采集子评论（回复）
  --delay           主评论分页延迟（秒，默认：2.0）
  --sub-delay       子评论采集延迟（秒，默认：1.0）
  -o, --output      输出文件路径 (Excel 格式)
```

### 4. 用户笔记 (cli_user_notes.py)

```bash
python cli_user_notes.py -u 用户 ID [选项]

选项:
  --all             采集所有笔记（自动分页）
  --pages           最大页数
  --delay           每页延迟时间（秒，默认：1.0）
  -o, --output      输出文件路径 (JSON 格式)
```

### 5. 分享链接转化 (cli_share_link.py)

```bash
python cli_share_link.py -u "分享链接"

功能:
  - 将分享短链接转换为标准笔记链接
  - 自动提取笔记 ID
  - 可直接用于评论采集和详情采集
```

## 📁 文件说明

### 核心脚本
- `cli_search.py` - 笔记搜索 CLI 工具
- `cli_user_notes.py` - 用户笔记采集 CLI 工具
- `cli_detail.py` - 笔记详情采集 CLI 工具
- `cli_comments.py` - 评论采集 CLI 工具
- `cli_share_link.py` - 分享链接转化 CLI 工具

### 核心类库
- `note_search.py` - 笔记搜索核心类
- `user_notes.py` - 用户笔记采集核心类
- `note_detail.py` - 笔记详情采集核心类
- `note_comments.py` - 评论采集核心类
- `share_link_convert.py` - 分享链接转化核心类

### 配置文件
- `.env.example` - 环境变量配置示例
- `requirements.txt` - Python 依赖包

### 文档
- `README.md` - 本使用指南
- `SKILL.md` - 技能说明文档
- `GETTING_STARTED.md` - 新用户入门指南

## ⚠️ 注意事项

1. **API 配额**: 每次请求都会消耗 API 配额，请合理使用
2. **速率限制**: 建议请求间隔至少 2 秒，避免触发 429 限流
3. **超时设置**: 默认超时 60 秒，复杂搜索可能更慢
4. **合法使用**: 请遵守相关法律法规和平台服务条款
5. **隐私保护**: 不要收集和使用用户隐私信息

## ❓ 常见问题

**Q: 返回 401 错误？**  
A: Token 无效或已过期，请检查并更新 Token

**Q: 返回 429 错误？**  
A: 超出速率限制，请增加延迟时间（--delay 参数）

**Q: 如何获取用户 ID？**  
A: 从用户主页 URL 获取，格式如：`5b83d9b2bced640001784c33`

**Q: 如何获取笔记 ID？**  
A: 从笔记分享链接提取，或使用 `cli_share_link.py` 转换获取

## 📚 更多资源

- 详细技能说明：[SKILL.md](SKILL.md)
- 新用户入门：[GETTING_STARTED.md](GETTING_STARTED.md)
