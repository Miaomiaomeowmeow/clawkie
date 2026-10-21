# 克讲机 Clawkie · 机身画法 — made by Miaomiao (https://github.com/Miaomiaomeowmeow) · CC BY-NC-SA 4.0
# 对讲机的样子：用 PIL 一笔一笔画出来（不是贴图），所以窗口拉多大都能重画、不会糊。
# render(...) → (图片, 各个部位的位置)
# 图片外面一圈是 KEY 色，窗口会把它变透明；部位位置给 clawkie_talkie.py 摆输入框、判断点到了哪。
#
# 照着真对讲机画（2026-10-14 看了 Bing 图片：Retevis / Midland 户外机、80 年代 Radio Shack / Fisher-Price 玩具机、
# Behance「Flat vs Skeuomorphic Walkie-Talkie」）：天线偏一边、顶上旋钮、喇叭孔、背光屏、侧面防滑通话键、
# 铭牌型号、螺丝、橡胶包边、机身高光。
#
# 两种小克（2026-10-15 用户选「A 和 B 都要」）：
#   A「小克机」：小克就是对讲机——耳朵是天线、眼睛是指示灯、右手是通话键、肚子是屏幕、四条腿当支架
#   B 其他 5 种机身：小克的头和爪子扒在机身顶上

import math
import random

from PIL import Image, ImageDraw, ImageFont

KEY = (255, 0, 254)
SS = 2  # 先画 2 倍大再缩小，边缘才顺滑
INK = "#151513"

THEMES = {
    "clawd": {
        "name": "小克机", "face": "#d97757", "rubber": INK, "accent": "#e2412b", "knob": "#fff3e0",
        "lcd": "#f2d04a", "lcd_ink": "#2a2410", "screen": "#fff3e0", "ink": INK, "label": "#fff3e0",
        "antenna": "ears", "grille": "none", "brand": "#fff3e0",
    },
    "pop": {
        "name": "扑克钴蓝", "face": "#2f4fd8", "rubber": "#1b1b2a", "accent": "#e2412b", "knob": "#f6f0e2",
        "lcd": "#f2d04a", "lcd_ink": "#2a2410", "screen": "#f6f0e2", "ink": "#1b1b2a", "label": "#f6f0e2",
        "antenna": "rubber", "grille": "slots", "brand": "#f6f0e2",
    },
    "rugged": {
        "name": "户外黄", "face": "#f2b705", "rubber": "#232427", "accent": "#232427", "knob": "#2c2d31",
        "lcd": "#f6a93b", "lcd_ink": "#2b1a05", "screen": "#f4f1e6", "ink": "#1b1b1b", "label": "#232427",
        "antenna": "rubber", "grille": "slots", "brand": "#232427",
    },
    "retro": {
        "name": "80 年代银灰", "face": "#babdc2", "rubber": "#3a3b40", "accent": "#e5582a", "knob": "#2f3034",
        "lcd": "#a9c48b", "lcd_ink": "#1f2a14", "screen": "#eef0e8", "ink": "#1d1e22", "label": "#2a2b30",
        "antenna": "chrome", "grille": "holes", "brand": "#e5582a",
    },
    "mint": {
        "name": "薄荷复古", "face": "#7fcbb4", "rubber": "#2b4a43", "accent": "#e5582a", "knob": "#c9a15b",
        "lcd": "#f3e3b0", "lcd_ink": "#3a2e12", "screen": "#f7f3e6", "ink": "#1f3a33", "label": "#1f3a33",
        "antenna": "rubber", "grille": "slots", "brand": "#1f3a33",
    },
    "y2k": {
        "name": "Y2K 糖果紫", "face": "#b69bff", "rubber": "#6c4bd8", "accent": "#ff6fb5", "knob": "#fbf7ff",
        "lcd": "#c7f5ff", "lcd_ink": "#2a1a5e", "screen": "#fbf7ff", "ink": "#2a1a5e", "label": "#ffffff",
        "antenna": "candy", "grille": "holes", "brand": "#ffffff",
    },
}
ORDER = ["clawd", "pop", "rugged", "retro", "mint", "y2k"]
MODES = ["聊", "记", "画"]
FONT_FILES = ["msyhbd.ttc", "msyh.ttc", "arialbd.ttf"]


