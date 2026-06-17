# 小红书爬虫技能 - 固定工作流程

**版本**: 2.6.0  
**最后更新**: 2026-04-13

## 🆕 版本 2.6.0 更新

**核心改进**:
- ✅ **笔记详情链接修复**：完整提取带 xsec_token 的笔记链接
- ✅ **数据结构解析优化**：正确处理 note_list 嵌套结构
- ✅ **URL 解码处理**：先解码再提取 xsec_token
- ✅ **双源 token 提取**：mini_program_info → qq_mini_program_info

---

## 📋 工作流程概览

```
用户请求
  ↓
AI 识别功能需求
  ↓
调用对应 CLI 脚本
  ↓
执行数据采集
  ↓
导出 Excel 表格 ✅
  ↓
返回 JSON 响应 ✅
  ↓
清理临时文件 ✅
  ↓
完成任务
```

---

## ✅ 固定规则

### 1. AI 执行规则

**必须遵守**:
- ✅ **只能调用现有 CLI 脚本** (`cli_*.py`)
- ✅ **禁止创建新脚本文件**
- ✅ **禁止生成测试文档**
- ✅ **禁止生成总结文档**
- ✅ **必须导出 Excel 表格**（除非用户明确要求不导出）
- ✅ **必须返回 JSON 响应**（完整数据结构）
- ✅ **执行后清理调试文件**

### 2. Excel 导出规则

**导出位置**:
- 默认保存到技能根目录：`d:\Openclaw_skill\.trae\skills\xhs_crawler_skill\`
- 支持用户自定义路径（`-o` 参数）

**文件命名**:
| 功能 | 命名规则 | 示例 |
|------|---------|------|
| 搜索笔记 | `search_关键词_排序方式.xlsx` | `search_skill_general.xlsx` |
| 笔记详情 | `note_笔记 ID_detail.xlsx` | `note_69bc8304000000002202b8af_detail.xlsx` |
| 评论采集 | `comments_笔记 ID.xlsx` | `comments_68669baf000000000b01c729.xlsx` |
| 用户笔记 | `user_notes_用户 ID.xlsx` | `user_notes_5b83d9b2bced640001784c33.xlsx` |
| 链接转换 | `link_convert_result.xlsx` | `link_convert_result.xlsx` |
| 批量转换 | `link_convert_result.xlsx` | `link_convert_result.xlsx` |

**Excel 格式要求**:
- ✅ 列宽自适应
- ✅ 长文本自动换行
- ✅ 状态标记（成功=绿色，失败=红色）
- ✅ 数据类型标记（主评论/子评论）
- ✅ 时间戳转换为日期格式

### 3. JSON 响应规则

**必须返回完整数据结构**:
```json
{
  "success": true,
  "data": {
    // 完整的 API 响应数据
  },
  "message": "执行成功"
}
```

**响应内容**:
- ✅ 包含所有原始字段
- ✅ 保持数据层级结构
- ✅ 包含统计信息（总数、成功数、失败数）

---

## 🔄 各功能工作流程

### 1️⃣ 搜索笔记

**CLI 命令**:
```bash
python cli_search.py -k "关键词" -t TOKEN -o 输出路径.xlsx
```

**工作流程**:
1. AI 识别搜索需求
2. 调用 `cli_search.py`
3. 设置参数（关键词、排序、时间范围）
4. 执行搜索（自动分页）
5. 导出 Excel（包含所有笔记数据）
6. 返回 JSON 响应
7. 清理临时文件

**Excel 内容**:
- 笔记 ID、标题、描述、类型
- 发布时间（日期格式）
- 点赞数、收藏数、评论数、分享数
- 作者信息（ID、昵称）
- 图片数量、封面图链接

---

### 2️⃣ 笔记详情

**CLI 命令**:
```bash
python cli_detail.py -n 笔记 ID -t TOKEN -o 输出路径.xlsx
```

**工作流程**:
1. AI 识别笔记详情需求
2. 如果是分享链接，先调用 `cli_share_link.py` 提取笔记 ID
3. 调用 `cli_detail.py`
4. 获取笔记完整信息
5. 导出 Excel（单行数据）
6. 返回 JSON 响应
7. 清理临时文件

**Excel 内容**:
- 笔记 ID、标题、描述
- 封面图链接（实际 URL，非超链接）
- 发布时间（日期格式）
- 点赞数、收藏数、评论数
- 作者信息
- 标签信息

---

### 3️⃣ 评论采集

**CLI 命令**:
```bash
python cli_comments.py -n 笔记 ID -t TOKEN --all --sub-comments -o 输出路径.xlsx
```

**工作流程**:
1. AI 识别评论采集需求
2. 调用 `cli_comments.py`
3. 采集主评论（自动分页）
4. 采集子评论（针对每条有回复的主评论）
5. 合并数据并去重
6. 导出 Excel（标记评论类型）
7. 返回 JSON 响应
8. 清理临时文件

**Excel 内容**:
- 评论 ID、内容、类型（主评论/子评论）
- 评论者信息（ID、昵称、头像）
- 点赞数、回复数
- 发布时间（日期格式）
- IP 属地
- 标签信息（首评、作者赞过等）

**数据验证**:
- ✅ 主评论数量 = API 返回的 `comment_count_l1`
- ✅ 子评论数量 = 所有 `sub_comment_count` 之和
- ✅ 总数量 = 主评论 + 子评论

---

### 4️⃣ 用户笔记

**CLI 命令**:
```bash
python cli_user_notes.py -u 用户 ID -t TOKEN --all -o 输出路径.xlsx
```

**工作流程**:
1. AI 识别用户笔记采集需求
2. 调用 `cli_user_notes.py`
3. 采集用户所有笔记（自动分页）
4. 导出 Excel
5. 返回 JSON 响应
6. 清理临时文件

**Excel 内容**:
- 笔记 ID、标题、描述
- 发布时间（日期格式）
- 互动数据（点赞、收藏、评论、分享）
- 图片数量、封面图链接

---

### 5️⃣ 链接转换

**CLI 命令**:
```bash
python cli_share_link.py -u "分享链接" -t TOKEN -o 输出路径.xlsx
```

**工作流程**:
1. AI 识别链接转换需求
2. 调用 `cli_share_link.py`
3. 调用 API 转换链接
4. 提取笔记 ID
5. 导出 Excel（单行数据）
6. 返回 JSON 响应
7. 清理临时文件

**Excel 内容**:
- 原始链接
- 转换后链接
- 笔记 ID
- 转换状态（成功/失败）

---

### 6️⃣ 批量转换

**CLI 命令**:
```bash
python cli_share_link.py -f urls.txt -t TOKEN -o 输出路径.xlsx
```

**工作流程**:
1. AI 识别批量转换需求
2. 从文件读取 URL 列表
3. 调用 `cli_share_link.py` 批量转换
4. 逐个转换并统计结果
5. 导出 Excel（所有链接）
6. 返回 JSON 响应（包含统计信息）
7. 清理临时文件

**Excel 内容**:
- 序号、状态（成功/失败）
- 原始链接、转换后链接
- 笔记 ID
- 消息/错误信息

---

## 🛠️ 错误处理流程

### 301 错误（采集失败）
```
检测到 301 错误
  ↓
