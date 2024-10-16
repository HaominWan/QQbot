import markdown
import imgkit
import os
import time
import chardet
import base64

async def markdown_to_image(md_text: str) -> str:
    try:
        temp_file = 'D:/QQbot/Bot/tmp/' + str(time.time()) + '.md'
        if not os.path.exists('D:/QQbot/Bot/tmp'):
            os.makedirs('D:/QQbot/Bot/tmp/')
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(md_text)
    except Exception as e:
        if os.path.exists(temp_file):
            os.remove(temp_file)
        print("[Markdown Renderer] Error:", e)
        raise e

    try:
        md_html = markdown.markdown(md_text, extensions=['extra', 'sane_lists', 'toc', 'tables', 'nl2br', 'attr_list', 'def_list', 'fenced_code', 'footnotes', 'meta', 'smarty', 'wikilinks', 'admonition', 'codehilite', 'legacy_attrs', 'legacy_em', 'md_in_html', 'pymdownx.arithmatex', 'pymdownx.betterem', 'pymdownx.caret', 'pymdownx.critic', 'pymdownx.details', 'pymdownx.inlinehilite', 'pymdownx.keys', 'pymdownx.magiclink', 'pymdownx.mark', 'pymdownx.smartsymbols', 'pymdownx.snippets', 'pymdownx.superfences', 'pymdownx.tasklist', 'pymdownx.tilde'])
        config = imgkit.config(wkhtmltoimage='C:/Program Files/wkhtmltopdf/bin/wkhtmltoimage.exe')
        imgkit.from_string(md_html, temp_file.replace('.md', '.jpg'), config = config)
        with open(temp_file.replace('.md', '.jpg'), 'rb') as img_file:
            img_data = img_file.read()
        img_base64 = base64.b64encode(img_data).decode('utf-8')
        return img_base64
    except Exception as e:
        print("[Markdown Renderer] Error:", e)
        raise e
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)
        if os.path.exists(temp_file.replace('.md', '.jpg')):
            os.remove(temp_file.replace('.md', '.jpg'))

async def handle_markdown_message(message_content):
    md_data = message_content[4:].strip() if message_content.startswith(".md ") else message_content[10:].strip()
    detected_encoding = chardet.detect(md_data.encode())['encoding']
    if detected_encoding is None:
        detected_encoding = 'utf-8'
        
    if detected_encoding != 'utf-8':
        typst_data = typst_data.encode(detected_encoding).decode('utf-8')

    image_base64 = await markdown_to_image(md_data)
    image_cq_code = f"[CQ:image,file=base64://{image_base64},type=show,id=40000]"

    return image_cq_code

__all__ = ['markdown_to_image']