def rgb(h):
    if not isinstance(h, str):
        return tuple(h)
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(c, k):
    """k>0 变亮，k<0 变暗"""
    c = rgb(c)
    return tuple(max(0, min(255, round(v + (255 - v) * k if k > 0 else v * (1 + k)))) for v in c)


def font(size, bold=True):
    for name in (FONT_FILES if bold else FONT_FILES[1:]):
        try:
            return ImageFont.truetype(name, max(6, int(size)))
        except OSError:
            continue
    return ImageFont.load_default()


def vgrad(img, box, top, bottom, radius):
    """竖着渐变的圆角块：一条一条横线画，再用圆角遮罩"""
    x0, y0, x1, y1 = [int(v) for v in box]
    h = max(1, y1 - y0)
    layer = Image.new("RGB", (max(1, x1 - x0), h))
    ld = ImageDraw.Draw(layer)
    t, b = rgb(top), rgb(bottom)
    for i in range(h):
        f = i / h
        ld.line([(0, i), (x1 - x0, i)], fill=tuple(round(t[j] + (b[j] - t[j]) * f) for j in range(3)))
    mask = Image.new("L", layer.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, x1 - x0 - 1, h - 1], radius=int(radius), fill=255)
    img.paste(layer, (x0, y0), mask)


def inset(d, box, fill, radius, depth):
    """凹进去的框：上面一圈暗、下面一圈亮"""
    x0, y0, x1, y1 = box
    d.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=mix(fill, -0.45))
    d.rounded_rectangle([x0, y0 + depth, x1, y1], radius=radius, fill=mix(fill, 0.35))
    d.rounded_rectangle([x0 + depth * 0.6, y0 + depth, x1 - depth * 0.6, y1 - depth * 0.6], radius=max(1, radius - depth), fill=rgb(fill))


def knob(d, cx, cy, r, color, ink, angle=None):
    """圆旋钮：一圈防滑齿 + 由亮到暗的面 + 指针"""
    for i in range(24):
        a = 2 * math.pi * i / 24
        x, y = cx + math.cos(a) * r, cy + math.sin(a) * r
        d.ellipse([x - r * 0.13, y - r * 0.13, x + r * 0.13, y + r * 0.13], fill=mix(color, -0.35))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=mix(color, -0.3))
    for i in range(8):
        rr = r * (0.92 - 0.06 * i)
        off = r * 0.03 * i
        d.ellipse([cx - rr - off, cy - rr - off, cx + rr - off, cy + rr - off], fill=mix(color, -0.15 + 0.05 * i))
    if angle is not None:
        a = math.radians(angle - 90)
        d.line([(cx + math.cos(a) * r * 0.2, cy + math.sin(a) * r * 0.2), (cx + math.cos(a) * r * 0.78, cy + math.sin(a) * r * 0.78)],
               fill=rgb(ink), width=max(2, int(r * 0.17)))


def screw(d, cx, cy, r, base):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=mix(base, -0.5))
    d.ellipse([cx - r * 0.8, cy - r * 0.8, cx + r * 0.8, cy + r * 0.8], fill=mix(base, 0.25))
    d.line([(cx - r * 0.55, cy + r * 0.55), (cx + r * 0.55, cy - r * 0.55)], fill=mix(base, -0.55), width=max(1, int(r * 0.35)))


def stepped(x0, y0, x1, y1, c):
    """像素风的切角方块（每个角切掉 c 那么大的一格）"""
    return [(x0, y0 + c), (x0 + c, y0 + c), (x0 + c, y0), (x1 - c, y0), (x1 - c, y0 + c), (x1, y0 + c),
            (x1, y1 - c), (x1 - c, y1 - c), (x1 - c, y1), (x0 + c, y1), (x0 + c, y1 - c), (x0, y1 - c)]


def box_div(b, s):
    return tuple(v / s for v in b)


