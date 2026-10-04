"""Two-pass assembler for RV32I with common pseudo-instructions.

Supported pseudos: nop, li, la, mv, not, neg, j, jr, ret, beqz, bnez, bgt, ble.
Directives: .word <int|label>[, ...]   Comments start with '#'.
"""
from __future__ import annotations

import re

from . import isa

MASK = 0xFFFFFFFF


class AsmError(Exception):
    pass


def _reg(tok: str, line: int) -> int:
    try:
        return isa.REGS[tok.strip()]
    except KeyError:
        raise AsmError(f"line {line}: unknown register {tok!r}")


def _int(tok: str) -> int:
    return int(tok.strip(), 0)


def _split_hi_lo(value: int) -> tuple[int, int]:
    """Split a 32-bit value into (upper 20 bits, signed lower 12) for lui+addi."""
    value &= MASK
    lo = value & 0xFFF
    if lo >= 0x800:
        lo -= 0x1000
    hi = ((value - lo) >> 12) & 0xFFFFF
    return hi, lo


def enc_r(f7, rs2, rs1, f3, rd, op): return (f7 << 25) | (rs2 << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | op
def enc_i(imm, rs1, f3, rd, op): return ((imm & 0xFFF) << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | op
def enc_s(imm, rs2, rs1, f3, op):
    return (((imm >> 5) & 0x7F) << 25) | (rs2 << 20) | (rs1 << 15) | (f3 << 12) | ((imm & 0x1F) << 7) | op
def enc_b(imm, rs2, rs1, f3, op):
    return (((imm >> 12) & 1) << 31) | (((imm >> 5) & 0x3F) << 25) | (rs2 << 20) | (rs1 << 15) | \
           (f3 << 12) | (((imm >> 1) & 0xF) << 8) | (((imm >> 11) & 1) << 7) | op
def enc_u(imm20, rd, op): return ((imm20 & 0xFFFFF) << 12) | (rd << 7) | op
def enc_j(imm, rd, op):
    return (((imm >> 20) & 1) << 31) | (((imm >> 1) & 0x3FF) << 21) | (((imm >> 11) & 1) << 20) | \
           (((imm >> 12) & 0xFF) << 12) | (rd << 7) | op


def _clean(source: str):
    """Yield (lineno, label_or_None, text) tuples."""
    for n, raw in enumerate(source.splitlines(), 1):
        text = raw.split("#")[0].strip()
        while text:
            m = re.match(r"^([A-Za-z_.][\w.]*):\s*(.*)$", text)
            if not m:
                break
            yield n, m.group(1), ""
            text = m.group(2)
        if text:
            yield n, None, text


def _expand(mn: str, ops: list[str], line: int) -> list[tuple[str, list[str]]]:
    """Expand pseudo-instructions into real ones (sizes must be known in pass 1)."""
    if mn == "nop": return [("addi", ["x0", "x0", "0"])]
    if mn == "mv": return [("addi", [ops[0], ops[1], "0"])]
    if mn == "not": return [("xori", [ops[0], ops[1], "-1"])]
    if mn == "neg": return [("sub", [ops[0], "x0", ops[1]])]
    if mn == "j": return [("jal", ["x0", ops[0]])]
    if mn == "jr": return [("jalr", ["x0", f"0({ops[0]})"])]
    if mn == "ret": return [("jalr", ["x0", "0(ra)"])]
    if mn == "beqz": return [("beq", [ops[0], "x0", ops[1]])]
    if mn == "bnez": return [("bne", [ops[0], "x0", ops[1]])]
    if mn == "bgt": return [("blt", [ops[1], ops[0], ops[2]])]
    if mn == "ble": return [("bge", [ops[1], ops[0], ops[2]])]
    if mn == "jal" and len(ops) == 1: return [("jal", ["ra", ops[0]])]
    if mn == "li":
        try:
            v = _int(ops[1])
        except ValueError:
            raise AsmError(f"line {line}: li needs a number, got {ops[1]!r}")
        if -2048 <= v < 2048:
            return [("addi", [ops[0], "x0", str(v)])]
        hi, lo = _split_hi_lo(v)
        return [("lui", [ops[0], str(hi)]), ("addi", [ops[0], ops[0], str(lo)])]
    if mn == "la":  # always 2 instructions so pass 1 sizes are fixed
        return [("lui@hi", [ops[0], ops[1]]), ("addi@lo", [ops[0], ops[0], ops[1]])]
    return [(mn, ops)]


def assemble(source: str, base: int = 0) -> bytes:
    labels: dict[str, int] = {}
    items: list[tuple[int, int, str, list[str]]] = []  # (addr, line, mnemonic, operands)
    pc = base
    for line, label, text in _clean(source):
        if label:
            if label in labels:
                raise AsmError(f"line {line}: duplicate label {label}")
            labels[label] = pc
            continue
        mn, _, rest = text.partition(" ")
        mn = mn.lower()
        ops = [o.strip() for o in rest.split(",")] if rest.strip() else []
        if mn == ".word":
            for o in ops:
                items.append((pc, line, ".word", [o]))
                pc += 4
            continue
        for emn, eops in _expand(mn, ops, line):
            items.append((pc, line, emn, eops))
            pc += 4

    out = bytearray()
    for addr, line, mn, ops in items:
        word = _encode(mn, ops, addr, labels, line) & MASK
        out += word.to_bytes(4, "little")
    return bytes(out)


def _val(tok: str, labels: dict, line: int) -> int:
    tok = tok.strip()
    if tok in labels:
        return labels[tok]
    try:
        return _int(tok)
    except ValueError:
        raise AsmError(f"line {line}: bad immediate or unknown label {tok!r}")


def _mem(tok: str, labels, line):
    m = re.match(r"^(.*)\((\w+)\)$", tok.strip())
    if not m:
        raise AsmError(f"line {line}: expected imm(reg), got {tok!r}")
    return _val(m.group(1) or "0", labels, line), _reg(m.group(2), line)


def _encode(mn, ops, addr, labels, line) -> int:
    try:
        if mn == ".word":
            return _val(ops[0], labels, line)
        if mn in isa.R_TYPE:
            f3, f7 = isa.R_TYPE[mn]
            return enc_r(f7, _reg(ops[2], line), _reg(ops[1], line), f3, _reg(ops[0], line), isa.OP_REG)
        if mn in isa.I_ALU:
            imm = _val(ops[2], labels, line)
            _check_range(imm, 12, line)
            return enc_i(imm, _reg(ops[1], line), isa.I_ALU[mn], _reg(ops[0], line), isa.OP_IMM)
        if mn in isa.I_SHIFT:
            f3, f7 = isa.I_SHIFT[mn]
            sh = _val(ops[2], labels, line)
            if not 0 <= sh < 32:
                raise AsmError(f"line {line}: shift amount out of range")
            return enc_i((f7 << 5) | sh, _reg(ops[1], line), f3, _reg(ops[0], line), isa.OP_IMM)
        if mn in isa.LOADS:
            imm, rs1 = _mem(ops[1], labels, line)
            _check_range(imm, 12, line)
            return enc_i(imm, rs1, isa.LOADS[mn], _reg(ops[0], line), isa.OP_LOAD)
        if mn in isa.STORES:
            imm, rs1 = _mem(ops[1], labels, line)
            _check_range(imm, 12, line)
            return enc_s(imm, _reg(ops[0], line), rs1, isa.STORES[mn], isa.OP_STORE)
        if mn in isa.BRANCHES:
            off = _val(ops[2], labels, line) - addr
            _check_range(off, 13, line)
            return enc_b(off, _reg(ops[1], line), _reg(ops[0], line), isa.BRANCHES[mn], isa.OP_BRANCH)
        if mn == "jal":
            off = _val(ops[1], labels, line) - addr
            _check_range(off, 21, line)
            return enc_j(off, _reg(ops[0], line), isa.OP_JAL)
        if mn == "jalr":
            imm, rs1 = _mem(ops[1], labels, line)
            return enc_i(imm, rs1, 0, _reg(ops[0], line), isa.OP_JALR)
        if mn == "lui":
            return enc_u(_val(ops[1], labels, line), _reg(ops[0], line), isa.OP_LUI)
        if mn == "auipc":
            return enc_u(_val(ops[1], labels, line), _reg(ops[0], line), isa.OP_AUIPC)
        if mn == "lui@hi":
            hi, _ = _split_hi_lo(_val(ops[1], labels, line))
            return enc_u(hi, _reg(ops[0], line), isa.OP_LUI)
        if mn == "addi@lo":
            _, lo = _split_hi_lo(_val(ops[2], labels, line))
            return enc_i(lo, _reg(ops[1], line), 0, _reg(ops[0], line), isa.OP_IMM)
        if mn == "ecall":
            return isa.OP_SYSTEM
    except IndexError:
        raise AsmError(f"line {line}: wrong number of operands for {mn}")
    raise AsmError(f"line {line}: unknown instruction {mn!r}")


def _check_range(v: int, bits: int, line: int) -> None:
    if not -(1 << (bits - 1)) <= v < (1 << (bits - 1)):
        raise AsmError(f"line {line}: immediate {v} does not fit in {bits} signed bits")
