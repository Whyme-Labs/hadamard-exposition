---
title: "What the Hadamard conjecture promises"
subtitle: "Perfect balance, the orders we can reach, and why balance does not guarantee better rounding"
author: "Wei Meng Soh · Whyme Labs"
lang: en
---

Version 3, prepared 22 October 2026, Malaysia time. AI assistance was used in the writing, derivations and verification code. Version 3 adds an account of the conjecture's history, constructions, computational frontier and asymptotic results. It merges the all-Hadamard addendum into the main text and shortens the application. The numerical study is unchanged from version 2.

## A question about perfect balance

Imagine changing coordinates so that every original coordinate contributes equally in magnitude to every new coordinate. We also want the change to preserve lengths and angles. For real coordinates, these requirements force a remarkable object: a Hadamard matrix after normalization.

The Hadamard conjecture asks whether such perfect balance is possible in every dimension divisible by four. It does not ask whether orthogonal transformations exist. They exist in every dimension. It asks whether one can choose a particularly restrictive kind whose entries all have the same magnitude. The question has been open for more than ninety years. Every order below 668 is settled, but no method is known that covers all orders. It is listed as JSP-000013 by the Justin Sun Prize. [1]

This article has three parts. The first explains what a Hadamard matrix is, why its order must be one, two or a multiple of four, and what exactly it optimizes. The second covers the existing constructions, how far they reach, where the first unknown orders lie, and what is proved about the problem as a whole. The third describes an application in numerical rounding. It shows that the perfect balance the conjecture promises does not guarantee less rounding error. Readers interested only in the conjecture can stop after the second part.

# Part I. The object

## Why multiples of four appear

An order-$n$ Hadamard matrix is a real matrix $H$ with entries in $\{-1,+1\}$ satisfying

$$HH^{\mathsf T}=nI_n.$$

Each row has squared length $n$, and distinct rows have dot product zero. Consequently $Q=H/\sqrt n$ is orthogonal, so $H^{\mathsf T}H=nI_n$ as well and the columns are orthogonal too. The normalization matters: $H$ itself multiplies lengths by $\sqrt n$.

Two operations preserve the defining identity: permuting rows or columns, and multiplying a row or column by $-1$. Matrices related by these operations are called *equivalent*. Every Hadamard matrix is equivalent to a *normalized* one, whose first row and first column contain only $+1$.

Orders one and two have immediate examples, $(1)$ and $\left(\begin{smallmatrix}1&1\\1&-1\end{smallmatrix}\right)$. For $n>2$, orthogonality forces $n$ to be divisible by four. Here is the complete counting argument.

Flip whole columns until the first row consists entirely of $+1$. Column flips preserve row dot products. The second row must then contain equally many $+1$ and $-1$ entries, so $n$ is even. Reorder the columns so the second row has its positive entries in the first half.

Let the third row have $a$ positive entries in the first half and $b$ in the second. Orthogonality with the first row gives $a+b=n/2$. Orthogonality with the second gives $a=b$. Therefore $a=b=n/4$ must be an integer.

This is a necessary condition, not a construction. **The Hadamard conjecture asserts the converse: for every positive integer $k$, there is a Hadamard matrix of order $4k$.** Confusing these directions would turn a short counting proof into a false solution.

## An exact optimization meaning

For a real orthogonal matrix $Q$, define its largest entry magnitude

$$\mu(Q)=\max_{i,j}|Q_{ij}|.$$

Every row has squared length one. If all entries were smaller in magnitude than $1/\sqrt n$, the sum of their squares would be smaller than one. Thus

$$\mu(Q)\geq\frac1{\sqrt n}.$$

Equality forces every entry of every row to have magnitude exactly $1/\sqrt n$. Otherwise a row containing a smaller entry could not reach squared length one without another entry exceeding the bound. Hence $\sqrt n\,Q$ is a Hadamard matrix. Conversely, every normalized Hadamard matrix attains equality.

This is more than a statement about individual entries. Treat $x$ as a row vector. For $\|x\|_1\leq1$,

