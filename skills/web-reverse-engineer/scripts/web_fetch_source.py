# 网站源码逆向分析 - 通用抓取脚本
# 用法: python web_fetch_source.py <url> [output_dir]
# 功能: 抓取目标URL的原始HTML + 所有关联JS文件 + 提取关键信息
import urllib.request
import ssl
import re
import json
import os
import sys
from html.parser import HTMLParser
from collections import defaultdict
from datetime import datetime

# ============ 配置 ============
DEFAULT_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
DEFAULT_HEADERS = {
    'User-Agent': DEFAULT_USER_AGENT,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'identity',  # 避免gzip解码问题
}

# SSL上下文（跳过验证）
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# ============ 工具函数 ============

def normalize_url(url, base_url=''):
    """规范化URL，处理相对路径、协议相对路径等"""
    if not url or url.startswith('data:') or url.startswith('blob:'):
        return None
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


def fetch_url(url, timeout=15):
    """抓取URL内容，返回文本"""
    try:
        req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=timeout) as resp:
            # 处理编码
            charset = 'utf-8'
            content_type = resp.headers.get('Content-Type', '')
            if 'charset=' in content_type:
                charset = content_type.split('charset=')[-1].strip().split(';')[0]
            raw = resp.read()
            try:
                return raw.decode(charset, errors='ignore')
            except:
                return raw.decode('utf-8', errors='ignore')
    except Exception as e:
        print(f'  [ERROR] {url}: {e}')
        return ''


