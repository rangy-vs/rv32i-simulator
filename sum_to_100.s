        li   t0, 100
        li   a0, 0
sum:    add  a0, a0, t0
        addi t0, t0, -1
        bnez t0, sum
        li   a7, 1
        ecall
        li   a0, 0
        li   a7, 93
        ecall
