"""Walk a Big Tuna .IM2 file (the "Implay" player's movie format) and export it.

Layout (from LMMM.EXE, FUN_00404e10):
  0  u32 LE  'IM20' (bytes "02MI")
  4  u32 LE  entry count N
  ...        entry data
  EOF-9N     directory: N x (u8 type, u32 LE size, u32 LE offset)

Usage: im2dump.py FILE.IM2 [OUTDIR]   (OUTDIR: write PNGs, WAVs and raw blobs)
"""
import os
import struct
import sys
import wave
import zlib

TYPES = {
    0: 'empty', 1: 'script', 2: 'symbols', 3: 'castnames', 4: 'score',
    5: 'palette', 6: 'bitmap', 7: 'sound', 8: 'type8', 9: 'labels',
}


def read_entries(d):
    if d[:4] != b'02MI':
        raise ValueError('not an IM2 file')
    n = struct.unpack_from('<I', d, 4)[0]
    t = len(d) - 9 * n
    out = []
    for i in range(n):
        ty, size, off = struct.unpack_from('<BII', d, t + 9 * i)
        out.append((i, ty, size, off))
    return out


def parse_labels(b):
    """Director VWLB layout, big-endian: count, (frame, offset) x count, total len, names."""
    n = struct.unpack_from('>H', b, 0)[0]
    pairs = [struct.unpack_from('>HH', b, 2 + 4 * i) for i in range(n + 1)]
    names = b[2 + 4 * (n + 1):]
    return [(pairs[i][0], names[pairs[i][1]:pairs[i + 1][1]].decode('latin1')) for i in range(n)]


def parse_names(b):
    """Name table (types 2 and 3): u32 count, count x {u32 name start, u32 value}, u32 names end, names.
    Type 3 is sorted case-insensitively (the player binary-searches it)."""
    n = struct.unpack_from('<I', b, 0)[0]
    ents = [struct.unpack_from('<II', b, 4 + 8 * i) for i in range(n)]
    end = struct.unpack_from('<I', b, 4 + 8 * n)[0]
    return [(b[s:(ents[i + 1][0] if i + 1 < n else end)].decode('latin1'), v) for i, (s, v) in enumerate(ents)]


def parse_palette(b):
    return [tuple(b[i:i + 3]) for i in range(0, 768, 3)]


def decode_bitmap(b, hdr=12):
    """Bitmap header (FUN_004055d0): u16 w, u16 h, u8 format, u8 opaque, s16 regx, s16 regy, u16 extra.
    Just Me and My Mom (1996) has a 10-byte header without the extra field.
    Formats: 0 RLE, 1 raw 8-bit, 2 raw 16-bit, 3 LZ. Rows are stored top first.
    Returns (w, h, fmt, opaque, regx, regy, extra, pixels, mask, bytes used); 16-bit pixels are u16 values."""
    w, h, fmt, opaque, rx, ry = struct.unpack_from('<HHBBhh', b, 0)
    extra = struct.unpack_from('<H', b, 10)[0] if hdr == 12 else 0
    p = hdr
    if fmt == 1:
        pix = b[p:p + w * h]
        mask = bytes(1 if opaque == 1 or c else 0 for c in pix)
        return w, h, fmt, opaque, rx, ry, extra, pix, mask, p + w * h
    if fmt == 2:
        pix = struct.unpack_from('<%dH' % (w * h), b, p)
        return w, h, fmt, opaque, rx, ry, extra, pix, b'\1' * (w * h), p + 2 * w * h
    if fmt == 3:
        out = bytearray()
        while len(out) < w * h:
            c = b[p]
            if c == 2:                        # escaped literal
                out.append(b[p + 1])
                p += 2
            elif 3 <= c <= 10:                # copy c bytes from (next + 1) back
                dist = b[p + 1] + 1
                for _ in range(c):
                    out.append(out[-dist])
                p += 2
            else:
                out.append(c)
                p += 1
        mask = bytes(1 if opaque == 1 or c else 0 for c in out)
        return w, h, fmt, opaque, rx, ry, extra, bytes(out), mask, p
    pix = bytearray(w * h)
    mask = bytearray(w * h)
    for y in range(h):
        x = 0
        row = y * w
        while True:
            c = b[p]
            p += 1
            if c == 0:
                break
            if c < 0x80:                      # literal
                pix[row + x:row + x + c] = b[p:p + c]
                mask[row + x:row + x + c] = b'\1' * c
                p += c
                x += c
            elif c < 0xC0:                    # run of one byte
                n = (c & 0x3F) + 1
                pix[row + x:row + x + n] = bytes([b[p]]) * n
                mask[row + x:row + x + n] = b'\1' * n
                p += 1
                x += n
            else:                             # transparent skip
                x += (c & 0x3F) + 1
            if x > w:
                raise ValueError('row %d overruns width %d' % (y, w))
    if opaque == 1:
        mask = b'\1' * (w * h)
    return w, h, fmt, opaque, rx, ry, extra, bytes(pix), bytes(mask), p


