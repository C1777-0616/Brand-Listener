---
name: "xhs_crawler_skill"
version: "2.6.0"
description: "爬取小红书笔记、用户、评论等数据，支持分享链接转化。Invoke when user wants to crawl Xiaohongshu/RED platform content, notes, user profiles, comments, or convert share links."
auto_upgrade: true
upgrade_url: "http://skills.ainm.store/api/public/skills/xhs_crawler_skill/download"
---

# 小红书爬虫技能 (Xiaohongshu Crawler Skill)

## 🎉 欢迎使用

**版本**: 2.6.0  
**更新时间**: 2026-04-13  
**自动升级**: ✅ 已启用（检测更新源：http://skills.ainm.store/api/public/skills/xhs_crawler_skill/download）

本技能用于从小红书 (Xiaohongshu/RED) 平台爬取各类数据，包括笔记、用户信息、评论等内容，并提供分享链接转化功能。基于 Proxy API 提供稳定的数据采集服务。

**API 服务**: Proxy API  
**Base URL**: `https://proxy-api.ainm.store/p`

---

## 🆕 版本 2.6.0 更新说明

**发布日期**: 2026-04-13

**核心改进**:
- ✅ **笔记详情链接修复**：完整提取带 xsec_token 的笔记链接，可直接访问
- ✅ **数据结构解析优化**：正确处理 note_list 嵌套结构
- ✅ **URL 解码处理**：先解码再提取 xsec_token，确保链接完整可用
- ✅ **双源 token 提取**：优先从 mini_program_info，降级从 qq_mini_program_info 获取

**修复问题**:
- 🐛 修复笔记链接缺少 xsec_token 导致无法访问的问题
- 🐛 修复 API 数据结构变化导致解析失败的问题

---

## 🆕 版本 2.5.0 更新说明

**发布日期**: 2026-04-13

**核心改进**:
- ✅ **修复 API 响应处理**：支持嵌套的 code/data 结构（外层 200，内层 0）
- ✅ **评论采集优化**：完整采集主评论和子评论，确保数量与 API 参考一致
- ✅ **短链转化修复**：正确处理 API 嵌套响应，提取笔记 ID 更准确
- ✅ **错误处理增强**：优化 301、429 等错误码的重试机制
- ✅ **Excel 导出优化**：所有功能默认导出 Excel，包含完整数据验证

**工作流程固定**:
- ✅ AI 自动调用 CLI 脚本执行任务
- ✅ 所有功能必须导出 Excel 表格
- ✅ 返回 JSON 响应结果
- ✅ 不生成测试/总结文档

---

## 🚀 功能清单（安装后必读）

**📌 提示**：以下是技能支持的所有功能，请根据您的需求选择对应功能！

| 序号 | 功能名称 | 功能描述 | 输入参数 | 输出结果 |
|------|---------|---------|---------|---------|
| 1️⃣ | 🔍 **搜索笔记** | 根据关键词搜索小红书笔记 | 关键词、排序方式、时间范围 | 笔记列表 + Excel 表格 |
| 2️⃣ | 📄 **笔记详情** | 获取指定笔记的详细信息 | 笔记 ID 或分享链接 | 笔记详情 + Excel 表格 |
| 3️⃣ | 💬 **评论采集** | 采集笔记的所有评论（含子评论） | 笔记 ID | 主评论 + 子评论 + Excel 表格 |
| 4️⃣ | 👤 **用户笔记** | 采集用户发布的所有笔记 | 用户 ID | 用户笔记列表 + Excel 表格 |
| 5️⃣ | 🔗 **链接转换** | 转换分享短链接为标准链接 | 分享链接 | 标准长链接 + 笔记 ID + Excel 表格 |
| 6️⃣ | 📊 **批量转换** | 批量转换多个分享链接 | URL 文件路径 | 转换结果 + Excel 表格 |

---

## 💬 选择功能后使用（AI 自动执行）

