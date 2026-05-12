#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站 API 深度提取脚本
从 B站首页 JS bundle 中提取所有 API 端点
"""

import re
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from site_analyzer import SiteAnalyzer

def extract_bilibili_apis():
    analyzer = SiteAnalyzer(timeout=20, delay=0.3)
    
    # 抓取首页
    print("🔍 抓取 B站首页...")
    page = analyzer.fetch_page('https://www.bilibili.com/')
    js_files = analyzer.fetch_js_files(page)
    
    print(f"📦 共下载 {len(js_files)} 个 JS 文件")
    
    all_apis = {}      # url -> info
    all_domains = set()
    auth_info = {}
    websockets = set()
    
    # 定义提取模式
    # 使用原始字节搜索避免引号转义问题
    api_patterns = [
        # /x/ 开头的 API 路径（B站标志性路径）
        (r'/x/[a-zA-Z0-9_/\-\.]+', 'bilibili_api'),
        # api.bilibili.com 完整 URL
        (r'(?:https?:)?//api\.bilibili\.com/[^\s\'"`,\)}\]]+', 'api_domain'),
        # passport 鉴权
        (r'(?:https?:)?//passport\.bilibili\.com/[^\s\'"`,\)}\]]+', 'passport'),
        # member 用户中心
        (r'(?:https?:)?//member\.bilibili\.com/[^\s\'"`,\)}\]]+', 'member'),
        # live 直播
        (r'(?:https?:)?//(?:api\.)?live\.bilibili\.com/[^\s\'"`,\)}\]]+', 'live'),
        # search 搜索
        (r'(?:https?:)?//search\.bilibili\.com/[^\s\'"`,\)}\]]+', 'search'),
        # space 个人空间
        (r'(?:https?:)?//space\.bilibili\.com/[^\s\'"`,\)}\]]+', 'space'),
        # message 消息
        (r'(?:https?:)?//message\.bilibili\.com/[^\s\'"`,\)}\]]+', 'message'),
        # s.search 搜索建议
        (r'(?:https?:)?//s\.search\.bilibili\.com/[^\s\'"`,\)}\]]+', 'search_suggest'),
        # cm 广告
        (r'(?:https?:)?//(?:api\.)?cm\.bilibili\.com/[^\s\'"`,\)}\]]+', 'ad'),
        # app 相关
        (r'(?:https?:)?//app\.bilibili\.com/[^\s\'"`,\)}\]]+', 'app'),
        # bapi
        (r'(?:https?:)?//bapi\.bilibili\.com/[^\s\'"`,\)}\]]+', 'bapi'),
        # WebSocket
        (r'wss?://[a-zA-Z0-9\-\.]+\.bilibili\.com[^\s\'"`,\)}\]]*', 'websocket'),
    ]
    
    static_exts = ('.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg', 
                   '.ico', '.woff', '.woff2', '.ttf', '.eot', '.map', '.webp')
    
    for src, content in js_files.items():
        file_label = src.split('/')[-1][:50] if '/' in src else src[:50]
        
        for pattern, category in api_patterns:
            for m in re.finditer(pattern, content):
                url = m.group(0).rstrip('\\').rstrip('"').rstrip("'").rstrip('`')
                
                # 过滤静态资源
                if any(url.lower().endswith(ext) for ext in static_exts):
                    continue
                
                # 过滤太短的
                if len(url) < 5:
                    continue
                
                if category == 'websocket':
                    websockets.add(url)
                    continue
                
                # 提取域名
                domain_match = re.search(r'//([a-zA-Z0-9\-\.]+\.bilibili\.com)', url)
                if domain_match:
                    all_domains.add(domain_match.group(1))
                
                if url not in all_apis:
                    # 获取上下文
                    start = max(0, m.start() - 80)
                    end = min(len(content), m.end() + 80)
                    context = content[start:end].strip()
                    
                    # 推断 HTTP 方法
                    method = 'GET'
                    ctx_lower = context.lower()
                    if 'post' in ctx_lower or 'method:"post"' in ctx_lower or "method:'post'" in ctx_lower:
                        method = 'POST'
                    
                    all_apis[url] = {
                        'url': url,
                        'method': method,
                        'category': category,
                        'source': file_label,
                        'context': context[:150],
                    }
    
    # 从内联脚本中提取 __INITIAL_STATE__ 等数据
    for script in page.get('scripts', []):
        if script.get('inline') and script.get('content'):
            content = script['content']
            
            # 提取 __INITIAL_STATE__
            state_match = re.search(r'__INITIAL_STATE__\s*=\s*(\{.+?\});', content, re.DOTALL)
            if state_match:
                try:
                    state = json.loads(state_match.group(1))
                    auth_info['initial_state_keys'] = list(state.keys())[:20]
                except:
                    pass
            
            # 提取 Cookie 相关
            for m in re.finditer(r'(?:document\.)?cookie.*?["\']([^"\']+)["\']', content):
                auth_info.setdefault('cookies', []).append(m.group(1))
    
    # 检查鉴权相关
    for src, content in js_files.items():
        # CSRF token
        if 'csrf' in content.lower() or 'bili_jct' in content:
            auth_info['csrf'] = 'bili_jct cookie used as CSRF token'
        
        # SESSDATA
        if 'SESSDATA' in content:
            auth_info['session'] = 'SESSDATA cookie for authentication'
        
        # buvid
        if 'buvid' in content.lower():
            auth_info['device_id'] = 'buvid3/buvid4 cookie for device identification'
        
        # wbi 签名
        if 'wbi' in content.lower() or 'mixin_key' in content.lower():
            auth_info['wbi_sign'] = 'WBI signature required for some APIs (img_key + sub_key)'
    
    # 输出结果
    print("\n" + "=" * 70)
    print("📊 B站 (bilibili.com) API 逆向分析报告")
    print("=" * 70)
    
    print(f"\n🌐 发现的域名 ({len(all_domains)} 个):")
    for d in sorted(all_domains):
        print(f"   • {d}")
    
    print(f"\n🔐 鉴权机制:")
    for k, v in auth_info.items():
        if k != 'cookies' and k != 'initial_state_keys':
            print(f"   • {k}: {v}")
    
    # 按分类整理
    categories = {}
    for url, info in all_apis.items():
        cat = info['category']
        categories.setdefault(cat, []).append(info)
    
    print(f"\n📡 发现 {len(all_apis)} 个 API 端点:")
    
    cat_names = {
        'bilibili_api': '🔵 核心 API (/x/ 路径)',
        'api_domain': '🟢 api.bilibili.com',
        'passport': '🔑 passport (鉴权)',
        'member': '👤 member (用户中心)',
        'live': '📺 live (直播)',
        'search': '🔍 search (搜索)',
        'search_suggest': '💡 search suggest (搜索建议)',
        'space': '🏠 space (个人空间)',
        'message': '💬 message (消息)',
        'ad': '📢 cm (广告)',
        'app': '📱 app (移动端)',
        'bapi': '🔷 bapi',
    }
    
    for cat, eps in sorted(categories.items()):
        cat_label = cat_names.get(cat, cat)
        print(f"\n   {cat_label} ({len(eps)} 个)")
        for ep in sorted(eps, key=lambda x: x['url'])[:25]:
            print(f"   {ep['method']:6s} {ep['url']}")
        if len(eps) > 25:
            print(f"   ... 还有 {len(eps) - 25} 个")
    
    if websockets:
        print(f"\n🔌 WebSocket ({len(websockets)} 个):")
        for ws in sorted(websockets):
            print(f"   • {ws}")
    
    # 保存完整结果
    result = {
        'site_url': 'https://www.bilibili.com/',
        'analyzed_at': __import__('time').strftime('%Y-%m-%dT%H:%M:%S'),
        'domains': sorted(all_domains),
        'api_endpoints': sorted(all_apis.values(), key=lambda x: (x['category'], x['url'])),
        'endpoints_count': len(all_apis),
        'auth_info': auth_info,
        'websockets': sorted(websockets),
        'page_info': {
            'title': page.get('title', ''),
            'forms': page.get('forms', []),
            'meta': page.get('meta', {}),
        }
    }
    
    output_path = '/data/workspace/bilibili_api_map.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n{'=' * 70}")
    print(f"✅ 完整接口图谱已保存到: {output_path}")
    print(f"   共 {len(all_apis)} 个 API + {len(websockets)} 个 WebSocket")
    
    return result


if __name__ == '__main__':
    extract_bilibili_apis()
