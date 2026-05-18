# 语雀API客户端 - 供skill调用的底层工具脚本
# 用法: python yuque_client.py <command> [args...]
# 命令:
#   whoami                        - 获取当前用户信息
#   list-books                    - 获取知识库列表
#   list-docs <book_id> [offset] [limit]  - 获取知识库文档列表
#   get-doc <doc_id> <book_id> [mode]     - 获取文档详情(mode=read/edit)
#   get-toc <book_id>             - 获取知识库目录结构
#   create-doc <book_id> <title> [slug] [body] - 创建文档
#   update-doc <doc_id> <book_id> [title] [--body-file <path>] [body] - 更新文档(支持从文件读取body)
#   delete-doc <doc_id> <book_id> - 删除文档
#   search <keyword> [type]       - 搜索(type=doc/book)
#   move-doc <doc_id> <book_id> <target_book_id> - 移动文档
#   get-doc-versions <doc_id>     - 获取文档版本列表
#
# 注意: update-doc 会通过 /api/docs/:id/content 接口同步更新 body 和 body_draft，
#       确保语雀前端能正确显示更新后的内容。
# 注意: 长内容建议用 --body-file 参数从文件读取，避免命令行长度限制。

import urllib.request
import urllib.parse
import ssl
import json
import os
import sys
from datetime import datetime

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

API_BASE = 'https://www.yuque.com'

# 从环境变量或配置文件读取凭证
def get_credentials():
    """获取语雀API凭证，优先从环境变量读取"""
    cookie = os.environ.get('YUQUE_COOKIE', '')
    csrf_token = os.environ.get('YUQUE_CSRF_TOKEN', '')
    x_login = os.environ.get('YUQUE_X_LOGIN', '')
    
    # 如果环境变量没设置，尝试从配置文件读取
    if not cookie:
        config_path = os.path.join(os.path.dirname(__file__), '..', 'credentials.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                cookie = config.get('cookie', '')
                csrf_token = config.get('csrf_token', '')
                x_login = config.get('x_login', '')
    
    return cookie, csrf_token, x_login


def api_request(method, path, params=None, data=None, cookie='', csrf_token='', x_login=''):
    """发送语雀API请求"""
    url = API_BASE + path
    if params:
        url += '?' + urllib.parse.urlencode(params)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Content-Type': 'application/json',
        'Cookie': cookie,
        'Referer': 'https://www.yuque.com/',
        'x-csrf-token': csrf_token,
        'x-login': x_login,
        'X-Requested-With': 'XMLHttpRequest',
        'X-KL-Ajax-Request': 'Ajax_Request',
    }
    
    body = None
    if data:
        body = json.dumps(data).encode('utf-8')
    
    try:
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=30) as resp:
            raw = resp.read().decode('utf-8', errors='ignore')
            try:
                return json.loads(raw)
            except:
                return {'_raw': raw[:5000]}
    except urllib.error.HTTPError as e:
        body_text = ''
        try:
            body_text = e.read().decode('utf-8', errors='ignore')[:1000]
        except:
            pass
        return {'_error': f'HTTP {e.code}', '_body': body_text}
    except Exception as e:
        return {'_error': str(e)}


def cmd_whoami(cookie, csrf_token, x_login):
    r = api_request('GET', '/api/mine', cookie=cookie, csrf_token=csrf_token, x_login=x_login)
    if '_error' in r:
        return r
    return r.get('data', r)


def cmd_list_books(cookie, csrf_token, x_login):
    r = api_request('GET', '/api/mine/books', cookie=cookie, csrf_token=csrf_token, x_login=x_login)
    if '_error' in r:
        return r
    books = r.get('data', [])
    result = []
    for b in books:
        result.append({
            'id': b.get('id'),
            'name': b.get('name'),
            'slug': b.get('slug'),
            'type': b.get('type'),
            'public': b.get('public'),
            'description': b.get('description', ''),
            'user': b.get('user', {}).get('login', ''),
            'topics_count': b.get('topics_count', 0),
            'public_topics_count': b.get('public_topics_count', 0),
        })
    return result


def cmd_list_docs(cookie, csrf_token, x_login, book_id, offset=0, limit=20):
    r = api_request('GET', f'/api/books/{book_id}/docs', 
                    params={'offset': offset, 'limit': limit},
                    cookie=cookie, csrf_token=csrf_token, x_login=x_login)
    if '_error' in r:
        return r
    docs = r.get('data', [])
    result = []
    for d in docs:
        result.append({
            'id': d.get('id'),
            'title': d.get('title'),
            'slug': d.get('slug'),
            'book_id': d.get('book_id'),
            'format': d.get('format'),
            'word_count': d.get('word_count'),
            'status': d.get('status'),
            'public': d.get('public'),
            'description': d.get('description', ''),
            'created_at': d.get('created_at'),
            'updated_at': d.get('updated_at'),
            'published_at': d.get('published_at'),
        })
    return result


