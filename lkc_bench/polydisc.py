"""Generate the polynomial bank and compute exact discriminants independently."""
from __future__ import annotations

import hashlib
import hmac
import json

WIDTH_BANDS = (15, 36, 205, 1001, 3484)
THRESHOLDS = (1 << 26, 1 << 36, 1 << 46, 1 << 56)
LCG_MULTIPLIER = 6364136223846793005
LCG_INCREMENT = 1442695040888963407
WORD_MASK = (1 << 64) - 1


def coefficient_width(kbits: int, position: int) -> int:
    """Return the specified width at a high-to-low non-leading coefficient position."""
    if kbits <= 64:
        base = 2 * max(0, 36 - kbits) // 7
        width = base + (kbits - base) * position // (10 + base)
    else:
        numerator = (kbits - 3) * (2448 * position - 2 * position * position)
        width = 3 + (numerator + 57599) // 57600
    return min(kbits, max(2, width))


def polynomial_coefficients(n: int) -> list[int]:
    """Produce all 25 coefficients, with the leading one first."""
    if type(n) is not int or n < 0:
        raise ValueError("A polynomial input must be a natural number.")
    kbits = WIDTH_BANDS[sum(n >= threshold for threshold in THRESHOLDS)]
    state = (LCG_MULTIPLIER * (n + 1) + LCG_INCREMENT) & WORD_MASK
    coefficients = [1]
    for position in range(1, 25):
        width = coefficient_width(kbits, position)
        words = (width + 63) // 64
        chunks = []
        for _ in range(words):
            state = (LCG_MULTIPLIER * state + LCG_INCREMENT) & WORD_MASK
            chunks.append(state.to_bytes(8, "little"))
        word = int.from_bytes(b"".join(chunks), "little")
        coefficient = (word >> (64 * words - width)) - (1 << (width - 1))
        coefficients.append(coefficient or 1)
    return coefficients


def polynomial_metadata(n: int) -> dict:
    coefficients = polynomial_coefficients(n)
    level = sum(n >= threshold for threshold in THRESHOLDS)
    return {"degree": 24, "level": level, "coefficient_width_bits": WIDTH_BANDS[level],
            "height_bits": max(abs(value).bit_length() for value in coefficients[1:]),
            "total_coefficient_bits": sum(abs(value).bit_length() for value in coefficients[1:])}


def determinant(matrix: list[list[int]]) -> int:
    """Evaluate an integer determinant with row pivots and exact Bareiss divisions."""
    size = len(matrix)
    if any(len(row) != size for row in matrix):
        raise ValueError("A determinant requires a square matrix.")
    if not size:
        return 1
    rows = [list(row) for row in matrix]
    previous, sign = 1, 1
    for column in range(size - 1):
        pivot_row = next((index for index in range(column, size) if rows[index][column]), None)
        if pivot_row is None:
            return 0
        if pivot_row != column:
            rows[column], rows[pivot_row] = rows[pivot_row], rows[column]
            sign = -sign
        pivot = rows[column][column]
        for index in range(column + 1, size):
            factor = rows[index][column]
            if factor or pivot != previous:
                for following in range(column + 1, size):
                    value = pivot * rows[index][following] - factor * rows[column][following]
                    quotient, remainder = divmod(value, previous)
                    if remainder:
                        raise ArithmeticError("Bareiss elimination encountered a non-exact division.")
                    rows[index][following] = quotient
            rows[index][column] = 0
        previous = pivot
    return sign * rows[-1][-1]


def polynomial_discriminant(coefficients: list[int]) -> int:
    """Use the full Sylvester matrix of a polynomial and its mathematical derivative."""
    if len(coefficients) < 2 or not coefficients[0]:
        raise ValueError("Supply a polynomial of positive degree with a nonzero leading coefficient.")
    degree = len(coefficients) - 1
    derivative = [(degree - index) * coefficient for index, coefficient in enumerate(coefficients[:-1])]
    size = 2 * degree - 1
    matrix = []
    for shift in range(degree - 1):
        matrix.append([0] * shift + list(coefficients) + [0] * (size - shift - len(coefficients)))
    for shift in range(degree):
        matrix.append([0] * shift + derivative + [0] * (size - shift - len(derivative)))
    value, remainder = divmod(determinant(matrix), coefficients[0])
    if remainder:
        raise ArithmeticError("The discriminant division by the leading coefficient was not exact.")
    return -value if degree * (degree - 1) // 2 % 2 else value


def polydisc_value(n: int) -> int:
    return polynomial_discriminant(polynomial_coefficients(n))


def public_inputs(groups: list[dict]) -> list[int]:
    """Reproduce the pinned uniform-integer sampler with its empty local key."""
    inputs = []
    domain = b"lean-kernel-challenge/grouped-evaluation-sample-v1\0"
    for group in groups:
        policy = group["sampling"]
        if policy["kind"] != "uniform_int":
            raise ValueError("Polynomial groups require uniform integer sampling.")
        lower, upper = policy["min"], policy["max"]
        capacity = upper - lower + 1
        if lower < 0 or not 0 < capacity <= 1 << 256 or not 0 < policy["count"] <= capacity:
            raise ValueError("Invalid polynomial sampling range or count.")
        limit = (1 << 256) - (1 << 256) % capacity
        used = set()
        for case in range(policy["count"]):
            attempt = 0
            while True:
                message = json.dumps(["polydisc", group["id"], case, "uniform-int", attempt],
                                     separators=(",", ":")).encode()
                value = int.from_bytes(hmac.new(b"", domain + message, hashlib.sha256).digest(), "big")
                attempt += 1
                if value >= limit:
                    continue
                n = lower + value % capacity
                if n not in used:
                    used.add(n)
                    inputs.append(n)
                    break
    return inputs
