#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def fail(message: str, code: int = 1) -> None:
    print(f"❌ {message}", file=sys.stderr)
    raise SystemExit(code)


def info(message: str) -> None:
    print(f"ℹ️  {message}")


def success(message: str) -> None:
    print(f"✅ {message}")


def detect_wrangler_command() -> list[str]:
    if shutil.which("wrangler"):
        return ["wrangler"]
    if shutil.which("npx"):
        return ["npx", "--yes", "wrangler@latest"]
    fail("Neither 'wrangler' nor 'npx' is available. Install Wrangler or Node.js first.")


def get_required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        fail(f"Missing required environment variable: {name}")
    return value


def validate_worker_dir(raw_path: str) -> Path:
    worker_dir = Path(raw_path).expanduser().resolve()
    if not worker_dir.exists() or not worker_dir.is_dir():
        fail(f"Worker directory does not exist: {worker_dir}")
    if not (worker_dir / "wrangler.toml").exists():
        fail(f"wrangler.toml not found in: {worker_dir}")
    return worker_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy a Cloudflare Worker project")
    parser.add_argument("--worker-dir", required=True, help="Path to the worker project directory")
    parser.add_argument("--env", help="Optional Wrangler environment name")
    args = parser.parse_args()

    token = get_required_env("CLOUDFLARE_API_TOKEN")
    account_id = get_required_env("CLOUDFLARE_ACCOUNT_ID")
    worker_dir = validate_worker_dir(args.worker_dir)

    cmd = detect_wrangler_command() + ["deploy"]
    if args.env:
        cmd.extend(["--env", args.env])

    env = os.environ.copy()
    env["CLOUDFLARE_API_TOKEN"] = token
    env["CLOUDFLARE_ACCOUNT_ID"] = account_id

    info(f"Worker dir: {worker_dir}")
    result = subprocess.run(cmd, cwd=str(worker_dir), env=env, check=False)
    if result.returncode != 0:
        fail(f"Worker deployment failed with exit code {result.returncode}")

    success("Worker deployment finished")


if __name__ == "__main__":
    main()
