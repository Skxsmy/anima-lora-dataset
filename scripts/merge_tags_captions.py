#!/usr/bin/env python3
"""
Step 7: 合成 Tag + Caption，准备训练数据

从 images_audited/（审计后标签）和 captions/（句子 caption）读取，
将两者合并为一个文件，放入 merged/ 子目录，同时复制图片。

合并格式（参考 # 句子 Caption 编写原则.md 第8节）：
    @trigger, tag1, tag2, tag3. Natural language caption sentence.

示例：
    @cierra-rabit, 1girl, solo, upper body, looking at viewer, bedroom, sitting.
    A girl sits on a bed looking toward the viewer.

用法：
  python scripts/merge_tags_captions.py --dataset cierra
  python scripts/merge_tags_captions.py --dataset cierra --dry-run    # 只显示，不写入
"""

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

# 共享日志工具
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.log_utils import load_log, write_log

SUPPORTED_EXT = {'.jpg', '.jpeg', '.png', '.webp'}


def main():
    parser = argparse.ArgumentParser(description='合成 Tag + Caption')
    parser.add_argument('--dataset', required=True, help='数据集名称')
    parser.add_argument('--dry-run', action='store_true', help='只预览，不实际写入')
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    dataset_dir = project_root / 'datasets' / args.dataset
    audited_dir = dataset_dir / 'images_audited'
    captions_dir = dataset_dir / 'captions'
    merged_dir = dataset_dir / 'merged'
    images_dir = dataset_dir / 'images'
    log_file = project_root / 'logs' / f'audit_{args.dataset}.csv'

    if not audited_dir.exists():
        print(f"[错误] 审计标签目录不存在: {audited_dir}")
        return
    if not captions_dir.exists():
        print(f"[错误] Caption 目录不存在: {captions_dir}")
        return

    merged_dir.mkdir(parents=True, exist_ok=True)

    # === 1. 加载日志 ===
    log_entries = load_log(log_file)

    # === 2. 遍历 audited_dir 中的 .txt 文件 ===
    audited_files = sorted(audited_dir.glob('*.txt'), key=lambda p: p.stem)
    if not audited_files:
        print("[错误] 审计目录为空")
        return

    # === 3. 初始化 results（从已有日志继承） ===
    results: dict = {}
    for img_name, entry in log_entries.items():
        results[img_name] = dict(entry)

    success = 0
    skipped = 0

    for audited_path in audited_files:
        stem = audited_path.stem

        # 确定图片文件名
        img_filename = None
        for ext in SUPPORTED_EXT:
            if (images_dir / f'{stem}{ext}').exists():
                img_filename = f'{stem}{ext}'
                break
        if not img_filename:
            print(f"  ⏭️  {stem} — 找不到图片文件")
            skipped += 1
            continue

        # 从已有日志继承，只覆写 merge 相关字段
        entry = dict(results.get(img_filename, {}))
        if not entry:
            entry = {'image': img_filename}

        # 读取审计后标签
        tags = audited_path.read_text(encoding='utf-8').strip()

        # 读取 caption
        cap_path = captions_dir / f'{stem}.txt'
        if not cap_path.exists():
            print(f"  ⏭️  {stem} — 缺少 caption 文件")
            entry.update({
                'timestamp': datetime.now().isoformat(),
                'error': 'missing caption',
                'merged': 'false',
            })
            results[img_filename] = entry
            skipped += 1
            continue
        caption = cap_path.read_text(encoding='utf-8').strip()
        if not caption:
            print(f"  ⏭️  {stem} — caption 为空")
            entry.update({
                'timestamp': datetime.now().isoformat(),
                'error': 'empty caption',
                'merged': 'false',
            })
            results[img_filename] = entry
            skipped += 1
            continue

        # 合并: tags + ". " + caption
        merged_text = f'{tags}. {caption}'

        if args.dry_run:
            print(f"  🔍 {stem}: {merged_text[:100]}...")
            continue

        # 写入 merged txt
        (merged_dir / f'{stem}.txt').write_text(merged_text + '\n', encoding='utf-8')

        # 复制图片
        img_path = images_dir / f'{stem}{Path(img_filename).suffix}'
        shutil.copy2(img_path, merged_dir / f'{stem}{img_path.suffix}')

        # 更新日志
        entry.update({
            'image': img_filename,
            'timestamp': datetime.now().isoformat(),
            'error': '',
            'merged': 'true',
        })
        results[img_filename] = entry
        success += 1

    # === 4. 写入日志 ===
    if not args.dry_run:
        write_log(results, log_file)

    # === 5. 汇总 ===
    print(f"\n{'='*60}")
    if args.dry_run:
        print(f"预览模式: {len(audited_files)} 张检查, {skipped} 跳过")
    else:
        merged_count = sum(1 for e in results.values() if e.get('merged') == 'true')
        print(f"合并完成: {success} 成功, {skipped} 跳过")
        print(f"日志 merged=true: {merged_count}")
        print(f"输出目录: {merged_dir}")
        if success > 0:
            example = next(merged_dir.glob('*.txt'))
            print(f"示例 ({example.name}):")
            print(f"  {example.read_text(encoding='utf-8').strip()}")


if __name__ == '__main__':
    main()
