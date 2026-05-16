---
name: email-sender
description: |
  零依赖、不易被 QQ/163/Gmail 屏蔽的邮件发送技能。直连收件方 MX 服务器 25 端口，不依赖任何第三方 SMTP/账号/密码。
  适合自动化场景下推送日报、告警、通知（已实战验证可稳定投递 QQ 邮箱）。
  触发词：发邮件、send email、邮件推送、日报邮件、告警邮件、推送到我的邮箱、QQ 邮箱、163 邮箱、防屏蔽、SMTP。
  支持 HTML+纯文本 multipart 同发、附件、多收件人、自定义发件域名。
license: MIT
---

# email-sender 技能 — 防屏蔽邮件发送

## 何时使用本技能

当需要从代码 / 脚本 / 自动化任务中向用户邮箱发送邮件，并满足以下任一条件时：

- ❌ 不想配置 SMTP 账号密码（如 QQ 授权码、163 SMTP 密码等）
- ❌ 担心被反垃圾邮件系统屏蔽（特别是 QQ 邮箱屏蔽率高）
- ✅ 希望发件流程"开箱即用"，零外部依赖
- ✅ 推送日报、告警、通知类邮件
- ✅ 在容器/CI/无桌面 Linux 环境下发邮件

## 核心原理（为什么不被屏蔽）

本技能采用 **直连 MX + 多重防屏蔽签名** 的组合策略：

1. **直连收件方 MX 服务器的 25 端口**，绕开三方 SMTP 的"借道嫌疑"
2. **From 域名使用轻量短域名**（如 `newsbot.com`/`mailer.com`），不带敏感关键词
3. **EHLO 标准化**，遵循 RFC 5321 完整握手
4. **Subject 用 RFC 2047 base64 编码**，UTF-8 中文不乱码
5. **multipart/alternative 同时投递纯文本+HTML**，命中"友好邮件"特征
6. **Date/Message-ID 标准头补齐**，进一步降低被打 spam 标签概率

## 快速开始

### 1. 最简发送（一行调用）

```js
const { sendEmail } = require('./scripts/sender.js');

await sendEmail({
  to: 'me@example.com',
  subject: '🔥 今日日报',
  html: '<h1>Hello</h1><p>这是一封测试邮件</p>',
});
```

### 2. 完整参数

```js
await sendEmail({
  to: 'me@example.com',                        // 收件人，必填
  subject: '主题',                              // 主题，必填
  html: '<p>HTML 正文</p>',                     // HTML 正文（推荐）
  text: '纯文本正文',                            // 纯文本正文（可选，默认从 html 提取）
  from: 'noreply@newsbot.com',                 // 发件人，默认 mailer@newsbot.com
  fromName: '通知助手',                         // 发件人显示名，可选
  cc: ['cc@example.com'],                      // 抄送，可选
  bcc: ['bcc@example.com'],                    // 密送，可选
  replyTo: 'reply@example.com',                // 回复地址，可选
  attachments: [                                // 附件，可选
    { filename: 'a.pdf', path: '/tmp/a.pdf' },
    { filename: 'b.txt', content: 'hello' },
  ],
  timeoutMs: 30000,                            // 默认 30s
});
```

### 3. CLI 直接发

```bash
node scripts/cli.js \
  --to me@example.com \
  --subject "测试" \
  --html "<h1>Hi</h1>"

# 或从文件读 HTML
node scripts/cli.js --to me@example.com --subject "日报" --html-file /tmp/report.html
```

## 防屏蔽 Checklist（重要！）

以下规则在 `scripts/sender.js` 内已自动实现，**修改时务必保留**：

| 项 | 推荐做法 | 反例（易被拦截） |
|---|---|---|
| 发件域名 | 短域名 + 普通词（newsbot.com、mailer.com） | 含 "ad/promo/spam" 等关键词 |
| EHLO 主机名 | 与 From 域名一致 | localhost / 随机字符串 |
| Subject 编码 | RFC 2047 base64 (`=?UTF-8?B?xxx?=`) | 直接放中文 |
| 正文格式 | multipart/alternative + 纯文本 | 仅 HTML，无纯文本 |
| 频率 | 单次发送间隔 ≥30 分钟 | 1 分钟内连发多封 |
| HTML 内容 | 不含 base64 大图、不挂可疑外链 | 含 .exe/.zip 链接 |
| Date 头 | RFC 5322 格式带时区 | 缺失或本地时间 |
| Message-ID | 唯一 ID@domain | 重复或缺失 |

## 已知限制

- ⚠️ **需要出方向 25 端口畅通**。多数云服务商（阿里云/腾讯云）默认封禁 25 端口出口，AnyDev 开发机经测试可用
- ⚠️ **首次发往新邮箱可能进入"垃圾箱"**，连续 3-5 次稳定发送后会被加入白名单
- ⚠️ **不保证 100% 不被屏蔽**：如反垃圾策略升级，请考虑切换到自有域名 + DKIM/SPF 配置

## 验证方法

发送后到 QQ 邮箱"收件箱 / 垃圾箱"检查：
- 进收件箱 → ✅ 通过
- 进垃圾箱 → ⚠️ 在客户端"标记非垃圾"训练 1-2 次后可改善
- 完全没收到 → ❌ 25 端口被封 / MX 拒收，看 stderr 中 SMTP 返回码

## 实战案例

> **每日热点 TOP20 日报**（`top20_daily_report.js`）已用此方案稳定推送数月，从未进 QQ 垃圾箱。

## 文件结构

```
email-sender/
├── SKILL.md              # 本文件
├── scripts/
│   ├── sender.js         # 核心发送库（单文件，零依赖）
│   ├── cli.js            # 命令行工具
│   └── test.js           # 自检脚本
└── references/
    └── smtp-rfc.md       # RFC 5321/5322/2047 关键摘要
```

## License

MIT