$$|(xQ)_j|\leq\sum_i|x_i|\,|Q_{ij}|\leq\mu(Q).$$

Choose $x$ to be a coordinate vector corresponding to an entry attaining the maximum, and equality is possible. Therefore

$$\sup_{\|x\|_1\leq1}\|xQ\|_\infty=\mu(Q).$$

The best possible value of this worst-case peak is $1/\sqrt n$, **and it is attainable exactly when an order-$n$ Hadamard matrix exists**. A minimum exists because the real orthogonal group is compact and the largest-entry function is continuous.

The Hadamard conjecture is thus an exact optimality question: does this lower bound become attainable in every dimension $n=4k$? The connection with flat real orthogonal matrices is established mathematics. Jaming and Matolcsi study this viewpoint and relaxations of perfect flatness. [2]

The input constraint is essential. Replace the $\ell_1$ unit ball by the $\ell_2$ unit sphere and every orthogonal matrix has the same worst-case peak:

$$\sup_{\|x\|_2=1}\|xQ\|_\infty=1.$$

The upper bound follows from length preservation. The vector $x=e_jQ^{\mathsf T}$ attains it. No fixed orthogonal transformation makes every unit vector less spiky.

## The same object maximizes a determinant

Hadamard's own interest was a determinant problem. [3] For any real $n\times n$ matrix $A$ with entries of magnitude at most one, let $G=AA^{\mathsf T}$. Its nonnegative eigenvalues have sum $\operatorname{tr}G\leq n^2$. Applying the arithmetic-geometric mean inequality gives

$$\det G\leq\left(\frac{n^2}{n}\right)^n=n^n,$$

and hence $|\det A|\leq n^{n/2}$. For a sign matrix, equality requires all eigenvalues of $G$ to equal $n$. Since $G$ is real symmetric, this is equivalent to $G=nI$.

So a Hadamard matrix simultaneously saturates a determinant bound and, after normalization, the smallest possible largest-entry bound. These are two precise meanings of perfect balance. When $n$ is not a multiple of four, the largest determinant of a sign matrix is a separate and harder *maximal determinant problem*. It is open in general. [4]

## Equivalent combinatorial forms

The conjecture has several equivalent forms, which is one reason it appears in so many fields. [4,5]

- **Designs.** Normalize an order-$4t$ Hadamard matrix and delete its first row and column. Record each remaining $+1$ as an incidence. The result is a symmetric $2$-$(4t-1,\,2t-1,\,t-1)$ design, and every such design arises in this way. The conjecture is equivalent to the existence of these *Hadamard designs* for every $t$.
- **Codes.** The rows of $H$ and $-H$, written over $\{0,1\}$, form a binary code of length $n$ with $2n$ codewords and minimum distance $n/2$. Plotkin's bound shows this is the largest possible such code, so Hadamard matrices give optimal codes.
- **Orthogonal arrays and experimental design.** Hadamard matrices give two-level orthogonal arrays of strength two. In statistics these are the Plackett-Burman designs for screening many factors with few runs.

These are reformulations, not routes around the difficulty. Each one is as hard as the original.

# Part II. What is known

## Building matrices: products and doubling

The simplest construction combines two smaller matrices. If $H_m$ and $H_n$ are Hadamard, their Kronecker product $H_m\otimes H_n$ is Hadamard of order $mn$, because

$$(H_m\otimes H_n)(H_m\otimes H_n)^{\mathsf T}=H_mH_m^{\mathsf T}\otimes H_nH_n^{\mathsf T}=mn\,I_{mn}.$$

Taking $H_2$ as one factor gives Sylvester's 1867 doubling: [6]

$$H_{2n}=\begin{pmatrix}H_n&H_n\\ H_n&-H_n\end{pmatrix}.$$

Starting at order one gives every power of two. It does not give order twelve. Infinite is not the same as exhaustive. Products alone also never produce an order whose odd part is a new prime, so new building blocks are needed.

## Paley's construction and order twelve

