const puppeteer = require('puppeteer');
const MarkdownIt = require('markdown-it');
// const emoji = require('markdown-it-emoji').default;

const md = new MarkdownIt();
// md.use(emoji);

async function renderMarkdownToImage(markdownText, outputPath) {
    const browser = await puppeteer.launch();
    const page = await browser.newPage();

    const htmlContent = `
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Markdown Renderer</title>
            <style>
                body { font-family: 'Arial', sans-serif; padding: 20px; }
                img { max-width: 100%; }
            </style>
        </head>
        <body>
            <div id="content">${md.render(markdownText)}</div>
        </body>
        </html>
    `;

    await page.setContent(htmlContent);
    await page.screenshot({ path: outputPath });

    await browser.close();
}

const markdownText = process.argv[2];
const outputPath = process.argv[3];

renderMarkdownToImage(markdownText, outputPath).catch(console.error);