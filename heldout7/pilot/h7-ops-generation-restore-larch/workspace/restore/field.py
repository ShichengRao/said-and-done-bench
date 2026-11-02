"""GF(256) arithmetic used by the generation storage format."""
import itertools

def multiply(a, b):
    result = 0
    while b:
        if b & 1: result ^= a
        a <<= 1
        if a & 256: a ^= 0x11b
        b >>= 1
    return result

def power(a, n):
    result = 1
    while n:
        if n & 1: result = multiply(result, a)
        a = multiply(a, a); n >>= 1
    return result

def dot(coefficients, values):
    result = 0
    for a, b in zip(coefficients, values): result ^= multiply(a, b)
    return result

def solutions(rows, width):
    matrix = [list(c) + [v] for c, v in rows]
    pivots = []; rank = 0
    for column in range(width):
        pivot = next((i for i in range(rank, len(matrix)) if matrix[i][column]), None)
        if pivot is None: continue
        matrix[rank], matrix[pivot] = matrix[pivot], matrix[rank]
        inverse = power(matrix[rank][column], 254)
        matrix[rank] = [multiply(x, inverse) for x in matrix[rank]]
        for i in range(len(matrix)):
            if i != rank and matrix[i][column]:
                factor = matrix[i][column]
                matrix[i] = [a ^ multiply(factor, b) for a, b in zip(matrix[i], matrix[rank])]
        pivots.append(column); rank += 1
    if any(not any(row[:width]) and row[-1] for row in matrix): return []
    free = [i for i in range(width) if i not in pivots]
    if len(free) > 1: raise ValueError('unsupported encoding profile')
    result = []
    for values in itertools.product(range(256), repeat=len(free)):
        decoded = [0] * width
        for i, value in zip(free, values): decoded[i] = value
        for row, pivot in zip(matrix, pivots): decoded[pivot] = row[-1] ^ dot(row[:width], decoded)
        result.append(bytes(decoded))
    return result
