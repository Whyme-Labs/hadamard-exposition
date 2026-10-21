"""Direct rational checks of the all-Hadamard extension; not a novelty claim."""
from fractions import Fraction
import itertools
import json
from exact_checks import is_hadamard, paley_prime
from counterexample_family import sylvester_integer


def witness(h: list[list[int]], bits: int, support=(0, 1, 2), signs=(1, 1, 1)) -> dict:
    if not is_hadamard(h) or len(h) < 4:
        raise ValueError('an exact Hadamard matrix of order at least four is required')
    n = len(h)
    if type(bits) is not int or bits < 3:
        raise ValueError('integer bit width at least three is required')
    if len(support) != 3 or len(set(support)) != 3 or any(type(i) is not int or not 0 <= i < n for i in support):
        raise ValueError('three distinct valid support rows required')
    if len(signs) != 3 or any(type(s) is not int or s not in (-1, 1) for s in signs):
        raise ValueError('three integer signs required')
    a, b, c = support
    k = 2**(bits-1)-1
    # u = x D H before the common 1/sqrt(n). No floating-point operations.
    u = [k*signs[0]*h[a][j] + signs[1]*h[b][j] + signs[2]*h[c][j] for j in range(n)]
    transformed_peak = max(map(abs, u))
    scale = Fraction(transformed_peak, k)
    rounded = [round(Fraction(v)/scale)*scale for v in u]
    reconstruction = sum((v-r)**2 for v, r in zip(u, rounded)) / (n*(k*k+2))
    output = sum(signs[0]*h[a][j]*rounded[j] for j in range(n)) / n
    output_error = (output-k)**2 / (k*k)
    expected_reconstruction = Fraction(1, 66) if bits == 3 else Fraction(11, 3332) if bits == 4 else Fraction(24, k*k*(k*k+2))
    expected_output_error = Fraction(1, 81) if bits == 3 else Fraction(1, 784) if bits == 4 else Fraction(16, k**4)
    # Independent sign-pair counts prove why an arbitrary set of three rows works.
    counts = {pair: 0 for pair in itertools.product((-1, 1), repeat=2)}
    for j in range(n):
        counts[h[a][j]*h[b][j], h[a][j]*h[c][j]] += 1
    if set(counts.values()) != {n//4} or transformed_peak != k+2:
        raise ArithmeticError('three-row balance failed')
    if reconstruction != expected_reconstruction or output_error != expected_output_error:
        raise ArithmeticError('generalized error formula failed')
    if (k+2)**2 >= n*k*k:
        raise ArithmeticError('strict peak reduction failed')
    return {'order': n, 'bits': bits, 'support': list(support), 'signs': list(signs),
            'each_sign_pair_count': n//4, 'reconstruction_error': str(reconstruction),
            'linear_output': str(output), 'linear_output_error': str(output_error),
            'peak_ratio_squared': str(Fraction((k+2)**2, n*k*k))}


def verify_all() -> dict:
    records = []
    for label, h in [('Paley-'+str(q), paley_prime(q)) for q in (3,7,11,19,23,31,43)] + [('Sylvester-16', sylvester_integer(16))]:
        n = len(h)
        # Includes arbitrary support, row/column sign changes and column reversal.
        changed = [[h[i][n-1-j] * (-1 if i % 2 else 1) * (-1 if j % 3 else 1)
                    for j in range(n)] for i in range(n)]
        for variant, matrix in [('original', h), ('row-column-equivalent', changed)]:
            for support in ((0,1,2), (n-1, n//2, 0)):
                for bits in (3,4,5,8,16):
                    for signs in itertools.product((-1,1), repeat=3):
                        records.append({'construction':label,'variant':variant,**witness(matrix,bits,support,signs)})
    return {'schema':'hadamard-all-matrices-witnesses.v1','status':'passed',
            'scope':'Finite corroboration of the separately written all-Hadamard proof. Derived after the registered study; no empirical preregistration or literature-priority claim.',
            'cases':len(records),'non_power_of_two_orders':[12,20,24,44],'records':records}


if __name__ == '__main__':
    print(json.dumps(verify_all(), indent=2))
