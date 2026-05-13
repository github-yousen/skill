# Cloudflare Ops

[中文](#chinese) | [English](#english)

---

<a id="chinese"></a>

## 这是什么

用于操作 Cloudflare 资源的技能 —— 部署和管理 Pages 站点、Workers、KV 绑定 Worker 和反向代理。

### 能做什么

1. **部署** — 将静态站点推送到 Cloudflare Pages，或通过 wrangler 部署 Worker
2. **管理** — 创建或更新 Pages 项目、列出已有部署、管理 KV 命名空间绑定
3. **代理** — 快速搭建并部署轻量反向代理 Worker 或 Pages Function
4. **引导** — 首次运行时自动检测凭证，若缺失则引导你完成配置

### 触发场景

- "把我的站点部署到 Cloudflare Pages"
- "更新我的 Cloudflare Worker"
- "创建一个反向代理 Worker，转发到 ..."
- "列出我的 Cloudflare Pages 项目"
- "帮我配置 KV 绑定的 Worker"

---

## 快速开始

### 第一步：获取 Cloudflare 凭证

#### 获取 API Token

1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. 点击右上角头像 → **My Profile**
3. 左侧菜单选择 **API Tokens** → **Create Token**
4. 选择模板 **Edit Cloudflare Workers**（或自定义权限）
   - 推荐权限：`Account - Cloudflare Pages:Edit`、`Account - Workers Scripts:Edit`
5. 点击 **Continue to summary** → **Create Token**
6. 复制 Token（**只显示一次，立即保存**）

#### 获取 Account ID

1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. 进入 **Workers & Pages** 页面
3. 右侧栏可见 **Account ID**（32 位十六进制字符串）

### 第二步：保存凭证

将凭证保存到本技能根目录的 `key.json`：

```json
{
  "CLOUDFLARE_API_TOKEN": "你的_API_Token",
  "CLOUDFLARE_ACCOUNT_ID": "你的_Account_ID",
  "CLOUDFLARE_EMAIL": "你的_邮箱（可选）"
}
```

> 文件路径：`<skills_dir>/cloudflare-ops/key.json`  
> 此文件已在 `.gitignore` 中排除，不会上传到任何仓库。

### 第三步：使用脚本

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
├── key.json                        # 凭证文件（本地，不上传）
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

## 许可证

MIT License

---

<a id="english"></a>

## What Is This

A skill for operating Cloudflare resources — deploy and manage Pages sites, Workers, KV-backed Workers, and reverse proxy patterns.

### What It Can Do

1. **Deploy** — Push static sites to Cloudflare Pages, or deploy Workers via wrangler
2. **Manage** — Create or update Pages projects, list existing deployments, manage KV namespace bindings
3. **Proxy** — Scaffold and deploy lightweight reverse proxy Workers or Pages Functions
4. **Guide** — On first run, auto-detect credentials; if missing, walk you through setup

### Trigger Scenarios

- "Deploy my site to Cloudflare Pages"
- "Update my Cloudflare Worker"
- "Create a reverse proxy Worker that forwards to ..."
- "List my Cloudflare Pages projects"
- "Help me set up a KV-backed Worker"

---

## Quick Start

### Step 1: Get Cloudflare Credentials

#### Get API Token

1. Log in to [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. Click avatar (top right) → **My Profile**
3. Left sidebar → **API Tokens** → **Create Token**
4. Choose template **Edit Cloudflare Workers** (or custom)
   - Recommended: `Account - Cloudflare Pages:Edit`, `Account - Workers Scripts:Edit`
5. Click **Continue to summary** → **Create Token**
6. Copy the token (**shown only once — save it immediately**)

#### Get Account ID

1. Log in to [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. Go to **Workers & Pages**
3. Find **Account ID** in the right sidebar (32-char hex string)

### Step 2: Save Credentials

Save to `key.json` in this skill's root directory:

```json
{
  "CLOUDFLARE_API_TOKEN": "your_api_token",
  "CLOUDFLARE_ACCOUNT_ID": "your_account_id",
  "CLOUDFLARE_EMAIL": "your_email (optional)"
}
```

> Path: `<skills_dir>/cloudflare-ops/key.json`  
> This file is excluded via `.gitignore` and will never be pushed to any repository.

### Step 3: Use Scripts

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
├── SKILL.md                        # Skill definition (Chinese)
├── README.md                       # This file (bilingual)
├── key.json                        # Credentials (local only, not committed)
├── scripts/
│   ├── deploy_pages.py             # Pages static site deployment
│   ├── deploy_worker.py            # Worker deployment
│   └── cloudflare_manager.py       # Pages project management + proxy scaffold
└── references/
    ├── pages.md                    # Pages deployment notes and API reference
    ├── workers.md                  # Worker notes, wrangler layout, KV binding
    └── proxy-patterns.md           # Reverse proxy and KV bridge patterns
```

---

## License

MIT License
