---
name: yuque
description: |
  语雀(Yuque)知识库操作技能。自动获取和管理用户语雀空间的文档、知识库信息，支持搜索、创建、编辑、删除文档等操作。
  当用户提到"语雀"、"yuque"、"知识库文档"、"查看我的语雀"、"语雀文档"、"语雀知识库"、"yuque文档"、"语雀笔记"、"编辑语雀"、"更新语雀文档"时触发此技能。
  也适用于用户想查看、搜索、创建、编辑、删除语雀文档的任何场景，即使用户没有明确提到"语雀"但上下文暗示在操作语雀平台。
---
# 语雀知识库操作技能

通过语雀 Web API 实现知识库和文档的自动化操作，包括查看、搜索、创建、编辑、删除等功能。

## 前置条件

使用前需要配置语雀凭证。检查本文档所在目录是否存在credentials.json且包含以下信息（如不包含，请用户按照配置方式进行配置）：

1. **Cookie** - 登录语雀后浏览器的完整 Cookie 字符串
2. **CSRF Token** - 即 Cookie 中 `yuque_ctoken` 的值
3. **用户 Login** - 语雀用户名（如 `your-login`）

### 凭证配置方式

**credentials.json 文件**（持久使用）

在 skill 目录下创建 `credentials.json`：

```json
{
  "cookie": "完整cookie字符串",
  "csrf_token": "yuque_ctoken值",
  "x_login": "用户login"
}
```

**获取凭证步骤**：

1. 浏览器登录 yuque.com
2. F12 → Network → 刷新页面
3. 找任意请求 → 复制 Request Headers 中的 Cookie 值
4. 从 Cookie 中提取 `yuque_ctoken` 的值作为 CSRF Token
5. 用户 login 在请求头的 `x-login` 字段中

---

## 核心操作

### 1. 获取用户信息

先用脚本确认凭证有效：

```bash
python {skill_dir}/scripts/yuque_client.py whoami
```

返回用户名、ID、知识库数量等基本信息。

### 2. 获取知识库列表

```bash
python {skill_dir}/scripts/yuque_client.py list-books
```

返回所有知识库的 id, name, slug, type 等。**记录目标知识库的 id 用于后续操作。**

### 3. 获取知识库文档列表

```bash
python {skill_dir}/scripts/yuque_client.py list-docs <book_id> [offset] [limit]
```

- `book_id` - 知识库ID（数字）
- `offset` - 偏移量，默认0
- `limit` - 每页数量，默认20

### 4. 获取知识库目录结构

```bash
python {skill_dir}/scripts/yuque_client.py get-toc <book_id>
```

返回 TOC 树形结构和文档列表，可展示知识库的完整目录。

### 5. 获取文档详情（含内容）

```bash
python {skill_dir}/scripts/yuque_client.py get-doc <doc_id_or_slug> <book_id> edit
```

**关键**: 必须传 `mode=edit` 才能获取文档 body 内容。`mode=read` 不返回 body。

文档 body 格式为 HTML，包裹在 `<div class="lake-content">` 中。

### 6. 搜索文档

```bash
python {skill_dir}/scripts/yuque_client.py search <keyword> [type]
```

- `keyword` - 搜索关键词
- `type` - `doc`(文档, 默认) 或 `book`(知识库)

⚠️ **注意：search 是语雀全站公开搜索，会返回所有用户的公开文档。当用户要找自己的文档时，不要用 search，应走"工作流3"（list-books → list-docs 按标题匹配）。**

### 7. 创建文档

```bash
python {skill_dir}/scripts/yuque_client.py create-doc <book_id> <title> [slug] [body]
```

- `book_id` - 知识库ID
- `title` - 文档标题
- `slug` - 可选，URL友好标识
- `body` - 可选，文档内容（HTML格式）

### 8. 更新文档

```bash
python {skill_dir}/scripts/yuque_client.py update-doc <doc_id> <book_id> [title] [body]
```

