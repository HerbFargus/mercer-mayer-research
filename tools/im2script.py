"""Disassemble the Implay bytecode in a Big Tuna .IM2 file.

Interpreter: LMMM.EXE FUN_00408c30. A stack machine; values are tagged words:
0 = void, odd = integer (n*2+1), even = pointer to an object
(0 list, 1 proplist (points/rects use loch/locv/left/top/right/bottom), 3 string).
Operands: V = big-endian base-128 varint (high bit = more), J = s16 LE jump,
relative to the byte after the opcode.

Type 2 resource = the movie's symbol table:
  u32 count, count x {u32 name start, u32 handler}, u32 names end, names.
  handler = (resource index + 1) << 16 | byte offset into that script (0 = no handler).
Symbols are interned globally by name and also hold global variable values.

Usage: im2script.py FILE.IM2 [--raw]
"""
import struct
import sys

sys.path.insert(0, __import__('os').path.dirname(__file__))
from im2dump import read_entries, parse_names as parse_symbols  # noqa: E402

# name, operand kinds
OPS = {
    0x01: ('add', ''), 0x02: ('and', ''), 0x03: ('jz', 'J'), 0x04: ('call', 'SV'),
    0x05: ('retval', ''), 0x06: ('func', 'B'), 0x07: ('proc', 'B'), 0x08: ('concat', ''),
    0x0b: ('div', ''), 0x0c: ('eq', ''), 0x0d: ('ge', ''), 0x0e: ('go', ''),
    0x0f: ('jmp', 'J'), 0x10: ('gt', ''), 0x11: ('le', ''), 0x12: ('lt', ''),
    0x13: ('mul', ''), 0x14: ('neg', ''), 0x15: ('ne', ''), 0x16: ('newlist', ''),
    0x17: ('member', ''), 0x18: ('not', ''), 0x19: ('or', ''), 0x1a: ('pushvoid', ''),
    0x1b: ('push1', ''), 0x1c: ('pushstr', 'T'), 0x1e: ('pushint', 'V'), 0x1f: ('push0', ''),
    0x20: ('ret', ''), 0x21: ('sub', ''), 0x22: ('getparam', 'V'), 0x23: ('setparam', 'V'),
    0x24: ('getglobal', 'S'), 0x25: ('setglobal', 'S'), 0x26: ('getprop', 'S'),
    0x27: ('setprop', 'S'), 0x28: ('getlocal', 'V'), 0x29: ('setlocal', 'V'),
    0x2a: ('set', 'B'), 0x2b: ('nop', ''), 0x2c: ('pop2', ''), 0x2d: ('mod', ''),
    0x2e: ('append', ''), 0x2f: ('iternext', 'V'), 0x30: ('newxtra', ''), 0x31: ('exit', ''),
    0x32: ('intersects', ''),
}

# Builtin ids shared by func (get), proc (call) and set. Names are guesses from
# behaviour in FUN_004099f0 (get/call) and FUN_0040a8e0 (set).
BUILTINS = {
    0x00: 'locH', 0x01: 'locV', 0x02: 'mouseDown?', 0x04: 'volume(ch)', 0x05: 'colorDepth',
    0x07: 'cursor', 0x09: 'discardString?', 0x0a: 'puppetSprite', 0x0b: 'soundFadeIn',
    0x0c: 'soundFadeOut', 0x0d: 'soundStop', 0x0e: 'abs', 0x0f: 'frame', 0x10: 'lastFrame?',
    0x11: 'label', 0x12: 'b12?', 0x13: 'mouseH', 0x14: 'mouseV', 0x15: 'param',
    0x16: 'paramCount', 0x17: 'soundBusy', 0x18: 'quit', 0x19: 'soundLevel',
    0x1a: 'timer', 0x1b: 'startTimer', 0x1c: 'popInt?', 0x1d: 'visible',
    0x1e: 'castNum', 0x1f: 'updateStage', 0x20: 'random', 0x21: 'memberNum',
    0x22: 'rollover', 0x25: 'memberNumOf', 0x26: 'key', 0x27: 'keyCode', 0x28: 'key2',
    0x2d: 'charToNum', 0x30: 'puppetSound', 0x34: 'string', 0x35: 'rollover2',
    0x36: 'clickOn', 0x37: 'getAt', 0x38: 'add', 0x39: 'clearGlobals', 0x3a: 'set414694?',
    0x3b: 'count', 0x3c: 'deleteAt', 0x3d: 'setAt', 0x3e: 'append', 0x3f: 'getPos',
    0x40: 'getOne?', 0x41: 'max', 0x42: 'addAt', 0x43: 'point', 0x44: 'loc', 0x45: 'constraint',
    0x46: 'height', 0x47: 'rect', 0x48: 'width', 0x49: 'inside', 0x4a: 'member',
    0x4b: 'listP', 0x4c: 'voidP', 0x4d: 'getPref', 0x4e: 'setPref', 0x4f: 'value',
    0x50: 'min', 0x51: 'left', 0x52: 'right', 0x53: 'top', 0x54: 'bottom',
}


def read_varint(b, p):
    v = 0
    while True:
        c = b[p]
        p += 1
        v = (v << 7) | (c & 0x7F)
        if not c & 0x80:
            return v, p


def disasm(b, start, syms, stop_at_ret=True):
    """Yields (offset, text). Stops after ret/exit when the next byte starts nothing reachable."""
    p = start
    targets = set()
    while p < len(b):
        o = p
        op = b[p]
        p += 1
        if op not in OPS:
            yield o, '?? %02x' % op
            return
        name, kinds = OPS[op]
        args = []
        for k in kinds:
            if k == 'J':
                rel = struct.unpack_from('<h', b, p)[0]
                t = o + 1 + rel
                targets.add(t)
                p += 2
                args.append('L%d' % t)
            elif k in 'VSB':
                v, p = read_varint(b, p)
                if k == 'S':
                    args.append(syms[v][0] if v < len(syms) else 'sym%d' % v)
                elif k == 'B':
                    args.append(BUILTINS.get(v, 'b%02x' % v))
                else:
                    args.append(str(v))
            elif k == 'T':
                n, p = read_varint(b, p)
                args.append(repr(b[p:p + n].decode('latin1')))
                p += n
        yield o, ('%s %s' % (name, ', '.join(args))).strip()
        if stop_at_ret and op in (0x20, 0x31) and not any(t >= p for t in targets):
            return


def handler_chain(b):
    """A script resource is a chain of handlers: u32 event symbol, u32 offset of the next (0 = last), code."""
    p = 0
    while True:
        sym, nxt = struct.unpack_from('<II', b, p)
        yield sym, p + 8
        if not nxt:
            return
        p = nxt


def main():
    path = sys.argv[1]
    d = open(path, 'rb').read()
    ents = read_entries(d)
    syms = []
    for i, ty, size, off in ents:
        if ty == 2:
            syms = parse_symbols(d[off:off + size])
    movie = {h: name for name, h in syms if h}
    scripts = [(i, d[off:off + size]) for i, ty, size, off in ents if ty == 1]
    print('; %s: %d symbols, %d scripts' % (path, len(syms), len(scripts)))
    for i, b in scripts:
        for sym, start in handler_chain(b):
            name = syms[sym][0] if sym < len(syms) else 'sym%d' % sym
            tag = '  (movie script)' if ((i + 1) << 16 | start) in movie else ''
            print()
            print('on %s   ; script %d +%d%s' % (name, i, start, tag))
            for o, text in disasm(b, start, syms):
                print('  %4d  %s' % (o, text))


if __name__ == '__main__':
    main()
