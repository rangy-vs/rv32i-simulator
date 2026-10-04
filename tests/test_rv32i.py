import pytest

from rv32i.assembler import AsmError, assemble
from rv32i.cpu import CPU, CpuError


def word(src: str) -> int:
    return int.from_bytes(assemble(src)[:4], "little")


def run_src(src: str, **kw) -> CPU:
    cpu = CPU(**kw)
    cpu.load_program(assemble(src))
    cpu.run()
    return cpu


def run_file(path: str) -> CPU:
    return run_src(open(path).read())


# ---- encoder: expected words checked against the RISC-V spec / reference assemblers ----
@pytest.mark.parametrize("src,expected", [
    ("addi x1, x0, 5", 0x00500093),
    ("add x3, x1, x2", 0x002081B3),
    ("sub x3, x1, x2", 0x402081B3),
    ("lw x2, 8(x1)", 0x0080A103),
    ("sw x2, 8(x1)", 0x0020A423),
    ("beq x1, x2, 8", 0x00208463),
    ("jal x1, 8", 0x008000EF),
    ("lui x5, 0x12345", 0x123452B7),
    ("ecall", 0x00000073),
])
def test_encoding(src, expected):
    if src.startswith(("beq", "jal")):  # immediates are label-relative; use a label 8 bytes ahead
        mn, _, rest = src.partition(" ")
        ops = [o.strip() for o in rest.split(",")]
        ops[-1] = "tgt"
        src = f"{mn} {', '.join(ops)}\n nop\n tgt: nop"
    assert word(src) == expected


# ---- behaviour ----
def test_x0_is_hardwired_zero():
    cpu = run_src("li t0, 7\n addi x0, t0, 5\n li a7, 93\n ecall")
    assert cpu.regs[0] == 0


def test_li_large_constants_and_sign():
    cpu = run_src("li a0, 0x12345FFF\n li a1, -1\n li a2, 0x80000000\n li a7, 93\n ecall")
    assert cpu.regs[10] == 0x12345FFF and cpu.regs[11] == 0xFFFFFFFF and cpu.regs[12] == 0x80000000


def test_signed_vs_unsigned_compare():
    cpu = run_src("""
        li t0, -1
        li t1, 1
        slt  a0, t0, t1     # signed:   -1 < 1  -> 1
        sltu a1, t0, t1     # unsigned: 0xFFFFFFFF < 1 -> 0
        li a7, 93
        ecall""")
    assert (cpu.regs[10], cpu.regs[11]) == (1, 0)


def test_shifts_arithmetic_vs_logical():
    cpu = run_src("li t0, -16\n srai a0, t0, 2\n srli a1, t0, 28\n slli a2, t0, 1\n li a7, 93\n ecall")
    assert cpu.regs[10] == (-4 & 0xFFFFFFFF) and cpu.regs[11] == 0xF and cpu.regs[12] == (-32 & 0xFFFFFFFF)


def test_byte_and_half_loads_sign_extend():
    cpu = run_src("""
        la t0, d
        lb  a0, 0(t0)
        lbu a1, 0(t0)
        lh  a2, 0(t0)
        lhu a3, 0(t0)
        li a7, 93
        ecall
d:      .word 0x0000F0F0""")
    assert cpu.regs[10] == 0xFFFFFFF0 and cpu.regs[11] == 0xF0
    assert cpu.regs[12] == 0xFFFFF0F0 and cpu.regs[13] == 0xF0F0


def test_jal_ret_function_call():
    cpu = run_src("""
        li a0, 6
        jal double
        li a7, 93
        ecall
double: add a0, a0, a0
        ret""")
    assert cpu.exit_code == 12


def test_exit_code_and_output():
    cpu = run_src("li a0, 65\n li a7, 11\n ecall\n li a0, 3\n li a7, 93\n ecall")
    assert "".join(cpu.output) == "A" and cpu.exit_code == 3


# ---- error handling ----
def test_unknown_instruction():
    with pytest.raises(AsmError):
        assemble("frobnicate x1, x2")


def test_immediate_out_of_range():
    with pytest.raises(AsmError):
        assemble("addi x1, x0, 5000")


def test_duplicate_label():
    with pytest.raises(AsmError):
        assemble("a: nop\n a: nop")


def test_illegal_instruction_and_oob_access():
    cpu = CPU(mem_size=64)
    with pytest.raises(CpuError):
        cpu.run(max_steps=10)  # all-zero word is illegal
    with pytest.raises(CpuError):
        run_src("li t0, 0x7FFFF000\n lw a0, 0(t0)", mem_size=4096)


def test_infinite_loop_guard():
    cpu = CPU()
    cpu.load_program(assemble("spin: j spin"))
    with pytest.raises(CpuError):
        cpu.run(max_steps=1000)


# ---- real programs ----
def test_fibonacci():
    cpu = run_file("programs/fib.s")
    assert "".join(cpu.output).split() == "0 1 1 2 3 5 8 13 21 34 55 89 144 233 377".split()


def test_gcd():
    assert "".join(run_file("programs/gcd.s").output) == "21"


def test_sum_to_100():
    assert "".join(run_file("programs/sum_to_100.s").output) == "5050"


def test_bubble_sort():
    out = [int(x) for x in "".join(run_file("programs/bubble_sort.s").output).split()]
    assert out == sorted([42, -7, 19, 3, 88, 0, -50, 12])
