#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web Reverse Engineer - 统一入口
网站逆向工程 + API 代理执行技能

子命令:
  analyze   - 分析网站（全流程：抓取 + JS 分析 + 接口图谱）
  fetch     - 仅抓取网站源码
  extract-js - 分析本地 JS 文件
  call      - 执行单个 API 调用
  replay    - 从接口图谱批量执行
"""

import argparse
import json
import sys
import os
import time
import logging
from typing import Dict, Any, Optional

# 添加当前目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from site_analyzer import SiteAnalyzer, save_site_dump
from js_deobfuscator import JSDeobfuscator
from api_executor import APIExecutor, parse_cookie_string, parse_header_args

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("WebRE")


def cmd_analyze(args):
    """分析网站：抓取 + JS 分析 + 生成接口图谱"""
    url = args.url
    depth = args.depth
    output = args.output

    logger.info(f"=" * 60)
    logger.info(f"开始分析网站: {url}")
    logger.info(f"抓取深度: {depth}")
    logger.info(f"=" * 60)

    # 准备额外参数
    cookies = parse_cookie_string(args.cookie) if args.cookie else None
    headers = parse_header_args(args.header) if args.header else None

    # 1. 抓取网站
    analyzer = SiteAnalyzer(
        timeout=args.timeout,
        delay=args.delay,
        extra_headers=headers,
        cookies=cookies,
    )
    site_data = analyzer.fetch_full_site(url, depth=depth)

    logger.info(f"抓取完成: {site_data['pages_count']} 页面, {site_data['js_files_count']} JS 文件")

    # 2. 分析 JS
    deobfuscator = JSDeobfuscator(base_url=url)

    # 先分析内联脚本
    for page in site_data.get("pages", []):
        for script in page.get("scripts", []):
            if script.get("inline") and script.get("content"):
                deobfuscator.analyze_js(script["content"], f"inline@{page['url']}")

    # 再分析外部 JS
    js_results = deobfuscator.analyze_multiple_js(site_data.get("js_contents", {}))

    # 3. 构建接口图谱
    api_map = {
        "site_url": url,
        "analyzed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "pages_analyzed": site_data["pages_count"],
        "js_files_analyzed": site_data["js_files_count"],
        "api_endpoints": js_results["endpoints"],
        "endpoints_count": js_results["endpoints_count"],
        "auth_info": js_results["auth_info"],
        "base_urls": js_results["base_urls"],
        "websockets": js_results["websockets"],
        "env_vars": js_results["env_vars"],
        "page_structure": {
            "title": site_data["pages"][0]["title"] if site_data["pages"] else "",
            "forms_count": sum(len(p.get("forms", [])) for p in site_data.get("pages", [])),
            "links_count": sum(len(p.get("links", [])) for p in site_data.get("pages", [])),
            "forms": [],
            "meta": site_data["pages"][0].get("meta", {}) if site_data["pages"] else {},
        },
    }

    # 收集所有表单
    for page in site_data.get("pages", []):
        for form in page.get("forms", []):
            form["page_url"] = page["url"]
            api_map["page_structure"]["forms"].append(form)

    # 4. 输出结果
    output_json = json.dumps(api_map, ensure_ascii=False, indent=2, default=str)

    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(output_json)
        logger.info(f"接口图谱已保存到: {output}")

    # 打印摘要
    print("\n" + "=" * 60)
    print(f"📊 网站分析报告: {url}")
    print("=" * 60)
    print(f"\n🌐 基本信息:")
    print(f"   标题: {api_map['page_structure']['title']}")
    print(f"   页面数: {api_map['pages_analyzed']}")
    print(f"   JS 文件数: {api_map['js_files_analyzed']}")
    print(f"   表单数: {api_map['page_structure']['forms_count']}")
    print(f"   链接数: {api_map['page_structure']['links_count']}")

    if api_map["base_urls"]:
        print(f"\n🔗 API Base URLs:")
        for bu in api_map["base_urls"]:
            print(f"   • {bu}")

    print(f"\n🔐 鉴权信息:")
    auth = api_map["auth_info"]
    print(f"   类型: {auth['auth_type']}")
    if auth["header_name"]:
        print(f"   头部: {auth['header_name']}")
    if auth["token_format"]:
        print(f"   格式: {auth['token_format']}")
    if auth["login_endpoint"]:
        print(f"   登录接口: {auth['login_endpoint']}")
    if auth["token_storage"]:
        print(f"   Token 存储: {auth['token_storage']}")
    if auth["refresh_endpoint"]:
        print(f"   刷新接口: {auth['refresh_endpoint']}")

    print(f"\n📡 发现 {api_map['endpoints_count']} 个 API 端点:")
    if api_map["api_endpoints"]:
        # 按分类分组显示
        categories = {}
        for ep in api_map["api_endpoints"]:
            cat = ep.get("category", "general")
            categories.setdefault(cat, []).append(ep)

        for cat, eps in categories.items():
            print(f"\n   [{cat.upper()}] ({len(eps)} 个)")
            for ep in eps[:10]:  # 每类最多显示10个
                confidence_icon = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(ep["confidence"], "⚪")
                print(f"   {confidence_icon} {ep['method']:6s} {ep['url']}")
                if ep.get("params"):
                    params_str = ", ".join(f"{k}={v}" for k, v in ep["params"].items())
                    print(f"            参数: {params_str}")
            if len(eps) > 10:
                print(f"   ... 还有 {len(eps) - 10} 个")
    else:
        print("   (未发现 API 端点)")

    if api_map["websockets"]:
        print(f"\n🔌 WebSocket 端点:")
        for ws in api_map["websockets"]:
            print(f"   • {ws}")

    if api_map["env_vars"]:
        print(f"\n🔧 环境变量引用:")
        for k, v in api_map["env_vars"].items():
            print(f"   • {k}" + (f" = {v}" if v else ""))

    print(f"\n{'=' * 60}")

    if output:
        print(f"✅ 完整接口图谱已保存到: {output}")
    else:
        print("💡 提示: 使用 --output <file.json> 保存完整接口图谱")

    # 同时输出完整 JSON（供 AI 读取）
    if not output:
        print(f"\n--- 完整 JSON 数据 ---")
        print(output_json)


def cmd_fetch(args):
    """仅抓取网站源码"""
    url = args.url
    save_dir = args.save_dir

    cookies = parse_cookie_string(args.cookie) if args.cookie else None
    headers = parse_header_args(args.header) if args.header else None

    analyzer = SiteAnalyzer(
        timeout=args.timeout,
        delay=args.delay,
        extra_headers=headers,
        cookies=cookies,
    )

    site_data = analyzer.fetch_full_site(url, depth=args.depth)

    if save_dir:
        save_site_dump(site_data, save_dir)
        print(f"✅ 源码已保存到: {save_dir}")
    else:
        # 输出摘要
        print(json.dumps({
            "url": url,
            "pages_count": site_data["pages_count"],
            "js_files_count": site_data["js_files_count"],
            "pages": [
                {
                    "url": p["url"],
                    "title": p.get("title", ""),
                    "html_size": p.get("html_size", 0),
                    "scripts_count": len(p.get("scripts", [])),
                    "forms_count": len(p.get("forms", [])),
                }
                for p in site_data.get("pages", [])
            ],
            "js_files": list(site_data.get("js_contents", {}).keys()),
        }, ensure_ascii=False, indent=2))


def cmd_extract_js(args):
    """分析本地 JS 文件"""
    js_path = args.js_file
    base_url = args.base_url or ""

    with open(js_path, "r", encoding="utf-8", errors="replace") as f:
        js_content = f.read()

    logger.info(f"分析 JS 文件: {js_path} ({len(js_content)} chars)")

    deobfuscator = JSDeobfuscator(base_url=base_url)
    results = deobfuscator.analyze_js(js_content, source_file=js_path)

    output = json.dumps(results, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"✅ 分析结果已保存到: {args.output}")
    else:
        print(output)


def cmd_call(args):
    """执行单个 API 调用"""
    url = args.url
    method = args.method

    headers = parse_header_args(args.header) if args.header else None
    cookies = parse_cookie_string(args.cookie) if args.cookie else None

    executor = APIExecutor(
        headers=headers,
        cookies=cookies,
        timeout=args.timeout,
        verify_ssl=not args.no_verify,
    )

    # 解析 body
    body = None
    if args.body:
        try:
            body = json.loads(args.body)
        except json.JSONDecodeError:
            body = args.body  # 作为原始字符串

    # 解析 params
    params = None
    if args.params:
        try:
            params = json.loads(args.params)
        except json.JSONDecodeError:
            # 尝试 key=value 格式
            params = {}
            for pair in args.params.split("&"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    params[k] = v

    result = executor.call(
        url=url,
        method=method,
        params=params,
        body=body,
        raw=args.raw,
    )

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def cmd_replay(args):
    """从接口图谱批量执行"""
    api_map_path = args.api_map

    headers = parse_header_args(args.header) if args.header else None
    cookies = parse_cookie_string(args.cookie) if args.cookie else None

    executor = APIExecutor(
        headers=headers,
        cookies=cookies,
        timeout=args.timeout,
        verify_ssl=not args.no_verify,
    )

    results = executor.replay_from_api_map(
        api_map_path,
        filter_category=args.category,
        filter_method=args.method,
    )

    # 输出结果
    output = {
        "results": results,
        "stats": executor.get_stats(),
    }

    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(
        description="Web Reverse Engineer - 网站逆向工程 + API 代理执行",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # ===== analyze =====
    p_analyze = subparsers.add_parser("analyze", help="分析网站（全流程）")
    p_analyze.add_argument("url", help="目标网站 URL")
    p_analyze.add_argument("--output", "-o", help="输出接口图谱 JSON 文件路径")
    p_analyze.add_argument("--depth", "-d", type=int, default=1, help="抓取深度（默认1）")
    p_analyze.add_argument("--timeout", type=int, default=30, help="请求超时秒数")
    p_analyze.add_argument("--delay", type=float, default=0.5, help="请求间隔秒数")
    p_analyze.add_argument("--header", "-H", action="append", default=[], help="额外请求头 (Name: Value)")
    p_analyze.add_argument("--cookie", "-C", default="", help="Cookie 字符串")
    p_analyze.set_defaults(func=cmd_analyze)

    # ===== fetch =====
    p_fetch = subparsers.add_parser("fetch", help="仅抓取网站源码")
    p_fetch.add_argument("url", help="目标网站 URL")
    p_fetch.add_argument("--save-dir", "-s", help="保存目录")
    p_fetch.add_argument("--depth", "-d", type=int, default=1, help="抓取深度")
    p_fetch.add_argument("--timeout", type=int, default=30, help="请求超时秒数")
    p_fetch.add_argument("--delay", type=float, default=0.5, help="请求间隔秒数")
    p_fetch.add_argument("--header", "-H", action="append", default=[], help="额外请求头")
    p_fetch.add_argument("--cookie", "-C", default="", help="Cookie 字符串")
    p_fetch.set_defaults(func=cmd_fetch)

    # ===== extract-js =====
    p_js = subparsers.add_parser("extract-js", help="分析本地 JS 文件")
    p_js.add_argument("js_file", help="JS 文件路径")
    p_js.add_argument("--base-url", "-b", default="", help="API Base URL")
    p_js.add_argument("--output", "-o", help="输出文件路径")
    p_js.set_defaults(func=cmd_extract_js)

    # ===== call =====
    p_call = subparsers.add_parser("call", help="执行单个 API 调用")
    p_call.add_argument("url", help="API URL")
    p_call.add_argument("--method", "-m", default="GET", help="HTTP 方法")
    p_call.add_argument("--header", "-H", action="append", default=[], help="请求头 (Name: Value)")
    p_call.add_argument("--cookie", "-C", default="", help="Cookie 字符串")
    p_call.add_argument("--body", "-b", default=None, help="请求体（JSON 字符串）")
    p_call.add_argument("--params", "-p", default=None, help="URL 查询参数（JSON 或 key=value&key2=value2）")
    p_call.add_argument("--timeout", type=int, default=30, help="超时秒数")
    p_call.add_argument("--no-verify", action="store_true", help="不验证 SSL")
    p_call.add_argument("--raw", action="store_true", help="返回原始响应")
    p_call.set_defaults(func=cmd_call)

    # ===== replay =====
    p_replay = subparsers.add_parser("replay", help="从接口图谱批量执行")
    p_replay.add_argument("api_map", help="接口图谱 JSON 文件路径")
    p_replay.add_argument("--header", "-H", action="append", default=[], help="请求头")
    p_replay.add_argument("--cookie", "-C", default="", help="Cookie 字符串")
    p_replay.add_argument("--category", default=None, help="只执行某分类")
    p_replay.add_argument("--method", default=None, help="只执行某方法")
    p_replay.add_argument("--timeout", type=int, default=30, help="超时秒数")
    p_replay.add_argument("--no-verify", action="store_true", help="不验证 SSL")
    p_replay.set_defaults(func=cmd_replay)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
