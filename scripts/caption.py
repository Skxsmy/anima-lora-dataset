#!/usr/bin/env python3
"""
自然语言 Caption 生成。
读取已审计的标签和图片，生成自然语言描述存入 captions/ 子目录。

运行逻辑:
  1. 读取日志 (audit_<dataset>.csv)
  2. --skip（默认）跳过 captioned=true 且 needs_recaption=false 的图片
  3. 并发调用 OpenRouter API 生成自然语言描述
  4. 输出写入 datasets/<角色名>/captions/

用法:
  python scripts/caption.py --dataset cierra --mode style
  python scripts/caption.py --dataset cierra --mode style --start-from 50 --limit 10
  python scripts/caption.py --dataset cierra --mode style --no-skip
"""

import argparse
import base64
import json
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# 共享日志工具
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.log_utils import load_log, write_log
from lib.api_utils import load_prompt, get_api_key, resolve_prompt_path, get_api_base, get_model

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUPPORTED_EXT = {'.jpg', '.jpeg', '.png', '.webp'}
TIMEOUT = 80




def generate_caption(image_path: Path, tags_text: str, api_key: str, api_base: str, model: str, system_prompt: str) -> str:
    """调用 OpenRouter API 生成自然语言 caption"""
    with open(image_path, 'rb') as f:
        image_b64 = base64.b64encode(f.read()).decode()

    ext = image_path.suffix.lower()
    mime = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'webp': 'image/webp'}.get(ext, 'image/jpeg')

    user_content = f"Tags: {tags_text}\n\nGenerate a natural language caption for this image."

    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {
                'role': 'user',
                'content': [
                    {'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,{image_b64}'}},
                    {'type': 'text', 'text': user_content}
                ]
            }
        ],
        'temperature': 0.3,
        'max_tokens': 2048,
    }

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        api_base + '/chat/completions', data=data,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://github.com/hermes-agent',
        },
        method='POST'
    )

    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        body = json.loads(resp.read().decode('utf-8'))
        msg = body.get('choices', [{}])[0].get('message', {})
        caption = (msg.get('content') or '').strip()

        if not caption or len(caption) < 10:
            return ''

        return caption


