---
title: "What the Hadamard conjecture promises"
subtitle: "The best possible spreading, and why it does not guarantee better rounding"
author: "Wei Meng Soh · Whyme Labs"
lang: en
---

Prepared 21 October 2026, Malaysia time. Version 2 research exposition. AI assistance was used in the writing, derivations and code. No committee selection or award is claimed.

## A question about perfect balance

Imagine changing coordinates so that every original coordinate contributes equally in magnitude to every new coordinate. We also want the change to preserve lengths and angles. For real coordinates, these requirements force a remarkable object: a Hadamard matrix after normalization.

The Hadamard conjecture asks whether such perfect balance is possible in every dimension divisible by four. It does not ask whether orthogonal transformations exist. They exist in every dimension. It asks whether one can choose a particularly restrictive kind whose entries all have the same magnitude. The general assertion remains the open problem listed as JSP-000013 by the Justin Sun Prize. [1]

This distinction connects the conjecture to numerical approximation without pretending that a quantization experiment solves it. A perfectly balanced change of coordinates is optimal for one precise worst-case objective. It need not minimize rounding error. We will prove both statements, construct a twelve-dimensional example, and test what happens when a quantizer receives better and worse inputs.

There are two reading routes. The first five sections explain the mathematics. The remaining sections connect it to quantization, prove a family of counterexamples and report a fresh-seed computational study. Every construction and numerical record needed for the latter is included in the accompanying package.

## Why multiples of four appear

An order-$n$ Hadamard matrix is a real matrix $H$ with entries in $\{-1,+1\}$ satisfying

$$HH^{\mathsf T}=nI_n.$$

Each row has squared length $n$, and distinct rows have dot product zero. Consequently $Q=H/\sqrt n$ is orthogonal. The normalization matters: $H$ itself multiplies lengths by $\sqrt n$.

Orders one and two have immediate examples. For $n>2$, orthogonality forces $n$ to be divisible by four. Here is the complete counting argument.

Flip whole columns until the first row consists entirely of $+1$. Column flips preserve row dot products. The second row must then contain equally many $+1$ and $-1$ entries, so $n$ is even. Reorder the columns so the second row has its positive entries in the first half.

Let the third row have $a$ positive entries in the first half and $b$ in the second. Orthogonality with the first row gives $a+b=n/2$. Orthogonality with the second gives $a=b$. Therefore $a=b=n/4$ must be an integer.

This is a necessary condition, not a construction. The conjecture asserts the missing converse for every positive multiple of four. Confusing these directions would turn a short counting proof into a false solution.

Sylvester doubling constructs an infinite family:

$$H_{2n}=\begin{pmatrix}H_n&H_n\\ H_n&-H_n\end{pmatrix}.$$

Multiplying this block matrix by its transpose proves its Hadamard identity whenever $H_n$ has one. Starting at order one gives every power of two. It does not give order twelve from that starting point. Infinite is not the same as exhaustive. These definitions, determinant equivalences and standard constructions are also documented in SageMath. [2]

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

The Hadamard conjecture is thus an exact optimality question: does this lower bound become attainable in every dimension $n=4k$? The connection with flat real orthogonal matrices is established mathematics, not a new conjecture or a priority claim in this article. Jaming and Matolcsi study this viewpoint and relaxations of perfect flatness. [3]

The input constraint is essential. Replace the $\ell_1$ unit ball by the $\ell_2$ unit sphere and every orthogonal matrix has the same worst-case peak:

$$\sup_{\|x\|_2=1}\|xQ\|_\infty=1.$$

The upper bound follows from length preservation. The vector $x=e_jQ^{\mathsf T}$ attains it. No fixed orthogonal transformation makes every unit vector less spiky. A useful guarantee must specify the input class or its randomness.

## The same object maximizes a determinant

For any real sign matrix $A$, let $G=AA^{\mathsf T}$. Its nonnegative eigenvalues have sum $\operatorname{tr}G=n^2$. Applying the arithmetic-geometric mean inequality gives

$$\det G\leq\left(\frac{n^2}{n}\right)^n=n^n,$$

and hence $|\det A|\leq n^{n/2}$. Equality requires all eigenvalues of $G$ to equal $n$. Since $G$ is real symmetric, this is equivalent to $G=nI$.

