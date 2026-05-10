import asyncio
import glob
import os
import re
from pathlib import Path

import jmcomic
from PIL import Image

_PLUGIN_DIR = Path(__file__).resolve().parent
_BOT_DIR = _PLUGIN_DIR.parent
_TMP_DIR = _BOT_DIR / "tmp"


def _natural_key(path):
    parts = re.split(r"(\d+)", os.path.normpath(path).replace(os.sep, "/"))
    return [int(part) if part.isdigit() else part.lower() for part in parts]


async def get_pdf(code):
    temp_dir = _TMP_DIR / str(code)
    pdf_name = temp_dir / f"{code}.pdf"
    temp_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Downloading JM album {code}...")

    option_path = _PLUGIN_DIR / "option.yml"
    os.environ["JM_DIR"] = str(_BOT_DIR)
    option = jmcomic.create_option_by_file(str(option_path))

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, jmcomic.download_album, code, option)
    except Exception as exc:
        print(f"[ERROR] Download failed: {exc}")
        import traceback

        traceback.print_exc()
        return 0

    image_files = sorted(
        glob.glob(str(temp_dir / "**" / "*.jpg"), recursive=True)
        + glob.glob(str(temp_dir / "**" / "*.png"), recursive=True),
        key=_natural_key,
    )

    if not image_files:
        print(f"[ERROR] No downloaded images found under {temp_dir}")
        return 0

    print(f"[INFO] Found {len(image_files)} images, building PDF...")

    images = []
    for img_path in image_files:
        try:
            img = Image.open(img_path)
            if img.mode != "RGB":
                img = img.convert("RGB")
            images.append(img)
        except Exception as exc:
            print(f"[WARN] Skipping {img_path}: {exc}")

    if not images:
        print("[ERROR] No valid images available for PDF generation")
        return 0

    images[0].save(str(pdf_name), save_all=True, append_images=images[1:])
    for img in images:
        img.close()

    print(f"[SUCCESS] PDF generated: {pdf_name}")
    return str(pdf_name)
