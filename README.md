# RV32I Simulator

![ci](../../actions/workflows/ci.yml/badge.svg)

A two-pass **assembler** and **instruction-set simulator** for the RISC-V RV32I base integer ISA, in pure Python (no dependencies).

```bash
python -m rv32i programs/bubble_sort.s --stats
# -50 -7 0 3 12 19 42 88
# 558 instructions retired, exit code 0
#   alu 41.6% | branch 21.5% | load 19.0% | jump 8.8% | store 6.1% | system 3.0%
```

## What it covers
- **Assembler:** all RV32I integer instructions, labels, `.word`, and pseudo-instructions (`li`, `la`, `mv`, `j`, `ret`, `beqz`, `bnez`, `bgt`, `ble`, `not`, `neg`, `nop`). `li` picks 1 or 2 instructions by value; `la` is always 2 so label addresses are stable in pass 1.
- **CPU:** fetch/decode/execute for R/I/S/B/U/J formats, sign-extension, signed vs unsigned compares, arithmetic vs logical shifts, byte/half loads, `x0` hard-wired to zero, bounds-checked memory, step limit to catch infinite loops.
- **Syscalls via `ecall`:** print int, print char, exit (a Linux-like subset).
- **Tooling:** `--trace` (per-instruction log) and `--stats` (instruction-mix histogram).

## Testing
25 tests (`python -m pytest -q`): encoder output checked against hand-computed spec encodings, per-instruction semantics, error paths (bad opcode, out-of-range immediate, duplicate label, out-of-bounds access, infinite loop), and four real programs (Fibonacci, GCD, bubble sort, sum 1..100).

## Limits (on purpose)
RV32I only: no M/A/F/C extensions, no CSRs, no privilege modes, no pipeline model. Next steps: add the M extension, an RV32I conformance run (riscv-tests), and a 5-stage pipeline model with hazard stats.
