# Cloudflare Ops

[English](#english) | [中文](#chinese)

---

<a id="english"></a>

## What Is This

A skill for operating Cloudflare resources — deploy and manage Pages sites, Workers, KV-backed Workers, and reverse proxy patterns, all without storing credentials in the repository.

### What It Can Do

1. **Deploy** — Push static sites to Cloudflare Pages, or deploy Workers via wrangler
2. **Manage** — Create or update Pages projects, list existing deployments, manage KV namespace bindings
3. **Proxy** — Scaffold and deploy lightweight reverse proxy Workers or Pages Functions
4. **Secure** — Read credentials from environment variables or agent memory only; never write them to files

### Trigger Scenarios

- "Deploy my site to Cloudflare Pages"
- "Update my Cloudflare Worker"
- "Create a reverse proxy Worker that forwards to ..."
- "List my Cloudflare Pages projects"
- "Help me set up a KV-backed Worker"

---

## Quick Start

### Required Credentials

```bash
export CLOUDFLARE_API_TOKEN=...
export CLOUDFLARE_ACCOUNT_ID=...
```

Optional:

```bash
export CLOUDFLARE_PAGES_BRANCH=main
```

### Scripts

```bash
# Deploy a static site to Pages
python3 scripts/deploy_pages.py \
  --site-dir /path/to/site \
  --project-name my-pages-project \
  --branch main

# Manage Pages projects
python3 scripts/cloudflare_manager.py list-pages
python3 scripts/cloudflare_manager.py create-pages --project-name my-project --branch main
python3 scripts/cloudflare_manager.py generate-pages-proxy --target-url https://api.example.com

# Deploy a Worker
python3 scripts/deploy_worker.py \
  --worker-dir /path/to/worker-project
```

---

## Project Structure

```
cloudflare-ops/
├── SKILL.md                        # 技能定义（中文）
├── README.md                       # 本文件（中英双语）
├── scripts/
│   ├── deploy_pages.py             # Pages 静态站点部署
│   ├── deploy_worker.py            # Worker 部署
│   └── cloudflare_manager.py       # Pages 项目管理 + 反向代理脚手架
└── references/
    ├── pages.md                    # Pages 部署说明与 API 参考
    ├── workers.md                  # Worker 部署说明、wrangler 布局、KV 绑定
    └── proxy-patterns.md           # 反向代理和 KV 桥接模式
```

---

## Security

This skill does **not** store `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, login email, KV IDs, or any other credentials. Always provide credentials at runtime via environment variables or agent memory.

---

## License

MIT License

---

<a id="chinese"></a>

## 这是什么

用于操作 Cloudflare 资源的技能 —— 部署和管理 Pages 站点、Workers、KV 绑定 Worker 和反向代理，全程不在仓库中存储任何凭证。

### 能做什么

1. **部署** — 将静态站点推送到 Cloudflare Pages，或通过 wrangler 部署 Worker
2. **管理** — 创建或更新 Pages 项目、列出已有部署、管理 KV 命名空间绑定
3. **代理** — 快速搭建并部署轻量反向代理 Worker 或 Pages Function
4. **安全** — 凭证仅从环境变量或 Agent 记忆中读取，绝不写入文件

### 触发场景

- "把我的站点部署到 Cloudflare Pages"
- "更新我的 Cloudflare Worker"
- "创建一个反向代理 Worker，转发到 ..."
- "列出我的 Cloudflare Pages 项目"
- "帮我配置 KV 绑定的 Worker"

---

## 快速开始

### 所需凭证

```bash
export CLOUDFLARE_API_TOKEN=...
export CLOUDFLARE_ACCOUNT_ID=...
```

可选：

```bash
export CLOUDFLARE_PAGES_BRANCH=main
```

### 脚本使用

```bash
# 部署静态站点到 Pages
python3 scripts/deploy_pages.py \
  --site-dir /path/to/site \
  --project-name my-pages-project \
  --branch main

# 管理 Pages 项目
python3 scripts/cloudflare_manager.py list-pages
python3 scripts/cloudflare_manager.py create-pages --project-name my-project --branch main
python3 scripts/cloudflare_manager.py generate-pages-proxy --target-url https://api.example.com

# 部署 Worker
python3 scripts/deploy_worker.py \
  --worker-dir /path/to/worker-project
```

---

## 项目结构

```
cloudflare-ops/
├── SKILL.md                        # 技能定义（中文）
├── README.md                       # 本文件（中英双语）
├── scripts/
│   ├── deploy_pages.py             # Pages 静态站点部署
│   ├── deploy_worker.py            # Worker 部署
│   └── cloudflare_manager.py       # Pages 项目管理 + 反向代理脚手架
└── references/
    ├── pages.md                    # Pages 部署说明与 API 参考
    ├── workers.md                  # Worker 部署说明、wrangler 布局、KV 绑定
    └── proxy-patterns.md           # 反向代理和 KV 桥接模式
```

---

## 安全

本技能不存储 `CLOUDFLARE_API_TOKEN`、`CLOUDFLARE_ACCOUNT_ID`、登录邮箱、KV ID 或任何其他凭证。请始终通过环境变量或 Agent 记忆在运行时提供凭证。

---

## 许可证

MIT License