**📝 使用说明**：
1. 从上方功能清单中选择您需要的功能
2. 复制下方对应的 AI 提示词模板
3. 填写参数（替换【】中的内容）
4. 发送给 AI，**自动调用 CLI 脚本执行**

**⚠️ 重要提示 - 固定工作流程**:
- ✅ AI 会直接调用现有的 CLI 脚本（如 `cli_search.py`、`cli_comments.py` 等）
- ✅ **不会创建新的脚本文件**
- ✅ **不会生成测试/总结文档**
- ✅ **必须导出 Excel 表格**（保存到技能根目录）
- ✅ **必须返回 JSON 响应**（完整数据结构）
- ✅ 所有功能执行后自动清理临时文件

### 1️⃣ 搜索笔记

**AI 提示词模板**：
```
帮我搜索小红书笔记，关键词是"【填写关键词，如：Python 教程】"，采集最近半年的数据，排序方式用综合排序，导出 Excel 表格。
```

**输出说明**：
- ✅ **Excel 表格**：保存到技能根目录（`search_关键词_排序方式.xlsx`）
- ✅ **JSON 响应**：包含搜索结果的完整数据结构
- ❌ **不生成**：测试文档、总结文档

---

### 2️⃣ 笔记详情

**AI 提示词模板**：
```
帮我采集小红书笔记详情，笔记 ID 是"【填写笔记 ID，如：69bc8304000000002202b8af】"，导出 Excel 表格，需要包含封面图、标题、内容、点赞数、收藏数、评论数等信息。
```

**输出说明**：
- ✅ **Excel 表格**：保存到技能根目录（`note_笔记 ID_detail.xlsx`）
- ✅ **JSON 响应**：包含笔记详情的完整数据结构
- ❌ **不生成**：测试文档、总结文档

---

### 3️⃣ 评论采集

**AI 提示词模板**：
```
帮我采集小红书笔记的所有评论，笔记 ID 是"【填写笔记 ID】"，需要采集所有主评论和子评论（回复），导出 Excel 表格，标记评论类型（主评论/子评论）。
```

**输出说明**：
- ✅ **Excel 表格**：保存到技能根目录（`comments_笔记 ID.xlsx`）
- ✅ **JSON 响应**：包含评论的完整层级结构
- ❌ **不生成**：测试文档、总结文档

---

### 4️⃣ 用户笔记

**AI 提示词模板**：
```
帮我采集小红书用户的所有笔记，用户 ID 是"【填写用户 ID，如：5b83d9b2bced640001784c33】"，采集所有笔记并导出 Excel 表格。
```

**输出说明**：
- ✅ **Excel 表格**：保存到技能根目录（`user_notes_用户 ID.xlsx`）
- ✅ **JSON 响应**：包含用户笔记的完整列表
- ❌ **不生成**：测试文档、总结文档

---

### 5️⃣ 链接转换

**AI 提示词模板**：
```
帮我转换小红书分享链接为标准链接，链接是"【填写分享链接，如：http://xhslink.com/o/xxx】"，提取笔记 ID 后导出 Excel 表格。
```

**输出说明**：
- ✅ **Excel 表格**：保存到技能根目录（`link_conversion_result.xlsx`）
- ✅ **JSON 响应**：包含转换结果的完整数据
- ❌ **不生成**：测试文档、总结文档

---

### 6️⃣ 批量转换

**AI 提示词模板**：
```
帮我批量转换小红书分享链接，链接文件是"【填写文件路径，如：urls.txt】"，导出 Excel 表格，包含原始链接、转换后链接、笔记 ID、转换状态。
```

**输出说明**：
- ✅ **Excel 表格**：保存到技能根目录（`link_conversion_result.xlsx`）
- ✅ **JSON 响应**：包含批量转换的统计信息（成功数、失败数）
- ❌ **不生成**：测试文档、总结文档

---

