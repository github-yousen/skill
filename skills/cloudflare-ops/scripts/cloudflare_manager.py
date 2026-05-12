#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API_BASE = "https://api.cloudflare.com/client/v4"


def fail(message: str, code: int = 1) -> None:
    print(f"❌ {message}", file=sys.stderr)
    raise SystemExit(code)


def info(message: str) -> None:
    print(f"ℹ️  {message}")


def success(message: str) -> None:
    print(f"✅ {message}")


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
        "User-Agent": "cloudflare-ops-skill",
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
            result = json.loads(body)
        except json.JSONDecodeError:
            fail(f"Cloudflare API request failed with HTTP {e.code}: {body}")
        return result
    except urllib.error.URLError as e:
        fail(f"Unable to reach Cloudflare API: {e}")


def list_pages(token: str, account_id: str) -> None:
    url = f"{API_BASE}/accounts/{account_id}/pages/projects"
    result = request_json("GET", url, token)
    items = result.get("result") or []
    print(json.dumps(items, ensure_ascii=False, indent=2))


def create_pages(token: str, account_id: str, project_name: str, branch: str) -> None:
    url = f"{API_BASE}/accounts/{account_id}/pages/projects"
    payload = {"name": project_name, "production_branch": branch}
    result = request_json("POST", url, token, payload)
    if result.get("success"):
        success(f"Created Pages project: {project_name}")
        print(json.dumps(result.get("result") or {}, ensure_ascii=False, indent=2))
        return

    errors = result.get("errors") or []
    text = json.dumps(errors, ensure_ascii=False)
    if "already exists" in text or "8000000" in text:
        info(f"Pages project already exists: {project_name}")
        return
    fail(f"Failed to create Pages project: {text}")


def generate_pages_proxy(target_url: str) -> None:
    content = f"""export default {{
  async fetch(request) {{
    const url = new URL(request.url);
    const target = new URL(url.pathname + url.search, {json.dumps(target_url)}).toString();

    try {{
      const response = await fetch(target, {{
        method: request.method,
        headers: request.headers,
        body: request.body,
        redirect: 'follow'
      }});

      const headers = new Headers(response.headers);
      headers.set('access-control-allow-origin', '*');
      headers.set('access-control-allow-methods', 'GET, POST, PUT, DELETE, OPTIONS');
      headers.set('access-control-allow-headers', 'Content-Type, Authorization');
      return new Response(response.body, {{ status: response.status, headers }});
    }} catch (error) {{
      return new Response(JSON.stringify({{ error: error.message }}), {{
        status: 502,
        headers: {{ 'content-type': 'application/json', 'access-control-allow-origin': '*' }}
      }});
    }}
  }}
}};
"""
    print(content)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cloudflare Pages/Proxy management helper")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list-pages", help="List Cloudflare Pages projects")

    p_create = sub.add_parser("create-pages", help="Create a Cloudflare Pages project")
    p_create.add_argument("--project-name", required=True)
    p_create.add_argument("--branch", default=os.environ.get("CLOUDFLARE_PAGES_BRANCH", "main"))

    p_proxy = sub.add_parser("generate-pages-proxy", help="Generate a simple reverse proxy function")
    p_proxy.add_argument("--target-url", required=True)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "generate-pages-proxy":
        generate_pages_proxy(args.target_url)
        return

    token = get_required_env("CLOUDFLARE_API_TOKEN")
    account_id = get_required_env("CLOUDFLARE_ACCOUNT_ID")

    if args.command == "list-pages":
        list_pages(token, account_id)
    elif args.command == "create-pages":
        create_pages(token, account_id, args.project_name, args.branch)
    else:
        fail(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
