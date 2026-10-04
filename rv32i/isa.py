"""RV32I instruction tables and register names."""

REGS = {f"x{i}": i for i in range(32)}
REGS.update({n: i for i, n in enumerate(
    "zero ra sp gp tp t0 t1 t2 s0 s1 a0 a1 a2 a3 a4 a5 a6 a7 "
    "s2 s3 s4 s5 s6 s7 s8 s9 s10 s11 t3 t4 t5 t6".split())})
REGS["fp"] = 8

# mnemonic -> (funct3, funct7)
R_TYPE = {"add": (0, 0x00), "sub": (0, 0x20), "sll": (1, 0), "slt": (2, 0), "sltu": (3, 0),
          "xor": (4, 0), "srl": (5, 0), "sra": (5, 0x20), "or": (6, 0), "and": (7, 0)}
I_ALU = {"addi": 0, "slti": 2, "sltiu": 3, "xori": 4, "ori": 6, "andi": 7}
I_SHIFT = {"slli": (1, 0x00), "srli": (5, 0x00), "srai": (5, 0x20)}
LOADS = {"lb": 0, "lh": 1, "lw": 2, "lbu": 4, "lhu": 5}
STORES = {"sb": 0, "sh": 1, "sw": 2}
BRANCHES = {"beq": 0, "bne": 1, "blt": 4, "bge": 5, "bltu": 6, "bgeu": 7}

OP_LOAD, OP_IMM, OP_AUIPC, OP_STORE, OP_REG = 0x03, 0x13, 0x17, 0x23, 0x33
OP_LUI, OP_BRANCH, OP_JALR, OP_JAL, OP_SYSTEM = 0x37, 0x63, 0x67, 0x6F, 0x73

# ecall numbers (placed in a7), a Linux-like subset
SYS_PRINT_INT, SYS_PRINT_CHAR, SYS_EXIT = 1, 11, 93
