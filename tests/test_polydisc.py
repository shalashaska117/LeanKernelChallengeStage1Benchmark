"""Check the polynomial stream, exact determinant and public input sampler."""
import hashlib
import itertools
import json
import random
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from lkc_bench import diagnostic, polydisc
from lkc_bench.workspace import ROOT


def permutation_determinant(matrix):
    value = 0
    for permutation in itertools.permutations(range(len(matrix))):
        inversions = sum(left > right for i, left in enumerate(permutation) for right in permutation[i + 1:])
        term = (-1) ** inversions
        for row, column in enumerate(permutation):
            term *= matrix[row][column]
        value += term
    return value


def multiply(left, right):
    product = [0] * (len(left) + len(right) - 1)
    for i, a in enumerate(left):
        for j, b in enumerate(right):
            product[i + j] += a * b
    return product


class DeterminantTests(unittest.TestCase):
    def test_matches_permutation_sum_with_singular_and_pivoting_matrices(self):
        rng = random.Random(24047)
        matrices = [[], [[0]], [[-7]], [[0, 2], [3, 4]],
                    [[1, 2, 3], [1, 2, 3], [4, 5, 6]],
                    [[0, 0, 2], [0, -3, 4], [5, 6, 7]]]
        matrices.extend([[rng.randrange(-5, 6) for _ in range(size)] for _ in range(size)]
                        for size in range(2, 7) for _ in range(5))
        for matrix in matrices:
            before = [list(row) for row in matrix]
            with self.subTest(matrix=matrix):
                self.assertEqual(polydisc.determinant(matrix), permutation_determinant(matrix))
                self.assertEqual(matrix, before)

    def test_large_integer_diagonal_and_nonsquare_rejection(self):
        a, b, c = (1 << 400) + 3, -(1 << 700) + 5, (1 << 900) + 7
        self.assertEqual(polydisc.determinant([[a, 2, 3], [0, b, 4], [0, 0, c]]), a * b * c)
        with self.assertRaises(ValueError):
            polydisc.determinant([[1, 2], [3]])

    def test_linear_and_quadratic_discriminants_include_negative_leading_coefficients(self):
        for a in (-5, -1, 1, 2, 7):
            self.assertEqual(polydisc.polynomial_discriminant([a, 19]), 1)
            for b in range(-3, 4):
                for c in range(-3, 4):
                    with self.subTest(a=a, b=b, c=c):
                        self.assertEqual(polydisc.polynomial_discriminant([a, b, c]), b * b - 4 * a * c)

    def test_cubic_formula_and_repeated_roots(self):
        for a, b, c, d in ((1, 2, 3, 4), (-2, 5, -7, 11), (3, 0, -4, 2), (1, -3, 3, -1)):
            expected = b * b * c * c - 4 * a * c ** 3 - 4 * b ** 3 * d - 27 * a * a * d * d + 18 * a * b * c * d
            self.assertEqual(polydisc.polynomial_discriminant([a, b, c, d]), expected)
        for coefficients in ([], [1], [0, 1, 2]):
            with self.assertRaises(ValueError):
                polydisc.polynomial_discriminant(coefficients)

    def test_product_of_root_differences_through_degree_seven(self):
        for roots in ((-2, 0, 3), (-5, -1, 2, 8), (-3, 0, 1, 4, 7, 9, 12), (1, 2, 2, 5)):
            coefficients = [1]
            expected = 1
            for root in roots:
                coefficients = multiply(coefficients, [1, -root])
            for i, left in enumerate(roots):
                for right in roots[i + 1:]:
                    expected *= (left - right) ** 2
            self.assertEqual(polydisc.polynomial_discriminant(coefficients), expected)


