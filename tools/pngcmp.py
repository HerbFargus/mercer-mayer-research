"""Compare PNGs pixel by pixel in RGB (palette or truecolour, 8-bit only).

Usage: pngcmp.py A.png B.png [A2.png B2.png ...]   exit 1 if any pair differs
"""
import struct
import sys
import zlib


def read_png(path):
    d = open(path, 'rb').read()
    p = 8
    idat = b''
    pal = None
    while p < len(d):
        n, t = struct.unpack_from('>I4s', d, p)
        body = d[p + 8:p + 8 + n]
        if t == b'IHDR':
            w, h, depth, ctype = struct.unpack_from('>IIBB', body)
        elif t == b'PLTE':
            pal = [tuple(body[i:i + 3]) for i in range(0, len(body), 3)]
        elif t == b'IDAT':
            idat += body
        p += 12 + n
    if depth != 8:
        raise ValueError('%s: bit depth %d' % (path, depth))
    bpp = {3: 1, 2: 3, 6: 4, 0: 1}[ctype]
    raw = zlib.decompress(idat)
    stride = w * bpp
    rows = []
    prev = bytearray(stride)
    q = 0
    for _ in range(h):
        f = raw[q]
        line = bytearray(raw[q + 1:q + 1 + stride])
        q += 1 + stride
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line)
        prev = line
    px = []
    for line in rows:
        for x in range(w):
            if ctype == 3:
                px.append(pal[line[x]])
            elif ctype == 0:
                px.append((line[x],) * 3)
            else:
                px.append(tuple(line[x * bpp:x * bpp + 3]))
    return w, h, px


def main():
    bad = 0
    args = sys.argv[1:]
    for a, b in zip(args[::2], args[1::2]):
        wa, ha, pa = read_png(a)
        wb, hb, pb = read_png(b)
        if (wa, ha) != (wb, hb):
            print('DIFF size %s %dx%d vs %dx%d' % (a, wa, ha, wb, hb))
            bad += 1
            continue
        diff = [i for i in range(len(pa)) if pa[i] != pb[i]]
        if diff:
            i = diff[0]
            print('DIFF %s: %d pixels, first at (%d,%d) %s vs %s' % (a, len(diff), i % wa, i // wa, pa[i], pb[i]))
            bad += 1
        else:
            print('same %s' % a)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
