# 网站源码逆向分析 - 通用抓取脚本
# 用法: python web_fetch_source.py <url> [output_dir]
# 功能: 抓取目标URL的原始HTML + 所有关联JS文件(含chunk) + Source Map + 提取关键信息
import urllib.request
import ssl
import re
import json
import os
import sys
import time
from html.parser import HTMLParser
from collections import defaultdict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 文件写入锁（防止并行抓取时同名文件竞态）
_file_lock = threading.Lock()

# ============ 配置 ============
DEFAULT_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
DEFAULT_HEADERS = {
    'User-Agent': DEFAULT_USER_AGENT,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'identity',  # 避免gzip解码问题
}

# 全局Cookie（可通过 --cookie 参数设置）
GLOBAL_COOKIE = ''

# 全局额外请求头（可通过 --header 参数设置）
GLOBAL_EXTRA_HEADERS = {}

# SSL上下文（跳过验证）
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# 并行抓取配置
MAX_WORKERS = 5          # 并行线程数
REQUEST_TIMEOUT = 20     # 单个请求超时(秒)
MAX_RETRIES = 2          # 失败重试次数
RETRY_DELAY = 1          # 重试间隔(秒)
REQUEST_INTERVAL = 0.2   # 同线程请求间隔(秒)，避免429

# Chunk递归抓取配置
MAX_CHUNK_DEPTH = 2      # chunk递归深度上限
MAX_TOTAL_JS = 100       # JS文件总数上限，防止无限扩散

# 静态资源后缀过滤
STATIC_EXTS = {'.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.woff', '.woff2', '.ttf', '.ico', '.map', '.webp', '.mp4', '.mp3'}

# ============ 工具函数 ============

def normalize_url(url, base_url=''):
    """规范化URL，处理相对路径、协议相对路径等"""
    if not url or url.startswith('data:') or url.startswith('blob:'):
        return None
    url = url.strip()
    if url.startswith('//'):
        return 'https:' + url
    if url.startswith('/'):
        if base_url:
            parsed = urllib.parse.urlparse(base_url)
            return f'{parsed.scheme}://{parsed.netloc}{url}'
        return None
    if not url.startswith('http'):
        if base_url:
            return urllib.parse.urljoin(base_url, url)
        return None
    return url


def fetch_url(url, timeout=REQUEST_TIMEOUT, retries=MAX_RETRIES):
    """抓取URL内容，返回 (文本, 状态码)，支持重试和Cookie"""
    for attempt in range(retries + 1):
        try:
            headers = dict(DEFAULT_HEADERS)
            if GLOBAL_COOKIE:
                headers['Cookie'] = GLOBAL_COOKIE
            headers.update(GLOBAL_EXTRA_HEADERS)
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=timeout) as resp:
                charset = 'utf-8'
                content_type = resp.headers.get('Content-Type', '')
                if 'charset=' in content_type:
                    charset = content_type.split('charset=')[-1].strip().split(';')[0]
                raw = resp.read()
                try:
                    return raw.decode(charset, errors='ignore'), resp.status
                except:
                    return raw.decode('utf-8', errors='ignore'), resp.status
        except urllib.error.HTTPError as e:
            if e.code == 429:
                # 限流：等待后重试
                wait = RETRY_DELAY * (attempt + 1) * 2
                print(f'    [429] 限流，等待 {wait}s 后重试...')
                time.sleep(wait)
                continue
            if e.code in (403, 404):
                return '', e.code
            if attempt < retries:
                time.sleep(RETRY_DELAY)
                continue
            print(f'  [HTTP {e.code}] {url}')
            return '', e.code
        except Exception as e:
            if attempt < retries:
                time.sleep(RETRY_DELAY)
                continue
            print(f'  [ERROR] {url}: {e}')
            return '', 0
    return '', 0


def resolve_js_url(src, page_url):
    """解析JS文件的完整URL"""
    if not src or src.startswith('data:') or src.startswith('blob:'):
        return None
    # 过滤明显非业务JS的资源
    skip_patterns = ['google-analytics', 'gtag', 'facebook', 'doubleclick',
                     'adservice', 'analytics', 'hotjar', 'clarity',
                     'googletagmanager', 'newrelic', 'sentry']
    for p in skip_patterns:
        if p in src.lower():
            return None
    return normalize_url(src, page_url)