Paley's 1933 paper supplied the first large families of new orders, from finite fields. [7] The conjecture is usually traced to that paper. We prove the prime-field case of his first construction.

Take a prime $q\equiv3\pmod4$. Define the quadratic character $\chi$ on residues modulo $q$: it is zero at zero, $+1$ at nonzero squares, and $-1$ at non-squares. Let

$$C_{ij}=\chi(j-i),\qquad 0\leq i,j<q.$$

The nonzero squares form a subgroup of index two, so $\chi$ is multiplicative and exactly half the nonzero residues have each sign. Every row sum of $C$ is therefore zero. Also $-1$ is not a square: a solution of $t^2=-1$ would give $t^{q-1}=-1$ when $q\equiv3\pmod4$, contrary to Fermat's little theorem. Thus $\chi(-1)=-1$, giving $C^{\mathsf T}=-C$.

The needed correlation identity is

$$\sum_x\chi(x-a)\chi(x-b)=\begin{cases}q-1,&a=b,\\-1,&a\ne b.\end{cases}$$

For distinct $a,b$, set $u=(2x-a-b)/(b-a)$. Then $(x-a)(x-b)=((b-a)/2)^2(u^2-1)$. The nonzero square factor has character one, so this invertible change of variable reduces the sum to $\sum_u\chi(u^2-1)$. Count pairs satisfying $v^2=u^2-1$. For each $u$ there are $1+\chi(u^2-1)$ choices of $v$. On the other hand, $(u-v)(u+v)=1$. Each nonzero residue $t=u-v$ uniquely determines $u+v=t^{-1}$, then $u$ and $v$ because two is invertible. There are $q-1$ pairs. Thus $q+\sum_u\chi(u^2-1)=q-1$, proving the identity.

It follows that $CC^{\mathsf T}=qI-J$, where $J$ is the all-ones matrix. Now set

$$H=\begin{pmatrix}1&\mathbf1^{\mathsf T}\\ \mathbf1&C-I\end{pmatrix}.$$

Every entry is a sign. The first row is orthogonal to every later row because $C-I$ has row sum $-1$. The lower-right block of $HH^{\mathsf T}$ is

$$J+(C-I)(C-I)^{\mathsf T}=J+(qI-J)+I=(q+1)I.$$

Therefore $HH^{\mathsf T}=(q+1)I$. The same argument works over any finite field of order $q\equiv3\pmod 4$, so Paley's first construction gives order $q+1$ for every such prime power. His second construction gives order $2(q+1)$ for every prime power $q\equiv1\pmod4$. [4,7]

For $q=11$, the nonzero squares are $1,3,4,5,9$. The resulting order-twelve matrix is below. A plus or minus denotes an integer, not an approximation.

```text
+ + + + + + + + + + + +
+ - + - + + + - - - + -
+ - - + - + + + - - - +
+ + - - + - + + + - - -
+ - + - - + - + + + - -
+ - - + - - + - + + + -
+ - - - + - - + - + + +
+ + - - - + - - + - + +
+ + + - - - + - - + - +
+ + + + - - - + - - + -
+ - + + + - - - + - - +
+ + - + + + - - - + - -
```

The exact verifier checks all 144 row dot products and computes $|\det H|=12^6=2{,}985{,}984$ using fraction-free integer elimination. It also checks the construction at primes $3,7,11,19,23,31,43$, producing orders $4,8,12,20,24,32,44$.

## How far the classical methods reach

Combine Sylvester doubling, both Paley constructions over prime powers, and Kronecker products. The accompanying script `known_orders.py` computes exactly which orders these classical methods reach. Up to 200 they give 44 of the 50 multiples of four. The six missing orders are

$$92,\ 116,\ 156,\ 172,\ 184,\ 188.$$

Order 92 is the first. Paley's first construction would need $q=91=7\cdot13$, and his second would need $q=45=3^2\cdot5$. Neither is a prime power. The only factorizations of 92 into two orders greater than one use 2 and 46, or 4 and 23, and neither 46 nor 23 is a Hadamard order. Up to 1000 the classical methods reach 195 of the 250 multiples of four. A missed order is not an unknown order. Every order missed below 668 has since been reached by other methods.

