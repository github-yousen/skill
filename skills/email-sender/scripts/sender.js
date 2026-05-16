/**
 * email-sender / sender.js
 *
 * 零依赖、防屏蔽的邮件发送库。
 * 直连收件方 MX 服务器 25 端口，不依赖任何第三方 SMTP/账号。
 *
 * 核心特性：
 *  - RFC 5321 标准 SMTP 握手
 *  - Subject RFC 2047 base64 编码（中文不乱码）
 *  - multipart/alternative 同时投递 HTML + 纯文本
 *  - 标准 Date / Message-ID 头
 *  - 支持附件（base64 编码 multipart/mixed）
 *  - 失败时自动尝试备用 MX
 *
 * 使用：
 *   const { sendEmail } = require('./sender.js');
 *   await sendEmail({ to, subject, html });
 *
 * License: MIT
 */

'use strict';

const dns = require('dns');
const net = require('net');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

// ==================== 工具函数 ====================

/** RFC 2047 base64 主题编码 */
function encodeSubject(subject) {
  return `=?UTF-8?B?${Buffer.from(subject, 'utf-8').toString('base64')}?=`;
}

/** RFC 5322 格式的 Date 头 */
function rfc5322Date(d = new Date()) {
  return d.toUTCString().replace('GMT', '+0000');
}

/** 生成全局唯一 Message-ID */
function genMessageId(domain) {
  const rnd = crypto.randomBytes(8).toString('hex');
  return `<${Date.now()}.${rnd}@${domain}>`;
}