So a Hadamard matrix simultaneously saturates a determinant bound and, after normalization, the smallest possible largest-entry bound. These are two precise meanings of perfect balance. Neither equality supplies a universal existence proof. [2]

## Building order twelve without doubling from one

Paley's construction gives the missing kind of example. We use its prime-field case, not its full prime-power generalization. Take a prime $q\equiv3\pmod4$. Define the quadratic character $\chi$ on residues modulo $q$: it is zero at zero, $+1$ at nonzero squares, and $-1$ at non-squares. Let

$$C_{ij}=\chi(j-i),\qquad 0\leq i,j<q.$$

The nonzero squares form a subgroup of index two, so $\chi$ is multiplicative and exactly half the nonzero residues have each sign. Every row sum of $C$ is therefore zero. Also $-1$ is not a square: a solution of $t^2=-1$ would give $t^{q-1}=-1$ when $q\equiv3\pmod4$, contrary to Fermat's little theorem. Thus $\chi(-1)=-1$, giving $C^{\mathsf T}=-C$.

The needed correlation identity is

$$\sum_x\chi(x-a)\chi(x-b)=\begin{cases}q-1,&a=b,\\-1,&a\ne b.\end{cases}$$

For distinct $a,b$, set $u=(2x-a-b)/(b-a)$. Then $(x-a)(x-b)=((b-a)/2)^2(u^2-1)$. The nonzero square factor has character one, so this invertible change of variable reduces the sum to $\sum_u\chi(u^2-1)$. Count pairs satisfying $v^2=u^2-1$. For each $u$ there are $1+\chi(u^2-1)$ choices of $v$. On the other hand, $(u-v)(u+v)=1$. Each nonzero residue $t=u-v$ uniquely determines $u+v=t^{-1}$, then $u$ and $v$ because two is invertible. There are $q-1$ pairs. Thus $q+\sum_u\chi(u^2-1)=q-1$, proving the identity.

It follows that $CC^{\mathsf T}=qI-J$, where $J$ is the all-ones matrix. Now set

$$H=\begin{pmatrix}1&\mathbf1^{\mathsf T}\\ \mathbf1&C-I\end{pmatrix}.$$

Every entry is a sign. The first row is orthogonal to every later row because $C-I$ has row sum $-1$. The lower-right block of $HH^{\mathsf T}$ is

$$J+(C-I)(C-I)^{\mathsf T}=J+(qI-J)+I=(q+1)I.$$

Therefore $HH^{\mathsf T}=(q+1)I$. This proves the prime-field construction used here. SageMath implements the broader Paley construction as well. [2]

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

The exact verifier checks all 144 row dot products and computes $|\det H|=12^6=2{,}985{,}984$ using fraction-free integer elimination. It also checks the construction at primes $3,7,11,19,23,31,43$, producing orders $4,8,12,20,24,32,44$. It rejects invalid parameters and a matrix with one deliberately corrupted entry. These finite checks support the implementation; the block calculation above proves the stated construction.

Paley gives more orders than doubling from one. It still does not establish the conjecture for every multiple of four. Nor would mere existence promise a fast transform. The familiar Walsh-Hadamard butterfly uses the special recursive structure of the power-of-two construction. Flatness and orthogonality alone do not specify such an algorithm.

## What changes when we round

For a linear layer $Y=XW$, compensate an orthogonal change of coordinates on both sides:

$$X_r=XQ,\qquad W_r=Q^{\mathsf T}W,\qquad X_rW_r=XW.$$

Now use a symmetric max-absolute-value quantizer. At bit width $b$, let $K=2^{b-1}-1$. For a nonzero group $z$, its scale is $\Delta=\|z\|_\infty/K$, and its reconstructed coordinates are

$$\widehat z_i=\Delta\,\operatorname{round}(z_i/\Delta).$$

We use nearest rounding with ties to even and signed codes $-K,\ldots,K$. An all-zero group reconstructs as zero. Smaller coordinate peaks can reduce the scale, but the distance to the quantizer's grid matters too. A bound on scale is not the realized rounding error.

Prior methods already use orthogonal and randomized Hadamard transformations in language-model quantization. QuaRot and QuIP# are important examples. They include architecture, packing or codebook choices that this synthetic experiment does not reproduce. SpinQuant also shows that the choice of rotation can matter. This exposition does not propose a replacement algorithm or claim those methods' performance. [4,5,6]

