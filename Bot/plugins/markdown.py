import asyncio
import base64
import os
import time

_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
_BOT_DIR    = os.path.dirname(_PLUGIN_DIR)
_TMP_DIR    = os.path.join(_BOT_DIR, 'tmp')
_RENDERER   = os.path.join(_PLUGIN_DIR, 'renderMarkdown.js')


async def markdown_to_image(md_text: str) -> str:
    """Render *md_text* to a PNG and return it as a base64 string."""
    os.makedirs(_TMP_DIR, exist_ok=True)
    ts      = str(time.time())
    md_file = os.path.join(_TMP_DIR, ts + '.md')
    out_file = os.path.join(_TMP_DIR, ts + '.png')

    try:
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(md_text)

        proc = await asyncio.create_subprocess_exec(
            'node', _RENDERER, md_file, out_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"renderMarkdown.js failed: {stderr.decode(errors='replace')}")

        with open(out_file, 'rb') as f:
            img_data = f.read()
        return base64.b64encode(img_data).decode('utf-8')

    finally:
        for path in (md_file, out_file):
            try:
                os.remove(path)
            except OSError:
                pass


async def handle_markdown_message(message_content: str) -> str:
    """Called by the .md command handler; returns a CQ image code."""
    if message_content.startswith('.markdown'):
        md_text = message_content[9:].strip()
    elif message_content.startswith('.md'):
        md_text = message_content[3:].strip()
    else:
        md_text = message_content.strip()

    try:
        image_b64 = await markdown_to_image(md_text)
        return f"[CQ:image,file=base64://{image_b64}]"
    except Exception as e:
        print(f"[Markdown] render failed: {e}")
        return f"Markdown 渲染失败：{e}"


__all__ = ['markdown_to_image', 'handle_markdown_message']
