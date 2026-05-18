# 语雀 API 参考文档

> 基于 web-reverse-engineer 技能逆向分析生成

## 鉴权方式

语雀 Web API 使用 **Cookie + CSRF Token** 方式鉴权。

### 必需凭证

| 凭证 | 来源 | 用途 |
|------|------|------|
| `Cookie` | 登录后浏览器 Cookie 全部内容 | 身份认证，需包含 `_yuque_session` |
| `x-csrf-token` | Cookie 中的 `yuque_ctoken` 值 | CSRF 防护，写操作必带 |
| `x-login` | 用户 login 名（如 `your-login`） | 标识当前用户 |

### 标准请求头

```
Cookie: {完整cookie}
x-csrf-token: {yuque_ctoken值}
x-login: {用户login}
X-Requested-With: XMLHttpRequest
Content-Type: application/json
```

---

## 一、用户信息

### GET /api/mine
获取当前登录用户信息。

**响应字段**: id, login, name, avatar_url, email, description, books_count, topics_count, followers_count, following_count, member_level 等

### GET /api/mine/books
获取我的知识库列表。

**响应**: `data` 为数组，每项含 id, name, slug, type, public, description, user

### GET /api/mine/groups
获取我的组列表。

### GET /api/mine/personal_books
获取个人知识库（不含协作）。

### GET /api/mine/collaborate_books
获取协作知识库。

### GET /api/mine/book_stacks
获取知识库栈。

### GET /api/mine/collaborations
获取协作列表。

### GET /api/mine/common_used
获取常用内容。返回 `{groups: [], books: []}`

### GET /api/mine/recycles
获取回收站。返回 `{data: [], total: number}`

### GET /api/mine/user_settings
获取用户设置。

### GET /api/mine/organizations
获取组织列表。

---

## 二、知识库操作

### GET /api/books/{book_id}/docs
获取知识库的文档列表（分页）。

**参数**: `offset` (默认0), `limit` (默认20, 最大?)

**响应字段**: id, title, slug, book_id, format, word_count, status, public, description, created_at, updated_at, published_at, user, last_editor

**注意**: 返回的文档**不包含 body 字段**，需单独获取。

### GET /api/books/{book_id}/toc
获取知识库的目录结构。

**响应**: `{toc: [...], docs: [...]}`

**TOC节点字段**: type(TITLE/DOC), title, uuid, url, level, doc_id, parent_uuid, child_uuid, sibling_uuid, visible, open_window

### GET /api/catalog_nodes?book_id={book_id}
获取目录节点列表。

---

## 三、文档操作

### GET /api/docs/{doc_id_or_slug}?book_id={book_id}
获取文档详情。

**关键参数**:
- `book_id` - **必需**，知识库ID
- `mode` - `edit` 返回 body，`read` 不返回 body

**mode=read 返回字段**: id, title, slug, book_id, format, word_count, status, public, description, body_asl, abilities, meta 等（**不含body**）

**mode=edit 返回字段**: 上述所有 + `body`, `body_draft`, `body_draft_asl`, `collab`, `locker`, `contributors` 等

**body格式**: HTML格式，包裹在 `<div class="lake-content">` 中

### POST /api/docs
创建新文档。

**请求体**: `{book_id, title, slug?, format:"lake", body?}`

**响应**: 返回创建的文档信息(id, title, slug等)

### PUT /api/docs/{doc_id}
更新文档。

**请求体**: `{book_id, title?, body?, ...}`

**注意**: 更新时只传需要修改的字段，但 book_id 必传。

**重要**: 此接口只更新 `body`（已发布内容），不更新 `body_draft`（编辑器草稿）。语雀前端渲染优先使用 `body_draft`，所以仅用此接口更新后，网页端可能看不到新内容。需配合 content 接口使用。

### PUT /api/docs/{doc_id}/content
更新文档内容（含草稿），这是语雀编辑器保存时使用的接口。

