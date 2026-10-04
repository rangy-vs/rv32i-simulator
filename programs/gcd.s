# Euclid's algorithm using only subtraction: gcd(1071, 462) = 21
        li   a0, 1071
        li   a1, 462
again:  beq  a0, a1, done
        blt  a0, a1, less
        sub  a0, a0, a1
        j    again
less:   sub  a1, a1, a0
        j    again
done:   li   a7, 1
        ecall               # print a0
        li   a0, 0
        li   a7, 93
        ecall
