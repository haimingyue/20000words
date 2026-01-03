#!/usr/bin/env python3
"""
Convert the tab-separated word TXT into CSV with only word, phonetic, meaning.
Percent values in the meaning (e.g., "28%") are stripped.
"""

import argparse
import csv
import re
from pathlib import Path
from collections import defaultdict
from typing import Iterable, Tuple, Optional, Set, Dict, List, Sequence, DefaultDict

WORD_RE = re.compile(r"^[A-Za-z][A-Za-z'\-]*")
PHONETIC_RE = re.compile(r"/[^/]+/")
EXAMPLE_RE = re.compile(r"[A-Z][^.?!]{15,}?[.?!]")
PERCENT_RE = re.compile(r"\d+%")

LEVEL_FROM_FILENAME = {
    "COCA": "COCA",
    "初中": "初中",
    "高中": "高中",
    "大学四级": "四级",
    "大学六级": "六级",
    "四级": "四级",
    "六级": "六级",
    "考研": "考研",
    "GRE": "GRE",
    "TOEFL": "TOEFL",
}

AUTO_LABEL_FILES = {
    # label: filename
    "小学": "广州小学英语__仅单词.txt",
    "初中": "初中英语单词__仅单词.txt",
    "高中": "高中英语单词__仅单词.txt",
    "四级": "大学四级英语单词__仅单词.txt",
    "六级": "大学六级英语单词__仅单词.txt",
    "考研": "考研词汇5500__仅单词.txt",
    "GRE": "极品GRE红宝书__仅单词.txt",
    "TOEFL": "TOEFL词汇__仅单词.txt",
}


def infer_level_from_path(input_path: Path) -> str:
    """
    Infer a level string from the input filename.
    Example: '初中英语单词__仅单词.txt' -> '初中'
    """
    name = input_path.name
    for key, level in LEVEL_FROM_FILENAME.items():
        if key in name:
            return level
    return ""


def load_word_set(word_list_path: Path, *, encoding: str = "utf-8") -> Set[str]:
    """
    Load a one-word-per-line word list file into a lowercase set.
    Blank lines and comment lines starting with '#' are ignored.
    """
    words: Set[str] = set()
    with word_list_path.open("r", encoding=encoding, errors="replace") as fh:
        for raw in fh:
            s = raw.strip()
            if not s or s.startswith("#"):
                continue
            words.add(s.lower())
    return words


def build_label_sets(
    label_specs: Sequence[str],
    *,
    auto_labels_dir: Optional[Path] = None,
    auto_labels: bool = False,
    encoding: str = "utf-8",
) -> List[Tuple[str, Set[str]]]:
    """
    Build label->word_set mappings from:
    - explicit --label specs, e.g. "小学=/path/to/广州小学英语__仅单词.txt"
    - optional auto discovery based on known filenames in a directory
    """
    merged: DefaultDict[str, Set[str]] = defaultdict(set)

    if auto_labels:
        if auto_labels_dir is None:
            raise ValueError("auto_labels_dir is required when auto_labels=True")
        for lbl, fname in AUTO_LABEL_FILES.items():
            p = auto_labels_dir / fname
            if p.exists():
                merged[lbl].update(load_word_set(p, encoding=encoding))

    for spec in label_specs or []:
        lbl, p = parse_label_spec(spec)
        merged[lbl].update(load_word_set(p, encoding=encoding))

    # keep stable order: auto labels order first, then manual specs in appearance order
    out: List[Tuple[str, Set[str]]] = []
    seen = set()
    if auto_labels:
        for lbl in AUTO_LABEL_FILES.keys():
            if lbl in merged and lbl not in seen:
                out.append((lbl, merged[lbl]))
                seen.add(lbl)
    for spec in label_specs or []:
        lbl, _ = parse_label_spec(spec)
        if lbl in merged and lbl not in seen:
            out.append((lbl, merged[lbl]))
            seen.add(lbl)
    return out