等待 5 秒后重试
  ↓
最多重试 3 次
  ↓
仍失败 → 返回错误信息
  ↓
成功 → 继续执行
```

### 429 错误（速率限制）
```
检测到 429 错误
  ↓
增加请求延迟（+1 秒）
  ↓
等待后重试
  ↓
记录错误次数
  ↓
超过阈值 → 停止并提示用户
```

### API 响应异常
```
检测到 code != 200
  ↓
检查嵌套结构（外层 200，内层 0）
  ↓
提取内层 data
  ↓
验证数据完整性
  ↓
不完整 → 重试或报错
```

---

## 📊 数据验证规则

### 评论采集验证
```python
# 验证主评论数量
if len(main_comments) != api_response.get("comment_count_l1"):
    print(f"⚠️ 主评论数量不匹配")

# 验证子评论数量
total_sub_comments = sum(c.get("sub_comment_count", 0) for c in main_comments)
if len(all_sub_comments) != total_sub_comments:
    print(f"⚠️ 子评论数量不匹配")

# 验证总数
total = len(main_comments) + len(all_sub_comments)
if total != api_response.get("comment_count"):
    print(f"⚠️ 总评论数量不匹配")
```

### Excel 导出验证
```python
# 验证文件是否存在
if not os.path.exists(output_path):
    raise Exception("Excel 文件创建失败")

# 验证数据行数
df = pd.read_excel(output_path)
if len(df) != expected_count:
    print(f"⚠️ Excel 数据行数不匹配")
```

---

## 🧹 清理规则

**每次执行后必须清理**:
- ✅ 调试脚本（`debug_*.py`）
- ✅ 临时 JSON 文件
- ✅ 临时日志文件
- ✅ 测试数据文件

**保留文件**:
- ✅ 核心脚本（`cli_*.py`, `*.py` 核心类）
- ✅ 文档文件（`SKILL.md`, `README.md`, `GETTING_STARTED.md`）
- ✅ 配置文件（`.env`, `.env.example`, `requirements.txt`）
- ✅ 导出的 Excel 文件（用户需要）

---

## 📝 用户沟通模板

### 任务开始时
```
🔍 正在执行 [功能名称]...
   参数：[参数列表]
   预计耗时：[时间估算]
```

### 任务完成时
```
✅ [功能名称] 完成！
   - 数据量：[数量]
   - Excel 路径：[文件路径]
   - JSON 响应：[数据结构说明]
```

### 遇到错误时
```
⚠️ [错误类型]：[错误描述]
   建议：[解决方案]
   是否继续尝试？[是/否]
```

---

## 🎯 最佳实践

### 1. 请求延迟设置
- 搜索笔记：1-2 秒
- 评论采集：主评论 2 秒，子评论 1 秒
- 用户笔记：1-2 秒
- 链接转换：0.5 秒

### 2. 分页处理
- 检测 `has_more` 字段
- 验证 cursor 是否有效
- 无数据时立即停止

### 3. 数据去重
- 使用 ID 集合去重
- 合并时检查重复
- 导出前再次验证

### 4. 错误重试
- 301 错误：等待 5 秒，重试 3 次
- 429 错误：增加延迟，重试 2 次
- 超时错误：等待 3 秒，重试 2 次

---

## 📞 技术支持

**遇到问题？**
1. 查看文档：`SKILL.md`, `README.md`
2. 检查错误日志
3. 验证 API Token 是否有效
4. 联系技术支持（微信：Tin240421）

---

**版本**: 2.5.0  
**最后更新**: 2026-04-13  
**维护者**: AI 牛马团队
