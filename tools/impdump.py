"""Walk a Just Me and My Dad .IMP file (Big Tuna's earlier "IW" player) and export it.

Layout:
  0   u16 0x0063, u16 0x7AB7
  4   u16 count
  6   count x 19 bytes { u8 len, name (padded to 10), u32 size, u32 offset }
Records are <name>.<type>: C palette, A film, P picture, S sound.

Usage: impdump.py FILE.IMP [OUTDIR]
"""
import os
import struct
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from im2dump import write_png  # noqa: E402


def read_entries(d):
    if d[:4] != b'\x63\x00\xb7\x7a':
        raise ValueError('not an IMP file')
    n = struct.unpack_from('<H', d, 4)[0]
    out = []
    for i in range(n):
        p = 6 + 19 * i
        name = d[p + 1:p + 1 + d[p]].decode('latin1')
        size, off = struct.unpack_from('<II', d, p + 11)
        out.append((name, size, off))
    return out


def parse_palette(b):
    """One leading byte, then 256 x RGB."""
    return [tuple(b[1 + i:4 + i]) for i in range(0, 768, 3)]


def decode_picture(b):
    """u16 w, u16 h, u16 flags (always 0), then per row u16 length + RLE:
    00 ends the row, 01-7F literal bytes, 80-FF repeat the next byte (n & 7F) times.
    Returns (w, h, flags, pixels, mask, bytes used); unwritten pixels have mask 0."""
    w, h, flags = struct.unpack_from('<HHH', b, 0)
    pix = bytearray(w * h)
    mask = bytearray(w * h)
    p = 6
    for y in range(h):
        n = struct.unpack_from('<H', b, p)[0]
        row = b[p + 2:p + 2 + n]
        p += 2 + n
        x = 0
        q = 0
        base = y * w
        while q < len(row):
            c = row[q]
            q += 1
            if c == 0:
                break
            if c < 0x80:
                pix[base + x:base + x + c] = row[q:q + c]
                mask[base + x:base + x + c] = b'\1' * c
                q += c
                x += c
            else:
                c &= 0x7F
                pix[base + x:base + x + c] = bytes([row[q]]) * c
                mask[base + x:base + x + c] = b'\1' * c
                q += 1
                x += c
            if x > w:
                raise ValueError('row %d overruns width %d' % (y, w))
    return w, h, flags, bytes(pix), bytes(mask), p


def parse_sound(b):
    """"snd8", u16 rate, u16 0, unsigned 8-bit PCM."""
    if b[:4] != b'snd8':
        raise ValueError('not snd8')
    rate = struct.unpack_from('<H', b, 4)[0]
    return rate, b[8:]


def main():
    path = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else None
    d = open(path, 'rb').read()
    ents = read_entries(d)
    pal = None
    for name, size, off in ents:
        if name.endswith('.C'):
            pal = parse_palette(d[off:off + size])
    if pal is None:
        pal = [(g, g, g) for g in range(256)]
    if outdir:
        os.makedirs(outdir, exist_ok=True)
    print('%s: %d records' % (path, len(ents)))
    for name, size, off in ents:
        b = d[off:off + size]
        kind = name.rsplit('.', 1)[-1]
        info = ''
        safe = name.replace('.', '_')
        if kind == 'P':
            w, h, flags, pix, mask, used = decode_picture(b)
            info = '%dx%d flags=%d%s' % (w, h, flags, '' if used == size else ' LEFTOVER %d' % (size - used))
            if outdir:
                write_png(os.path.join(outdir, safe + '.png'), w, h, pix, mask, pal)
        elif kind == 'S':
            rate, pcm = parse_sound(b)
            info = '%d Hz %.2fs' % (rate, len(pcm) / rate)
            if outdir:
                with wave.open(os.path.join(outdir, safe + '.wav'), 'wb') as wv:
                    wv.setnchannels(1)
                    wv.setsampwidth(1)
                    wv.setframerate(rate)
                    wv.writeframes(pcm)
        else:
            info = b[:24].hex()
            if outdir:
                open(os.path.join(outdir, safe + '.bin'), 'wb').write(b)
        print('%-12s %8d @%-9d %s' % (name, size, off, info))


if __name__ == '__main__':
    main()
