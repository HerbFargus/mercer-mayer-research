"""Decode the film (.A record) of a Just Me and My Dad .IMP file.

A film (DAD.EXE FUN_1008_030b) is a 19-byte header then 19-byte records:
  header: u16 record count, u8 channel count, u8 b3, 15 more bytes
  record: u8 type, u8 channel, u8 b2, u8 b3, s16 a, s16 b, s16 c, u8 len + name (8)

Usage: impfilm.py FILE.IMP [--summary]
"""
import collections
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from impdump import read_entries  # noqa: E402

TYPES = {2: 'pic', 4: 'snd', 5: 'stop', 6: 'label', 7: 'btn', 9: 'flag', 10: 'act10'}


def read_film(d):
    for name, size, off in read_entries(d):
        if name.endswith('.A'):
            b = d[off:off + size]
            count, channels, h3 = struct.unpack_from('<HBB', b, 0)
            recs = []
            for i in range(count):
                p = 19 + 19 * i
                t, ch, b2, b3, a, bb, c = struct.unpack_from('<BBBBhhh', b, p)
                nm = b[p + 11:p + 11 + min(b[p + 10], 8)].decode('latin1')
                recs.append((t, ch, b2, b3, a, bb, c, nm))
            return name, b[:19], channels, recs, size == 19 + 19 * count
    return None


def main():
    d = open(sys.argv[1], 'rb').read()
    name, head, channels, recs, exact = read_film(d)
    print('; %s: %d records, %d channels, header %s, size %s' % (name, len(recs), channels, head.hex(), 'exact' if exact else 'MISMATCH'))
    if '--summary' in sys.argv:
        c = collections.Counter(r[0] for r in recs)
        print(dict(c))
        return
    for i, (t, ch, b2, b3, a, bb, c, nm) in enumerate(recs, 1):
        print('%5d %-6s ch%-3d b2=%02x b3=%02x %6d %6d %6d %s' % (i, TYPES.get(t, 't%d' % t), ch, b2, b3, a, bb, c, nm))


if __name__ == '__main__':
    main()