/** HTML → 纯文本（极简版，仅去标签） */
function htmlToText(html) {
  return html
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<[^>]+>/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

/** 解析 MX 记录，按优先级返回所有 exchange，便于失败重试 */
function resolveMX(domain) {
  return new Promise((resolve, reject) => {
    dns.resolveMx(domain, (err, addresses) => {
      if (err) return reject(err);
      addresses.sort((a, b) => a.priority - b.priority);
      resolve(addresses.map((a) => a.exchange));
    });
  });
}

// ==================== 邮件构造 ====================

/**
 * 构造原始 RFC 5322 邮件文本
 * @param {Object} opts
 */
function buildRawEmail(opts) {
  const {
    from,
    fromName,
    to,
    cc = [],
    bcc = [],
    replyTo,
    subject,
    html,
    text,
    attachments = [],
    extraHeaders = {},
  } = opts;

  const fromDomain = from.split('@')[1] || 'mailer.com';
  const messageId = genMessageId(fromDomain);

  const fromHeader = fromName
    ? `${encodeSubject(fromName)} <${from}>`
    : from;

  const headers = [
    `From: ${fromHeader}`,
    `To: ${Array.isArray(to) ? to.join(', ') : to}`,
    cc.length ? `Cc: ${cc.join(', ')}` : null,
    replyTo ? `Reply-To: ${replyTo}` : null,
    `Subject: ${encodeSubject(subject)}`,
    `Date: ${rfc5322Date()}`,
    `Message-ID: ${messageId}`,
    `MIME-Version: 1.0`,
    `X-Mailer: email-sender/1.0`,
  ].filter(Boolean);

  Object.entries(extraHeaders).forEach(([k, v]) => {
    headers.push(`${k}: ${v}`);
  });

  // 选择 MIME 结构
  const hasAttachments = attachments.length > 0;
  const hasMultipart = !!html;

  if (!hasAttachments && !hasMultipart) {
    // 纯文本简单邮件
    headers.push('Content-Type: text/plain; charset=UTF-8');
    headers.push('Content-Transfer-Encoding: base64');
    return headers.join('\r\n') + '\r\n\r\n' + Buffer.from(text || '', 'utf-8').toString('base64');
  }

  if (!hasAttachments && hasMultipart) {
    // multipart/alternative
    const boundary = 'alt_' + crypto.randomBytes(8).toString('hex');
    headers.push(`Content-Type: multipart/alternative; boundary="${boundary}"`);
    const plainText = text || htmlToText(html);
    const body = [
      '',
      `--${boundary}`,
      `Content-Type: text/plain; charset=UTF-8`,
      `Content-Transfer-Encoding: base64`,
      ``,
      Buffer.from(plainText, 'utf-8').toString('base64'),
      ``,
      `--${boundary}`,
      `Content-Type: text/html; charset=UTF-8`,
      `Content-Transfer-Encoding: base64`,
      ``,
      Buffer.from(html, 'utf-8').toString('base64'),
      ``,
      `--${boundary}--`,
      ``,
    ].join('\r\n');
    return headers.join('\r\n') + body;
  }

  // multipart/mixed（带附件） → 内层再 multipart/alternative
  const mixedBoundary = 'mix_' + crypto.randomBytes(8).toString('hex');
  const altBoundary = 'alt_' + crypto.randomBytes(8).toString('hex');
  headers.push(`Content-Type: multipart/mixed; boundary="${mixedBoundary}"`);

  const parts = [''];

  // 文本部分
  parts.push(`--${mixedBoundary}`);
  parts.push(`Content-Type: multipart/alternative; boundary="${altBoundary}"`);
  parts.push('');
  const plainText = text || (html ? htmlToText(html) : '');
  parts.push(`--${altBoundary}`);
  parts.push(`Content-Type: text/plain; charset=UTF-8`);
  parts.push(`Content-Transfer-Encoding: base64`);
  parts.push('');
  parts.push(Buffer.from(plainText, 'utf-8').toString('base64'));
  parts.push('');
  if (html) {
    parts.push(`--${altBoundary}`);
    parts.push(`Content-Type: text/html; charset=UTF-8`);
    parts.push(`Content-Transfer-Encoding: base64`);
    parts.push('');
    parts.push(Buffer.from(html, 'utf-8').toString('base64'));
    parts.push('');
  }
  parts.push(`--${altBoundary}--`);
  parts.push('');

  // 附件
  for (const att of attachments) {
    let content;
    if (att.path) content = fs.readFileSync(att.path);
    else if (Buffer.isBuffer(att.content)) content = att.content;
    else content = Buffer.from(att.content || '', 'utf-8');

    const filename = att.filename || (att.path ? path.basename(att.path) : 'attachment');
    const mime = att.contentType || 'application/octet-stream';
    parts.push(`--${mixedBoundary}`);
    parts.push(`Content-Type: ${mime}; name="${encodeSubject(filename)}"`);
    parts.push(`Content-Disposition: attachment; filename="${encodeSubject(filename)}"`);
    parts.push(`Content-Transfer-Encoding: base64`);
    parts.push('');
    // 每行 76 字符的 base64
    parts.push(content.toString('base64').replace(/(.{76})/g, '$1\r\n'));
    parts.push('');
  }
  parts.push(`--${mixedBoundary}--`);
  parts.push('');

  return headers.join('\r\n') + parts.join('\r\n');
}

// ==================== SMTP 客户端 ====================

/**
 * 与单个 MX 主机进行 SMTP 会话并投递邮件
 */
function smtpDeliver(mxHost, options) {
  const {
    from,
    rcpts, // [to, ...cc, ...bcc]
    rawEmail,
    ehloHost,
    timeoutMs = 30000,
    verbose = false,
  } = options;

  return new Promise((resolve, reject) => {
    const client = net.createConnection(25, mxHost);
    let buffer = '';
    let step = 0;
    const log = verbose ? (m) => console.log('[SMTP]', m) : () => {};
    let rcptIdx = 0;

    client.setTimeout(timeoutMs);

    function send(line) {
      log('> ' + line);
      client.write(line + '\r\n');
    }

    client.on('data', (data) => {
      buffer += data.toString();
      const lines = buffer.split('\r\n');
      buffer = lines.pop();
      for (const line of lines) {
        if (!line) continue;
        log('< ' + line);
        const code = parseInt(line.substring(0, 3), 10);
        const more = line.charAt(3) === '-';

        if (more) continue; // 多行响应继续等

        if (step === 0 && code === 220) {
          send(`EHLO ${ehloHost}`);
          step = 1;
        } else if (step === 1 && code === 250) {
          send(`MAIL FROM:<${from}>`);
          step = 2;
        } else if (step === 2 && code === 250) {
          if (rcptIdx >= rcpts.length) {
            send('DATA');
            step = 4;
          } else {
            send(`RCPT TO:<${rcpts[rcptIdx++]}>`);
            step = 3;
          }
        } else if (step === 3 && code === 250) {
          if (rcptIdx >= rcpts.length) {
            send('DATA');
            step = 4;
          } else {
            send(`RCPT TO:<${rcpts[rcptIdx++]}>`);
          }
        } else if (step === 4 && code === 354) {
          // 数据中含 "\r\n.\r\n" 的需要点填充
          const safeBody = rawEmail.replace(/\r\n\./g, '\r\n..');
          client.write(safeBody);
          client.write('\r\n.\r\n');
          step = 5;
        } else if (step === 5 && code === 250) {
          send('QUIT');
          step = 6;
          resolve({ ok: true, mx: mxHost, response: line });
        } else if (step === 6) {
          client.destroy();
        } else if (code >= 400) {
          client.destroy();
          reject(new Error(`SMTP ${mxHost}: ${line}`));
        }
      }
    });
    client.on('error', (e) => reject(new Error(`Connect ${mxHost}: ${e.message}`)));
    client.on('timeout', () => {
      client.destroy();
      reject(new Error(`Timeout ${mxHost}`));
    });
  });
}

// ==================== 主接口 ====================

/**
 * 发送邮件 —— 主入口
 *
 * @param {Object} opts
 * @param {string|string[]} opts.to        收件人（必填）
 * @param {string} opts.subject            主题（必填）
 * @param {string} [opts.html]             HTML 正文
 * @param {string} [opts.text]             纯文本正文（默认从 html 提取）
 * @param {string} [opts.from]             发件人邮箱，默认 mailer@newsbot.com
 * @param {string} [opts.fromName]         发件人显示名
 * @param {string[]} [opts.cc]             抄送
 * @param {string[]} [opts.bcc]            密送
 * @param {string} [opts.replyTo]          回复地址
 * @param {Array} [opts.attachments]       附件 [{filename, path|content, contentType}]
 * @param {Object} [opts.extraHeaders]     自定义头
 * @param {number} [opts.timeoutMs]        SMTP 超时，默认 30s
 * @param {boolean} [opts.verbose]         打印 SMTP 会话
 * @returns {Promise<{ok, mx, response}>}
 */
async function sendEmail(opts) {
  if (!opts.to) throw new Error('opts.to is required');
  if (!opts.subject) throw new Error('opts.subject is required');
  if (!opts.html && !opts.text) throw new Error('either opts.html or opts.text is required');

  const from = opts.from || 'mailer@newsbot.com';
  const fromDomain = from.split('@')[1] || 'newsbot.com';
  const ehloHost = opts.ehloHost || fromDomain;

  const tos = Array.isArray(opts.to) ? opts.to : [opts.to];
  const cc = opts.cc || [];
  const bcc = opts.bcc || [];
  const allRcpts = [...tos, ...cc, ...bcc];

  // 按收件域名分组（同域名共享一次连接），不同域名分别投递
  const byDomain = {};
  for (const r of allRcpts) {
    const d = r.split('@')[1];
    (byDomain[d] = byDomain[d] || []).push(r);
  }

  const rawEmail = buildRawEmail({ ...opts, from });

  const results = [];
  for (const [domain, rcpts] of Object.entries(byDomain)) {
    const mxList = await resolveMX(domain);
    if (!mxList.length) throw new Error(`No MX for ${domain}`);

    let lastErr = null;
    let delivered = false;
    for (const mx of mxList) {
      try {
        const r = await smtpDeliver(mx, {
          from, rcpts, rawEmail, ehloHost,
          timeoutMs: opts.timeoutMs,
          verbose: opts.verbose,
        });
        results.push({ domain, ...r });
        delivered = true;
        break;
      } catch (e) {
        lastErr = e;
      }
    }
    if (!delivered) throw lastErr || new Error(`Delivery to ${domain} failed`);
  }

  return { ok: true, results };
}

module.exports = { sendEmail, buildRawEmail, encodeSubject, resolveMX };