## An infinite family where every supported sign choice still hurts

The following algebraic extension was derived for this revision after the fresh-seed experiment. It is separate from that experiment's prespecified endpoints. No first-discovery claim is made.

**Claim.** Let $n=2^r\geq4$, $b\geq3$, $K=2^{b-1}-1$, and

$$x=(K,1,1,0,\ldots,0).$$

Use the standard binary-indexed Sylvester matrix and any diagonal sign matrix $D$. For $Q=DH_n/\sqrt n$, full-width maxabs quantization represents $x$ exactly before transformation. After transformation, its peak is strictly smaller, but its relative squared reconstruction error is strictly positive. That error is independent of $n$ and of $D$.

**Proof.** The original scale is one, so all coordinates of $x$ are represented exactly. Only the first three signs of $D$ matter. In the first three Sylvester rows, the first row is constant and the other two independent sign patterns take their four possible pairs equally often. Up to an overall sign, the unnormalized transformed coordinates therefore have magnitudes

$$K+2,\quad K,\quad K-2$$

with multiplicities $n/4,n/2,n/4$. Changing the three supported signs permutes these values or flips their overall sign. Symmetric rounding preserves their squared errors.

The transformed peak is $(K+2)/\sqrt n<K$ because $K\geq3$ and $n\geq4$. Work with the unnormalized coordinates to avoid irrational arithmetic. Their scale is $(K+2)/K$; divide the final squared error by $n$ to account for normalization.

For $b\geq5$, so $K\geq15$, the three quantizer codes are respectively $K$, $K-2$, and $K-4$. Indeed,

$$\frac{K^2}{K+2}=K-2+\frac4{K+2},\qquad
\frac{K(K-2)}{K+2}=K-4+\frac8{K+2},$$

and both residual fractions lie below one half. The unnormalized reconstruction errors are zero, $-4/K$, and $-8/K$. Their normalized squared sum is

$$\frac1n\left[\frac n2\frac{16}{K^2}+\frac n4\frac{64}{K^2}\right]=\frac{24}{K^2}.$$

Dividing by $\|x\|_2^2=K^2+2$ gives

$$\boxed{\frac{\|\widehat{xQ}-xQ\|_2^2}{\|x\|_2^2}=\frac{24}{K^2(K^2+2)}>0,\quad b\geq5.}$$

The two remaining widths follow by direct rational rounding: $1/66$ at three bits and $11/3332$ at four bits. The same multiplicity argument makes them independent of dimension and signs. This completes the proof.

At fixed bit width, the peak ratio $(K+2)/(K\sqrt n)$ tends to zero as dimension increases, while this positive relative error stays constant. Randomizing the signs cannot rescue this particular fixed input. This does not contradict probabilistic peak bounds: it demonstrates that a small peak is not enough to guarantee lower realized rounding error.

The exact code checks 14 bit widths, six dimensions and all eight supported sign patterns, for 672 finite witnesses. It evaluates the quantizer directly with rational arithmetic rather than checking only the closed-form expression. Finite witnesses corroborate the proof; they do not replace it.

### A linear-layer version, with both operands quantized

The same construction can change a layer's output, not only its activation coordinates. Take a single output weight column $w=e_0$, so the original scalar output is $xw=K$. Both original operands are represented exactly by their respective full-width maxabs quantizers.

Since the first Sylvester row is constant, $Q^{\mathsf T}w$ has every entry equal to $D_{00}/\sqrt n$. Its maxabs quantizer represents these weights exactly too. The reconstructed output is therefore $D_{00}\sum_j\widehat u_j/n$, where $\widehat u$ is the unnormalized rounded activation from the proof.

For $b\geq5$, the three errors and their multiplicities give output $K-4/K$. The relative squared output error is exactly

$$\frac{(K-4/K-K)^2}{K^2}=\frac{16}{K^4}>0.$$

Direct rational rounding gives $1/81$ at three bits and $1/784$ at four bits. Every supported sign pattern and every power-of-two dimension at least four gives the same respective result. Thus the failure can survive quantization of both operands in an actual linear product; it is not only a reconstruction-metric example. This remains a constructed counterexample, not an estimate of real-model behavior.

## A fresh-seed test with competing transforms

A favorable example should not be the only numerical evidence. Before generating the new samples, we committed a protocol with seeds 1000 through 1099, disjoint from the previously inspected seeds 0 through 19. It fixed every setting below and one primary comparison. [7]

