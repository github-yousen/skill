#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

API_BASE = "https://api.cloudflare.com/client/v4"


def fail(message: str, code: int = 1) -> None:
    print(f"❌ {message}", file=sys.stderr)
    raise SystemExit(code)


def info(message: str) -> None:
    print(f"ℹ️  {message}")


def success(message: str) -> None:
    print(f"✅ {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deploy a static directory to Cloudflare Pages")
    parser.add_argument("--site-dir", required=True, help="Absolute or relative path to the deployable site directory")
    parser.add_argument("--project-name", required=True, help="Cloudflare Pages project name")
    parser.add_argument("--branch", default=os.environ.get("CLOUDFLARE_PAGES_BRANCH", "main"), help="Deployment branch (default: main)")
    parser.add_argument("--skip-create", action="store_true", help="Skip project creation and only deploy")
    return parser.parse_args()


def get_required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        fail(f"Missing required environment variable: {name}")
    return value


def request_json(method: str, url: str, token: str, payload: dict | None = None) -> dict:
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "cloudflare-pages-deploy-skill",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            fail(f"Cloudflare API request failed with HTTP {e.code}: {body}")
    except urllib.error.URLError as e:
        fail(f"Unable to reach Cloudflare API: {e}")


def create_project_if_needed(token: str, account_id: str, project_name: str, branch: str) -> None:
    url = f"{API_BASE}/accounts/{account_id}/pages/projects"
    payload = {"name": project_name, "production_branch": branch}
    result = request_json("POST", url, token, payload)

    if result.get("success"):
        success(f"Created Pages project: {project_name}")
        return

    errors = result.get("errors") or []
    text = json.dumps(errors, ensure_ascii=False)
    if "already exists" in text or "8000000" in text:
        info(f"Pages project already exists: {project_name}")
        return

    fail(f"Failed to create Pages project: {text}")


def detect_wrangler_command() -> list[str]:
    if shutil.which("wrangler"):
        return ["wrangler"]
    if shutil.which("npx"):
        return ["npx", "--yes", "wrangler@latest"]
    fail("Neither 'wrangler' nor 'npx' is available. Install Wrangler or Node.js first.")


def deploy_site(site_dir: Path, project_name: str, branch: str, token: str, account_id: str) -> None:
    cmd = detect_wrangler_command() + [
        "pages",
        "deploy",
        str(site_dir),
        "--project-name",
        project_name,
        "--branch",
        branch,
    ]

    env = os.environ.copy()
    env["CLOUDFLARE_API_TOKEN"] = token
    env["CLOUDFLARE_ACCOUNT_ID"] = account_id

    info("Running deployment command...")
    result = subprocess.run(cmd, env=env, check=False)
    if result.returncode != 0:
        fail(f"Deployment command failed with exit code {result.returncode}")


def validate_site_dir(raw_site_dir: str) -> Path:
    site_dir = Path(raw_site_dir).expanduser().resolve()
    if not site_dir.exists() or not site_dir.is_dir():
        fail(f"Site directory does not exist: {site_dir}")

    index_file = site_dir / "index.html"
    if not index_file.exists():
        info(f"No index.html found in {site_dir}. This may still be valid for some frameworks.")

    return site_dir


def main() -> None:
    args = parse_args()
    token = get_required_env("CLOUDFLARE_API_TOKEN")
    account_id = get_required_env("CLOUDFLARE_ACCOUNT_ID")
    site_dir = validate_site_dir(args.site_dir)

    info(f"Project: {args.project_name}")
    info(f"Site dir: {site_dir}")
    info(f"Branch: {args.branch}")

    if not args.skip_create:
        create_project_if_needed(token, account_id, args.project_name, args.branch)

    deploy_site(site_dir, args.project_name, args.branch, token, account_id)

    success("Deployment finished")
    print(f"🌐 URL: https://{args.project_name}.pages.dev")


if __name__ == "__main__":
    main()