## Williamson's method and the computer

Williamson's 1944 construction builds an order-$4m$ matrix from four smaller pieces. [8] Let $A,B,C,D$ be symmetric circulant $m\times m$ sign matrices that commute with each other and satisfy

$$A^2+B^2+C^2+D^2=4m\,I_m.$$

Then the block matrix

$$H=\begin{pmatrix}A&B&C&D\\-B&A&-D&C\\-C&D&A&-B\\-D&-C&B&A\end{pmatrix}$$

is Hadamard of order $4m$. The pattern of signs is the multiplication table of the quaternions, which is why the cross terms cancel. For $m=3$, take $A=J$ and $B=C=D=2I-J$. Then $A^2+3B^2=3J+3(4I-4J+3J)=12I$, giving another order-twelve matrix. The accompanying test checks this block identity directly.

The method turns a search over $(4m)^2$ signs into a search over four circulant first rows of length $m$, with symmetry cutting that further. In 1962 Baumert, Golomb and Hall used an early computer at the Jet Propulsion Laboratory to find Williamson matrices with $m=23$. This gave the first Hadamard matrix of order 92. [9] It is an early example of a computer settling a case of a classical existence question.

Williamson's method is not universal. Exhaustive searches show that Williamson matrices do not exist for $m=35$, nor for $m=47,53,59$. [10] Hadamard matrices of those orders exist by other means. Goethals and Seidel removed the symmetry requirement by inserting a reversal matrix into a modified array. [11] Turyn found infinite families of Williamson matrices. [12] Later work used complementary sequences, difference families and signed groups. Each method reaches many new orders, and none is known to reach them all.

## The computational frontier

Progress at individual orders now comes from large structured searches. Kharaghani and Tayfeh-Rezaie constructed order 428 in 2005. [13] Đoković constructed order 764 in 2008, using a Goethals-Seidel array. [14] As of a 2024 database of constructions, the only multiples of four up to 1208 with no known Hadamard matrix are [15]

$$668,\ 716,\ 892,\ 1132.$$

The smallest open case, $668=4\cdot167$, has resisted every method so far. Paley's constructions would need $q=667=23\cdot29$ or $q=333=3^2\cdot37$, and neither is a prime power. Since 167 is prime, no Kronecker product with a smaller factor gives order 668 either. Searches with the array methods have not found the required sequences. This is evidence of difficulty, not of nonexistence. No order divisible by four has ever been shown to have no Hadamard matrix.

The number of matrices grows quickly once they exist. Up to equivalence there is one Hadamard matrix of each order 1, 2, 4, 8 and 12. Order 16 has five, order 20 has three, order 24 has 60 and order 28 has 487. [16] Order 32 has exactly 13,710,027, a classification completed by Kharaghani and Tayfeh-Rezaie. [17] Abundance at the orders we can search does not translate into a general existence proof.

## What is proved about all orders

The strongest general results show that every odd number appears in some Hadamard order, provided we allow a large enough power of two. In 1976 Seberry proved that for every odd $q$ there is a Hadamard matrix of order $2^tq$ for all $t$ larger than about $2\log_2q$. [18] Craigen's signed-group method lowered the coefficient of $\log_2 q$ to about $2/3$. [19] Later refinements lowered it to about $1/5$. [20] The conjecture asks for $t=2$ for every odd $q$, and these bounds still grow with $q$.

Density results measure the same gap from another direction. If the conjecture holds, the number of Hadamard orders up to $x$ is about $x/4$. Paley's constructions alone give about $x/\log x$ orders. De Launey and Gordon proved a slightly larger lower bound for all known constructions together, and noted that it is still not known whether known Hadamard orders have positive density. [21] De Launey also proved an asymptotic existence result of this kind that holds for all odd $q$ outside an exceptional set of small density. [22]

