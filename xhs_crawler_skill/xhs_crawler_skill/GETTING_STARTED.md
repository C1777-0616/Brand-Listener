# 新用户入门指南

欢迎使用小红书爬虫技能！本指南将帮助您快速上手。

**当前版本**: 2.6.0  
**更新时间**: 2026-04-13  
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

## 🚀 第一步：获取 API Token

**获取方式：**

**方式 1：微信联系（推荐）**
- 微信号：**Tin240421**
- 添加微信获取 API Key 和使用指导

**方式 2：AI 牛马平台**
- 访问平台注册账号
- 创建应用获取 API Token

**配置 Token：**
1. 复制配置文件：`cp .env.example .env`
2. 编辑 `.env` 文件，填入您的 API Token：`XHS_API_TOKEN=sk-your-token-here`

## 🚀 第二步：使用 CLI 工具（推荐）

**CLI 工具简单快捷，无需编写代码：**

```bash
# 搜索笔记
python cli_search.py -k "Python 编程"

# 采集笔记详情
python cli_detail.py -n 69bc8304000000002202b8af

# 采集评论（含子评论）
python cli_comments.py -n 69bc8304000000002202b8af --all --sub-comments

# 采集用户笔记
python cli_user_notes.py -u 5b83d9b2bced640001784c33 --all

# 转换分享链接
python cli_share_link.py -u "https://www.xiaohongshu.com/explore/xxx"
```

**查看帮助**：
```bash
python cli_search.py --help
```

## 🚀 第三步：使用 Python 代码（灵活定制）

## 📋 第二步：了解功能

本技能提供 5 大核心功能：

### 1. 笔记搜索
**用途**：根据关键词搜索小红书笔记  
**API 接口**：`/p/xiaohongshu/search-note/v2`

**示例**：
```python
from note_search import XHSNoteSearch

searcher = XHSNoteSearch(api_token="your_token")
result = searcher.search(keyword="Python 编程")
```

### 2. 用户笔记采集
**用途**：采集博主发布的所有笔记  
**API 接口**：`/p/xiaohongshu/get-user-note-list/v4`

**示例**：
```python
from user_notes import XHSUserNotes

crawler = XHSUserNotes(api_token="your_token")
result = crawler.get_all_user_notes(user_id="5b83d9b2bced640001784c33")
```

### 3. 笔记详情采集
**用途**：获取指定笔记的详细信息  
**API 接口**：`/p/xiaohongshu/get-note-detail/v1`

**示例**：
```python
from note_detail import XHSNoteDetail

crawler = XHSNoteDetail(api_token="your_token")
result = crawler.get_note_detail(note_id="698af6400000000015031456")
```

### 4. 评论采集
**用途**：采集笔记的评论列表（支持主评论和子评论）  
**API 接口**：`/p/xiaohongshu/get-note-comment/v2`

**示例**：
```python
from note_comments import XHSNoteComments

crawler = XHSNoteComments(api_token="your_token")
result = crawler.get_all_comments(note_id="698af6400000000015031456")
```

### 5. 分享链接转化
**用途**：将分享链接转换为标准笔记链接  
**API 接口**：`/p/xiaohongshu/share-url-transfer/v1`

**示例**：
```python
from share_link_convert import XHSShareLinkConverter

converter = XHSShareLinkConverter(api_token="your_token")
result = converter.convert_share_url("分享链接")
```

## ⚙️ 第三步：配置 API Token

1. 复制配置示例：
   ```bash
   cp .env.example .env
   ```

2. 编辑 `.env` 文件，填入你的 API Token：
   ```
   XHS_API_TOKEN=your_api_token_here
   ```

## 💡 使用提示

1. **速率限制**：建议请求间隔至少 1 秒，避免触发限流
2. **API 配额**：每次请求都会消耗配额，请合理使用
3. **数据导出**：支持 JSON、CSV、Excel 格式
4. **合法使用**：确保用于合法合规的目的

## ❓ 常见问题

### Q: 如何获取 API Token？

A: 获取 Proxy API 访问令牌。

### Q: 触发限流怎么办？

A: 增加请求延迟时间，建议至少 1-2 秒。

### Q: 如何导出 Excel？

A: 使用各模块提供的 `export_to_excel()` 方法。

## 📚 更多资源

- 详细技能说明：[SKILL.md](SKILL.md)
- 使用指南：[README.md](README.md)
- 技能版本：2.5.0
- API 服务：Proxy API
