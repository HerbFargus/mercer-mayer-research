# Big Tuna's Mercer Mayer games: research notes

Notes and tools from reverse-engineering Big Tuna's players for the Mercer Mayer games: the "Implay" .IM2 movies (Just Me and My Mom, Little Monster: The Smelly Mystery, Little Critter and the Great Race, Little Monster: The Mummy Mystery) and the earlier "IW" .IMP files of Just Me and My Dad: their scores, bytecode and rendering.

The ScummVM engine built from this work is on the `bigtuna` branch of the fork: https://github.com/HerbFargus/scummvm/tree/bigtuna (see BIGTUNA.md there).

## Notes

- `NOTES.md`: the formats and both players

## Tools

Python 3 unless noted; most need only the standard library.

- `tools/im2dump.py`: walk a .IM2 file and export it
- `tools/im2score.py`: decode the score (type 4 "film") of a .IM2 file
- `tools/im2script.py`: disassemble the Implay bytecode in a .IM2 file
- `tools/im2render.py`: reference renderer: play a score to frame N and write a PNG
- `tools/im2survey.py`: run the decoders over every .IM2 file and list ops and failures
- `tools/impdump.py`: walk a Just Me and My Dad .IMP file and export it
- `tools/impfilm.py`: decode the film (.A record) of an .IMP file
- `tools/imprender.py`: reference renderer for the .IMP films
- `tools/pngcmp.py`: compare PNGs pixel by pixel
- `tools/fn.py`: print functions from a Ghidra DumpAll export

## Ghidra scripts

Headless Ghidra scripts and the batch files that ran them. Set GHIDRA to your Ghidra install; the batch files otherwise look for one beside the project.

- `tools/ghidra/DecompAt.java`
- `tools/ghidra/DumpAll.java`

## Not included

No game files, extracted assets, screenshots, or decompiled or disassembled
game code are in this repo. The tools work on your own copy of the game.

## About these notes

The research and the tools were written with an LLM (Claude), working from
the games themselves. They are published as a reference for how the formats
and the engine work. Check anything you rely on against the games.

The matching ScummVM engine on the fork is AI-written too and is not a ScummVM
contribution: ScummVM's AI guidelines do not allow AI-authored submissions.
Anyone writing a real engine should treat this repo as notes, not code to copy.

## Licence

GPL-3.0 (see LICENSE), the same as ScummVM.
