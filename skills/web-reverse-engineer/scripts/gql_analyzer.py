# GraphQL 分析脚本
# 用法: python gql_analyzer.py <js_file_or_dir> [output_file]
# 功能: 从JS源码中提取GraphQL操作(query/mutation/subscription)、schema信息、端点配置
import re
import json
import os
import sys
from collections import defaultdict


class GraphQLAnalyzer:
    """GraphQL分析器"""

    def __init__(self, content, source_name=''):
        self.content = content
        self.source = source_name
        self.results = {
            'endpoints': [],
            'operations': [],       # query/mutation/subscription
            'fragments': [],
            'type_names': [],       # __typename 引用
            'schema_hints': [],     # 从代码推断的schema
            'client_config': [],    # Apollo/Relay/URQL配置
            'persisted_queries': [], # 持久化查询
        }

    def analyze(self):
        self._extract_endpoints()
        self._extract_operations()
        self._extract_fragments()
        self._extract_typenames()
        self._extract_schema_hints()
        self._extract_client_config()
        self._extract_persisted_queries()
        return self

    def _safe_findall(self, pattern, flags=0):
        try:
            return re.findall(pattern, self.content, flags)
        except:
            return []

    def _get_context(self, match_obj, before=50, after=200):
        start = max(0, match_obj.start() - before)
        end = min(len(self.content), match_obj.end() + after)
        return self.content[start:end].replace('\n', ' ')

    def _extract_endpoints(self):
        """提取GraphQL端点URL"""
        patterns = [
            (r'["\']((?:https?:)?//[^"\']*(?:graphql|gql)[^"\']*)["\']', 'graphql_url'),
            (r'(?:graphql|gql)\s*(?:Url|URL|Endpoint|endpoint|uri|URI)\s*[:=]\s*["\']([^"\']+)["\']', 'graphql_config'),
            (r'/(?:graphql|gql)(?:/?(?:v\d+)?)?', 'graphql_path'),
        ]

        for pat, ptype in patterns:
            for m in re.finditer(pat, self.content, re.IGNORECASE):
                ctx = self._get_context(m)
                value = m.group(1) if m.lastindex else m.group(0)
                self.results['endpoints'].append({
                    'type': ptype,
                    'value': value[:200],
                    'context': ctx[:300],
                    'source': self.source
                })

    def _extract_operations(self):
        """提取GraphQL操作定义"""
        # 标准GraphQL操作
        # 匹配: query Xxx { ... } / mutation Xxx($var: Type) { ... } / subscription Xxx { ... }
        # 也匹配 gql`query Xxx { ... }` 模板字符串

        # 从模板字符串中提取
        gql_template = re.finditer(
            r'(?:gql|graphql|GQL|GraphQL)\s*(?:\.tag)?`([\s\S]*?)`',
            self.content
        )
        for m in gql_template:
            self._parse_gql_string(m.group(1), 'template_literal')

        # 从字符串中提取
        gql_string = re.finditer(
            r'["\']((?:query|mutation|subscription)\s+\w+[\s\S]*?(?:\{[\s\S]*?\}))["\']',
            self.content
        )
        for m in gql_string:
            self._parse_gql_string(m.group(1), 'string_literal')

        # 提取操作名引用（客户端代码中调用时使用）
        op_refs = re.finditer(
            r'(?:operationName|operation)\s*[:=]\s*["\'](\w+)["\']',
            self.content
        )
        for m in op_refs:
            self.results['operations'].append({
                'type': 'operation_ref',
                'operation_type': 'unknown',
                'name': m.group(1),
                'context': self._get_context(m)[:200],
                'source': self.source
            })

        # useQuery / useMutation hooks（React）
        hook_refs = re.finditer(
            r'use(Query|Mutation|Subscription|LazyQuery)\s*\(\s*["\']?(\w+)',
            self.content
        )
        for m in hook_refs:
            op_type = m.group(1).lower()
            if op_type == 'lazyquery':
                op_type = 'query'
            self.results['operations'].append({
                'type': 'react_hook',
                'operation_type': op_type,
                'name': m.group(2),
                'context': self._get_context(m)[:200],
                'source': self.source
            })

    def _parse_gql_string(self, gql_str, source_type):
        """解析单个GraphQL字符串"""
        # 提取操作定义
        found_named = False
        for m in re.finditer(
            r'(query|mutation|subscription)\s+(\w+)(?:\s*\([^)]*\))?\s*\{',
            gql_str
        ):
            found_named = True
            op_type = m.group(1)
            op_name = m.group(2)
            # 提取查询的字段（简化版）
            fields = re.findall(r'(\w+)\s*(?:\(|\{|\n)', gql_str[m.start():])
            self.results['operations'].append({
                'type': source_type,
                'operation_type': op_type,
                'name': op_name,
                'fields': fields[:10],  # 只取前10个字段
                'source': self.source
            })

        # 无名操作
        if not found_named:
            for m in re.finditer(r'(query|mutation|subscription)\s*\{', gql_str):
                self.results['operations'].append({
                    'type': source_type,
                    'operation_type': m.group(1),
                    'name': '(anonymous)',
                    'source': self.source
                })

    def _extract_fragments(self):
        """提取GraphQL Fragment"""
        fragments = re.finditer(
            r'fragment\s+(\w+)\s+on\s+(\w+)',
            self.content
        )
        for m in fragments:
            self.results['fragments'].append({
                'name': m.group(1),
                'on_type': m.group(2),
                'context': self._get_context(m)[:200],
                'source': self.source
            })

    def _extract_typenames(self):
        """提取 __typename 引用，推断类型"""
        typenames = re.finditer(
            r'__typename\s*(?::|==|===|!==)\s*["\'](\w+)["\']',
            self.content
        )
        seen = set()
        for m in typenames:
            tname = m.group(1)
            if tname not in seen:
                seen.add(tname)
                self.results['type_names'].append({
                    'type_name': tname,
                    'context': self._get_context(m)[:200],
                    'source': self.source
                })

        # 另一种模式：switch(__typename) case "XxxType"
        switch_types = re.finditer(
            r'case\s+["\'](\w+Type)["\']',
            self.content
        )
        for m in switch_types:
            tname = m.group(1)
            if tname not in seen:
                seen.add(tname)
                self.results['type_names'].append({
                    'type_name': tname,
                    'context': self._get_context(m)[:200],
                    'source': self.source
                })

    def _extract_schema_hints(self):
        """从代码推断schema结构"""
        # 接口字段映射
        field_mappings = re.finditer(
            r'(?:data|result|response)\s*\.(\w+)\s*\.(\w+)',
            self.content
        )
        seen = set()
        for m in field_mappings:
            key = f'{m.group(1)}.{m.group(2)}'
            if key not in seen and len(m.group(1)) > 2 and len(m.group(2)) > 2:
                seen.add(key)
                if len(seen) <= 50:  # 限制数量
                    self.results['schema_hints'].append({
                        'type': 'field_access',
                        'parent': m.group(1),
                        'field': m.group(2),
                        'source': self.source
                    })

        # TypeScript接口定义（如果JS中有JSDoc类型注释）
        ts_types = re.finditer(
            r'/\*\*\s*@type\s*\{([^}]+)\}',
            self.content
        )
        for m in ts_types:
            self.results['schema_hints'].append({
                'type': 'jsdoc_type',
                'definition': m.group(1)[:200],
                'source': self.source
            })

    def _extract_client_config(self):
        """提取GraphQL客户端配置"""
        # Apollo Client
        apollo_patterns = [
            (r'new\s+ApolloClient\s*\(', 'apollo_client'),
            (r'ApolloProvider', 'apollo_provider'),
            (r'createApolloClient|ApolloClient\s*=\s*new', 'apollo_create'),
            (r'InMemoryCache|HttpLink|ApolloLink', 'apollo_link'),
        ]

        for pat, ptype in apollo_patterns:
            for m in re.finditer(pat, self.content):
                ctx = self._get_context(m, before=30, after=300)
                self.results['client_config'].append({
                    'type': ptype,
                    'context': ctx[:400],
                    'source': self.source
                })

        # URQL
        urql_patterns = [
            (r'createClient\s*\(\s*\{[^}]*url', 'urql_client'),
            (r'Provider\s+value=\{.*?client', 'urql_provider'),
        ]
        for pat, ptype in urql_patterns:
            for m in re.finditer(pat, self.content):
                ctx = self._get_context(m, before=30, after=200)
                self.results['client_config'].append({
                    'type': ptype,
                    'context': ctx[:300],
                    'source': self.source
                })

        # Relay
        relay_patterns = [
            (r'RelayEnvironment|relayEnvironment', 'relay_env'),
            (r'fetchQuery|useLazyLoadQuery|usePreloadedQuery', 'relay_hook'),
        ]
        for pat, ptype in relay_patterns:
            for m in re.finditer(pat, self.content):
                ctx = self._get_context(m, before=30, after=200)
                self.results['client_config'].append({
                    'type': ptype,
                    'context': ctx[:300],
                    'source': self.source
                })

    def _extract_persisted_queries(self):
        """提取持久化查询/自动持久化查询(APQ)"""
        # APQ: 使用sha256Hash标识查询（严格匹配，排除普通CryptoJS用法）
        apq_patterns = [
            (r'extensions\s*[.\[]\s*["\']?persistedQuery', 'apq'),
            (r'sha256Hash|persistedQuery', 'apq'),
            (r'operationId\s*[:=]\s*["\']([a-f0-9]{32,})["\']', 'operation_id'),
            (r'persisted_queries|persistedQueries|queryMap', 'persisted_map'),
        ]

        for pat, ptype in apq_patterns:
            for m in re.finditer(pat, self.content, re.IGNORECASE):
                ctx = self._get_context(m, before=50, after=200)
                self.results['persisted_queries'].append({
                    'type': ptype,
                    'context': ctx[:300],
                    'source': self.source
                })


