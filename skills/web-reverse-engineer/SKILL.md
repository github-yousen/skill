---
name: web-reverse-engineer
description: |
  网站源码逆向分析技能：给定一个网站URL，通过抓取HTML/JS源码（而非浏览器渲染）逆向分析网站的接口、页面布局、鉴权流程和数据流。
  当用户提到"分析网站"、"逆向网站"、"网站接口"、"抓接口"、"网站源码分析"、"逆向工程"、"分析API"、"爬取接口"、"网站结构分析"、
  "给我分析一下这个网站"、"这个网站有什么接口"、"逆向这个站"、"破解网站接口"、"网站白盒分析"时触发此技能。
  即使用户只是给了一个URL说"帮我看看这个网站"，也应触发此技能并主动进行源码逆向分析。
---

# 网站理解与操作技能

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

### 陷阱4：HTTP 方法和路径在 JS 中是分离的

大多数框架写法是 `{method: 'GET', url: '/api/xxx'}`，需要专门正则同时捕获两者：
```python
re.findall(r'method:\s*["\']( GET|POST|PUT|DELETE|PATCH)["\'].*?url:\s*["\']([^"\']+)["\']', content)
```

### 陷阱5：主入口 JS 不是全部

现代前端（Vite/Webpack）做代码分割，业务逻辑在 chunk 文件。
需要在主 JS 中搜索 chunk 引用，按需抓取。

---

## 分析模式：源码获取与理解

### 步骤一：抓取原始 HTML

**使用 `scripts/web_fetch_source.py`（一键完成）**，或手动：

```bash
python temp-scripts/web_fetch_source.py https://目标网站.com/ output_dir
```

脚本自动完成：抓 HTML → 提取 JS 列表 → 批量抓取 JS → 提取 API 端点 → 保存分析报告。

### 步骤二：识别技术栈

从 HTML 快速判断，决定后续分析策略：

| 特征 | 技术栈 | 影响 |
|------|--------|------|
| `__NEXT_DATA__` | Next.js | 内联 JSON 含首屏数据和路由 |
| `__NUXT__` / `__INITIAL_STATE__` | Nuxt / Vue SSR | 内联状态有用户数据 |
| `window.__pinia` | Pinia | 内联状态树可直接解析 |
| `twirp/` 路径 | gRPC-Web | 全部 POST，请求体是 JSON |
| `graphql` / `__typename` | GraphQL | 操作名即功能，单端点多查询 |
| `sourceMappingURL` | 有 Source Map | **优先获取**，可拿未混淆源码 |

### 步骤三：提取接口

对每个 JS 文件批量正则搜索（优先级从高到低）：

```python
# 1. 最信息量：带方法的对象格式
method_url = re.findall(
    r'method:\s*["\']( GET|POST|PUT|DELETE|PATCH)["\'].*?url:\s*["\']([^"\']+)["\']',
    content
)

# 2. 常见路径前缀
apis = re.findall(r'["\'`](/(?:api|x|v[0-9]+|pgc|graphql)/[a-zA-Z0-9_/.-]+)["\'`]', content)

# 3. 完整域名 URL
full_urls = re.findall(r'(https?://api\.[a-z0-9.-]+/[a-zA-Z0-9_/.-]+)', content)

# 4. baseURL 变量
base = re.findall(r'(?:baseUrl|baseURL|API_URL)\s*[:=]\s*["\']([^"\']+)["\']', content)
```

**去重**：以 `{method}:{path}` 为 key 去重，过滤静态资源后缀（`.js/.css/.png`等）。

### 步骤四：理解鉴权

**使用 `scripts/auth_analyzer.py`，或手动搜索。**

```bash
python temp-scripts/auth_analyzer.py output_dir/js/ auth_report.json
```

重点关注：

| 搜索关键词 | 目的 |
|-----------|------|
| `interceptors.request.use` | 找请求拦截器，看统一加了什么头 |
| `localStorage.setItem` / `sessionStorage` | 找 Token 存储位置 |
| `csrf` / `bili_jct` / `X-CSRF` | 找 CSRF 机制 |
| `Authorization` / `Bearer` | 找 Bearer Token 方式 |
| `w_rid` / `wts` / `mixin_key` | 找 WBI 类签名机制 |
| `withCredentials: true` | 确认 Cookie 跨域携带 |

**WBI 签名模式**（B站等网站使用的参数签名，遇到时逆向）：
1. 从导航接口拿 `img_key` + `sub_key`
2. 按打乱数组重排拼接取前32位得 `mixin_key`
3. 参数按 key 字母序排序拼接，过滤 `!'()*`
4. `w_rid = MD5(querystring + mixin_key)`，`wts = 秒级时间戳`

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

def bilibili_request(method, path, params=None, data=None, cookies=''):
    base = 'https://api.bilibili.com'
    url = base + path
    if params:
        url += '?' + urllib.parse.urlencode(params)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Cookie': cookies,
        'Referer': 'https://www.bilibili.com/',
    }

    body = None
    if data:
        body = urllib.parse.urlencode(data).encode()
        headers['Content-Type'] = 'application/x-www-form-urlencoded'

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, context=ctx) as resp:
        return json.loads(resp.read().decode())
