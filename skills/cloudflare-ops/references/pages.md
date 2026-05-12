# Cloudflare Pages Notes

## Typical tasks

- Create a Pages project
- Deploy a static directory
- Redeploy an updated build
- Generate a simple Pages Function reverse proxy
- List existing Pages projects

## Required environment variables

```bash
export CLOUDFLARE_API_TOKEN=...
export CLOUDFLARE_ACCOUNT_ID=...
```

## Pages deployment command

```bash
python3 scripts/deploy_pages.py --site-dir /path/to/site --project-name my-pages-project
```

## Common deployment inputs

- Plain static HTML directory
- Frontend build output such as `dist/`, `build/`, `.output/public/`

## Create or inspect Pages projects

```bash
python3 scripts/cloudflare_manager.py list-pages
python3 scripts/cloudflare_manager.py create-pages --project-name my-pages-project --branch main
```

## Notes

- Project names become the default `<project>.pages.dev` subdomain.
- Project creation may return an "already exists" style error for existing projects; treat that as non-fatal when the next step is deployment.
- Keep credentials outside repository files.
