# skill

Personal public skill repository for reusable agent skills.

## Included skills

- `cloudflare-ops`: Cloudflare operations skill covering Pages deployment, Workers deployment, KV-backed worker patterns, Pages project management, and reverse proxy scaffolding without storing credentials in the repository.
- `web-reverse-engineer`: Website source reverse engineering skill for extracting raw HTML/JS, identifying APIs, auth flows, GraphQL usage, WebSocket endpoints, and producing reusable operation reports.

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
  web-reverse-engineer/
    SKILL.md
    main.py
    api_executor.py
    js_deobfuscator.py
    site_analyzer.py
    bilibili_deep_extract.py
    scripts/
      web_fetch_source.py
      auth_analyzer.py
      gql_analyzer.py
    references/
      report_template.md
```

## Security

This repository does **not** store Cloudflare API tokens, account IDs, emails, GitHub tokens, or other private credentials.
Provide credentials at runtime or through secure agent memory / environment only.
