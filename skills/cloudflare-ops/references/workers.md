# Cloudflare Workers Notes

## Typical project layout

```text
worker-project/
  wrangler.toml
  worker.js
```

or

```text
worker-project/
  wrangler.toml
  src/
    index.js
```

## Worker deployment

```bash
python3 scripts/deploy_worker.py --worker-dir /path/to/worker-project
```

Optional environment:

```bash
python3 scripts/deploy_worker.py --worker-dir /path/to/worker-project --env production
```

## KV binding example

```toml
name = "ai-bridge"
main = "worker.js"
compatibility_date = "2024-01-01"

[[kv_namespaces]]
binding = "AI_BRIDGE"
id = "YOUR_KV_NAMESPACE_ID"
```

## Notes

- `wrangler.toml` is required.
- Use runtime environment variables for Cloudflare token and account ID.
- `wrangler` is preferred; `npx --yes wrangler@latest` is a valid fallback.
