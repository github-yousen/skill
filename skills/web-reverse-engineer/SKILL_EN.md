---
name: web-reverse-engineer
description: |
  Website source code reverse engineering skill: Given a website URL, reverse-engineer the site's APIs, page layout, authentication flows, and data flows by fetching HTML/JS source code (not browser rendering).
  Trigger this skill when users mention "analyze website", "reverse engineer", "website API", "scrape endpoints", "website source code analysis", "reverse engineering", "analyze API", "crawl API", "website structure analysis",
  "help me look at this website", "what APIs does this site have", "white-box analysis", or simply provide a URL asking to check it out.
  Even if the user just gives a URL and says "help me look at this website", this skill should be triggered to proactively perform source code reverse engineering.
---

# Website Understanding & Operation Skill

## Core Objective

Given a website, achieve:

1. **Understand**: Figure out what the website can do and its functional structure
2. **Operate**: Given credentials (Cookie / Token), directly complete specific operations through API calls or simulated frontend interactions
3. **Persist**: Produce analysis documents for direct reuse next time, no need to re-analyze

Reverse engineering source code is a means, not the end.

---

## Work Modes

Enter different modes based on user intent:

| User Says | Mode |
|-----------|------|
| "Analyze this website" / Provides a URL | **Analysis Mode**: Understand features + Extract APIs + Produce documentation |
| "Help me operate xxx" + Has credentials | **Operation Mode**: Directly call APIs to complete tasks |
| "Help me operate xxx" + No credentials | Analyze first to find operation paths, prompt user for credentials |
| Provides a previously analyzed website | Prioritize reading existing analysis docs, enter operation mode directly |

---

## Critical Pitfalls (Must Read)

### Pitfall 1: web_fetch Returns Summaries, Not Raw Source Code

**Never use `web_fetch` to extract script tags, JS references, or API endpoints.**

The `web_fetch` tool AI-processes pages, returning readable summaries where `<script src>` tags are completely lost.

**Correct approach**: Always use Python scripts to fetch raw HTML:

```python
import urllib.request, ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(url, headers={
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept-Encoding': 'identity',
})
with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
    html = resp.read().decode('utf-8', errors='ignore')
```

### Pitfall 2: PowerShell Inline Code Quote Conflicts

**Don't use `python -c "..."` inline code in `execute_command`** — PowerShell breaks quotes.

**Correct approach**: Write `.py` script files first, then execute with `python temp-scripts/xxx.py`.

### Pitfall 3: Various URL Formats Need Unified Handling

| Format | Example | Handling |
|--------|---------|----------|
| Protocol-relative | `//api.example.com/...` | Prepend `https:` |
| Absolute path | `/x/web-interface/nav` | Concatenate with domain |
| Full URL | `https://api.example.com/...` | Use directly |

### Pitfall 4: HTTP Method and Path Are Separated in JS

Most frameworks write `{method: 'GET', url: '/api/xxx'}`, requiring specialized regex to capture both:
```python
re.findall(r'method:\s*["\']( GET|POST|PUT|DELETE|PATCH)["\'].*?url:\s*["\']([^"\']+)["\']', content)
```

### Pitfall 5: Main Entry JS Isn't Everything

Modern frontends (Vite/Webpack) use code splitting; business logic lives in chunk files.
Search for chunk references in the main JS and fetch them as needed.

---

## Analysis Mode: Source Code Fetching & Understanding

### Step 1: Fetch Raw HTML

**Use `scripts/web_fetch_source.py` (one-click completion)**, or manually:

```bash
python temp-scripts/web_fetch_source.py https://target-website.com/ output_dir
```

### Step 2: Identify Tech Stack

| Feature | Tech Stack | Impact |
|---------|-----------|--------|
| `__NEXT_DATA__` | Next.js | Inline JSON contains first-screen data and routes |
| `__NUXT__` / `__INITIAL_STATE__` | Nuxt / Vue SSR | Inline state has user data |
| `window.__pinia` | Pinia | Inline state tree can be directly parsed |
| `twirp/` paths | gRPC-Web | All POST, request body is JSON |
| `graphql` / `__typename` | GraphQL | Operation names = features, single endpoint multi-query |
| `sourceMappingURL` | Has Source Map | **Prioritize fetching** — can get unminified source |