Two related problems are also open and are sometimes confused with this one. The *skew-Hadamard conjecture* asks for a Hadamard matrix with $H+H^{\mathsf T}=2I$ in every order divisible by four. Ryser's *circulant Hadamard conjecture* asserts the opposite kind of statement: no circulant Hadamard matrix exists beyond order four. Excluding circulant matrices does not construct general Hadamard matrices. [1,4]

## Why the problem is hard

Three features explain why no single idea has closed the gap.

1. **Constructions need structure.** Every infinite family comes from algebra: finite fields, group rings, or sequences with special autocorrelation. Each structure exists only at orders with matching arithmetic, such as $q+1$ for a prime power $q$. The open orders are exactly those where no known structure fits.
2. **Unstructured search is hopeless at these sizes.** An order-668 sign matrix has $668^2=446{,}224$ entries. Williamson-type arrays reduce this to a few sequences of length 167. Even that space is too large to search exhaustively without further constraints that might exclude every solution.
3. **Random constructions are too rare to count.** For a random sign matrix, two given rows are orthogonal with probability of order $1/\sqrt n$. Requiring all $\binom n2$ pairs to be orthogonal makes Hadamard matrices extremely rare among sign matrices. Probabilistic methods can show that matrices with a small number of mutually orthogonal rows exist in large numbers. [23] They are nowhere near the full square case.

The conjecture is therefore not about whether balance is plausible. It asks whether a rigid algebraic coincidence, which we can produce in many families, occurs in every admissible order.

# Part III. An application: balance is not rounding

## The rotation trick

Large numerical models are often stored with low-precision weights and activations. A single large coordinate forces a coarse quantization grid on everything that shares its scale. A common remedy rotates the coordinates first. For a linear layer $Y=XW$ and any orthogonal $Q$,

$$X_r=XQ,\qquad W_r=Q^{\mathsf T}W,\qquad X_rW_r=XW.$$

A normalized Hadamard matrix is the natural choice. By Part I it minimizes the worst-case peak over the $\ell_1$ ball, and a Sylvester matrix also has a fast transform. Methods such as QuaRot and QuIP# build randomized Hadamard rotations into language-model quantization. SpinQuant shows that the choice of rotation matters. [24,25,26] This article does not propose or evaluate such a method.

The question here is narrower. Suppose the conjecture were true, so perfectly balanced rotations existed in every admissible dimension. Would they guarantee lower rounding error? They would not. This holds even with the optimal peak, and even for every Hadamard matrix at once.

## A fixed input that every Hadamard matrix hurts

Use a symmetric max-absolute-value quantizer. At bit width $b$, let $K=2^{b-1}-1$. For a nonzero vector $z$, its scale is $\Delta=\|z\|_\infty/K$, and its reconstructed coordinates are $\widehat z_i=\Delta\,\operatorname{round}(z_i/\Delta)$, with nearest rounding, ties to even, and signed codes $-K,\ldots,K$. A smaller peak gives a finer grid, but the distance from the data to the grid also matters.

**Theorem.** Fix an order $n\geq4$ for which a real Hadamard matrix exists, a bit width $b\geq3$, and three distinct indices $a,c,d$. Let

$$x=K e_a+e_c+e_d,\qquad w=e_a.$$

For **every** order-$n$ Hadamard matrix $H$, put $Q=H/\sqrt n$ and quantize each vector with one full-width scale. Then $x$ and $w$ are represented exactly, and the rotated peak $(K+2)/\sqrt n$ is smaller than $K$. But the rotated activation and the rotated linear output both have positive error. Their relative squared values depend on neither $n$ nor $H$:

| Bit width | Activation reconstruction error | Linear-output error |
|---|---:|---:|
| $b=3$ | $1/66$ | $1/81$ |
| $b=4$ | $11/3332$ | $1/784$ |
| $b\geq5$ | $24/[K^2(K^2+2)]$ | $16/K^4$ |

