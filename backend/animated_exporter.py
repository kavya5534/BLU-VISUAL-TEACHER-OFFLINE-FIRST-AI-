"""
Animated educational MP4 exporter for BLU Visual Teacher.
Produces real per-frame motion using Pillow + FFmpeg.

Scene types handled with unique motion effects:
  title_card      — fading intro, drifting particles, pulsing orb
  loop_cards      — number cards 1-5 slide in, bounce, loop arrow sweeps back
  code_walkthrough— code lines appear progressively, current line highlighted, cursor blinks
  loop_arrow      — curved return arrow with moving dot trace
  diagram         — nodes pulse, connector dots travel along lines
  (fallback)      — animated nodes + particles for any other type
"""

import os, shutil, subprocess, tempfile, math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1280, 720, 25

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _find_ffmpeg():
    p = shutil.which("ffmpeg")
    if p:
        return p
    for c in [
        os.environ.get("FFMPEG_PATH"),
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    ]:
        if c and Path(c).exists():
            return c
    for e in os.environ.get("PATH", "").split(os.pathsep):
        c = Path(e) / "ffmpeg.exe"
        if c.exists():
            return str(c)
    return None


def _font(size, bold=False):
    candidates = (
        ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf"]
        if bold
        else ["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"]
    )
    for n in candidates:
        try:
            return ImageFont.truetype(n, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _mono(size):
    for n in [
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/cour.ttf",
        "C:/Windows/Fonts/lucon.ttf",
    ]:
        try:
            return ImageFont.truetype(n, size)
        except Exception:
            pass
    return _font(size)


def _wrap(draw, text, font, max_w):
    words = str(text).split()
    lines, current = [], ""
    for w in words:
        test = (current + " " + w).strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_w:
            current = test
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines or [""]


def _lerp(a, b, t):
    return a + (b - a) * max(0.0, min(1.0, t))


def _ease_out(t):
    return 1 - (1 - t) ** 3


def _ease_in_out(t):
    return t * t * (3 - 2 * t)


# ─── Frame drawing helpers ─────────────────────────────────────────────────────

def _draw_background(d, t):
    """Scrolling star-field background."""
    d.rectangle((0, 0, W, H), fill="#071226")
    # Ambient glow
    gx = int(W / 2 + 200 * math.sin(t * 0.4))
    gy = int(H / 2 + 80 * math.cos(t * 0.3))
    d.ellipse((gx - 350, gy - 280, gx + 350, gy + 280), fill=(10, 50, 120, 30))
    # Drifting particles
    for i in range(50):
        speed = 8 + (i % 5) * 3
        x = int((i * 197 + t * speed) % W)
        y = int((i * 83 + 20 * math.sin(t * 0.7 + i)) % H)
        alpha = 100 + int(55 * math.sin(t * 2 + i))
        r = 1 + (i % 3)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(65, 170, 255, alpha))


def _draw_chrome(d, lesson_title, scene_idx, scene_count, t, dur, narration):
    """Shared top bar, subtitle box, and progress bar."""
    # Top bar
    d.rounded_rectangle((38, 28, W - 38, 98), radius=16,
                         fill=(10, 24, 47, 230), outline=(46, 137, 255, 200), width=2)
    d.text((58, 42), str(lesson_title)[:70], font=_font(20, True), fill="#81d8ff")
    scene_label = f"SCENE {scene_idx + 1:02d} / {scene_count:02d}"
    sb = d.textbbox((0, 0), scene_label, font=_font(17, True))
    d.text((W - 58 - (sb[2] - sb[0]), 47), scene_label, font=_font(17, True), fill="#5b8fd4")

    # Narration subtitle box
    d.rounded_rectangle((50, H - 125, W - 50, H - 20), radius=14,
                         fill=(4, 13, 30, 220), outline=(43, 102, 180, 180), width=2)
    lines = _wrap(d, narration, _font(20), W - 140)[:3]
    for j, line in enumerate(lines):
        d.text((75, H - 112 + j * 30), line, font=_font(20), fill="#e8f4ff")

    # Progress bar
    prog = max(0.02, min(1.0, t / max(dur, 0.1)))
    d.rounded_rectangle((50, H - 14, W - 50, H - 6), radius=4, fill=(30, 50, 80, 255))
    bar_w = int((W - 100) * prog)
    d.rounded_rectangle((50, H - 14, 50 + bar_w, H - 6), radius=4, fill=(42, 174, 255, 255))