def bitmap_header_size(d, ents):
    """12 bytes from Smelly on, 10 in Mom: whichever decodes every bitmap exactly."""
    bitmaps = [(size, off) for _, ty, size, off in ents if ty == 6]
    for hdr in (12, 10):
        try:
            if all(decode_bitmap(d[off:off + size], hdr)[-1] == size for size, off in bitmaps):
                return hdr
        except (ValueError, IndexError):
            pass
    raise ValueError('bitmaps decode with neither header size')


def write_png(path, w, h, pix, mask, pal):
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w):
            i = y * w + x
            if pal is None:                   # 16-bit RGB555
                v = pix[i]
                r, g, b = (v >> 7) & 0xF8, (v >> 2) & 0xF8, (v << 3) & 0xF8
            else:
                r, g, b = pal[pix[i]]
            raw += bytes((r, g, b, 255 if mask[i] else 0))

    def chunk(t, data):
        c = struct.pack('>I', len(data)) + t + data
        return c + struct.pack('>I', zlib.crc32(t + data) & 0xffffffff)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)))
        f.write(chunk(b'IDAT', zlib.compress(bytes(raw), 6)))
        f.write(chunk(b'IEND', b''))


def parse_sound(b):
    """u8 bits, u16 LE rate, then unsigned PCM."""
    bits, rate = struct.unpack_from('<BH', b, 0)
    return bits, rate, b[3:]


def main():
    path = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else None
    d = open(path, 'rb').read()
    ents = read_entries(d)
    pal = None
    for i, ty, size, off in ents:
        if ty == 5:
            pal = parse_palette(d[off:off + size])
    if pal is None:
        pal = [(g, g, g) for g in range(256)]
    hdr = bitmap_header_size(d, ents)
    if outdir:
        os.makedirs(outdir, exist_ok=True)
    print('%s: %d entries, %d-byte bitmap header' % (path, len(ents), hdr))
    for i, ty, size, off in ents:
        if ty == 0:
            continue
        b = d[off:off + size]
        name = TYPES.get(ty, 'type%d' % ty)
        info = ''
        if ty == 9:
            info = ' '.join('%d:%s' % fl for fl in parse_labels(b))
        elif ty in (2, 3):
            t = parse_names(b)
            if ty == 2:   # value = handler (resource+1)<<16 | offset
                info = '%d symbols: ' % len(t) + ' '.join(n for n, _ in t[:12])
            else:         # value = Lingo member number = directory index - 6
                info = '%d names: ' % len(t) + ' '.join('%s=%d' % (n, v + 6) for n, v in t[:8])
            if outdir:
                open(os.path.join(outdir, '%03d.%s.bin' % (i, name)), 'wb').write(b)
        elif ty == 6:
            w, h, fmt, opaque, rx, ry, extra, pix, mask, used = decode_bitmap(b, hdr)
            info = '%dx%d fmt=%d opaque=%d reg=(%d,%d) extra=%d%s' % (
                w, h, fmt, opaque, rx, ry, extra, '' if used == size else ' LEFTOVER %d' % (size - used))
            if outdir:
                write_png(os.path.join(outdir, '%03d.png' % i), w, h, pix, mask, None if fmt == 2 else pal)
        elif ty == 7:
            bits, rate, pcm = parse_sound(b)
            info = '%d-bit %d Hz %.2fs' % (bits, rate, len(pcm) / rate)
            if outdir:
                with wave.open(os.path.join(outdir, '%03d.wav' % i), 'wb') as wv:
                    wv.setnchannels(1)
                    wv.setsampwidth(1)
                    wv.setframerate(rate)
                    wv.writeframes(pcm)
        else:
            info = b[:24].hex()
            if outdir:
                open(os.path.join(outdir, '%03d.%s.bin' % (i, name)), 'wb').write(b)
        print('%4d %-9s %8d @%-9d %s' % (i, name, size, off, info))


if __name__ == '__main__':
    main()