**Proof.** The original scale is one, so $x$ and $w$ are exact. Define sign sequences $p_j=H_{aj}H_{cj}$ and $q_j=H_{aj}H_{dj}$. Orthogonality of rows $a$, $c$ and $d$ gives

$$\sum_jp_j=0,\qquad \sum_jq_j=0,\qquad \sum_jp_jq_j=\sum_jH_{cj}H_{dj}=0.$$

For $s,t\in\{-1,+1\}$, the number of columns with $p_j=s$ and $q_j=t$ is therefore

$$N_{s,t}=\frac14\sum_j(1+s p_j)(1+t q_j)=\frac n4.$$

This is the same three-row count that forced $n$ to be a multiple of four. Write $u=xH$ and $v_j=H_{aj}u_j=K+p_j+q_j$. Thus $v_j$ takes the values $K+2,K,K-2$ with multiplicities $n/4,n/2,n/4$, and the rotated peak is $(K+2)/\sqrt n<K$.

Work before dividing by $\sqrt n$, with scale $s=(K+2)/K$. Symmetric rounding is odd, so the sign $H_{aj}$ passes through it. For $b\geq5$, so $K\geq15$, the codes for $K+2,K,K-2$ are $K,K-2,K-4$, because

$$\frac{K^2}{K+2}=K-2+\frac4{K+2},\qquad
\frac{K(K-2)}{K+2}=K-4+\frac8{K+2},$$

and both fractions are below one half. The reconstruction errors are $0,-4/K,-8/K$. Their squared values, averaged with the multiplicities above, give $24/K^2$. Dividing by $\|x\|_2^2=K^2+2$ gives the activation formula.

The rotated weight $Q^{\mathsf T}w$ has every coordinate equal to $\pm1/\sqrt n$, so its quantizer is exact. The quantized output is the average of the rounded $v_j$, which is $K-4/K$, whereas the exact output is $K$. The relative squared error is $16/K^4$. At three bits, scale $5/3$ rounds $5,3,1$ to $5,10/3,5/3$. At four bits, scale $9/7$ rounds $9,7,5$ to $9,45/7,36/7$. Direct substitution gives the remaining table entries. $\square$

As the dimension grows, the peak ratio $(K+2)/(K\sqrt n)$ tends to zero while the error stays fixed. Choosing a different Hadamard matrix, or randomizing its signs and permutations, cannot remove the error for this input, because those operations produce another Hadamard matrix. This does not contradict probabilistic guarantees for random inputs. It shows that perfect balance alone does not guarantee a better result. The theorem assumes one scale per vector. It says nothing about smaller groups, learned quantizers or real models. No first-discovery claim is made for this derivation.

The accompanying checker evaluates 1,280 rational cases across seven Paley orders and one Sylvester order, including the non-power-of-two orders 12, 20, 24 and 44. A further 672 cases cover Sylvester matrices with every supported sign pattern. Finite cases corroborate the proof; they do not replace it.

## A fresh-seed study with competing transforms

A constructed example shows what can happen; it does not show what usually happens. A separate study compares four transforms on synthetic data. Its protocol fixed seeds 1000 through 1099, every setting and one primary comparison before any of those samples were generated. [27]

Each seed creates a $512\times128$ Gaussian activation matrix and a $128\times64$ Gaussian weight matrix. Activation column zero is multiplied by $1,2,4,8,16$ or $32$ to create an outlier. Four arms are compared: the original basis, a randomized Hadamard rotation, a Haar-random orthogonal matrix, and a signed permutation that reorders without mixing. Both operands receive the same four-bit quantizer, grouped over 32 input features in the primary setting. Error is the relative squared Frobenius error of the output, simulated in float64.

At the primary setting, with multiplier 32, mean error fell from **2.606175% to 1.355898%** under Hadamard, a **47.97% reduction**. All 100 paired seeds favored Hadamard, and the 95% whole-seed bootstrap interval for the change was $[-1.307,\,-1.194]$ percentage points.

The secondary comparisons limit what this shows. The table gives mean percentage errors at group size 32 for selected multipliers.