def render(w, h, k, theme_id, clawd_cells=None, knob_angles=(0, 0, 0, 0), mode=0, knobs=True,
           clawd_color="#d97757", busy=False):
    T = dict(THEMES.get(theme_id, THEMES["pop"]))
    A = theme_id == "clawd"
    if A:
        T["face"] = clawd_color
    S = SS
    W, H = w * S, h * S
    u = k * S  # 1 个「设计单位」= 屏幕缩放后的 1px
    img = Image.new("RGB", (W, H), rgb(T["rubber"]))
    d = ImageDraw.Draw(img)
    sil = Image.new("L", (W, H), 0)  # 外形：哪里是对讲机 / 小克（其余变透明）
    sd = ImageDraw.Draw(sil)
    L = {}

    # ---------- 外形 ----------
    if A:
        top = 46 * u
        left, right = 26 * u, W - 30 * u
        bottom = H - 30 * u
    else:
        top = 64 * u
        left, right = 16 * u, W - 18 * u
        bottom = H - 4 * u
    bw = right - left
    r_body = 30 * u

    # 顶上两个小旋钮：频道（换对话）、机身（换样子）
    tk_r = 14 * u
    knob_x = (0.40, 0.60) if A else (0.70, 0.86)
    tops = []
    for fx in knob_x:
        cx = left + bw * fx
        y0 = top - 20 * u
        sd.rounded_rectangle([cx - tk_r, y0, cx + tk_r, top + 10 * u], radius=5 * u, fill=255)
        d.rounded_rectangle([cx - tk_r, y0, cx + tk_r, top + 10 * u], radius=5 * u, fill=mix(T["knob"], -0.25))
        for j in range(6):
            xx = cx - tk_r + (j + 0.5) * (2 * tk_r / 6)
            d.line([(xx, y0 + 3 * u), (xx, top + 6 * u)], fill=mix(T["knob"], -0.45), width=int(1.5 * u))
        d.rounded_rectangle([cx - tk_r, y0, cx + tk_r, y0 + 5 * u], radius=4 * u, fill=mix(T["knob"], 0.12))
        tops.append((cx, y0))
    L["chan"] = box_div((tops[0][0] - tk_r, tops[0][1], tops[0][0] + tk_r, top + 6 * u), S)
    L["skin"] = box_div((tops[1][0] - tk_r, tops[1][1], tops[1][0] + tk_r, top + 6 * u), S)

    py0, py1 = top + (bottom - top) * 0.30, top + (bottom - top) * 0.50
    if A:
        # 耳朵 = 天线（矮胖的像素耳朵，内耳浅色）
        ew, step, rows = 48 * u, 11 * u, 3
        for ex in (left + bw * 0.10, right - bw * 0.10 - ew):
            for i in range(rows):
                ins = i * 9 * u
                yy = top - (i + 1) * step
                sd.rectangle([ex + ins - 3 * u, yy - 3 * u, ex + ew - ins + 3 * u, yy + step + 3 * u], fill=255)
                d.rectangle([ex + ins - 3 * u, yy - 3 * u, ex + ew - ins + 3 * u, yy + step + 3 * u], fill=rgb(INK))
            for i in range(rows):
                ins = i * 9 * u
                yy = top - (i + 1) * step
                d.rectangle([ex + ins, yy, ex + ew - ins, yy + step + 3 * u], fill=rgb(T["face"]))
            for i in range(rows - 1):
                ins = i * 9 * u + 12 * u
                yy = top - (i + 1) * step
                d.rectangle([ex + ins, yy + 2 * u, ex + ew - ins, yy + step + 3 * u], fill=mix(T["face"], 0.45))
        # 四条腿当支架
        for fx in (0.14, 0.32, 0.62, 0.80):
            lx = left + bw * fx
            sd.rectangle([lx - 3 * u, bottom - 4 * u, lx + 24 * u, H - 2 * u], fill=255)
            d.rectangle([lx - 3 * u, bottom - 4 * u, lx + 24 * u, H - 2 * u], fill=rgb(INK))
            d.rectangle([lx, bottom, lx + 21 * u, H - 5 * u], fill=rgb(T["face"]))
        # 左手（装饰）、右手 = 通话键（按住说话）
        ay0, ay1 = top + (bottom - top) * 0.36, top + (bottom - top) * 0.44
        sd.rectangle([left - 22 * u, ay0 - 3 * u, left + 4 * u, ay1 + 3 * u], fill=255)
        d.rectangle([left - 22 * u, ay0 - 3 * u, left + 4 * u, ay1 + 3 * u], fill=rgb(INK))
        d.rectangle([left - 19 * u, ay0, left + 4 * u, ay1], fill=rgb(T["face"]))
        sd.rectangle([right - 4 * u, py0 - 3 * u, right + 26 * u, py1 + 3 * u], fill=255)
        d.rectangle([right - 4 * u, py0 - 3 * u, right + 26 * u, py1 + 3 * u], fill=rgb(INK))
        d.rectangle([right - 4 * u, py0, right + 23 * u, py1], fill=rgb(T["face"]))
        for j in range(8):
            yy = py0 + 8 * u + j * (py1 - py0 - 16 * u) / 7
            d.line([(right + 6 * u, yy), (right + 19 * u, yy)], fill=mix(T["face"], -0.3), width=int(1.6 * u))
        L["side"] = box_div((right - 4 * u, py0, right + 26 * u, py1), S)
        # 身子：像素切角 + 黑描边
        c = 12 * u
        sd.polygon(stepped(left - 3 * u, top - 3 * u, right + 3 * u, bottom + 3 * u, c), fill=255)
        d.polygon(stepped(left - 3 * u, top - 3 * u, right + 3 * u, bottom + 3 * u, c), fill=rgb(INK))
        d.polygon(stepped(left, top, right, bottom, c), fill=rgb(T["face"]))
        d.rectangle([left + c, top + 3 * u, right - c, top + 9 * u], fill=mix(T["face"], 0.22))  # 顶边高光
        d.rectangle([left + 3 * u, bottom - 14 * u, right - 3 * u, bottom - c * 0.5], fill=mix(T["face"], -0.12))  # 肚子下沿暗一点
        fl, ft, fr, fb = left + 6 * u, top + 6 * u, right - 6 * u, bottom - 6 * u
    else:
        # 天线（左边）
        ax = left + bw * 0.16
        if T["antenna"] == "chrome":
            sd.rounded_rectangle([ax - 3 * u, 10 * u, ax + 3 * u, top + 10 * u], radius=3 * u, fill=255)
            sd.ellipse([ax - 8 * u, 0, ax + 8 * u, 16 * u], fill=255)
            d.rounded_rectangle([ax - 3 * u, 10 * u, ax + 3 * u, top + 10 * u], radius=3 * u, fill=(205, 208, 214))
            d.line([(ax - 1 * u, 12 * u), (ax - 1 * u, top)], fill=(245, 246, 248), width=int(1.5 * u))
            d.ellipse([ax - 8 * u, 0, ax + 8 * u, 16 * u], fill=rgb(T["accent"]))
            d.ellipse([ax - 4 * u, 3 * u, ax + 1 * u, 8 * u], fill=mix(T["accent"], 0.5))
        else:
            col = T["rubber"] if T["antenna"] == "rubber" else T["accent"]
            sd.rounded_rectangle([ax - 10 * u, 4 * u, ax + 10 * u, top + 14 * u], radius=9 * u, fill=255)
            d.rounded_rectangle([ax - 10 * u, 4 * u, ax + 10 * u, top + 14 * u], radius=9 * u, fill=rgb(col))
            for i in range(4):
                yy = 18 * u + i * 9 * u
                d.line([(ax - 8 * u, yy), (ax + 8 * u, yy)], fill=mix(col, -0.35), width=int(1.6 * u))
            d.line([(ax - 5 * u, 8 * u), (ax - 5 * u, top)], fill=mix(col, 0.25), width=int(2 * u))
        # 小克趴在顶上：先画小克，再画机身挡住他下半身，最后画两只爪子扒在边上
        if clawd_cells:
            cu = bw * 0.30 / 28
            ccx = left + bw * 0.44
            ox = ccx - 7 * cu  # 小克的格子从 x=-7 到 21
            oy = top + 6 * u - 11 * cu  # 露出上面 11 格左右
            for kind, x, yy, cw, chh, col in clawd_cells:
                bx, by = ox + x * cu, oy + yy * cu
                if by > top + 8 * u:
                    continue
                sd.rectangle([bx, by, bx + cw * cu, min(by + chh * cu, top + 8 * u)], fill=255)
                if kind == "r":
                    d.rectangle([bx, by, bx + cw * cu, min(by + chh * cu, top + 8 * u)], fill=col)
                else:
                    d.rectangle([bx, by, bx + cw * cu, by + chh * cu], outline=col, width=max(1, int(0.7 * cu)))
            L["clawd"] = box_div((ox - 7 * cu, oy - 3 * cu, ox + 21 * cu, top + 8 * u), S)
            paws = [(ox + 0 * cu, top - 1 * u), (ox + 15 * cu, top - 1 * u)]
        else:
            paws = []
        # 侧面通话键（右边，带防滑纹）
        sd.rounded_rectangle([right - 6 * u, py0, right + 14 * u, py1], radius=8 * u, fill=255)
        d.rounded_rectangle([right - 6 * u, py0, right + 14 * u, py1], radius=8 * u, fill=rgb(T["rubber"]))
        for j in range(9):
            yy = py0 + 8 * u + j * (py1 - py0 - 16 * u) / 8
            d.line([(right + 1 * u, yy), (right + 11 * u, yy)], fill=mix(T["rubber"], 0.25), width=int(1.4 * u))
        L["side"] = box_div((right - 6 * u, py0, right + 14 * u, py1), S)
        # 橡胶包边 + 机身面板（上亮下暗）
        sd.rounded_rectangle([left, top, right, bottom], radius=r_body, fill=255)
        d.rounded_rectangle([left, top, right, bottom], radius=r_body, fill=rgb(T["rubber"]))
        d.rounded_rectangle([left + 2 * u, top + 2 * u, right - 2 * u, top + 28 * u], radius=r_body, fill=mix(T["rubber"], 0.18))
        fl, ft, fr, fb = left + 6 * u, top + 6 * u, right - 6 * u, bottom - 6 * u
        vgrad(img, (fl, ft, fr, fb), mix(T["face"], 0.16), mix(T["face"], -0.12), r_body - 6 * u)
        d.rounded_rectangle([fl + 3 * u, ft + 2 * u, fr - 3 * u, ft + 5 * u], radius=2 * u, fill=mix(T["face"], 0.42))
        shade_w = int(22 * u)
        for i in range(shade_w):
            f = (1 - i / shade_w) ** 2 * 0.22
            for xx in (fl + i, fr - i):
                d.line([(xx, ft + r_body * 0.7), (xx, fb - r_body * 0.7)], fill=mix(T["face"], -f), width=1)
        d.rounded_rectangle([fl, ft, fr, fb], radius=r_body - 6 * u, outline=mix(T["face"], -0.3), width=int(1.4 * u))
        if theme_id == "y2k":
            rnd = random.Random(7)
            for _ in range(16):
                x_ = rnd.uniform(fl + 30 * u, fr - 30 * u)
                y_ = rnd.uniform(ft + 30 * u, fb - 30 * u)
                ln = rnd.uniform(20, 60) * u
                col = mix(T["face"], 0.22)
                if rnd.random() < 0.5:
                    d.line([(x_, y_), (min(x_ + ln, fr - 30 * u), y_)], fill=col, width=int(2 * u))
                else:
                    d.line([(x_, y_), (x_, min(y_ + ln, fb - 30 * u))], fill=col, width=int(2 * u))
                d.ellipse([x_ - 3 * u, y_ - 3 * u, x_ + 3 * u, y_ + 3 * u], fill=col)
        for j in range(10):
            yy = top + (bottom - top) * 0.58 + j * 7 * u
            d.line([(left + 1.5 * u, yy), (left + 4.5 * u, yy)], fill=mix(T["rubber"], 0.3), width=int(1.5 * u))
        # 爪子扒在机身顶边
        for (px_, py_) in paws:
            pw_, ph_ = 7 * cu, 4 * cu
            sd.rectangle([px_ - 2 * u, py_ - 2 * u, px_ + pw_ + 2 * u, py_ + ph_ + 2 * u], fill=255)
            d.rectangle([px_ - 2 * u, py_ - 2 * u, px_ + pw_ + 2 * u, py_ + ph_ + 2 * u], fill=rgb(INK))
            d.rectangle([px_, py_, px_ + pw_, py_ + ph_], fill=rgb(clawd_color))
            for t_ in (1, 2):
                xx = px_ + pw_ * t_ / 3
                d.line([(xx, py_ + ph_ * 0.45), (xx, py_ + ph_)], fill=rgb(INK), width=max(1, int(1.2 * u)))

    L["body"] = box_div((left, top, right, bottom), S)
    pad = 16 * u
    x0, x1 = fl + pad, fr - pad
    y = ft + 10 * u

    # ---------- 第一行：三档拨杆 · 喇叭孔或眼睛 · 指示灯 · 电源键 ----------
    row_h = 30 * u
    seg_w, seg_h = 26 * u, 22 * u
    sx0, sy0 = x0, y + (row_h - seg_h) / 2
    d.rounded_rectangle([sx0 - 3 * u, sy0 - 3 * u, sx0 + 3 * seg_w + 3 * u, sy0 + seg_h + 3 * u], radius=6 * u, fill=mix(T["face"], -0.5))
    fm = font(12 * u)
    for i, name in enumerate(MODES):
        bx = sx0 + i * seg_w
        on = i == mode
        if on:
            d.rounded_rectangle([bx + 1 * u, sy0 + 1 * u, bx + seg_w - 1 * u, sy0 + seg_h - 1 * u], radius=4 * u, fill=rgb(T["lcd"]))
            d.rounded_rectangle([bx + 3 * u, sy0 + 2 * u, bx + seg_w - 3 * u, sy0 + 5 * u], radius=2 * u, fill=mix(T["lcd"], 0.4))
        d.text((bx + seg_w / 2, sy0 + seg_h / 2), name, font=fm, fill=rgb(T["lcd_ink"]) if on else mix(T["face"], 0.55), anchor="mm")
        L[f"mode{i}"] = box_div((bx, sy0, bx + seg_w, sy0 + seg_h), S)

    pr = 11 * u
    pcx, pcy = x1 - pr, y + row_h / 2
    d.ellipse([pcx - pr, pcy - pr, pcx + pr, pcy + pr], fill=mix(T["rubber"], 0.12))
    d.arc([pcx - pr * 0.55, pcy - pr * 0.55, pcx + pr * 0.55, pcy + pr * 0.55], 300, 240, fill=mix(T["face"], 0.6), width=int(2 * u))
    d.line([(pcx, pcy - pr * 0.7), (pcx, pcy - pr * 0.1)], fill=mix(T["face"], 0.6), width=int(2 * u))
    L["power"] = box_div((pcx - pr, pcy - pr, pcx + pr, pcy + pr), S)

    gx0, gx1 = sx0 + 3 * seg_w + 16 * u, pcx - pr - 22 * u
    if A:
        # 眼睛 = 指示灯：等回答时右眼变红
        ew, eh = 11 * u, 18 * u
        mid = (gx0 + gx1) / 2
        for i, ex in enumerate((mid - 22 * u, mid + 22 * u - ew)):
            col = (226, 65, 43) if (busy and i == 1) else rgb(INK)
            d.rectangle([ex, y + (row_h - eh) / 2, ex + ew, y + (row_h + eh) / 2], fill=col)
        L["led"] = box_div((mid - 22 * u, y, mid + 22 * u, y + row_h), S)
    else:
        if T["grille"] == "slots":
            n = 3
            for i in range(n):
                yy = y + 4 * u + i * (row_h - 6 * u) / n
                d.rounded_rectangle([gx0, yy, gx1, yy + (row_h - 6 * u) / n * 0.5], radius=3 * u, fill=mix(T["face"], -0.55))
        else:
            rr = 2.8 * u
            cols = max(1, int((gx1 - gx0) / (10 * u)))
            for i in range(3):
                for j in range(cols):
                    cx, cy = gx0 + 4 * u + j * 10 * u, y + 6 * u + i * 9 * u
                    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=mix(T["face"], -0.55))
        lx = gx1 + 8 * u
        col = (255, 70, 50) if busy else (90, 220, 120)
        d.ellipse([lx, y + row_h / 2 - 5 * u, lx + 10 * u, y + row_h / 2 + 5 * u], fill=col)
        d.ellipse([lx + 2 * u, y + row_h / 2 - 3 * u, lx + 5 * u, y + row_h / 2], fill=mix(col, 0.6))
        L["led"] = box_div((lx, y, lx + 10 * u, y + row_h), S)
    y += row_h + 8 * u

    # ---------- 背光屏 ----------
    lh = 44 * u
    inset(d, (x0, y, x1, y + lh), T["lcd"], 7 * u, 3 * u)
    for gx in range(int(x0 + 6 * u), int(x1 - 6 * u), max(1, int(3 * u))):
        d.line([(gx, y + 5 * u), (gx, y + lh - 4 * u)], fill=mix(T["lcd"], -0.04), width=1)
    L["lcd"] = box_div((x0 + 8 * u, y + 5 * u, x1 - 8 * u, y + lh - 4 * u), S)
    y += lh + 10 * u

    # ---------- 从下往上：铭牌 → 输入行 → 旋钮行，中间剩下的都给屏幕 ----------
    yb = fb - 8 * u
    plate_h = 22 * u if not A else 18 * u
    fb_big, fb_small = font(14 * u), font(8 * u, bold=False)
    if A:
        d.text(((x0 + x1) / 2, yb - plate_h / 2), "Clawkie · CLK-02", font=fb_small, fill=mix(T["face"], 0.55), anchor="mm")
    else:
        d.rounded_rectangle([x0 + 26 * u, yb - plate_h, x1 - 26 * u, yb], radius=5 * u, fill=mix(T["face"], -0.18))
        d.rounded_rectangle([x0 + 27 * u, yb - plate_h + 1 * u, x1 - 27 * u, yb - plate_h + 3 * u], radius=2 * u, fill=mix(T["face"], 0.1))
        d.text((x0 + 36 * u, yb - plate_h / 2), "Clawkie", font=fb_big, fill=rgb(T["brand"]), anchor="lm")
        room = (x1 - 36 * u) - (x0 + 36 * u + d.textlength("Clawkie", font=fb_big) + 12 * u)
        model = next((t for t in ("CLK-01 · 克讲机", "CLK-01") if d.textlength(t, font=fb_small) <= room), "")
        d.text((x1 - 36 * u, yb - plate_h / 2), model, font=fb_small, fill=rgb(T["brand"]), anchor="rm")
        for sx in (x0 + 12 * u, x1 - 12 * u):
            screw(d, sx, yb - plate_h / 2, 5 * u, T["face"])
    yb -= plate_h + 8 * u

    # 输入行：输入槽 · 麦克风（按住说话）· 发送
    ih = 36 * u
    send_w, mic_w = 62 * u, ih
    inset(d, (x0, yb - ih, x1 - send_w - mic_w - 16 * u, yb), T["screen"], 7 * u, 3 * u)
    L["input"] = box_div((x0 + 9 * u, yb - ih + 6 * u, x1 - send_w - mic_w - 25 * u, yb - 5 * u), S)
    mx0 = x1 - send_w - mic_w - 8 * u
    mcx, mcy, mr = mx0 + mic_w / 2, yb - ih / 2, ih / 2
    d.ellipse([mcx - mr, mcy - mr + 2 * u, mcx + mr, mcy + mr + 2 * u], fill=mix(T["rubber"], -0.3))
    d.ellipse([mcx - mr, mcy - mr, mcx + mr, mcy + mr], fill=mix(T["rubber"], 0.1))
    d.ellipse([mcx - mr * 0.75, mcy - mr * 0.8, mcx + mr * 0.75, mcy - mr * 0.3], fill=mix(T["rubber"], 0.25))
    mic = mix(T["face"], 0.7) if A else rgb("#ffffff")
    d.rounded_rectangle([mcx - 4 * u, mcy - 9 * u, mcx + 4 * u, mcy + 3 * u], radius=4 * u, fill=mic)
    d.arc([mcx - 7 * u, mcy - 6 * u, mcx + 7 * u, mcy + 7 * u], 0, 180, fill=mic, width=int(1.8 * u))
    d.line([(mcx, mcy + 7 * u), (mcx, mcy + 10 * u)], fill=mic, width=int(1.8 * u))
    L["mic"] = box_div((mcx - mr, mcy - mr, mcx + mr, mcy + mr), S)
    bx0 = x1 - send_w
    d.rounded_rectangle([bx0, yb - ih + 2 * u, x1, yb + 2 * u], radius=ih / 2, fill=mix(T["accent"], -0.4))
    vgrad(img, (bx0, yb - ih, x1, yb), mix(T["accent"], 0.18), mix(T["accent"], -0.1), ih / 2)
    d.rounded_rectangle([bx0 + 8 * u, yb - ih + 4 * u, x1 - 8 * u, yb - ih + 8 * u], radius=3 * u, fill=mix(T["accent"], 0.4))
    L["ptt"] = box_div((bx0, yb - ih, x1, yb), S)
    yb -= ih + 10 * u

    if knobs:
        kr = 13 * u
        kh = kr * 2 + 14 * u
        ks = []
        for i in range(4):
            cx = x0 + (x1 - x0) * (i + 0.5) / 4
            cy = yb - kh + kr
            knob(d, cx - 22 * u, cy, kr, T["knob"], T["accent"] if T["knob"] != T["accent"] else "#ffffff", knob_angles[i])
            ks.append(box_div((cx - 22 * u - kr * 1.3, cy - kr * 1.3, cx + 34 * u, cy + kr * 1.4), S))
            L[f"knob{i}_label"] = ((cx - 22 * u + kr + 5 * u) / S, cy / S)
        L["knobs"] = ks
        yb -= kh + 6 * u
    else:
        L["knobs"] = []

    # ---------- 屏幕 ----------
    yb = max(yb, y + 60 * u)
    inset(d, (x0, y, x1, yb), (25, 25, 30), 11 * u, 3 * u)
    d.rounded_rectangle([x0 + 5 * u, y + 5 * u, x1 - 5 * u, yb - 5 * u], radius=7 * u, fill=rgb(T["screen"]))
    L["screen"] = box_div((x0 + 10 * u, y + 8 * u, x1 - 8 * u, yb - 8 * u), S)

    out = img.resize((w, h), Image.LANCZOS)
    m = sil.resize((w, h), Image.LANCZOS).point(lambda v: 255 if v > 110 else 0)
    out = Image.composite(out, Image.new("RGB", (w, h), KEY), m)
    return out, L


if __name__ == "__main__":
    # 出一张六种机身的预览图：python skin.py 预览.png
    import sys
    cells = [("r", 0, 2, 20, 12, "#d97757"), ("r", 4, 5, 2, 3, INK), ("r", 14, 5, 2, 3, INK), ("r", 3, -3, 4, 5, "#d97757"), ("r", 13, -3, 4, 5, "#d97757")]
    sheet = Image.new("RGB", (len(ORDER) * 300, 500), (240, 236, 226))
    for i, t in enumerate(ORDER):
        im, _ = render(290, 490, 0.75, t, cells, mode=i % 3)
        sheet.paste(im, (i * 300 + 5, 5))
    sheet.save(sys.argv[1] if len(sys.argv) > 1 else "preview.png")