Each seed creates a $512\times128$ Gaussian activation matrix and a $128\times64$ Gaussian weight matrix, with weights divided by $\sqrt{128}$. We multiply activation column zero by $1,2,4,8,16$ or $32$. We compare the original basis, randomized Hadamard, a Haar-distributed real orthogonal matrix generated by sign-corrected Gaussian QR, and a signed permutation. The latter controls for reordering without mixing. The QR construction follows the standard Haar-generation procedure. [8]

Both operands receive the same four-bit quantizer, grouped over 128, 32 or 16 contiguous input features. Comparisons within a group size use equal scale counts. Smaller groups use more scales: 576, 2,304 and 4,608 per arm respectively. This is not a same-memory comparison across group sizes.

All computations simulate quantization in float64. We measure relative squared Frobenius output error against the same unquantized product within each comparison. We measure no packed memory use, inference latency or language-model accuracy.

### Primary result

The prespecified primary setting is multiplier 32, group size 32, Hadamard minus original error. On the 100 fresh seeds, mean errors were **2.606175% and 1.355898%**, a **47.9737% reduction in mean relative squared output error**. All 100 paired seeds favored Hadamard.

The paired mean change was **-1.250277 percentage points**. Its 95% whole-seed percentile bootstrap interval was **[-1.307422, -1.194203] points**, using 10,000 resamples fixed in the protocol. This satisfies the prespecified directional criterion within this synthetic family. It does not establish performance on real activations.

### The comparisons that limit the claim

At group size 32, every multiplier gives the following mean percentage errors. These secondary comparisons are descriptive. Their intervals are unadjusted for multiple comparisons.

| Activation-column multiplier | Original | Hadamard | Haar orthogonal | Signed permutation |
|---:|---:|---:|---:|---:|
| 1 | 1.891841 | 1.899478 | 1.895267 | 1.892540 |
| 2 | 1.929323 | 1.896343 | 1.896201 | 1.930822 |
| 4 | 2.237005 | 1.878227 | 1.892689 | 2.229054 |
| 8 | 3.159413 | 1.788790 | 1.887406 | 3.149352 |
| 16 | 3.725695 | 1.572253 | 1.887476 | 3.705417 |
| 32 | 2.606175 | 1.355898 | 1.893716 | 2.577981 |

The generic orthogonal transform also helps on strong outliers. Therefore outlier reduction is not exclusive to Hadamard. Hadamard performed better than this Haar arm in the primary synthetic setting, but this experiment is not a universal ranking of transforms.

On the Gaussian control, Hadamard was slightly worse: 1.899478% versus 1.891841%. The unadjusted paired interval for that small difference was above zero. We retain it rather than extending the earlier 20-seed observation that every Gaussian interval included zero.

There is an exact population check behind this control. For independent isotropic Gaussian $X$ and $W$, and any independent orthogonal $Q$, the pair $(XQ,Q^{\mathsf T}W)$ has the same joint distribution as $(X,W)$. Orthogonal maps preserve the Gaussian densities because those densities depend only on squared lengths. Consequently the population distribution of this error statistic is unchanged. A small sampled difference, even with an unadjusted secondary interval above zero, is not evidence of a systematic Gaussian advantage or disadvantage. The fresh study tests a finite sample, not the population identity.

The baseline error is not monotone in the multiplier. Relative error divides by the energy of the reference output, which changes across multipliers; maxabs quantization also changes its grid. Cross-multiplier values should not be read as the same prediction task getting uniformly harder.

A separate grid-aligned negative control remains decisive. Original and signed-permutation errors were zero. Hadamard produced 2.742108% mean error and Haar 2.707647%. Hadamard lost on all 100 seeds. An explanation that omits this case would misrepresent the mechanism.

The run retained all **7,600 arm-level measurements** across 19 settings, input and transform hashes, a protocol hash, source hashes and runtime details. Exact Paley checks passed. An independent script reconstructed coverage, means, win counts and paired intervals from the CSV, performing 228 summary checks without importing the experiment implementation.

## What the evidence supports

We now have a precise connection between the conjecture and optimal coordinate spreading, an explicit construction outside powers of two, a proved counterexample family and a broader synthetic experiment with competing transforms and unfavorable controls.

