# Proxy and KV Bridge Patterns

## Reverse proxy Worker / Pages Function

Use this pattern when the user wants a lightweight Cloudflare edge proxy.

### Core behavior

- Accept the incoming request
- Rebuild the upstream target URL
- Forward method, headers, and body
- Return the upstream response body
- Add CORS headers when the caller is a browser app

### Example use cases

- Bypass basic geo/network reachability issues
- Add a stable proxy endpoint in front of an upstream service
- Expose a simple browser-consumable endpoint

## KV-backed bridge Worker

Use KV when the user needs lightweight persistence or relay at the edge.

### Proven pattern

- Store inbox messages under keys like `msg:<room>:<target>`
- Store room history under keys like `history:<room>`
- Expose simple send / recv / history / clear routes

### Notes

- Good for lightweight message relay and polling
- Not a replacement for queues or databases under heavy throughput
- Keep payload size and history retention bounded

## Example wrangler.toml KV binding

```toml
[[kv_namespaces]]
binding = "AI_BRIDGE"
id = "YOUR_KV_NAMESPACE_ID"
```