# ============ HTML解析 ============

class SourceExtractor:
    """从HTML源码中提取关键信息"""

    def __init__(self, html, page_url):
        self.html = html
        self.page_url = page_url
        self.js_files = []
        self.inline_scripts = []
        self.css_files = []
        self.links = []
        self.meta_info = {}
        self.initial_state = {}
        self.service_workers = []
        self.websocket_urls = []

    def extract_all(self):
        self._extract_scripts()
        self._extract_styles()
        self._extract_links()
        self._extract_meta()
        self._extract_initial_state()
        self._extract_service_workers()
        self._extract_websocket_refs()
        return self

    def _extract_scripts(self):
        # 外部JS文件
        script_srcs = re.findall(r'<script[^>]*\ssrc=["\']([^"\']+)["\']', self.html)
        for src in script_srcs:
            url = resolve_js_url(src, self.page_url)
            if url:
                self.js_files.append(url)

        # 内联脚本
        inline = re.findall(r'<script[^>]*>(.*?)</script>', self.html, re.DOTALL)
        for s in inline:
            s = s.strip()
            if s and len(s) > 10:
                self.inline_scripts.append(s)

    def _extract_styles(self):
        css_hrefs = re.findall(r'<link[^>]*\shref=["\']([^"\']+\.css[^"\']*)["\']', self.html)
        for href in css_hrefs:
            url = normalize_url(href, self.page_url)
            if url:
                self.css_files.append(url)

    def _extract_links(self):
        hrefs = re.findall(r'<a[^>]*\shref=["\']([^"\']+)["\']', self.html)
        for href in hrefs:
            if href and not href.startswith('#') and not href.startswith('javascript:'):
                self.links.append(href)

    def _extract_meta(self):
        # 技术栈识别
        if '__NEXT_DATA__' in self.html or 'next-route-announcer' in self.html:
            self.meta_info['framework'] = 'Next.js'
        if '__NUXT__' in self.html:
            self.meta_info['framework'] = 'Nuxt.js'
        if 'ng-app' in self.html or 'ng-version' in self.html:
            self.meta_info['framework'] = 'Angular'
        if '__INITIAL_STATE__' in self.html:
            self.meta_info['framework'] = 'Vue (SSR)'
        if 'data-reactroot' in self.html:
            self.meta_info['framework'] = 'React (SSR)'
        if 'data-v-' in self.html:
            self.meta_info['framework'] = 'Vue'
        if 'vite' in self.html.lower():
            self.meta_info['bundler'] = 'Vite'
        if 'webpack' in self.html.lower():
            self.meta_info['bundler'] = 'Webpack'

        # SPA检测
        body_content = re.search(r'<body[^>]*>(.*?)</body>', self.html, re.DOTALL)
        if body_content:
            body = body_content.group(1)
            # 去除script标签后看内容量
            body_no_script = re.sub(r'<script[^>]*>.*?</script>', '', body, flags=re.DOTALL)
            body_no_script = re.sub(r'<[^>]+>', '', body_no_script).strip()
            if len(body_no_script) < 100 and len(self.js_files) > 0:
                self.meta_info['render_mode'] = 'CSR (SPA)'
            elif '__NEXT_DATA__' in self.html or '__NUXT__' in self.html:
                self.meta_info['render_mode'] = 'SSR'
            else:
                self.meta_info['render_mode'] = 'CSR'

        # Source Map引用
        sourcemap = re.findall(r'sourceMappingURL\s*=\s*(\S+)', self.html)
        if sourcemap:
            self.meta_info['source_maps'] = sourcemap

    def _extract_initial_state(self):
        # Next.js: __NEXT_DATA__
        m = re.search(r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', self.html, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
                self.initial_state['__NEXT_DATA__'] = data
                # 提取路由信息
                if 'buildId' in data:
                    self.meta_info['next_buildId'] = data['buildId']
                if 'page' in data:
                    self.meta_info['next_page'] = data['page']
            except:
                pass

        # Vue SSR: window.__INITIAL_STATE__
        m = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});\s*</script>', self.html, re.DOTALL)
        if m:
            try:
                self.initial_state['__INITIAL_STATE__'] = json.loads(m.group(1))
            except:
                self.initial_state['__INITIAL_STATE__raw'] = m.group(1)[:5000]

        # Nuxt.js: __NUXT__
        m = re.search(r'window\.__NUXT__\s*=\s*(.*?);\s*</script>', self.html, re.DOTALL)
        if m:
            self.initial_state['__NUXT__raw'] = m.group(1)[:5000]

        # Pinia
        if 'window.__pinia__' in self.html or '__pinia__' in self.html:
            self.meta_info['state_management'] = 'Pinia'
        if '__vuex__' in self.html or 'Vuex' in self.html:
            self.meta_info['state_management'] = 'Vuex'

    def _extract_service_workers(self):
        """检测Service Worker注册"""
        sw_patterns = [
            r'navigator\.serviceWorker\.register\s*\(\s*["\']([^"\']+)["\']',
            r'registerServiceWorker\s*\(\s*["\']([^"\']+)["\']',
            r'sw\.js|service-worker\.js|sw\.ts',
        ]
        for pat in sw_patterns:
            matches = re.findall(pat, self.html)
            for m in matches:
                url = normalize_url(m, self.page_url) if not m.startswith('http') else m
                if url:
                    self.service_workers.append(url)

    def _extract_websocket_refs(self):
        """检测HTML中的WebSocket引用"""
        ws_patterns = [
            r'(wss?://[a-zA-Z0-9._/-]+)',
            r'new\s+WebSocket\s*\(\s*["\']([^"\']+)["\']',
        ]
        for pat in ws_patterns:
            matches = re.findall(pat, self.html)
            for m in matches:
                if m not in self.websocket_urls:
                    self.websocket_urls.append(m)


