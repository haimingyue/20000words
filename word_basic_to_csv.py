#!/usr/bin/env python3
"""
Convert the tab-separated word TXT into CSV with only word, phonetic, meaning.
Percent values in the meaning (e.g., "28%") are stripped.
"""

import argparse
import csv
import re
from pathlib import Path
from typing import Iterable, Tuple

WORD_RE = re.compile(r"^[A-Za-z][A-Za-z'\-]*")
PHONETIC_RE = re.compile(r"/[^/]+/")
EXAMPLE_RE = re.compile(r"[A-Z][^.?!]{15,}?[.?!]")
PERCENT_RE = re.compile(r"\d+%")


def clean_meaning(text: str, example: str, word: str, phonetic: str) -> str:
    meaning = text
    if example:
        cut = meaning.find(example)
        if cut > 0:
            meaning = meaning[:cut]
    meaning = PERCENT_RE.sub("", meaning)
    if phonetic:
        meaning = meaning.replace(phonetic, "")
    if word:
        leading = re.compile(rf"^{re.escape(word)}\s+", re.IGNORECASE)
        meaning = leading.sub("", meaning)
    return meaning.strip()


def extract_fields(line: str) -> Tuple[str, str, str, str, str]:
    parts = line.split("\t", 1)
    left = parts[0].strip(' "\'')
    right = parts[1].strip(' "\'') if len(parts) > 1 else ""
    combined = f"{left} {right}".strip()

    word_match = WORD_RE.match(left) or WORD_RE.match(combined)
    word = word_match.group(0) if word_match else ""

    ph = PHONETIC_RE.search(left) or PHONETIC_RE.search(right)
    phonetic = ph.group(0) if ph else ""

    ex = EXAMPLE_RE.search(right) or EXAMPLE_RE.search(left)
    example = ex.group(0).strip() if ex else ""

    meaning = clean_meaning(right or left, example, word, phonetic)

    example = ""
    source = ""

    return word, phonetic, meaning, example, source


def convert(lines: Iterable[str]) -> Iterable[Tuple[int, str, str, str, str, str]]:
    """
    Yield rows in COCA order (i.e., the appearance order in the input file),
    with a 1-based rank column.
    """
    rank = 0
    for raw in lines:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        rank += 1
        word, phonetic, meaning, example, source = extract_fields(raw.rstrip("\n"))
        yield rank, word, phonetic, meaning, example, source


def convert_file(input_path: Path, output_path: Path, encoding: str = "utf-8") -> None:
    """
    Convert a word-list TXT file to CSV.

    Output columns: rank, word, phonetic, meaning, example, source
    """
    with input_path.open("r", encoding=encoding, errors="replace") as fh:
        rows = list(convert(fh))

    with output_path.open("w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(["rank", "word", "phonetic", "meaning", "example", "source"])
        writer.writerows(rows)


def convert_file_with_output_encoding(
    input_path: Path,
    output_path: Path,
    *,
    input_encoding: str = "utf-8",
    output_encoding: str = "utf-8",
) -> None:
    """
    Convert TXT to CSV with explicit input/output encodings.

    Tip: use output_encoding="utf-8-sig" for Excel-friendly UTF-8 with BOM.
    """
    with input_path.open("r", encoding=input_encoding, errors="replace") as fh:
        rows = list(convert(fh))

    with output_path.open("w", newline="", encoding=output_encoding) as out:
        writer = csv.writer(out)
        writer.writerow(["rank", "word", "phonetic", "meaning", "example", "source"])
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert word-list TXT to CSV (rank, word, phonetic, meaning)."
    )
    parser.add_argument("input", type=Path, help="input TXT file")
    parser.add_argument("output", type=Path, help="output CSV file path")
    parser.add_argument(
        "--encoding", default="utf-8", help="file encoding (default: utf-8)"
    )
    parser.add_argument(
        "--output-encoding",
        default="utf-8",
        help='output CSV encoding (default: utf-8). For Excel, use "utf-8-sig".',
    )
    parser.add_argument(
        "--excel",
        action="store_true",
        help='write CSV as "utf-8-sig" (UTF-8 with BOM) for better Excel compatibility',
    )
    args = parser.parse_args()

    output_encoding = "utf-8-sig" if args.excel else args.output_encoding
    convert_file_with_output_encoding(
        args.input,
        args.output,
        input_encoding=args.encoding,
        output_encoding=output_encoding,
    )


if __name__ == "__main__":
    main()
