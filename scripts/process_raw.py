#!/usr/bin/env python3
"""
Step 2: 图片摄入与命名标准化
摄取 raw/ 中的原始图片，复制到 images/ 并统一编号命名。
用法: python process_raw.py --dataset 角色名
"""

import argparse
import os
import sys
import shutil
import csv
from pathlib import Path

import struct
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUPPORTED_EXT = {'.png', '.jpg', '.jpeg', '.webp'}
BLOCKED_EXT = {'.psd', '.clip', '.sai', '.gif', '.bmp'}


def is_valid_image(path: Path) -> bool:
    """尝试读取图片头，确认文件不是损坏的"""
    try:
        with Image.open(path) as img:
            img.verify()
        return True
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description='图片摄入与命名标准化')
    parser.add_argument('--dataset', required=True, help='数据集名称（对应 datasets/下的子目录名）')
    args = parser.parse_args()

    dataset_dir = PROJECT_ROOT / 'datasets' / args.dataset
    raw_dir = dataset_dir / 'raw'
    images_dir = dataset_dir / 'images'

    # 检查 raw/ 目录
    if not raw_dir.exists():
        print(f"[错误] raw/ 目录不存在: {raw_dir}")
        print(f"请先创建 {raw_dir} 并放入原始图片")
        sys.exit(1)

    raw_files = sorted(
        [f for f in raw_dir.iterdir() if f.is_file()],
        key=lambda p: p.name
    )
    if not raw_files:
        print(f"[警告] raw/ 目录为空: {raw_dir}")
        print("请放入图片后重新运行")
        sys.exit(0)

    # 创建 images/ 目录
    images_dir.mkdir(parents=True, exist_ok=True)

    # 确定起始编号（从已有文件的最大编号继续）
    existing = sorted(
        [f for f in images_dir.iterdir() if f.is_file() and f.suffix in SUPPORTED_EXT],
        key=lambda p: p.name
    )
    start_num = 1
    if existing:
        last_name = existing[-1].stem  # 如 '000005'
        try:
            start_num = int(last_name) + 1
        except ValueError:
            start_num = len(existing) + 1

    # 统计
    processed = 0
    skipped = 0
    mapping = []

    print(f"数据集: {args.dataset}")
    print(f"源目录: {raw_dir}")
    print(f"目标目录: {images_dir}")
    print(f"起始编号: {start_num:06d}")
    print(f"图片总数: {len(raw_files)}")
    print("-" * 50)

    for i, src_path in enumerate(raw_files):
        ext = src_path.suffix.lower()

        # 检查扩展名
        if ext in BLOCKED_EXT:
            print(f"  [跳过] 不支持格式: {src_path.name}")
            skipped += 1
            continue
        if ext not in SUPPORTED_EXT:
            print(f"  [跳过] 未知格式: {src_path.name}")
            skipped += 1
            continue

        # 检查图片是否可读
        if not is_valid_image(src_path):
            print(f"  [跳过] 图片损坏: {src_path.name}")
            skipped += 1
            continue

        # 生成目标文件名
        num = start_num + processed
        dst_name = f"{num:06d}{ext}"
        dst_path = images_dir / dst_name

        # 复制文件
        shutil.copy2(src_path, dst_path)
        mapping.append((src_path.name, dst_name, str(src_path), str(dst_path)))
        processed += 1
        print(f"  [{processed:3d}] {src_path.name} → {dst_name}")

    # 写入映射表
    if mapping:
        csv_path = dataset_dir / 'mapping.csv'
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['original_name', 'new_name', 'original_path', 'new_path'])
            writer.writerows(mapping)
        print(f"\n映射表: {csv_path}")

    # 汇总
    print("-" * 50)
    print(f"处理完成: {processed} 张已导入, {skipped} 张已跳过")
    if processed > 0:
        print(f"编号范围: {start_num:06d} ~ {start_num + processed - 1:06d}")


if __name__ == '__main__':
    main()
