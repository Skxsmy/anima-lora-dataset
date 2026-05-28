#!/usr/bin/env python3
"""
PixAi 自动打标，可选 OppaiOracle 补充。
对 images/ 中的每张图片运行 tagger，输出 Danbooru 标签到 images/*.txt。

用法:
  python tag_images.py --dataset 角色名 --trigger "trigger_word"
  python tag_images.py --dataset 角色名 --trigger "trigger_word" --supplement
  python tag_images.py --dataset 角色名 --trigger "trigger_word" --force
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image
import tqdm

# 共享日志工具
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.log_utils import load_log, write_log, init_log

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUPPORTED_EXT = {'.png', '.jpg', '.jpeg', '.webp'}
MODELS_DIR = PROJECT_ROOT / 'models'

# PixAi tagger 推荐阈值
PIXAI_THRESHOLD_GENERAL = 0.30
PIXAI_THRESHOLD_CHARACTER = 0.75
PIXAI_TOP_K = 128

# OppaiOracle 默认阈值
OPPAI_THRESHOLD = 0.35


# ============================================================
# PixAi Tagger — PyTorch (safetensors) 后端
# ============================================================

class PixAiTagger:
    """EVA02 架构的 anime tagger，基于 PixAi 训练的权重"""

    MODEL_ID = '1038lab/pixai-tagger'

    def __init__(self, threshold_general: float = PIXAI_THRESHOLD_GENERAL,
                 threshold_character: float = PIXAI_THRESHOLD_CHARACTER,
                 top_k: int = PIXAI_TOP_K):
        self.threshold_general = threshold_general
        self.threshold_character = threshold_character
        self.top_k = top_k
        self._model = None
        self._tags = None
        self._tag_groups = None

    def _load_model(self):
        import safetensors.torch

        model_dir = MODELS_DIR / 'PixelAI_tagger'
        if not model_dir.exists():
            raise FileNotFoundError(f"模型目录不存在: {model_dir}")

        tags_json = model_dir / 'tags_v0.9_13k.json'
        safetensors_path = model_dir / 'pixai-tagger_v0.9.safetensors'

        with open(tags_json, 'r') as f:
            tags_data = json.load(f)

        tag_map = tags_data['tag_map']
        tag_split = tags_data['tag_split']
        gen_count = tag_split['gen_tag_count']
        char_count = tag_split['character_tag_count']

        sorted_items = sorted(tag_map.items(), key=lambda x: x[1])
        self._tags = [tag for tag, _ in sorted_items]

        self._tag_groups = []
        for i in range(len(self._tags)):
            self._tag_groups.append('general' if i < gen_count else 'character')

        num_classes = len(self._tags)
        print(f"  标签数: {num_classes} (general: {gen_count}, character: {char_count})")

        print(f"  加载 EVA02 模型...")
        try:
            import timm
            import torch
            import safetensors.torch as sf_torch

            model = timm.create_model(
                'eva02_large_patch14_448',
                pretrained=False,
                num_classes=num_classes,
            )

            state_dict = sf_torch.load_file(str(safetensors_path))
            clean_state = {}
            for k, v in state_dict.items():
                if k.startswith('0.'):
                    clean_key = k[2:]
                elif k.startswith('1.head.0.'):
                    clean_key = k.replace('1.head.0.', 'head.')
                else:
                    clean_key = k
                clean_state[clean_key] = v

            model.load_state_dict(clean_state, strict=True)
            model.eval()
            self._model = model
            self._input_size = 448
        except ImportError:
            raise ImportError("需要安装 timm: pip install timm")

    def _preprocess(self, image: Image.Image) -> np.ndarray:
        import torch
        from torchvision import transforms

        size = self._input_size
        transform = transforms.Compose([
            transforms.Resize((size, size), interpolation=transforms.InterpolationMode.LANCZOS),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.5, 0.5, 0.5],
                               std=[0.5, 0.5, 0.5]),
        ])
        return transform(image).unsqueeze(0)

    def tag(self, image: Image.Image) -> list[tuple[str, float]]:
        import torch

        if self._model is None:
            self._load_model()

        with torch.no_grad():
            input_tensor = self._preprocess(image)
            logits = self._model(input_tensor)
            probs = torch.sigmoid(logits)[0]

        results = []
        for i in range(len(self._tags)):
            score = float(probs[i])
            group = self._tag_groups[i] if self._tag_groups else 'general'
            threshold = (self.threshold_character if group == 'character'
                        else self.threshold_general)
            if score >= threshold:
                results.append((self._tags[i], score, group))

        results.sort(key=lambda x: x[1], reverse=True)
        results = results[:self.top_k]

        return [(tag, score) for tag, score, _ in results]


# ============================================================
# OppaiOracle — ONNX 后端
# ============================================================

class OppaiOracleTagger:
    """OppaiOracle ONNX tagger"""

    MODEL_ID = 'Grio43/OppaiOracle'

    def __init__(self, threshold: float = OPPAI_THRESHOLD, variant: str = 'V1.1'):
        self.threshold = threshold
        self.variant = variant
        self._session = None
        self._tags = None
        self._target_size = None

    def _load_model(self):
        model_dir = MODELS_DIR / 'OppaiOracle'
        if not model_dir.exists():
            raise FileNotFoundError(f"模型目录不存在: {model_dir}")

        model_path = model_dir / 'model.onnx'
        tags_path = model_dir / 'selected_tags.csv'

        with open(tags_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)
            self._tags = [row[2] for row in reader if len(row) >= 3]

        import onnxruntime as ort
        self._session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])

        input_meta = self._session.get_inputs()[0]
        self._target_size = input_meta.shape[2]

        print(f"  标签数: {len(self._tags)}, 输入尺寸: {self._target_size}")

    def _preprocess(self, image: Image.Image) -> tuple[np.ndarray, np.ndarray]:
        size = self._target_size or 448

        w, h = image.size
        short = min(w, h)
        left = (w - short) // 2
        top = (h - short) // 2
        image = image.crop((left, top, left + short, top + short))
        image = image.resize((size, size), Image.LANCZOS)

        img = np.array(image, dtype=np.float32)
        img = img / 127.5 - 1.0
        img = np.transpose(img, (2, 0, 1))
        img = np.expand_dims(img, axis=0)

        mask = np.ones((1, size, size), dtype=bool)

        return img.astype(np.float32), mask

    def tag(self, image: Image.Image) -> list[tuple[str, float]]:
        if self._session is None:
            self._load_model()

        input_data, padding_mask = self._preprocess(image)
        input_name = self._session.get_inputs()[0].name
        mask_name = self._session.get_inputs()[1].name
        output_name = self._session.get_outputs()[0].name

        probs = self._session.run(
            [output_name],
            {input_name: input_data, mask_name: padding_mask}
        )[0][0]

        results = [(self._tags[i], float(probs[i]))
                   for i in range(len(self._tags))
                   if probs[i] >= self.threshold]

        results.sort(key=lambda x: x[1], reverse=True)
        return results


# ============================================================
# 合并逻辑
# ============================================================

def merge_tags(primary: list[tuple[str, float]],
               supplement: list[tuple[str, float]]) -> str:
    """
    合并两个 tagger 的结果：
    - 保留 primary 所有标签
    - 从 supplement 中补充 primary 没有的标签（追加到末尾）

    注意：触发词不在此处添加。触发词由 audit_batch.py 在 LLM 审计完成后统一注入。
    """
    existing = {tag for tag, _ in primary}

    for tag, score in supplement:
        tag_normalized = tag.replace('_', ' ').lower()
        if tag_normalized not in {t.replace('_', ' ').lower() for t in existing}:
            primary.append((tag, score))
            existing.add(tag)

    tags = [tag for tag, _ in primary]

    return ', '.join(tags)


def main():
    parser = argparse.ArgumentParser(description='PixAi 自动打标 (可选 OppaiOracle 补充)')
    parser.add_argument('--dataset', required=True, help='数据集名称')
    parser.add_argument('--trigger', required=True, help='触发词')
    parser.add_argument('--threshold-general', type=float, default=PIXAI_THRESHOLD_GENERAL,
                        help=f'PixAi 通用标签阈值 (默认: {PIXAI_THRESHOLD_GENERAL})')
    parser.add_argument('--threshold-character', type=float, default=PIXAI_THRESHOLD_CHARACTER,
                        help=f'PixAi 角色标签阈值 (默认: {PIXAI_THRESHOLD_CHARACTER})')
    parser.add_argument('--top-k', type=int, default=PIXAI_TOP_K,
                        help=f'PixAi 最大标签数 (默认: {PIXAI_TOP_K})')
    parser.add_argument('--supplement', action='store_true',
                        help='同时运行 OppaiOracle 补充标注（默认仅 PixAi）')
    parser.add_argument('--force', action='store_true',
                        help='强制重新标注（忽略日志中的 tagged 状态）')
    args = parser.parse_args()

    images_dir = PROJECT_ROOT / 'datasets' / args.dataset / 'images'
    if not images_dir.exists():
        print(f"[错误] images/ 目录不存在: {images_dir}")
        sys.exit(1)

    # 日志
    audited_dir = images_dir.parent / 'images_audited'
    captions_dir = images_dir.parent / 'captions'
    merged_dir = images_dir.parent / 'merged'
    log_file = PROJECT_ROOT / 'logs' / f'audit_{args.dataset}.csv'

    # 初始化或加载日志
    log_entries = load_log(log_file)
    if not log_entries:
        log_entries = init_log(images_dir, audited_dir, captions_dir, log_file, merged_dir)

    # 扫描图片
    image_files = sorted(
        [f for f in images_dir.iterdir()
         if f.is_file() and f.suffix.lower() in SUPPORTED_EXT],
        key=lambda p: p.name
    )
    if not image_files:
        print(f"[错误] images/ 目录没有图片: {images_dir}")
        sys.exit(1)

    # 跳过逻辑：tagged=true AND needs_retag=false → 跳过
    if not args.force:
        to_process = [img_f for img_f in image_files
                      if log_entries.get(img_f.name, {}).get('tagged', 'false') != 'true'
                      or log_entries.get(img_f.name, {}).get('needs_retag', 'false') == 'true']
    else:
        to_process = list(image_files)

    if not to_process:
        print("所有图片已打标 (--force 强制重标)")
        return

    print(f"数据集: {args.dataset}")
    print(f"触发词: {args.trigger}")
    print(f"日志: {log_file} ({len(log_entries)} 条)")
    print(f"待标注: {len(to_process)}/{len(image_files)} 张")
    print(f"PixAi 阈值: general>{args.threshold_general}, character>{args.threshold_character}")
    print(f"{'='*60}")

    # === 加载主标注器: PixAi ===
    print("\n[1/2] 加载 PixAi Tagger (PyTorch)...")
    try:
        pixai = PixAiTagger(
            threshold_general=args.threshold_general,
            threshold_character=args.threshold_character,
            top_k=args.top_k,
        )
        print("  预热中...")
        with Image.open(image_files[0]) as img:
            pixai.tag(img.convert('RGB'))
        print("  ✅ PixAi 加载完成")
    except Exception as e:
        print(f"  ❌ PixAi 加载失败: {e}")
        print("  需要: pip install timm torch safetensors")
        sys.exit(1)

    # === 加载补充标注器: OppaiOracle ===
    oppai = None
    if args.supplement:
        print("\n[2/2] 加载 OppaiOracle (ONNX)...")
        try:
            oppai = OppaiOracleTagger(threshold=OPPAI_THRESHOLD)
            with Image.open(image_files[0]) as img:
                oppai.tag(img.convert('RGB'))
            print("  ✅ OppaiOracle 加载完成")
        except Exception as e:
            print(f"  ⚠️  OppaiOracle 加载失败: {e}")
            print("  将仅使用 PixAi 标注")
            oppai = None

    print(f"\n{'='*60}")
    print("开始标注...")

    # 预处理 results：预填入已标记的条目（保持日志完整）
    results: dict = {}
    for img_name, entry in log_entries.items():
        results[img_name] = dict(entry)

    success = 0
    failed = 0

    for img_path in tqdm.tqdm(to_process, desc='标注中', unit='张'):
        img_name = img_path.name

        # 继承已有记录
        entry = dict(log_entries.get(img_name, {}))
        if not entry:
            entry = {'image': img_name}
        entry.update({
            'image': img_name,
            'timestamp': datetime.now().isoformat(),
            'tagged': 'false',
            'needs_retag': 'false',
            'error': '',
        })

        try:
            with Image.open(img_path) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                primary = pixai.tag(img)

                if oppai:
                    supplement = oppai.tag(img)
                else:
                    supplement = []

                tag_text = merge_tags(primary.copy(), supplement)

            txt_path = images_dir / f"{img_path.stem}.txt"
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(tag_text + '\n')

            entry['tagged'] = 'true'
            entry['original_count'] = len(primary) + len(supplement)
            entry['error'] = ''
            success += 1

        except Exception as e:
            entry['tagged'] = 'false'
            entry['error'] = str(e)[:100]
            failed += 1
            tqdm.tqdm.write(f"\n[失败] {img_name}: {e}")

        results[img_name] = entry

    # 写入日志
    write_log(results, log_file)

    print(f"\n{'='*60}")
    if oppai:
        print(f"完成 (PixAi + OppaiOracle): {success} 成功, {failed} 失败")
    else:
        print(f"完成 (仅 PixAi): {success} 成功, {failed} 失败")
    print(f"日志: {log_file}")

    # 示例
    sample_txt = images_dir / f"{to_process[0].stem}.txt"
    if sample_txt.exists():
        with open(sample_txt, 'r') as f:
            sample = f.read().strip()
        print(f"\n示例 ({to_process[0].name}):")
        print(f"  {sample[:300]}...")


if __name__ == '__main__':
    main()
