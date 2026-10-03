"""RV32I instruction-set simulator (user-level, single hart, little-endian)."""
from __future__ import annotations

from dataclasses import dataclass, field

from . import isa

MASK = 0xFFFFFFFF


def sext(value: int, bits: int) -> int:
    value &= (1 << bits) - 1
    return value - (1 << bits) if value >> (bits - 1) else value


def signed(v: int) -> int:
    return sext(v, 32)


class CpuError(Exception):
    pass


@dataclass
class CPU:
    mem_size: int = 1 << 20
    regs: list[int] = field(default_factory=lambda: [0] * 32)
    pc: int = 0
    halted: bool = False
    exit_code: int = 0
    steps: int = 0
    output: list[str] = field(default_factory=list)
    mix: dict[str, int] = field(default_factory=dict)  # instruction-class histogram

    def __post_init__(self):
        self.mem = bytearray(self.mem_size)
        self.regs[2] = self.mem_size  # sp starts at top of memory

    # ---- memory ----
    def load_program(self, code: bytes, base: int = 0) -> None:
        if base + len(code) > self.mem_size:
            raise CpuError("program does not fit in memory")
        self.mem[base:base + len(code)] = code
        self.pc = base

    def _check(self, addr: int, n: int) -> None:
        if addr < 0 or addr + n > self.mem_size:
            raise CpuError(f"memory access out of range: 0x{addr:08x} (pc=0x{self.pc:08x})")

    def read(self, addr: int, n: int) -> int:
        self._check(addr, n)
        return int.from_bytes(self.mem[addr:addr + n], "little")

    def write(self, addr: int, n: int, value: int) -> None:
        self._check(addr, n)
        self.mem[addr:addr + n] = (value & ((1 << (8 * n)) - 1)).to_bytes(n, "little")

    def set_reg(self, rd: int, value: int) -> None:
        if rd != 0:  # x0 is hard-wired to zero
            self.regs[rd] = value & MASK

    # ---- execution ----
    def step(self) -> None:
        inst = self.read(self.pc, 4)
        op = inst & 0x7F
        rd, f3 = (inst >> 7) & 31, (inst >> 12) & 7
        rs1, rs2, f7 = (inst >> 15) & 31, (inst >> 20) & 31, inst >> 25
        a, b = self.regs[rs1], self.regs[rs2]
        nxt = (self.pc + 4) & MASK

        def tally(name):
            self.mix[name] = self.mix.get(name, 0) + 1

        if op == isa.OP_REG:
            tally("alu")
            sh = b & 31
            if f3 == 0:   r = a - b if f7 == 0x20 else a + b
            elif f3 == 1: r = a << sh
            elif f3 == 2: r = int(signed(a) < signed(b))
            elif f3 == 3: r = int(a < b)
            elif f3 == 4: r = a ^ b
            elif f3 == 5: r = (signed(a) >> sh) if f7 == 0x20 else (a >> sh)
            elif f3 == 6: r = a | b
            else:         r = a & b
            self.set_reg(rd, r)
        elif op == isa.OP_IMM:
            tally("alu")
            imm = sext(inst >> 20, 12)
            sh = (inst >> 20) & 31
            if f3 == 0:   r = a + imm
            elif f3 == 1: r = a << sh
            elif f3 == 2: r = int(signed(a) < imm)
            elif f3 == 3: r = int(a < (imm & MASK))
            elif f3 == 4: r = a ^ imm
            elif f3 == 5: r = (signed(a) >> sh) if (inst >> 30) & 1 else (a >> sh)
            elif f3 == 6: r = a | imm
            else:         r = a & imm
            self.set_reg(rd, r)
        elif op == isa.OP_LOAD:
            tally("load")
            addr = (a + sext(inst >> 20, 12)) & MASK
            if f3 == 0:   r = sext(self.read(addr, 1), 8)
            elif f3 == 1: r = sext(self.read(addr, 2), 16)
            elif f3 == 2: r = self.read(addr, 4)
            elif f3 == 4: r = self.read(addr, 1)
            elif f3 == 5: r = self.read(addr, 2)
            else: raise CpuError(f"bad load funct3={f3}")
            self.set_reg(rd, r)
        elif op == isa.OP_STORE:
            tally("store")
            imm = sext(((inst >> 25) << 5) | ((inst >> 7) & 31), 12)
            n = {0: 1, 1: 2, 2: 4}.get(f3)
            if n is None: raise CpuError(f"bad store funct3={f3}")
            self.write((a + imm) & MASK, n, b)
        elif op == isa.OP_BRANCH:
            tally("branch")
            imm = sext(((inst >> 31) << 12) | (((inst >> 7) & 1) << 11) |
                       (((inst >> 25) & 0x3F) << 5) | (((inst >> 8) & 0xF) << 1), 13)
            taken = {0: a == b, 1: a != b, 4: signed(a) < signed(b), 5: signed(a) >= signed(b),
                     6: a < b, 7: a >= b}.get(f3)
            if taken is None: raise CpuError(f"bad branch funct3={f3}")
            if taken: nxt = (self.pc + imm) & MASK
        elif op == isa.OP_JAL:
            tally("jump")
            imm = sext(((inst >> 31) << 20) | (((inst >> 12) & 0xFF) << 12) |
                       (((inst >> 20) & 1) << 11) | (((inst >> 21) & 0x3FF) << 1), 21)
            self.set_reg(rd, nxt)
            nxt = (self.pc + imm) & MASK
        elif op == isa.OP_JALR:
            tally("jump")
            target = (a + sext(inst >> 20, 12)) & ~1 & MASK
            self.set_reg(rd, nxt)
            nxt = target
        elif op == isa.OP_LUI:
            tally("alu"); self.set_reg(rd, inst & 0xFFFFF000)
        elif op == isa.OP_AUIPC:
            tally("alu"); self.set_reg(rd, self.pc + (inst & 0xFFFFF000))
        elif op == isa.OP_SYSTEM and inst == isa.OP_SYSTEM:
            tally("system")
            call = self.regs[17]
            if call == isa.SYS_EXIT:
                self.halted, self.exit_code = True, signed(self.regs[10])
            elif call == isa.SYS_PRINT_INT:
                self.output.append(str(signed(self.regs[10])))
            elif call == isa.SYS_PRINT_CHAR:
                self.output.append(chr(self.regs[10] & 0xFF))
            else:
                raise CpuError(f"unsupported ecall {call}")
        else:
            raise CpuError(f"illegal instruction 0x{inst:08x} at pc=0x{self.pc:08x}")
        self.pc = nxt
        self.steps += 1

    def run(self, max_steps: int = 5_000_000, trace: bool = False) -> int:
        while not self.halted:
            if self.steps >= max_steps:
                raise CpuError(f"exceeded {max_steps} steps (infinite loop?)")
            if trace:
                print(f"{self.steps:>6} pc=0x{self.pc:08x} inst=0x{self.read(self.pc, 4):08x}")
            self.step()
        return self.exit_code
