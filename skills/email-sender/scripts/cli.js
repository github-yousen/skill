#!/usr/bin/env node
/**
 * email-sender CLI
 *
 * Usage:
 *   node cli.js --to <email> --subject <subj> --html "<h1>..</h1>"
 *   node cli.js --to <email> --subject <subj> --html-file /path/to/x.html
 *   node cli.js --to <email> --subject <subj> --text "纯文本"
 *
 * 全部参数：
 *   --to <email>          收件人（必填，可多次指定）
 *   --cc <email>          抄送（可多次）
 *   --bcc <email>         密送（可多次）
 *   --subject <text>      主题（必填）
 *   --html <html>         HTML 内容
 *   --html-file <path>    从文件读 HTML
 *   --text <text>         纯文本
 *   --text-file <path>    从文件读纯文本
 *   --from <email>        发件人（默认 mailer@newsbot.com）
 *   --from-name <name>    发件人显示名
 *   --reply-to <email>    回复地址
 *   --attach <path>       附件（可多次）
 *   --verbose             打印 SMTP 会话
 *   --help                帮助
 */

const fs = require('fs');
const { sendEmail } = require('./sender.js');

function parseArgs(argv) {
  const args = { to: [], cc: [], bcc: [], attach: [] };
  for (let i = 2; i < argv.length; i++) {
    const k = argv[i];
    const v = argv[i + 1];
    switch (k) {
      case '--to': args.to.push(v); i++; break;
      case '--cc': args.cc.push(v); i++; break;
      case '--bcc': args.bcc.push(v); i++; break;
      case '--subject': args.subject = v; i++; break;
      case '--html': args.html = v; i++; break;
      case '--html-file': args.htmlFile = v; i++; break;
      case '--text': args.text = v; i++; break;
      case '--text-file': args.textFile = v; i++; break;
      case '--from': args.from = v; i++; break;
      case '--from-name': args.fromName = v; i++; break;
      case '--reply-to': args.replyTo = v; i++; break;
      case '--attach': args.attach.push(v); i++; break;
      case '--verbose': args.verbose = true; break;
      case '--help':
      case '-h':
        printHelpAndExit();
    }
  }
  return args;
}

function printHelpAndExit() {
  const help = fs.readFileSync(__filename, 'utf-8')
    .split('\n')
    .filter((l) => l.startsWith(' *') || l.startsWith('/**') || l.startsWith(' */'))
    .map((l) => l.replace(/^ \* ?/, '').replace('/**', '').replace(' */', ''))
    .join('\n')
    .trim();
  console.log(help);
  process.exit(0);
}

(async () => {
  const args = parseArgs(process.argv);
  if (!args.to.length || !args.subject) {
    console.error('❌ --to 和 --subject 是必填项，使用 --help 查看用法');
    process.exit(1);
  }

  let html = args.html;
  if (args.htmlFile) html = fs.readFileSync(args.htmlFile, 'utf-8');
  let text = args.text;
  if (args.textFile) text = fs.readFileSync(args.textFile, 'utf-8');

  const attachments = args.attach.map((p) => ({ path: p }));

  try {
    const r = await sendEmail({
      to: args.to.length === 1 ? args.to[0] : args.to,
      cc: args.cc.length ? args.cc : undefined,
      bcc: args.bcc.length ? args.bcc : undefined,
      subject: args.subject,
      html, text,
      from: args.from,
      fromName: args.fromName,
      replyTo: args.replyTo,
      attachments: attachments.length ? attachments : undefined,
      verbose: args.verbose,
    });
    console.log('✅ 发送成功:', JSON.stringify(r.results, null, 2));
  } catch (e) {
    console.error('❌ 发送失败:', e.message);
    process.exit(1);
  }
})();
