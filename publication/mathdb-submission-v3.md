# MathDB submission packet: v3

The MathDB pilot process says to submit Exposition material "through MathDB's available submission entry point". For this problem that is the Paper section of [mathdb.com](https://mathdb.com/papers) ("Upload paper"), which requires a signed-in account. Only the author should upload. The prize rules say uploading someone else's work does not make the uploader the contributor.

## Files to upload

The exact files are committed in [`publication/mathdb-v3/`](mathdb-v3/) on branch `claude/friendly-archimedes-hr59ze`. Upload those copies. They can also be rebuilt from a clean checkout of the same branch:

```bash
python publication/build_mathdb_packet.py      # writes build/mathdb-v3/
```

| File | Bytes | SHA-256 |
|---|---:|---|
| `hadamard-conjecture-v3.pdf` (main paper) | 309,619 | `cdc51674a7a25633445088c7767e3ccb6aaea219fedacaa1aa2ecdd1847635d4` |
| `hadamard-exposition-v3-supporting-files.zip` (supporting material) | 452,530 | `c36d540d33b20da5d6d7bd46f882b3ecb93fca0fd3f4e8c67f5da9baf0f9b2f1` |

The PDF is the frozen `submission/v3` file, unchanged. The ZIP holds `submission/v3` and `submission/v2` at their repository paths, so the article's "Reproduce and inspect" commands run from the ZIP root. A fresh clone rebuilt both files with identical digests. A different Python or zlib version can still compress the ZIP differently, so if a rebuilt ZIP's digest differs, use the committed copy; each edition's own `SHA256SUMS` checks the contents either way. If the upload form accepts only one file, upload the PDF.

## Form fields

**Title:** What the Hadamard conjecture promises

**Subtitle, if the form has one:** Perfect balance, the orders we can reach, and why balance does not guarantee better rounding

**Author:** Wei Meng Soh (Whyme Labs)

**Linked problem:** Hadamard conjecture, https://mathdb.com/p/315867

**Category or type, if asked:** Exposition

**License, if asked:** CC BY 4.0 for the text and data, MIT for the code

**Abstract:**

> An exposition of the Hadamard conjecture (JSP-000013). Part I proves that a Hadamard matrix has order 1, 2 or a multiple of four. It characterizes Hadamard matrices as the orthogonal matrices with the smallest possible largest entry and as the sign matrices of maximal determinant, and explains the equivalent design, code and orthogonal-array forms. Part II surveys what is known: Sylvester, Paley and Williamson constructions, with a complete proof of the prime-field Paley construction; the exact reach of the classical constructions; the 1962 computer search for order 92 and the failure of the Williamson conjecture; the computational frontier from order 428 to the twelve orders below 2000 settled in 2026, leaving 2396 as the smallest open order; and the asymptotic and density results of Seberry, Craigen, de Launey and others. Part III is an application. It gives a fixed input that is quantized exactly in its original coordinates but with positive error after rotation by every Hadamard matrix of each existing order, so perfect balance does not guarantee better rounding. A preregistered synthetic study is summarized, including its unfavorable results. No new Hadamard order or proof of the conjecture is claimed. AI assistance in writing, derivations, code and internal review is disclosed.

**Note to reviewers, if there is a comment field:**

> Submitted as an Exposition for JSP-000013 under the MathDB pilot. Version 3 is fixed by the SHA-256 digests above. The internal review record is in the supporting ZIP at submission/v3/REVIEW.md; it is AI self-review, not external peer review.

## Before you upload

1. Sign in to MathDB as the author.
2. Compare both files' SHA-256 digests with the table above (`shasum -a 256` on macOS, `sha256sum` on Linux).
3. Read the PDF once more. After upload, the version is fixed; any change needs a new version and, under the prize rules, a fresh 14-day notice.

## After you upload

The upload creates the public date that counts for priority. Record it right away:

1. Open the paper's MathDB URL in a private browser window, signed out, and confirm the PDF downloads.
2. Note the UTC time at which you saw it public, and the page's own posted date.
3. Download the PDF back from MathDB and check its SHA-256 against the table.
4. Send these to the assistant, or commit them as `publication/receipt-v3.json`: the MathDB paper URL, the observed UTC time, the posted date, and the downloaded digest. Do not edit `submission/v3/PUBLICATION.json`; it is the frozen pre-publication record.

## For an assistant doing the upload in a browser

- Work from branch `claude/friendly-archimedes-hr59ze` of `Whyme-Labs/hadamard-exposition`. It is not merged into `main`.
- The author signs in to MathDB personally. Never type, store or ask for the password.
- Upload `publication/mathdb-v3/hadamard-conjecture-v3.pdf` as the paper, and the ZIP as supporting material if the form allows it.
- Fill the fields from "Form fields" above, verbatim. If the form needs a field not listed here, ask the author.
- Link the upload to problem 315867. If there is no way to link it, stop and ask.
- Before the final submit, show the author the completed form and get explicit approval. The upload is public, and it fixes the version.
- After submitting, do the "After you upload" steps and commit `publication/receipt-v3.json` on the same branch:

```json
{
  "mathdb_paper_url": "",
  "first_public_observed_utc": "",
  "mathdb_posted_date": "",
  "downloaded_pdf_sha256": "",
  "matches_submitted_pdf": true,
  "observed_signed_out": true
}
```

## What happens next under the official process

- MathDB reviews the content. After its checks pass, MathDB, not the author, opens or updates the prize's Claim Reward issue and emails the contributor, copying the prize team (`thejustinsunprize@hejustinsun.com`).
- Reply to that email personally. Send identity or payment details only through the official email channel, never in a public issue.
- If accepted, the candidate is listed publicly for a 14-day review. The committee separately selects the first satisfactory exposition.

As of 22 October 2026 the pilot register showed the rollout as "prepared", with formal automatic claims starting only after activation is announced. JSP-000013 listed no announced reward and no Exposition candidate. Uploading now fixes a public date, but the claim may wait for activation. If nothing arrives after activation, MathDB support is `admin@mathdb.com`.

Official process: https://github.com/TheJustinSunPrize/awards/blob/main/docs/award-process-mathdb.md
