"""Print decompiled functions from a Ghidra DumpAll .c file: fn.py LMMM.c 4049e0 404a30 ..."""
import re, sys
src = open(sys.argv[1]).read()
parts = {m.group(1).lower(): m.group(0) for m in re.finditer(r'(?ms)^// ==== \S+ @ ([0-9a-fA-F]+)\n.*?(?=^// ==== |\Z)', src)}
for a in sys.argv[2:]:
    print(parts.get(a.lower().removeprefix('0x').zfill(8), '// not found: ' + a))