# ============ JS分析 ============

class JSAnalyzer:
    """分析JS源码，提取API端点、鉴权信息、路由等"""

    # API路径提取正则（通用）
    API_PATTERNS = [
        # 方法-URL对（最信息量）
        (r'method:\s*["\'](GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)["\'].*?url:\s*["\']([^"\']+)["\']', 'method-url', True),
        # 通用API路径
        (r'["\'`](/(?:api|x|v[0-9]+|pgc|graphql|gql|rest|rpc|auth|user|admin|ws)/[a-zA-Z0-9_/.-]+)["\'`]', 'api-path', False),
        # 完整域名API URL
        (r'(https?://api\.[a-z0-9.-]+\.[a-z]+/[a-zA-Z0-9_/.-]+)', 'api-domain', False),
        # Passport/认证域名
        (r'(https?://[a-z0-9.-]*passport[a-z0-9.-]*\.[a-z]+/[a-zA-Z0-9_/.-]+)', 'passport', False),
        # GraphQL端点
        (r'(https?://[a-z0-9.-]*graphql[a-z0-9.-]*\.[a-z]+)', 'graphql', False),
        # WebSocket端点（严格匹配wss?协议开头）
        (r'(wss?://[a-zA-Z0-9._:/?=&-]+)', 'websocket', False),
        # 业务路径（常见业务模块）
        (r'["\'`](/(?:medialist|audio|live|member|msg|dynamic|feed|account|search|comment|follow|like|favorite|collect|upload|download|pay|order|cart|setting|profile|notification|message|chat|im)/[a-zA-Z0-9_/.-]+)["\'`]', 'biz-path', False),
    ]

    # 鉴权关键词（正则，避免 token 匹配 moment.js 的 unusedTokens/formattingTokens 等）
    AUTH_PATTERNS = [
        (r'\bAuthorization\b', 'Authorization'),
        (r'\bBearer\s+', 'Bearer'),
        (r'\b(?:access_token|auth_token|jwt_token|id_token|refresh_token|csrf_token)\b', 'named_token'),
        (r'\bcsrf\b', 'csrf'),
        (r'\bCookie\b', 'Cookie'),
        (r'\bwithCredentials\b', 'withCredentials'),
        (r'\bX-Token\b', 'X-Token'),
        (r'\bAccess-Token\b', 'Access-Token'),
        (r'localStorage\.setItem', 'localStorage.setItem'),
        (r'sessionStorage\.setItem', 'sessionStorage.setItem'),
        (r'interceptors\.request', 'interceptors.request'),
        (r'interceptors\.response', 'interceptors.response'),
        (r'\bgetToken\b', 'getToken'),
        (r'\bsetToken\b', 'setToken'),
        (r'\brefreshToken\b', 'refreshToken'),
    ]

    # 签名/加密关键词（更精确，避免 sign 匹配 design/assign 等）
    SIGN_PATTERNS = [
        (r'\bsign(?:ature)?\s*[:=]\s*["\']|\.sign\s*\(', 'sign'),
        (r'\b(?:hmac|HMAC)\s*\(', 'hmac'),
        (r'\b(?:md5|MD5)\s*\(', 'md5'),
        (r'\b(?:sha256|SHA256|sha1|SHA1)\s*\(', 'sha'),
        (r'\b(?:encrypt|decrypt)\s*\(', 'encrypt_decrypt'),
        (r'\bCryptoJS\b', 'CryptoJS'),
        (r'\bcrypto\.subtle\b', 'crypto.subtle'),
        (r'\b(?:appkey|app_key|secret_key|sign_key)\s*[:=]', 'sign_key'),
    ]

    # 路由提取正则
    ROUTE_PATTERNS = [
        r'path:\s*["\']([^"\']+)["\']\s*,\s*component:',
        r'path:\s*["\']([^"\']+)["\']\s*,\s*name:',
        r'path:\s*["\'](/[^"\']+)["\']',
        r'<Route\s+path=["\']([^"\']+)["\']',
    ]

    def __init__(self, js_content, source_name=''):
        self.content = js_content
        self.source = source_name
        self.apis = []
        self.auth_info = []
        self.sign_info = []
        self.routes = []
        self.chunk_refs = []
        self.sourcemap_url = None
        self.websocket_urls = []
        self.sw_register = []

    def analyze(self):
        self._extract_apis()
        self._extract_auth()
        self._extract_signing()
        self._extract_routes()
        self._extract_chunk_refs()
        self._extract_sourcemap()
        self._extract_websocket()
        self._extract_service_worker()
        return self

    def _extract_apis(self):
        for pattern, ptype, is_method_url in self.API_PATTERNS:
            try:
                matches = re.findall(pattern, self.content)
            except:
                continue
            for m in matches:
                if is_method_url:
                    method, path = m
                    self.apis.append({'method': method.strip(), 'path': path, 'type': ptype, 'source': self.source})
                else:
                    path = m
                    # 过滤静态资源
                    if any(path.endswith(ext) for ext in STATIC_EXTS):
                        continue
                    if len(path) < 5:
                        continue
                    self.apis.append({'method': '', 'path': path, 'type': ptype, 'source': self.source})

    def _extract_auth(self):
        for pattern, kw in self.AUTH_PATTERNS:
            for m in re.finditer(pattern, self.content, re.IGNORECASE):
                start = max(0, m.start() - 80)
                end = min(len(self.content), m.end() + 150)
                ctx = self.content[start:end].replace('\n', ' ')
                self.auth_info.append({'keyword': kw, 'context': ctx, 'source': self.source})

    def _extract_signing(self):
        for pattern, kw in self.SIGN_PATTERNS:
            for m in re.finditer(pattern, self.content, re.IGNORECASE):
                start = max(0, m.start() - 80)
                end = min(len(self.content), m.end() + 200)
                ctx = self.content[start:end].replace('\n', ' ')
                self.sign_info.append({'keyword': kw, 'context': ctx, 'source': self.source})

        # 提取签名用打乱数组
        mixin_match = re.search(r'\[(\d+(?:,\s*\d+){30,})\]', self.content)
        if mixin_match:
            self.sign_info.append({
                'keyword': 'shuffle_array',
                'context': f'[{mixin_match.group(1)}]',
                'source': self.source
            })

    def _extract_routes(self):
        """提取前端路由定义"""
        seen = set()
        for pat in self.ROUTE_PATTERNS:
            matches = re.findall(pat, self.content)
            for path in matches:
                path = path.strip()
                if path and path not in seen and not path.endswith(('.js', '.css', '.png', '.svg')):
                    seen.add(path)
                    self.routes.append(path)

    def _extract_chunk_refs(self):
        """提取chunk/lazy加载的JS引用

        支持的格式：
        - Webpack: "chunk-xxx.js", "vendor-xxx.js"
        - Vite: "./xxx-hash.js", "./xxx.mjs-hash.js"
        - Module Federation: "__loadShare__xxx.js", "__remoteEntry__xxx.js"
        - 动态import: import("./xxx.js")
        - 通用: from './xxx.js'
        """
        patterns = [
            # 带chunk/lazy/async/vendor关键字的引用
            r'["\']([^"\']*(?:chunk|lazy|async|vendor)[^"\']*\.js)["\']',
            # Vite/ESM 风格的相对路径导入
            r'''from\s+['"](\.{1,2}/[^'"]+\.js)['"]''',
            # 动态import
            r'import\s*\(\s*["\']([^"\']+\.js)["\']\s*\)',
            # Module Federation
            r'["\']([^"\']*(?:__loadShare__|__remoteEntry__|remoteEntry)[^"\']*\.js)["\']',
            # 通用相对路径JS引用（在引号中，含短hash格式）
            r'''["'](\.{1,2}/[a-zA-Z0-9_-]+-[a-zA-Z0-9]{4,}\.js)["']''',
        ]
        seen = set()
        for pat in patterns:
            matches = re.findall(pat, self.content)
            for m in matches:
                # 过滤明显非业务JS
                skip_kw = ['polyfill', 'sentry', 'hotjar', 'clarity', 'analytics', 'gtag', 'fb-sdk']
                if any(kw in m.lower() for kw in skip_kw):
                    continue
                if m not in seen:
                    seen.add(m)
                    self.chunk_refs.append(m)

    def _extract_sourcemap(self):
        """提取Source Map引用"""
        m = re.search(r'sourceMappingURL\s*=\s*(\S+\.map)', self.content)
        if m:
            self.sourcemap_url = m.group(1)

    def _extract_websocket(self):
        """提取JS中的WebSocket引用"""
        patterns = [
            r'new\s+WebSocket\s*\(\s*["\']([^"\']+)["\']',
            r'(wss?://[a-zA-Z0-9._:/?=&-]+)',
        ]
        seen = set()
        for pat in patterns:
            matches = re.findall(pat, self.content)
            for m in matches:
                if m not in seen:
                    # 过滤误报：排除含 "browser" 但不含 "ws" 协议的普通字符串
                    if m.startswith('ws') or 'websocket' in m.lower() or 'socket.io' in m.lower() or 'sockjs' in m.lower():
                        seen.add(m)
                        self.websocket_urls.append(m)

    def _extract_service_worker(self):
        """提取Service Worker注册"""
        patterns = [
            r'navigator\.serviceWorker\.register\s*\(\s*["\']([^"\']+)["\']',
            r'registerServiceWorker\s*\(\s*["\']([^"\']+)["\']',
        ]
        for pat in patterns:
            matches = re.findall(pat, self.content)
            for m in matches:
                self.sw_register.append(m)


