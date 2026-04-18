"""
Render a 296×152 black/white PNG image showing Claude + OpenAI Codex usage.
Layout fills the full screen height, distributing space evenly across rows.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

W, H = 296, 152
PAD = 6

FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD    = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

BLACK = 0
WHITE = 255

LA = ZoneInfo("America/Los_Angeles")

LABEL_W  = 28   # fixed px reserved for row label ("5h", "7d", "Wk")
NOTE_W   = 82   # fixed px reserved for right-side text ("79% · 3h26m")


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _text_w(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    return int(draw.textlength(text, font=font))


def _draw_bar(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, used_pct: float) -> None:
    draw.rectangle([x, y, x + w - 1, y + h - 1], outline=BLACK, width=1)
    filled = int((w - 2) * min(used_pct, 100) / 100)
    if filled > 0:
        draw.rectangle([x + 1, y + 1, x + filled, y + h - 2], fill=BLACK)


def _draw_row(
    draw: ImageDraw.ImageDraw,
    y: int,
    row_h: int,
    label: str,
    used_pct: float,
    note: Optional[str],
    fonts: dict,
) -> None:
    """Draw one full-width metric row centered vertically within row_h."""
    bar_h = max(10, row_h - 8)
    bar_y = y + (row_h - bar_h) // 2

    # Label — vertically centered
    lbl_font = fonts["label"]
    lbl_h = lbl_font.size
    draw.text((PAD, bar_y + (bar_h - lbl_h) // 2), label, font=lbl_font, fill=BLACK)

    # Right-side note text — vertically centered
    note_font = fonts["note"]
    remaining = 100.0 - used_pct
    note_text = f"{remaining:.0f}%"
    if note:
        note_text += f"  {note}"
    note_h = note_font.size
    draw.text(
        (W - PAD - NOTE_W, bar_y + (bar_h - note_h) // 2),
        note_text,
        font=note_font,
        fill=BLACK,
    )

    # Bar between label and note
    bar_x = PAD + LABEL_W
    bar_w = W - PAD - NOTE_W - 4 - bar_x
    _draw_bar(draw, bar_x, bar_y, bar_w, bar_h, used_pct)


def render_image(
    claude_usage: Optional[dict],
    openai_usage=None,
) -> bytes:
    img = Image.new("L", (W, H), WHITE)
    draw = ImageDraw.Draw(img)

    fonts = {
        "title":   _font(FONT_BOLD,    12),
        "ts":      _font(FONT_REGULAR, 10),
        "section": _font(FONT_BOLD,    11),
        "label":   _font(FONT_BOLD,    11),
        "note":    _font(FONT_REGULAR, 10),
    }

    # ── Header ────────────────────────────────────────────────────────────
    now      = datetime.now(LA)
    date_str = now.strftime("%b %-d")
    time_str = now.strftime("%-I:%M %p")

    draw.text((PAD, PAD), "Token Usage", font=fonts["title"], fill=BLACK)

    ts_w   = _text_w(draw, time_str, fonts["ts"])
    date_w = _text_w(draw, date_str, fonts["ts"])
    ts_y   = PAD + (fonts["title"].size - fonts["ts"].size) // 2
    draw.text((W - PAD - ts_w,            ts_y), time_str, font=fonts["ts"], fill=BLACK)
    draw.text((W - PAD - ts_w - 6 - date_w, ts_y), date_str, font=fonts["ts"], fill=BLACK)

    header_bottom = PAD + fonts["title"].size + 4
    draw.line([(0, header_bottom), (W, header_bottom)], fill=BLACK, width=1)

    # ── Collect rows ──────────────────────────────────────────────────────
    from display import format_time_until, format_time_until_iso

    claude_rows: list[tuple[str, float, Optional[str]]] = []
    if claude_usage:
        for key, lbl in [("five_hour", "5h"), ("seven_day", "7d"),
                          ("seven_day_sonnet", "7dS"), ("seven_day_opus", "7dO")]:
            w = claude_usage.get(key)
            if w:
                try:
                    note = format_time_until_iso(w["resets_at"])
                except Exception:
                    note = None
                claude_rows.append((lbl, w["utilization"], note))

    openai_rows: list[tuple[str, float, Optional[str]]] = []
    if openai_usage:
        if openai_usage.primary_limit:
            w = openai_usage.primary_limit
            openai_rows.append(("5h", w.used_percent,
                                 format_time_until(w.resets_at) if w.resets_at else None))
        if openai_usage.secondary_limit:
            w = openai_usage.secondary_limit
            openai_rows.append(("Wk", w.used_percent,
                                 format_time_until(w.resets_at) if w.resets_at else None))

    # ── Layout calculation ─────────────────────────────────────────────────
    # Fixed heights
    SECTION_H  = fonts["section"].size + 5   # section label row
    DIVIDER_H  = 8                            # dashed line + gaps
    SOLID_H    = 1

    n_claude  = len(claude_rows)
    n_openai  = len(openai_rows)
    n_sections = (1 if n_claude else 0) + (1 if n_openai else 0)
    n_rows    = n_claude + n_openai
    has_both  = n_claude > 0 and n_openai > 0

    content_h = H - header_bottom - SOLID_H - 1
    fixed_h   = n_sections * SECTION_H + (DIVIDER_H if has_both else 0)
    row_h     = (content_h - fixed_h) // n_rows if n_rows else content_h

    # ── Draw Claude ───────────────────────────────────────────────────────
    y = header_bottom + 2
    if claude_rows:
        draw.text((PAD, y), "Claude", font=fonts["section"], fill=BLACK)
        y += SECTION_H
        for label, used_pct, note in claude_rows:
            _draw_row(draw, y, row_h, label, used_pct, note, fonts)
            y += row_h

    # ── Dashed divider ────────────────────────────────────────────────────
    if has_both:
        y += (DIVIDER_H - 1) // 2
        dash, gap, x = 6, 4, 0
        while x < W:
            draw.line([(x, y), (min(x + dash - 1, W), y)], fill=BLACK, width=1)
            x += dash + gap
        y += (DIVIDER_H - 1) // 2 + 1

    # ── Draw OpenAI ───────────────────────────────────────────────────────
    if openai_rows:
        label = "OpenAI Codex"
        if openai_usage and openai_usage.credits_remaining is not None:
            label += f"  ({openai_usage.credits_remaining:.0f} cr)"
        draw.text((PAD, y), label, font=fonts["section"], fill=BLACK)
        y += SECTION_H
        for row_label, used_pct, note in openai_rows:
            _draw_row(draw, y, row_h, row_label, used_pct, note, fonts)
            y += row_h

    buf = io.BytesIO()
    img.convert("1").save(buf, format="PNG")
    return buf.getvalue()


if __name__ == "__main__":
    from usage import get_claude_usage, get_openai_usage

    claude, openai = None, None
    try:
        claude = get_claude_usage()
    except Exception as e:
        print(f"Claude error: {e}")
    try:
        openai = get_openai_usage()
    except Exception as e:
        print(f"OpenAI error: {e}")

    png = render_image(claude, openai)
    with open("/tmp/usage_preview.png", "wb") as f:
        f.write(png)
    print(f"Saved /tmp/usage_preview.png ({len(png)} bytes)")
