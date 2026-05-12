---
name: web-reverse-engineer
description: |
  网站源码逆向分析技能：给定一个网站URL，通过抓取HTML/JS源码（而非浏览器渲染）逆向分析网站的接口、页面布局、鉴权流程和数据流。
  当用户提到"分析网站"、"逆向网站"、"网站接口"、"抓接口"、"网站源码分析"、"逆向工程"、"分析API"、"爬取接口"、"网站结构分析"、
  "给我分析一下这个网站"、"这个网站有什么接口"、"逆向这个站"、"破解网站接口"、"网站白盒分析"时触发此技能。
  即使用户只是给了一个URL说"帮我看看这个网站"，也应触发此技能并主动进行源码逆向分析。
---

# 网站源码逆向分析技能

## 核心目标

给定一个网站，做到：

1. **理解**：搞清楚这个网站能做什么，功能结构是什么
2. **操作**：给定凭证（Cookie / Token），直接通过 API 调用或模拟前端交互完成具体操作
3. **沉淀**：产出分析文档，下次直接复用，不用重新分析

逆向分析源码只是手段，不是目的。

---

## 工作模式

根据用户意图，进入不同模式：

| 用户说 | 进入模式 |
|--------|----------|
| "分析这个网站" / 给一个 URL | **分析模式**：理解功能 + 提取接口 + 产出文档 |
| "帮我操作 xxx" + 已有凭证 | **操作模式**：直接调用接口完成任务 |
| "帮我操作 xxx" + 没有凭证 | 先分析找到操作路径，提示用户提供凭证 |
| 给一个之前分析过的网站 | 优先读取已有的分析文档，直接进入操作模式 |

---

## ⚠️ 关键陷阱（必读）

### 陷阱1：`web_fetch` 返回摘要，不是原始源码

**绝对不要用 `web_fetch` 来提取 script 标签、JS 引用、API 端点。**

`web_fetch` 工具会对页面进行 AI 处理，返回可读摘要，`<script src>` 标签全部丢失。

**正确做法**：始终用 Python 脚本抓取原始 HTML：

```python
import urllib.request, ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(url, headers={
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept-Encoding': 'identity',  # 避免 gzip 解码问题
})
with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
    html = resp.read().decode('utf-8', errors='ignore')
```

### 陷阱2：PowerShell 内联代码引号冲突

**不要在 `execute_command` 中用 `python -c "..."` 内联代码**，PowerShell 会破坏引号。

**正确做法**：先写 `.py` 脚本文件，再 `python temp-scripts/xxx.py` 执行。

### 陷阱3：URL 格式多样，需统一处理

| 格式 | 示例 | 处理 |
|------|------|------|
| 协议相对路径 | `//api.example.com/...` | 补 `https:` |
| 绝对路径 | `/x/web-interface/nav` | 拼接域名 |
| 完整 URL | `https://api.example.com/...` | 直接用 |
| 相对路径 | `../chunks/xxx.js` | 用 `urljoin` 拼接 |

### 陷阱4：HTTP 方法和路径在 JS 中是分离的

大多数框架写法是 `{method: 'GET', url: '/api/xxx'}`，需要专门正则同时捕获两者：
```python
re.findall(r'method:\s*["\']( GET|POST|PUT|DELETE|PATCH)["\'].*?url:\s*["\']([^"\']+)["\']', content)
```

### 陷阱5：主入口 JS 不是全部

现代前端（Vite/Webpack）做代码分割，业务逻辑在 chunk 文件。**脚本已自动递归抓取 chunk 文件**。

### 陷阱6：SPA 空壳页面

纯 CSR 应用首屏 HTML 几乎无内容，只有 `<div id="app">`。此时需要：
- 重点分析 JS 路由配置
- 检查 Service Worker 缓存策略
- 必要时用浏览器自动化获取渲染后内容

### 陷阱7：429 限流

批量抓取时容易触发限流。脚本已内置重试和延迟机制。若仍被限流：
- 减小 `MAX_WORKERS`（默认5）
- 增大 `REQUEST_INTERVAL`（默认0.2s）
- 添加更真实的请求头

### 陷阱8：有些站点需要鉴权

有些站点需要登录后才能访问，直接抓取会返回空页面或登录页。

**正确做法**：使用 `--cookie` 参数传入登录 Cookie：

```bash
python temp-scripts/web_fetch_source.py https://internal.example.com/ output_dir \
  --cookie "sid=xxx; token=yyy; user=zzz"
```

### 陷阱9：CDN 域名与页面域名不同

