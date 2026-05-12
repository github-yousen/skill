# 鉴权与签名算法深度分析脚本
# 用法: python auth_analyzer.py <js_file_or_dir> [output_file]
# 功能: 从JS文件中深度提取鉴权流程、签名算法、Cookie逻辑、OAuth流程、JWT分析
import re
import json
import os
import sys
import base64
from collections import defaultdict


class AuthDeepAnalyzer:
    """鉴权深度分析器（通用版）"""

    def __init__(self, content, source_name=''):
        self.content = content
        self.source = source_name
        self.results = {
            'cookie_operations': [],
            'csrf_mechanism': [],
            'token_flow': [],
            'request_interceptors': [],
            'signing_algorithms': [],
            'param_signing': [],       # 参数签名机制（含WBI等特化签名）
            'oauth_flow': [],
            'jwt_analysis': [],        # JWT结构分析
            'api_base_urls': [],
            'url_api_keys': [],        # URL中暴露的API Key
            'websocket_auth': [],      # WebSocket鉴权
        }

    def analyze(self):
        self._extract_cookie_ops()
        self._extract_csrf()
        self._extract_token_flow()
        self._extract_interceptors()
        self._extract_signing()
        self._extract_param_signing()
        self._extract_oauth()
        self._extract_jwt()
        self._extract_api_base()
        self._extract_url_api_keys()
        self._extract_ws_auth()
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
            (r'document\.cookie', 'read_cookie'),
            (r'document\.cookie\s*=\s*["\']?([^=;\s]+)\s*=', 'set_cookie'),
            (r'(?:function|const|let|var)\s+(\w*(?:[Cc]ookie|[Gg]et[Cc]ookie|[Ss]et[Cc]ookie)\w*)\s*[=\(]', 'cookie_func'),
            (r'(?:getCookie|readCookie|parseCookie)\s*\(\s*["\']([^"\']+)["\']', 'cookie_read_field'),
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
        csrf_patterns = [
            (r'csrf[_-]?token\s*[:=]\s*["\']?([^"\'\s,;)]+)', 'csrf_value'),
            (r'csrf\s*[:=]\s*(?:getCookie|readCookie)\s*\(\s*["\']([^"\']+)["\']', 'csrf_from_cookie'),
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
            (r'(?:access_token|auth_token|jwt_token|id_token)\s*[:=]', 'token_assign'),
            (r'(?:localStorage|sessionStorage)\s*[.\[]\s*["\']?(?:token|access_token|auth)["\']?', 'token_storage'),
            (r'Authorization\s*[:=]\s*["\']?(?:Bearer|Basic|JWT)\s+', 'token_in_header'),
            (r'refresh[_-]?token\s*[:=]', 'refresh_token'),
            (r'(?:token.*?expir|expir.*?token|expires_in\b|token_type\b)', 'token_expiry'),
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
        """通用签名算法提取"""
        sign_patterns = [
            (r'(?:sign|signature)\s*[:=]\s*(?:function|\()', 'sign_function'),
            (r'(?:MD5|SHA256|SHA1|HMAC|AES|RSA|RSA256)\s*\(', 'crypto_usage'),
            (r'CryptoJS\.(MD5|SHA256|HmacSHA256|AES|enc)', 'cryptojs_usage'),
            (r'crypto\.subtle\.(?:sign|digest|encrypt)', 'webcrypto_usage'),
            (r'(?:timestamp|ts)\s*[:=]\s*(?:Date\.now|new Date|Math\.round|parseInt)\s*\(', 'timestamp_sign'),
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

    def _extract_param_signing(self):
        """参数签名机制提取（含WBI等特化签名模式）

        通用模式：
        1. 参数排序 → 拼接 → 哈希签名
        2. 时间戳 + 签名
        3. 密钥提取 + HMAC
        4. 特化签名（如B站WBI、微信签名等）
        """
        param_sign_patterns = [
            # WBI签名（B站等网站的反爬签名模式）
            (r'(?:w_rid|wbi_sign|wbi_sign_params)', 'wbi_sign'),
            (r'(?:img_key|imgKey|sub_key|subKey)\s*[:=]', 'wbi_keys'),
            (r'mixin[_-]?key\s*[:=]', 'mixin_key'),
            # 通用参数签名模式（更精确，排除普通排序代码）
            (r'(?:sign|signature|sig)\s*\(\s*(?:params|data|query|body|options)', 'sign_params_call'),
            # 参数拼接签名（需同时有sort和sign/hmac/md5在附近）
            (r'(?:Object\.(?:keys|entries))\s*\([^)]*\)\s*\.\s*sort\s*\([^)]*\)[^;]{0,200}(?:sign|hmac|md5)', 'object_sort_sign'),
            # encodeURIComponent + sign（签名前编码）
            (r'(?:encodeURIComponent|encodeURI)\s*\([^)]*(?:sign|signature|sig)', 'encode_sign'),
        ]

        for pat, ptype in param_sign_patterns:
            for m in re.finditer(pat, self.content, re.IGNORECASE):
                ctx = self._get_context(m, before=100, after=300)
                self.results['param_signing'].append({
                    'type': ptype,
                    'context': ctx[:500],
                    'source': self.source
                })

        # 提取打乱数组（如WBI的mixin_key_enc_tab等参数签名用的映射表）
        array_match = self._safe_search(r'\[(\d+(?:\s*,\s*\d+){30,})\]')
        if array_match:
            nums = [int(x.strip()) for x in array_match.group(1).split(',')]
            if len(nums) >= 32 and max(nums) >= 32:
                self.results['param_signing'].append({
                    'type': 'shuffle_array',
                    'context': f'Array length={len(nums)}, max={max(nums)}: [{array_match.group(1)[:200]}]',
                    'source': self.source
                })

    def _extract_oauth(self):
        """OAuth/OIDC流程提取"""
        oauth_patterns = [
            # 精确匹配OAuth参数名（在URL或对象属性中）
            (r'(?:redirect_uri|client_id|client_secret|response_type|grant_type)\s*[:=]', 'oauth_param'),
            (r'oauth[_/](?:authorize|token|callback)', 'oauth_endpoint'),
            (r'openid|code_challenge|PKCE|id_token_hint', 'openid_param'),
            # SSO：需更精确，排除普通代码中的子串匹配
            (r'(?:sso[_/-]|sso\.|/sso|single.sign.on|cas[_/]login|shiro|saml[_/])', 'sso_pattern'),
        ]

        for pat, ptype in oauth_patterns:
            for m in re.finditer(pat, self.content, re.IGNORECASE):
                ctx = self._get_context(m, before=50, after=150)
                self.results['oauth_flow'].append({
                    'type': ptype,
                    'context': ctx[:300],
                    'source': self.source
                })

        # 尝试提取OAuth授权URL模板
        oauth_urls = self._safe_findall(
            r'["\']((?:https?:)?//[^"\']*(?:oauth|sso)[^"\']*)["\']'
        )
        for u in oauth_urls:
            self.results['oauth_flow'].append({
                'type': 'oauth_url',
                'context': u[:300],
                'source': self.source
            })

    def _extract_jwt(self):
        """JWT结构分析与提取"""
        # 提取JWT Token模式
        jwt_patterns = [
            # JWT赋值
            (r'(?:jwt|token|id_token)\s*[:=]\s*["\']?(eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+)', 'jwt_value'),
            # JWT解析函数
            (r'(?:parseJwt|decodeJwt|parseToken|jwt_decode|jwtDecode)\s*\(', 'jwt_decode_func'),
            # JWT库引用
            (r'import.*?jwt[-_]?decode|require.*?jwt[-_]?decode|from\s+["\']jwt-decode["\']', 'jwt_decode_import'),
            # 手动base64解析JWT（排除data URI等误报）
            (r'atob\s*\(\s*["\']?(eyJ[a-zA-Z0-9_-]+)', 'jwt_manual_decode'),
        ]

        for pat, ptype in jwt_patterns:
            for m in re.finditer(pat, self.content, re.IGNORECASE):
                ctx = self._get_context(m)
                result = {
                    'type': ptype,
                    'context': ctx[:300],
                    'source': self.source
                }

                # 如果匹配到JWT值，尝试解码payload
                if ptype == 'jwt_value' and len(m.groups()) >= 1:
                    jwt_str = m.group(1)
                    try:
                        # JWT格式: header.payload.signature
                        parts = jwt_str.split('.')
                        if len(parts) >= 2:
                            # 解码payload（第二部分）
                            payload_b64 = parts[1]
                            # 补齐base64 padding
                            padding = 4 - len(payload_b64) % 4
                            if padding != 4:
                                payload_b64 += '=' * padding
                            payload_bytes = base64.urlsafe_b64decode(payload_b64)
                            payload = json.loads(payload_bytes.decode('utf-8'))
                            result['decoded_payload'] = payload
                            result['payload_fields'] = list(payload.keys())
                    except:
                        pass

                self.results['jwt_analysis'].append(result)

    def _extract_api_base(self):
        """API基础URL提取"""
        base_patterns = [
            r'(?:baseUrl|baseURL|apiBase|API_URL|apiUrl|api_prefix|serviceUrl|SERVER_URL)\s*[:=]\s*["\']([^"\']+)["\']',
            r'(?:BASE_URL|API_HOST|API_ENDPOINT)\s*[:=]\s*["\']([^"\']+)["\']',
            r'(?:VITE_|NEXT_PUBLIC_|REACT_APP_)(?:API|SERVER|BASE)_?(?:URL|HOST|ENDPOINT)\s*[:=]?\s*["\']([^"\']+)["\']',
            r'(?:process\.env\.(?:API_URL|BASE_URL|REACT_APP_API_URL|NEXT_PUBLIC_API_URL))\s*',  # 环境变量引用
        ]

        for pat in base_patterns:
            matches = self._safe_findall(pat)
            for m in matches:
                if isinstance(m, str) and len(m) > 2:
                    self.results['api_base_urls'].append({
                        'url': m,
                        'source': self.source
                    })

    def _extract_url_api_keys(self):
        """URL中暴露的API Key/Token检测"""
        # 检测URL查询参数中的敏感信息
        url_key_patterns = [
            (r'["\'](?:api_key|apikey|key|token|secret|access_token|app_key|appkey)\s*=\s*([^"&\'\s]+)', 'url_param_key'),
            (r'\?\s*(?:api_key|apikey|key|token|secret|access_token)\s*=\s*([^"&\'\s]+)', 'query_param_key'),
            (r'(?:headers|params)\s*\[?\s*["\'](?:api_key|apikey|key|token|secret)["\']\s*\]?\s*[:=]\s*["\']([^"\']+)["\']', 'header_key'),
        ]

        for pat, ptype in url_key_patterns:
            matches = self._safe_findall(pat, re.IGNORECASE)
            for m in matches:
                self.results['url_api_keys'].append({
                    'type': ptype,
                    'value': m[:100] if isinstance(m, str) else str(m)[:100],
                    'source': self.source
                })

    def _extract_ws_auth(self):
        """WebSocket鉴权提取"""
        ws_patterns = [
            (r'new\s+WebSocket\s*\([^)]*token[^)]*\)', 'ws_token_param'),
            (r'(?:ws|socket)\.(?:on|send|emit)\s*\([^)]*(?:auth|token|cookie)', 'ws_auth_message'),
            (r'wss?://[^"\'\s]*[?&](?:token|key|auth|ticket)=', 'ws_url_auth'),
        ]

        for pat, ptype in ws_patterns:
            for m in re.finditer(pat, self.content, re.IGNORECASE):
                ctx = self._get_context(m, before=50, after=200)
                self.results['websocket_auth'].append({
                    'type': ptype,
                    'context': ctx[:400],
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
        if not items:
            continue
        print(f'  {key}: {len(items)} 条')
        for item in items[:3]:
            if isinstance(item, dict):
                val = item.get('context', item.get('value', item.get('url', '')))[:100]
                extra = ''
                if 'payload_fields' in item:
                    extra = f' [fields: {item["payload_fields"]}]'
                print(f'    - {item.get("type", "")}: {val}...{extra}')

    # 保存
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f'\n结果保存到: {output}')


if __name__ == '__main__':
    main()
