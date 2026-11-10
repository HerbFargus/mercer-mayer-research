// Dump every function's decompiled C to <out>, plus strings with their xrefs.
//@category BigTuna
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.data.*;
import ghidra.program.model.symbol.*;
import java.io.*;

public class DumpAll extends GhidraScript {
    @Override
    public void run() throws Exception {
        String out = getScriptArgs()[0];
        // vtable slots point at code Ghidra left as labels: make them functions
        ghidra.program.model.mem.MemoryBlock text = currentProgram.getMemory().getBlock(".text");
        for (ghidra.program.model.mem.MemoryBlock b : currentProgram.getMemory().getBlocks()) {
            if (!b.getName().equals(".rdata") && !b.getName().equals(".data")) continue;
            for (ghidra.program.model.address.Address a = b.getStart(); a.compareTo(b.getEnd().subtract(3)) < 0; a = a.add(4)) {
                long v = currentProgram.getMemory().getInt(a) & 0xffffffffL;
                ghidra.program.model.address.Address t = toAddr(v);
                if (!text.contains(t) || getFunctionAt(t) != null) continue;
                if (getFunctionContaining(t) != null) continue;
                disassemble(t);
                createFunction(t, null);
            }
        }
        analyzeChanges(currentProgram);
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        try (PrintWriter w = new PrintWriter(new FileWriter(out + ".c"))) {
            for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
                DecompileResults r = di.decompileFunction(f, 60, monitor);
                w.println("// ==== " + f.getName() + " @ " + f.getEntryPoint());
                if (r.decompileCompleted()) w.println(r.getDecompiledFunction().getC());
                else w.println("// decompile failed: " + r.getErrorMessage());
            }
        }
        try (PrintWriter w = new PrintWriter(new FileWriter(out + ".strings.txt"))) {
            for (Data d : currentProgram.getListing().getDefinedData(true)) { if (!d.hasStringValue()) continue;
                StringBuilder refs = new StringBuilder();
                for (Reference ref : getReferencesTo(d.getAddress())) {
                    Function f = getFunctionContaining(ref.getFromAddress());
                    refs.append(" ").append(f == null ? ref.getFromAddress().toString() : f.getName());
                }
                w.println(d.getAddress() + "\t" + d.getDefaultValueRepresentation() + "\t<-" + refs);
            }
        }
    }
}
