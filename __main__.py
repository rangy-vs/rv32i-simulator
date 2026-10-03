"""Usage: python -m rv32i programs/fib.s [--trace] [--stats]"""
import argparse
import sys

from .assembler import AsmError, assemble
from .cpu import CPU, CpuError


def main() -> int:
    ap = argparse.ArgumentParser(prog="rv32i", description="RV32I assembler + simulator")
    ap.add_argument("source")
    ap.add_argument("--trace", action="store_true", help="print each executed instruction")
    ap.add_argument("--stats", action="store_true", help="print instruction-mix statistics")
    args = ap.parse_args()
    try:
        code = assemble(open(args.source).read())
        cpu = CPU()
        cpu.load_program(code)
        rc = cpu.run(trace=args.trace)
    except (AsmError, CpuError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print("".join(cpu.output))
    if args.stats:
        print(f"\n{cpu.steps} instructions retired, exit code {rc}")
        for k, v in sorted(cpu.mix.items(), key=lambda kv: -kv[1]):
            print(f"  {k:<7}{v:>8}  {v / cpu.steps:6.1%}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
