#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API 代理执行器
使用 Token/Cookie 直接调用提取出的 API 端点
"""

import re
import json
import time
import logging
from urllib.parse import urljoin, urlparse, urlencode
from typing import Dict, List, Optional, Any, Tuple

import requests

logger = logging.getLogger("APIExecutor")


class APIExecutor:
    """API 代理执行器 - 直接调用 API 绕过浏览器"""

    def __init__(self,
                 base_url: str = "",
                 headers: Optional[Dict[str, str]] = None,
                 cookies: Optional[Dict[str, str]] = None,
                 timeout: int = 30,
                 verify_ssl: bool = True):
        """
        Args:
            base_url: API 基础 URL
            headers: 全局请求头（如 Authorization）
            cookies: 全局 Cookie
            timeout: 请求超时秒数
            verify_ssl: 是否验证 SSL 证书
        """
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.session = requests.Session()

        # 设置默认头
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })

        if headers:
            self.session.headers.update(headers)
        if cookies:
            self.session.cookies.update(cookies)

        # 请求历史
        self.history: List[Dict] = []

    def set_auth(self, auth_type: str, token: str,
                 header_name: str = "Authorization"):
        """
        设置鉴权信息

        Args:
            auth_type: bearer/api_key/cookie/custom
            token: Token 值
            header_name: 自定义头名称
        """
        if auth_type == "bearer":
            self.session.headers["Authorization"] = f"Bearer {token}"
        elif auth_type == "api_key":
            self.session.headers[header_name] = token
        elif auth_type == "cookie":
            # token 格式: "key1=val1; key2=val2"
            for pair in token.split(";"):
                pair = pair.strip()
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    self.session.cookies.set(k.strip(), v.strip())
        elif auth_type == "custom":
            self.session.headers[header_name] = token

        logger.info(f"已设置鉴权: {auth_type}")

    def call(self,
             url: str,
             method: str = "GET",
             params: Optional[Dict] = None,
             body: Optional[Any] = None,
             headers: Optional[Dict] = None,
             cookies: Optional[Dict] = None,
             files: Optional[Dict] = None,
             follow_redirects: bool = True,
             raw: bool = False) -> Dict[str, Any]:
        """
        执行 API 调用

        Args:
            url: API URL（相对路径或完整 URL）
            method: HTTP 方法
            params: URL 查询参数
            body: 请求体（dict 自动 JSON 序列化）
            headers: 额外请求头（会合并到全局头）
            cookies: 额外 Cookie
            files: 上传文件
            follow_redirects: 是否跟随重定向
            raw: 是否返回原始响应内容

        Returns:
            {
                "status_code": int,
                "headers": dict,
                "body": any,       # JSON 解析后的 body 或原始文本
                "url": str,        # 最终 URL（可能经过重定向）
                "elapsed_ms": float,
                "success": bool,
                "error": str,
            }
        """
        # 解析 URL
        if not url.startswith("http"):
            url = f"{self.base_url}/{url.lstrip('/')}" if self.base_url else url

        # 准备请求
        method = method.upper()
        kwargs = {
            "timeout": self.timeout,
            "allow_redirects": follow_redirects,
            "verify": self.verify_ssl,
        }

        if params:
            kwargs["params"] = params
        if headers:
            kwargs["headers"] = headers
        if cookies:
            kwargs["cookies"] = cookies
        if files:
            kwargs["files"] = files

        # 处理请求体
        if body is not None:
            if isinstance(body, (dict, list)):
                kwargs["json"] = body
            elif isinstance(body, str):
                kwargs["data"] = body
            else:
                kwargs["data"] = str(body)

        # 执行请求
        start_time = time.time()
        result = {
            "url": url,
            "method": method,
            "status_code": 0,
            "headers": {},
            "body": None,
            "elapsed_ms": 0,
            "success": False,
            "error": "",
        }

        try:
            resp = self.session.request(method, url, **kwargs)
            elapsed = (time.time() - start_time) * 1000

            result["status_code"] = resp.status_code
            result["headers"] = dict(resp.headers)
            result["url"] = resp.url
            result["elapsed_ms"] = round(elapsed, 2)
            result["success"] = 200 <= resp.status_code < 400

            # 解析响应体
            if raw:
                result["body"] = resp.text
            else:
                content_type = resp.headers.get("Content-Type", "")
                if "json" in content_type:
                    try:
                        result["body"] = resp.json()
                    except json.JSONDecodeError:
                        result["body"] = resp.text
                elif "html" in content_type:
                    result["body"] = resp.text[:10000]  # 截断 HTML
                    result["body_truncated"] = len(resp.text) > 10000
                else:
                    result["body"] = resp.text[:5000]

            # 检查常见错误
            if resp.status_code == 401:
                result["error"] = "未授权 - Token/Cookie 可能已过期"
            elif resp.status_code == 403:
                result["error"] = "禁止访问 - 权限不足"
            elif resp.status_code == 404:
                result["error"] = "接口不存在"
            elif resp.status_code == 429:
                result["error"] = "请求过于频繁，请稍后重试"
                # 提取 Retry-After
                retry_after = resp.headers.get("Retry-After", "")
                if retry_after:
                    result["error"] += f" (Retry-After: {retry_after}s)"
            elif resp.status_code >= 500:
                result["error"] = f"服务器错误 ({resp.status_code})"

        except requests.Timeout:
            result["error"] = f"请求超时 ({self.timeout}s)"
            result["elapsed_ms"] = round((time.time() - start_time) * 1000, 2)
        except requests.ConnectionError as e:
            result["error"] = f"连接失败: {e}"
        except requests.RequestException as e:
            result["error"] = f"请求异常: {e}"

        # 记录历史
        self.history.append({
            "url": result["url"],
            "method": method,
            "status_code": result["status_code"],
            "elapsed_ms": result["elapsed_ms"],
            "success": result["success"],
            "timestamp": time.time(),
        })

        return result

    def batch_call(self, endpoints: List[Dict],
                   delay: float = 0.5) -> List[Dict]:
        """
        批量执行 API 调用

        Args:
            endpoints: [{"url": str, "method": str, "params": dict, ...}]
            delay: 请求间隔秒数

        Returns:
            结果列表
        """
        results = []
        for i, ep in enumerate(endpoints):
            logger.info(f"[{i+1}/{len(endpoints)}] {ep.get('method', 'GET')} {ep.get('url', '')}")
            result = self.call(
                url=ep.get("url", ""),
                method=ep.get("method", "GET"),
                params=ep.get("params"),
                body=ep.get("body"),
                headers=ep.get("headers"),
            )
            results.append(result)

            if delay > 0 and i < len(endpoints) - 1:
                time.sleep(delay)

        return results

    def replay_from_api_map(self, api_map_path: str,
                            filter_category: Optional[str] = None,
                            filter_method: Optional[str] = None) -> List[Dict]:
        """
        从接口图谱文件加载并执行 API

        Args:
            api_map_path: 接口图谱 JSON 文件路径
            filter_category: 只执行某分类的接口
            filter_method: 只执行某方法的接口

        Returns:
            执行结果列表
        """
        with open(api_map_path, "r", encoding="utf-8") as f:
            api_map = json.load(f)

        endpoints = api_map.get("api_endpoints", [])

        # 过滤
        if filter_category:
            endpoints = [ep for ep in endpoints if ep.get("category") == filter_category]
        if filter_method:
            endpoints = [ep for ep in endpoints
                         if ep.get("method", "GET").upper() == filter_method.upper()]

        logger.info(f"从接口图谱加载 {len(endpoints)} 个端点")

        return self.batch_call(endpoints)

    def get_history(self) -> List[Dict]:
        """获取请求历史"""
        return self.history

    def get_stats(self) -> Dict:
        """获取统计信息"""
        if not self.history:
            return {"total": 0}

        total = len(self.history)
        success = sum(1 for h in self.history if h["success"])
        avg_time = sum(h["elapsed_ms"] for h in self.history) / total

        return {
            "total_requests": total,
            "successful": success,
            "failed": total - success,
            "success_rate": f"{success/total*100:.1f}%",
            "avg_response_ms": round(avg_time, 2),
        }


def parse_cookie_string(cookie_str: str) -> Dict[str, str]:
    """解析 Cookie 字符串为字典"""
    cookies = {}
    for pair in cookie_str.split(";"):
        pair = pair.strip()
        if "=" in pair:
            k, v = pair.split("=", 1)
            cookies[k.strip()] = v.strip()
    return cookies


def parse_header_args(header_args: List[str]) -> Dict[str, str]:
    """解析命令行 --header 参数"""
    headers = {}
    for h in header_args:
        if ":" in h:
            k, v = h.split(":", 1)
            headers[k.strip()] = v.strip()
    return headers
