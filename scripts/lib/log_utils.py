#!/usr/bin/env python3
"""
共享日志工具 — audit_batch.py 和 caption.py 共用。
所有日志操作统一走此模块，避免各脚本各自写一套导致格式不一致。
"""

import csv
from datetime import datetime
from pathlib import Path

# ============================================================
# 日志列定义
# ============================================================
# 所有脚本共用的列顺序，靠前列名区分。
# 各脚本只更新自己的列，通过 entry.update() 覆写，不破坏其他列。
LOG_COLS = [
    'timestamp',            # 最近一次更新时间
    'image',                # 图片文件名（含扩展名）
    'original_count',       # PixAi 原始标签数
    'new_count',            # LLM 审计后标签数
    'status',               # success / failed / processing / skipped
    'error',                # 错误信息
    'needs_reaudit',        # 需要重新审计（由 audit 脚本使用）
    'needs_caption',        # 需要生成 caption（由 caption 脚本使用）
    'needs_recaption',      # 需要重新生成 caption（由 caption 脚本使用）
    'caption_length',       # 生成的 caption 词数
    'merged',               # tags+caption 是否已合并到 merged/（由 merge 脚本使用）
]


def init_log(images_dir: Path, audited_dir: Path,
             captions_dir: Path, log_path: Path,
             merged_dir: Path = None) -> dict:
    """扫描图片目录，创建初始空白日志。
    
    从 images/*.txt 读取原始标签数（original_count），
    从 images_audited/*.txt 读取审计后标签数（new_count），
    从 captions/*.txt 读取已有 caption 词数（caption_length）。
    如果 merged_dir 存在，检查 merged/*.txt 设置 merged 标记。
    
    返回 {image_name: entry_dict}
    """
    SUPPORTED_EXT = {'.jpg', '.jpeg', '.png', '.webp'}

    # 去重：一张图可能有多扩展名，只留一条记录
    stems = set()
    for f in sorted(images_dir.iterdir()):
        if f.suffix.lower() in SUPPORTED_EXT:
            stems.add(f.stem)

    entries = {}
    for stem in sorted(stems):
        # 确定实际图片文件名（优先 .jpg）
        img_filename = None
        for ext in ('.jpg', '.png', '.jpeg', '.webp'):
            if (images_dir / f"{stem}{ext}").exists():
                img_filename = f"{stem}{ext}"
                break
        if not img_filename:
            continue

        # 原始 PixAi 标签数
        pixai_txt = images_dir / f"{stem}.txt"
        orig_count = 0
        if pixai_txt.exists():
            tags = pixai_txt.read_text(encoding='utf-8').strip()
            orig_count = len([t for t in tags.split(', ') if t.strip()])

        # 审计后标签数
        audited_txt = audited_dir / f"{stem}.txt"
        new_count = 0
        if audited_txt.exists():
            tags = audited_txt.read_text(encoding='utf-8').strip()
            new_count = len([t for t in tags.split(', ') if t.strip()])

        # 已有 caption
        cap_txt = captions_dir / f"{stem}.txt" if captions_dir else None
        cap_len = 0
        has_caption = False
        if cap_txt and cap_txt.exists():
            cap_len = len(cap_txt.read_text(encoding='utf-8').strip().split())
            has_caption = True

        # 是否已合并到 merged/
        merged = False
        if merged_dir:
            merged_file = merged_dir / f"{stem}.txt"
            if merged_file.exists():
                merged = True

        entries[img_filename] = {
            'timestamp': datetime.now().isoformat(),
            'image': img_filename,
            'original_count': orig_count,
            'new_count': new_count,
            'status': 'success' if audited_txt.exists() else 'pending',
            'error': '',
            'needs_reaudit': 'false',
            'needs_caption': 'false' if has_caption else 'true',
            'needs_recaption': 'false',
            'caption_length': cap_len,
            'merged': 'true' if merged else 'false',
        }

    # 写入文件
    log_path.parent.mkdir(parents=True, exist_ok=True)
    write_log(entries, log_path)
    return entries


def load_log(log_path: Path) -> dict:
    """读取日志，返回 {image_name: {entry_dict}}。日志不存在返回空字典。"""
    if not log_path.exists():
        return {}
    result = {}
    with open(log_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 统一数字类型
            try:
                row['original_count'] = int(row.get('original_count', 0))
            except (ValueError, TypeError):
                row['original_count'] = 0
            try:
                row['new_count'] = int(row.get('new_count', 0))
            except (ValueError, TypeError):
                row['new_count'] = 0
            try:
                row['caption_length'] = int(row.get('caption_length', 0))
            except (ValueError, TypeError):
                row['caption_length'] = 0
            result[row['image']] = row
    return result


def write_log(entries: dict, log_path: Path):
    """将日志条目字典写入 CSV（覆写，按图片名排序）。
    
    始终使用 LOG_COLS 定义的列顺序。
    每个条目中缺失的列自动填默认值。
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    sorted_keys = sorted(entries.keys())
    with open(log_path, 'w', encoding='utf-8', newline='') as f:
        f.write(','.join(LOG_COLS) + '\n')
        for key in sorted_keys:
            r = entries[key]
            vals = [str(r.get(c, '')) for c in LOG_COLS]
            # error 列可能需要引号，但 csv 字段统一为 raw
            f.write(','.join(vals) + '\n')
