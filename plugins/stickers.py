import base64
import json
import os
import random
from typing import Dict, List, Optional

_BOT_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_STICKER_DIR = os.path.join(_BOT_DIR, 'stickers')
_MANIFEST    = os.path.join(_STICKER_DIR, 'manifest.json')
_SUPPORTED   = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}


def _load_manifest() -> Dict[str, str]:
    if not os.path.isfile(_MANIFEST):
        return {}
    with open(_MANIFEST, 'r', encoding='utf-8') as f:
        return json.load(f)


def _scan() -> Dict[str, List[str]]:
    """Return {emotion: [filepath, …]} by stripping trailing digits from filenames."""
    result: Dict[str, List[str]] = {}
    if not os.path.isdir(_STICKER_DIR):
        return result
    for fname in sorted(os.listdir(_STICKER_DIR)):
        name, ext = os.path.splitext(fname)
        if ext.lower() not in _SUPPORTED:
            continue
        # strip trailing digits: "shy0", "shy12" → "shy"
        emotion = name.rstrip('0123456789') or name
        result.setdefault(emotion, []).append(os.path.join(_STICKER_DIR, fname))
    return result


def get_available_stickers() -> Dict[str, str]:
    """Return {emotion: description} for emotions that have both images and a manifest entry."""
    manifest = _load_manifest()
    return {e: manifest[e] for e in _scan() if e in manifest}


def sticker_to_segment(name: str) -> Optional[dict]:
    """Return a OneBot image segment for a randomly chosen image of the named emotion."""
    pool = _scan().get(name)
    if not pool:
        return None
    path = random.choice(pool)
    with open(path, 'rb') as f:
        data = base64.b64encode(f.read()).decode('utf-8')
    return {"type": "image", "data": {"file": f"base64://{data}"}}


__all__ = ['get_available_stickers', 'sticker_to_segment']
