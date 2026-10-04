# Print fib(0..14) separated by spaces, then exit(0)
        li   s0, 0          # a
        li   s1, 1          # b
        li   s2, 15         # count
loop:   mv   a0, s0
        li   a7, 1          # print int
        ecall
        li   a0, 32         # ' '
        li   a7, 11
        ecall
        add  t0, s0, s1
        mv   s0, s1
        mv   s1, t0
        addi s2, s2, -1
        bnez s2, loop
        li   a0, 0
        li   a7, 93
        ecall
