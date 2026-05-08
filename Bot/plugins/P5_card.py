import asyncio
import base64
import hashlib
import os
import random
import tempfile
from pathlib import Path

import typst


_PLUGIN_DIR = Path(__file__).resolve().parent
_BOT_DIR = _PLUGIN_DIR.parent
_SRC_DIR = _PLUGIN_DIR / "src"
_TMP_DIR = _BOT_DIR / "tmp"
_BASE_PATH = _SRC_DIR / "base.png"
_LOGO_PATH = _SRC_DIR / "logo.png"
_CANVAS_PATH = _SRC_DIR / "canvas.png"
_WIDTH = 2200
_HEIGHT = 1672
_BASE_X = 134
_BASE_Y = 138
_BASE_WIDTH = 1932
_BASE_HEIGHT = 1420
_BASE_CENTER_X = _BASE_X + _BASE_WIDTH / 2
_BASE_CENTER_Y = _BASE_Y + _BASE_HEIGHT / 2
_P5_REFERENCE_WIDTH = 1770
_P5_REFERENCE_HEIGHT = 1300
_P5_SCALE = _BASE_WIDTH / _P5_REFERENCE_WIDTH
_P5_PADDING = 30 * _P5_SCALE
_P5_GUTTER = 5 * _P5_SCALE
_P5_LINE_PULLUP = 40 * _P5_SCALE
_LOGO_WIDTH = 250
_RED = "#e5191c"
_WHITE = "#fdfdfd"
_PAPER = "#0f0f0f"
_FONT_STACK = (
    "Microsoft YaHei",
    "SimHei",
    "Noto Sans CJK SC",
    "Yu Gothic",
    "Meiryo",
    "Noto Sans CJK JP",
    "Arial",
)
_PUNCTUATION = set(".,!?[]()<>:;") | {chr(code) for code in (
    0x3001, 0x3002, 0xff0c, 0xff01, 0xff1f, 0x2026, 0x30fb, 0xff65,
    0x300e, 0x300f, 0x300c, 0x300d, 0xff08, 0xff09, 0x3010, 0x3011,
    0x300a, 0x300b, 0xff1a, 0xff1b,
)}
_MODE_FIRST = "first"
_MODE_WHITE = "white"
_MODE_RED = "red"
_LINE_PATTERNS = {
    2: (0.78, 1.22),
    3: (1.16, 0.78, 1.16),
    4: (1.16, 0.78, 1.16, 0.78),
}


def _typst_string(text: str) -> str:
    escaped = (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "")
    )
    return f'"{escaped}"'


def _font_expr() -> str:
    return "(" + ", ".join(_typst_string(font) for font in _FONT_STACK) + ")"


def _visual_width(char: str) -> float:
    if char.isspace():
        return 0.45
    if char.isascii():
        return 0.65 if char not in _PUNCTUATION else 0.45
    return 1.0


def _tile_width(char: str, size: int) -> int:
    if char in _PUNCTUATION:
        return max(22, round(size * 0.72))
    if char.isascii():
        return max(28, round(size * 0.86))
    return max(36, round(size * 1.08))


def _wrap_paragraph(text: str, limit: float) -> list[str]:
    chars = [char for char in text if char != "\n"]
    if not chars:
        return []

    total_width = sum(_visual_width(char) for char in chars)
    line_count = max(1, round(total_width / limit))
    line_count = min(4, line_count, len(chars))
    weights = _LINE_PATTERNS.get(
        line_count,
        tuple(1.14 if index % 2 == 0 else 0.82 for index in range(line_count)),
    )
    target_widths = [total_width * weight / sum(weights) for weight in weights]

    lines: list[str] = []
    start = 0
    width = 0.0
    for index, char in enumerate(chars):
        width += _visual_width(char)
        remaining_chars = len(chars) - index - 1
        remaining_lines = line_count - len(lines) - 1
        if remaining_lines <= 0:
            continue
        if remaining_chars < remaining_lines:
            continue

        next_char = chars[index + 1] if index + 1 < len(chars) else ""
        target = target_widths[len(lines)]
        should_break = width >= target or width + _visual_width(next_char) * 0.6 >= target
        if should_break and next_char not in _PUNCTUATION:
            line = "".join(chars[start:index + 1]).strip()
            if line:
                lines.append(line)
            start = index + 1
            width = 0.0

    tail = "".join(chars[start:]).strip()
    if tail:
        lines.append(tail)
    return lines