# ============================================================
# 主流程
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='自然语言 Caption 生成')
    parser.add_argument('--dataset', required=True, help='数据集名称')
    parser.add_argument('--mode', required=True,
                        help='处理模式 (如 style, character)。对应 prompts/<脚本>_<mode>.md')
    parser.add_argument('--concurrency', type=int, default=10, help='并发数')
    parser.add_argument('--start-from', type=int, default=1, help='起始编号')
    parser.add_argument('--limit', type=int, default=0, help='处理张数（0=全部）')
    parser.add_argument('--skip', action='store_true', default=True,
                        help='跳过已有 caption 的图片（默认）')
    parser.add_argument('--no-skip', dest='skip', action='store_false',
                        help='忽略已有 caption，全部重跑')
    args = parser.parse_args()

    api_key = get_api_key(PROJECT_ROOT)
    if not api_key:
        print("[错误] 未找到 API Key（请在 .env 中设置 LLM_API_KEY）")
        sys.exit(1)

    api_base = get_api_base(PROJECT_ROOT)
    model = get_model(PROJECT_ROOT)

    prompt_path = resolve_prompt_path(PROJECT_ROOT, 'caption_prompt', args.mode)
    system_prompt = load_prompt(prompt_path)

    images_dir = PROJECT_ROOT / 'datasets' / args.dataset / 'images'
    audited_dir = images_dir.parent / 'images_audited'
    captions_dir = images_dir.parent / 'captions'
    log_file = PROJECT_ROOT / 'logs' / f'audit_{args.dataset}.csv'

    if not images_dir.exists():
        print(f"[错误] 图片目录不存在: {images_dir}")
        sys.exit(1)
    if not audited_dir.exists():
        print(f"[错误] 审计输出目录不存在: {audited_dir}\n请先运行 audit_batch.py")
        sys.exit(1)

    captions_dir.mkdir(parents=True, exist_ok=True)

    # === 1. 获取全部图片 ===
    all_images = sorted(
        [f for f in images_dir.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED_EXT],
        key=lambda p: p.name
    )
    total = len(all_images)

    # start-from / limit
    name_filter = [f for f in all_images if int(f.stem) >= args.start_from]
    start_idx = all_images.index(name_filter[0]) if name_filter else 0
    end_idx = min(total, start_idx + args.limit) if args.limit > 0 else total
    to_process = all_images[start_idx:end_idx]

    # === 2. 加载日志 ===
    log_entries = load_log(log_file)

    # === 3. 过滤 ===
    if args.skip and log_entries:
        before = len(to_process)
        to_process = [f for f in to_process
                      if log_entries.get(f.name, {}).get('captioned', 'false') != 'true'
                      or log_entries.get(f.name, {}).get('needs_recaption', 'false') == 'true']
        skipped = before - len(to_process)
    else:
        skipped = 0

    # === 4. 概览 ===
    print(f"{'='*60}")
    print(f"Caption 生成: {args.dataset}  (mode={args.mode})")
    print(f"日志: {log_file} ({'已读' if log_entries else '无'})")
    print(f"范围: {all_images[start_idx].stem} ~ {all_images[end_idx-1].stem} ({end_idx-start_idx} 张)")
    if args.skip:
        print(f"跳过模式: 开 ({skipped} 张已有 caption)")
    else:
        print(f"跳过模式: 关")
    if to_process:
        print(f"需处理: {len(to_process)} 张")
    print(f"并发: {args.concurrency}, 超时: {TIMEOUT}s/张")
    print(f"Prompt: {prompt_path}")
    print(f"API: {api_base} -- {model}")
    print(f"输出: {captions_dir}")
    print(f"{'='*60}\n")

    if not to_process:
        print("全部已有 caption，无需运行。")
        return

    # === 5. 并发处理 ===
    print_lock = __import__('threading').Lock()
    start_time = time.time()
    results: dict[str, dict] = {}

    # 预填入所有日志条目（保持日志完整，避免 write_log 覆写时丢失数据）
    for img_name, entry in log_entries.items():
        results[img_name] = dict(entry)

    success = 0
    failed = 0

    def process_and_caption(img_path):
        nonlocal success, failed
        t0 = time.time()
        img_name = img_path.name
        # 从已有记录继承，只覆写 caption 相关字段
        entry = dict(log_entries.get(img_name, {}))
        if not entry:
            entry = {'image': img_name, 'original_count': 0, 'new_count': 0}
        entry.update({
            'image': img_name,
            'timestamp': datetime.now().isoformat(),
            'captioned': 'false',
            'needs_recaption': 'false',
            'caption_length': 0,
            'error': '',
        })
        results[img_name] = entry
        with print_lock:
            write_log(results, log_file)

        try:
            audited_txt = audited_dir / f"{img_path.stem}.txt"
            if not audited_txt.exists():
                raise FileNotFoundError(f"审计标签不存在: {audited_txt}")
            tags = audited_txt.read_text(encoding='utf-8').strip()

            caption = generate_caption(img_path, tags, api_key, api_base, model, system_prompt)

            if not caption:
                raise ValueError("返回为空")

            out_path = captions_dir / f"{img_path.stem}.txt"
            out_path.write_text(caption + '\n', encoding='utf-8')

            entry['captioned'] = 'true'
            entry['error'] = ''
            elapsed = time.time() - t0
            word_count = len(caption.split())
            icon = '✅'

        except Exception as e:
            entry['captioned'] = 'false'
            entry['error'] = str(e)[:100]
            elapsed = time.time() - t0
            word_count = 0
            icon = '❌'

        with print_lock:
            wc_str = f"{word_count}w" if word_count else ""
            print(f"  {icon} {img_name:15s} {wc_str:>6}  ({elapsed:.0f}s)  {entry['error']}")
            entry['timestamp'] = datetime.now().isoformat()
            entry['needs_recaption'] = 'false'
            entry['caption_length'] = word_count
            results[img_name] = entry
            write_log(results, log_file)

        if entry['captioned'] == 'true':
            success += 1
        else:
            failed += 1

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = {executor.submit(process_and_caption, f): f for f in to_process}
        for future in as_completed(futures):
            future.result()

    elapsed = time.time() - start_time
    avg = elapsed / max(len(to_process), 1)
    print(f"\n{'='*60}")
    print(f"完成: {success} 成功, {failed} 失败")
    print(f"耗时: {elapsed:.0f}s (平均 {avg:.1f}s/张)")
    print(f"日志: {log_file}")


if __name__ == '__main__':
    main()
