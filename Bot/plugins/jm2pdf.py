import asyncio
import glob
import os
import re

import jmcomic
from PIL import Image


def _natural_key(path):
    parts = re.split(r'(\d+)', os.path.normpath(path).replace(os.sep, '/'))
    return [int(p) if p.isdigit() else p.lower() for p in parts]


async def get_pdf(code):
    temp_dir = f"Bot/tmp/{code}"
    pdf_name = f"Bot/tmp/{code}/{code}.pdf"
    os.makedirs(temp_dir, exist_ok=True)

    print(f"[INFO] 正在下载本子 {code}...")

    option_path = os.path.join(os.path.dirname(__file__), "option.yml")
    option = jmcomic.create_option_by_file(option_path)

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, jmcomic.download_album, code, option)
    except Exception as e:
        print(f"[ERROR] 下载失败: {e}")
        import traceback
        traceback.print_exc()
        return 0

    image_files = sorted(
        glob.glob(f"{temp_dir}/**/*.jpg", recursive=True)
        + glob.glob(f"{temp_dir}/**/*.png", recursive=True),
        key=_natural_key,
    )

    if not image_files:
        print(f"[ERROR] 没有找到下载的图片: {temp_dir}")
        return 0

    print(f"[INFO] 找到 {len(image_files)} 张图片，正在生成PDF...")

    images = []
    for img_path in image_files:
        try:
            img = Image.open(img_path)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            images.append(img)
        except Exception as e:
            print(f"[WARN] 跳过文件 {img_path}: {e}")

    if not images:
        print(f"[ERROR] 没有有效图片可生成PDF")
        return 0

    images[0].save(pdf_name, save_all=True, append_images=images[1:])
    for img in images:
        img.close()

    print(f"[SUCCESS] PDF生成完成: {pdf_name}")
    return pdf_name