class PolynomialStreamTests(unittest.TestCase):
    def test_documented_zero_input_coefficients_and_discriminant(self):
        coefficients = [1, 1, 18, -15, 75, 1, 27, -223, 347, -618, 503, 146, 1161,
                        -1499, -2101, 4094, -2473, 2364, 4018, -9725, 11989, 15716, 1630, 3984, -3697]
        expected = -1437475373221515423615709146748564172609479315133942550011246093047173337258904221338662563268181154344436806624326331905334612913874200226104057144892486060212832
        self.assertEqual(polydisc.polynomial_coefficients(0), coefficients)
        self.assertEqual(diagnostic.expected_values("polydisc", [0]), {0: expected})

    def test_all_width_band_boundaries_and_nonzero_coefficients(self):
        inputs = [0] + [n for threshold in polydisc.THRESHOLDS for n in (threshold - 1, threshold)]
        expected_widths = [15, 15, 36, 36, 205, 205, 1001, 1001, 3484]
        for n, width in zip(inputs, expected_widths):
            coefficients = polydisc.polynomial_coefficients(n)
            metadata = polydisc.polynomial_metadata(n)
            with self.subTest(n=n):
                self.assertEqual(len(coefficients), 25)
                self.assertEqual(coefficients[0], 1)
                self.assertTrue(all(coefficient != 0 for coefficient in coefficients))
                self.assertEqual(metadata["degree"], 24)
                self.assertEqual(metadata["coefficient_width_bits"], width)
                self.assertLessEqual(metadata["height_bits"], width)
                self.assertEqual(metadata["total_coefficient_bits"], sum(abs(c).bit_length() for c in coefficients[1:]))

    def test_little_endian_multiword_stream_matches_closed_form_lcg(self):
        n, kbits = 1 << 36, 205
        multiplier, increment, modulus = 6364136223846793005, 1442695040888963407, 1 << 64
        coefficients, updates = [1], 1
        for position in range(1, 25):
            numerator = (kbits - 3) * (102 * 24 * position - 2 * position * position)
            width = min(kbits, max(2, 3 - (-numerator // 57600)))
            count = -(-width // 64)
            states = []
            for update in range(updates + 1, updates + count + 1):
                power = multiplier ** update
                states.append((power * (n + 1) + increment * (power - 1) // (multiplier - 1)) % modulus)
            assembled = sum(state * modulus ** index for index, state in enumerate(states))
            coefficient = assembled // (1 << (64 * count - width)) - (1 << (width - 1))
            coefficients.append(coefficient if coefficient else 1)
            updates += count
        self.assertEqual(polydisc.polynomial_coefficients(n), coefficients)

    def test_zero_is_replaced_by_one_and_large_nat_preserves_stream_period(self):
        # The fifth non-leading coefficient at n=0 would otherwise be zero.
        state = 0 + 1
        for _ in range(6):
            state = (6364136223846793005 * state + 1442695040888963407) % (1 << 64)
        self.assertEqual((state >> 56) - 128, 0)
        self.assertEqual(polydisc.polynomial_coefficients(0)[5], 1)
        n = (1 << 64) + 37
        self.assertEqual(polydisc.polynomial_coefficients(n), polydisc.polynomial_coefficients(n + (1 << 64)))


class PublicPlanTests(unittest.TestCase):
    def test_uniform_sampler_matches_six_inputs_and_widths(self):
        manifest = json.loads((ROOT / "benchmarks/8-polydisc/cases.json").read_text())
        sampled = polydisc.public_inputs(manifest["groups"])
        self.assertEqual(sampled, [19337098, 9225987, 6476047012455, 10487306645701,
                                   5042242704654352709, 4530401864863699852])
        self.assertEqual(sampled, manifest["diagnostic_inputs"])
        self.assertEqual(sampled, diagnostic.DEFAULT_INPUTS["polydisc"])
        self.assertEqual([polydisc.polynomial_metadata(n)["coefficient_width_bits"] for n in sampled],
                         [15, 15, 205, 205, 3484, 3484])
        self.assertEqual(manifest["memory_mb"], diagnostic.DEFAULT_MEMORY_MB["polydisc"])

    def test_sampler_rejects_biased_digest_and_duplicate_then_keeps_case_order(self):
        group = {"id": "D1", "sampling": {"kind": "uniform_int", "min": 10, "max": 12, "count": 2}}
        values = iter([(1 << 256) - 1, 2, 2, 0])
        messages = []

        def digest(key, message, algorithm):
            self.assertEqual(key, b"")
            self.assertIs(algorithm, hashlib.sha256)
            messages.append(message)
            value = next(values).to_bytes(32, "big")
            return SimpleNamespace(digest=lambda: value)

        with patch.object(polydisc.hmac, "new", side_effect=digest):
            self.assertEqual(polydisc.public_inputs([group]), [12, 10])
        self.assertEqual([json.loads(message.split(b"\0", 1)[1]) for message in messages],
                         [["polydisc", "D1", case, "uniform-int", attempt]
                          for case, attempt in ((0, 0), (0, 1), (1, 0), (1, 1))])

    def test_invalid_sampler_configuration_fails(self):
        valid = {"kind": "uniform_int", "min": 10, "max": 12, "count": 2}
        for update in ({"kind": "packed_seed"}, {"count": 4}, {"count": 0}, {"min": -1},
                       {"min": 13}, {"max": 1 << 257}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                polydisc.public_inputs([{"id": "D1", "sampling": {**valid, **update}}])


if __name__ == "__main__":
    unittest.main()