```

**Bearer Token 鉴权**
```bash
curl -X GET "https://api.example.com/api/xxx" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json"
```

**需要 WBI 签名**
```python
import hashlib, time, re, urllib.parse

def wbi_sign(params: dict, img_key: str, sub_key: str) -> dict:
    tab = [46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,
           27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13,
           37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,
           22,25,54,21,56,59,6,63,57,62,11,36,20,34,44,52]
    orig = img_key + sub_key
    mixin_key = ''.join(orig[i] for i in tab if i < len(orig))[:32]
    params['wts'] = str(int(time.time()))
    query = '&'.join(
        f'{k}={re.sub(r"[!\'()*]", "", str(v))}'
        for k, v in sorted(params.items())
    )
    params['w_rid'] = hashlib.md5((query + mixin_key).encode()).hexdigest()
    return params
```

### 3. 多步操作链

有些操作需要先后调多个接口，按依赖顺序执行：

```
示例（B站）：
① GET /x/web-interface/nav          → 拿 WBI keys（需 SESSDATA）
② 生成 w_rid + wts                  → 用 ① 的 keys 签名
③ GET /x/web-interface/wbi/search   → 搜索（带签名）
④ POST /x/v2/history/toview/add     → 添加稍后再看（需 csrf=bili_jct）
```

---

## 产出文档说明

分析结束后，产出 `{网站名}_report.md`，包含：

| 章节 | 内容 | 主要用途 |
|------|------|----------|
| 基本信息 | 技术栈、JS 文件、Source Map | 快速了解网站结构 |
| 鉴权流程 | 凭证清单、传递方式、签名机制 | 知道需要提供什么 |
| API 接口清单 | 按模块分组的接口表 | 找到对应接口 |
| 页面路由 | 路径 → 功能映射 | 了解网站功能全貌 |
| 关键数据结构 | 重要接口的响应格式 | 解析返回数据 |
| **可直接调用的操作** | 操作清单 + 调用模板 | **核心交付，下次直接用** |
| 附录 | JS 清单、域名体系 | 补充信息 |

报告模板在 `references/report_template.md`。

---

## 通用脚本

| 脚本 | 用途 |
|------|------|
| `scripts/web_fetch_source.py` | 一键抓取：HTML → JS → API端点提取 |
| `scripts/auth_analyzer.py` | 鉴权深度分析：Cookie/CSRF/Token/签名 |

**使用**：复制到项目 `temp-scripts/` 目录运行。

---

## 工具使用优先级

| 场景 | 工具 |
|------|------|
| 获取原始 HTML / JS | Python `urllib.request` 脚本 |
| 搜索 JS 中的模式 | Python `re` 模块，写脚本批量处理 |
| 发起 API 调用 | Python 脚本 或 `curl`（写成 `.ps1` 执行） |
| 想用 web_fetch | ❌ 只用于获取人类可读内容，不用于源码获取 |

所有脚本放在项目 `temp-scripts/` 目录，文件头部加中文注释。
