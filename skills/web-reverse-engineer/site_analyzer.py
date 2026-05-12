#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网站源码抓取与 HTML 解析引擎
Site Analyzer - 抓取 HTML/JS/CSS 源码，解析页面结构
"""

import re
import json
import time
import hashlib
import logging
from urllib.parse import urljoin, urlparse, parse_qs
from typing import Dict, List, Optional, Tuple, Any

import requests
from bs4 import BeautifulSoup, Comment

logger = logging.getLogger("SiteAnalyzer")

# 默认请求头 - 模拟真实浏览器
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


class SiteAnalyzer:
    """网站源码抓取与解析引擎"""

    def __init__(self, timeout: int = 30, delay: float = 0.5,
                 max_js_size: int = 10 * 1024 * 1024,
                 extra_headers: Optional[Dict] = None,
                 cookies: Optional[Dict] = None):
        """
        Args:
            timeout: 请求超时秒数
            delay: 请求间隔（秒），避免触发反爬
            max_js_size: 单个 JS 文件最大下载大小（字节）
            extra_headers: 额外请求头
            cookies: Cookie 字典
        """
        self.timeout = timeout
        self.delay = delay
        self.max_js_size = max_js_size
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        if extra_headers:
            self.session.headers.update(extra_headers)
        if cookies:
            self.session.cookies.update(cookies)

        # 缓存已下载的资源
        self._cache: Dict[str, str] = {}
        self._js_contents: Dict[str, str] = {}
        self._css_contents: Dict[str, str] = {}

    def fetch_page(self, url: str) -> Dict[str, Any]:
        """
        抓取单个页面，返回 HTML 源码和解析结果

        Returns:
            {
                "url": str,
                "status_code": int,
                "html": str,
                "title": str,
                "meta": dict,
                "scripts": [{"src": str, "inline": bool, "content": str}],
                "stylesheets": [{"href": str, "inline": bool, "content": str}],
                "forms": [{"action": str, "method": str, "inputs": [...]}],
                "links": [{"href": str, "text": str}],
                "iframes": [{"src": str}],
                "comments": [str],
                "json_ld": [dict],
                "response_headers": dict,
            }
        """
        logger.info(f"抓取页面: {url}")

        try:
            resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"抓取失败: {url} - {e}")
            return {"url": url, "error": str(e), "status_code": getattr(e.response, 'status_code', 0) if hasattr(e, 'response') else 0}

        html = resp.text
        soup = BeautifulSoup(html, "html.parser")

        result = {
            "url": resp.url,  # 可能经过重定向
            "status_code": resp.status_code,
            "html": html,
            "html_size": len(html),
            "title": self._extract_title(soup),
            "meta": self._extract_meta(soup),
            "scripts": self._extract_scripts(soup, resp.url),
            "stylesheets": self._extract_stylesheets(soup, resp.url),
            "forms": self._extract_forms(soup, resp.url),
            "links": self._extract_links(soup, resp.url),
            "iframes": self._extract_iframes(soup, resp.url),
            "comments": self._extract_comments(soup),
            "json_ld": self._extract_json_ld(soup),
            "response_headers": dict(resp.headers),
        }

        return result

    def fetch_js_files(self, page_result: Dict) -> Dict[str, str]:
        """
        下载页面引用的所有外部 JS 文件

        Args:
            page_result: fetch_page() 的返回值

        Returns:
            {js_url: js_content, ...}
        """
        js_contents = {}

        for script in page_result.get("scripts", []):
            if script.get("inline"):
                # 内联脚本直接保存
                js_contents[f"inline_{hashlib.md5(script['content'].encode()).hexdigest()[:8]}"] = script["content"]
                continue

            src = script.get("src", "")
            if not src or src in self._js_contents:
                if src in self._js_contents:
                    js_contents[src] = self._js_contents[src]
                continue

            # 跳过第三方分析/广告脚本
            if self._is_third_party_script(src):
                logger.debug(f"跳过第三方脚本: {src}")
                continue

            try:
                time.sleep(self.delay)
                logger.info(f"下载 JS: {src}")
                resp = self.session.get(src, timeout=self.timeout,
                                       stream=True)
                resp.raise_for_status()

                # 检查大小
                content_length = int(resp.headers.get("Content-Length", 0))
                if content_length > self.max_js_size:
                    logger.warning(f"JS 文件过大({content_length}B), 跳过: {src}")
                    continue

                content = resp.text
                if len(content) <= self.max_js_size:
                    js_contents[src] = content
                    self._js_contents[src] = content
                else:
                    logger.warning(f"JS 内容过大({len(content)}B), 截断: {src}")
                    js_contents[src] = content[:self.max_js_size]

            except requests.RequestException as e:
                logger.warning(f"下载 JS 失败: {src} - {e}")

        return js_contents

    def fetch_full_site(self, url: str, depth: int = 1) -> Dict[str, Any]:
        """
        完整网站分析：抓取页面 + 下载 JS + 提取结构

        Args:
            url: 目标 URL
            depth: 抓取深度（1=仅首页，2=首页+一级链接）

        Returns:
            完整的站点分析结果
        """
        visited = set()
        pages = []
        all_js = {}
        queue = [(url, 0)]

        base_domain = urlparse(url).netloc

        while queue:
            current_url, current_depth = queue.pop(0)

            # 规范化 URL
            parsed = urlparse(current_url)
            normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if normalized in visited:
                continue
            visited.add(normalized)

            # 只抓同域页面
            if parsed.netloc != base_domain:
                continue

            # 抓取页面
            page = self.fetch_page(current_url)
            if "error" in page:
                continue
            pages.append(page)

            # 下载 JS
            js = self.fetch_js_files(page)
            all_js.update(js)

            # 如果还有深度，把页面链接加入队列
            if current_depth < depth - 1:
                for link in page.get("links", []):
                    href = link.get("href", "")
                    if href and not href.startswith(("#", "javascript:", "mailto:", "tel:")):
                        queue.append((href, current_depth + 1))

            time.sleep(self.delay)

        return {
            "base_url": url,
            "domain": base_domain,
            "pages_count": len(pages),
            "js_files_count": len(all_js),
            "pages": pages,
            "js_contents": all_js,
        }

    # ========== 内部解析方法 ==========

    def _extract_title(self, soup: BeautifulSoup) -> str:
        tag = soup.find("title")
        return tag.get_text(strip=True) if tag else ""

    def _extract_meta(self, soup: BeautifulSoup) -> Dict:
        meta = {}
        for tag in soup.find_all("meta"):
            name = tag.get("name") or tag.get("property") or tag.get("http-equiv", "")
            content = tag.get("content", "")
            if name and content:
                meta[name] = content
            # charset
            charset = tag.get("charset")
            if charset:
                meta["charset"] = charset
        return meta

    def _extract_scripts(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        scripts = []
        for tag in soup.find_all("script"):
            src = tag.get("src")
            if src:
                full_src = urljoin(base_url, src)
                scripts.append({
                    "src": full_src,
                    "inline": False,
                    "type": tag.get("type", ""),
                    "async": tag.has_attr("async"),
                    "defer": tag.has_attr("defer"),
                    "content": "",
                })
            else:
                content = tag.string or ""
                if content.strip():
                    scripts.append({
                        "src": "",
                        "inline": True,
                        "type": tag.get("type", ""),
                        "content": content.strip(),
                    })
        return scripts

    def _extract_stylesheets(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        sheets = []
        # <link rel="stylesheet">
        for tag in soup.find_all("link", rel="stylesheet"):
            href = tag.get("href")
            if href:
                sheets.append({
                    "href": urljoin(base_url, href),
                    "inline": False,
                    "content": "",
                })
        # <style> 内联
        for tag in soup.find_all("style"):
            content = tag.string or ""
            if content.strip():
                sheets.append({
                    "href": "",
                    "inline": True,
                    "content": content.strip(),
                })
        return sheets

    def _extract_forms(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        forms = []
        for form in soup.find_all("form"):
            action = form.get("action", "")
            if action:
                action = urljoin(base_url, action)

            inputs = []
            for inp in form.find_all(["input", "textarea", "select", "button"]):
                input_info = {
                    "tag": inp.name,
                    "type": inp.get("type", "text"),
                    "name": inp.get("name", ""),
                    "id": inp.get("id", ""),
                    "placeholder": inp.get("placeholder", ""),
                    "value": inp.get("value", ""),
                    "required": inp.has_attr("required"),
                }
                if inp.name == "select":
                    input_info["options"] = [
                        {"value": opt.get("value", ""), "text": opt.get_text(strip=True)}
                        for opt in inp.find_all("option")
                    ]
                inputs.append(input_info)

            forms.append({
                "action": action,
                "method": (form.get("method", "GET")).upper(),
                "enctype": form.get("enctype", ""),
                "id": form.get("id", ""),
                "class": form.get("class", []),
                "inputs": inputs,
            })
        return forms

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        links = []
        seen = set()
        for a in soup.find_all("a", href=True):
            href = urljoin(base_url, a["href"])
            if href in seen:
                continue
            seen.add(href)
            links.append({
                "href": href,
                "text": a.get_text(strip=True)[:100],
                "target": a.get("target", ""),
                "rel": a.get("rel", []),
            })
        return links

    def _extract_iframes(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        iframes = []
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src", "")
            if src:
                iframes.append({
                    "src": urljoin(base_url, src),
                    "id": iframe.get("id", ""),
                    "name": iframe.get("name", ""),
                })
        return iframes

    def _extract_comments(self, soup: BeautifulSoup) -> List[str]:
        """提取 HTML 注释（常含调试信息、API 地址等）"""
        comments = []
        for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
            text = str(comment).strip()
            if text and len(text) > 5:  # 过滤空注释
                comments.append(text[:500])  # 截断过长注释
        return comments

    def _extract_json_ld(self, soup: BeautifulSoup) -> List[Dict]:
        """提取 JSON-LD 结构化数据"""
        results = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "{}")
                results.append(data)
            except json.JSONDecodeError:
                pass
        return results

    def _is_third_party_script(self, url: str) -> bool:
        """判断是否为第三方分析/广告脚本"""
        third_party_patterns = [
            "google-analytics.com", "googletagmanager.com",
            "googlesyndication.com", "googleadservices.com",
            "facebook.net", "fbcdn.net",
            "doubleclick.net", "adsense",
            "hotjar.com", "mixpanel.com",
            "segment.com", "amplitude.com",
            "sentry.io", "bugsnag.com",
            "cdn.jsdelivr.net/npm/mathjax",
            "recaptcha", "hcaptcha",
            "clarity.ms",
        ]
        url_lower = url.lower()
        return any(p in url_lower for p in third_party_patterns)


def save_site_dump(site_result: Dict, save_dir: str):
    """将抓取结果保存到本地目录"""
    import os
    os.makedirs(save_dir, exist_ok=True)

    # 保存 HTML
    for i, page in enumerate(site_result.get("pages", [])):
        html_path = os.path.join(save_dir, f"page_{i}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(page.get("html", ""))

    # 保存 JS
    js_dir = os.path.join(save_dir, "js")
    os.makedirs(js_dir, exist_ok=True)
    for url, content in site_result.get("js_contents", {}).items():
        # 安全文件名
        safe_name = re.sub(r'[^\w\-.]', '_', urlparse(url).path.split("/")[-1] or "inline")
        if not safe_name.endswith(".js"):
            safe_name += ".js"
        js_path = os.path.join(js_dir, safe_name)
        with open(js_path, "w", encoding="utf-8") as f:
            f.write(content)

    # 保存元信息
    meta = {k: v for k, v in site_result.items() if k not in ("pages", "js_contents")}
    for page in site_result.get("pages", []):
        page_meta = {k: v for k, v in page.items() if k not in ("html",)}
        meta.setdefault("pages_meta", []).append(page_meta)

    meta_path = os.path.join(save_dir, "site_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f"站点数据已保存到: {save_dir}")
    return save_dir
