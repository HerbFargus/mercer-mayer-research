"""Decode the score (type 4 "film") of a Big Tuna .IM2 file.

The score is a delta stream of film operations (LMMM.EXE FUN_004034f0, preloader
FUN_00403000). Each frame is a run of ops ended by 0x11 (next frame) or 0x0d n
(n frames). Member and script numbers are resource indices + 1 (the player adds
a dummy entry 0). V = big-endian base-128 varint, sV = varint with the sign in
bit 0, s = u8-length string.

Usage: im2score.py FILE.IM2 [score resource index]
"""
import struct
import sys

sys.path.insert(0, __import__('os').path.dirname(__file__))
from im2dump import read_entries, parse_labels  # noqa: E402
from im2script import read_varint, parse_symbols  # noqa: E402


def read_svarint(b, p):
    v, p = read_varint(b, p)
    return (-(v >> 1) if v & 1 else v >> 1), p


def read_pstr(b, p):
    n = b[p]
    return b[p + 1:p + 1 + n].decode('latin1'), p + 1 + n


def decode_score(b, terminators=False):
    """Yields (frame, op, args); with terminators, also (frame, 'end', (n,)) where a frame ends."""
    p = 0
    frame = 1
    while p < len(b):
        op = b[p]
        p += 1
        if op == 0x00:
            spr, p = read_varint(b, p)
            s, p = read_pstr(b, p)
            yield frame, 'spritename', (spr, s)
        elif op == 0x01:
            yield frame, 'cursor', (b[p],)
            p += 1
        elif op == 0x02:
            spr, p = read_varint(b, p)
            yield frame, 'clear', (spr,)
        elif op == 0x03:
            s, p = read_pstr(b, p)
            yield frame, 'goto', (s,)
        elif op == 0x04:
            m, p = read_pstr(b, p)
            s, p = read_pstr(b, p)
            yield frame, 'gomovie', (m, s)
        elif op == 0x05:
            s, p = read_pstr(b, p)
            yield frame, 'comment', (s,)
        elif op == 0x06:
            r, p = read_varint(b, p)
            yield frame, 'palette', (r - 1,)
        elif op == 0x07:
            spr, p = read_varint(b, p)
            mem, p = read_varint(b, p)
            x, p = read_svarint(b, p)
            y, p = read_svarint(b, p)
            yield frame, 'sprite', (spr, mem - 1, x, y)
        elif op == 0x08:
            spr, p = read_varint(b, p)
            scr, p = read_varint(b, p)
            yield frame, 'script', (spr, scr - 1 if scr else None)
        elif op in (0x09, 0x0a):
            ch = b[p]
            mem, p = read_varint(b, p + 1)
            yield frame, 'sound%d' % (op - 8), (ch, mem - 1 if mem else None)
        elif op == 0x0b:
            yield frame, 'tempo', (b[p],)
            p += 1
        elif op == 0x0c:
            ch, vol = b[p], b[p + 1]
            fade, p = read_varint(b, p + 2)
            yield frame, 'volume', (ch, vol, fade)
        elif op == 0x0d:
            n, p = read_varint(b, p)
            yield frame, 'end' if terminators else 'wait', (n,)
            frame += n
        elif op == 0x0e:
            x, p = read_svarint(b, p)
            y, p = read_svarint(b, p)
            w, p = read_varint(b, p)
            h, p = read_varint(b, p)
            s, p = read_pstr(b, p)
            yield frame, 'video', (x, y, w, h, s)
        elif op == 0x0f:
            ch = b[p]
            v, p = read_varint(b, p + 1)
            yield frame, 'chanprop', (ch, v)
        elif op == 0x10:
            a, p = read_varint(b, p)
            c, p = read_varint(b, p)
            yield frame, 'stage', (a, c)
        elif op == 0x11:
            if terminators:
                yield frame, 'end', (1,)
            frame += 1
        elif op == 0x14:
            yield frame, 'waitsound', (b[p],)
            p += 1
        elif op == 0x16:
            a, p = read_varint(b, p)
            c, p = read_varint(b, p)
            yield frame, 'origin', (a, c)
        else:
            raise ValueError('unknown film op %02x at %d' % (op, p - 1))


def main():
    path = sys.argv[1]
    d = open(path, 'rb').read()
    ents = read_entries(d)
    labels = {}
    for i, ty, size, off in ents:
        if ty == 9:
            labels = dict(parse_labels(d[off:off + size]))
    scores = [(i, d[off:off + size]) for i, ty, size, off in ents if ty == 4]
    if len(sys.argv) > 2:
        scores = [s for s in scores if s[0] == int(sys.argv[2])]
    for i, b in scores:
        print('; score %d (%d bytes)' % (i, len(b)))
        last = None
        for frame, op, args in decode_score(b):
            if frame != last:
                print('frame %d%s' % (frame, '  [%s]' % labels[frame] if frame in labels else ''))
                last = frame
            print('   %-10s %s' % (op, ' '.join(map(str, args))))


if __name__ == '__main__':
    main()
