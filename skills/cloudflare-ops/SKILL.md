---
name: cloudflare-ops
description: 操作 Cloudflare 资源，用于静态站点和轻量边缘服务。当用户需要部署或更新 Cloudflare Pages、部署或更新 Cloudflare Workers、管理 KV 绑定的 Worker、创建简单反向代理 Worker 或 Pages Functions、列出已有 Pages 项目、或验证 Cloudflare 部署前置条件时，使用本技能。
---

# Cloudflare 运维技能

本技能用于 Cloudflare 部署和轻量边缘运维。

## 支持的能力

1. 将静态站点部署到 **Cloudflare Pages**
2. 创建或更新 **Cloudflare Pages 项目**
3. 使用 `wrangler` 部署 **Cloudflare Workers**
4. 处理 Worker 的 **KV 命名空间绑定**
5. 生成并部署简单的 **反向代理 Worker / Pages Function**
6. 通过 Cloudflare REST API 列出已有 Pages 项目

## 凭证管理

### 首次运行

首次使用时，技能将检测本技能根目录下的 `key.json` 文件是否存在。若不存在，主动引导用户获取凭证并完成配置。

**如何在 Cloudflare 上获取所需凭证：**

#### 1. 获取 API Token
1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. 点击右上角头像 → **My Profile**
3. 左侧菜单选择 **API Tokens**
4. 点击 **Create Token**
5. 选择模板 **Edit Cloudflare Workers**（或点击 Custom Token 自定义）
   - 权限建议：`Account - Cloudflare Pages:Edit`、`Account - Workers Scripts:Edit`、`Zone - Workers Routes:Edit`
6. 点击 **Continue to summary** → **Create Token**
7. 复制生成的 Token（**只显示一次，请立即保存**）

#### 2. 获取 Account ID
1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. 进入任意一个域名或进入 **Workers & Pages** 页面
3. 右侧栏（或 URL 中）可找到 **Account ID**，格式为 32 位十六进制字符串

### 凭证存储

获取凭证后，保存到本技能根目录下的 `key.json`（此文件不会上传到任何仓库）：

```json
{
  "CLOUDFLARE_API_TOKEN": "你的_API_Token",
  "CLOUDFLARE_ACCOUNT_ID": "你的_Account_ID",
  "CLOUDFLARE_EMAIL": "你的_Cloudflare_邮箱（可选）"
}
```

> `key.json` 路径：`<skills_dir>/cloudflare-ops/key.json`

### 运行时读取凭证

脚本优先从 `key.json` 读取，其次回退到环境变量：

```python
import json, os, pathlib

def load_credentials():
    key_file = pathlib.Path(__file__).parent.parent / "key.json"
    if key_file.exists():
        with open(key_file) as f:
            creds = json.load(f)
        return creds
    # 回退到环境变量
    return {
        "CLOUDFLARE_API_TOKEN": os.environ.get("CLOUDFLARE_API_TOKEN", ""),
        "CLOUDFLARE_ACCOUNT_ID": os.environ.get("CLOUDFLARE_ACCOUNT_ID", ""),
    }
```

## 脚本使用

### 1）Pages 部署

```bash
python3 scripts/deploy_pages.py \
  --site-dir /absolute/path/to/site \
  --project-name my-pages-project \
  --branch main
```

### 2）Pages 项目管理 / 反向代理脚手架

```bash
python3 scripts/cloudflare_manager.py list-pages
python3 scripts/cloudflare_manager.py create-pages --project-name my-pages-project --branch main
python3 scripts/cloudflare_manager.py generate-pages-proxy --target-url https://example.com/api
```

### 3）Worker 部署

```bash
python3 scripts/deploy_worker.py \
  --worker-dir /absolute/path/to/worker-project
```

## 工作流程

1. 检查技能根目录下是否存在 `key.json`，若不存在则引导用户完成凭证配置。
2. 确定目标资源类型：Pages、Worker、KV 绑定 Worker 或反向代理。
3. 确认本地源码目录或生成的模板。
4. 使用对应脚本执行操作。
5. 汇报最终 URL、部署目标以及后续配置项（如自定义域名、KV ID 等）。

## Pages 注意事项

- 优先使用构建产物目录，而非源码根目录，除非根目录本身就是静态站点。
- 简单 HTML 站点的部署目录通常包含 `index.html`。
- 框架项目的部署目录可能是 `dist/`、`build/` 或 `.output/public/`。

## Workers 注意事项

- Worker 项目通常包含 `wrangler.toml` 以及 `worker.js`、`index.js` 或 `src/index.js`。
- 如果使用 KV，确保 `wrangler.toml` 中存在正确的命名空间绑定。
- 使用 `wrangler deploy` 或 `npx --yes wrangler@latest deploy` 进行部署。

## 反向代理模式

本技能支持两种常见代理模式：

1. **Pages Function / Worker 反向代理**
   - 将传入请求转发到目标上游
   - 保留请求方法和请求体
   - 在需要浏览器访问的场景下添加宽松 CORS 头
2. **KV 桥接 Worker**
   - 使用 KV 做轻量收件箱/历史记录持久化
   - 适合简单中转、类队列轮询或状态快照

## 内置参考文档

- `references/pages.md`：Pages 部署说明和 API 用法
- `references/workers.md`：Worker 部署说明、wrangler 目录结构、KV 绑定示例
- `references/proxy-patterns.md`：反向代理和 KV 桥接模式

## 输出预期

任务成功后，请汇报：

- 使用的资源类型
- 本地源码目录
- 项目 / Worker 名称
- 分支或部署环境
- 最终 URL 或端点
- 任何缺失的后续配置，如自定义域名、KV ID 或密钥绑定
