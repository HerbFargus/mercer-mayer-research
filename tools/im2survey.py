"""Run the score and script decoders over every IM2 file; print op inventories and failures.

Usage: im2survey.py GAMEDIR...
"""
import collections
import glob
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
from im2dump import read_entries  # noqa: E402
from im2script import parse_symbols, disasm, OPS  # noqa: E402
from im2score import decode_score  # noqa: E402

for game in sys.argv[1:]:
    film = collections.Counter()
    ops = collections.Counter()
    builtins = collections.Counter()
    fails = []
    nscore = nscript = nhandler = 0
    events = collections.Counter()
    for f in sorted(glob.glob(os.path.join(game, '*.IM2'))):
        d = open(f, 'rb').read()
        ents = read_entries(d)
        syms = []
        for i, ty, size, off in ents:
            if ty == 2:
                syms = parse_symbols(d[off:off + size])
        for i, ty, size, off in ents:
            b = d[off:off + size]
            try:
                if ty == 4:
                    nscore += 1
                    for _, op, _ in decode_score(b):
                        film[op] += 1
                elif ty == 1:
                    nscript += 1
                    # walk the behaviour chain: u32 symbol, u32 next offset, code
                    p = 0
                    starts = set()
                    while True:
                        sym, nxt = struct.unpack_from('<II', b, p)
                        events[syms[sym][0] if sym < len(syms) else '?%d' % sym] += 1
                        starts.add(p + 8)
                        if not nxt:
                            break
                        p = nxt
                    for name, h in syms:
                        if h and (h >> 16) == i + 1:
                            starts.add(h & 0xFFFF)
                    for s in starts:
                        nhandler += 1
                        for o, text in disasm(b, s, syms):
                            if text.startswith('??'):
                                raise ValueError('bad opcode at %d: %s' % (o, text))
                            ops[text.split()[0]] += 1
                            if text.startswith(('func', 'proc', 'set ')):
                                builtins[text] += 1
            except Exception as e:  # noqa: BLE001
                fails.append('%s #%d type %d: %s' % (os.path.basename(f), i, ty, e))
    print('==', game)
    print('  scores %d, scripts %d, handlers %d, failures %d' % (nscore, nscript, nhandler, len(fails)))
    for x in fails[:8]:
        print('   FAIL', x)
    print('  film ops:', dict(film.most_common()))
    print('  opcodes:', dict(ops.most_common()))
    print('  events:', dict(events.most_common(20)))
    print('  builtins:', ', '.join('%s=%d' % kv for kv in sorted(builtins.items())))