def _wrap_message(message: str) -> list[str]:
    message = " ".join(message.strip().split()) if "\n" not in message else message.strip()
    if not message:
        message = "\u4e88\u544a\u72b6\u3002\u5fc3\u306e\u602a\u76d7\u56e3\u3088\u308a\u3002"

    lines: list[str] = []
    for paragraph in message.splitlines():
        paragraph = paragraph.strip()
        if paragraph:
            lines.extend(_wrap_paragraph(paragraph, 9))

    if len(lines) > 9:
        compact = "".join(lines)
        lines = _wrap_paragraph(compact, max(9, min(13, len(compact) / 7)))
    return lines[:10]


def _line_modes(line: str, rng: random.Random) -> list[str]:
    modes = [_MODE_WHITE for _ in line]
    for index, char in enumerate(line):
        if char.isspace():
            continue
        modes[index] = _MODE_FIRST
        break

    for start in range(1, len(line), 5):
        for index in range(start, min(start + 4, len(line))):
            if line[index].isspace():
                continue
            if rng.random() > 0.6:
                modes[index] = _MODE_RED
                break
    return modes


def _place(body: str, x: float, y: float) -> str:
    return f"#place(top + left, dx: {x:.1f}pt, dy: {y:.1f}pt, {body})"


def _asset_path(path: Path) -> str:
    return Path(os.path.relpath(path, _TMP_DIR)).as_posix()


def _image(path: Path, width: float, height: float | None = None) -> str:
    height_part = "" if height is None else f", height: {height:.1f}pt"
    return f'image({_typst_string(_asset_path(path))}, width: {width:.1f}pt{height_part})'


def _tile_plan(char: str, rng: random.Random, size: int, mode: str) -> dict[str, float | int]:
    char_scale = 1.36 if mode == _MODE_FIRST else rng.choice((1.12, 1.0, 0.92))
    char_size = round(size * char_scale)
    width = round(_tile_width(char, char_size) * rng.uniform(1.16, 1.34))
    height = round(char_size * rng.uniform(1.28, 1.5))
    rotation = -rng.randrange(0, 10)
    if mode != _MODE_FIRST and rng.randrange(0, 2):
        rotation *= -1
    stroke = max(6, round(size * 0.07))
    font_size = round(char_size * (0.9 if char.isascii() else 0.98))
    if mode == _MODE_FIRST:
        width = round(width * 1.34)
        height = round(height * 1.32)
    return {
        "width": width,
        "height": height,
        "rotation": rotation,
        "stroke": stroke,
        "font_size": font_size,
        "x_jitter": rng.uniform(-4, 4),
        "y_jitter": rng.uniform(-11, 11),
    }


def _tile(char: str, x: float, y: float, plan: dict[str, float | int], mode: str) -> tuple[str, float]:
    width = int(plan["width"])
    height = int(plan["height"])
    rotation = float(plan["rotation"])
    stroke = int(plan["stroke"])
    font_size = int(plan["font_size"])
    x += float(plan["x_jitter"])
    y += float(plan["y_jitter"])

    if mode == _MODE_FIRST:
        outer_width = width
        outer_height = height
        inner_width = round(outer_width * 0.84)
        inner_height = round(outer_height * 0.84)
        cx = x + outer_width / 2
        cy = y + outer_height / 2
        text_x = x + outer_width * 0.15
        text_y = y + outer_height * 0.1
        parts = [
            _place(
                f'rotate({rotation - 5:.2f}deg, box(width: {outer_width}pt, height: {outer_height}pt, '
                f'fill: rgb("{_PAPER}"), stroke: {stroke}pt + white))',
                x,
                y,
            ),
            _place(
                f'rotate({rotation + 3:.2f}deg, box(width: {inner_width}pt, height: {inner_height}pt, '
                f'fill: rgb("{_RED}")))',
                cx - inner_width / 2,
                cy - inner_height / 2,
            ),
            _place(
                f'rotate({rotation + 5:.2f}deg, text(font: {_font_expr()}, size: {font_size}pt, '
                f'weight: "bold", fill: rgb("{_WHITE}"), {_typst_string(char)}))',
                text_x,
                text_y,
            ),
        ]
        return "\n".join(parts), outer_width

    text_fill = _RED if mode == _MODE_RED else _WHITE
    body = (
        f'rotate({rotation + 1:.2f}deg, '
        f'box(width: {width}pt, height: {height}pt, '
        f'fill: rgb("{_PAPER}"), stroke: {stroke}pt + white, inset: 0pt, '
        f'align(center + horizon, '
        f'rotate(-1deg, text(font: {_font_expr()}, size: {font_size}pt, weight: "bold", '
        f'fill: rgb("{text_fill}"), {_typst_string(char)})))))'
    )
    return _place(body, x, y), width