def resolve_js_url(src, page_url):
    """解析JS文件的完整URL"""
    if not src or src.startswith('data:') or src.startswith('blob:'):
        return None
    # 过滤明显非JS的资源
    skip_patterns = ['google-analytics', 'gtag', 'facebook', 'doubleclick',
                     'adservice', 'analytics', 'hotjar', 'clarity']
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

    def extract_all(self):
        self._extract_scripts()
        self._extract_styles()
        self._extract_links()
        self._extract_meta()
        self._extract_initial_state()
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
            if s and len(s) > 10:  # 过滤空脚本
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
        if 'next-route-announcer' in self.html or '__NEXT_DATA__' in self.html:
            self.meta_info['framework'] = 'Next.js'
        if '__NUXT__' in self.html:
            self.meta_info['framework'] = 'Nuxt.js'
        if 'ng-app' in self.html or 'ng-version' in self.html:
            self.meta_info['framework'] = 'Angular'
        if '__INITIAL_STATE__' in self.html:
            self.meta_info['framework'] = 'Vue (SSR)'
        if 'data-reactroot' in self.html or '__NEXT_DATA__' in self.html:
            self.meta_info['framework'] = 'React (SSR)'
        if 'vite' in self.html.lower():
            self.meta_info['bundler'] = 'Vite'
        if 'webpack' in self.html.lower():
            self.meta_info['bundler'] = 'Webpack'

        # 查找 source map 引用
        sourcemap = re.findall(r'sourceMappingURL\s*=\s*(\S+)', self.html)
        if sourcemap:
            self.meta_info['source_maps'] = sourcemap

    def _extract_initial_state(self):
        # Vue SSR: window.__INITIAL_STATE__
        m = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});\s*</script>', self.html, re.DOTALL)
        if m:
            try:
                self.initial_state['__INITIAL_STATE__'] = json.loads(m.group(1))
            except:
                self.initial_state['__INITIAL_STATE__raw'] = m.group(1)[:5000]

        # Next.js: __NEXT_DATA__
        m = re.search(r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', self.html, re.DOTALL)
        if m:
            try:
                self.initial_state['__NEXT_DATA__'] = json.loads(m.group(1))
            except:
                pass

        # Nuxt.js: __NUXT__
        m = re.search(r'window\.__NUXT__\s*=\s*(.*?);\s*</script>', self.html, re.DOTALL)
        if m:
            self.initial_state['__NUXT__raw'] = m.group(1)[:5000]

        # 通用: window.__pinia__
        m = re.search(r'window\.__pinia__\s*=\s*\(function', self.html)
        if m:
            self.meta_info['state_management'] = 'Pinia'


# ============ JS分析 ============

class JSAnalyzer:
    """分析JS源码，提取API端点、鉴权信息等"""

    # API路径提取正则
    API_PATTERNS = [
        # (正则, 类型名, 是否为方法-URL对)
        (r'["\'`](/x/[a-zA-Z0-9_/.-]+)["\'`]', 'x-api', False),
        (r'["\'`](/api/[a-zA-Z0-9_/.-]+)["\'`]', 'api-path', False),
        (r'["\'`](/pgc/[a-zA-Z0-9_/.-]+)["\'`]', 'pgc-api', False),
        (r'["\'`](/v[0-9]+/[a-zA-Z0-9_/.-]+)["\'`]', 'versioned-api', False),
        (r'(https?://api\.[a-z0-9.-]+\.[a-z]+/[a-zA-Z0-9_/.-]+)', 'api-domain', False),
        (r'(https?://[a-z0-9.-]*passport[a-z0-9.-]*\.[a-z]+/[a-zA-Z0-9_/.-]+)', 'passport', False),
        (r'(https?://[a-z0-9.-]*graphql[a-z0-9.-]*\.[a-z]+)', 'graphql', False),
        (r'method:\s*["\'](GET|POST|PUT|DELETE|PATCH)["\'].*?url:\s*["\']([^"\']+)["\']', 'method-url', True),
        (r'["\'`](/(?:medialist|audio|live|member|msg|dynamic|feed|account)[a-zA-Z0-9_/.-]+)["\'`]', 'biz-path', False),
    ]

    # 鉴权关键词
    AUTH_KEYWORDS = [
        'Authorization', 'Bearer', 'token', 'Token', 'csrf', 'csrf_token',
        'Cookie', 'SESSDATA', 'bili_jct', 'DedeUserID', 'buvid',
        'localStorage.setItem', 'sessionStorage.setItem',
        'interceptors.request', 'interceptors.response',
        'withCredentials', 'X-Token', 'Access-Token',
        'getToken', 'setToken', 'refreshToken',
        'login', 'logout', 'auth',
    ]

    # 签名/加密关键词
    SIGN_KEYWORDS = [
        'w_rid', 'wts', 'wbi', 'sign', 'signature', 'hmac', 'md5', 'sha256',
        'encrypt', 'decrypt', 'mixin_key', 'img_key', 'sub_key',
        'GenWebTicket', 'access_token', 'appkey',
    ]

    def __init__(self, js_content, source_name=''):
        self.content = js_content
        self.source = source_name
        self.apis = []
        self.auth_info = []
        self.sign_info = []

    def analyze(self):
        self._extract_apis()
        self._extract_auth()
        self._extract_signing()
        return self

    def _extract_apis(self):
        for pattern, ptype, is_method_url in self.API_PATTERNS:
            matches = re.findall(pattern, self.content)
            for m in matches:
                if is_method_url:
                    method, path = m
                    self.apis.append({'method': method, 'path': path, 'type': ptype, 'source': self.source})
                else:
                    path = m
                    # 过滤静态资源
                    if any(path.endswith(ext) for ext in ['.js', '.css', '.png', '.jpg', '.gif', '.svg', '.woff', '.ico', '.map']):
                        continue
                    if len(path) < 5:
                        continue
                    self.apis.append({'method': '', 'path': path, 'type': ptype, 'source': self.source})

    def _extract_auth(self):
        for kw in self.AUTH_KEYWORDS:
            for m in re.finditer(re.escape(kw), self.content, re.IGNORECASE):
                start = max(0, m.start() - 80)
                end = min(len(self.content), m.end() + 150)
                ctx = self.content[start:end].replace('\n', ' ')
                self.auth_info.append({'keyword': kw, 'context': ctx, 'source': self.source})

    def _extract_signing(self):
        for kw in self.SIGN_KEYWORDS:
            for m in re.finditer(kw, self.content, re.IGNORECASE):
                start = max(0, m.start() - 80)
                end = min(len(self.content), m.end() + 200)
                ctx = self.content[start:end].replace('\n', ' ')
                self.sign_info.append({'keyword': kw, 'context': ctx, 'source': self.source})

        # 特别提取 WBI mixin_key 数组（B站等网站的反爬签名）
        mixin_match = re.search(r'\[(\d+(?:,\s*\d+){30,})\]', self.content)
        if mixin_match:
            self.sign_info.append({
                'keyword': 'mixin_key_array',
                'context': f'[{mixin_match.group(1)}]',
                'source': self.source
            })


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
    html = fetch_url(url)
    if not html:
        print('[!] 无法获取HTML，退出')
        return None

    html_path = os.path.join(output_dir, 'page_source.html')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'    HTML长度: {len(html)}, 已保存到 {html_path}')

    # ---- 步骤2: 解析HTML提取信息 ----
    print('\n[2] 解析HTML结构...')
    extractor = SourceExtractor(html, url).extract_all()

    print(f'    外部JS文件: {len(extractor.js_files)}')
    print(f'    内联脚本: {len(extractor.inline_scripts)}')
    print(f'    CSS文件: {len(extractor.css_files)}')
    print(f'    页面链接: {len(extractor.links)}')
    print(f'    技术栈: {extractor.meta_info}')
    print(f'    初始状态: {list(extractor.initial_state.keys())}')

    # 保存HTML提取结果
    html_info = {
        'url': url,
        'js_files': extractor.js_files,
        'css_files': extractor.css_files,
        'meta_info': extractor.meta_info,
        'initial_state_keys': list(extractor.initial_state.keys()),
        'links_count': len(extractor.links),
    }
    with open(os.path.join(output_dir, 'html_info.json'), 'w', encoding='utf-8') as f:
        json.dump(html_info, f, ensure_ascii=False, indent=2)

    # 保存initial_state
    if extractor.initial_state:
        with open(os.path.join(output_dir, 'initial_state.json'), 'w', encoding='utf-8') as f:
            json.dump(extractor.initial_state, f, ensure_ascii=False, indent=2, default=str)

    # ---- 步骤3: 抓取并分析JS文件 ----
    print(f'\n[3] 抓取并分析JS文件...')
    all_apis = []
    all_auth = []
    all_sign = []
    js_results = []

    # 优先级排序：主入口JS放前面
    js_files = extractor.js_files
    # 识别主入口（通常文件名含 index/app/main）
    def js_priority(url):
        fname = url.split('/')[-1].lower()
        if any(k in fname for k in ['index', 'app', 'main', 'vendor', 'chunk']):
            if 'vendor' in fname:
                return 0
            if 'index' in fname:
                return 1
            if 'app' in fname:
                return 2
            return 3
        return 9

    js_files.sort(key=js_priority)

    for i, js_url in enumerate(js_files):
        fname = js_url.split('/')[-1].split('?')[0]
        if not fname.endswith('.js'):
            fname += '.js'
        fpath = os.path.join(js_dir, fname)

        print(f'  [{i+1}/{len(js_files)}] {fname}')
        content = fetch_url(js_url)
        if not content:
            continue

        # 保存JS
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'    长度: {len(content)}')

        # 分析JS
        analyzer = JSAnalyzer(content, fname).analyze()
        all_apis.extend(analyzer.apis)
        all_auth.extend(analyzer.auth_info)
        all_sign.extend(analyzer.sign_info)

        js_results.append({
            'filename': fname,
            'url': js_url,
            'size': len(content),
            'api_count': len(analyzer.apis),
            'auth_count': len(analyzer.auth_info),
            'sign_count': len(analyzer.sign_info),
        })

        # 检查是否有chunk引用（需要进一步抓取）
        chunk_refs = re.findall(r'["\']([^"\']*(?:chunk|lazy|async)[^"\']*\.js)["\']', content)
        if chunk_refs:
            print(f'    发现 {len(chunk_refs)} 个chunk引用（可能需要手动获取）')

        # 检查source map
        sourcemap_ref = re.search(r'sourceMappingURL\s*=\s*(\S+\.map)', content)
        if sourcemap_ref:
            map_url = normalize_url(sourcemap_ref.group(1), js_url)
            print(f'    !! 发现 Source Map: {map_url}')

    # ---- 步骤4: 分析内联脚本 ----
    print(f'\n[4] 分析内联脚本...')
    for i, script in enumerate(extractor.inline_scripts):
        analyzer = JSAnalyzer(script, f'inline_script_{i+1}').analyze()
        all_apis.extend(analyzer.apis)
        all_auth.extend(analyzer.auth_info)
        all_sign.extend(analyzer.sign_info)

    # ---- 步骤5: 去重并输出 ----
    print(f'\n[5] 汇总结果...')

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

    # 保存完整结果
    report = {
        'url': url,
        'timestamp': datetime.now().isoformat(),
        'meta_info': extractor.meta_info,
        'js_files_analyzed': js_results,
        'total_apis': len(unique_apis),
        'total_auth_refs': len(unique_auth),
        'total_sign_refs': len(unique_sign),
        'apis': unique_apis,
        'auth_info': unique_auth,
        'sign_info': unique_sign,
    }

    report_path = os.path.join(output_dir, 'analysis_report.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    # ---- 步骤6: 输出摘要 ----
    print(f'\n{"="*60}')
    print(f'分析完成!')
    print(f'{"="*60}')
    print(f'HTML: {len(html)} chars')
    print(f'JS文件: {len(js_files)} 个, 成功 {len(js_results)} 个')
    print(f'API端点: {len(unique_apis)} 个')
    for typ, items in sorted(grouped.items()):
        print(f'  {typ}: {len(items)} 个')
    print(f'鉴权引用: {len(unique_auth)} 个')
    print(f'签名引用: {len(unique_sign)} 个')
    print(f'\n结果保存到: {os.path.abspath(output_dir)}/')
    print(f'  - page_source.html (原始HTML)')
    print(f'  - html_info.json (HTML结构信息)')
    print(f'  - initial_state.json (初始状态数据)')
    print(f'  - js/ (所有JS文件)')
    print(f'  - analysis_report.json (完整分析报告)')

    return report


# ============ 入口 ============

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法: python web_fetch_source.py <url> [output_dir]')
        print('示例: python web_fetch_source.py https://www.bilibili.com/ bilibili_analysis')
        sys.exit(1)

    target_url = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else 'web_analysis'

    analyze_website(target_url, output)