很多站点的静态资源在独立 CDN 域名上（如页面 `app.example.com`，JS 在 `static.cdn.example.com`）。脚本已自动处理：chunk URL 与来源 JS 同域即可放行。

---

## 分析模式：源码获取与理解

### 步骤一：一键抓取

**使用 `scripts/web_fetch_source.py`（一键完成）**：

```bash
# 无鉴权站点
python temp-scripts/web_fetch_source.py https://目标网站.com/ output_dir

# 需要鉴权的站点
python temp-scripts/web_fetch_source.py https://example.com/ output_dir \
  --cookie "sid=xxx; token=yyy"

# 额外请求头
python temp-scripts/web_fetch_source.py https://目标网站.com/ output_dir \
  --header "X-Custom-Header: value"

# 调整并行数
python temp-scripts/web_fetch_source.py https://目标网站.com/ output_dir --workers 3
```

**命令行参数**：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `url` | 目标网站URL | 必填 |
| `output_dir` | 输出目录 | `web_analysis` |
| `--cookie, -c` | Cookie字符串 | 无 |
| `--header, -H` | 额外请求头（可多次） | 无 |
| `--workers, -w` | 并行线程数 | 5 |

脚本自动完成：
1. 抓 HTML → 解析结构 → 识别技术栈
2. 提取 JS 列表 → **并行抓取**（5线程）→ 自动下载 Source Map
3. **自动递归抓取 chunk 文件**（最多2层深度，100个文件上限）
4. 分析内联脚本
5. 提取 API 端点、鉴权信息、前端路由、WebSocket 端点
6. 去重汇总 → 保存分析报告

**关键配置**（在脚本顶部可修改）：
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `MAX_WORKERS` | 5 | 并行抓取线程数 |
| `REQUEST_TIMEOUT` | 20 | 单个请求超时(秒) |
| `MAX_RETRIES` | 2 | 失败重试次数 |
| `MAX_CHUNK_DEPTH` | 2 | chunk递归深度 |
| `MAX_TOTAL_JS` | 100 | JS文件总数上限 |

### 步骤二：识别技术栈

脚本自动识别，判断策略：

| 特征 | 技术栈 | 影响 |
|------|--------|------|
| `__NEXT_DATA__` | Next.js | 内联 JSON 含首屏数据和路由 |
| `__NUXT__` / `__INITIAL_STATE__` | Nuxt / Vue SSR | 内联状态有用户数据 |
| `window.__pinia__` | Pinia | 内联状态树可直接解析 |
| `ng-app` / `ng-version` | Angular | 模块化强，接口在 service 中 |
| `vite` | Vite | chunk 命名规则不同 |
| `graphql` / `__typename` | GraphQL | 需用 gql_analyzer 深度分析 |
| `sourceMappingURL` | 有 Source Map | **已自动下载**，可拿未混淆源码 |
| `new WebSocket` | WebSocket | 有实时通信，需分析 WS 鉴权 |
| `serviceWorker.register` | Service Worker | 可能暴露缓存策略和离线 API |

### 步骤三：深度鉴权分析

**使用 `scripts/auth_analyzer.py`**：

```bash
python temp-scripts/auth_analyzer.py output_dir/js/ auth_report.json
```

自动提取：
- Cookie 操作（读/写/工具函数）
- CSRF 机制（header/cookie/字段）
- Token 流程（获取/存储/传递/刷新/过期）
- 请求拦截器（axios/fetch 包装/头注入）
- 签名算法（MD5/SHA256/HMAC/AES/参数排序签名）
- **参数签名机制**（WBI 等特化签名、打乱数组）
- OAuth/OIDC 流程
- **JWT 解码**（自动 base64 解码 payload，列出字段）
- **URL 中的 API Key 检测**
- **WebSocket 鉴权**
- API 基础 URL（含 Vite/Next.js 环境变量）

### 步骤四：GraphQL 深度分析（检测到 GraphQL 时）

**使用 `scripts/gql_analyzer.py`**：

```bash
# 从JS源码提取操作定义
python temp-scripts/gql_analyzer.py output_dir/js/ gql_report.json

# 尝试 Introspection 查询（获取完整 schema）
python temp-scripts/gql_analyzer.py --introspect https://api.example.com/graphql schema.json
```

自动提取：
- GraphQL 端点 URL
- 操作定义（query/mutation/subscription + 名称 + 字段）
- Fragment 定义
- `__typename` 类型推断
- 客户端配置（Apollo/URQL/Relay）
- 持久化查询（APQ）

### 步骤五：产出文档

**读取 `references/report_template.md`，按模板填写，保存为 `{网站名}_report.md`。**

