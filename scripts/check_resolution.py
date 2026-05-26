#!/usr/bin/env python3
"""
Step 3: 分辨率检查与可选缩放
检查 images/ 中的图片分辨率，对超大的图片建议等比缩放。
用法:
  python check_resolution.py --dataset 角色名         # 仅报告
  python check_resolution.py --dataset 角色名 --apply  # 执行缩放
"""

import argparse
import os
import sys
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUPPORTED_EXT = {'.png', '.jpg', '.jpeg', '.webp'}
LONG_SIDE_TARGET = 1024
LONG_SIDE_UPPER = 1536
SHORT_SIDE_MIN = 768


def get_image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as img:
        return img.size  # (width, height)


def calc_scale(width: int, height: int) -> tuple[int, int] | None:
    """如果长边超过上限，计算缩放后的尺寸（严格保持宽高比）。返回 (new_w, new_h) 或 None。"""
    long_side = max(width, height)
    if long_side <= LONG_SIDE_UPPER:
        return None
    ratio = LONG_SIDE_TARGET / long_side
    new_w = round(width * ratio)
    new_h = round(height * ratio)
    return (new_w, new_h)


def downscale_image(src: Path, dst: Path, new_size: tuple[int, int]):
    with Image.open(src) as img:
        img = img.resize(new_size, Image.LANCZOS)
        img.save(dst, optimize=True)


def main():
    parser = argparse.ArgumentParser(description='分辨率检查与可选缩放')
    parser.add_argument('--dataset', required=True, help='数据集名称')
    parser.add_argument('--apply', action='store_true', help='执行缩放（默认仅报告）')
    args = parser.parse_args()

    images_dir = PROJECT_ROOT / 'datasets' / args.dataset / 'images'
    if not images_dir.exists():
        print(f"[错误] images/ 目录不存在: {images_dir}")
        sys.exit(1)

    image_files = sorted(
        [f for f in images_dir.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED_EXT],
        key=lambda p: p.name
    )
    if not image_files:
        print(f"[警告] images/ 目录为空: {images_dir}")
        sys.exit(0)

    print(f"数据集: {args.dataset}")
    print(f"图片总数: {len(image_files)}")
    print(f"{'='*60}")

    ok_list = []
    downscale_list = []
    keep_list = []

    for img_path in image_files:
        w, h = get_image_size(img_path)
        long_side = max(w, h)
        short_side = min(w, h)
        ar = w / h

        new_size = calc_scale(w, h)
        if new_size:
            downscale_list.append((img_path, w, h, new_size))
        elif short_side < SHORT_SIDE_MIN:
            keep_list.append((img_path, w, h))
        else:
            ok_list.append((img_path, w, h))

    # 打印报告
    print(f"\n分类报告:")

    if ok_list:
        print(f"\n[OK] 长边在范围内，无需处理 ({len(ok_list)} 张):")
        for path, w, h in ok_list[:8]:
            print(f"  ✅ {path.name}  {w}x{h}")
        if len(ok_list) > 8:
            print(f"  ... 还有 {len(ok_list)-8} 张")

    if downscale_list:
        print(f"\n[↓ 需缩放] 长边 > {LONG_SIDE_UPPER}px ({len(downscale_list)} 张):")
        for path, w, h, (nw, nh) in downscale_list:
            print(f"  📏 {path.name}  {w}x{h} → {nw}x{nh}")

    if keep_list:
        print(f"\n[保留] 短边 < {SHORT_SIDE_MIN}px，不做放大 ({len(keep_list)} 张):")
        for path, w, h in keep_list:
            print(f"  🔒 {path.name}  {w}x{h}")

    # 执行缩放
    if args.apply and downscale_list:
        print(f"\n{'='*60}")
        print("开始执行缩放...")
        for src_path, w, h, new_size in downscale_list:
            # 备份原图到 raw/
            raw_dir = PROJECT_ROOT / 'datasets' / args.dataset / 'raw'
            raw_dir.mkdir(parents=True, exist_ok=True)
            backup_path = raw_dir / f"original_{src_path.stem}{src_path.suffix}"
            if not backup_path.exists():
                import shutil
                shutil.copy2(src_path, backup_path)

            # 缩放
            downscale_image(src_path, src_path, new_size)
            nw, nh = new_size
            print(f"  ✅ {src_path.name}: {w}x{h} → {nw}x{nh}")

        print(f"\n缩放完成！原图已备份到 {raw_dir}")

    elif not args.apply:
        if downscale_list:
            print(f"\n💡 如需执行缩放，运行: python scripts/check_resolution.py --dataset {args.dataset} --apply")
        else:
            print(f"\n所有图片分辨率正常，无需缩放。")


if __name__ == '__main__':
    main()