## ⚙️ 配置说明

### 获取 API Token
- 微信联系：**Tin240421**
- 或访问 AI 牛马平台注册

### 配置 Token
```bash
# 编辑 .env 文件
XHS_API_TOKEN=sk-your-token-here
```

### 自动升级
- ✅ 已启用自动升级功能
- 📡 检测源：http://skills.ainm.store/api/public/skills/xhs_crawler_skill/download
- 🔄 每次调用时自动检查版本，有新版本自动升级

---

## 🤖 AI 提示词（复制即用）

**💡 提示**：复制以下提示词模板，填入您的参数后发送给 AI，即可快速使用技能！

### 🔍 搜索笔记
```
帮我搜索小红书笔记，关键词是"【填写关键词】"，采集最近半年的数据，排序方式用综合排序，导出 Excel 表格。
```

### 📄 查看笔记详情
```
帮我采集小红书笔记详情，笔记 ID 是"【填写笔记 ID】"，导出 Excel 表格，需要包含封面图、标题、内容、点赞数等信息。
```

### 💬 采集笔记评论
```
帮我采集小红书笔记的所有评论，笔记 ID 是"【填写笔记 ID】"，需要采集所有主评论和子评论（回复），导出 Excel 表格，标记评论类型。
```

### 👤 采集用户笔记
```
帮我采集小红书用户的所有笔记，用户 ID 是"【填写用户 ID】"，采集所有笔记并导出 Excel 表格。
```

### 🔗 转换分享链接
```
帮我转换小红书分享链接为标准链接，链接是"【填写分享链接】"，提取笔记 ID 后导出 Excel 表格。
```

### 📊 批量转换链接
```
帮我批量转换小红书分享链接，链接文件是"【填写文件路径】"，导出 Excel 表格，包含原始链接、转换后链接、笔记 ID。
```

---

## 💡 使用引导（每次使用时阅读）

**📌 重要提示**：每次使用技能前，请先确认您的使用场景，选择对应的功能模块。

### 🎯 第一步：明确您的需求

请根据您的实际需求选择对应功能：

| 需求场景 | 使用功能 | 输入参数 | 输出结果 |
|---------|---------|---------|---------|
| 🔍 **找笔记** | 笔记搜索 | 关键词（如"Python 教程"） | 笔记列表 + Excel |
| 📄 **看详情** | 笔记详情 | 笔记 ID 或分享链接 | 笔记详细信息 + Excel |
| 💬 **采评论** | 评论采集 | 笔记 ID | 主评论 + 子评论 + Excel |
| 👤 **扒博主** | 用户笔记 | 用户 ID | 用户所有笔记 + Excel |
| 🔗 **转链接** | 链接转换 | 分享短链接 | 标准长链接 + 笔记 ID + Excel |

### 🚀 第二步：选择使用方式

**推荐新手使用 CLI 工具**，简单快捷，无需编写代码！

#### 方式 1：CLI 工具（推荐）

```bash
# 所有 CLI 工具都支持 --help 查看帮助
python cli_功能名.py --help
```

**快速命令参考**：
```bash
# 1. 搜索笔记
python cli_search.py -k "关键词" -t YOUR_TOKEN

# 2. 采集笔记详情
python cli_detail.py -n 笔记 ID -t YOUR_TOKEN

# 3. 采集评论（含子评论）
python cli_comments.py -n 笔记 ID -t YOUR_TOKEN --all --sub-comments

# 4. 采集用户笔记
python cli_user_notes.py -u 用户 ID -t YOUR_TOKEN --all

# 5. 转换分享链接
python cli_share_link.py -u "分享链接" -t YOUR_TOKEN

# 6. 批量转换链接（从文件读取）
python cli_share_link.py -f urls.txt -t YOUR_TOKEN -o result.xlsx
```

#### 方式 2：Python 代码（灵活定制）

