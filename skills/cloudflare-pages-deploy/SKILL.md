---
name: cloudflare-pages-deploy
description: Deploy or update static websites on Cloudflare Pages. Use when a user wants to publish a local static site directory to Cloudflare Pages, create a Pages project if it does not exist, redeploy an updated build, or verify deployment prerequisites. Never store Cloudflare tokens or account IDs in this skill or repository; collect them during initialization or from user memory/environment only.
---

# Cloudflare Pages Deploy

Use this skill to deploy a local static site directory to Cloudflare Pages without hardcoding secrets.

## Workflow

1. Confirm the target directory exists and contains the deployable output.
   - For simple static sites, this is usually the folder containing `index.html`.
   - For framework projects, this is the built output directory such as `dist/` or `.output/public/`.
2. Obtain the following credentials from the user, runtime environment, or long-term memory:
   - `CLOUDFLARE_API_TOKEN`
   - `CLOUDFLARE_ACCOUNT_ID`
3. Never write those credentials into this repository, the skill files, or generated public artifacts.
4. Run the bundled deployment script.
5. Report the final Pages URL and any follow-up steps.

## Deployment script

```bash
python3 scripts/deploy_pages.py \
  --site-dir /absolute/path/to/site \
  --project-name my-pages-project \
  --branch main
```

### Environment variables

The script reads credentials from environment variables first:

```bash
export CLOUDFLARE_API_TOKEN=...
export CLOUDFLARE_ACCOUNT_ID=...
```

Optional runtime variables:

- `CLOUDFLARE_PAGES_BRANCH` (default: `main`)

## What the script does

- Validates the site directory
- Creates the Pages project if it does not already exist
- Deploys the local directory with `wrangler`
- Falls back to `npx --yes wrangler@latest` if `wrangler` is not already installed
- Prints the final `https://<project>.pages.dev` URL

## Operational rules

- Prefer the built artifact directory, not the project source root, unless the source root is itself a static site.
- If the user says "remember my Cloudflare token/account", store that in agent memory separately rather than this skill.
- If deployment fails because `wrangler` or `npx` is unavailable, explain the missing dependency clearly.
- If the user wants a custom domain, deploy first, then handle domain binding as a separate step.

## Common examples

### Deploy a plain HTML site

```bash
python3 scripts/deploy_pages.py \
  --site-dir /data/workspace/my-site \
  --project-name my-site
```

### Deploy a built frontend project

```bash
python3 scripts/deploy_pages.py \
  --site-dir /data/workspace/app/dist \
  --project-name app-prod \
  --branch main
```

## Output expectations

After a successful run, provide:

- Project name
- Deployed directory
- Branch used
- Final Pages URL
