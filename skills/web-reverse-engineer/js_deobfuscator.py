#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JS 反混淆 + API 端点提取器
从 JavaScript 代码中提取 API 端点、请求参数、鉴权方式等信息
"""

import re
import json
import base64
import logging
from urllib.parse import urljoin, urlparse
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field, asdict

logger = logging.getLogger("JSDeobfuscator")


@dataclass
class APIEndpoint:
    """API 端点信息"""
    url: str                        # API 路径（如 /api/v1/users）
    full_url: str = ""              # 完整 URL
    method: str = "GET"             # HTTP 方法
    params: Dict[str, str] = field(default_factory=dict)   # 参数及类型
    headers: Dict[str, str] = field(default_factory=dict)  # 请求头
    body_schema: Dict = field(default_factory=dict)         # 请求体结构
    source_file: str = ""           # 来源 JS 文件
    source_context: str = ""        # 上下文代码片段
    confidence: str = "medium"      # 置信度: high/medium/low
    category: str = ""              # 分类: auth/data/upload/...
    notes: str = ""                 # 备注

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class AuthInfo:
    """鉴权信息"""
    auth_type: str = "unknown"      # bearer/cookie/api_key/basic/custom
    header_name: str = ""           # 鉴权头名称
    token_format: str = ""          # Token 格式模板
    login_endpoint: str = ""        # 登录接口
    token_storage: str = ""         # Token 存储位置 (localStorage/cookie/...)
    refresh_endpoint: str = ""      # Token 刷新接口
    notes: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


class JSDeobfuscator:
    """JS 代码分析与 API 提取器"""

    # ============ API 路径匹配模式 ============

    # 常见 API 路径模式
    API_PATH_PATTERNS = [
        # RESTful API 路径
        r'''["'`](/api/[a-zA-Z0-9_/\-{}\.:]+)["'`]''',
        r'''["'`](/v[0-9]+/[a-zA-Z0-9_/\-{}\.:]+)["'`]''',
        r'''["'`](/rest/[a-zA-Z0-9_/\-{}\.:]+)["'`]''',
        r'''["'`](/graphql[a-zA-Z0-9_/\-]*)["'`]''',

        # 完整 URL 中的 API
        r'''["'`](https?://[a-zA-Z0-9\-\.]+/api/[a-zA-Z0-9_/\-{}\.:]+)["'`]''',
        r'''["'`](https?://[a-zA-Z0-9\-\.]+/v[0-9]+/[a-zA-Z0-9_/\-{}\.:]+)["'`]''',

        # 后端路由常见模式
        r'''["'`](/auth/[a-zA-Z0-9_/\-]+)["'`]''',
        r'''["'`](/login|/logout|/register|/signup|/signin|/oauth)["'`]''',
        r'''["'`](/user[s]?/[a-zA-Z0-9_/\-{}\.:]+)["'`]''',
        r'''["'`](/admin/[a-zA-Z0-9_/\-{}\.:]+)["'`]''',
        r'''["'`](/upload[s]?|/download[s]?|/export|/import)["'`]''',
    ]

    # HTTP 方法调用模式
    HTTP_METHOD_PATTERNS = [
        # fetch API
        r'''fetch\s*\(\s*["'`]([^"'`]+)["'`]\s*(?:,\s*\{[^}]*method\s*:\s*["'`](\w+)["'`])?''',
        # axios
        r'''axios\s*\.\s*(get|post|put|patch|delete|head|options)\s*\(\s*["'`]([^"'`]+)["'`]''',
        r'''axios\s*\(\s*\{[^}]*url\s*:\s*["'`]([^"'`]+)["'`][^}]*method\s*:\s*["'`](\w+)["'`]''',
        # XMLHttpRequest
        r'''\.open\s*\(\s*["'`](\w+)["'`]\s*,\s*["'`]([^"'`]+)["'`]''',
        # jQuery ajax
        r'''\$\.ajax\s*\(\s*\{[^}]*url\s*:\s*["'`]([^"'`]+)["'`][^}]*type\s*:\s*["'`](\w+)["'`]''',
        r'''\$\.(get|post|getJSON)\s*\(\s*["'`]([^"'`]+)["'`]''',
        # ky / got / superagent
        r'''(?:ky|got|superagent)\s*\.\s*(get|post|put|patch|delete)\s*\(\s*["'`]([^"'`]+)["'`]''',
    ]

    # 鉴权相关模式
    AUTH_PATTERNS = [
        # Authorization header
        r'''["'`]Authorization["'`]\s*:\s*["'`]([^"'`]+)["'`]''',
        r'''Authorization\s*["'`]\s*:\s*["'`]Bearer\s+''',
        r'''setHeader\s*\(\s*["'`]Authorization["'`]''',

        # Token 存储
        r'''localStorage\s*\.\s*(?:getItem|setItem)\s*\(\s*["'`]([^"'`]*(?:token|auth|session|jwt)[^"'`]*)["'`]''',
        r'''sessionStorage\s*\.\s*(?:getItem|setItem)\s*\(\s*["'`]([^"'`]*(?:token|auth|session|jwt)[^"'`]*)["'`]''',
        r'''(?:document\.)?cookie\s*[=:]\s*["'`]([^"'`]*(?:token|session|auth)[^"'`]*)''',

        # API Key
        r'''["'`](?:x-api-key|api[_-]?key|apikey|app[_-]?key)["'`]\s*:\s*["'`]([^"'`]+)["'`]''',

        # CSRF
        r'''["'`](?:x-csrf-token|csrf[_-]?token|_token|_csrf)["'`]\s*:\s*''',
    ]

    # Base URL / API 前缀
    BASE_URL_PATTERNS = [
        r'''(?:baseURL|baseUrl|BASE_URL|API_URL|API_BASE|apiUrl|apiBase|apiPrefix)\s*[:=]\s*["'`](https?://[^"'`\s]+)["'`]''',
        r'''(?:baseURL|baseUrl|BASE_URL|API_URL|API_BASE)\s*[:=]\s*["'`](/[^"'`\s]*)["'`]''',
        r'''(?:process\.env\.(?:REACT_APP_|NEXT_PUBLIC_|VITE_|VUE_APP_)?(?:API_URL|BASE_URL|BACKEND_URL))\s*\|\|\s*["'`](https?://[^"'`\s]+)["'`]''',
    ]

    # WebSocket 模式
    WS_PATTERNS = [
        r'''["'`](wss?://[a-zA-Z0-9\-\.:/]+)["'`]''',
        r'''new\s+WebSocket\s*\(\s*["'`]([^"'`]+)["'`]''',
    ]

    def __init__(self, base_url: str = ""):
        self.base_url = base_url
        self.endpoints: List[APIEndpoint] = []
        self.auth_info = AuthInfo()
        self.base_urls: Set[str] = set()
        self.websockets: List[str] = []
        self.env_vars: Dict[str, str] = {}

    def analyze_js(self, js_content: str, source_file: str = "") -> Dict[str, Any]:
        """
        分析单个 JS 文件，提取所有 API 信息

        Args:
            js_content: JS 源码
            source_file: 来源文件名

        Returns:
            分析结果字典
        """
        if not js_content or len(js_content.strip()) < 10:
            return {"endpoints": [], "auth": {}, "base_urls": []}

        # 1. 先尝试反混淆
        js_content = self._basic_deobfuscate(js_content)

        # 2. 提取 Base URL
        self._extract_base_urls(js_content)

        # 3. 提取 API 端点
        self._extract_api_endpoints(js_content, source_file)

        # 4. 提取 HTTP 方法调用
        self._extract_http_calls(js_content, source_file)

        # 5. 提取鉴权信息
        self._extract_auth_info(js_content)

        # 6. 提取 WebSocket
        self._extract_websockets(js_content)

        # 7. 提取环境变量
        self._extract_env_vars(js_content)

        # 8. 去重
        self._deduplicate_endpoints()

        return self.get_results()

    def analyze_multiple_js(self, js_files: Dict[str, str]) -> Dict[str, Any]:
        """
        分析多个 JS 文件

        Args:
            js_files: {文件名/URL: JS内容}

        Returns:
            合并后的分析结果
        """
        for source, content in js_files.items():
            logger.info(f"分析 JS: {source} ({len(content)} chars)")
            self.analyze_js(content, source)

        self._deduplicate_endpoints()
        return self.get_results()

    def get_results(self) -> Dict[str, Any]:
        """获取分析结果"""
        return {
            "endpoints": [ep.to_dict() for ep in self.endpoints],
            "endpoints_count": len(self.endpoints),
            "auth_info": self.auth_info.to_dict(),
            "base_urls": list(self.base_urls),
            "websockets": self.websockets,
            "env_vars": self.env_vars,
        }

    # ============ 核心提取方法 ============

    def _extract_base_urls(self, js: str):
        """提取 Base URL"""
        for pattern in self.BASE_URL_PATTERNS:
            for match in re.finditer(pattern, js, re.IGNORECASE):
                url = match.group(1)
                if url and len(url) > 3:
                    self.base_urls.add(url)

    def _extract_api_endpoints(self, js: str, source_file: str):
        """从 JS 中提取 API 路径"""
        for pattern in self.API_PATH_PATTERNS:
            for match in re.finditer(pattern, js):
                path = match.group(1)
                if self._is_valid_api_path(path):
                    # 获取上下文
                    start = max(0, match.start() - 100)
                    end = min(len(js), match.end() + 100)
                    context = js[start:end].strip()

                    # 推断 HTTP 方法
                    method = self._infer_method_from_context(context, path)

                    # 推断分类
                    category = self._categorize_endpoint(path)

                    ep = APIEndpoint(
                        url=path,
                        full_url=self._resolve_full_url(path),
                        method=method,
                        source_file=source_file,
                        source_context=context[:200],
                        confidence="high" if path.startswith("/api/") else "medium",
                        category=category,
                    )
                    self.endpoints.append(ep)

    def _extract_http_calls(self, js: str, source_file: str):
        """提取 HTTP 方法调用（fetch/axios/XHR/jQuery）"""
        for pattern in self.HTTP_METHOD_PATTERNS:
            for match in re.finditer(pattern, js, re.IGNORECASE):
                groups = match.groups()

                # 不同模式的 group 顺序不同
                if "fetch" in pattern:
                    url = groups[0]
                    method = (groups[1] or "GET").upper() if len(groups) > 1 else "GET"
                elif "axios" in pattern and "." in pattern:
                    method = groups[0].upper()
                    url = groups[1]
                elif ".open" in pattern:
                    method = groups[0].upper()
                    url = groups[1]
                elif "$.ajax" in pattern:
                    url = groups[0]
                    method = (groups[1] or "GET").upper() if len(groups) > 1 else "GET"
                elif "$." in pattern:
                    method = groups[0].upper()
                    if method == "GETJSON":
                        method = "GET"
                    url = groups[1]
                else:
                    method = groups[0].upper() if groups[0] else "GET"
                    url = groups[1] if len(groups) > 1 else groups[0]

                if url and self._is_valid_api_path(url):
                    # 获取上下文提取参数
                    start = max(0, match.start() - 50)
                    end = min(len(js), match.end() + 300)
                    context = js[start:end]

                    # 提取请求体参数
                    params = self._extract_params_from_context(context)
                    headers = self._extract_headers_from_context(context)

                    ep = APIEndpoint(
                        url=url,
                        full_url=self._resolve_full_url(url),
                        method=method,
                        params=params,
                        headers=headers,
                        source_file=source_file,
                        source_context=context[:200],
                        confidence="high",
                        category=self._categorize_endpoint(url),
                    )
                    self.endpoints.append(ep)

    def _extract_auth_info(self, js: str):
        """提取鉴权信息"""
        # Bearer Token
        if re.search(r'Authorization.*Bearer', js, re.IGNORECASE):
            self.auth_info.auth_type = "bearer"
            self.auth_info.header_name = "Authorization"
            self.auth_info.token_format = "Bearer {token}"

        # API Key
        api_key_match = re.search(
            r'''["'`](x-api-key|api[_-]?key|apikey)["'`]\s*:\s*["'`]([^"'`]+)["'`]''',
            js, re.IGNORECASE
        )
        if api_key_match:
            if self.auth_info.auth_type == "unknown":
                self.auth_info.auth_type = "api_key"
            self.auth_info.header_name = api_key_match.group(1)

        # Token 存储位置
        storage_match = re.search(
            r'''(localStorage|sessionStorage)\s*\.\s*(?:getItem|setItem)\s*\(\s*["'`]([^"'`]+)["'`]''',
            js
        )
        if storage_match:
            self.auth_info.token_storage = f"{storage_match.group(1)}.{storage_match.group(2)}"

        # Cookie 鉴权
        cookie_match = re.search(
            r'''(?:document\.)?cookie.*(?:token|session|auth)''',
            js, re.IGNORECASE
        )
        if cookie_match and self.auth_info.auth_type == "unknown":
            self.auth_info.auth_type = "cookie"

        # 登录端点
        login_match = re.search(
            r'''["'`](/(?:api/)?(?:v\d+/)?(?:auth/)?(?:login|signin|authenticate))["'`]''',
            js, re.IGNORECASE
        )
        if login_match:
            self.auth_info.login_endpoint = login_match.group(1)

        # Token 刷新端点
        refresh_match = re.search(
            r'''["'`](/(?:api/)?(?:v\d+/)?(?:auth/)?(?:refresh|token/refresh))["'`]''',
            js, re.IGNORECASE
        )
        if refresh_match:
            self.auth_info.refresh_endpoint = refresh_match.group(1)

        # CSRF
        csrf_match = re.search(
            r'''["'`](x-csrf-token|csrf[_-]?token|_token|_csrf)["'`]''',
            js, re.IGNORECASE
        )
        if csrf_match:
            self.auth_info.notes += f"CSRF token header: {csrf_match.group(1)}; "

    def _extract_websockets(self, js: str):
        """提取 WebSocket 地址"""
        for pattern in self.WS_PATTERNS:
            for match in re.finditer(pattern, js):
                ws_url = match.group(1)
                if ws_url not in self.websockets:
                    self.websockets.append(ws_url)

    def _extract_env_vars(self, js: str):
        """提取环境变量引用"""
        env_patterns = [
            r'''process\.env\.(\w+)''',
            r'''import\.meta\.env\.(\w+)''',
            r'''__ENV__\.(\w+)''',
        ]
        for pattern in env_patterns:
            for match in re.finditer(pattern, js):
                var_name = match.group(1)
                # 尝试找到默认值
                context_start = match.start()
                context_end = min(len(js), match.end() + 100)
                context = js[context_start:context_end]
                default_match = re.search(r'''\|\|\s*["'`]([^"'`]+)["'`]''', context)
                default_val = default_match.group(1) if default_match else ""
                self.env_vars[var_name] = default_val

    # ============ 辅助方法 ============

    def _basic_deobfuscate(self, js: str) -> str:
        """基础反混淆处理"""
        # 1. 解码 Unicode 转义
        try:
            js = js.encode().decode('unicode_escape')
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass

        # 2. 解码十六进制字符串 \x41\x42 → AB
        def hex_replace(m):
            try:
                return bytes.fromhex(m.group(1)).decode('utf-8', errors='replace')
            except Exception:
                return m.group(0)
        js = re.sub(r'\\x([0-9a-fA-F]{2})', hex_replace, js)

        # 3. 解码 Base64 字符串（常见于混淆）
        def b64_replace(m):
            try:
                decoded = base64.b64decode(m.group(1)).decode('utf-8', errors='replace')
                # 只替换看起来像 URL/路径的
                if '/' in decoded or 'http' in decoded.lower():
                    return f'"{decoded}"'
            except Exception:
                pass
            return m.group(0)
        js = re.sub(r'''atob\s*\(\s*["'`]([A-Za-z0-9+/=]+)["'`]\s*\)''', b64_replace, js)

        # 4. 简单字符串拼接还原: "a" + "b" + "c" → "abc"
        def concat_replace(m):
            parts = re.findall(r'''["'`]([^"'`]*)["'`]''', m.group(0))
            if parts:
                return f'"{"".join(parts)}"'
            return m.group(0)
        js = re.sub(r'''["'`][^"'`]*["'`](?:\s*\+\s*["'`][^"'`]*["'`]){2,}''', concat_replace, js)

        return js

    def _is_valid_api_path(self, path: str) -> bool:
        """判断是否为有效的 API 路径"""
        if not path or len(path) < 3:
            return False

        # 排除静态资源
        static_exts = ('.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg',
                       '.ico', '.woff', '.woff2', '.ttf', '.eot', '.map',
                       '.html', '.htm', '.xml', '.txt', '.md')
        if any(path.lower().endswith(ext) for ext in static_exts):
            return False

        # 排除明显的非 API 路径
        exclude_patterns = [
            r'^/$',
            r'^/#',
            r'^/static/',
            r'^/assets/',
            r'^/public/',
            r'^/images/',
            r'^/fonts/',
            r'^/css/',
            r'^/js/',
            r'^/node_modules/',
            r'^\w+://',  # 非 http(s) 协议
        ]
        for pattern in exclude_patterns:
            if re.match(pattern, path):
                # 但如果是 http(s) 开头的 API URL，保留
                if path.startswith("http") and ("/api/" in path or "/v" in path):
                    return True
                return False

        return True

    def _resolve_full_url(self, path: str) -> str:
        """将相对路径解析为完整 URL"""
        if path.startswith("http"):
            return path
        if self.base_url:
            return urljoin(self.base_url, path)
        if self.base_urls:
            base = next(iter(self.base_urls))
            return urljoin(base, path)
        return path

    def _infer_method_from_context(self, context: str, path: str) -> str:
        """从上下文推断 HTTP 方法"""
        ctx_lower = context.lower()

        # 明确的方法声明
        method_match = re.search(r'''method\s*[:=]\s*["'`](get|post|put|patch|delete)["'`]''',
                                 ctx_lower)
        if method_match:
            return method_match.group(1).upper()

        # 从路径推断
        path_lower = path.lower()
        if any(kw in path_lower for kw in ["create", "add", "new", "register", "signup", "login", "upload"]):
            return "POST"
        if any(kw in path_lower for kw in ["update", "edit", "modify"]):
            return "PUT"
        if any(kw in path_lower for kw in ["delete", "remove"]):
            return "DELETE"

        # 从上下文推断
        if "post" in ctx_lower and ("body" in ctx_lower or "data" in ctx_lower):
            return "POST"

        return "GET"

    def _categorize_endpoint(self, path: str) -> str:
        """对 API 端点进行分类"""
        path_lower = path.lower()

        categories = {
            "auth": ["login", "logout", "register", "signup", "signin", "auth", "oauth", "token", "refresh"],
            "user": ["user", "profile", "account", "me"],
            "data": ["list", "search", "query", "filter", "get"],
            "crud": ["create", "update", "delete", "edit", "add", "remove"],
            "upload": ["upload", "file", "image", "media", "attachment"],
            "export": ["export", "download", "report"],
            "notification": ["notification", "message", "alert", "push"],
            "config": ["config", "setting", "preference"],
            "admin": ["admin", "manage", "dashboard"],
        }

        for cat, keywords in categories.items():
            if any(kw in path_lower for kw in keywords):
                return cat

        return "general"

    def _extract_params_from_context(self, context: str) -> Dict[str, str]:
        """从上下文代码中提取请求参数"""
        params = {}

        # JSON body 中的 key
        body_match = re.search(r'''(?:body|data|params)\s*[:=]\s*\{([^}]{1,500})\}''', context)
        if body_match:
            body_str = body_match.group(1)
            # 提取 key: value 或 key 名
            for key_match in re.finditer(r'''["'`]?(\w+)["'`]?\s*:''', body_str):
                key = key_match.group(1)
                if key not in ("method", "headers", "body", "mode", "cache", "credentials"):
                    params[key] = "unknown"

        # URL 查询参数
        query_match = re.search(r'''\?([a-zA-Z_]+=)''', context)
        if query_match:
            query_str = context[query_match.start():query_match.start() + 200]
            for param_match in re.finditer(r'''([a-zA-Z_]\w*)=''', query_str):
                params[param_match.group(1)] = "string"

        return params

    def _extract_headers_from_context(self, context: str) -> Dict[str, str]:
        """从上下文中提取请求头"""
        headers = {}

        headers_match = re.search(r'''headers\s*[:=]\s*\{([^}]{1,500})\}''', context)
        if headers_match:
            headers_str = headers_match.group(1)
            for h_match in re.finditer(r'''["'`]([^"'`]+)["'`]\s*:\s*["'`]([^"'`]*)["'`]''', headers_str):
                headers[h_match.group(1)] = h_match.group(2)

        return headers

    def _deduplicate_endpoints(self):
        """去重：相同 URL + Method 只保留一个（优先保留 confidence=high）"""
        seen = {}
        for ep in self.endpoints:
            key = f"{ep.method}:{ep.url}"
            if key not in seen or (ep.confidence == "high" and seen[key].confidence != "high"):
                seen[key] = ep
        self.endpoints = list(seen.values())

        # 按分类排序
        category_order = ["auth", "user", "data", "crud", "upload", "export",
                          "notification", "config", "admin", "general"]
        self.endpoints.sort(key=lambda ep: (
            category_order.index(ep.category) if ep.category in category_order else 99,
            ep.url
        ))
