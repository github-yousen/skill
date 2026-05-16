#!/usr/bin/env node
/**
 * 自检脚本：发送一封测试邮件到指定收件人
 *
 * 用法：
 *   node test.js <收件邮箱>
 *   node test.js me@example.com
 */

const { sendEmail } = require('./sender.js');

async function main() {
  const to = process.argv[2];
  if (!to) {
    console.error('用法: node test.js <收件邮箱>');
    process.exit(1);
  }

  const html = `<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:20px;background:#f0f2f5;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;">
<div style="max-width:600px;margin:0 auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);">
  <div style="background:linear-gradient(135deg,#1a237e,#3949ab);padding:32px;text-align:center;color:#fff;">
    <div style="font-size:48px;">📧</div>
    <h1 style="margin:12px 0 4px;font-size:22px;">email-sender 自检通过</h1>
    <p style="margin:0;opacity:0.85;font-size:13px;">如果您收到这封邮件，说明发件链路畅通</p>
  </div>
  <div style="padding:24px;color:#333;font-size:14px;line-height:1.7;">
    <p><strong>测试时间：</strong>${new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}</p>
    <p><strong>测试目标：</strong>${to}</p>
    <p><strong>使用技能：</strong>email-sender (零依赖直连 MX)</p>
    <p>这封邮件由 <code>email-sender</code> 技能发送，无 SMTP 账号密码，直连收件方 MX 25 端口。</p>
    <p style="color:#888;font-size:12px;margin-top:24px;">如果这封邮件进入了垃圾箱，请标记"非垃圾邮件"训练 1-2 次，后续会自动进收件箱。</p>
  </div>
</div>
</body></html>`;

  console.log(`📤 正在发送测试邮件到 ${to} ...`);
  try {
    const r = await sendEmail({
      to,
      subject: '✅ email-sender 自检 / Skill Test',
      html,
      fromName: 'email-sender 自检',
    });
    console.log('✅ 成功投递');
    console.log(JSON.stringify(r.results, null, 2));
  } catch (e) {
    console.error('❌ 失败:', e.message);
    process.exit(1);
  }
}

main();