**长内容推荐用 `--body-file` 从文件读取**（避免命令行长度限制）：

```bash
python {skill_dir}/scripts/yuque_client.py update-doc <doc_id> <book_id> "新标题" --body-file /path/to/body.html
```

- 传入需要修改的字段，未传的字段保持不变
- `book_id` 必传
- `--body-file` 可以放在 title 之前或之后，脚本会自动识别
- **内部机制**：脚本会通过 `/api/docs/:id/content` 接口同步更新 `body_draft`（语雀前端渲染依赖此字段），再通过 `/api/docs/:id` 更新已发布的 `body`，确保网页端立即可见

### 9. 删除文档

```bash
python {skill_dir}/scripts/yuque_client.py delete-doc <doc_id> <book_id>
```

**谨慎操作**，删除后文档进入回收站。

### 10. 获取文档版本历史

```bash
python {skill_dir}/scripts/yuque_client.py get-doc-versions <doc_id>
```

---

## 常见工作流

### 工作流1：浏览知识库内容

```
1. list-books → 找到目标知识库 id
2. get-toc <book_id> → 查看目录结构
3. list-docs <book_id> → 获取文档列表
4. get-doc <doc_id> <book_id> edit → 读取具体文档内容
```

### 工作流2：创建并编辑文档

```
1. list-books → 确认目标知识库 id
2. get-toc <book_id> → 查看当前目录，确定放置位置
3. create-doc <book_id> "文档标题" → 创建文档
4. update-doc <doc_id> <book_id> "新标题" "新内容" → 编辑文档
```

### 工作流3：查找用户自己的文档并更新

**当用户说"找我的文档"、"看我的XX文档"、"我的语雀里有篇…"等表达时，必须走此流程，不要用 search 命令（search 是全站公开搜索，会搜到别人的文档）。**

```
1. list-books → 获取用户所有知识库
2. list-docs <book_id> → 遍历知识库（可并行多个），按标题匹配目标文档
3. get-doc <doc_id> <book_id> edit → 读取具体文档内容
4. update-doc <doc_id> <book_id> "新标题" "新内容" → 更新文档（如需）
```

### 工作流4：搜索语雀公开文档

**仅当用户明确要搜索语雀平台上的公开内容（非自己知识库）时才使用 search 命令。**

```
1. search <keyword> → 全站搜索公开文档
2. 根据搜索结果获取文档详情
```

---

## 重要注意事项

1. **body 只在 mode=edit 时返回** - 这是语雀的设计，read 模式不返回文档内容
2. **book_id 必传** - 几乎所有文档 API 都需要 book_id 参数
3. **Cookie 会过期** - 如果返回 401/403，需要用户重新获取 Cookie
4. **文档内容是 HTML 格式** - 语雀的 lake 编辑器使用 HTML 格式，更新时需要保持格式一致
5. **分页** - 文档列表默认每页20条，知识库文档多时需要分页获取
6. **v2 API 不可用** - `/api/v2/` 路径需要 OAuth Token，Cookie 方式只能用 v1 API
7. **写操作需 CSRF Token** - POST/PUT/DELETE 操作必须携带有效的 x-csrf-token
8. **body vs body_draft** - 语雀有两套存储：`body`（已发布内容）和 `body_draft`（编辑器草稿）。前端渲染优先用 `body_draft`。本脚本的 `update-doc` 已通过 `/api/docs/:id/content` 接口自动同步两者
9. **长内容用 --body-file** - 命令行参数有长度限制（Windows ~8000字节），长文档内容应先写入临时文件，用 `--body-file /path/to/file.html` 传入

---

## API 详细参考

完整 API 文档在 `references/api_reference.md`，包含所有已验证的接口、请求格式、响应字段和已知限制。

## 脚本工具

| 脚本            | 路径                        | 用途                                |
| --------------- | --------------------------- | ----------------------------------- |
| yuque_client.py | `scripts/yuque_client.py` | 语雀 API 命令行客户端，支持所有操作 |
