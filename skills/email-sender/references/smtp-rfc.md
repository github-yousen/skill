# SMTP / 邮件协议关键 RFC 速查

本文档摘录 email-sender 实现中所依赖的关键协议条款，便于读者理解为什么这样写。

## RFC 5321 — SMTP（核心传输协议）

### 标准会话流程

```
S: 220 mx.qq.com ESMTP ready              ← 服务端 banner
C: EHLO sender.example.com                ← 客户端打招呼
S: 250-mx.qq.com Hello                    ← 多行响应（"-" 表示 still more）
S: 250 SIZE 52428800
C: MAIL FROM:<sender@example.com>         ← 设置发件人
S: 250 OK
C: RCPT TO:<recipient@qq.com>             ← 设置收件人（可多次）
S: 250 OK
C: DATA                                   ← 开始数据
S: 354 End data with <CR><LF>.<CR><LF>
C: <邮件原始内容>
C: .                                      ← 单独一行的"."表示数据结束
S: 250 OK queued
C: QUIT
S: 221 Bye
```

### 重要细节

1. **行结束符必须是 CRLF（`\r\n`）** —— LF 单字符会被部分 MX 拒收
2. **数据点填充**：邮件正文中如果出现 `\r\n.\r\n` 会被服务端误认为结束，需把开头的"." 加倍变 ".."（client 加，server 解）
3. **EHLO 主机名**应是与 From 域名一致的 FQDN，否则可能被打 spam 标签
4. **响应码**：2xx 成功，3xx 中间态（如 354），4xx 临时失败（应重试），5xx 永久失败

## RFC 5322 — 邮件格式（信头与信体）

### 必需头

| 头 | 示例 | 说明 |
|---|---|---|
| From | `From: Sender <a@b.com>` | 发件人 |
| Date | `Date: Tue, 16 May 2026 03:15:00 +0000` | UTC 格式 |
| Message-ID | `<unique@domain>` | 必须全局唯一，强烈推荐补齐 |

### 推荐头

- `To` / `Cc` / `Reply-To`
- `Subject`
- `MIME-Version: 1.0`
- `X-Mailer`（标明发件软件，可选但有助于反垃圾系统判断）

### Date 头格式（RFC 5322 §3.3）

```
Date: <day-name>, <day> <month> <year> <hour>:<min>:<sec> <zone>
```

例：`Wed, 16 May 2026 11:14:01 +0800`

## RFC 2047 — 头字段非 ASCII 编码

中文 Subject 必须编码为 base64 形式：

```
Subject: =?UTF-8?B?5pel5oql?=
                  ^charset?B?<base64>?=
                  B = base64 编码
                  Q = quoted-printable 编码
```

⚠️ 直接放中文会被部分 MX 退回（5.0.0 Header invalid）。

## RFC 2045 / 2046 / 2049 — MIME 多部分内容

### multipart/alternative

同一封邮件提供多种格式，客户端选最优显示。本 skill 默认用 `text/plain + text/html` 双格式：

```
Content-Type: multipart/alternative; boundary="alt_xxx"

--alt_xxx
Content-Type: text/plain; charset=UTF-8
Content-Transfer-Encoding: base64

<base64 of plain text>

--alt_xxx
Content-Type: text/html; charset=UTF-8
Content-Transfer-Encoding: base64

<base64 of html>

--alt_xxx--
```

为什么"双格式"防屏蔽？反垃圾系统会扣分纯 HTML 邮件，因为这是营销邮件常见特征。

### multipart/mixed（带附件时）

外层 mixed，内层放一个 alternative 子树承载文本/HTML，平级追加每个附件：

```
multipart/mixed
├── multipart/alternative
│   ├── text/plain
│   └── text/html
└── application/octet-stream (附件)
```

## 防屏蔽工程要点（实战经验）

1. **从域名要"轻"**：避免 `noreply-promo-2025.aaa.io` 这类 spam-like 域名
2. **频率限制**：每收件人每小时不超过 3 封，每天不超过 20 封（QQ 反垃圾经验值）
3. **正文不要全是图片**或全是链接，纯文本内容应至少 50 字
4. **避免常见 spam 关键词**：免费、中奖、点击、限时、亿万富翁……
5. **HELO 主机名要可解析**，最好与 From 域名一致
6. **DKIM/SPF**：如果有自有域名，强烈推荐配置（本 skill 不强制，但是配了能进收件箱概率显著提升）

## 排错

| SMTP 返回码 | 含义 | 处理 |
|---|---|---|
| 421 | 服务暂时不可用 | 等几分钟重试 |
| 450 | 邮箱忙 | 重试 |
| 451 | 处理失败 | 重试 |
| 550 | 邮箱不存在 / 拒收 | 检查地址，不要重试 |
| 552 | 邮件超大 | 拆分 |
| 554 | 拒绝（反垃圾） | 检查 From 域名 / 内容 / 频率 |

## 进一步阅读

- RFC 5321: https://tools.ietf.org/html/rfc5321
- RFC 5322: https://tools.ietf.org/html/rfc5322
- RFC 2045-2049: MIME 系列
- RFC 2047: 头字段编码
