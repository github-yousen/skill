# skill

Personal public skill repository for reusable agent skills.

## Included skills

- `cloudflare-ops`: Cloudflare operations skill covering Pages deployment, Workers deployment, KV-backed worker patterns, Pages project management, and reverse proxy scaffolding without storing credentials in the repository.

## Repository layout

```text
skills/
  cloudflare-ops/
    SKILL.md
    scripts/
      deploy_pages.py
      deploy_worker.py
      cloudflare_manager.py
    references/
      pages.md
      workers.md
      proxy-patterns.md
```

## Security

This repository does **not** store Cloudflare API tokens, account IDs, emails, or other credentials.
Provide credentials at runtime or through secure agent memory / environment only.
