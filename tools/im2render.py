"""Reference renderer: plays a movie's main score to frame N and writes the stage as a PNG.

Same model as the ScummVM engine: sprite channels drawn in ascending order onto
a 640x480 stage cleared to index 0, bitmaps placed at loc - reg point, masked
pixels skipped, film loops (sprites whose member is a score) advanced once per
frame before the frame's own ops and drawn at loc - loop origin.

Usage: im2render.py FILE.IM2 OUT.png FRAME [FRAME...]   (OUT gets -NNNN per frame)
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from im2dump import read_entries, bitmap_header_size, decode_bitmap, parse_palette, write_png  # noqa: E402
from im2score import decode_score  # noqa: E402

W, H = 640, 480


def frames_of(b):
    """Splits a score into frames (lists of (op, args)) the way the engine does: 0x0d n ends a
    frame and adds n - 1 empty ones; ops after the last terminator make one more frame."""
    frames = []
    cur = []
    for _, op, args in decode_score(b, terminators=True):
        if op == 'end':
            frames.append(cur)
            frames.extend([] for _ in range(args[0] - 1))
            cur = []
        else:
            cur.append((op, args))
    if cur:
        frames.append(cur)
    return frames


class Movie:
    def __init__(self, path):
        self.d = open(path, 'rb').read()
        ents = read_entries(self.d)
        self.res = {i + 1: (ty, size, off) for i, ty, size, off in ents}
        self.hdr = bitmap_header_size(self.d, ents)
        self.bitmaps = {}
        self.scores = {}
        self.palette = None
        for r, (ty, size, off) in sorted(self.res.items()):
            if ty == 5 and self.palette is None:
                self.palette = parse_palette(self.d[off:off + size])

    def data(self, r):
        ty, size, off = self.res[r]
        return self.d[off:off + size]

    def type(self, r):
        return self.res.get(r, (0, 0, 0))[0]

    def bitmap(self, r):
        if r not in self.bitmaps:
            self.bitmaps[r] = decode_bitmap(self.data(r), self.hdr) if self.type(r) == 6 else None
        return self.bitmaps[r]

    def score(self, r):
        if r not in self.scores:
            self.scores[r] = frames_of(self.data(r))
        return self.scores[r]


class Player:
    def __init__(self, movie, frames, is_loop):
        self.movie, self.frames, self.is_loop = movie, frames, is_loop
        self.reset()

    def reset(self):
        self.sprites = {}
        self.frame = 0
        self.origin = (0, 0)

    def advance(self):
        for s in self.sprites.values():
            if s['loop']:
                s['loop'].advance()
        if self.frame >= len(self.frames):
            if not self.is_loop or not self.frames:
                return False
            self.reset()
        self.frame += 1
        for op, args in self.frames[self.frame - 1]:
            self.apply(op, args)
        return True

    def apply(self, op, args):
        if op == 'clear':
            self.sprites.pop(args[0], None)
        elif op == 'sprite':
            ch, mem, x, y = args
            mem += 1                      # im2score prints directory indices
            s = self.sprites.setdefault(ch, {'member': 0, 'loop': None})
            if s['member'] != mem:
                s['member'] = mem
                s['loop'] = Player(self.movie, self.movie.score(mem), True) if self.movie.type(mem) == 4 else None
            s['x'], s['y'] = x, y
        elif op == 'origin':
            self.origin = args
        elif op == 'palette' and self.movie.type(args[0] + 1) == 5:
            self.movie.palette = parse_palette(self.movie.data(args[0] + 1))


def draw(stage, mask_skip, player, ox, oy):
    for ch in sorted(player.sprites):
        s = player.sprites[ch]
        if not s['member']:
            continue
        x, y = s['x'] + ox, s['y'] + oy
        if s['loop']:
            draw(stage, mask_skip, s['loop'], x - s['loop'].origin[0], y - s['loop'].origin[1])
            continue
        bm = player.movie.bitmap(s['member'])
        if not bm:
            continue
        w, h, fmt, opaque, rx, ry, extra, pix, mask, used = bm
        if fmt == 2:
            continue
        x0, y0 = x - rx, y - ry
        for sy in range(h):
            dy = y0 + sy
            if not 0 <= dy < H:
                continue
            lo, hi = max(0, -x0), min(w, W - x0)
            if lo >= hi:
                continue
            row = sy * w
            base = dy * W + x0
            if opaque == 1:
                stage[base + lo:base + hi] = pix[row + lo:row + hi]
            else:
                for sx in range(lo, hi):
                    if mask[row + sx]:
                        stage[base + sx] = pix[row + sx]


def main():
    path, out = sys.argv[1], sys.argv[2]
    wanted = sorted(int(a) for a in sys.argv[3:])
    movie = Movie(path)
    player = Player(movie, movie.score(1), False)
    stem, ext = os.path.splitext(out)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    for target in wanted:
        while player.frame < target and player.advance():
            pass
        stage = bytearray(W * H)
        draw(stage, None, player, 0, 0)
        write_png('%s-%04d%s' % (stem, player.frame, ext), W, H, stage, b'\1' * (W * H), movie.palette)
        print('frame %d' % player.frame)


if __name__ == '__main__':
    main()