def analyze_file(filepath):
    """分析单个JS文件"""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    fname = os.path.basename(filepath)
    analyzer = GraphQLAnalyzer(content, fname).analyze()
    return analyzer.results


def analyze_directory(dirpath):
    """分析目录下所有JS文件"""
    all_results = defaultdict(list)

    for root, dirs, files in os.walk(dirpath):
        for fname in files:
            if fname.endswith('.js'):
                fpath = os.path.join(root, fname)
                results = analyze_file(fpath)
                for key, items in results.items():
                    all_results[key].extend(items)

    return dict(all_results)


def try_introspection(endpoint_url, output_file=None):
    """尝试GraphQL Introspection查询"""
    import urllib.request
    import ssl

    introspection_query = '''
    {
      __schema {
        queryType { name }
        mutationType { name }
        subscriptionType { name }
        types {
          name
          kind
          fields {
            name
            type { name kind }
            args { name type { name kind } }
          }
        }
      }
    }
    '''

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        data = json.dumps({'query': introspection_query}).encode()
        req = urllib.request.Request(
            endpoint_url,
            data=data,
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'Mozilla/5.0',
                'Accept-Encoding': 'identity',
            }
        )
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
            return result
    except Exception as e:
        print(f'[!] Introspection查询失败: {e}')
        return None