# ─── Scene renderers ──────────────────────────────────────────────────────────

def _render_title_card(lesson, scene, idx, count, t, dur):
    im = Image.new("RGB", (W, H), "#071226")
    d = ImageDraw.Draw(im, "RGBA")
    _draw_background(d, t)

    # Pulsing orb
    orb_t = min(1.0, t / 1.5)
    orb_r = int(_ease_out(orb_t) * 90 + 10 * math.sin(t * 3))
    orb_x, orb_y = W // 2, 290
    for layer in range(4, 0, -1):
        alpha = 20 * layer
        lr = orb_r + layer * 18
        d.ellipse((orb_x - lr, orb_y - lr, orb_x + lr, orb_y + lr),
                  fill=(30, 120, 255, alpha))
    d.ellipse((orb_x - orb_r, orb_y - orb_r, orb_x + orb_r, orb_y + orb_r),
              fill=(60, 170, 255, 230))
    # Orb symbol
    sym = "\u221e"
    sb = d.textbbox((0, 0), sym, font=_font(52, True))
    d.text((orb_x - (sb[2] - sb[0]) // 2, orb_y - (sb[3] - sb[1]) // 2 - 4),
           sym, font=_font(52, True), fill="white")

    # Heading fade-in (simulate by full alpha after 0.6s)
    heading = str(scene.get("heading", "Welcome"))
    fade = min(1.0, max(0.0, (t - 0.5) / 1.0))
    heading_color = (255, 255, 255, int(255 * fade))
    hb = d.textbbox((0, 0), heading, font=_font(52, True))
    hx = (W - (hb[2] - hb[0])) // 2
    d.text((hx, 185), heading, font=_font(52, True), fill=heading_color)

    # Sub-heading slides up
    sub = "A loop repeats instructions automatically."
    sub_fade = min(1.0, max(0.0, (t - 1.2) / 1.0))
    sub_y = int(_lerp(H - 160, 360, _ease_out(sub_fade)))
    sb2 = d.textbbox((0, 0), sub, font=_font(26))
    d.text(((W - (sb2[2] - sb2[0])) // 2, sub_y), sub, font=_font(26),
           fill=(180, 220, 255, int(220 * sub_fade)))

    _draw_chrome(d, lesson.get("title", "BLU Visual Teacher"), idx, count, t, dur,
                 scene.get("narration", ""))
    return im


def _render_loop_cards(lesson, scene, idx, count, t, dur):
    """Moving number cards 1-5 with a loop-back arrow."""
    im = Image.new("RGB", (W, H), "#071226")
    d = ImageDraw.Draw(im, "RGBA")
    _draw_background(d, t)

    # Grid lines
    for gx in range(0, W, 80):
        d.line((gx, 110, gx, H - 140), fill=(30, 60, 100, 40))
    for gy in range(110, H - 140, 60):
        d.line((50, gy, W - 50, gy), fill=(30, 60, 100, 40))

    # Heading
    heading = str(scene.get("heading", "Loop: 1 to 5"))
    hb = d.textbbox((0, 0), heading, font=_font(36, True))
    d.text(((W - (hb[2] - hb[0])) // 2, 110), heading, font=_font(36, True), fill="#ffffff")

    # Cards appear sequentially; each card appears at t >= card_start_t
    n_cards = 5
    card_w, card_h = 130, 130
    spacing = (W - 120) // n_cards
    center_y = 330

    # Each card appears during first 60% of scene, one per slot
    appear_end = dur * 0.6
    card_interval = appear_end / n_cards

    # After all cards appear, show loop arrow for remaining time
    all_appeared_t = card_interval * n_cards

    active_card = -1  # The card currently "active" (highlighted)

    for ci in range(n_cards):
        card_start = ci * card_interval
        card_x = 60 + ci * spacing + spacing // 2

        if t < card_start:
            continue  # Not yet appeared

        # Slide in from right
        arrive_t = min(1.0, (t - card_start) / 0.35)
        slide = _ease_out(arrive_t)
        # Bounce: card comes from right edge
        start_x = W + card_w
        cx = int(_lerp(start_x, card_x, slide))

        # Bounce effect on arrival
        bounce = 0
        if 0.7 <= arrive_t <= 1.0:
            bounce_t = (arrive_t - 0.7) / 0.3
            bounce = int(-12 * math.sin(bounce_t * math.pi))

        cy = center_y + bounce

        # Determine active card (cycling after all appear)
        if t >= all_appeared_t:
            cycle_t = (t - all_appeared_t) / max(0.1, dur - all_appeared_t)
            active_idx = int(cycle_t * n_cards) % n_cards
            active_card = active_idx
        else:
            active_card = ci  # Most recently appeared

        is_active = (ci == active_card)

        # Card background
        glow_r = 14 + (4 if is_active else 0)
        card_color = (18, 80, 160, 240) if is_active else (14, 40, 90, 230)
        border_color = (80, 200, 255, 255) if is_active else (46, 120, 200, 200)
        d.rounded_rectangle(
            (cx - card_w // 2, cy - card_h // 2, cx + card_w // 2, cy + card_h // 2),
            radius=glow_r, fill=card_color, outline=border_color, width=3
        )
        if is_active:
            for gl in range(3, 0, -1):
                d.rounded_rectangle(
                    (cx - card_w // 2 - gl * 6, cy - card_h // 2 - gl * 6,
                     cx + card_w // 2 + gl * 6, cy + card_h // 2 + gl * 6),
                    radius=glow_r + gl * 4, outline=(50, 150, 255, 25 * gl), width=2
                )

        # Number
        num_str = str(ci + 1)
        nb = d.textbbox((0, 0), num_str, font=_font(54, True))
        d.text((cx - (nb[2] - nb[0]) // 2, cy - (nb[3] - nb[1]) // 2 - 4),
               num_str, font=_font(54, True), fill="white")

        # Label below card
        label = f"i = {ci + 1}"
        lb = d.textbbox((0, 0), label, font=_font(16))
        d.text((cx - (lb[2] - lb[0]) // 2, cy + card_h // 2 + 10),
               label, font=_font(16), fill="#7fc8ff")

    # Loop back arrow (appears after all cards)
    if t >= all_appeared_t:
        arrow_progress = min(1.0, (t - all_appeared_t) / max(0.1, (dur - all_appeared_t) * 0.5))
        arrow_t_cycle = (t - all_appeared_t) % 2.0 / 2.0  # 0-1 cycling every 2s

        # Draw a curved arc from right card back to left card
        x_start = 60 + (n_cards - 1) * spacing + spacing // 2
        x_end = 60 + spacing // 2
        arc_y_top = center_y - card_h // 2 - 55  # above the cards

        # Draw arc as polyline
        arc_pts = []
        for step in range(41):
            frac = step / 40
            ax = int(_lerp(x_start, x_end, frac))
            # Parabolic arc
            ay = int(arc_y_top + 40 * (4 * frac * (1 - frac)))  # inverted parabola
            arc_pts.append((ax, ay))

        # Draw arc segments
        for i in range(len(arc_pts) - 1):
            frac_along = i / (len(arc_pts) - 1)
            if frac_along > arrow_progress:
                break
            d.line([arc_pts[i], arc_pts[i + 1]], fill=(80, 200, 255, 200), width=4)

        # Moving dot on arc
        if arrow_progress > 0.1:
            dot_idx = int(arrow_t_cycle * (len(arc_pts) - 1))
            dot_idx = min(dot_idx, len(arc_pts) - 1)
            dx, dy = arc_pts[dot_idx]
            d.ellipse((dx - 10, dy - 10, dx + 10, dy + 10), fill=(120, 240, 255, 255))

        # Arrowhead at end
        if arrow_progress > 0.8:
            # Draw arrowhead pointing down-right at x_end
            ah_x, ah_y = x_end, arc_pts[-1][1]
            d.polygon([(ah_x - 10, ah_y - 18), (ah_x + 10, ah_y - 18), (ah_x, ah_y + 4)],
                      fill=(120, 240, 255, 220))

        # Label
        lbl = "loop repeats! \u2192"
        lab_fade = min(1.0, (t - all_appeared_t - 0.3) / 0.5)
        if lab_fade > 0:
            lb = d.textbbox((0, 0), lbl, font=_font(22, True))
            d.text(((W - (lb[2] - lb[0])) // 2, arc_y_top - 34),
                   lbl, font=_font(22, True),
                   fill=(200, 240, 255, int(255 * lab_fade)))

    # Iteration counter top-right
    if t >= all_appeared_t:
        cycle_t = (t - all_appeared_t) / max(0.1, dur - all_appeared_t)
        iter_n = int(cycle_t * n_cards) % n_cards + 1
        iter_str = f"Iteration: {iter_n}"
    else:
        iter_n = min(n_cards, int(t / card_interval) + 1)
        iter_str = f"Iteration: {iter_n}"
    ib = d.textbbox((0, 0), iter_str, font=_font(22, True))
    d.rounded_rectangle((W - 250, 30, W - 30, 76), radius=10,
                         fill=(10, 40, 90, 220), outline=(60, 160, 255, 200), width=2)
    d.text((W - 240, 42), iter_str, font=_font(22, True), fill="#81d8ff")

    _draw_chrome(d, lesson.get("title", "BLU"), idx, count, t, dur, scene.get("narration", ""))
    return im


def _syntax_highlight(d, line_text, x, y, font_size):
    """Draw a single code line with basic syntax highlighting."""
    KEYWORDS = {"for", "in", "if", "else", "elif", "while", "def", "return",
                 "import", "from", "print", "range", "break", "continue", "pass"}
    mono = _mono(font_size)
    tokens = []
    word = ""
    for ch in line_text + " ":
        if ch in " ():.,[]{}=<>!+-*/":
            if word:
                tokens.append(("word", word))
            tokens.append(("punc", ch))
            word = ""
        else:
            word += ch

    cx = x
    for kind, tok in tokens:
        if kind == "word":
            if tok in KEYWORDS:
                color = "#569cd6"  # blue for keywords
            elif tok.startswith(("'", '"', "f'")):
                color = "#ce9178"  # orange for strings
            elif tok.isdigit():
                color = "#b5cea8"  # green for numbers
            else:
                color = "#d4d4d4"  # default white-ish
        else:
            color = "#808080"  # gray for punctuation

        tb = d.textbbox((0, 0), tok, font=mono)
        d.text((cx, y), tok, font=mono, fill=color)
        cx += tb[2] - tb[0]
    return cx  # returns end x position of this line


def _render_code_walkthrough(lesson, scene, idx, count, t, dur):
    im = Image.new("RGB", (W, H), "#0d1117")
    d = ImageDraw.Draw(im, "RGBA")

    # Subtle animated background glow
    gx = int(W * 0.15 + 40 * math.sin(t * 0.5))
    d.ellipse((gx - 300, 100, gx + 300, 620), fill=(20, 50, 100, 18))

    code_text = str(scene.get("code", "# No code provided\npass"))
    all_lines = code_text.splitlines()
    if not all_lines:
        all_lines = ["# empty"]

    # Lines appear progressively: one new line every (dur/len) seconds
    reveal_speed = dur / max(len(all_lines), 1)
    lines_to_show = max(1, min(len(all_lines), int(t / reveal_speed) + 1))

    # Current highlighted line
    highlight_lines = scene.get("highlight_lines", [])
    current_hl = None
    if highlight_lines:
        hl_idx = int(t / reveal_speed) % len(highlight_lines)
        current_hl = highlight_lines[hl_idx] - 1  # 0-indexed

    # Code editor panel
    d.rounded_rectangle((50, 108, W - 50, H - 145), radius=16,
                         fill=(13, 17, 23, 245), outline=(48, 80, 130, 200), width=2)

    # Editor header bar
    d.rounded_rectangle((50, 108, W - 50, 145), radius=10,
                         fill=(22, 30, 45, 255))
    for dot_x, dot_col in [(80, "#ff5f56"), (104, "#ffbd2e"), (128, "#27c93f")]:
        d.ellipse((dot_x - 7, 120, dot_x + 7, 134), fill=dot_col)
    d.text((155, 120), "python_loop.py", font=_mono(18), fill="#888")

    font_size = 22
    mono = _mono(font_size)
    line_h = 34
    start_y = 158
    line_num_w = 55

    # Line number gutter
    d.rectangle((50, 145, 50 + line_num_w, H - 145), fill=(18, 22, 32, 200))

    for li in range(lines_to_show):
        line_text = all_lines[li]
        y = start_y + li * line_h
        if y > H - 160:
            break

        # Highlight current line
        is_highlighted = (li == current_hl)
        if is_highlighted:
            d.rectangle((50 + line_num_w, y - 3, W - 50, y + line_h - 3),
                         fill=(40, 80, 20, 120))
            d.rectangle((50 + line_num_w, y - 3, 50 + line_num_w + 4, y + line_h - 3),
                         fill=(100, 220, 60, 255))

        # Line number
        ln_str = str(li + 1)
        lb = d.textbbox((0, 0), ln_str, font=_mono(18))
        d.text((50 + line_num_w - (lb[2] - lb[0]) - 8, y + 4),
               ln_str, font=_mono(18), fill="#404060")

        # Code text with syntax highlighting
        indent = len(line_text) - len(line_text.lstrip())
        indent_px = indent * 12
        end_x = _syntax_highlight(d, line_text, 50 + line_num_w + 12 + indent_px, y + 2, font_size)

        # Blinking cursor on latest/highlighted line
        if li == lines_to_show - 1:
            cursor_on = (int(t * 2) % 2 == 0)
            if cursor_on:
                cur_x = end_x + 2 if li == lines_to_show - 1 else 50 + line_num_w + 14
                d.rectangle((cur_x, y + 2, cur_x + 3, y + font_size + 4),
                             fill=(200, 230, 200, 230))

    _draw_chrome(d, lesson.get("title", "BLU"), idx, count, t, dur, scene.get("narration", ""))
    return im


def _render_loop_arrow(lesson, scene, idx, count, t, dur):
    """Big animated loop-back arc with moving dot."""
    im = Image.new("RGB", (W, H), "#071226")
    d = ImageDraw.Draw(im, "RGBA")
    _draw_background(d, t)

    heading = str(scene.get("heading", "The Loop Arrow"))
    hb = d.textbbox((0, 0), heading, font=_font(38, True))
    d.text(((W - (hb[2] - hb[0])) // 2, 110), heading, font=_font(38, True), fill="#ffffff")

    # Two boxes: "loop body" on left, "check condition" on right
    box_y = 220
    box_h = 100

    left_x = 180
    right_x = W - 180 - 220

    for bx, label, color in [
        (left_x, "Loop body\nruns here", (14, 80, 200)),
        (right_x, "Check:\nmore items?", (120, 60, 14))
    ]:
        d.rounded_rectangle((bx, box_y, bx + 220, box_y + box_h),
                             radius=16, fill=(*color, 200), outline=(100, 180, 255, 200), width=2)
        lines = label.split("\n")
        for li, l in enumerate(lines):
            lb = d.textbbox((0, 0), l, font=_font(22, True))
            d.text((bx + (220 - (lb[2] - lb[0])) // 2,
                    box_y + 24 + li * 32), l, font=_font(22, True), fill="white")

    # Arrow from left box -> right box (straight, top area)
    ax1 = left_x + 220
    ax2 = right_x
    ay = box_y + box_h // 2
    d.line((ax1, ay, ax2, ay), fill=(100, 200, 255, 200), width=4)
    # Arrowhead right
    d.polygon([(ax2 - 14, ay - 10), (ax2, ay), (ax2 - 14, ay + 10)],
              fill=(100, 200, 255, 220))

    # Big curved return arrow (looping back)
    # Arc from right box bottom, curves down and left, back to left box bottom
    arc_steps = 80
    arc_pts = []
    for step in range(arc_steps + 1):
        frac = step / arc_steps
        # Cubic bezier: P0=right box bottom, P3=left box bottom, control points below
        p0x, p0y = right_x + 110, box_y + box_h
        p3x, p3y = left_x + 110, box_y + box_h
        p1x, p1y = right_x + 110, box_y + box_h + 200
        p2x, p2y = left_x + 110, box_y + box_h + 200
        # Bezier formula
        bx_pt = (1 - frac) ** 3 * p0x + 3 * (1 - frac) ** 2 * frac * p1x + \
                3 * (1 - frac) * frac ** 2 * p2x + frac ** 3 * p3x
        by_pt = (1 - frac) ** 3 * p0y + 3 * (1 - frac) ** 2 * frac * p1y + \
                3 * (1 - frac) * frac ** 2 * p2y + frac ** 3 * p3y
        arc_pts.append((int(bx_pt), int(by_pt)))

    # Draw the arc
    cycle_dur = max(1.0, dur * 0.5)
    dot_frac = (t % cycle_dur) / cycle_dur
    reveal = min(1.0, t / (dur * 0.4))

    for i in range(len(arc_pts) - 1):
        if i / len(arc_pts) > reveal:
            break
        d.line([arc_pts[i], arc_pts[i + 1]], fill=(80, 200, 255, 200), width=5)

    # Moving dot on arc
    dot_i = int(dot_frac * (len(arc_pts) - 1))
    dot_i = min(dot_i, len(arc_pts) - 1)
    dx, dy = arc_pts[dot_i]
    for gl in range(3, 0, -1):
        d.ellipse((dx - 8 - gl * 4, dy - 8 - gl * 4, dx + 8 + gl * 4, dy + 8 + gl * 4),
                  fill=(80, 180, 255, 30 * gl))
    d.ellipse((dx - 10, dy - 10, dx + 10, dy + 10), fill=(140, 240, 255, 255))

    # "YES - repeat!" label
    arc_mid = arc_pts[len(arc_pts) // 2]
    lbl = "YES \u2192 repeat!"
    lb = d.textbbox((0, 0), lbl, font=_font(24, True))
    bounce = int(5 * math.sin(t * 4))
    lbl_fade = min(1.0, t / 1.2)
    d.text((arc_mid[0] - (lb[2] - lb[0]) // 2, arc_mid[1] + 12 + bounce),
           lbl, font=_font(24, True), fill=(140, 240, 255, int(255 * lbl_fade)))

    # "NO → Done" label near right box
    done_fade = min(1.0, max(0.0, (t - 1.0) / 0.8))
    d.text((right_x + 50, box_y - 50), "NO \u2192 loop ends",
           font=_font(22, True), fill=(200, 255, 180, int(220 * done_fade)))

    _draw_chrome(d, lesson.get("title", "BLU"), idx, count, t, dur, scene.get("narration", ""))
    return im


def _render_diagram(lesson, scene, idx, count, t, dur):
    im = Image.new("RGB", (W, H), "#071226")
    d = ImageDraw.Draw(im, "RGBA")
    _draw_background(d, t)

    heading = str(scene.get("heading", "Diagram"))
    hb = d.textbbox((0, 0), heading, font=_font(38, True))
    d.text(((W - (hb[2] - hb[0])) // 2, 110), heading, font=_font(38, True), fill="white")

    items = scene.get("items") or ["Start", "Process", "End"]
    n = len(items)
    n = max(2, min(6, n))
    items = items[:n]

    # Node positions (horizontal row)
    node_r = 52
    total_w = (n - 1) * 180 + node_r * 2
    start_x = (W - total_w) // 2 + node_r
    node_y = 340

    # Appear reveal: nodes appear one by one
    appear_interval = dur * 0.7 / max(n, 1)
    nodes_shown = min(n, int(t / max(appear_interval, 0.01)) + 1)

    # Moving dot between nodes
    seg_dur = (dur * 0.5) / max(n - 1, 1)
    dot_progress = (t % max(dur, 0.1)) / max(dur, 0.1)
    dot_abs = dot_progress * (n - 1)
    dot_seg = int(dot_abs) % max(n - 1, 1)
    dot_frac = dot_abs - int(dot_abs)

    # Draw connector lines
    for i in range(min(nodes_shown - 1, n - 1)):
        x1 = start_x + i * 180
        x2 = start_x + (i + 1) * 180
        d.line((x1 + node_r, node_y, x2 - node_r, node_y),
               fill=(43, 123, 255, 180), width=4)
        # Arrowhead
        ax = x2 - node_r
        d.polygon([(ax - 12, node_y - 8), (ax, node_y), (ax - 12, node_y + 8)],
                  fill=(80, 180, 255, 200))

    # Moving dot on connectors
    if nodes_shown >= 2:
        seg = min(dot_seg, nodes_shown - 2)
        x1 = start_x + seg * 180 + node_r
        x2 = start_x + (seg + 1) * 180 - node_r
        dx = int(_lerp(x1, x2, dot_frac))
        dy = node_y
        for gl in range(3, 0, -1):
            d.ellipse((dx - 6 - gl * 4, dy - 6 - gl * 4, dx + 6 + gl * 4, dy + 6 + gl * 4),
                      fill=(100, 220, 255, 25 * gl))
        d.ellipse((dx - 8, dy - 8, dx + 8, dy + 8), fill=(140, 240, 255, 255))

    # Draw nodes
    for i in range(nodes_shown):
        nx = start_x + i * 180
        pulse = int(4 * math.sin(t * 2.5 + i * 0.8))
        nr = node_r + pulse

        is_current = (i == min(dot_seg, nodes_shown - 1))
        fill_col = (18, 80, 200, 240) if is_current else (14, 50, 110, 220)
        outline_col = (100, 230, 255, 255) if is_current else (60, 150, 255, 200)

        # Glow
        if is_current:
            for gl in range(3, 0, -1):
                glr = nr + gl * 12
                d.ellipse((nx - glr, node_y - glr, nx + glr, node_y + glr),
                           fill=(40, 120, 255, 20 * gl))

        d.ellipse((nx - nr, node_y - nr, nx + nr, node_y + nr),
                  fill=fill_col, outline=outline_col, width=3)

        # Node label (inside)
        label = items[i]
        # Truncate if too long for inside
        if len(label) > 8:
            label = label[:7] + "\u2026"
        lb = d.textbbox((0, 0), label, font=_font(17, True))
        d.text((nx - (lb[2] - lb[0]) // 2, node_y - (lb[3] - lb[1]) // 2 - 2),
               label, font=_font(17, True), fill="white")

        # Full label below
        full_label = items[i]
        flb = d.textbbox((0, 0), full_label, font=_font(15))
        d.text((nx - (flb[2] - flb[0]) // 2, node_y + nr + 10),
               full_label, font=_font(15), fill="#a0d0ff")

    _draw_chrome(d, lesson.get("title", "BLU"), idx, count, t, dur, scene.get("narration", ""))
    return im


def _render_fallback(lesson, scene, idx, count, t, dur):
    """Generic animated scene for unrecognized scene types."""
    im = Image.new("RGB", (W, H), "#071226")
    d = ImageDraw.Draw(im, "RGBA")
    _draw_background(d, t)

    heading = str(scene.get("heading", "Explore the idea"))
    hb = d.textbbox((0, 0), heading, font=_font(40, True))
    d.text(((W - (hb[2] - hb[0])) // 2, 120), heading, font=_font(40, True), fill="white")

    items = scene.get("items") or [scene.get("type", "concept")]
    content = scene.get("code") or "  \u2022  ".join(str(x) for x in items[:5])
    labels = [x for x in str(content).splitlines() if x.strip()][:5] or ["Explore"]
    n = max(2, min(5, len(labels)))
    xs = [140 + i * (W - 280) // (n - 1) for i in range(n)]
    cy = 340

    for i in range(n - 1):
        d.line((xs[i], cy, xs[i + 1], cy), fill=(43, 123, 255, 180), width=4)
        q = (t * 0.8 + i * 0.25) % 1
        bx = int(xs[i] + (xs[i + 1] - xs[i]) * q)
        d.ellipse((bx - 9, cy - 9, bx + 9, cy + 9), fill=(120, 245, 255, 255))

    for i, x in enumerate(xs):
        y = cy + int(10 * math.sin(t * 2 + i))
        r = 45 + int(4 * math.sin(t * 2 + i))
        d.ellipse((x - r - 5, y - r - 5, x + r + 5, y + r + 5),
                  fill=(18, 61, 123, 200), outline=(80, 210, 255, 255), width=3)
        s = str(i + 1)
        sb = d.textbbox((0, 0), s, font=_font(30, True))
        d.text((x - (sb[2] - sb[0]) // 2, y - (sb[3] - sb[1]) // 2 - 3),
               s, font=_font(30, True), fill="white")
        for j, line in enumerate(_wrap(d, labels[i % len(labels)], _font(16), 180)[:2]):
            lb = d.textbbox((0, 0), line, font=_font(16))
            d.text((x - (lb[2] - lb[0]) // 2, cy + 65 + j * 24),
                   line, font=_font(16), fill="#c9e7ff")

    _draw_chrome(d, lesson.get("title", "BLU"), idx, count, t, dur, scene.get("narration", ""))
    return im


# ─── Scene dispatcher ─────────────────────────────────────────────────────────

SCENE_RENDERERS = {
    "title_card": _render_title_card,
    "loop_cards": _render_loop_cards,
    "code_walkthrough": _render_code_walkthrough,
    "loop_arrow": _render_loop_arrow,
    "diagram": _render_diagram,
}


def _render_frame(lesson, scene, idx, count, t, dur):
    stype = str(scene.get("type", "")).strip().lower()
    renderer = SCENE_RENDERERS.get(stype, _render_fallback)
    return renderer(lesson, scene, idx, count, t, dur)


# ─── Public API ───────────────────────────────────────────────────────────────

def make_mp4(lesson: dict, output_path: str, audio_path: str | None = None) -> str:
    """
    Render an animated MP4 from a lesson dict.

    Args:
        lesson: Lesson dictionary with title, scenes, etc.
        output_path: Destination .mp4 file path.
        audio_path: Optional path to an existing .mp3/.wav audio file.

    Returns:
        The output_path string on success.

    Raises:
        RuntimeError: If FFmpeg is not found or encoding fails.
        ValueError: If the lesson contains no scenes.
    """
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError(
            "FFmpeg not found. Install FFmpeg and add it to PATH, or set the "
            "FFMPEG_PATH environment variable."
        )

    scenes = lesson.get("scenes") or []
    if not scenes:
        raise ValueError("Lesson contains no scenes to animate.")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="blu_animated_") as td_str:
        td = Path(td_str)
        frame_number = 0

        for si, scene in enumerate(scenes):
            words = len(str(scene.get("narration", "")).split())
            # Longer duration for complex scenes
            stype = str(scene.get("type", "")).lower()
            if stype == "code_walkthrough":
                code_lines = len(str(scene.get("code", "")).splitlines())
                dur = max(5.0, min(18.0, code_lines * 1.2 + words / 3.0))
            elif stype in ("loop_cards", "loop_arrow"):
                dur = max(7.0, min(16.0, words / 2.5 + 3.0))
            else:
                dur = max(4.0, min(14.0, words / 2.5 + 1.5))

            total_frames = max(1, int(dur * FPS))
            for fi in range(total_frames):
                t = fi / FPS
                frame = _render_frame(lesson, scene, si, len(scenes), t, dur)
                frame.save(td / f"frame_{frame_number:06d}.jpg", quality=88)
                frame_number += 1

        # FFmpeg encode
        cmd = [
            ffmpeg, "-y",
            "-framerate", str(FPS),
            "-i", str(td / "frame_%06d.jpg"),
        ]

        has_audio = bool(audio_path and Path(audio_path).exists())
        if has_audio:
            cmd += ["-i", str(audio_path)]

        cmd += [
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "21",
            "-pix_fmt", "yuv420p",
        ]

        if has_audio:
            cmd += [
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:a", "aac",
                "-b:a", "160k",
                "-shortest",
            ]
        else:
            cmd += ["-an"]

        cmd += ["-movflags", "+faststart", str(out)]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(
                f"FFmpeg encoding failed:\n{(result.stderr or 'Unknown error')[-3000:]}"
            )

    return str(out)