**请求体**:
```json
{
  "format": "lake",
  "body_asl": "<html内容>",
  "body_draft_asl": "<html内容>",
  "save_type": "user",
  "draft_version": <number>
}
```

**必需字段**:
- `format` - 固定为 `"lake"`
- `body_asl` - 文档内容（HTML 格式）
- `save_type` - `"user"`（手动保存）或 `"auto"`（自动保存）
- `draft_version` - 当前草稿版本号，需先通过 `GET /api/docs/:id?mode=edit` 获取

**可选字段**:
- `body_draft_asl` - 草稿内容（通常与 body_asl 一致）

**注意**: 此接口更新 `body_draft`，语雀前端立即可见。配合 `PUT /api/docs/:id` 更新 `body` 可确保完整更新。

### DELETE /api/docs/{doc_id}
删除文档。

**请求体**: `{book_id}`

---

## 四、搜索

### GET /api/zsearch?q={keyword}&type={type}
全局搜索。

**参数**:
- `q` - 搜索关键词
- `type` - **必需**，搜索类型: `doc`(文档) 或 `book`(知识库)
- `bookId` - 可选，限定知识库范围

**响应**: `{type, hits: [...], totalHits, numHits}`

**hit字段**: id, title, slug, type, url, abstract, book_name, group_name, privacy

---

## 五、文档版本

### GET /api/doc_versions?doc_id={doc_id}
获取文档版本历史。

**响应字段**: id, doc_id, title, user_id, draft, created_at, isReleased, origin, name, publication_status

---

## 六、目录节点操作

### POST /api/catalog_nodes
创建目录节点。

### PUT /api/catalog_nodes/{id}
更新目录节点。

### DELETE /api/catalog_nodes/{id}
删除目录节点。

### PUT /api/catalog_nodes/move
移动目录节点。

### PUT /api/catalog_nodes/publish_doc
发布文档到目录。

---

## 七、收藏

### GET /api/mine/marks/{target_id}?target_type=Book
获取收藏状态。

**响应**: `{markAction, marked}`

---

## 八、其他API

### 文档操作
- `POST /api/docs/copy` - 复制文档
- `POST /api/docs/move` - 移动文档
- `POST /api/docs/convert` - 转换文档格式
- `POST /api/docs/restore` - 恢复已删除文档
- `POST /api/docs/batch_private` - 批量设为私有
- `POST /api/docs/add_to_catalog` - 添加到目录
- `POST /api/docs/share_to_personal_feed` - 分享到动态

### 资源操作
- `GET /api/resources?book_id={id}` - 获取资源列表
- `POST /api/resources` - 创建资源
- `POST /api/resources/store` - 上传资源
- `POST /api/resources/copy` - 复制资源
- `POST /api/resources/move` - 移动资源

### 编辑器
- `GET /api/editor/search` - 编辑器内搜索
- `GET /api/editor/recent` - 最近编辑
- `GET /api/editor/link_detail` - 链接详情

### 评论
- `GET /api/comments?target_type=Book&target_id={id}` - 获取评论

---

## 九、已知限制

1. **v2 API** (`/api/v2/...`) 需要 OAuth Token，Cookie 方式无法访问
2. **文档内容** 只有 `mode=edit` 才返回 body，`mode=read` 不返回
3. **知识库详情** 没有独立的 API 获取知识库元信息（如 name/description），需从 mine/books 获取
4. **namespace** 格式为 `{user_login}/{book_slug}`，但 API 主要用 `book_id`（数字）
5. **分页** 文档列表默认每页20条，需用 offset+limit 翻页
6. **body vs body_draft** 语雀有两套存储：`PUT /api/docs/:id` 只更新 `body`（已发布），`PUT /api/docs/:id/content` 更新 `body_draft`（编辑器草稿）。前端渲染优先用 `body_draft`，更新文档必须两个接口配合使用
7. **content 接口需要 draft_version** `PUT /api/docs/:id/content` 需要传 `draft_version` 字段（从 `GET /api/docs/:id?mode=edit` 获取），否则返回 400
