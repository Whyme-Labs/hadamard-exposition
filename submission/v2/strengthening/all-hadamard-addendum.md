---
title: "The failure does not depend on the Hadamard construction"
subtitle: "An all-Hadamard extension of the quantization counterexample"
author: "Wei Meng Soh · Whyme Labs"
lang: en
---

Addendum to version 2, prepared 21 October 2026. This derivation follows the registered synthetic study. It is not a preregistered empirical endpoint, a solution of the Hadamard conjecture, or a claim of literature priority. AI assistance was used in the derivation, writing and checks.

## A stronger statement with the same fixed input

The version-2 article proved its counterexample for binary-indexed Sylvester matrices with arbitrary diagonal signs. That restriction is unnecessary. Pairwise orthogonality of three sign rows supplies all the balance the proof needs.

**Theorem.** Fix an integer $n\geq4$ for which a real Hadamard matrix exists, a bit width $b\geq3$, and $K=2^{b-1}-1$. Choose three distinct row indices $a,c,d$ once and set

$$x=K e_a+e_c+e_d,\qquad w=e_a.$$

For **every** order-$n$ Hadamard matrix $H$, put $Q=H/\sqrt n$. Apply full-width symmetric maxabs quantization with codes $-K,\ldots,K$ and nearest rounding with ties to even. The original $x$ and $w$ are represented exactly. The rotated activation peak is $(K+2)/\sqrt n<K$, but both the activation reconstruction error and the linear-output error after quantizing both operands are positive. Their relative squared values do not depend on $n$ or on $H$:

| Bit width | Activation reconstruction error | Linear-output error |
|---|---:|---:|
| $b=3$ | $1/66$ | $1/81$ |
| $b=4$ | $11/3332$ | $1/784$ |
| $b\geq5$ | $24/[K^2(K^2+2)]$ | $16/K^4$ |

The quantifiers matter. For fixed $n,b,a,c,d$, the input is fixed before choosing $H$. Randomly choosing a different Hadamard matrix, or changing its row or column signs and permutations, cannot remove this particular failure. Those operations still produce a Hadamard matrix. This is not an assertion about arbitrary real orthogonal matrices or arbitrary quantizers.

## Why three orthogonal sign rows are enough

Define two sign sequences by

$$p_j=H_{aj}H_{cj},\qquad q_j=H_{aj}H_{dj}.$$

Orthogonality gives

$$\sum_jp_j=0,\qquad \sum_jq_j=0,\qquad \sum_jp_jq_j=\sum_jH_{cj}H_{dj}=0.$$

For $s,t\in\{-1,+1\}$, the number of columns with $p_j=s$ and $q_j=t$ is

$$N_{s,t}=\frac14\sum_j(1+s p_j)(1+t q_j)=\frac n4.$$

This identity works for any three distinct rows, including rows of a Paley matrix at a non-power-of-two order. No recursive transform structure is involved.

Write $u=xH$. Multiplying each coordinate by the corresponding sign in row $a$ gives

$$v_j=H_{aj}u_j=K+p_j+q_j.$$

Thus $v_j$ takes the positive values $K+2,K,K-2$ with multiplicities $n/4,n/2,n/4$. In particular, the transformed peak is $(K+2)/\sqrt n$. It is smaller than $K$ because $\sqrt n\geq2$ and $K>2$.

## Rounding and the linear product

Work before dividing by $\sqrt n$, using scale $s=(K+2)/K$. Let $R(v)=s\operatorname{round}(v/s)$. Symmetric ties-to-even rounding is odd, so multiplying a coordinate by $H_{aj}$ also multiplies its rounded value by $H_{aj}$. The activation error is therefore

$$\frac{\|\widehat{xQ}-xQ\|_2^2}{\|x\|_2^2}
=\frac{\sum_j[R(v_j)-v_j]^2}{n(K^2+2)}.$$

For $b\geq5$, $K\geq15$. The codes for $K+2,K,K-2$ are $K,K-2,K-4$ because

$$\frac{K^2}{K+2}=K-2+\frac4{K+2},\qquad
\frac{K(K-2)}{K+2}=K-4+\frac8{K+2},$$

and both fractions are below one half. The corresponding errors are $0,-4/K,-8/K$. Averaging their squared values with the proved multiplicities gives $24/K^2$ before division by the original energy $K^2+2$. This proves the third activation formula.

The rotated weight has coordinates $(Q^{\mathsf T}w)_j=H_{aj}/\sqrt n$. Its full-width maxabs quantizer represents every coordinate exactly, with signed code $\pm K$. Consequently the quantized output is

$$\widehat{xQ}\,\widehat{Q^{\mathsf T}w}=\frac1n\sum_jR(v_j).$$

At $b\geq5$ this is $K-4/K$, whereas the exact output is $xw=K$. The relative squared output error is $16/K^4$.

At three bits, direct rounding at scale $5/3$ gives the values $5,10/3,5/3$ for inputs $5,3,1$. The weighted mean is $10/3$, giving output error $1/81$ and activation error $1/66$. At four bits, scale $9/7$ gives $9,45/7,36/7$ for inputs $9,7,5$. The weighted mean is $27/4$, giving output error $1/784$ and activation error $11/3332$. This proves every row of the table.

## What this adds to the exposition

Hadamard existence guarantees perfect entrywise balance. Even if the conjecture were established in every dimension divisible by four, that would not imply a universal rounding improvement for this quantizer. The counterexample is shared by the entire Hadamard class at each existing order, not an accident of the Sylvester algorithm.

For example, order twelve comes from the prime-field Paley construction in the main article. At four bits its transformed peak is $9/\sqrt{12}$ rather than $7$, yet its activation error is still $11/3332$ and its linear-output error is still $1/784$.

The supplied exact checker evaluates 1,280 cases using seven Paley orders and one Sylvester order, two row/column-equivalent variants, two support choices, five bit widths and all eight supported diagonal sign patterns. It includes the non-power-of-two orders 12, 20, 24 and 44. A deliberately corrupted matrix is rejected. These rational checks corroborate the proof; finite cases do not prove its universal quantifier.

```bash
python strengthening/all_hadamard_checks.py > new-all-hadamard-checks.json
python -m unittest discover -s strengthening -p 'test_all_hadamard.py' -v
```

The result assumes one scale over the entire activation vector and one over the entire weight column. It does not automatically extend to smaller quantization groups, learned quantizers, different codebooks or real-model quality. The 100-seed empirical study remains unchanged and separately qualified. No numerical outcome was selected or rerun to obtain this algebraic result.

The Hadamard definition and Paley construction are established mathematics, with sources in the main article. The count $N_{s,t}=n/4$ follows from row orthogonality as proved here. This note claims the displayed derivation and an inspectable teaching example, not a first-discovery result or an external review decision.

Text: CC BY 4.0. Original verification code: MIT.