def main():
    if len(sys.argv) < 2:
        print('用法: python gql_analyzer.py <js_file_or_dir> [output_file]')
        print('      python gql_analyzer.py --introspect <graphql_endpoint_url> [output_file]')
        print('示例: python gql_analyzer.py ./web_analysis/js/ gql_report.json')
        print('      python gql_analyzer.py --introspect https://api.example.com/graphql schema.json')
        sys.exit(1)

    if sys.argv[1] == '--introspect':
        if len(sys.argv) < 3:
            print('[!] 需要提供GraphQL端点URL')
            sys.exit(1)
        endpoint = sys.argv[2]
        output = sys.argv[3] if len(sys.argv) > 3 else 'gql_schema.json'
        print(f'[*] Introspection查询: {endpoint}')
        result = try_introspection(endpoint, output)
        if result:
            types = result.get('data', {}).get('__schema', {}).get('types', [])
            print(f'[+] 获取到 {len(types)} 个类型定义')
            for t in types[:10]:
                if not t['name'].startswith('__'):
                    fields = t.get('fields', []) or []
                    print(f'  - {t["kind"]} {t["name"]}: {len(fields)} fields')
            print(f'\n结果保存到: {output}')
        return

    target = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else 'gql_report.json'

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
    print('GraphQL分析结果:')
    print(f'{"="*60}')
    for key, items in results.items():
        if not items:
            continue
        print(f'  {key}: {len(items)} 条')
        for item in items[:3]:
            if isinstance(item, dict):
                val = item.get('name', item.get('value', item.get('type_name', item.get('context', '')[:80])))
                print(f'    - {item.get("type", "")}: {val}')

    # 保存
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f'\n结果保存到: {output}')


if __name__ == '__main__':
    main()