```python
# 示例：搜索笔记并导出 Excel
from note_search import XHSNoteSearch

# 初始化
searcher = XHSNoteSearch(api_token="your_token")

# 搜索
result = searcher.search(keyword="Python 编程")

# 导出 Excel
searcher.export_to_excel(result, "search_result.xlsx")
```

### 📝 第三步：准备必要参数

**必须准备的参数**：
1. ✅ **API Token** - 从微信（Tin240421）获取
2. ✅ **功能参数** - 根据选择的功能准备：
   - 搜索：关键词
   - 详情：笔记 ID
   - 评论：笔记 ID
   - 用户：用户 ID
   - 转换：分享链接

**可选参数**：
- `-o` 或 `--output` - 指定输出文件路径
- `--all` - 采集所有数据（自动分页）
- `--sub-comments` - 采集子评论
- `--delay` - 设置请求延迟（避免触发限流）

### 📂 第四步：查看输出结果

**Excel 文件默认保存位置**：
```
d:\Openclaw_skill\.trae\skills\xhs_crawler_skill\
├── search_关键词_排序方式.xlsx    # 搜索笔记
├── note_笔记 ID_detail.xlsx       # 笔记详情
├── comments_笔记 ID.xlsx          # 评论数据
├── user_notes_用户 ID.xlsx        # 用户笔记
└── link_conversion_result.xlsx    # 链接转换
```

**Excel 表格特性**：
- ✅ 自动列宽自适应
- ✅ 长文本自动换行
- ✅ 状态标记（成功=绿色，失败=红色）
- ✅ 数据类型标记（主评论/子评论）

### ⚠️ 常见问题

**Q1: 如何获取 API Token？**
- 微信联系：**Tin240421**
- 或访问 AI 牛马平台注册

**Q2: 如何查看命令帮助？**
```bash
python cli_search.py --help
```

**Q3: Excel 文件在哪里？**
- 默认保存到技能根目录
- 可用 `-o 自定义路径.xlsx` 指定位置

**Q4: 如何批量处理？**
- 搜索：自动分页采集
- 链接转换：使用 `-f urls.txt` 从文件读取

**Q5: 触发限流怎么办？**
- 增加 `--delay` 参数（如 `--delay 3.0`）
- 减少单次采集数量

## 🚀 快速上手（3 分钟开始使用）

### 第一步：配置 API Token

```bash
# 1. 创建 .env 文件（如果不存在）
cp .env.example .env

# 2. 编辑 .env 文件，填入您的 API Token
# XHS_API_TOKEN=sk-your-token-here
```

**如何获取 API Token？**

**方式 1：微信联系（推荐）**
- 微信号：**Tin240421**
- 添加微信获取 API Key 和使用指导

**方式 2：AI 牛马平台**
- 访问 AI 牛马平台注册账号
- 创建应用并获取 API Token

### 第二步：选择使用方式

**方式 1：使用 CLI 工具（推荐，简单快捷）**

```bash
# 搜索笔记
python cli_search.py -k "Python 编程" -t YOUR_TOKEN

# 采集笔记详情
python cli_detail.py -n 69bc8304000000002202b8af -t YOUR_TOKEN

# 采集评论（含子评论）
python cli_comments.py -n 69bc8304000000002202b8af -t YOUR_TOKEN --all --sub-comments

# 采集用户笔记
python cli_user_notes.py -u 5b83d9b2bced640001784c33 -t YOUR_TOKEN --all

# 转换分享链接
python cli_share_link.py -u "https://www.xiaohongshu.com/explore/xxx" -t YOUR_TOKEN
```

**方式 2：使用 Python 代码（灵活定制）**

```python
from note_search import XHSNoteSearch

# 初始化
searcher = XHSNoteSearch(api_token="your_token")

# 搜索笔记
result = searcher.search(keyword="Python 编程")
print(searcher.format_results(result))

# 导出 Excel
searcher.export_to_excel(result, "search_result.xlsx")
```