def cmd_get_doc(cookie, csrf_token, x_login, doc_id, book_id, mode='edit'):
    r = api_request('GET', f'/api/docs/{doc_id}', 
                    params={'book_id': book_id, 'mode': mode},
                    cookie=cookie, csrf_token=csrf_token, x_login=x_login)
    if '_error' in r:
        return r
    d = r.get('data', {})
    result = {
        'id': d.get('id'),
        'title': d.get('title'),
        'slug': d.get('slug'),
        'book_id': d.get('book_id'),
        'format': d.get('format'),
        'word_count': d.get('word_count'),
        'status': d.get('status'),
        'public': d.get('public'),
        'description': d.get('description', ''),
        'body': d.get('body', ''),
        'body_draft': d.get('body_draft', ''),
        'created_at': d.get('created_at'),
        'updated_at': d.get('updated_at'),
        'published_at': d.get('published_at'),
    }
    return result


def cmd_get_toc(cookie, csrf_token, x_login, book_id):
    r = api_request('GET', f'/api/books/{book_id}/toc',
                    cookie=cookie, csrf_token=csrf_token, x_login=x_login)
    if '_error' in r:
        return r
    data = r.get('data', {})
    toc = data.get('toc', [])
    docs = data.get('docs', [])
    return {'toc': toc, 'docs': docs}


def cmd_create_doc(cookie, csrf_token, x_login, book_id, title, slug='', body=''):
    doc_data = {
        'book_id': book_id,
        'title': title,
        'format': 'lake',
    }
    if slug:
        doc_data['slug'] = slug
    if body:
        doc_data['body'] = body
    
    r = api_request('POST', '/api/docs', data=doc_data,
                    cookie=cookie, csrf_token=csrf_token, x_login=x_login)
    if '_error' in r:
        return r
    d = r.get('data', {})
    return {
        'id': d.get('id'),
        'title': d.get('title'),
        'slug': d.get('slug'),
        'book_id': d.get('book_id'),
        'format': d.get('format'),
    }


def cmd_update_doc(cookie, csrf_token, x_login, doc_id, book_id, title=None, body=None):
    """更新文档。
    
    使用两步更新策略：
    1. PUT /api/docs/:id/content — 更新 body_draft（语雀前端渲染依赖此字段）
    2. PUT /api/docs/:id — 更新 body 和 title（已发布内容）
    
    这样确保语雀网页端能立即看到更新后的内容。
    """
    result_info = {}
    
    # Step 1: 如果有 body，通过 content 接口更新 body_draft
    if body is not None:
        # 先获取 draft_version
        doc_info = api_request('GET', f'/api/docs/{doc_id}',
                               params={'book_id': book_id, 'mode': 'edit'},
                               cookie=cookie, csrf_token=csrf_token, x_login=x_login)
        if '_error' in doc_info:
            return {'_error': 'Failed to get draft_version', '_detail': doc_info}
        
        draft_version = doc_info.get('data', {}).get('draft_version', 0)
        
        content_data = {
            'format': 'lake',
            'body_asl': body,
            'body_draft_asl': body,
            'save_type': 'user',
            'draft_version': draft_version,
        }
        r_content = api_request('PUT', f'/api/docs/{doc_id}/content', data=content_data,
                                cookie=cookie, csrf_token=csrf_token, x_login=x_login)
        if '_error' in r_content:
            result_info['_content_warning'] = f"content接口失败: {r_content.get('_error', '')}"
        else:
            result_info['content_updated'] = True
    
    # Step 2: 用普通接口更新 body 和 title
    doc_data = {'book_id': book_id}
    if title is not None:
        doc_data['title'] = title
    if body is not None:
        doc_data['body'] = body
    
    r = api_request('PUT', f'/api/docs/{doc_id}', data=doc_data,
                    cookie=cookie, csrf_token=csrf_token, x_login=x_login)
    if '_error' in r:
        return {**result_info, '_error': r.get('_error'), '_body': r.get('_body', '')}
    
    d = r.get('data', {})
    return {
        **result_info,
        'id': d.get('id'),
        'title': d.get('title'),
        'slug': d.get('slug'),
        'book_id': d.get('book_id'),
    }


def cmd_delete_doc(cookie, csrf_token, x_login, doc_id, book_id):
    r = api_request('DELETE', f'/api/docs/{doc_id}', data={'book_id': book_id},
                    cookie=cookie, csrf_token=csrf_token, x_login=x_login)
    if '_error' in r:
        return r
    return {'success': True, 'doc_id': doc_id}


