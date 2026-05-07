const puppeteer = require('puppeteer');
const MarkdownIt = require('markdown-it');
const texmath   = require('markdown-it-texmath');
const katex     = require('katex');
const fs        = require('fs');
const path      = require('path');

const KATEX_CSS = path.join(
    path.dirname(require.resolve('katex/dist/katex.min.css')),
    'katex.min.css'
);

// Support $…$, $$…$$ (preferred) and \(…\), \[…\] (fallback for AI output)
const md = new MarkdownIt({ html: false, linkify: true, typographer: true })
    .use(texmath, {
        engine: katex,
        delimiters: texmath.mergeDelimiters(['dollars', 'brackets']),
        katexOptions: { throwOnError: false, output: 'html' },
    });

async function renderMarkdownToImage(mdFilePath, outputPath) {
    const markdownText = fs.readFileSync(mdFilePath, 'utf-8');
    const katexCss     = fs.readFileSync(KATEX_CSS, 'utf-8');

    const browser = await puppeteer.launch({ args: ['--no-sandbox', '--disable-setuid-sandbox'] });
    const page    = await browser.newPage();
    await page.setViewport({ width: 800, height: 600 });

    // Resolve katex font URLs to absolute file:// paths so they load offline
    const katexDistDir = path.dirname(KATEX_CSS).replace(/\\/g, '/');
    const katexCssAbsolute = katexCss.replace(
        /url\(fonts\//g,
        `url(file:///${katexDistDir}/fonts/`
    );

    const htmlContent = `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
${katexCssAbsolute}
</style>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #ffffff; }
#content {
    font-family: 'Microsoft YaHei', 'PingFang SC', 'Segoe UI', Arial, sans-serif;
    font-size: 15px;
    line-height: 1.65;
    color: #24292e;
    padding: 20px 24px;
    max-width: 720px;
    word-break: break-word;
}
h1, h2, h3, h4, h5, h6 { margin: 16px 0 8px; font-weight: 600; line-height: 1.25; }
h1 { font-size: 1.75em; border-bottom: 1px solid #eaecef; padding-bottom: 8px; }
h2 { font-size: 1.4em;  border-bottom: 1px solid #eaecef; padding-bottom: 6px; }
h3 { font-size: 1.2em; }
p  { margin: 8px 0; }
pre {
    background: #f6f8fa;
    border: 1px solid #e1e4e8;
    border-radius: 6px;
    padding: 14px 16px;
    overflow-x: auto;
    margin: 12px 0;
    font-size: 0.88em;
}
code { font-family: 'Consolas', 'SFMono-Regular', 'Courier New', monospace; }
pre code { background: none; padding: 0; border-radius: 0; }
code:not(pre code) {
    background: rgba(175,184,193,0.2);
    padding: 2px 5px;
    border-radius: 4px;
    font-size: 0.9em;
}
ul, ol { margin: 8px 0; padding-left: 24px; }
li { margin: 4px 0; }
li > ul, li > ol { margin: 2px 0; }
blockquote {
    border-left: 4px solid #dfe2e5;
    color: #6a737d;
    padding: 4px 16px;
    margin: 10px 0;
}
table { border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 0.93em; }
th, td { border: 1px solid #dfe2e5; padding: 8px 12px; text-align: left; }
th { background: #f6f8fa; font-weight: 600; }
tr:nth-child(even) td { background: #fafbfc; }
hr { border: none; border-top: 2px solid #eaecef; margin: 16px 0; }
a { color: #0366d6; text-decoration: none; }
strong { font-weight: 600; }
em { font-style: italic; }
/* KaTeX display blocks */
.katex-display { margin: 12px 0; overflow-x: auto; }
.katex { font-size: 1.1em; }
</style>
</head>
<body>
<div id="content">${md.render(markdownText)}</div>
</body>
</html>`;

    await page.setContent(htmlContent, { waitUntil: 'networkidle0' });

    const element = await page.$('#content');
    if (!element) throw new Error('#content element not found');
    await element.screenshot({ path: outputPath });

    await browser.close();
}

const mdFilePath = process.argv[2];
const outputPath  = process.argv[3];

if (!mdFilePath || !outputPath) {
    console.error('Usage: node renderMarkdown.js <md-file> <output-png>');
    process.exit(1);
}

renderMarkdownToImage(mdFilePath, outputPath).catch(err => {
    console.error(err);
    process.exit(1);
});
