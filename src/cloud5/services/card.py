"""Генерация картинки-карточки донатера (случайное оформление).

Если Pillow не установлен — функция вернёт None, и бот опубликует текстовую
карточку. На телефоне ставится так:  pkg install python-pillow
"""

from __future__ import annotations

import io
import random
from pathlib import Path

_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_FONT_BOLD = _FONT_DIR / "DejaVuSans-Bold.ttf"
_FONT_REG = _FONT_DIR / "DejaVuSans.ttf"

# Палитры градиентов (верхний, нижний цвет)
_PALETTES = [
    ((255, 94, 98), (255, 195, 113)),    # закат
    ((131, 58, 180), (253, 29, 29)),     # пурпур-алый
    ((33, 147, 176), (109, 213, 237)),   # океан
    ((255, 0, 132), (96, 9, 240)),       # неон
    ((17, 153, 142), (56, 239, 125)),    # изумруд
    ((255, 175, 189), (255, 195, 160)),  # пастель
    ((44, 62, 80), (76, 161, 175)),      # ночь
    ((238, 9, 121), (255, 106, 0)),      # фуксия-оранж
]


def render_donor_card(name: str, amount: int) -> bytes | None:
    """Нарисовать карточку донатера. Возвращает PNG-байты или None (нет Pillow)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:  # noqa: BLE001 — Pillow не установлен
        return None

    W, H = 1000, 600
    top, bottom = random.choice(_PALETTES)

    # вертикальный градиент
    grad = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / (H - 1)
        grad.putpixel(
            (0, y),
            (
                int(top[0] + (bottom[0] - top[0]) * t),
                int(top[1] + (bottom[1] - top[1]) * t),
                int(top[2] + (bottom[2] - top[2]) * t),
            ),
        )
    img = grad.resize((W, H)).convert("RGBA")
    draw = ImageDraw.Draw(img)

    def font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
        path = _FONT_BOLD if bold else _FONT_REG
        try:
            return ImageFont.truetype(str(path), size)
        except Exception:  # noqa: BLE001
            return ImageFont.load_default()

    # звёздочки-конфетти на фоне
    for _ in range(random.randint(18, 30)):
        x, y = random.randint(0, W), random.randint(0, H)
        s = random.randint(16, 46)
        shade = random.randint(200, 255)
        draw.text(
            (x, y), "★", font=font(s),
            fill=(shade, shade, shade, random.randint(40, 110)),
        )

    # центральная карточка (полупрозрачная тёмная)
    pad = 70
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle(
        [pad, pad, W - pad, H - pad], radius=40, fill=(0, 0, 0, 120)
    )
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    def center(text: str, y: int, f, fill=(255, 255, 255, 255)) -> None:
        box = draw.textbbox((0, 0), text, font=f)
        w = box[2] - box[0]
        draw.text(((W - w) / 2, y), text, font=f, fill=fill)

    gold = (255, 214, 92, 255)
    center("★ СПАСИБО ЗА ПОДДЕРЖКУ ★", 120, font(40), gold)

    # ник — подгоняем размер под ширину
    name = (name or "Аноним").strip()[:32]
    size = 90
    while size > 30:
        f = font(size)
        box = draw.textbbox((0, 0), name, font=f)
        if box[2] - box[0] <= W - 2 * pad - 40:
            break
        size -= 6
    center(name, 250, font(size))

    center(f"поддержал на  {amount} ★", 400, font(46), gold)
    center("Д О С К А   П О Ч Ё Т А", 500, font(30), (230, 230, 230, 230))

    out = io.BytesIO()
    img.convert("RGB").save(out, format="PNG")
    return out.getvalue()