文档的核心价值是**下次直接用**——不用重新分析，直接看"可操作清单"章节。

---

## 操作模式：直接执行任务

用户说"帮我 xxx"，且已有凭证时，直接操作：

### 1. 查找操作对应的接口

优先查已有的分析文档；没有文档则先做分析。

### 2. 构造请求

**Cookie 鉴权（最常见）**
```python
import urllib.request, urllib.parse, ssl, json

def api_request(method, base_url, path, params=None, data=None, cookies='', extra_headers=None):
    url = base_url + path
    if params:
        url += '?' + urllib.parse.urlencode(params)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Cookie': cookies,
        'Referer': base_url,
        'Accept-Encoding': 'identity',
    }
    if extra_headers:
        headers.update(extra_headers)

    body = None
    if data:
        body = urllib.parse.urlencode(data).encode()
        headers['Content-Type'] = 'application/x-www-form-urlencoded'

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
        return json.loads(resp.read().decode())
```

**Bearer Token 鉴权**
```python
headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json',
}
```

**GraphQL 请求**
```python
import json

def gql_request(endpoint, query, variables=None, headers=None):
    body = json.dumps({'query': query, 'variables': variables or {}})
    req = urllib.request.Request(
        endpoint,
        data=body.encode(),
        headers={**headers, 'Content-Type': 'application/json'}
    )
    # ... 同上发送请求
```

**参数签名（通用模式）**

很多网站使用"参数排序 + 拼接 + 密钥哈希"的签名方式：
```python
import hashlib, time

def sign_params(params: dict, secret: str) -> dict:
    """通用参数签名：按key排序拼接，加时间戳，HMAC-MD5签名"""
    params['timestamp'] = str(int(time.time()))
    # 按 key 字母序排序拼接
    query = '&'.join(f'{k}={v}' for k, v in sorted(params.items()))
    # 签名
    sign = hashlib.md5((query + secret).encode()).hexdigest()
    params['sign'] = sign
    return params
```

### 3. 多步操作链

有些操作需要先后调多个接口，按依赖顺序执行：

```
示例（通用）：
① GET /api/user/info       → 拿用户标识和签名密钥
② 生成签名                 → 用 ① 的密钥签名
③ GET /api/data/list       → 获取数据（带签名）
④ POST /api/data/action    → 执行操作（需 CSRF Token）
```

---

## 产出文档说明

分析结束后，产出 `{网站名}_report.md`在用户所调用本技能的项目的根目录里，包含：

| 章节 | 内容 | 主要用途 |
|------|------|----------|
| 基本信息 | 技术栈、JS 文件、Source Map | 快速了解网站结构 |
| 凭证说明 | 需要的凭证及获取方式 | 知道需要提供什么 |
| **可直接执行的操作** | 操作清单 + 调用模板 | **核心交付，下次直接用** |
| 鉴权与签名 | 凭证传递方式、签名机制 | 理解鉴权流程 |
| 完整 API 接口清单 | 按模块分组的接口表 | 找到对应接口 |
| GraphQL（如有） | 操作定义、端点、schema | GraphQL 专用 |
| WebSocket（如有） | WS 端点、鉴权方式 | 实时通信 |
| 页面功能地图 | 路径 → 功能映射 | 了解网站功能全貌 |
| 附录 | JS 清单、域名体系、分析局限 | 补充信息 |

报告模板在 `references/report_template.md`。

---

## 通用脚本

| 脚本 | 用途 |
|------|------|
| `scripts/web_fetch_source.py` | 一键抓取：HTML → JS（并行+chunk递归）→ API端点 → Source Map → 报告 |
| `scripts/auth_analyzer.py` | 鉴权深度分析：Cookie/CSRF/Token/签名/JWT/OAuth/WS鉴权 |
| `scripts/gql_analyzer.py` | GraphQL分析：操作提取/Introspection/客户端配置 |

**使用**：复制到项目 `temp-scripts/` 目录运行。

---

## 工具使用优先级

| 场景 | 工具 |
|------|------|
| 获取原始 HTML / JS | Python `urllib.request` 脚本（`web_fetch_source.py`） |
| 搜索 JS 中的模式 | Python `re` 模块，写脚本批量处理 |
| 发起 API 调用 | Python 脚本 或 `curl`（写成 `.ps1` 执行） |
| GraphQL 分析 | `gql_analyzer.py` + Introspection |
| 想用 web_fetch | ❌ 只用于获取人类可读内容，不用于源码获取 |

所有脚本放在项目 `temp-scripts/` 目录，文件头部加中文注释。

---