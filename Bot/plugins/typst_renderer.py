import asyncio
import base64
import os
import tempfile
from pathlib import Path

import chardet
import emoji
import typst

_PLUGIN_DIR = Path(__file__).resolve().parent
_BOT_DIR = _PLUGIN_DIR.parent
_TMP_DIR = _BOT_DIR / "tmp"
_FONT_STACK = (
    "Noto Color Emoji",
    "Noto Sans CJK SC",
    "Microsoft YaHei",
    "Microsoft Yahei",
    "PingFang SC",
    "Times New Roman",
)


def render(typst_text: str) -> bytes:
    typst_text = emoji.emojize(typst_text)
    fonts = ", ".join(f'"{font}"' for font in _FONT_STACK)
    typst_text = (
        f"#set text(font:({fonts}))\n"
        + "#set page(width: auto, height: auto, margin: (x: 10pt, y: 10pt))\n"
        + f"#par[{typst_text}]\n"
    )

    _TMP_DIR.mkdir(parents=True, exist_ok=True)
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".typ",
            prefix="typst_",
            dir=_TMP_DIR,
            encoding="utf-8",
            delete=False,
        ) as temp:
            temp.write(typst_text)
            temp_file = temp.name

        image = typst.compile(temp_file, root=str(_BOT_DIR), format="png")
        if isinstance(image, list):
            return b"".join(image)
        return image
    except Exception as exc:
        print("[Typst Renderer] Error:", exc)
        raise
    finally:
        if temp_file and os.path.exists(temp_file):
            os.remove(temp_file)


async def render_async(typst_text: str) -> bytes:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, render, typst_text)


async def handle_typst_message(message_content):
    typst_data = message_content[5:].strip() if message_content.startswith(".typ ") else message_content[7:].strip()
    detected_encoding = chardet.detect(typst_data.encode())["encoding"]

    if detected_encoding is None:
        detected_encoding = "utf-8"

    if detected_encoding != "utf-8":
        typst_data = typst_data.encode(detected_encoding).decode("utf-8")

    image_data = await render_async(typst_data)
    image_base64 = base64.b64encode(image_data).decode("utf-8")
    image_cq_code = f"[CQ:image,file=base64://{image_base64},type=show,id=40000]"

    return image_cq_code


__all__ = ["render", "render_async", "handle_typst_message"]