### 第三步：查看帮助

```bash
# 查看所有 CLI 命令
python cli_search.py --help
python cli_detail.py --help
python cli_comments.py --help
python cli_user_notes.py --help
python cli_share_link.py --help
```

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

## 🔑 API Token 获取

### 方式 1：微信联系（推荐）

**微信号：Tin240421**

添加微信后：
- ✅ 获取 API Key
- ✅ 获取使用指导
- ✅ 技术支持和问题解答

### 方式 2：AI 牛马平台

1. 访问 AI 牛马平台注册账号
2. 在平台中创建应用
3. 获取 API Token
4. 将 Token 保存到 `.env` 文件中

**配置 Token**:
```bash
# 方法 1: 手动编辑 .env 文件
cp .env.example .env
# 编辑 .env 文件，将 XHS_API_TOKEN 替换为您的实际 Token

# 方法 2: 直接在命令行指定（无需配置文件）
python cli_search.py -k "Python" -t sk-your-token-here
```

## 已实现功能

### ✅ 功能 1: 笔记搜索 (Note Search)

**文件**: `note_search.py`

**功能描述**: 根据关键词和可选筛选条件搜索小红书笔记，返回分页结果集。

**核心特性**:
- 支持关键词搜索
- 多种排序方式（综合、热度、时间、评论数、收藏数）
- 笔记类型筛选（通用、视频、普通）
- 时间范围筛选（一天内、一周内、半年内）
- 分页支持
- 完整的错误处理
- **默认排序**：综合排序（general）
- **默认时间范围**：全部时间（不限制）

**翻页逻辑**:
```python
# 搜索接口使用页码分页（page 参数）
params = {
    "keyword": "Python",
    "page": 1,  # 页码：1, 2, 3...
    "sort": "general"  # 综合排序
}

# 当页无数据时自动停止采集
if not items:
    print("没有更多数据")
    break
```

**使用方法**:
```python
from note_search import XHSNoteSearch

# 初始化
searcher = XHSNoteSearch(api_token="your_token")

# 基本搜索
result = searcher.search(keyword="Python 编程")

# 高级搜索
result = searcher.search(
    keyword="旅行攻略",
    page=1,
    sort="popularity_descending",
    note_type="_1",
    note_time="一周内"
)

# 格式化输出
print(searcher.format_results(result))
```

### ✅ 功能 2: 用户笔记采集 (User Notes)

**文件**: `user_notes.py`

**功能描述**: 获取指定小红书用户发布的笔记分页列表，支持全量采集和分页采集。

**核心特性**:
- 根据用户 ID 采集其发布的所有笔记
- 支持单页采集和全量自动分页采集
- 可设置最大页数和请求延迟，避免触发限流
- 支持导出 JSON、CSV 和 Excel 格式
- 完整的错误处理和友好的输出

**翻页逻辑**:
```python
# 用户笔记翻页
# 1. 从最后一条笔记获取 cursor 字段
raw_cursor = notes[-1].get("cursor")

# 2. 提取嵌套的 cursor 值（可能是 JSON 字符串）
last_cursor = self._extract_cursor(raw_cursor)

# 3. 使用 lastCursor 参数请求下一页
params["lastCursor"] = last_cursor

# _extract_cursor 方法处理嵌套结构：
# 输入：{"cursor":"66f651b3000000001b0216c4","index":1}
# 输出：66f651b3000000001b0216c4
```

**使用方法**:
```python
from user_notes import XHSUserNotes

# 初始化
crawler = XHSUserNotes(api_token="your_token")

# 单页采集（第一页）
result = crawler.get_user_notes(user_id="5c2f338a000000000701e1c6")

# 全量采集（自动分页）
result = crawler.get_all_user_notes(
    user_id="5c2f338a000000000701e1c6",
    max_pages=10,  # 最大页数，None 表示不限制
    delay_seconds=1.0  # 每页延迟时间（秒）
)

# 格式化输出
print(crawler.format_notes(result))

# 导出数据
crawler.export_to_json(result, "user_notes.json")
crawler.export_to_csv(result, "user_notes.csv")
crawler.export_to_excel(notes, "user_notes.xlsx")  # Excel 导出
```

