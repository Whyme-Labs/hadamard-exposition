# Hadamard exposition v3 (draft)

[What the Hadamard conjecture promises](hadamard-conjecture.md) is the version-3 draft. It is a revision, not a replacement record: `submission/v2` stays frozen as the accepted v2 source edition.

## What changed from v2

- **New Part II, "What is known".** History from Sylvester and Hadamard to Paley; Kronecker products; the exact reach of the classical constructions; Williamson's method and the 1962 order-92 search; the computational frontier (428, 764, and the open orders 668, 716, 892 and 1132); asymptotic results of Seberry, Craigen and later work; density results; related open problems; and why the problem is hard.
- **New equivalent forms** in Part I: Hadamard designs, optimal codes and orthogonal arrays.
- **Addendum merged.** The all-Hadamard counterexample theorem replaces the Sylvester-only version in the main text.
- **Application shortened** into Part III. The study's design and headline numbers are unchanged, and the four-arm table shows selected multipliers.
- **Prize discussion removed** from the manuscript body. Award status belongs in the submission note.

## Check and build

```bash
python exposition-v3/known_orders.py --limit 200
python -m unittest discover -s exposition-v3 -p 'test_*.py' -v
python exposition-v3/build_article.py            # needs Pandoc
node submission/v2/strengthening/verify_lab.cjs exposition-v3/build/hadamard-conjecture-v3.html
```

`known_orders.py` computes which multiples of four the Sylvester, Paley and Kronecker-product constructions reach. A missed order is not a nonexistence claim. The tests also check the Williamson array on two examples (orders 12 and 20). The counterexample theorem and study evidence are checked from `submission/v2`, as the article's last section describes.

## Not yet done

- Independent review of Part II by someone who works on Hadamard matrices. The citations were checked against bibliographic sources, but the papers were not all read in full.
- A frozen `submission/v3` source edition, PDF rendering and checksums, after review.
- Public release with a stable link and date, then submission through the official review route.
