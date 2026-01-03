#!/usr/bin/env python3
"""
从《考研词汇5500.txt》这种“带 RECITE/DICTATION/SPELLING 标签”的词库中提取“仅单词”列表。

该文件的典型结构（每个词条会出现 3 行左右）：
- RECITE <word> [phonetic] \t "RECITE <word> [phonetic] ..."
- "SPELLING ..."\t "SPELLING ... \t <word> \t [phonetic] ..."
- DICTATION \t "DICTATION \t <word> \t [phonetic] ..."

输出：
- 每行一个单词（默认去重且保持首次出现顺序）
"""

import argparse
import re
from pathlib import Path
from typing import Iterable, Iterator, Optional


WORD_RE = re.compile(r"^[A-Za-z][A-Za-z'\-]*$")
RECITE_RE = re.compile(r"^RECITE\s+([A-Za-z][A-Za-z'\-]*)\b")


def _strip_quotes(s: str) -> str:
    return s.strip().strip('"').strip("'")


def _extract_from_recite(first_field: str) -> Optional[str]:
    m = RECITE_RE.match(first_field.strip())
    return m.group(1) if m else None


def _extract_from_dictation(second_field: str) -> Optional[str]:
    # second_field: 'DICTATION \tabandon \t[...'
    s = _strip_quotes(second_field)
    if not s.startswith("DICTATION"):
        return None
    # split by tabs/spaces, take the next token after DICTATION
    parts = re.split(r"[\t ]+", s)
    for i, tok in enumerate(parts):
        if tok == "DICTATION" and i + 1 < len(parts):
            w = parts[i + 1].strip()
            return w if WORD_RE.match(w) else None
    return None


def _extract_from_spelling(second_field: str) -> Optional[str]:
    # second_field often contains: ... \t <word> \t [phonetic] ...
    s = _strip_quotes(second_field)
    if "SPELLING" not in s:
        return None
    parts = s.split("\t")
    # Heuristic: find a token that looks like a word and is followed by a phonetic token.
    for i, tok in enumerate(parts):
        w = tok.strip()
        if not WORD_RE.match(w):
            continue
        nxt = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if nxt.startswith("[") or nxt.startswith("/") or nxt.startswith("['") or nxt.startswith('["'):
            return w
    return None


def iter_words(lines: Iterable[str]) -> Iterator[str]:
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        fields = line.split("\t", 1)
        first = _strip_quotes(fields[0])
        second = fields[1] if len(fields) > 1 else ""

        w = _extract_from_recite(first)
        if w:
            yield w
            continue

        if first == "DICTATION":
            w = _extract_from_dictation(second)
            if w:
                yield w
            continue

        if first.startswith("SPELLING") or first == "SPELLING" or "SPELLING" in first:
            w = _extract_from_spelling(second)
            if w:
                yield w
            continue


def write_words(
    input_path: Path,
    output_path: Path,
    *,
    input_encoding: str = "utf-8",
    output_encoding: str = "utf-8",
    dedupe: bool = True,
    to_lower: bool = False,
) -> int:
    seen = set()
    count = 0

    with input_path.open("r", encoding=input_encoding, errors="replace") as f:
        with output_path.open("w", encoding=output_encoding, newline="\n") as out:
            for w in iter_words(f):
                if to_lower:
                    w = w.lower()
                if dedupe:
                    key = w.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                out.write(w + "\n")
                count += 1

    return count


def default_output_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}__仅单词.txt")


def main() -> None:
    p = argparse.ArgumentParser(description="从考研词汇5500（RECITE/DICTATION/SPELLING 格式）提取仅单词列表")
    p.add_argument("input", type=Path, help="输入 TXT 文件路径（如：考研词汇5500.txt）")
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="输出 TXT 文件路径（默认：输入文件名 + __仅单词.txt）",
    )
    p.add_argument("--encoding", default="utf-8", help="输入文件编码（默认：utf-8）")
    p.add_argument(
        "--output-encoding",
        default="utf-8",
        help='输出文件编码（默认：utf-8；Excel 友好可用 "utf-8-sig"）',
    )
    p.add_argument(
        "--keep-duplicates",
        action="store_true",
        help="不去重（默认：去重并保序；去重时按小写比较）",
    )
    p.add_argument("--lower", action="store_true", help="输出统一转小写")
    args = p.parse_args()

    output_path: Path = args.output or default_output_path(args.input)
    n = write_words(
        args.input,
        output_path,
        input_encoding=args.encoding,
        output_encoding=args.output_encoding,
        dedupe=(not args.keep_duplicates),
        to_lower=args.lower,
    )
    print(f"已输出 {n} 行单词 -> {output_path}")


if __name__ == "__main__":
    main()