### ✅ 功能 3: 笔记详情采集 (Note Detail)

**文件**: `note_detail.py`

**功能描述**: 获取指定小红书笔记的完整详细信息，支持单个笔记和批量笔记采集，无需提供用户 ID。

**核心特性**:
- 根据笔记 ID 直接获取笔记详情（无需用户 ID）
- 支持单个笔记采集和批量笔记采集
- 支持从笔记链接提取笔记 ID
- 支持导出 JSON 和 Excel 格式
- Excel 导出支持列宽自适应和自动换行
- 完整的错误处理和友好的输出
- 提取标签信息、互动数据、媒体信息等
- 自动请求延迟控制，避免触发限流

**使用方法**:
```python
from note_detail import XHSNoteDetail

# 初始化
crawler = XHSNoteDetail(api_token="your_token")

# 单个笔记详情（无需用户 ID）
result = crawler.get_note_detail(note_id="63b38c37000000001e03de92")
print(crawler.format_note_detail(result))

# 批量笔记详情
note_ids = ["note_id_1", "note_id_2", "note_id_3"]
result = crawler.get_notes_by_ids(
    note_ids=note_ids,
    delay_seconds=1.0
)

# 导出数据
crawler.export_to_json(result, "note_detail.json")

# 导出 Excel（封面图显示实际链接、列宽自适应、自动换行）
notes = [result.get("data", {}).get("note", {})]
crawler.export_to_excel(notes, "note_detail.xlsx")
```

### ✅ 功能 4: 评论采集 (Note Comments)

**文件**: `note_comments.py`

**功能描述**: 获取小红书笔记的评论列表，支持分页采集、多种排序方式，包含评论内容、用户信息、IP 位置等元数据。支持主评论和子评论（回复）的全量采集。

**核心特性**:
- 根据笔记 ID 获取评论列表
- 支持单页采集和全量自动分页采集
- 支持排序方式（最新优先/默认排序）
- 可设置最大页数和请求延迟
- 支持导出 JSON、CSV 和 Excel 格式
- 完整的错误处理和友好的输出
- 提取评论标签（如"首评"、"作者赞过"等）
- Excel 导出支持列宽自适应和自动换行
- 支持主评论和子评论自动去重
- 优化子评论采集逻辑，节省 API 配额

**翻页逻辑**:
```python
# 主评论翻页
# 1. 从响应顶层获取 cursor 字段
raw_cursor = data.get("cursor")

# 2. 提取嵌套的 cursor 值（可能是 JSON 字符串）
last_cursor = self._extract_cursor(raw_cursor)

# 3. 使用 lastCursor 参数请求下一页
params["lastCursor"] = last_cursor

# _extract_cursor 方法处理嵌套结构：
# 输入：{"cursor":"65bf662f0000000008017f77","index":2}
# 输出：65bf662f0000000008017f77
```

**子评论翻页**:
```python
# 子评论使用相同的翻页逻辑
# 从响应顶层获取 cursor 字段并提取实际值
sub_comment_cursor = self._extract_cursor(data.get("cursor"))
params["lastCursor"] = sub_comment_cursor
```

