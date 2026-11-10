"""Reference renderer for Dad's films: applies a film's cell records up to a record
index (no jumps) and writes the 640x480 screen as a PNG.

Same model as the engine: 512x384 stage at (64,48), pictures at (a, 384 - b - h),
higher layer (c) drawn first, index 255 and unwritten pixels transparent.

Usage: imprender.py FILE.IMP OUT.png RECORD [RECORD...]   (OUT gets -NNNN per record)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from impdump import read_entries, parse_palette, decode_picture  # noqa: E402
from impfilm import read_film  # noqa: E402
from im2dump import write_png  # noqa: E402

W, H, SX, SY, SW, SH = 640, 480, 64, 48, 512, 384


def main():
    path, out = sys.argv[1], sys.argv[2]
    d = open(path, 'rb').read()
    ents = {n: (s, o) for n, s, o in read_entries(d)}
    pal = parse_palette(d[ents['macpal.C'][1]:][:769])
    recs = read_film(d)[3]
    pics = {}
    stem, ext = os.path.splitext(out)
    for target in sorted(int(a) for a in sys.argv[3:]):
        cells = {}
        for t, ch, b2, b3, a, b, c, nm in recs[:target]:
            if t == 0:
                cells.pop(ch, None)
            elif t == 2:
                cells[ch] = (nm, a, b, c)
        stage = bytearray(W * H)
        for ch in sorted(cells, key=lambda k: (-cells[k][3], k)):
            nm, a, b, c = cells[ch]
            if nm not in pics:
                s, o = ents[nm + '.P']
                pics[nm] = decode_picture(d[o:o + s])
            w, h, f, pix, mask, used = pics[nm]
            x0, y0 = SX + a, SY + SH - b - h
            for y in range(h):
                dy = y0 + y
                if not SY <= dy < SY + SH:
                    continue
                for x in range(w):
                    dx = x0 + x
                    i = y * w + x
                    if SX <= dx < SX + SW and mask[i] and pix[i] != 255:
                        stage[dy * W + dx] = pix[i]
        write_png('%s-%04d%s' % (stem, target, ext), W, H, stage, b'\1' * (W * H), pal)


if __name__ == '__main__':
    main()
