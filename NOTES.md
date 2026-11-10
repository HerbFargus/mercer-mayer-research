# Big Tuna engine: first look (2026-10-16)

Goal: a ScummVM engine for the Big Tuna New Media Mercer Mayer games that are
not Director. Game files are in `reference-files/game-files/`.

## What's on the discs

| Game | Year | Data | Player EXE | Toolchain |
|---|---|---|---|---|
| Just Me and My Dad | 1996 | 34 x `.IMP` (magic `63 00 B7 7A`) | DAD.EXE 70 KB | Borland C, Win16 NE |
| Just Me and My Mom | 1996 | 46 x `.IM2` (magic `02MI`) | MOM.EXE 127 KB | Watcom Win386 (16-bit NE stub + bound 32-bit) |
| Little Monster: Smelly Mystery | 1997 | 45 x `.IM2` | SMELLY.EXE 166 KB | Watcom Win386 |
| Little Critter: Great Race | 1999/2001 | 47 x `.IM2` | TGR.EXE 87 KB | MSVC Win32 PE, built 1999-11-01, `C:\BigTuna\` |
| Little Monster: Mummy Mystery | 2001 | 52 x `.IM2` | LMMM.EXE 87 KB | MSVC Win32 PE, built 2001-05-02 |
| Just Me and My Grandpa | 1998 | `.DXR` (RIFX/MV93) | JMMG.EXE | real Director: not this engine |

TGR.EXE and LMMM.EXE are the same size and differ only slightly, so the late
player is generic and the per-game logic lives in the data files.

## The player: "Implay" (stage 0, 2026-10-16)

LMMM.EXE (window class `ImpWindow`, app name `Implay`) is a small
Director-style runtime. It has a score/frame player, cast members, a Lingo-like
bytecode interpreter (stack machine: "Interpreter stack overflow", "Unknown
opcode", "popInt", lists with getAt/setAt/deleteAt), the Director events
(`startmovie`, `enterframe`, `exitframe`, `mousedown`, `mouseup`,
`mouseenter`, `mouseleave`, `mousewithin`, `keydown`), `go` to a movie or
frame, film loops ("Unknown film operation"), preloading, video, cursors, and
a built-in PrintOMatic xtra shim (`drawstagepicture`, `drawtext`, ...).
Big Tuna clearly authored in Director and compiled the movies to their own
format.

Ghidra: `re/ghidra-proj` (project `bigtuna`). The full decompile is in
`re/LMMM.c` and the strings with their xrefs are in `re/LMMM.strings.txt`.
Regenerate with `tools/ghidra/DumpAll.java`, which also turns vtable targets
into functions. `tools/fn.py re/LMMM.c <addr>...` prints single functions.

Key functions: `404e10` open movie, `404cf0` per-type object factory, `4052b0`
type registry (types 2/4/6/8 have their own classes), `4055d0` bitmap decode,
`40cbe0` RLE, `408c30` interpreter main loop, `4099f0` builtin functions,
`40a8e0` sprite properties, `403b90` event dispatch, `402640` goframe,
`4034f0` film ops, `40bc00`/`40c0a0` sound (waveOut).

## .IM2 container (CONFIRMED, all 4 games, 190 files)

```
0       "02MI"  (u32 LE 'IM20')
4       u32 LE  entry count N
...     data
EOF-9N  directory: N x { u8 type, u32 LE size, u32 LE offset }
```

| type | meaning | format |
|---|---|---|
| 0 | empty slot | (size 0) |
| 1 | script | handler chain: {u32 event symbol, u32 next handler offset (0 = last), bytecode} |
| 2 | symbol table | name table; value = handler (resource+1)<<16 \| offset, 0 = none |
| 3 | cast names | name table; value = Lingo member number. **Mom: labels instead** (value = score byte offset of the frame) |
| 4 | score | film-op stream; 1 per file in Mom/Smelly, extras in Great Race/Mummy |
| 5 | palette | 256 x RGB, Mac system palette order |
| 6 | bitmap | see below |
| 7 | sound | u8 bits (8), u16 LE rate (11025 or 11127), unsigned mono PCM |
| 9 | frame labels | Director VWLB, big-endian: count, (frame, name offset) x count, total length, names; missing in Mom |

Bitmap: u16 w, u16 h, u8 format, u8 opaque (1 = no mask), s16 reg x, s16 reg y,
u16 extra. **Mom has a 10-byte header without `extra`.** Rows are stored top
first.
- format 0: RLE per row: `00` = end of row, `01-7F` = n literal bytes,
  `80-BF` = repeat the next byte (n&3F)+1 times, `C0-FF` = skip (n&3F)+1
  transparent pixels.
- format 1: raw 8-bit; the mask is pixel != 0.
- format 2: raw 16-bit (RGB555 presumably; unused in these games).
- format 3: LZ: `02 x` = literal x, `03-0A d` = copy n bytes from d+1 back,
  else literal (unused in these games).

`tools/im2dump.py FILE.IM2 [OUTDIR]` lists every entry and exports
PNG/WAV/raw blobs. A run over all 190 files gives zero errors and zero leftover
bytes (about 91k bitmaps and 10k sounds). Listings are in
`re/listing/<game>/`; sample exports are in `re/dump/`.

Numbers: Mom 23.9k bitmaps / 2.0k sounds / 1.5k scripts; Smelly 28.9k / 2.9k /
1.5k; Great Race 15.7k / 2.3k / 1.7k; Mummy 23.3k / 3.2k / 1.7k.

Name table (types 2, 3): u32 count, count x {u32 name start, u32 value},
u32 names end, then the names. Type 3 is sorted case-insensitively (binary
searched).

**Numbering.** The player prepends a dummy entry, so resource N (1-based) =
directory index N-1. Score member/script/sound operands are resource numbers.
Lingo member numbers are resource - 7 (slots 1-7 are reserved: score, symbols,
labels, cast names, palette, 2 spare). Fixed slots: 1 = score, 2 = symbols,
3 = labels (type 9; type 3 in Mom), 4 = cast names.

## Bytecode (stage 1, CONFIRMED, all 4 games)

`tools/im2script.py FILE.IM2` disassembles every handler. A survey over every
file (`tools/im2survey.py GAMEDIR...`) gives zero failures: 6,412 scripts and
8,145 handlers.

Stack VM (FUN_00408c30). Values are tagged words: 0 = void, odd = int (n*2+1),
even = object pointer (type 0 list, 1 proplist (point = loch/locv, rect =
left/top/right/bottom), 3 string). Operands: V = big-endian base-128 varint,
J = s16 LE relative to the byte after the opcode, T = V length + bytes.
Stack limit 100.

| op | name | | op | name |
|---|---|---|---|---|
| 01 | add (ints or points) | | 1a | push void |
| 02 | and | | 1b | push 1 |
| 03 J | jz | | 1c T | push string |
| 04 V V | call symbol, argc (movie handler, `rect`, or a method on the object arg) | | 1e V | push int |
| 05 | return value | | 1f | push 0 |
| 06 V | func builtin (get) | | 20 | return |
| 07 V | proc builtin (call) | | 21 | sub (ints or points) |
| 08 | concat | | 22/23 V | get/set param |
| 0b | div (by 0 gives 0x7fffffff) | | 24/25 V | get/set global (symbol) |
| 0c/15 | eq/ne | | 26/27 V | get/set proplist prop (symbol) |
| 0d/10/11/12 | ge/gt/le/lt | | 28/29 V | get/set local |
| 0e | go: pops movie, then frame (int or label; void = start) | | 2a V | set builtin property |
| 0f J | jmp | | 2b | nop |
| 13/14 | mul/neg | | 2c | pop member + string (no-op) |
| 16 | new list | | 2d | mod |
| 17 | member (name or number) | | 2e | list append (keeps list) |
| 18 | not | | 2f V | iterate local list: pops first, pushes item and 1, or 0 |
| 19 | or | | 30 | new xtra (only "PrintOMatic") |
| | | | 31 | exit (clear stack, return) |
| | | | 32 | sprites intersect |

Builtin ids are one table shared by func/proc/set (FUN_004099f0 get/call,
FUN_0040a8e0 set). Names are in `BUILTINS` in im2script.py; most are pinned
by behaviour (locH/locV, loc, rect, width/height, member/castNum, visible,
puppetSprite, puppetSound, sound fade/stop/busy, volume, cursor, timer, random,
mouseH/V, rollover, clickOn, key/charToNum, label, list ops (getAt, setAt,
addAt, deleteAt, count, getPos), point, inside, min/max, string, value,
getPref/setPref (files under `C:\BigTuna\`), updateStage). A few marked `?`
are guesses.

Movie names in `go` drop the extension (Mom still says `"Page01Z.Dir"`).

## Score / film ops (stage 1, CONFIRMED)

`tools/im2score.py FILE.IM2` prints the frames. FUN_004034f0 plays it and
FUN_00403000 preloads. It is a delta stream; sV = varint with the sign in bit
0, s = u8-length string:

| op | args | meaning |
|---|---|---|
| 00 | V sprite, s name | sprite named script (unused in these games) |
| 01 | u8 | cursor |
| 02 | V sprite | clear sprite |
| 03 | s label | go to label |
| 04 | s movie, s label | go to movie |
| 05 | s | comment / no-op |
| 06 | V res | palette |
| 07 | V sprite, V member res, sV x, sV y | sprite member + loc (reg point) |
| 08 | V sprite, V script res | sprite script (sprite 0 = frame script) |
| 09/0a | u8 chan, V sound res | play sound |
| 0b | u8 | tempo (fps) |
| 0c | u8 chan, u8 vol, V fade | volume / fade |
| 0d | V n | end of frame, advance n |
| 0e | sV x, sV y, V w, V h, s file | play video in rect |
| 0f | u8 chan, V | sound-channel property (Mom only) |
| 10 | V, V | stage scroll (unused) |
| 11 | | end of frame, advance 1 |
| 14 | u8 chan | wait for sound to finish |
| 16 | V, V | sprite origin offset |

Events (FUN_00403b90): `enterframe`/`exitframe` go to the frame script;
`mouseenter`/`mousewithin`/`mouseleave`/`mousedown`/`mouseup` go to the
topmost sprite's script; `keydown` and `startmovie` go to the movie scripts
via the symbol table. A sprite/frame script answers an event if its handler
chain has a handler named for it.

Inventory: Mom and Smelly mostly use frame and sprite scripts with `go`. Great
Race and Mummy add movie-script libraries (`hcursor*`, `hmusic`, `hsave`/
`hload`, `hjournal`, inventory dragging) and heavy global lists.

## .IMP (Dad)

An older container with a named directory: `macpal.C`, `intro.A`, `1.P`,
`74.P`, `70.S` (cast-number.type: C = CLUT, P = picture, S = sound, A = maybe
score/anim).

## Plan (stages)

0. **DONE (container, bitmaps, sound, palette, labels)**. **Format RE**: write `tools/im2dump.py` to walk a whole IM2 into labels,
   palette, scripts, bitmaps and sounds, and export PNG/WAV. Use Ghidra on
   LMMM.EXE (small, Win32, easiest to read) to confirm the chunk layout and get
   the bytecode opcode table.
1. **DONE (bytecode, symbols, cast names, score)**. **Script VM**: a disassembler for every script in all 4 IM2 games, then an
   opcode inventory.
2. **DONE (3806fb95b5)**. **ScummVM engine skeleton** (`engines/bigtuna`): detection for the 4 IM2
   games (+ Dad later), a page loader, bitmap/palette display, sound.
3. **Interpreter**: hotspots, page flow, animation playback; Great Race and
   Mummy first (newest, same player).
4. **Older revisions**: Smelly and Mom (Watcom builds, possibly hardcoded
   logic), then Dad's .IMP.
5. Playtest each game start to finish.

## Stage 2: ScummVM engine skeleton (DONE 2026-10-16)

Commit `3806fb95b5` on branch `bigtuna` (worktree
`magic-school-bus/scummvm-bigtuna`, cut from upstream/master 55895ab0d3;
local only, not pushed, not merged into `combined`). AI-written notice in
`BIGTUNA.md`, as with yaga.

Results:
- All four games are detected (EXE + INTRO.IM2 md5) and boot into `intro`.
- A sweep (`bigtuna_allmovies`) over all 190 movies steps 342,687 frames and
  decodes every bitmap and score: zero warnings. Bitmap counts match the
  Python tools.
- Pixel compare: 40 sampled frames (intros and pages of all four games,
  including film-loop frames in Great Race INTRO / PAGE23G and Mummy
  PAGE03/06) are identical to `tools/im2render.py`, an independent Python
  renderer.
- Sound plays on channels 1 and 2 at 11025/11127 Hz (seen in the debug log;
  not listened to).

Tooling (`magic-school-bus/tools-bigtuna/`): `make.sh` (re-runs itself under
MSYS2 UCRT64; `CONFIGURE=1` the first time; configure must run in MSYS2, not
Git Bash), `boot.sh <mom|smelly|race|mummy> [secs]`,
`shots.sh <game> <movie> <frames>`, `compare.sh <game> <movie> <frames>`
(engine shot vs reference, pixel for pixel). Output goes to
`magic-school-bus/bigtuna-tests/`.

Known gaps / decisions made while building:
- Draw order is ascending channel (Director style). The player's z is
  `base - channel` and wasn't traced to the end; it looks right in every
  frame checked.
- Masked drawing is a plain "skip transparent pixels". The real player uses
  SRCPAINT/SRCAND with a mono mask; identical for normal art.
- Pages hold on their last frame, since looping comes from scripts (stage 3).
- Film ops 0e (video), 0f (Mom channel prop), 10 (stage), 01 (cursor) and
  00 (sprite name) are parsed but ignored.

### Original stage 2 plan

Goal: a `bigtuna` engine that detects the four IM2 games, opens a movie and
**plays its score without the script VM**: backgrounds, animated sprites,
palette, tempo and sound on screen and through the speakers. The VM, events
and `go` come in stage 3.

Facts the plan rests on: the stage is 640x480 8-bit. With no command-line
argument the player starts at movie `intro` (+ `.im2`), from FUN_0040cd90.
Movie names in `go` drop the extension. The `.rsrc` section is only 0x39C
bytes, so cursors are cast members or built-in ids (200 = Director's blank
cursor), not EXE resources.

### Where
- A new worktree `magic-school-bus/scummvm-bigtuna`, branch `bigtuna`, cut
  from current `upstream/master` (the yaga setup: fork-only, Assisted-by
  trailers, never PR'd upstream). It gets merged into `combined` once it plays.
- Tooling copied from tools-yaga: `tools-bigtuna/make.sh`, `boot.sh` (run one
  game with a timeout and keep the log), `shots.sh` (config keys
  `bigtuna_ticks` / `bigtuna_shots` / `bigtuna_movie` save the screen at given
  frames, then quit), `play.sh` entries.

### Steps
2a. **Boilerplate + detection.** `engines/bigtuna/` with configure.engine,
    module.mk, metaengine, detection.cpp + detection_tables.h. Game ids:
    `jmmmom`, `smellymystery`, `greatrace`, `mummymystery`. Entries are keyed
    on `INTRO.IM2` md5 (5,000 bytes) + size, plus the EXE (MOM.EXE /
    SMELLY.EXE / TGR.EXE / LMMM.EXE). Flag: `GF_IM2_V1` for Mom (10-byte
    bitmap header, type-3 labels by score offset). Done when all four show up
    in the launcher with the right names and start into an empty 640x480 screen.
2b. **Movie loader** (`movie.cpp`): opens `<name>.im2` case-insensitively and
    reads the directory with the dummy entry 0 so numbers match the player.
    Resources load lazily and are cached per movie. Parses the symbol table,
    labels (type 9, or Mom's type 3), cast names and palette. A debugger
    console with `movies`, `res <n>`, `labels`, `score`.
2c. **Decoders** (`bitmap.cpp`, `sound.cpp`): bitmap formats 0-3 with mask and
    reg point into `Graphics::ManagedSurface` (CLUT8 + 1-bit mask); sound via
    `Audio::makeRawStream` (8-bit unsigned, 11025/11127 Hz).
2d. **Score player** (`score.cpp`): the film-op stream as a per-frame delta
    into channel state (sprite member, loc, script id kept for later), tempo,
    palette, sound channels 1-2 (play, volume/fade, wait-for-sound),
    `origin`, and Mom's op 0f. Label-to-frame tables for both label formats.
    Seeking to a frame replays deltas from frame 1 (cheap: largest score is
    about 66 KB).
2e. **Renderer** (`stage.cpp`): composite the sprite channels in order onto a
    640x480 CLUT8 surface (bitmap drawn at loc minus reg point, mask = skip
    transparent pixels, opaque bitmaps copied straight), clip oversize art
    (Mom's 649x484 pages), and dirty-rect update to the screen at the score
    tempo.
2f. **Verification:**
    - A Python reference renderer (`tools/im2render.py`, reusing the
      im2dump/im2score decoders) that renders frame N of a movie to PNG.
      `shots.sh` grabs the same frames from ScummVM, and a compare script
      demands pixel-identical results. This proves the decoders and the
      compositing without needing the original EXE.
    - Run `intro` of each game: Mummy's title animation (members 171+ with
      sound 230), the Great Race map page, Smelly's opener, Mom's train
      station.
    - No crashes or decoder warnings when stepping every frame of every
      movie in all four games (a `bigtuna_allmovies=1` sweep mode).

### Out of scope for stage 2
The bytecode VM, the event loop (mouse, keys, rollover), `go`/label jumps
driven by scripts, cursors, film op 0e (video; unused in these four games),
PrintOMatic, save/load (`getPref`/`setPref`). With no VM the score just runs
to its last frame and holds.

### Risks / open questions
- **Mom runs on a different player** (MOM.EXE, Watcom Win386). Its data
  decodes with the same tools, but its runtime behaviour (label seek by byte
  offset, op 0f) isn't confirmed from code yet. MOM.EXE's 32-bit part is bound
  under a Win386 stub, so Ghidra needs it extracted first. That's stage 4; in
  stage 2 Mom only needs to draw.
- **Sprite channel order and ink.** I'm assuming a higher channel draws on
  top and the only inks are mask vs opaque. This needs checking against the
  draw loop (FUN_00407390 / FUN_004070b0 area) during 2e.
- **Detection data.** These are HD copies of single releases; other
  languages and versions are unknown. Each entry also carries the EXE md5 so
  unknown variants show up as "unknown game" reports.
- **Size.** About 4-5 sessions: 2a+2b 1, 2c 1, 2d+2e 1-2, 2f 1.

## Stage 3: script VM, events, navigation (built 2026-10-17)

Commits on `bigtuna`: `22c13b314a` (VM + event loop), plus follow-ups below.
New files: `value.{h,cpp}` (tagged values, lists and proplists shared by
reference, `compareValues` = FUN_00408490 including its quirks: `gt` is
`cmp == 1` and `lt` is `cmp == -1`), `script.{h,cpp}` (interpreter, call
frames {argc, base, pc, res}, params below the frame, locals above it),
`builtins.cpp` (func/proc/set ids). The score became timed **steps**
(`Step{offset, frame, length}`).

Facts pinned from the EXE while building:
- builtin 02 = video playing (always 0 here), 0F = doubleClick, 10 = the
  frame, 12 = mouseDown, 18 = **quit** (arrow cursor + CRT exit(0)), 22/35 = rollover (member number
  under the mouse, -1 for none), 26/28 = key (1-char string, or 0), 27 =
  keyCode, 36 = clickOn (channel of the scripted sprite under the mouse this
  step).
- Globals default to int 0 the first time they're named; clearGlobals sets
  the movie's symbols to void.
- Cursor members load **resource n+8** (n+9 if n+7 is empty), white
  transparent, hotspot at the reg point. Cursor 200 hides the cursor and
  blocks mouse events.
- Movie load (FUN_00402490/00402d90): sound reset (both channels stop,
  volume 255), every sprite destroyed, frame 1 applied, `startmovie` runs,
  then the score rewinds (shown non-puppet sprites destroyed, **hidden ones
  keep their hidden state**), sound reset again, then go to the frame/label.
- Score sounds don't restart if the channel already plays that sound.
- Labels can end in `
`; lookups ignore it.
- getPref/setPref = files under `C:\BigTuna\` -> ScummVM save files
  `<target>-<name>` (Mummy: `LMMMPref`).

Verification so far (`tools-bigtuna/play-test.sh <game> <secs> [actions]`,
actions `ms:c:x:y`, `ms:k:code`, `ms:s`; `FUZZ=1 SEED=n`):
- Mummy: intro -> Page00a, menu (Page00m) -> NEW GAME -> cutscene, Escape
  skips sections (`go gnextframe`) -> Page01 gameplay with inventory bar.
- Great Race: intro -> menu (Page00) -> NEW GAME -> Page00a -> Page00b.
- Mom: intro -> Intro2 -> Option; buttons only take scripts from frame 475;
  READ -> PgRd01.
- Smelly: intro -> Option (line-up screen).
- Fuzz (random clicks on scripted sprites, sometimes Escape; 0aaca8bbbc): 4 min per game, **zero VM warnings**. Mummy covered 25 movie
  changes (pages, menu, save screen Page00s, journal Page00j, Page00x); Great
  Race 32 (Page01/02/08/17, menu, save); Smelly reached Page01; Mom read
  pages 1-3.
- **Save/load works through the games' own screens**: the fuzzer saved a
  Mummy game (`mummymystery-LMMMPref` holds the original's list format), and
  menu -> LOAD GAME shows the slots with page thumbnails; slot 1 + OK
  returns to Page01.

Not done / not verified:
- 3f (Mom's own player, MOM.EXE) wasn't needed: Mom runs on the LMMM model
  with no warnings so far. Its event rules are still unconfirmed against
  its binary.
- Audio is only checked through the debug log, not by ear.
- PrintOMatic methods are ignored (print buttons do nothing).
- Nobody has played a game start to finish yet: that's the user playtest.

### Original stage 3 plan

Goal: the four games are **playable**. Clicking hotspots, keys, page
navigation, inventory, sounds and save/load through the games' own menus all
behave as in the original player.

### What the EXE does (new findings for this plan)
- **Main loop** (FUN_00402ed0): `step = film ops until 0x11/0x0D n`, then
  FUN_00403b90 runs that step. **When the score runs out, the player quits.**
  Every page keeps itself alive with an exitFrame `go` loop.
- **A step is not a frame.** `0D n` advances the frame counter by n and the
  step lasts n frame periods, but enterFrame/exitFrame fire **once** for it.
  Stage 2 expanded holds into n identical frames; stage 3 replaces that with
  timed steps (labels keep their real frame numbers).
- **Per step** (FUN_00403b90): enterFrame -> frame script. For the step's
  duration: poll input; a key fires `keydown` on the movie scripts (via the
  symbol table); the sprite under the mouse (topmost channel with a script,
  hit by rect then pixel mask, FUN_00407800/407060) gets `mouseenter` once,
  then `mousewithin`; a click fires `mousedown`, and `mouseup` only if no
  mousedown handler ran; moving off fires `mouseleave`. **Mouse events are
  ignored while the cursor is 200** (the blank "busy" cursor). Film loops step
  once per frame. Then exitFrame.
- **Script dispatch** (FUN_00408170): a sprite or frame script answers an
  event if its handler chain has that name. `call` (op 04) runs a movie
  handler by symbol, otherwise `rect`, otherwise a method on the object
  argument (only PrintOMatic).
- **go** (op 0E): pops movie then frame. A movie change loads the new movie
  and **ends the running script**. A frame-only go seeks and continues.
  `startmovie` runs on load. Globals are symbols interned by name, so they
  survive movie changes. Seeking (FUN_00402640) replays the score from the
  current frame or frame 1, keeping the last sound per channel.
- **Display list** sorted so channel 1 draws first, confirming stage 2's
  order; `intersects` (op 32) is rect overlap plus a mask check at the
  centre.
- **Cursors**: 200 = blank/busy (and input lock), 0 = arrow, or a list of
  1-2 members (image, mask) in Great Race/Mummy.
- **Prefs**: getPref/setPref read and write text files under `C:\BigTuna\`.
  The games' own save/load (`hsave`/`hload`) go through these.

### Steps
3a. **Values and VM core** (`script.cpp`, `value.h`): a tagged Value (void,
    int, string, list, proplist (point/rect), symbol, member, xtra), the
    operand stack (limit 100), call frames (params, locals, return pc, saved
    script), and all 0x01-0x32 opcodes. Global variables live on interned
    symbols across movies. Script resources load from the handler chain.
    Unit check: a `bigtuna_trace` config key logs every op, and a
    disassembly cross-check runs against `im2script.py` output.
3b. **Builtins and properties**: the ~70 ids in use (func/proc/set). Before
    implementing, pin the uncertain ones by reading their EXE code: 02
    (mouseDown?), 10 (lastFrame?), 12, 18, 3a, 40 (getOne?), 09. Sprite
    props: loc/locH/locV, member/castNum, visible, constraint, puppetSprite;
    rollover, clickOn, mouseH/V, key/keyCode, timer, random, label, list ops,
    string/value, point/rect/inside, sound fade/stop/busy/volume, updateStage
    (redraw mid-script), PrintOMatic as a no-op stub.
3c. **Event loop rewrite** (`bigtuna.cpp`, `score.cpp`): steps instead of
    frames, the per-step event sequence above, the mouse state machine
    (enter/within/leave, down/up), pixel-mask hit test, the cursor-200 input
    lock, keydown, startmovie, and go/movie switching with script abort. Film
    loops step once per frame period.
3d. **Cursors**: 200 hidden, 0 arrow, member cursors built from bitmap +
    mask via CursorMan.
3e. **Prefs to saves**: getPref/setPref map to ScummVM save files
    `<target>-<name>`, so the games' own save/load menus work. ScummVM's
    GMM save/load stays off for now.
3f. **Mom's player check**: Mom runs on MOM.EXE (Watcom Win386). Its data
    and opcodes match, but confirm its event model and label seeking on the
    real binary: extract the bound 32-bit image from the Win386 stub and run
    Ghidra on it. Only if Mom misbehaves in 3g; otherwise note it as
    unverified.
3g. **Verification:**
    - Scripted play-throughs with a `bigtuna_clicks=step:x:y,...` hook (like
      yaga's): boot each game, click through the title to the first page,
      open the menu, and go page to page, with screenshots checked by eye.
      For Great Race and Mummy, also pick up an inventory item and save and
      reload from the in-game menu.
    - A no-crash sweep that starts every movie and runs ~200 steps with
      random clicks (fuzz), logging unknown builtins and VM errors.
    - Then hand it to you for a real playtest of each game.

### Out of scope
Video (op 0E; none of these four games use it), PrintOMatic printing (the
"print" buttons do nothing), ScummVM GMM save/load and thumbnails, Dad's .IMP
player, and merging into `combined` (after your playtest).

### Risks
- **Mom's player** may differ in ways the data doesn't show (event order,
  label seek, op 0f). Mitigated by 3f.
- **Timing-sensitive scripts** (`timer`, `startTimer`, waits on soundBusy):
  these should be fine against real time but may need ScummVM-side tuning.
- **Uncertain builtins**: 7 ids still marked `?`; 3b pins them from the EXE
  before use.
- **Size**: about 5-7 sessions: 3a 1-2, 3b 1-2, 3c 1, 3d+3e 1, 3f/3g 1-2.
  Great Race and Mummy (heavy script libraries) are the stress test; Mom
  and Smelly are mostly `go` and hotspots.

## Stage 4: Just Me and My Dad (.IMP), built 2026-10-17

Commits `86f0ef2dfd` (IMP player), `de0dd5c428` (film end = quit) on
`bigtuna`. Engine: `imp.{h,cpp}` (ImpFile, ImpPlayer), `Bitmap::loadImp`,
`Sound::playRaw` (looping), detection `jmmdad` (DAD.EXE + INTRO.IMP,
`GF_IMP`). Tools: `impdump.py`, `impfilm.py`, `imprender.py` (reference
renderer). `tools-bigtuna/*.sh` take `dad`.

Corrections found while building:
- **Film y counts up from the bottom**: top = 384 - y - height (the
  upside-down kid and the menu buttons gave it away; the main program
  creates a 512x384 stage).
- Type 5 `go`'s indirection flag is **b**; the records with a=1 are direct.
- QuickTime (a, b) is the **centre** of the 160x120 video (page13 uses
  256,192); a click stops it.
- **The program exits when a film runs out of records** (entry point
  1000:0099 calls the frame loop once). QUIT's "bye" path ends the game that
  way. Clicks start disabled.

Verified: sweep of all 34 files (34,901 frames, 14,237 pictures, 0
problems); intro -> intro1 -> option1; READ -> pgrd01; the TV on page13
plays the QuickTime video dithered into the TV; QUIT -> bye exits the game;
4 min fuzz across 20+ film changes with zero warnings; 7 sampled frames
pixel-identical to `imprender.py`. Not verified: audio by ear, Play mode in
depth, every page.

### Decoded (4a/4b)
- `tools/impdump.py`: all 14,237 pictures in the 34 files decode with zero
  leftover bytes, flags always 0 (the nybble format is unused). Palette =
  1 byte + 256 RGB (index 0 and 255 are both black). **Transparent = index
  255 and unwritten pixels** (rows that end early).
- `tools/impfilm.py`: a film = 19-byte header {u16 count, u8 channels, u8
  palette id, ...} + count x 19-byte records {u8 type, u8 channel, u8
  **duration in 1/60 s ticks (non-zero = end of frame)**, u8 transition (0
  everywhere), s16 a, s16 b, s16 c, name[9]}. All 33 films parse exactly.
- **Stage is 512x384** (432 backdrops sit at (0,0) at 512x384); (a,b) is the
  top-left; centred in the 640x480 screen; backdrops up to 870 wide pan.
- Record types (FUN_1008_1159 apply, FUN_1008_0c24 main loop, FUN_1008_0a04
  wait + clicks, FUN_1008_05df go to label, FUN_1008_04bd load film):
  - 0 clear the channel; 2 picture `<name>.P` at (a,b), layer c (0x7FFF =
    backdrop; draw high c first); 1 box `.B` / 3 text `.T` (unused);
  - 4 sound `<name>.S`, queued on channel a (1-2) with loop = b, started
    after the frame's wait; 10 sound channel a: b = volume (0 -> c = fade
    ticks, or stop if c = 0);
  - 5 go to name (b != 0: the name is a variable); 6 label; 7 button: channel
    -> this record (name = target, a != 0: target from a variable); 9 clicks
    on/off (and the cursor); 11 QuickTime `<name>.mov`, 160x120, blocking;
    12 set variable `<name>.V` = next record (type 8)'s name.
- Frame end: draw, wait the previous frame's duration (clicks: topmost
  sprite under the mouse; if its channel has a button, the button's target
  is taken and the wait ends), start queued sounds, then go to the target:
  a label in this film (sprites rebuilt from the last cell record per
  channel), else the film file `<name>.IMP`. Space = go to `option1`. At the
  end of the records the film rewinds.
- Record-name suffix constants live in code segment 2 (1008:xxxx). Ghidra
  shows them with segment 1068, which is wrong.

### Original stage 4 plan

### What Dad is
- The PC release is **not** Director, and **not** the Implay player either.
  DAD.EXE is a 70 KB **Turbo Pascal for Windows** program (`TPWinCrt`,
  Borland 1983-92), built on an older Big Tuna toolkit called "IW"
  (`c:\iw\funit.dmp`, `IW.CNF`). It has a record-library layer (`GLop`,
  `GLread`, `GLacc`, "record has no dad": records are nested), "films",
  `goto`, and "nybblized" picture compression. The Mac release is real
  Director and already in ScummVM's Director tables as `jmmd` (Mac only).
- Ghidra: imported into the `bigtuna` project; `re/DAD.c` holds 559
  functions. Pascal nested procedures make the decompile wordy but readable.
  It's much smaller than LMMM.EXE. Strings aren't xref'd (NE segments), so
  they have to be located by segment:offset by hand.

### .IMP container (CONFIRMED on INTRO/PAGE01/MACPAL)
```
u16 0x0063, u16 0x7AB7          magic/version
u16 count
count x 19 bytes { u8 len + name, padded to 11 bytes; u32 size; u32 offset }
```
Records are named `<number>.<type>`, plus `<movie>.A` and `macpal.C`:
- `.C` palette: one byte + 256 x RGB (`macpal.C` per movie, plus
  MACPAL.IMP).
- `.S` sound: `"snd8"`, u16 rate (11127), u16 0, unsigned 8-bit PCM.
- `.P` picture: u16 w, u16 h, u16 flags, then per row a u16 byte length and
  RLE: `01-7F` literal run, `80-FF` repeat the next byte `n & 7F` times (no
  +1), and a short row leaves the rest blank/transparent. Unconfirmed: what
  `flags` select (the EXE also has a 4-bit "nybblized" format), and where
  the reg point and transparency come from.
- `.A` film (one per movie, 26 KB in INTRO): records holding channel, x, y,
  a z-like value and **member names as strings** (`"74"`, `"75"`, `"80"`),
  `snd ` records, label names (`opening`, `btnm`, `written`), and a trailing
  `intro1`, probably the next movie. No compiled script language spotted;
  interactivity probably sits in film records (hotspots/buttons -> goto
  label or movie). This is the main unknown.
- PAGE13QT.MOV (104 MB): QuickTime, **Cinepak 160x120 + raw 8-bit 11127
  Hz**. ScummVM's QuickTimeDecoder handles both.

### Plan
4a. **Dumper**: `tools/impdump.py`, which lists records and exports
    pictures/sounds/palettes. Confirm the picture RLE over every `.P` in all
    34 files (zero leftover bytes, as with IM2), find the nybble format and
    what `flags` mean.
4b. **Film RE**: find the film parser in DAD.EXE (look for the `goto` and
    `gofile: Cannot find film` users and the record-library calls), and write
    `tools/impfilm.py` to decode every record type. Check it over all 34
    films with zero unknown records. Then map the interaction model (clicks,
    hotspots, `btnm`, keys, page turns, the `.mov` playback) from the EXE.
4c. **Engine**: add Dad to `bigtuna` as a second container/player type
    (`GF_IMP`): detection (DAD.EXE + INTRO.IMP), an `ImpMovie` reader, the
    picture and sound decoders, and a film player that feeds the existing
    stage/sound code. Separate from the IM2 VM, sharing the stage, sound,
    cursor and test hooks.
4d. **QuickTime page**: page 13's movie through `Video::QuickTimeDecoder`,
    drawn into the stage.
4e. **Verification**: a sweep over every film (no unknown records, all
    pictures decode), the Python reference renderer extended for .IMP with
    pixel compares, scripted play-throughs (intro -> option -> read/play
    pages -> quit), and a fuzz run. Then your playtest.

### Risks / open questions
- **Film semantics are the unknown.** Unlike IM2 there's no Director-shaped
  structure to lean on, and 16-bit Pascal is slower to read. This is most of
  the effort.
- The nybblized picture format and the transparency rule need the EXE.
- Possibly MIDI or other assets not seen yet; the 4a/4b sweeps will show.
- **Size**: about 3-5 sessions (4a 1, 4b 1-2, 4c+4d 1, 4e 1).
- **Alternative**: the Mac release already plays in ScummVM's Director
  engine, if a copy of it is easy to get.
