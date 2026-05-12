# Web Reverse Engineer

[English](#english) | [中文](#chinese)

---

<a id="english"></a>

## What Is This

A skill that reverse-engineers websites by fetching and analyzing their HTML/JS source code — not through browser rendering, but through raw source extraction. It discovers API endpoints, authentication flows, page structure, and data flows from the frontend code.

### What It Can Do

1. **Understand** — Given a website, figure out what it does: every API endpoint, page route, and data structure
2. **Operate** — Given credentials (Cookie / Token), directly call those APIs to get things done — no browser needed
3. **Persist** — Produce a complete analysis document, so next time you can skip the reverse engineering entirely

### How It Works

1. Fetch the target page's raw HTML, extract all `<script src>` references
2. Batch-download every JS file (including code-split chunks)
3. Extract API endpoints via regex patterns (method + path, baseURL variables, full domain URLs)
4. Analyze authentication: Cookie operations, CSRF tokens, request interceptors, signing algorithms
5. Identify tech stack (Next.js / Nuxt / Vue SSR / gRPC-Web / GraphQL / Source Maps)
6. Output a structured analysis report with actionable API call templates

### Trigger Scenarios

- "Analyze this website" / "Reverse engineer this site"
- "What APIs does this website have?"
- "Help me scrape the endpoints from ..."
- Or simply paste a URL and say "help me look at this website"

---

## Quick Start

### Install

Clone this skill into your AI tool's skills directory:

```bash
git clone https://github.com/github-yousen/web-reverse-engineer.git <your-skills-dir>/web-reverse-engineer
```

### Use

Tell the AI which website to analyze, and provide a curl with your auth info:

```
Analyze https://www.example.com
Here's a curl with my auth:
curl 'https://www.example.com/api/user' -H 'Cookie: session=abc123' -H 'X-CSRF-Token: xyz'
```

### How to Get the curl

The curl carries your login session. Get it from your browser:

1. Open the target website and log in
2. Press **F12** → **Network** tab
3. Browse the site normally — API requests will appear
4. Find a request **to the target site's domain** — make sure not to copy requests from browser extensions or other domains
5. Right-click that request → **Copy** → **Copy as cURL**
6. Paste into your AI chat — it contains your Cookie, CSRF token, and other auth headers

Without a curl, the skill can still analyze the public-facing surface. With a curl, it unlocks the full authenticated API.

---

## Example: Generating a Dedicated Skill with Skill Creator

The analysis output from this skill can be fed into [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator) to generate a permanent, site-specific skill:

```
URL + curl (from F12 → Network → Copy as cURL)
                    ↓
        web-reverse-engineer analyzes the site
                    ↓
        Extracts: APIs, auth flow, data structures
                    ↓
        skill-creator packages into a dedicated skill
                    ↓
        Next time: call that skill directly, no re-analysis
```

For instance: you provide `https://www.example.com` + a curl copied from your browser. This skill reverse-engineers the site's API — discovers endpoints for listing, searching, creating, and updating resources. Then skill-creator can package that analysis into a dedicated `example` skill, permanently reusable without re-analysis.

---

## Project Structure

```
web-reverse-engineer/
├── SKILL.md                    # Skill definition (Chinese)
├── SKILL_EN.md                 # Skill definition (English)
├── README.md                   # This file
├── scripts/
│   ├── web_fetch_source.py     # One-click: HTML → JS → API endpoint extraction
│   └── auth_analyzer.py        # Auth deep analysis: Cookie/CSRF/Token/Signing
└── references/
    └── report_template.md      # Analysis report template
```

---

## Scripts

### web_fetch_source.py

One-click source code fetching and analysis:

```bash
python scripts/web_fetch_source.py https://target-website.com/ output_dir
```

Automatically: Fetch HTML → Extract JS list → Batch fetch JS → Extract API endpoints → Save analysis report

### auth_analyzer.py

Deep authentication analysis on JS files:

```bash
python scripts/auth_analyzer.py ./output_dir/js/ auth_report.json
```

Extracts: Cookie operations, CSRF mechanisms, Token flows, Request interceptors, Signing algorithms, OAuth flows

---

## Important Notes

1. **Don't use AI-summarized fetchers for source code** — They return readable summaries where `<script src>` tags are lost. Always fetch raw HTML.
2. **Don't inline Python in PowerShell** — Quote conflicts occur; write `.py` files first.
3. **Main JS isn't everything** — Modern frontends use code splitting; search for chunk references.
4. **HTTP methods and paths are often separate in JS** — Use regex to capture both simultaneously.
5. **Provide curl with auth** — Without credentials, you can only analyze the public surface. A curl from your browser unlocks the full API.

---

## License

MIT License

---

<a id="chinese"></a>

## 这是什么

一个网站逆向分析 skill，通过抓取和分析 HTML/JS 源码（不是浏览器渲染，而是原始源码提取）来发现 API 端点、鉴权流程、页面结构和数据流。

### 能做什么

1. **理解** — 给定一个网站，搞清楚它能做什么：每个 API 端点、页面路由、数据结构
2. **操作** — 给定凭证（Cookie / Token），直接调用 API 完成任务 —— 不需要浏览器
3. **沉淀** — 产出完整的分析文档，下次不用再逆向

### 工作原理

1. 抓取目标页面的原始 HTML，提取所有 `<script src>` 引用
2. 批量下载每个 JS 文件（包括代码分割的 chunk）
3. 通过正则提取 API 端点（方法+路径、baseURL 变量、完整域名 URL）
4. 分析鉴权：Cookie 操作、CSRF Token、请求拦截器、签名算法
5. 识别技术栈（Next.js / Nuxt / Vue SSR / gRPC-Web / GraphQL / Source Map）
6. 输出结构化分析报告，包含可直接调用的 API 模板

### 触发场景

- "分析网站"、"逆向网站"、"网站接口"、"抓接口"
- "网站源码分析"、"逆向工程"、"分析API"
- "爬取接口"、"网站结构分析"、"网站白盒分析"
- 或者直接给一个 URL 说"帮我看看这个网站"

---

## 快速开始

### 安装

将本 skill 克隆到你的 AI 工具的 skills 目录：

```bash
git clone https://github.com/github-yousen/web-reverse-engineer.git <你的skills目录>/web-reverse-engineer
```

### 使用

告诉 AI 你想分析哪个网站，并提供含鉴权信息的 curl：

```
分析 https://www.example.com
这是我从浏览器复制的 curl：
curl 'https://www.example.com/api/user' -H 'Cookie: session=abc123' -H 'X-CSRF-Token: xyz'
```

### 如何获取 curl

curl 携带你的登录态，从浏览器获取：

1. 打开目标网站并登录
2. 按 **F12** → **网络（Network）** 标签
3. 正常浏览网站 — API 请求会不断出现
4. 找到一条**目标网站域名**的请求，注意不要复制到浏览器扩展等其他域名的请求
5. **右键** → **复制** → **复制为 cURL**
6. 粘贴给 AI — 里面包含了你的 Cookie、CSRF Token 等鉴权信息

没有 curl 也能分析公开页面，有 curl 才能解锁完整鉴权后的 API。

---

## 示例：配合 Skill Creator 生成专属 Skill

本 skill 的分析输出可以传入 [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator) 来生成永久的、针对特定网站的 skill：

```
URL + curl（从 F12 → 网络 → 右键复制为 cURL 获取）
                    ↓
        web-reverse-engineer 分析网站
                    ↓
        提取：API、鉴权流程、数据结构
                    ↓
        skill-creator 打包成专属 skill
                    ↓
        下次：直接调用该 skill，无需重新分析
```

例如：你提供 `https://www.example.com` + 从浏览器复制的 curl。本 skill 逆向分析该网站的 API —— 发现列表、搜索、创建、更新等接口。然后 skill-creator 可以把分析结果打包成一个专属的 `example` skill，永久可用，无需再次逆向。

---

## 项目结构

```
web-reverse-engineer/
├── SKILL.md                    # 技能定义文件（中文）
├── SKILL_EN.md                 # 技能定义文件（English）
├── README.md                   # 本文件
├── scripts/
│   ├── web_fetch_source.py     # 一键抓取：HTML → JS → API端点提取
│   └── auth_analyzer.py        # 鉴权深度分析：Cookie/CSRF/Token/签名
└── references/
    └── report_template.md      # 分析报告模板
```

---

## 脚本说明

### web_fetch_source.py

一键完成网站源码抓取和分析：

```bash
python scripts/web_fetch_source.py https://target-website.com/ output_dir
```

自动完成：抓取 HTML → 提取 JS 列表 → 批量抓取 JS → 提取 API 端点 → 保存分析报告

### auth_analyzer.py

对 JS 文件进行鉴权深度分析：

```bash
python scripts/auth_analyzer.py ./output_dir/js/ auth_report.json
```

提取内容：Cookie 操作、CSRF 机制、Token 流程、请求拦截器、签名算法、OAuth 流程

---

## 关键注意事项

1. **不要用 AI 摘要工具提取源码** — 它们返回可读摘要，`<script src>` 标签会丢失。始终抓取原始 HTML
2. **PowerShell 中不要内联 Python** — 引号冲突，应先写 `.py` 文件再执行
3. **主入口 JS 不是全部** — 现代前端做代码分割，需搜索 chunk 引用
4. **HTTP 方法和路径在 JS 中常分离** — 需用正则同时捕获
5. **提供含鉴权的 curl** — 没有凭证只能分析公开表面，浏览器复制的 curl 能解锁完整 API

---

## 许可证

MIT License
