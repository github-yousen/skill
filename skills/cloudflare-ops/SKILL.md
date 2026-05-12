---
name: cloudflare-ops
description: Operate Cloudflare resources for static sites and lightweight edge services. Use when a user wants to deploy or update Cloudflare Pages, deploy or update Cloudflare Workers, manage KV-backed Worker bindings, create simple reverse proxy Workers or Pages Functions, list existing Pages projects, or validate Cloudflare deployment prerequisites. Never store Cloudflare API tokens, account IDs, emails, or other credentials inside this skill or any public repository; collect them at runtime or from user memory/environment only.
---

# Cloudflare Ops

Use this skill for Cloudflare deployment and lightweight edge operations.

## Covered capabilities

1. Deploy static sites to **Cloudflare Pages**
2. Create or update **Cloudflare Pages projects**
3. Deploy **Cloudflare Workers** with `wrangler`
4. Work with **KV namespace bindings** for Workers
5. Generate and deploy a simple **reverse proxy Worker / Pages Function**
6. List existing Pages projects through Cloudflare REST API

## Security rules

- Never write `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, login email, KV IDs, or other secrets into this skill or a public repository.
- Read credentials from runtime environment variables, user input, or agent memory.
- If the user asks to remember Cloudflare credentials, store them in agent memory, not in the skill files.

## Required runtime credentials

```bash
export CLOUDFLARE_API_TOKEN=...
export CLOUDFLARE_ACCOUNT_ID=...
```

Optional:

```bash
export CLOUDFLARE_PAGES_BRANCH=main
```

## Scripts

### 1) Pages deployment

```bash
python3 scripts/deploy_pages.py \
  --site-dir /absolute/path/to/site \
  --project-name my-pages-project \
  --branch main
```

### 2) Pages project listing / creation / proxy function scaffold

```bash
python3 scripts/cloudflare_manager.py list-pages
python3 scripts/cloudflare_manager.py create-pages --project-name my-pages-project --branch main
python3 scripts/cloudflare_manager.py generate-pages-proxy --target-url https://example.com/api
```

### 3) Worker deployment

```bash
python3 scripts/deploy_worker.py \
  --worker-dir /absolute/path/to/worker-project
```

## Workflow

1. Identify the target resource type: Pages, Worker, KV-backed Worker, or proxy.
2. Confirm the local source directory or generated template.
3. Obtain runtime credentials from environment variables or user memory.
4. Use the matching script.
5. Report the final URL, deployment target, and any next-step actions.

## Pages guidance

- Prefer the built artifact directory, not the source root, unless the root is itself a static site.
- For simple HTML sites, the deploy directory usually contains `index.html`.
- For framework projects, the deploy directory may be `dist/`, `build/`, or `.output/public/`.

## Workers guidance

- A Worker project normally contains `wrangler.toml` plus `worker.js`, `index.js`, or `src/index.js`.
- If KV is used, ensure the correct namespace binding exists in `wrangler.toml`.
- Deploy with `wrangler deploy` or `npx --yes wrangler@latest deploy`.

## Reverse proxy patterns

This skill supports two common proxy patterns:

1. **Pages Function / Worker reverse proxy**
   - Forward incoming requests to a target upstream
   - Preserve method and body
   - Add permissive CORS headers when the use case requires browser access
2. **KV-backed bridge Worker**
   - Use KV for lightweight inbox/history persistence
   - Good for simple relay, queue-like polling, or state snapshots

## Bundled references

- `references/pages.md`: Pages deployment notes and API usage
- `references/workers.md`: Worker deployment notes, wrangler layout, KV binding examples
- `references/proxy-patterns.md`: Reverse proxy and KV bridge patterns derived from proven local implementations

## Output expectations

After a successful task, report:

- Resource type used
- Local source directory
- Project / Worker name
- Branch or deployment environment
- Final URL or endpoint
- Any missing follow-up configuration such as custom domain, KV ID, or secret bindings
