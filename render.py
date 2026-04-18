"""
Render a 296×152 black/white PNG image showing Claude + OpenAI Codex usage.

Renders at 3× resolution (supersampling) then scales down to 1× before
converting to 1-bit, giving smooth crisp text on the e-ink display.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

# Logical canvas size (matches e-ink display)
W, H = 296, 152

# Supersample scale: render at S× then scale down
S = 3

FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD    = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

BLACK = 0
WHITE = 255
LA    = ZoneInfo("America/Los_Angeles")

# Layout constants (logical pixels)
PAD     = 6
LABEL_W = 28
NOTE_W  = 86


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    """Load font at S× the logical size for supersampling."""
    return ImageFont.truetype(path, size * S)


def _lsize(font: ImageFont.FreeTypeFont) -> int:
    """Logical font height (divide supersampled size back down)."""
    return font.size // S


def _lw(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    """Logical text width."""
    return int(draw.textlength(text, font=font)) // S


def _p(v: int | float) -> int:
    """Convert logical coordinate to supersampled canvas coordinate."""
    return int(v * S)


def _bar(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, used_pct: float) -> None:
    """Draw a progress bar at logical coordinates."""
    draw.rectangle([_p(x), _p(y), _p(x + w) - 1, _p(y + h) - 1], outline=BLACK, width=S)
    filled = int((w - 2) * min(used_pct, 100) / 100)
    if filled > 0:
        draw.rectangle([_p(x) + S, _p(y) + S, _p(x) + S + _p(filled) - 1, _p(y + h) - S - 1], fill=BLACK)


def _text(draw: ImageDraw.ImageDraw, pos: tuple[int, int], text: str,
          font: ImageFont.FreeTypeFont) -> None:
    """Draw text at logical coordinates."""
    draw.text((_p(pos[0]), _p(pos[1])), text, font=font, fill=BLACK)


def _hline(draw: ImageDraw.ImageDraw, y: int, x0: int = 0, x1: int = W, width: int = 1) -> None:
    draw.line([(_p(x0), _p(y)), (_p(x1), _p(y))], fill=BLACK, width=width * S)


def _dashed_hline(draw: ImageDraw.ImageDraw, y: int, dash: int = 6, gap: int = 4) -> None:
    x = 0
    while x < W:
        draw.line([(_p(x), _p(y)), (_p(min(x + dash, W)) - 1, _p(y))], fill=BLACK, width=S)
        x += dash + gap


def _draw_row(
    draw: ImageDraw.ImageDraw,
    y: int,
    row_h: int,
    label: str,
    used_pct: float,
    note: Optional[str],
    fonts: dict,
) -> None:
    """Draw one full-width metric row at logical coordinates."""
    lbl_font  = fonts["label"]
    note_font = fonts["note"]

    bar_h = max(10, row_h - 6)
    bar_y = y + (row_h - bar_h) // 2

    lbl_h  = _lsize(lbl_font)
    note_h = _lsize(note_font)

    # Label
    _text(draw, (PAD, bar_y + (bar_h - lbl_h) // 2), label, lbl_font)

    # Right note
    remaining = 100.0 - used_pct
    note_text = f"{remaining:.0f}%"
    if note:
        note_text += f"  {note}"
    note_x = W - PAD - NOTE_W
    _text(draw, (note_x, bar_y + (bar_h - note_h) // 2), note_text, note_font)

    # Bar
    bar_x = PAD + LABEL_W
    bar_w = note_x - 4 - bar_x
    _bar(draw, bar_x, bar_y, bar_w, bar_h, used_pct)


def render_image(
    claude_usage: Optional[dict],
    openai_usage=None,
) -> bytes:
    img  = Image.new("L", (W * S, H * S), WHITE)
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

    _text(draw, (PAD, PAD), "Token Usage", fonts["title"])

    ts_w   = _lw(draw, time_str, fonts["ts"])
    date_w = _lw(draw, date_str, fonts["ts"])
    ts_y   = PAD + (_lsize(fonts["title"]) - _lsize(fonts["ts"])) // 2
    _text(draw, (W - PAD - ts_w, ts_y), time_str, fonts["ts"])
    _text(draw, (W - PAD - ts_w - 6 - date_w, ts_y), date_str, fonts["ts"])

    header_bottom = PAD + _lsize(fonts["title"]) + 4
    _hline(draw, header_bottom)

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

    # ── Layout ────────────────────────────────────────────────────────────
    SECTION_H = _lsize(fonts["section"]) + 5
    DIVIDER_H = 8

    n_claude = len(claude_rows)
    n_openai = len(openai_rows)
    n_rows   = n_claude + n_openai
    has_both = n_claude > 0 and n_openai > 0

    content_h = H - header_bottom - 2
    fixed_h   = ((1 if n_claude else 0) + (1 if n_openai else 0)) * SECTION_H
    fixed_h  += DIVIDER_H if has_both else 0
    row_h     = (content_h - fixed_h) // n_rows if n_rows else content_h

    # ── Claude ────────────────────────────────────────────────────────────
    y = header_bottom + 2
    if claude_rows:
        _text(draw, (PAD, y), "Claude", fonts["section"])
        y += SECTION_H
        for label, used_pct, note in claude_rows:
            _draw_row(draw, y, row_h, label, used_pct, note, fonts)
            y += row_h

    # ── Dashed divider ────────────────────────────────────────────────────
    if has_both:
        y += DIVIDER_H // 2
        _dashed_hline(draw, y)
        y += DIVIDER_H // 2

    # ── OpenAI ────────────────────────────────────────────────────────────
    if openai_rows:
        label = "OpenAI Codex"
        if openai_usage and openai_usage.credits_remaining is not None:
            label += f"  ({openai_usage.credits_remaining:.0f} cr)"
        _text(draw, (PAD, y), label, fonts["section"])
        y += SECTION_H
        for row_label, used_pct, note in openai_rows:
            _draw_row(draw, y, row_h, row_label, used_pct, note, fonts)
            y += row_h

    # ── Scale down and convert to 1-bit ───────────────────────────────────
    img = img.resize((W, H), Image.LANCZOS)
    img = img.convert("1")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
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
