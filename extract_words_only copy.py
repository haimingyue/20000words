#!/usr/bin/env python3
"""
从词库 TXT 中提取“仅单词”列表。

适用输入格式（你这个文件就是这种）：
- 前几行可能是 #separator:tab / #html:false 之类的注释行
- 每行以英文单词开头，后面跟音标/释义/例句等
- 行内可能有 TAB 分隔

输出：
- 每行一个单词（默认去重且保持首次出现顺序）
"""

import argparse
import re
from pathlib import Path
from typing import Iterable, Iterator, Optional


# 支持：letters + apostrophe + hyphen（覆盖 what's / pencil-box 这类）
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*")


def iter_words(lines: Iterable[str]) -> Iterator[str]:
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        # 优先只看 TAB 前（你这个文件 TAB 前就包含单词 + 音标信息）
        left = line.split("\t", 1)[0].strip().strip(' "\'')

        m = WORD_RE.match(left) or WORD_RE.search(left)
        if not m:
            continue
        yield m.group(0)


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
        words = iter_words(f)

        with output_path.open("w", encoding=output_encoding, newline="\n") as out:
            for w in words:
                if to_lower:
                    w = w.lower()
                if dedupe:
                    if w in seen:
                        continue
                    seen.add(w)
                out.write(w + "\n")
                count += 1

    return count


def default_output_path(input_path: Path) -> Path:
    # 保留原扩展名为 .txt
    return input_path.with_name(f"{input_path.stem}__仅单词.txt")


def main() -> None:
    p = argparse.ArgumentParser(description="从词库 TXT 提取仅单词列表（每行一个单词）")
    p.add_argument("input", type=Path, help="输入 TXT 文件路径")
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
        help="不去重，保留重复单词（默认：去重并保序）",
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