**使用方法**:
```python
from note_comments import XHSNoteComments

# 初始化
crawler = XHSNoteComments(api_token="your_token")

# 单页采集
result = crawler.get_comments(
    note_id="698af6400000000015031456",
    sort="latest"  # 或 "normal"
)
print(crawler.format_comments(result))

# 全量采集（自动分页 + 子评论）
result = crawler.get_all_comments(
    note_id="698af6400000000015031456",
    max_pages=None,  # 不限制页数
    delay_seconds=2.0,  # 主评论分页延迟（秒）
    sort="latest",
    fetch_sub_comments=True,  # 采集子评论
    sub_comment_delay=1.0  # 子评论采集延迟（秒）
)

# 导出数据
crawler.export_to_json(result, "comments.json")
crawler.export_to_csv(result, "comments.csv")

# 导出 Excel（列宽自适应、自动换行、全局去重）
crawler.export_to_excel(result, "comments.xlsx")
```

### ✅ 功能 5: 分享链接转化 (Share Link Converter)

**文件**: `share_link_convert.py`

**功能描述**: 将小红书分享短链接转换为标准笔记链接，自动提取笔记 ID，用于下游 API 调用。支持单个链接转换和批量转换，可导出 Excel 表格。

**核心特性**:
- 将分享短链接转换为标准笔记链接
- 自动从链接中提取笔记 ID
- 支持各种分享链接格式（discovery/item、explore 等）
- **支持批量转换**（从文件读取多个链接）
- **支持导出 Excel**（带状态标记和颜色）
- 用于笔记详情和评论采集的前置处理
- 完整的错误处理和友好的输出

**使用方法**:
```python
from share_link_convert import XHSShareLinkConverter

# 初始化
converter = XHSShareLinkConverter(api_token="your_token")

# 单个链接转换
share_url = "https://www.xiaohongshu.com/discovery/item/69a8b0b9000000001a02fb14"
result = converter.convert_share_url(share_url)

# 输出结果
print(converter.format_result(result))

# 获取笔记 ID
note_id = result.get("data", {}).get("note_id", "")

# 直接用于笔记详情采集
from note_detail import XHSNoteDetail
crawler = XHSNoteDetail(api_token="your_token")
note_result = crawler.get_note_detail(note_id)

# 批量转换
urls = [
    "https://www.xiaohongshu.com/discovery/item/xxx1",
    "https://www.xiaohongshu.com/explore/xxx2",
    # ... 更多链接
]

batch_result = converter.convert_batch(urls, delay_seconds=0.5)

# 导出 Excel
converter.export_to_excel(batch_result, "link_conversion.xlsx")
```

**CLI 工具**:
```bash
# 转换单个链接
python cli_share_link.py -u "https://www.xiaohongshu.com/explore/xxx"

# 批量转换（从文件读取 URL，每行一个）
python cli_share_link.py -f urls.txt

# 批量转换并导出 Excel
python cli_share_link.py -f urls.txt -o result.xlsx

# 指定 API Token
python cli_share_link.py -f urls.txt -t sk-your-token-here -o result.xlsx
```

## 功能对比

| 功能 | 文件 | API 接口 | 主要用途 | 输入参数 | 输出格式 | 分页支持 | Excel 导出 |
|------|------|----------|----------|----------|----------|----------|------------|
| **笔记搜索** | `note_search.py` | `/xiaohongshu/search-note/v2` | 根据关键词搜索笔记 | 关键词、排序、类型、时间 | JSON, Excel | ✅ 支持 | ✅ 支持 |
| **用户笔记采集** | `user_notes.py` | `/xiaohongshu/get-user-note-list/v4` | 采集用户发布的所有笔记 | 用户 ID | JSON, CSV, Excel | ✅ 自动分页 | ✅ 支持 |
| **笔记详情采集** | `note_detail.py` | `/xiaohongshu/get-note-detail/v1` | 获取指定笔记的详细信息 | 笔记 ID | JSON, Excel | ❌ 无需分页 | ✅ 支持 |
| **评论采集** | `note_comments.py` | `/xiaohongshu/get-note-comment/v2` | 采集笔记的评论列表 | 笔记 ID、排序 | JSON, CSV, Excel | ✅ 自动分页 | ✅ 支持 |
| **分享链接转化** | `share_link_convert.py` | `/xiaohongshu/share-url-transfer/v1` | 转换分享链接为标准链接 | 分享链接 | JSON, Excel | ❌ 无需分页 | ✅ 支持（批量转换） |

