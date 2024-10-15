import markdown
import imgkit
import os
import time

async def markdown_to_image(md_text: str) -> bytes:
    try:
        temp_file = 'D:/QQbot/Bot/tmp/' + str(time.time()) + '.md'
        if not os.path.exists('D:/QQbot/Bot/tmp'):
            os.makedirs('D:/QQbot/Bot/tmp/')
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(md_text)
    except Exception as e:
        os.remove(temp_file)
        print("[Markdown Renderer] Error:", e)
        raise e

    try:
        md_html = markdown.markdown(md_text)
        config = imgkit.config(wkhtmltoimage='C:/Program Files/wkhtmltopdf/bin/wkhtmltoimage.exe')
        img = imgkit.from_string(md_html, False, config=config)
        os.remove(temp_file)
        return img
    except OSError as e:
        if "No wkhtmltoimage executable found" in str(e):
            print("[Markdown Renderer] wkhtmltoimage 可执行文件未找到，请确保已安装 wkhtmltopdf 并将其路径添加到系统 PATH 中。")
        os.remove(temp_file)
        raise e
    except Exception as e:
        os.remove(temp_file)
        print("[Markdown Renderer] Error:", e)
        raise e