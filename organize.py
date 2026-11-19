#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文件整理工具 (file-organizer)

把杂乱文件夹里的文件按类型自动归类到子文件夹，可选：
  - 预览模式（--dry-run）：只看会发生什么，不动任何文件
  - 重复文件检测（--duplicates）：按内容哈希找出完全相同的文件
  - 清理空目录（--clean-empty）
  - 撤销上一次整理（--undo <日志文件>）

只依赖 Python 标准库，无需 pip 安装任何东西。
"""

import argparse
import hashlib
import json
import logging
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------- 配置区

# 分类规则：类别名 -> 该类别包含的扩展名（全部小写）
CATEGORIES = {
    "文档": {".doc", ".docx", ".pdf", ".txt", ".md", ".xls", ".xlsx",
             ".ppt", ".pptx", ".csv", ".rtf", ".odt", ".epub"},
    "图片": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp",
             ".heic", ".tif", ".tiff", ".ico"},
    "视频": {".mp4", ".mov", ".avi", ".mkv", ".flv", ".wmv", ".webm", ".m4v"},
    "音频": {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".wma"},
    "压缩包": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
    "安装包": {".exe", ".msi", ".dmg", ".pkg", ".apk", ".deb", ".rpm"},
    "代码": {".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".hpp",
             ".html", ".css", ".json", ".xml", ".sql", ".sh", ".bat", ".ipynb"},
}

OTHER_CATEGORY = "其他"      # 不在上面任何类别里的文件
DUPLICATE_CATEGORY = "_重复文件"   # --duplicates 时重复文件的去处

log = logging.getLogger("file-organizer")


# ---------------------------------------------------------------- 工具函数

def classify(path: Path) -> str:
    """根据扩展名判断文件属于哪个类别。"""
    suffix = path.suffix.lower()
    for category, suffixes in CATEGORIES.items():
        if suffix in suffixes:
            return category
    return OTHER_CATEGORY


def unique_target(dest_dir: Path, filename: str) -> Path:
    """目标目录里已有同名文件时，自动加 (1)(2) 后缀，绝不覆盖。"""
    target = dest_dir / filename
    if not target.exists():
        return target
    stem, suffix = Path(filename).stem, Path(filename).suffix
    index = 1
    while True:
        candidate = dest_dir / f"{stem}({index}){suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def file_hash(path: Path, chunk_size: int = 1 << 20) -> str:
    """分块计算文件 SHA-256，避免一次性把大文件读进内存。"""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


# ---------------------------------------------------------------- 核心功能

def organize(root: Path, dry_run: bool = False) -> list:
    """把 root 下（只处理第一层）的散落文件移动到分类子文件夹。

    返回操作记录列表，可直接写入日志用于撤销。
    """
    records = []
    moved_count = 0

    for item in sorted(root.iterdir()):
        # 跳过子文件夹、隐藏文件（如 .DS_Store）、以及本工具自己的日志
        if not item.is_file() or item.name.startswith("."):
            continue
        if item.name.endswith("_log.json"):
            continue

        category = classify(item)
        dest_dir = root / category
        target = unique_target(dest_dir, item.name)

        if dry_run:
            log.info("[预览] %s  ->  %s", item.name, category)
        else:
            dest_dir.mkdir(exist_ok=True)
            shutil.move(str(item), str(target))
            records.append({
                "action": "move",
                "src": str(item),
                "dst": str(target),
            })
            log.info("[移动] %s  ->  %s/%s", item.name, category, target.name)
        moved_count += 1

    if dry_run:
        log.info("预览完成：共 %d 个文件待整理，未做任何改动。", moved_count)
    else:
        log.info("整理完成：共移动 %d 个文件。", moved_count)
    return records


def pick_keeper(files: list) -> Path:
    """在一组重复文件里挑出要保留的那一份。

    优先级：名字里没有「副本 / copy / (1)」这类字样 > 体积更大 > 修改时间更早。
    """
    copy_keywords = ("副本", "copy", "(1)", "_1", "复制")

    def score(file: Path):
        name = file.name.lower()
        looks_like_copy = any(keyword in name for keyword in copy_keywords)
        stat = file.stat()
        return (looks_like_copy, -stat.st_size, stat.st_mtime)

    return min(files, key=score)


def find_duplicates(root: Path, dry_run: bool = False) -> list:
    """按「先比大小、再比哈希」的方式找出内容完全相同的文件。

    同一组重复文件里保留一份原始文件，其余移动到 _重复文件 目录。
    """
    by_size = defaultdict(list)
    for item in root.rglob("*"):
        if item.is_file() and not item.name.startswith("."):
            by_size[item.stat().st_size].append(item)

    duplicate_groups = []
    for size, files in by_size.items():
        if len(files) < 2:
            continue
        by_hash = defaultdict(list)
        for file in files:
            by_hash[file_hash(file)].append(file)
        for same_files in by_hash.values():
            if len(same_files) > 1:
                duplicate_groups.append(sorted(same_files))

    records = []
    log.info("发现 %d 组重复文件。", len(duplicate_groups))
    for group in duplicate_groups:
        keeper = pick_keeper(group)
        rest = [file for file in group if file != keeper]
        log.info("保留：%s", keeper.relative_to(root))
        for file in rest:
            log.info("   重复：%s", file.relative_to(root))
            if dry_run:
                continue
            dest_dir = root / DUPLICATE_CATEGORY
            dest_dir.mkdir(exist_ok=True)
            target = unique_target(dest_dir, file.name)
            shutil.move(str(file), str(target))
            records.append({"action": "move", "src": str(file), "dst": str(target)})

    if not duplicate_groups:
        log.info("没有发现重复文件。")
    return records


def clean_empty_dirs(root: Path, dry_run: bool = False) -> list:
    """自下而上删除空文件夹（root 本身保留）。"""
    records = []
    # 深度优先：先处理最深的目录，删掉后父目录才可能变空
    for directory in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if not directory.is_dir():
            continue
        try:
            next(directory.iterdir())
        except StopIteration:      # 目录为空
            if dry_run:
                log.info("[预览] 删除空目录：%s", directory.relative_to(root))
            else:
                directory.rmdir()
                records.append({"action": "rmdir", "src": str(directory), "dst": ""})
                log.info("删除空目录：%s", directory.relative_to(root))
    return records


def save_log(records: list, root: Path) -> Path:
    """把操作记录存成 json，供 --undo 使用。文件名带微秒，避免同一秒多次运行互相覆盖。"""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:23]
    log_path = root / f"organize_{stamp}_log.json"
    index = 1
    while log_path.exists():          # 极端情况下仍重名，兜底加序号
        log_path = root / f"organize_{stamp}_{index}_log.json"
        index += 1
    with log_path.open("w", encoding="utf-8") as handle:
        json.dump(records, handle, ensure_ascii=False, indent=2)
    log.info("操作日志已保存：%s", log_path)
    return log_path


def undo(log_path: Path) -> None:
    """按日志倒序撤销：把移走的文件放回原位，把删掉的空目录建回来。"""
    with log_path.open("r", encoding="utf-8") as handle:
        records = json.load(handle)

    for record in reversed(records):
        if record["action"] == "move":
            src, dst = Path(record["src"]), Path(record["dst"])
            if dst.exists():
                src.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dst), str(src))
                log.info("还原：%s", src.name)
            else:
                log.warning("跳过（原文件已不存在）：%s", dst)
        elif record["action"] == "rmdir":
            Path(record["src"]).mkdir(parents=True, exist_ok=True)
            log.info("重建目录：%s", Path(record["src"]).name)
    log.info("撤销完成。")


# ---------------------------------------------------------------- 命令行入口

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="organize.py",
        description="按类型自动整理文件夹里的文件（默认整理「下载」目录）",
    )
    parser.add_argument(
        "path", nargs="?", default=str(Path.home() / "Downloads"),
        help="要整理的文件夹路径，默认是系统的「下载」目录",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="预览模式：只打印将要发生的操作，不移动任何文件",
    )
    parser.add_argument(
        "--duplicates", action="store_true",
        help="只做重复文件检测，把重复文件移到 _重复文件 目录",
    )
    parser.add_argument(
        "--clean-empty", action="store_true",
        help="整理后清理空文件夹",
    )
    parser.add_argument(
        "--undo", metavar="LOG",
        help="撤销：传入之前生成的 organize_xxx_log.json 路径",
    )
    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = build_parser().parse_args()

    if args.undo:
        undo(Path(args.undo))
        return 0

    root = Path(args.path).expanduser()
    if not root.is_dir():
        log.error("路径不存在或不是文件夹：%s", root)
        return 1

    log.info("目标目录：%s", root)
    if args.dry_run:
        log.info("当前为预览模式，不会移动任何文件。\n")

    all_records = []
    if args.duplicates:
        all_records += find_duplicates(root, dry_run=args.dry_run)
    else:
        all_records += organize(root, dry_run=args.dry_run)
        if args.clean_empty:
            all_records += clean_empty_dirs(root, dry_run=args.dry_run)

    if all_records and not args.dry_run:
        save_log(all_records, root)
        log.info("如需回退，执行：python organize.py --undo <日志文件>")

    return 0


if __name__ == "__main__":
    sys.exit(main())
