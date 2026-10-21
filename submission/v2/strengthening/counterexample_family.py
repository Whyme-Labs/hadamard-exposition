"""Exact witnesses for the expository counterexample family derived after the study.

The general claim is proved in conjecture-companion.md. Finite checks corroborate
that proof; they do not prove the Hadamard conjecture or establish novelty.
"""
from fractions import Fraction
import json
import itertools


def sylvester_integer(n: int) -> list[list[int]]:
    if type(n) is not int or n<1 or n & (n-1):
        raise ValueError('power-of-two dimension required')
    return [[1-2*((i&j).bit_count()%2) for j in range(n)] for i in range(n)]


def exact_family(bits: int, n: int, signs: tuple[int,int,int]=(1,1,1)) -> dict:
    if type(bits) is not int or bits<3 or type(n) is not int or n<4 or n & (n-1):
        raise ValueError('bits >= 3 and power-of-two n >= 4 required')
    if len(signs)!=3 or any(type(s) is not int or s not in (-1,1) for s in signs):
        raise ValueError("three supported coordinate signs required")
    levels=2**(bits-1)-1
    h=sylvester_integer(n)
    # Work before division by sqrt(n), so every arithmetic operation is rational.
    u=[levels*signs[0]*h[0][j]+signs[1]*h[1][j]+signs[2]*h[2][j] for j in range(n)]
    magnitudes=list(map(abs,u))
    counts={value:magnitudes.count(value) for value in set(magnitudes)}
    expected={levels+2:n//4,levels:n//2,levels-2:n//4}
    if counts!=expected:
        raise ArithmeticError('Sylvester multiplicities do not match the proof')
    scale=Fraction(levels+2,levels)
    rounded=[round(Fraction(v)/scale)*scale for v in u]
    squared=sum((a-b)**2 for a,b in zip(u,rounded))
    relative=squared/(n*(levels*levels+2))
    predicted=(Fraction(1,66) if bits==3 else Fraction(11,3332) if bits==4
               else Fraction(24,levels*levels*(levels*levels+2)))
    if relative!=predicted or relative<=0 or (levels+2)**2>=levels*levels*n:
        raise ArithmeticError('family identity or strict peak reduction failed')
    # Set W=e_0. Q.T W is constant signs[0]/sqrt(n), hence its
    # own full-width maxabs quantizer represents every weight exactly.
    linear_observed = signs[0] * sum(rounded) / n
    linear_error = (linear_observed-levels)**2 / levels**2
    linear_predicted = (Fraction(1,81) if bits==3 else Fraction(1,784) if bits==4
                        else Fraction(16,levels**4))
    if linear_error != linear_predicted or linear_error <= 0:
        raise ArithmeticError('linear-layer corollary failed')
    return {'linear_target':levels,'linear_observed':str(linear_observed),
            'linear_output_relative_squared_error':str(linear_error),
            'rotated_weight_exactly_representable':True,'bits':bits,'n':n,'levels':levels,'input_prefix':[levels,1,1],
            'remaining_input_coordinates':0,'original_error':0,
            'relative_squared_error':str(relative),'predicted_error':str(predicted),
            'supported_signs':list(signs),'unnormalized_absolute_multiplicities':{str(k):v for k,v in sorted(counts.items())},
            'peak_ratio_squared':str(Fraction((levels+2)**2,n*levels*levels)),
            'peak_strictly_lower':True}


if __name__=='__main__':
    result={'scope':'Algebraic extension derived after the prespecified study; not a preregistered empirical endpoint.',
            'priority_claim':False,'examples':[exact_family(b,n) for b in range(3,17) for n in (4,8,16,32,64,128)]}
    result['all_sign_cases_checked']=0
    for bits in range(3,17):
        for n in (4,8,16,32,64,128):
            for signs in itertools.product((-1,1),repeat=3):
                exact_family(bits,n,signs)
                result['all_sign_cases_checked']+=1
    print(json.dumps(result,indent=2))