| Activation-column multiplier | Original | Hadamard | Haar orthogonal | Signed permutation |
|---:|---:|---:|---:|---:|
| 1 | 1.891841 | 1.899478 | 1.895267 | 1.892540 |
| 4 | 2.237005 | 1.878227 | 1.892689 | 2.229054 |
| 16 | 3.725695 | 1.572253 | 1.887476 | 3.705417 |
| 32 | 2.606175 | 1.355898 | 1.893716 | 2.577981 |

- **Generic rotations also help.** A Haar-random orthogonal matrix also removes most of the outlier penalty, so the benefit is not exclusive to Hadamard.
- **No outlier, no benefit.** With no outlier, Hadamard was marginally worse. For isotropic Gaussian inputs every orthogonal rotation leaves the error distribution unchanged, so this small difference is sampling noise, not a systematic effect.
- **Grid-aligned data is hurt.** When the data already sit on the quantization grid, the original basis has zero error. Hadamard averaged 2.742108% error and lost on all 100 seeds. This is the mechanism of the theorem above, seen in random data.

The study retains all 7,600 measurements, input and transform hashes, and an independent audit that recomputes every reported summary from the raw data. It measures no model quality, memory or speed.

## What the evidence supports

The Hadamard conjecture asks whether a perfectly balanced orthogonal matrix exists in every dimension divisible by four. Part I showed that this balance is exactly the minimum possible largest entry and the maximum possible determinant. Part II showed how far algebraic and computer-assisted constructions have reached: every order below 668, and every odd factor once enough powers of two are allowed. The general case remains open. Part III showed that the promised balance does not guarantee less rounding error. Every Hadamard matrix fails on the same fixed input, while a synthetic study shows the benefit in the case the method targets.

The constructions, equivalences and frontier results in Parts I and II are established mathematics, credited to their sources. Proofs are given where they are short enough to include. The counterexample theorem and the study are offered as teaching material, not as new quantization methods. Nothing here proves the conjecture at any new order.

## Reproduce and inspect

The checks need Python and NumPy, with no GPU, model download or external dataset.

```bash
python exposition-v3/known_orders.py --limit 200
python -m unittest discover -s exposition-v3 -p 'test_*.py' -v
cd submission/v2
python -m unittest discover -s strengthening -p 'test_*.py' -v
python strengthening/audit_study.py run-v2
python strengthening/all_hadamard_checks.py > new-all-hadamard-checks.json
```

The first two commands check the classical-order counts and the Williamson example in Part II. The remaining commands check the Paley construction, the counterexample theorem and the retained study data, which are unchanged from version 2. A fresh study run uses `python strengthening/study.py --output new-run` from the same directory.

## Sources

