#!/usr/bin/env python3
"""Build the standalone article from the tracked manuscript and assets."""

import argparse
from pathlib import Path
import shutil
import subprocess


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=root / "exposition.html")
    args = parser.parse_args()
    pandoc = shutil.which("pandoc")
    if pandoc is None:
        raise SystemExit("Pandoc is required to build the article. Numerical validation does not require it.")
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            pandoc, "article.md", "--standalone", "--mathml", "--embed-resources",
            "--css", "style.css", "--include-after-body=calculator.html",
            "--metadata", "pagetitle=What changes when the answer stays the same",
            "--output", str(output),
        ],
        cwd=root,
        check=True,
        timeout=60,
    )
    print(f"Built {output}")


if __name__ == "__main__":
    main()
