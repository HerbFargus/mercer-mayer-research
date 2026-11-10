// Decompile code at the given addresses (creating functions if needed): DecompAt.java out.c addr...
//@category BigTuna
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import java.io.*;

public class DecompAt extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        try (PrintWriter w = new PrintWriter(new FileWriter(args[0]))) {
            for (int i = 1; i < args.length; i++) {
                ghidra.program.model.address.Address a = toAddr(args[i]);
                if (getFunctionAt(a) == null) {
                    disassemble(a);
                    createFunction(a, null);
                }
                Function f = getFunctionAt(a);
                w.println("// ==== " + args[i]);
                if (f == null) { w.println("// no function"); continue; }
                DecompileResults r = di.decompileFunction(f, 60, monitor);
                w.println(r.decompileCompleted() ? r.getDecompiledFunction().getC() : "// failed " + r.getErrorMessage());
            }
        }
    }
}