These are contributions to an exposition. The flat-matrix equivalence and Paley construction are known mathematics. The closed-form counterexample is presented with its proof and without a claim of literature priority. The numerical study confirms a conditional mechanism under its specified generator. It supplies no model-quality result and no proof that Hadamard matrices exist in every admissible order.

The remaining uncertainty about an award is external. The Justin Sun Prize rules allow Exposition to explain an open problem, but require content review and committee selection. Passing our numerical checks is not that selection. [9]

The best reason to submit this work is not that it produces a large improvement percentage. It is that a reader can see what the conjecture promises, what a construction proves, what an experiment measures, and why none of those statements should be substituted for another.

## Reproduce and inspect

The accompanying archive is self-contained for these tests. It does not need the private research repository, a GPU, a model download or an external dataset. It uses Python 3.13.5 and NumPy 2.3.5 in the recorded local run. Other environments must disclose their versions.

```bash
python -m pip install -r requirements-v2.txt
python -m unittest discover -s strengthening -p 'test_*.py' -v
python strengthening/study.py --output new-run
python strengthening/verify_study.py new-run
python strengthening/counterexample_family.py > new-family-checks.json
```

Use a new output directory for each run. The study refuses to overwrite existing evidence. Its internal deadline is 180 seconds and it requests one BLAS thread. For a hard process deadline on Linux, prefix the study command with `timeout 180s`. The retained raw results are in `run-v2/cells.csv`; the complete setting summaries, input hashes and execution receipt are beside them. Exact finite reconstruction checks are in `family-checks.json`. The later linear-layer corollary and its finite witnesses are retained separately in `family-linear-checks.json`.

The prior exposition remains unchanged. This revision has its own source identities and validation record; it does not inherit an external review or public publication date from the earlier private draft.

## Sources and contribution notes

[1] The Justin Sun Prize, [JSP-000013 catalog entry](https://github.com/TheJustinSunPrize/awards/blob/main/problems/catalog-0001-0100.md#jsp-000013--hadamard-matrix-conjecture). Problem identity and general statement.

[2] SageMath, [Hadamard matrices reference and construction implementation](https://doc.sagemath.org/html/en/reference/combinat/sage/combinat/matrices/hadamard_matrix.html). Standard definitions, determinant characterization, Sylvester and Paley constructions. Our verifier deliberately implements only prime-field Paley I.

[3] Philippe Jaming and Máté Matolcsi, [On the existence of flat orthogonal matrices](https://arxiv.org/abs/1505.03668), 2015. Prior work connecting perfect flatness with Hadamard matrices. The elementary optimization proof above is included for the reader, not claimed as new.

[4] Saleh Ashkboos and coauthors, [QuaRot: Outlier-Free 4-Bit Inference in Rotated LLMs](https://arxiv.org/abs/2404.00456), 2024. Prior rotation-based model quantization.

[5] Albert Tseng and coauthors, [QuIP#: Even Better LLM Quantization with Hadamard Incoherence and Lattice Codebooks](https://proceedings.mlr.press/v235/tseng24a.html), 2024. Prior randomized Hadamard incoherence processing and distinct quantization/codebook design.

[6] Zechun Liu and coauthors, [SpinQuant: LLM quantization with learned rotations](https://arxiv.org/abs/2405.16406), 2024, revised 2025. Prior evidence that rotation selection matters.

[7] `strengthening/protocol-v2.json`, registered in research commit `7d5e4dabccace930c0de2cc41e7da847486f95a1` before the new sample generation. Protocol SHA-256: `1a239984661f3c229225aa4d899fe3960eb2f5f47dc5e7099c49764022f08c29`. Private registration is not represented as public priority. All new experimental numbers in this article come from the accompanying code and raw records, not the cited model papers.

[8] Francesco Mezzadri, [How to generate random matrices from the classical compact groups](https://arxiv.org/abs/math-ph/0609050), 2006. Gaussian QR and Haar-distributed orthogonal matrices.

[9] The Justin Sun Prize, [MathDB award process](https://github.com/TheJustinSunPrize/awards/blob/main/docs/award-process-mathdb.md). Exposition review and committee-selection requirements. The process, submission and award states must be checked separately at handoff.

The article is licensed under CC BY 4.0. The accompanying original experiment and verification code is licensed under MIT. Citations do not relicense third-party work.
