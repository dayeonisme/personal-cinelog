#!/usr/bin/env python3
"""Cinelog 앱 아이콘(1024px PNG) 생성 — 다크 슬레이트 + 클래퍼보드.
사용법: python3 make_icon.py <출력경로.png>"""
import sys
from PIL import Image, ImageDraw

SS = 4096   # 슈퍼샘플
OUT = 1024  # 최종 크기


def vgradient(size, top, bottom):
    img = Image.new("RGB", (1, size), top)
    px = img.load()
    for y in range(size):
        t = y / (size - 1)
        px[0, y] = tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
    return img.resize((size, size))


def draw():
    base = Image.new("RGBA", (SS, SS), (0, 0, 0, 0))
    grad = vgradient(SS, (0x2A, 0x2C, 0x38), (0x14, 0x15, 0x1C)).convert("RGBA")  # 다크 슬레이트
    mask = Image.new("L", (SS, SS), 0)
    m = int(SS * 0.085)
    r = int((SS - 2 * m) * 0.2235)
    ImageDraw.Draw(mask).rounded_rectangle([m, m, SS - m, SS - m], radius=r, fill=255)
    base.paste(grad, (0, 0), mask)

    d = ImageDraw.Draw(base)
    white = (245, 245, 248, 255)
    dark = (0x1A, 0x1B, 0x22, 255)
    # 보드 본체
    bx0, by0, bx1, by1 = int(SS*0.22), int(SS*0.46), int(SS*0.78), int(SS*0.74)
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=int(SS*0.03), fill=white)
    # 클래퍼 바 (기울어진 흰색 평행사변형)
    bar_top, bar_h, skew = int(SS*0.30), int(SS*0.12), int(SS*0.06)
    d.polygon([(bx0, bar_top), (bx1, bar_top - skew),
               (bx1, bar_top - skew + bar_h), (bx0, bar_top + bar_h)], fill=white)
    # 줄무늬 (어두운 평행사변형)
    n, span = 5, bx1 - bx0
    for i in range(n):
        x0 = bx0 + int(span * (i + 0.12) / n)
        x1 = bx0 + int(span * (i + 0.62) / n)
        ya = bar_top - int(skew * (x0 - bx0) / span)
        yb = bar_top - int(skew * (x1 - bx0) / span)
        d.polygon([(x0, ya), (x1, yb), (x1, yb + bar_h), (x0, ya + bar_h)], fill=dark)
    return base


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "cinelog_1024.png"
    draw().resize((OUT, OUT), Image.LANCZOS).save(out)
    print(out)