def append_level(level: str, add: str, *, sep: str = ",") -> str:
    """
    Append a level tag to an existing level string, de-duplicated by separator.

    Examples:
    - append_level("", "初中") -> "初中"
    - append_level("COCA", "初中") -> "COCA,初中"
    - append_level("COCA,初中", "初中") -> "COCA,初中"
    """
    add = (add or "").strip()
    if not add:
        return level

    level = (level or "").strip()
    if not level:
        return add

    tokens = [t.strip() for t in level.split(sep)]
    if add in tokens:
        return level
    return f"{level}{sep}{add}"


def load_existing_levels_by_rank(csv_path: Path) -> Dict[int, str]:
    """
    Load existing level values from an already-generated CSV.
    Returns a mapping: rank(int) -> level(str).

    If the CSV doesn't have rank/level columns, returns {}.
    """
    for enc in ("utf-8-sig", "utf-8"):
        try:
            with csv_path.open("r", newline="", encoding=enc, errors="replace") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    return {}
                if "rank" not in reader.fieldnames or "level" not in reader.fieldnames:
                    return {}
                out: Dict[int, str] = {}
                for row in reader:
                    try:
                        r = int((row.get("rank") or "").strip())
                    except ValueError:
                        continue
                    out[r] = (row.get("level") or "").strip()
                return out
        except FileNotFoundError:
            return {}
    return {}


def parse_label_spec(spec: str) -> Tuple[str, Path]:
    """
    Parse label spec in the form:
    - "小学=/path/to/广州小学英语__仅单词.txt"
    - "初中:/path/to/初中英语单词__仅单词.txt"
    """
    s = (spec or "").strip()
    if not s:
        raise ValueError("empty label spec")
    if "=" in s:
        label, path = s.split("=", 1)
    elif ":" in s:
        label, path = s.split(":", 1)
    else:
        raise ValueError('label spec must contain "=" or ":" (e.g., 小学=广州小学英语__仅单词.txt)')
    label = label.strip()
    path = path.strip().strip('"').strip("'")
    if not label or not path:
        raise ValueError('label spec must be like "小学=path"')
    return label, Path(path)


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


def extract_first_three_meanings(full_meaning: str) -> str:
    """
    Extract the first three meanings from full_meaning.
    Meanings are typically separated by semicolons (； or ;), commas (， or ,), 
    or by part-of-speech markers (like "art.", "adv.", "n.", etc.).
    """
    if not full_meaning:
        return ""
    
    # Strategy 1: Split by semicolon (most common in Chinese-English dictionaries)
    if "；" in full_meaning:
        meanings = [m.strip() for m in full_meaning.split("；") if m.strip()]
        if len(meanings) <= 3:
            return full_meaning
        return "；".join(meanings[:3])
    elif ";" in full_meaning:
        meanings = [m.strip() for m in full_meaning.split(";") if m.strip()]
        if len(meanings) <= 3:
            return full_meaning
        return ";".join(meanings[:3])
    
    # Strategy 2: Split by comma
    if "，" in full_meaning:
        meanings = [m.strip() for m in full_meaning.split("，") if m.strip()]
        if len(meanings) <= 3:
            return full_meaning
        return "，".join(meanings[:3])
    elif "," in full_meaning:
        meanings = [m.strip() for m in full_meaning.split(",") if m.strip()]
        if len(meanings) <= 3:
            return full_meaning
        return ",".join(meanings[:3])
    
    # Strategy 3: Split by part-of-speech markers (art., adv., n., v., etc.)
    # Pattern: word class abbreviation followed by meaning
    # Example: "art.这；那adv.更加" -> ["art.这；那", "adv.更加"]
    pos_pattern = r"([a-z]+\.\s*[^a-z]+?)(?=[a-z]+\.|$)"
    matches = list(re.finditer(pos_pattern, full_meaning, re.IGNORECASE))
    if len(matches) > 3:
        # Take first three POS groups
        end_pos = matches[2].end()
        return full_meaning[:end_pos].strip()
    elif len(matches) > 0:
        # If 3 or fewer, return all
        return full_meaning
    
    # Strategy 4: If no clear separator found, try to find natural breaks
    # Look for patterns like "词性.意思" and count them
    pos_break_pattern = r"([a-z]+\.\s*[^a-z\.]+)"
    pos_matches = list(re.finditer(pos_break_pattern, full_meaning, re.IGNORECASE))
    if len(pos_matches) > 3:
        end_pos = pos_matches[2].end()
        return full_meaning[:end_pos].strip()
    
    # Fallback: return the whole meaning if we can't split it meaningfully
    return full_meaning


