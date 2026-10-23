# Hadamard exposition v3 (draft)

[What the Hadamard conjecture promises](hadamard-conjecture.md) is the version-3 draft. It is a revision, not a replacement record: `submission/v2` stays frozen as the accepted v2 source edition.

## What changed from v2

- **New Part II, "What is known".** History from Sylvester and Hadamard to Paley; Kronecker products; the exact reach of the classical constructions; Williamson's method and the 1962 order-92 search; the computational frontier (428, 764, the twelve orders below 2000 settled in 2026, and the smallest open order 2396); asymptotic results of Seberry, Craigen and later work; density results; related open problems; and why the problem is hard.
- **New equivalent forms** in Part I: Hadamard designs, optimal codes and orthogonal arrays.
- **Addendum merged.** The all-Hadamard counterexample theorem replaces the Sylvester-only version in the main text.
- **Application shortened** into Part III. The study's design and headline numbers are unchanged, and the four-arm table shows selected multipliers.
- **Prize discussion removed** from the manuscript body. Award status belongs in the submission note.

## Check, build and freeze

```bash
python exposition-v3/known_orders.py --limit 200
python -m unittest discover -s exposition-v3 -p 'test_*.py' -v
python exposition-v3/build_article.py            # needs Pandoc
python exposition-v3/build_pdf.py                # needs Playwright and Chromium
python exposition-v3/freeze_edition.py           # clean committed tree only; writes submission/v3
```

`known_orders.py` computes which multiples of four the Sylvester, Paley and Kronecker-product constructions reach. A missed order is not a nonexistence claim. The tests check the Williamson array at orders 12 and 20, and rebuild the 1962 order-92 matrix from its published first rows. `edition/` holds the metadata files copied into the frozen edition. `freeze_edition.py` refuses to overwrite an existing `submission/v3`.

## Not yet done

- Human specialist review. An internal AI review is recorded in [REVIEW.md](REVIEW.md), with every finding fixed. A few bibliographic details remain unconfirmed online.
- Public release with a stable link and date, then submission through the official review route.
