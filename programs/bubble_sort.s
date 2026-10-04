# Bubble sort an array in memory (data lives after the code via .word), print it.
        la   s0, array
        li   s1, 8                  # n
outer:  li   t0, 0                  # swapped = 0
        li   t1, 1                  # i = 1
inner:  bge  t1, s1, check
        slli t2, t1, 2
        add  t2, t2, s0             # &array[i]
        lw   t3, -4(t2)             # array[i-1]
        lw   t4, 0(t2)              # array[i]
        ble  t3, t4, noswap
        sw   t4, -4(t2)
        sw   t3, 0(t2)
        li   t0, 1
noswap: addi t1, t1, 1
        j    inner
check:  bnez t0, outer
        li   t1, 0
print:  slli t2, t1, 2
        add  t2, t2, s0
        lw   a0, 0(t2)
        li   a7, 1
        ecall
        li   a0, 32
        li   a7, 11
        ecall
        addi t1, t1, 1
        blt  t1, s1, print
        li   a0, 0
        li   a7, 93
        ecall
array:  .word 42, -7, 19, 3, 88, 0, -50, 12
