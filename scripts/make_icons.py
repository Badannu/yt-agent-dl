#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_icons.py —— 生成 Chrome 扩展所需的 16/32/48/128 四尺寸图标。

上架 Chrome 网上应用店必须有图标，所以这里用纯标准库手写 PNG，
不依赖 Pillow / cairo 之类的第三方包。

图案：蓝色圆角方块 + 白色向下箭头（表示"把 cookie 导出到本地"）。
用 4 倍超采样再降采样，边缘不会锯齿。

用法：
    python make_icons.py
"""

import os
import zlib
import struct

BG = (47, 111, 237, 255)      # 蓝
FG = (255, 255, 255, 255)     # 白
SS = 4                        # 超采样倍数


def write_png(path, w, h, rows):
    raw = bytearray()
    for row in rows:
        raw.append(0)  # filter type: None
        for px in row:
            raw += bytes(px)

    def chunk(typ, data):
        return (struct.pack(">I", len(data)) + typ + data
                + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF))

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


def rounded_rect(x, y, size, radius):
    """点 (x,y) 归一化到 [0,1]，判断是否在圆角矩形内。"""
    r = radius
    if x < r and y < r:
        return (x - r) ** 2 + (y - r) ** 2 <= r * r
    if x > 1 - r and y < r:
        return (x - (1 - r)) ** 2 + (y - r) ** 2 <= r * r
    if x < r and y > 1 - r:
        return (x - r) ** 2 + (y - (1 - r)) ** 2 <= r * r
    if x > 1 - r and y > 1 - r:
        return (x - (1 - r)) ** 2 + (y - (1 - r)) ** 2 <= r * r
    return 0 <= x <= 1 and 0 <= y <= 1


def in_triangle(px, py, tri):
    """叉积法判断点是否在三角形内。"""
    (x1, y1), (x2, y2), (x3, y3) = tri
    d1 = (px - x2) * (y1 - y2) - (x1 - x2) * (py - y2)
    d2 = (px - x3) * (y2 - y3) - (x2 - x3) * (py - y3)
    d3 = (px - x1) * (y3 - y1) - (x3 - x1) * (py - y1)
    has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
    has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
    return not (has_neg and has_pos)


def is_arrow(x, y):
    # 竖杆
    if 0.43 <= x <= 0.57 and 0.24 <= y <= 0.56:
        return True
    # 箭头三角
    return in_triangle(x, y, ((0.50, 0.80), (0.25, 0.53), (0.75, 0.53)))


def render(size):
    """先按 SS 倍渲染，再 box filter 降采样。"""
    big = size * SS
    acc = [[[0, 0, 0, 0] for _ in range(size)] for _ in range(size)]
    for by in range(big):
        y = (by + 0.5) / big
        oy = by // SS
        for bx in range(big):
            x = (bx + 0.5) / big
            ox = bx // SS
            if not rounded_rect(x, y, 1, 0.22):
                continue
            col = FG if is_arrow(x, y) else BG
            for i in range(4):
                acc[oy][ox][i] += col[i]
    n = SS * SS
    # acc[y][x] 是长度为 4 的 [r,g,b,a] 累加值
    return [[tuple(c // n for c in px) for px in row] for row in acc]


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(os.path.dirname(here), "chrome-extension", "icons")
    os.makedirs(out_dir, exist_ok=True)
    for size in (16, 32, 48, 128):
        path = os.path.join(out_dir, "icon%d.png" % size)
        write_png(path, size, size, render(size))
        print("生成 %s (%d x %d)" % (path, size, size))
    print("\n记得确认 manifest.json 里有 icons 字段：")
    print('  "icons": {"16":"icons/icon16.png","32":"icons/icon32.png",'
          '"48":"icons/icon48.png","128":"icons/icon128.png"}')


if __name__ == "__main__":
    main()