### Step 3: Extract APIs

```python
# 1. Most informative: method-URL object format
method_url = re.findall(
    r'method:\s*["\']( GET|POST|PUT|DELETE|PATCH)["\'].*?url:\s*["\']([^"\']+)["\']',
    content
)

# 2. Common path prefixes
apis = re.findall(r'["\'`](/(?:api|x|v[0-9]+|pgc|graphql)/[a-zA-Z0-9_/.-]+)["\'`]', content)

# 3. Full domain URLs
full_urls = re.findall(r'(https?://api\.[a-z0-9.-]+/[a-zA-Z0-9_/.-]+)', content)

# 4. baseURL variables
base = re.findall(r'(?:baseUrl|baseURL|API_URL)\s*[:=]\s*["\']([^"\']+)["\']', content)
```

**Deduplication**: Use `{method}:{path}` as key, filter static resource extensions.

### Step 4: Understand Authentication

**Use `scripts/auth_analyzer.py`**, or search manually.

```bash
python temp-scripts/auth_analyzer.py output_dir/js/ auth_report.json
```

| Search Keyword | Purpose |
|---------------|---------|
| `interceptors.request.use` | Find request interceptors |
| `localStorage.setItem` / `sessionStorage` | Find Token storage locations |
| `csrf` / `X-CSRF` | Find CSRF mechanisms |
| `Authorization` / `Bearer` | Find Bearer Token method |
| `w_rid` / `wts` / `mixin_key` | Find WBI-type signing mechanisms |
| `withCredentials: true` | Confirm Cookie cross-origin sending |

### Step 5: Produce Documentation

**Read `references/report_template.md`, fill in the template, save as `{website_name}_report.md`.**

---

## Operation Mode: Direct Task Execution

### 1. Find the API for the Operation

Check existing analysis docs first; if none, analyze first.

### 2. Construct Requests

**Cookie Authentication (Most Common)**
```python
import urllib.request, urllib.parse, ssl, json

def api_request(method, path, params=None, data=None, cookies=''):
    base = 'https://api.example.com'
    url = base + path
    if params:
        url += '?' + urllib.parse.urlencode(params)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Cookie': cookies,
        'Referer': 'https://www.example.com/',
    }
    body = None
    if data:
        body = urllib.parse.urlencode(data).encode()
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, context=ctx) as resp:
        return json.loads(resp.read().decode())
```

**Bearer Token Authentication**
```bash
curl -X GET "https://api.example.com/api/xxx" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json"
```

### 3. Multi-Step Operation Chains

Some operations require calling multiple APIs in sequence, execute in dependency order.

---

## Documentation Output

Produce `{website_name}_report.md` containing:

| Section | Content | Main Purpose |
|---------|---------|--------------|
| Basic Info | Tech stack, JS files, Source Map | Quick understanding |
| Auth Flow | Credential list, signing mechanism | Know what to provide |
| API Endpoint List | APIs grouped by module | Find the corresponding API |
| Page Routes | Path to Feature mapping | Understand full functionality |
| Key Data Structures | Important API response formats | Parse return data |
| **Actionable Operations** | Operation list + Call templates | **Core deliverable** |
| Appendix | JS list, domain system | Supplementary information |

Report template is in `references/report_template.md`.

---

## General Scripts

| Script | Purpose |
|--------|---------|
| `scripts/web_fetch_source.py` | One-click: HTML to JS to API endpoint extraction |
| `scripts/auth_analyzer.py` | Auth deep analysis: Cookie/CSRF/Token/Signing |

**Usage**: Copy to project `temp-scripts/` directory and run.

---

## Tool Usage Priority

| Scenario | Tool |
|----------|------|
| Fetch raw HTML / JS | Python `urllib.request` script |
| Search patterns in JS | Python `re` module, batch process with scripts |
| Make API calls | Python script or `curl` (write as `.ps1` to execute) |
| Want to use web_fetch | Only for human-readable content, not for source code fetching |
