# 鉴权与签名算法深度分析脚本
# 用法: python auth_analyzer.py <js_file_or_dir> [output_file]
# 功能: 从JS文件中深度提取鉴权流程、签名算法、Cookie逻辑
import re
import json
import os
import sys
from collections import defaultdict


class AuthDeepAnalyzer:
    """鉴权深度分析器"""

    def __init__(self, content, source_name=''):
        self.content = content
        self.source = source_name
        self.results = {
            'cookie_operations': [],
            'csrf_mechanism': [],
            'token_flow': [],
            'request_interceptors': [],
            'signing_algorithms': [],
            'wbi_signing': [],
            'oauth_flow': [],
            'api_base_urls': [],
        }

    def analyze(self):
        self._extract_cookie_ops()
        self._extract_csrf()
        self._extract_token_flow()
        self._extract_interceptors()
        self._extract_signing()
        self._extract_wbi()
        self._extract_oauth()
        self._extract_api_base()
        return self

    def _safe_findall(self, pattern, flags=0):
        try:
            return re.findall(pattern, self.content, flags)
        except:
            return []

    def _safe_search(self, pattern, flags=0):
        try:
            return re.search(pattern, self.content, flags)
        except:
            return None

    def _get_context(self, match_obj, before=100, after=200):
        """获取匹配位置附近的上下文"""
        start = max(0, match_obj.start() - before)
        end = min(len(self.content), match_obj.end() + after)
        return self.content[start:end].replace('\n', ' ')

    def _extract_cookie_ops(self):
        """Cookie操作提取"""
        patterns = [
            # 读取Cookie
            (r'document\.cookie', 'read_cookie'),
            # 设置Cookie
            (r'document\.cookie\s*=\s*["\']?([^=;\s]+)\s*=', 'set_cookie'),
            # Cookie工具函数
            (r'(?:function|const|let|var)\s+(\w*(?:[Cc]ookie|[Gg]et[Cc]ookie|[Ss]et[Cc]ookie)\w*)\s*[=\(]', 'cookie_func'),
            # Cookie中读取特定字段
            (r'(?:getCookie|readCookie|parseCookie)\s*\(\s*["\']([^"\']+)["\']', 'cookie_read_field'),
            # localStorage/sessionStorage
            (r'(?:localStorage|sessionStorage)\.(?:setItem|getItem)\s*\(\s*["\']([^"\']+)["\']', 'storage_key'),
        ]

        for pat, ptype in patterns:
            matches = self._safe_findall(pat)
            for m in matches:
                self.results['cookie_operations'].append({
                    'type': ptype,
                    'value': m if isinstance(m, str) else m,
                    'source': self.source
                })

    def _extract_csrf(self):
        """CSRF机制提取"""
        # CSRF Token获取
        csrf_patterns = [
            (r'csrf[_-]?token\s*[:=]\s*["\']?([^"\'\s,;)]+)', 'csrf_value'),
            (r'csrf\s*[:=]\s*(?:getCookie|readCookie|ea)\s*\(\s*["\']([^"\']+)["\']', 'csrf_from_cookie'),
            (r'X-CSRF-Token|X-XSRF-Token|csrfmiddlewaretoken', 'csrf_header'),
            (r'_csrf|_token|authenticity_token', 'csrf_field'),
        ]

        for pat, ptype in csrf_patterns:
            matches = self._safe_findall(pat, re.IGNORECASE)
            for m in matches:
                self.results['csrf_mechanism'].append({
                    'type': ptype,
                    'value': m[:200] if isinstance(m, str) else str(m)[:200],
                    'source': self.source
                })

        # CSRF在请求中的使用方式
        csrf_usage = self._safe_findall(
            r'(?:params|headers|data|body)\s*\[?["\']?(?:csrf|_csrf|csrf_token|X-CSRF)["\']?\]?\s*[:=]'
        )
        if csrf_usage:
            self.results['csrf_mechanism'].append({
                'type': 'csrf_in_request',
                'value': f'Found {len(csrf_usage)} csrf usage in request construction',
                'source': self.source
            })

    def _extract_token_flow(self):
        """Token流程提取"""
        token_patterns = [
            # Token获取
            (r'(?:access_token|auth_token|jwt_token|id_token)\s*[:=]', 'token_assign'),
            # Token存储
            (r'(?:localStorage|sessionStorage|cookie)\s*[.\[]\s*["\']?(?:token|access_token|auth)["\']?', 'token_storage'),
            # Token传递（Header方式）
            (r'Authorization\s*[:=]\s*["\']?(?:Bearer|Basic|JWT)\s+', 'token_in_header'),
            # Token刷新
            (r'refresh[_-]?token\s*[:=]', 'refresh_token'),
            # Token过期
            (r'(?:token.*?expir|expir.*?token|ttl|expires_in)', 'token_expiry'),
        ]

        for pat, ptype in token_patterns:
            for m in re.finditer(pat, self.content, re.IGNORECASE):
                ctx = self._get_context(m)
                self.results['token_flow'].append({
                    'type': ptype,
                    'context': ctx[:300],
                    'source': self.source
                })

    def _extract_interceptors(self):
        """请求拦截器提取"""
        # axios拦截器
        for m in re.finditer(r'interceptors?\.(request|response)\.use\s*\(', self.content):
            ctx = self._get_context(m, before=50, after=500)
            self.results['request_interceptors'].append({
                'type': 'axios_interceptor',
                'interceptor_type': m.group(1),
                'context': ctx[:600],
                'source': self.source
            })

        # fetch包装
        for m in re.finditer(r'(?:window\.fetch|originalFetch|fetchWrapper)\s*=', self.content):
            ctx = self._get_context(m, before=30, after=400)
            self.results['request_interceptors'].append({
                'type': 'fetch_wrapper',
                'context': ctx[:500],
                'source': self.source
            })

        # 请求头注入
        for m in re.finditer(r'(?:headers|common)\s*\[?\s*["\']?(?:Authorization|X-Token|Access-Token|X-Access)["\']?\]?\s*[:=]', self.content, re.IGNORECASE):
            ctx = self._get_context(m, before=50, after=200)
            self.results['request_interceptors'].append({
                'type': 'header_injection',
                'context': ctx[:300],
                'source': self.source
            })

    def _extract_signing(self):
        """签名算法提取"""
        sign_patterns = [
            # 通用签名
            (r'(?:sign|signature)\s*[:=]\s*(?:function|\()', 'sign_function'),
            (r'(?:MD5|SHA256|SHA1|HMAC|AES|RSA|RSA256)\s*\(', 'crypto_usage'),
            (r'CryptoJS\.(MD5|SHA256|HmacSHA256|AES|enc)', 'cryptojs_usage'),
            # 时间戳签名
            (r'(?:timestamp|ts|t)\s*[:=]\s*(?:Date\.now|new Date|Math\.round|parseInt)', 'timestamp_sign'),
            # 参数排序签名
            (r'Sort|sort\s*\(\s*\(\s*\w+\s*,\s*\w+\s*\)', 'param_sort'),
            # 密钥
            (r'(?:app_?key|secret_?key|api_?key|sign_?key)\s*[:=]\s*["\']([^"\']+)["\']', 'sign_key'),
        ]

        for pat, ptype in sign_patterns:
            for m in re.finditer(pat, self.content, re.IGNORECASE):
                ctx = self._get_context(m, before=50, after=300)
                self.results['signing_algorithms'].append({
                    'type': ptype,
                    'context': ctx[:400],
                    'source': self.source
                })

    def _extract_wbi(self):
        """WBI签名提取（B站特有，但模式可复用）"""
        wbi_patterns = [
            (r'w_rid\s*[:=]', 'w_rid'),
            (r'wts\s*[:=]', 'wts'),
            (r'(?:img_key|imgKey|sub_key|subKey)\s*[:=]', 'wbi_keys'),
            (r'mixin[_-]?key\s*[:=]', 'mixin_key'),
            (r'wbi[_-]?img\s*[:=]', 'wbi_img'),
        ]

        for pat, ptype in wbi_patterns:
            for m in re.finditer(pat, self.content, re.IGNORECASE):
                ctx = self._get_context(m, before=100, after=300)
                self.results['wbi_signing'].append({
                    'type': ptype,
                    'context': ctx[:500],
                    'source': self.source
                })

        # 提取打乱数组（如WBI的mixin_key_enc_tab）
        array_match = self._safe_search(r'\[(\d+(?:\s*,\s*\d+){30,})\]')
        if array_match:
            nums = [int(x.strip()) for x in array_match.group(1).split(',')]
            if len(nums) >= 32 and max(nums) >= 32:
                # 很可能是签名用的打乱数组
                self.results['wbi_signing'].append({
                    'type': 'shuffle_array',
                    'context': f'Array length={len(nums)}, max={max(nums)}: [{array_match.group(1)[:200]}]',
                    'source': self.source
                })

    def _extract_oauth(self):
        """OAuth流程提取"""
        oauth_patterns = [
            (r'(?:oauth|authorize|callback|redirect_uri|client_id|response_type=code)', 'oauth_param'),
            (r'(?:openid|scope|state|nonce|code_challenge)', 'openid_param'),
            (r'(?:sso|single.sign|cas\.login|shiro)', 'sso_pattern'),
        ]

        for pat, ptype in oauth_patterns:
            for m in re.finditer(pat, self.content, re.IGNORECASE):
                ctx = self._get_context(m, before=50, after=150)
                self.results['oauth_flow'].append({
                    'type': ptype,
                    'context': ctx[:300],
                    'source': self.source
                })

    def _extract_api_base(self):
        """API基础URL提取"""
        base_patterns = [
            r'(?:baseUrl|baseURL|apiBase|API_URL|apiUrl|api_prefix|serviceUrl|SERVER_URL)\s*[:=]\s*["\']([^"\']+)["\']',
            r'(?:BASE_URL|API_HOST|API_ENDPOINT)\s*[:=]\s*["\']([^"\']+)["\']',
            r'(?:VITE_|NEXT_PUBLIC_)(?:API|SERVER|BASE)_?(?:URL|HOST|ENDPOINT)\s*[:=]?\s*["\']([^"\']+)["\']',
        ]

        for pat in base_patterns:
            matches = self._safe_findall(pat)
            for m in matches:
                self.results['api_base_urls'].append({
                    'url': m,
                    'source': self.source
                })