# ============ 并行JS抓取 ============

def fetch_and_analyze_js(js_url, js_dir, page_url, idx, total):
    """抓取并分析单个JS文件，返回分析结果"""
    print(f'  [{idx}/{total}] {js_url.split("/")[-1].split("?")[0]}')
    content, status = fetch_url(js_url)

    if not content:
        return None

    # 文件名生成和写入加锁，防止并行时同名覆盖
    with _file_lock:
        fname = js_url.split('/')[-1].split('?')[0]
        if not fname.endswith('.js'):
            fname += '.js'
        fpath = os.path.join(js_dir, fname)
        if os.path.exists(fpath):
            base, ext = os.path.splitext(fname)
            counter = 1
            while os.path.exists(os.path.join(js_dir, f'{base}_{counter}{ext}')):
                counter += 1
            fname = f'{base}_{counter}{ext}'
            fpath = os.path.join(js_dir, fname)
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)

    # 分析JS（不需要锁，各线程独立分析）
    analyzer = JSAnalyzer(content, fname).analyze()

    return {
        'filename': fname,
        'url': js_url,
        'size': len(content),
        'api_count': len(analyzer.apis),
        'auth_count': len(analyzer.auth_info),
        'sign_count': len(analyzer.sign_info),
        'route_count': len(analyzer.routes),
        'apis': analyzer.apis,
        'auth_info': analyzer.auth_info,
        'sign_info': analyzer.sign_info,
        'routes': analyzer.routes,
        'chunk_refs': analyzer.chunk_refs,
        'sourcemap_url': analyzer.sourcemap_url,
        'websocket_urls': analyzer.websocket_urls,
        'sw_register': analyzer.sw_register,
    }