def extract_fields(line: str) -> Tuple[str, str, str, str, str, str]:
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

    # Get full meaning (before cleaning)
    raw_meaning = right or left
    if example:
        cut = raw_meaning.find(example)
        if cut > 0:
            raw_meaning = raw_meaning[:cut]
    
    # Clean full meaning
    full_meaning = clean_meaning(raw_meaning, example, word, phonetic)
    
    # Extract first three meanings
    meaning = extract_first_three_meanings(full_meaning)

    example = ""
    source = ""

    return word, phonetic, meaning, full_meaning, example, source


def convert(
    lines: Iterable[str],
    *,
    level: str = "",
    level_words: Optional[Set[str]] = None,
    level_value: str = "初中",
    level_sep: str = ",",
    existing_levels_by_rank: Optional[Dict[int, str]] = None,
    label_sets: Optional[Sequence[Tuple[str, Set[str]]]] = None,
) -> Iterable[Tuple[int, str, str, str, str, str, str, str]]:
    """
    Yield rows in COCA order (i.e., the appearance order in the input file),
    with a 1-based rank column.
    Returns: rank, level, word, phonetic, meaning, full_meaning, example, source
    """
    rank = 0
    for raw in lines:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        rank += 1
        word, phonetic, meaning, full_meaning, example, source = extract_fields(raw.rstrip("\n"))
        row_level = (
            existing_levels_by_rank.get(rank, level)
            if existing_levels_by_rank is not None
            else level
        )
        w_lower = word.lower() if word else ""
        if level_words is not None and w_lower and w_lower in level_words:
            row_level = append_level(row_level, level_value, sep=level_sep)
        if label_sets and w_lower:
            for lbl, words in label_sets:
                if w_lower in words:
                    row_level = append_level(row_level, lbl, sep=level_sep)
        yield rank, row_level, word, phonetic, meaning, full_meaning, example, source


def convert_file(
    input_path: Path,
    output_path: Path,
    encoding: str = "utf-8",
    *,
    level: str = "",
    level_words: Optional[Set[str]] = None,
    level_value: str = "初中",
    level_sep: str = ",",
    merge_existing_output: bool = False,
    label_sets: Optional[Sequence[Tuple[str, Set[str]]]] = None,
) -> None:
    """
    Convert a word-list TXT file to CSV.

    Output columns: rank, level, word, phonetic, meaning, full_meaning, example, source
    """
    existing_levels_by_rank = (
        load_existing_levels_by_rank(output_path)
        if merge_existing_output and output_path.exists()
        else None
    )

    with input_path.open("r", encoding=encoding, errors="replace") as fh:
        rows = list(
            convert(
                fh,
                level=level,
                level_words=level_words,
                level_value=level_value,
                level_sep=level_sep,
                existing_levels_by_rank=existing_levels_by_rank,
                label_sets=label_sets,
            )
        )

    with output_path.open("w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(
            ["rank", "level", "word", "phonetic", "meaning", "full_meaning", "example", "source"]
        )
        writer.writerows(rows)