## 快速开始

### 新用户引导

**首次使用？运行引导脚本：**

```bash
python setup_guide.py
```

引导脚本将帮助您：
1. ✅ 配置 API Token
2. ✅ 了解 5 大核心功能
3. ✅ 查看使用示例
4. ✅ 快速入门使用

## 使用场景

- 需要分析小红书热门笔记和内容趋势
- 需要获取特定用户的信息和发布内容
- 需要爬取笔记评论进行情感分析或数据研究
- 需要监控特定话题或标签下的内容
- 竞品分析和市场调研

## 注意事项

1. **遵守法律法规**: 确保爬虫行为符合相关法律法规和平台服务条款
2. **API 配额**: 每次请求都会消耗 API 配额，请合理使用
3. **速率限制**: 建议请求间隔至少 1 秒，避免触发限流
4. **数据使用**: 仅将爬取的数据用于合法合规的目的
5. **隐私保护**: 不要收集和使用用户隐私信息

## 错误码说明

| 错误码 | 说明 |
|--------|------|
| 0 | 成功 |
| 100 | Token 无效或已失效 |
| 301 | 采集失败，请重试 |
| 302 | 超出速率限制 |
| 400 | 参数错误 |
| 500 | 内部服务器错误 |

## 技术实现

**依赖库**:
- `requests` - HTTP 请求
- `python-dotenv` - 环境变量管理
- `pandas` - 数据处理
- `openpyxl` - Excel 文件操作
- **API 服务**: Proxy API

**安装依赖**:
```bash
pip install -r requirements.txt
```

**配置 API Token**:
```bash
# 复制配置示例
cp .env.example .env

# 编辑 .env 文件，填入你的 API Token
XHS_API_TOKEN=your_api_token_here
```

## 文件结构

```
xhs_crawler_skill/
├── SKILL.md              # 技能说明文档（本文件）
├── README.md             # 详细使用指南
├── GETTING_STARTED.md    # 新用户入门指南
├── note_search.py        # 笔记搜索核心类
├── user_notes.py         # 用户笔记采集核心类
├── note_detail.py        # 笔记详情采集核心类
├── note_comments.py      # 评论采集核心类
├── share_link_convert.py # 分享链接转化核心类
├── cli_search.py         # CLI 工具 - 搜索
├── cli_detail.py         # CLI 工具 - 详情
├── cli_comments.py       # CLI 工具 - 评论
├── cli_user_notes.py     # CLI 工具 - 用户笔记
├── cli_share_link.py     # CLI 工具 - 链接转换
├── .env                  # API Token 配置文件
├── .env.example          # 配置文件示例
└── requirements.txt      # Python 依赖
```

## 相关配置

首次使用时需要配置:
- **API Token**: AI 牛马平台的访问令牌（必填）
- **请求超时**: 默认 60 秒
- **请求延迟**: 建议至少 1 秒，避免触发限流

## API 接口说明

所有 API 接口均使用 AI 牛马代理平台：

**Base URL**: `https://proxy-api.ainm.store/p`

**完整接口路径**:
- 笔记搜索：`https://proxy-api.ainm.store/p/xiaohongshu/search-note/v2`
- 用户笔记：`https://proxy-api.ainm.store/p/xiaohongshu/get-user-note-list/v4`
- 笔记详情：`https://proxy-api.ainm.store/p/xiaohongshu/get-note-detail/v1`
- 笔记评论：`https://proxy-api.ainm.store/p/xiaohongshu/get-note-comment/v2`
- 评论回复：`https://proxy-api.ainm.store/p/xiaohongshu/get-note-sub-comment/v2`
- 分享链接：`https://proxy-api.ainm.store/p/xiaohongshu/share-url-transfer/v1`