# ============ Source Map下载 ============

def download_sourcemap(map_url, js_url, output_dir):
    """下载Source Map文件"""
    full_url = normalize_url(map_url, js_url)
    if not full_url:
        return None

    fname = full_url.split('/')[-1].split('?')[0]
    map_dir = os.path.join(output_dir, 'sourcemaps')
    os.makedirs(map_dir, exist_ok=True)
    fpath = os.path.join(map_dir, fname)

    print(f'    [SourceMap] 下载 {fname}...')
    content, status = fetch_url(full_url)
    if content:
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        # 尝试解析Source Map，提取原始文件列表
        try:
            sm = json.loads(content)
            sources = sm.get('sources', [])
            if sources:
                print(f'    [SourceMap] 包含 {len(sources)} 个原始文件: {sources[:5]}...')
                return {'url': full_url, 'sources': sources, 'size': len(content)}
        except:
            pass
        return {'url': full_url, 'sources': [], 'size': len(content)}
    return None


# ============ 主流程 ============

def analyze_website(url, output_dir='web_analysis'):
    """主分析流程"""
    print(f'[*] 目标: {url}')
    print(f'[*] 输出目录: {output_dir}')
    print()

    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    js_dir = os.path.join(output_dir, 'js')
    os.makedirs(js_dir, exist_ok=True)

    # ---- 步骤1: 抓取HTML ----
    print('[1] 抓取原始HTML...')
    html, status = fetch_url(url)
    if not html:
        print('[!] 无法获取HTML，退出')
        return None

    html_path = os.path.join(output_dir, 'page_source.html')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'    HTML长度: {len(html)}, 状态码: {status}, 已保存到 {html_path}')

    # ---- 步骤2: 解析HTML提取信息 ----
    print('\n[2] 解析HTML结构...')
    extractor = SourceExtractor(html, url).extract_all()

    print(f'    外部JS文件: {len(extractor.js_files)}')
    print(f'    内联脚本: {len(extractor.inline_scripts)}')
    print(f'    CSS文件: {len(extractor.css_files)}')
    print(f'    页面链接: {len(extractor.links)}')
    print(f'    技术栈: {extractor.meta_info}')
    print(f'    初始状态: {list(extractor.initial_state.keys())}')
    if extractor.service_workers:
        print(f'    Service Workers: {extractor.service_workers}')
    if extractor.websocket_urls:
        print(f'    WebSocket引用: {extractor.websocket_urls}')

    # 保存HTML提取结果
    html_info = {
        'url': url,
        'js_files': extractor.js_files,
        'css_files': extractor.css_files,
        'meta_info': extractor.meta_info,
        'initial_state_keys': list(extractor.initial_state.keys()),
        'links_count': len(extractor.links),
        'service_workers': extractor.service_workers,
        'websocket_urls': extractor.websocket_urls,
    }
    with open(os.path.join(output_dir, 'html_info.json'), 'w', encoding='utf-8') as f:
        json.dump(html_info, f, ensure_ascii=False, indent=2)

    # 保存initial_state
    if extractor.initial_state:
        with open(os.path.join(output_dir, 'initial_state.json'), 'w', encoding='utf-8') as f:
            json.dump(extractor.initial_state, f, ensure_ascii=False, indent=2, default=str)

    # ---- 步骤3: 并行抓取并分析JS文件 ----
    print(f'\n[3] 并行抓取并分析JS文件 (线程数={MAX_WORKERS})...')

    # 收集所有JS URL（主入口 + 后续chunk）
    all_js_urls = list(extractor.js_files)
    fetched_urls = set(extractor.js_files)  # 已抓取URL集合
    all_results = []
    sourcemap_results = []

    # 按优先级排序主入口
    def js_priority(u):
        fname = u.split('/')[-1].lower()
        if any(k in fname for k in ['vendor', 'vendors']):
            return 0
        if 'index' in fname:
            return 1
        if 'app' in fname:
            return 2
        if 'main' in fname:
            return 3
        return 9

    all_js_urls.sort(key=js_priority)

    # 分轮次抓取：先主入口，再chunk
    depth = 0
    total_fetched = 0

    while all_js_urls and depth <= MAX_CHUNK_DEPTH and total_fetched < MAX_TOTAL_JS:
        current_batch = all_js_urls[:MAX_TOTAL_JS - total_fetched]
        all_js_urls = all_js_urls[len(current_batch):]
        batch_size = len(current_batch)

        print(f'\n  --- 第{depth+1}轮: {batch_size} 个JS文件 ---')

        # 并行抓取
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {}
            for i, js_url in enumerate(current_batch):
                future = executor.submit(fetch_and_analyze_js, js_url, js_dir, url, i+1, batch_size)
                futures[future] = js_url

            for future in as_completed(futures):
                result = future.result()
                if result:
                    all_results.append(result)
                    total_fetched += 1

                    # 下载Source Map
                    if result['sourcemap_url']:
                        sm_info = download_sourcemap(result['sourcemap_url'], result['url'], output_dir)
                        if sm_info:
                            sourcemap_results.append(sm_info)

                    # 收集新的chunk引用，加入下一轮
                    if depth < MAX_CHUNK_DEPTH:
                        chunk_added = 0
                        for chunk_ref in result['chunk_refs']:
                            # 基于当前JS的URL解析相对路径
                            chunk_url = normalize_url(chunk_ref, result['url'])
                            if not chunk_url:
                                continue
                            if chunk_url in fetched_urls:
                                continue
                            # 域名过滤：chunk URL 与来源JS同域即可（CDN场景下JS和页面域名不同）
                            # 也可与页面同域（普通场景）
                            parsed_js = urllib.parse.urlparse(result['url'])
                            parsed_page = urllib.parse.urlparse(url)
                            parsed_chunk = urllib.parse.urlparse(chunk_url)
                            chunk_domain = parsed_chunk.netloc.lower()
                            js_domain = parsed_js.netloc.lower()
                            page_domain = parsed_page.netloc.lower()
                            # 同域判断：chunk与JS同域 OR chunk与页面同域 OR 子域关系
                            is_same_domain = (
                                chunk_domain == js_domain or
                                chunk_domain == page_domain or
                                chunk_domain.endswith('.' + js_domain) or
                                chunk_domain.endswith('.' + page_domain) or
                                js_domain.endswith('.' + chunk_domain) or
                                page_domain.endswith('.' + chunk_domain)
                            )
                            if is_same_domain:
                                fetched_urls.add(chunk_url)
                                all_js_urls.append(chunk_url)
                                chunk_added += 1

        depth += 1

    # ---- 步骤4: 分析内联脚本 ----
    print(f'\n[4] 分析内联脚本 ({len(extractor.inline_scripts)} 个)...')
    inline_apis = []
    inline_auth = []
    inline_sign = []
    for i, script in enumerate(extractor.inline_scripts):
        analyzer = JSAnalyzer(script, f'inline_script_{i+1}').analyze()
        inline_apis.extend(analyzer.apis)
        inline_auth.extend(analyzer.auth_info)
        inline_sign.extend(analyzer.sign_info)

    # ---- 步骤5: 去重并汇总 ----
    print(f'\n[5] 汇总结果...')

    # 合并所有结果
    all_apis = inline_apis
    all_auth = inline_auth
    all_sign = inline_sign
    all_routes = []
    all_ws = list(extractor.websocket_urls)
    all_sw = list(extractor.service_workers)
    js_results_summary = []

    for r in all_results:
        all_apis.extend(r['apis'])
        all_auth.extend(r['auth_info'])
        all_sign.extend(r['sign_info'])
        all_routes.extend(r['routes'])
        all_ws.extend(r['websocket_urls'])
        all_sw.extend(r['sw_register'])
        js_results_summary.append({
            'filename': r['filename'],
            'url': r['url'],
            'size': r['size'],
            'api_count': r['api_count'],
            'auth_count': r['auth_count'],
            'sign_count': r['sign_count'],
            'route_count': r['route_count'],
        })

    # API去重
    seen_apis = set()
    unique_apis = []
    for api in all_apis:
        key = f"{api.get('method', '')}:{api['path']}"
        if key not in seen_apis:
            seen_apis.add(key)
            unique_apis.append(api)

    # 按类型分组
    grouped = defaultdict(list)
    for api in unique_apis:
        grouped[api['type']].append(api)

    # 鉴权去重
    seen_auth = set()
    unique_auth = []
    for a in all_auth:
        key = f"{a['keyword']}:{a['context'][:50]}"
        if key not in seen_auth:
            seen_auth.add(key)
            unique_auth.append(a)

    # 签名去重
    seen_sign = set()
    unique_sign = []
    for s in all_sign:
        key = f"{s['keyword']}:{s['context'][:50]}"
        if key not in seen_sign:
            seen_sign.add(key)
            unique_sign.append(s)

    # 路由去重
    unique_routes = list(dict.fromkeys(all_routes))

    # WebSocket去重
    unique_ws = list(dict.fromkeys(all_ws))

    # Service Worker去重
    unique_sw = list(dict.fromkeys(all_sw))

    # 保存完整结果
    report = {
        'url': url,
        'timestamp': datetime.now().isoformat(),
        'meta_info': extractor.meta_info,
        'js_files_analyzed': js_results_summary,
        'sourcemaps': sourcemap_results,
        'total_apis': len(unique_apis),
        'total_auth_refs': len(unique_auth),
        'total_sign_refs': len(unique_sign),
        'total_routes': len(unique_routes),
        'apis': unique_apis,
        'auth_info': unique_auth,
        'sign_info': unique_sign,
        'routes': unique_routes,
        'websocket_urls': unique_ws,
        'service_workers': unique_sw,
    }

    report_path = os.path.join(output_dir, 'analysis_report.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    # ---- 步骤6: 输出摘要 ----
    print(f'\n{"="*60}')
    print(f'分析完成!')
    print(f'{"="*60}')
    print(f'HTML: {len(html)} chars, 状态码: {status}')
    print(f'JS文件: {total_fetched} 个 (含chunk)')
    print(f'Source Maps: {len(sourcemap_results)} 个')
    print(f'API端点: {len(unique_apis)} 个')
    for typ, items in sorted(grouped.items()):
        print(f'  {typ}: {len(items)} 个')
    print(f'鉴权引用: {len(unique_auth)} 个')
    print(f'签名引用: {len(unique_sign)} 个')
    print(f'前端路由: {len(unique_routes)} 个')
    if unique_ws:
        print(f'WebSocket端点: {len(unique_ws)} 个')
        for ws in unique_ws[:5]:
            print(f'  - {ws}')
    if unique_sw:
        print(f'Service Workers: {len(unique_sw)} 个')
    print(f'\n结果保存到: {os.path.abspath(output_dir)}/')
    print(f'  - page_source.html (原始HTML)')
    print(f'  - html_info.json (HTML结构信息)')
    print(f'  - initial_state.json (初始状态数据)')
    print(f'  - js/ (所有JS文件，含chunk)')
    print(f'  - sourcemaps/ (Source Map文件)')
    print(f'  - analysis_report.json (完整分析报告)')

    return report


# ============ 入口 ============

def parse_args():
    """解析命令行参数"""
    import argparse
    parser = argparse.ArgumentParser(description='网站源码逆向分析 - 通用抓取脚本')
    parser.add_argument('url', help='目标网站URL')
    parser.add_argument('output_dir', nargs='?', default='web_analysis', help='输出目录 (默认: web_analysis)')
    parser.add_argument('--cookie', '-c', default='', help='Cookie字符串，用于需要鉴权的站点')
    parser.add_argument('--header', '-H', action='append', default=[], help='额外请求头，格式: "Key: Value"，可多次使用')
    parser.add_argument('--workers', '-w', type=int, default=MAX_WORKERS, help=f'并行线程数 (默认: {MAX_WORKERS})')
    return parser.parse_args()


def main():
    """主入口函数"""
    args = parse_args()

    # 设置全局Cookie和请求头
    global GLOBAL_COOKIE, GLOBAL_EXTRA_HEADERS, MAX_WORKERS

    if args.cookie:
        GLOBAL_COOKIE = args.cookie
        print(f'[*] 已设置Cookie (长度: {len(args.cookie)})')

    for h in args.header:
        try:
            key, value = h.split(':', 1)
            GLOBAL_EXTRA_HEADERS[key.strip()] = value.strip()
        except ValueError:
            print(f'[!] 忽略格式错误的header: {h}')

    MAX_WORKERS = args.workers

    analyze_website(args.url, args.output_dir)


if __name__ == '__main__':
    main()