def analyze_file(filepath):
    """分析单个JS文件"""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    fname = os.path.basename(filepath)
    analyzer = AuthDeepAnalyzer(content, fname).analyze()
    return analyzer.results


def analyze_directory(dirpath):
    """分析目录下所有JS文件"""
    all_results = defaultdict(list)

    for root, dirs, files in os.walk(dirpath):
        for fname in files:
            if fname.endswith('.js'):
                fpath = os.path.join(root, fname)
                print(f'  Analyzing: {fname}')
                results = analyze_file(fpath)
                for key, items in results.items():
                    all_results[key].extend(items)

    return dict(all_results)


def main():
    if len(sys.argv) < 2:
        print('用法: python auth_analyzer.py <js_file_or_dir> [output_file]')
        print('示例: python auth_analyzer.py ./web_analysis/js/ auth_report.json')
        sys.exit(1)

    target = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else 'auth_report.json'

    print(f'[*] 目标: {target}')

    if os.path.isdir(target):
        results = analyze_directory(target)
    elif os.path.isfile(target):
        results = analyze_file(target)
    else:
        print(f'[!] 文件/目录不存在: {target}')
        sys.exit(1)

    # 统计
    print(f'\n{"="*60}')
    print('鉴权分析结果:')
    print(f'{"="*60}')
    for key, items in results.items():
        print(f'  {key}: {len(items)} 条')
        # 展示前3条
        for item in items[:3]:
            if isinstance(item, dict):
                val = item.get('context', item.get('value', item.get('url', '')))[:100]
                print(f'    - {item.get("type", "")}: {val}...')

    # 保存
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f'\n结果保存到: {output}')


if __name__ == '__main__':
    main()
