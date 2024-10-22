import os
import time
import base64
import subprocess
import chardet

async def markdown_to_image(md_text: str) -> str:
    temp_file = 'D:/QQbot/Bot/tmp/' + str(time.time()) + '.md'
    output_image = temp_file.replace('.md', '.png')

    try:
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(md_text)

        subprocess.run(['node', 'Bot/plugins/renderMarkdown.js', md_text, output_image], check=True)

        with open(output_image, 'rb') as img_file:
            img_data = img_file.read()
        img_base64 = base64.b64encode(img_data).decode('utf-8')
        return img_base64

    except Exception as e:
        print("[Markdown Renderer] Error:", e)
        raise e
    
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)
        if os.path.exists(output_image):
            os.remove(output_image)

async def handle_markdown_message(message_content):
    md_data = message_content[4:].strip() if message_content.startswith(".md ") else message_content[10:].strip()
    detected_encoding = chardet.detect(md_data.encode())['encoding']
    if detected_encoding is None:
        detected_encoding = 'utf-8'
        
    if detected_encoding != 'utf-8':
        md_data = md_data.encode(detected_encoding).decode('utf-8')

    image_base64 = await markdown_to_image(md_data)
    image_cq_code = f"[CQ:image,file=base64://{image_base64},type=show,id=40000]"

    return image_cq_code

__all__ = ['markdown_to_image']