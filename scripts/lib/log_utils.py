#!/usr/bin/env python3
"""
共享日志工具 — tag_images.py / audit_batch.py / caption.py / merge_tags_captions.py 共用。
所有日志操作统一走此模块，避免各脚本各自写一套导致格式不一致。
"""

import csv
from datetime import datetime
from pathlib import Path

# ============================================================
# 日志列定义
# ============================================================
# 三阶段完成标志：tagged / audited / captioned（true=已完成）
# 三阶段重跑标志：needs_retag / needs_reaudit / needs_recaption（true=需重跑）
# 各脚本只读自己的两列，只写自己的两列。
LOG_COLS = [
    'timestamp',            # 最近一次更新时间
    'image',                # 图片文件名（含扩展名）
    'tagged',               # PixAi 打标完成（tag_images.py）
    'needs_retag',          # 需要重新打标（tag_images.py）
    'original_count',       # PixAi 原始标签数
    'audited',              # LLM 审计完成（audit_batch.py）
    'needs_reaudit',        # 需要重新审计（audit_batch.py）
    'new_count',            # LLM 审计后标签数
    'captioned',            # 句子 caption 完成（caption.py）
    'needs_recaption',      # 需要重新生成 caption（caption.py）
    'caption_length',       # 生成的 caption 词数
    'merged',               # tags+caption 已合并到 merged/（merge_tags_captions.py）
    'error',                # 最近一次错误信息
]

SUPPORTED_EXT = {'.jpg', '.jpeg', '.png', '.webp'}


def _scan_filesystem(images_dir: Path, audited_dir: Path,
                     captions_dir: Path, merged_dir: Path = None) -> dict:
    """扫描文件系统，构建当前状态条目字典 {img_filename: entry}。
    纯扫描，不涉及旧日志。
    """
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

        # PixAi 打标完成？
        pixai_txt = images_dir / f"{stem}.txt"
        has_pixai = pixai_txt.exists()
        orig_count = 0
        if has_pixai:
            tags = pixai_txt.read_text(encoding='utf-8').strip()
            orig_count = len([t for t in tags.split(', ') if t.strip()])

        # LLM 审计完成？
        audited_txt = audited_dir / f"{stem}.txt"
        has_audited = audited_txt.exists()
        new_count = 0
        if has_audited:
            tags = audited_txt.read_text(encoding='utf-8').strip()
            new_count = len([t for t in tags.split(', ') if t.strip()])

        # 句子 caption 完成？
        cap_txt = captions_dir / f"{stem}.txt" if captions_dir else None
        has_caption = False
        cap_len = 0
        if cap_txt and cap_txt.exists():
            cap_len = len(cap_txt.read_text(encoding='utf-8').strip().split())
            has_caption = True

        # 已合并到 merged/？
        merged = False
        if merged_dir:
            merged_file = merged_dir / f"{stem}.txt"
            if merged_file.exists():
                merged = True

        entries[img_filename] = {
            'timestamp': datetime.now().isoformat(),
            'image': img_filename,
            'tagged': 'true' if has_pixai else 'false',
            'needs_retag': 'false',
            'original_count': orig_count,
            'audited': 'true' if has_audited else 'false',
            'needs_reaudit': 'false',
            'new_count': new_count,
            'captioned': 'true' if has_caption else 'false',
            'needs_recaption': 'false',
            'caption_length': cap_len,
            'merged': 'true' if merged else 'false',
            'error': '',
        }

    return entries


def init_log(images_dir: Path, audited_dir: Path,
             captions_dir: Path, log_path: Path,
             merged_dir: Path = None) -> dict:
    """初始化或更新日志文件。幂等：无变化时不写入。

    对比文件系统与旧日志，检测新增/删除的图片：
    - 新图片：创建新条目，完成标志根据文件系统设，重跑标志=false
    - 删除的图片：打印警告，从日志移除
    - 已存在的图片：保留用户手动设置的 needs_retag/needs_reaudit/needs_recaption

    返回 {image_name: entry_dict}
    """
    # 1. 扫描文件系统当前状态
    new_entries = _scan_filesystem(images_dir, audited_dir, captions_dir, merged_dir)

    # 2. 加载旧日志
    old_entries = load_log(log_path)

    # 3. 首次初始化：直接写入
    if not old_entries:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        write_log(new_entries, log_path)
        print(f"[初始化] 新建日志: {len(new_entries)} 张图片, {log_path}")
        return new_entries

    # 4. 对比差异
    old_names = set(old_entries.keys())
    new_names = set(new_entries.keys())

    added = new_names - old_names
    removed = old_names - new_names
    kept = old_names & new_names

    # 5. 删除的图片：警告
    if removed:
        removed_list = sorted(removed)[:10]
        suffix = f" 等共 {len(removed)} 张" if len(removed) > 10 else ""
        print(f"[⚠ 图片已删除] {', '.join(removed_list)}{suffix}")

    # 6. 已存在的图片：保留用户手动设置的重跑标志（error 不保留——--init 即清理）
    for img_name in kept:
        old = old_entries[img_name]
        new = new_entries[img_name]
        for flag in ('needs_retag', 'needs_reaudit', 'needs_recaption'):
            if old.get(flag, 'false') == 'true':
                new[flag] = 'true'

    # 7. 判断是否有变化
    # 简化比较：去掉 timestamp（每次都不一样），比较其余字段
    def comparable(entry):
        return {k: v for k, v in entry.items() if k != 'timestamp'}

    no_change = (
        not added and not removed
        and all(
            comparable(new_entries[n]) == comparable(old_entries[n])
            for n in kept
        )
    )
    if no_change:
        print(f"[跳过] 日志已是最新，无需更新 ({len(new_entries)} 张)")
        return old_entries

    # 8. 写入
    log_path.parent.mkdir(parents=True, exist_ok=True)
    write_log(new_entries, log_path)

    parts = []
    if added:
        parts.append(f"+{len(added)} 新增")
    if removed:
        parts.append(f"-{len(removed)} 删除")
    if kept:
        parts.append(f"{len(kept)} 不变")
    print(f"[更新] 日志已写入: {', '.join(parts)}, {log_path}")

    return new_entries


def load_log(log_path: Path) -> dict:
    """读取日志，返回 {image_name: {entry_dict}}。日志不存在返回空字典。"""
    if not log_path.exists():
        return {}
    result = {}
    with open(log_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 统一数字类型
            for col in ('original_count', 'new_count', 'caption_length'):
                try:
                    row[col] = int(row.get(col, 0))
                except (ValueError, TypeError):
                    row[col] = 0
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
            f.write(','.join(vals) + '\n')