[1] The Justin Sun Prize, [JSP-000013 catalog entry](https://github.com/TheJustinSunPrize/awards/blob/main/problems/catalog-0001-0100.md#jsp-000013--hadamard-matrix-conjecture). Problem identity and general statement.

[2] Philippe Jaming and Máté Matolcsi, [On the existence of flat orthogonal matrices](https://arxiv.org/abs/1505.03668), 2015.

[3] Jacques Hadamard, Résolution d'une question relative aux déterminants, *Bulletin des Sciences Mathématiques* 17 (1893), 240–246.

[4] Robert Craigen and Hadi Kharaghani, Hadamard matrices and Hadamard designs, in C. J. Colbourn and J. H. Dinitz (eds.), *Handbook of Combinatorial Designs*, 2nd ed., Chapman & Hall/CRC, 2007. Also SageMath, [Hadamard matrices reference](https://doc.sagemath.org/html/en/reference/combinat/sage/combinat/matrices/hadamard_matrix.html).

[5] Kathy J. Horadam, *Hadamard Matrices and Their Applications*, Princeton University Press, 2007.

[6] J. J. Sylvester, Thoughts on inverse orthogonal matrices, *Philosophical Magazine* 34 (1867), 461–475.

[7] R. E. A. C. Paley, On orthogonal matrices, *Journal of Mathematics and Physics* 12 (1933), 311–320.

[8] John Williamson, Hadamard's determinant theorem and the sum of four squares, *Duke Mathematical Journal* 11 (1944), 65–81.

[9] L. Baumert, S. W. Golomb and M. Hall Jr., [Discovery of an Hadamard matrix of order 92](https://www.ams.org/journals/bull/1962-68-03/S0002-9904-1962-10761-7), *Bulletin of the AMS* 68 (1962), 237–238.

[10] D. Ž. Đoković, Williamson matrices of order $4n$ for $n=33,35,39$, *Discrete Mathematics* 115 (1993), 267–271; W. H. Holzmann, H. Kharaghani and B. Tayfeh-Rezaie, Williamson matrices up to order 59, *Designs, Codes and Cryptography* 46 (2008), 343–352.

[11] J. M. Goethals and J. J. Seidel, A skew Hadamard matrix of order 36, *Journal of the Australian Mathematical Society* 11 (1970), 343–344.

[12] R. J. Turyn, An infinite class of Williamson matrices, *Journal of Combinatorial Theory, Series A* 12 (1972), 319–321.

[13] H. Kharaghani and B. Tayfeh-Rezaie, A Hadamard matrix of order 428, *Journal of Combinatorial Designs* 13 (2005), 435–440.

[14] D. Ž. Đoković, [Hadamard matrices of order 764 exist](https://arxiv.org/abs/math/0703312), *Combinatorica* 28 (2008), 487–489.

[15] Matteo Cati and Dmitrii V. Pasechnik, [A database of constructions of Hadamard matrices](https://arxiv.org/abs/2411.18897), 2024.

[16] Brendan McKay, [Hadamard matrices data](https://users.cecs.anu.edu.au/~bdm/data/hadamard.html). Equivalence-class counts for small orders.

[17] H. Kharaghani and B. Tayfeh-Rezaie, On the classification of Hadamard matrices of order 32, *Journal of Combinatorial Designs* 18 (2010), 328–336.

[18] Jennifer Seberry Wallis, On the existence of Hadamard matrices, *Journal of Combinatorial Theory, Series A* 21 (1976), 188–195.

[19] Robert Craigen, Signed groups, sequences, and the asymptotic existence of Hadamard matrices, *Journal of Combinatorial Theory, Series A* 71 (1995), 241–254.

[20] Ivan Livinskyi, [Asymptotic existence of Hadamard matrices](https://mspace.lib.umanitoba.ca/handle/1993/8915), M.Sc. thesis, University of Manitoba, 2012.

[21] Warwick de Launey and Daniel M. Gordon, [On the density of the set of known Hadamard orders](https://arxiv.org/abs/1004.4872), *Cryptography and Communications* 2 (2010), 233–246.

[22] Warwick de Launey, [On the asymptotic existence of Hadamard matrices](https://arxiv.org/abs/1003.4001), 2010.

[23] Warwick de Launey and David A. Levin, A Fourier-analytic approach to counting partial Hadamard matrices, *Cryptography and Communications* 2 (2010), 307–334.

[24] Saleh Ashkboos and coauthors, [QuaRot: Outlier-Free 4-Bit Inference in Rotated LLMs](https://arxiv.org/abs/2404.00456), 2024.

[25] Albert Tseng and coauthors, [QuIP#: Even Better LLM Quantization with Hadamard Incoherence and Lattice Codebooks](https://proceedings.mlr.press/v235/tseng24a.html), 2024.

[26] Zechun Liu and coauthors, [SpinQuant: LLM quantization with learned rotations](https://arxiv.org/abs/2405.16406), 2024.

[27] `submission/v2/strengthening/protocol-v2.json`, SHA-256 `1a239984661f3c229225aa4d899fe3960eb2f5f47dc5e7099c49764022f08c29`. The study code, raw measurements and audit are in `submission/v2`.

The article is licensed under CC BY 4.0. The accompanying original code is licensed under MIT. Citations do not relicense third-party work.
