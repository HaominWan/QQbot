import markdown
import imgkit
import os
import time

async def markdown_to_image(md_text:str)->str:
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
        img = imgkit.from_string(md_html, False)
        os.remove(temp_file)
    except Exception as e:
        os.remove(temp_file)
        print("[Markdown Renderer] Error:", e)
        raise e