def convert_file_with_output_encoding(
    input_path: Path,
    output_path: Path,
    *,
    input_encoding: str = "utf-8",
    output_encoding: str = "utf-8",
    level: str = "",
    level_words: Optional[Set[str]] = None,
    level_value: str = "初中",
    level_sep: str = ",",
    merge_existing_output: bool = False,
    label_sets: Optional[Sequence[Tuple[str, Set[str]]]] = None,
) -> None:
    """
    Convert TXT to CSV with explicit input/output encodings.

    Output columns: rank, level, word, phonetic, meaning, full_meaning, example, source
    Tip: use output_encoding="utf-8-sig" for Excel-friendly UTF-8 with BOM.
    """
    existing_levels_by_rank = (
        load_existing_levels_by_rank(output_path)
        if merge_existing_output and output_path.exists()
        else None
    )

    with input_path.open("r", encoding=input_encoding, errors="replace") as fh:
        rows = list(
            convert(
                fh,
                level=level,
                level_words=level_words,
                level_value=level_value,
                level_sep=level_sep,
                existing_levels_by_rank=existing_levels_by_rank,
                label_sets=label_sets,
            )
        )

    with output_path.open("w", newline="", encoding=output_encoding) as out:
        writer = csv.writer(out)
        writer.writerow(
            ["rank", "level", "word", "phonetic", "meaning", "full_meaning", "example", "source"]
        )
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert word-list TXT to CSV (rank, level, word, phonetic, meaning, full_meaning)."
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
    parser.add_argument(
        "--level",
        default=None,
        help='level to write into the "level" column (default: infer from input filename; empty if unknown)',
    )
    parser.add_argument(
        "--level-words",
        type=Path,
        default=None,
        help='path to a one-word-per-line word list; if provided, rows whose "word" appears in this list will be labeled',
    )
    parser.add_argument(
        "--level-value",
        default="初中",
        help='value to write into "level" when matched by --level-words (default: 初中)',
    )
    parser.add_argument(
        "--level-sep",
        default="、",
        help='separator for multiple level tags in the "level" column (default: "、")',
    )
    parser.add_argument(
        "--label",
        action="append",
        default=[],
        help='repeatable: add label from a word list, like --label 小学=广州小学英语__仅单词.txt --label 初中=初中英语单词__仅单词.txt',
    )
    parser.add_argument(
        "--auto-labels",
        action="store_true",
        help="auto load level word lists from known *__仅单词.txt filenames in the same directory as input file",
    )
    parser.add_argument(
        "--auto-labels-dir",
        type=Path,
        default=None,
        help="directory to search for known *__仅单词.txt files when --auto-labels is set (default: input file directory)",
    )
    parser.add_argument(
        "--merge-existing-output",
        action="store_true",
        help="if output CSV already exists, merge its existing level values by rank before appending new tags",
    )
    args = parser.parse_args()

    output_encoding = "utf-8-sig" if args.excel else args.output_encoding
    # If user provides labels (manual or auto) and does NOT explicitly set --level,
    # default base level to empty to avoid surprising auto-inferred tags like "COCA".
    has_labels = bool(args.label) or bool(args.auto_labels)
    level: str = args.level if args.level is not None else ("" if has_labels else infer_level_from_path(args.input))
    level_words = load_word_set(args.level_words) if args.level_words else None

    auto_dir = args.auto_labels_dir or args.input.parent
    label_sets: List[Tuple[str, Set[str]]] = build_label_sets(
        args.label or [],
        auto_labels_dir=auto_dir,
        auto_labels=bool(args.auto_labels),
        encoding=args.encoding,
    )

    convert_file_with_output_encoding(
        args.input,
        args.output,
        input_encoding=args.encoding,
        output_encoding=output_encoding,
        level=level,
        level_words=level_words,
        level_value=args.level_value,
        level_sep=args.level_sep,
        merge_existing_output=args.merge_existing_output,
        label_sets=label_sets or None,
    )


if __name__ == "__main__":
    main()