def _text_blocks(message: str) -> list[str]:
    seed = int(hashlib.sha1(message.encode("utf-8", errors="ignore")).hexdigest()[:16], 16)
    rng = random.Random(seed)
    lines = _wrap_message(message)
    count = len(lines)
    if count <= 4:
        size = 82
    elif count <= 6:
        size = 76
    else:
        size = 68 if count <= 8 else 60

    parts: list[str] = []
    max_width = _BASE_WIDTH - _P5_PADDING * 2
    planned_lines = []
    for line in lines:
        line_size = round(size * rng.uniform(0.97, 1.05))
        modes = _line_modes(line, rng)

        while True:
            entries = []
            line_width = _P5_PADDING * 2
            line_height = 0.0
            for index, char in enumerate(line):
                if char.isspace():
                    entries.append((index, char, None))
                    line_width += _P5_GUTTER * 2
                    continue

                plan = _tile_plan(char, rng, line_size, modes[index])
                entries.append((index, char, plan))
                line_width += float(plan["width"]) + _P5_GUTTER
                line_height = max(line_height, float(plan["height"]))

            line_height += _P5_PADDING * 2
            if line_width <= max_width or line_size <= 48:
                break
            line_size -= 3

        planned_lines.append((entries, modes, line_width, line_height, line_size))

    middle_offset = ((_BASE_HEIGHT - size * count) / 2.5) - (size / 5 * count)
    cursor_y = 0.0
    line_positions = []
    for entries, modes, line_width, line_height, line_size in planned_lines:
        y = _BASE_Y + middle_offset + cursor_y
        line_positions.append((entries, modes, line_width, line_height, y))
        cursor_y += max(0, line_height - _P5_LINE_PULLUP)

    if line_positions:
        top = min(y for *_, y in line_positions)
        bottom = max(y + line_height for _, _, _, line_height, y in line_positions)
        y_shift = _BASE_CENTER_Y - (top + bottom) / 2
    else:
        y_shift = 0.0

    for entries, modes, line_width, line_height, line_y in line_positions:
        x = _BASE_X + (_BASE_WIDTH - line_width) / 2 + _P5_PADDING
        y_base = line_y + y_shift

        for index, char, plan in entries:
            if plan is None:
                x += _P5_GUTTER * 2
                continue

            tile_y = y_base + (line_height - float(plan["height"])) / 2
            tile, width = _tile(char, x, tile_y, plan, modes[index])
            parts.append(tile)
            x += width + _P5_GUTTER

    return parts


def _background() -> str:
    return _place(_image(_CANVAS_PATH, _WIDTH, _HEIGHT), 0, 0) + "\n" + _place(_image(_BASE_PATH, _BASE_WIDTH, _BASE_HEIGHT), _BASE_X, _BASE_Y)


def _logo() -> str:
    return _place(_image(_LOGO_PATH, _LOGO_WIDTH), _BASE_X + _BASE_WIDTH - _LOGO_WIDTH - 34, _BASE_Y + _BASE_HEIGHT - 285)


def _build_typst(message: str) -> str:
    parts = [
        f"#set page(width: {_WIDTH}pt, height: {_HEIGHT}pt, margin: 0pt, fill: black)",
        "#set text(kerning: false)",
        _background(),
        *_text_blocks(message),
        _logo(),
    ]
    return "\n".join(parts) + "\n"


def render_card(message: str) -> bytes:
    _TMP_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".typ",
        prefix="p5_",
        dir=_TMP_DIR,
        encoding="utf-8",
        delete=False,
    ) as temp:
        temp.write(_build_typst(message))
        temp_path = temp.name

    try:
        image = typst.compile(temp_path, root=str(_BOT_DIR), font_paths=[str(_SRC_DIR)], format="png")
        if isinstance(image, list):
            return b"".join(image)
        return image
    finally:
        try:
            os.remove(temp_path)
        except FileNotFoundError:
            pass


async def get_card(message: str) -> str:
    loop = asyncio.get_event_loop()
    image = await loop.run_in_executor(None, render_card, message)
    image_base64 = base64.b64encode(image).decode("utf-8")
    return f"[CQ:image,file=base64://{image_base64},type=show,id=40000]"


__all__ = ["get_card", "render_card"]