def cmd_search(cookie, csrf_token, x_login, keyword, search_type='doc'):
    r = api_request('GET', '/api/zsearch', 
                    params={'q': keyword, 'type': search_type},
                    cookie=cookie, csrf_token=csrf_token, x_login=x_login)
    if '_error' in r:
        return r
    data = r.get('data', {})
    hits = data.get('hits', [])
    result = []
    for h in hits:
        result.append({
            'id': h.get('id'),
            'title': h.get('title'),
            'slug': h.get('slug'),
            'type': h.get('type'),
            'url': h.get('url'),
            'abstract': h.get('abstract', ''),
            'book_name': h.get('book_name', ''),
        })
    return {'total': data.get('totalHits', len(result)), 'hits': result}


def cmd_get_doc_versions(cookie, csrf_token, x_login, doc_id):
    r = api_request('GET', '/api/doc_versions', params={'doc_id': doc_id},
                    cookie=cookie, csrf_token=csrf_token, x_login=x_login)
    if '_error' in r:
        return r
    versions = r.get('data', [])
    result = []
    for v in versions:
        result.append({
            'id': v.get('id'),
            'title': v.get('title'),
            'draft': v.get('draft'),
            'created_at': v.get('created_at'),
            'isReleased': v.get('isReleased'),
        })
    return result


def main():
    if len(sys.argv) < 2:
        print('用法: python yuque_client.py <command> [args...]')
        print('命令: whoami, list-books, list-docs, get-doc, get-toc, create-doc, update-doc, delete-doc, search, get-doc-versions')
        sys.exit(1)
    
    cookie, csrf_token, x_login = get_credentials()
    if not cookie:
        print('错误: 未设置凭证。请设置环境变量 YUQUE_COOKIE, YUQUE_CSRF_TOKEN, YUQUE_X_LOGIN 或创建 credentials.json')
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'whoami':
        result = cmd_whoami(cookie, csrf_token, x_login)
    elif command == 'list-books':
        result = cmd_list_books(cookie, csrf_token, x_login)
    elif command == 'list-docs':
        book_id = int(sys.argv[2])
        offset = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else 20
        result = cmd_list_docs(cookie, csrf_token, x_login, book_id, offset, limit)
    elif command == 'get-doc':
        doc_id = sys.argv[2]
        book_id = int(sys.argv[3])
        mode = sys.argv[4] if len(sys.argv) > 4 else 'edit'
        result = cmd_get_doc(cookie, csrf_token, x_login, doc_id, book_id, mode)
    elif command == 'get-toc':
        book_id = int(sys.argv[2])
        result = cmd_get_toc(cookie, csrf_token, x_login, book_id)
    elif command == 'create-doc':
        book_id = int(sys.argv[2])
        title = sys.argv[3]
        slug = sys.argv[4] if len(sys.argv) > 4 else ''
        body = sys.argv[5] if len(sys.argv) > 5 else ''
        result = cmd_create_doc(cookie, csrf_token, x_login, book_id, title, slug, body)
    elif command == 'update-doc':
        doc_id = sys.argv[2]
        book_id = int(sys.argv[3])
        title = None
        body = None
        # 解析剩余参数，支持 --body-file
        i = 4
        while i < len(sys.argv):
            if sys.argv[i] == '--body-file':
                i += 1
                if i < len(sys.argv):
                    file_path = sys.argv[i]
                    with open(file_path, 'r', encoding='utf-8') as f:
                        body = f.read()
                i += 1
            elif title is None:
                title = sys.argv[i]
                i += 1
            elif body is None:
                body = sys.argv[i]
                i += 1
            else:
                i += 1
        result = cmd_update_doc(cookie, csrf_token, x_login, doc_id, book_id, title, body)
    elif command == 'delete-doc':
        doc_id = sys.argv[2]
        book_id = int(sys.argv[3])
        result = cmd_delete_doc(cookie, csrf_token, x_login, doc_id, book_id)
    elif command == 'search':
        keyword = sys.argv[2]
        search_type = sys.argv[3] if len(sys.argv) > 3 else 'doc'
        result = cmd_search(cookie, csrf_token, x_login, keyword, search_type)
    elif command == 'get-doc-versions':
        doc_id = int(sys.argv[2])
        result = cmd_get_doc_versions(cookie, csrf_token, x_login, doc_id)
    else:
        print(f'未知命令: {command}')
        sys.exit(1)
    
    output = json.dumps(result, ensure_ascii=False, indent=2)
    # 处理Windows控制台编码问题
    try:
        print(output)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(output.encode('utf-8', errors='replace'))
        sys.stdout.buffer.write(b'\n')


if __name__ == '__main__':
    # 设置stdout编码
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
