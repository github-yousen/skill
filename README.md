# skill

Personal public skill repository for reusable agent skills.

## Included skills

- `cloudflare-pages-deploy`: Deploy or update static sites on Cloudflare Pages without storing secrets in the repository.

## Repository layout

```text
skills/
  cloudflare-pages-deploy/
    SKILL.md
    scripts/
      deploy_pages.py
```

## Security

This repository does **not** store Cloudflare API tokens or account credentials.
Provide credentials at runtime or through your agent memory / environment only.
