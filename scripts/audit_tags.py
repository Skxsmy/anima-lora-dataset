#!/usr/bin/env python3
"""
多模态 LLM 审计与修正 PixAi Tagger 输出。
逐张读取图片 + 当前标签，发送给外部多模态 LLM 审计后写回。

用法:
  python scripts/audit_tags.py --dataset cierra               # 处理全部（自动读取 .env）
  python scripts/audit_tags.py --dataset cierra --image 000001  # 只处理单张（用于多并发）
  python scripts/audit_tags.py --dataset cierra --dry-run      # 仅展示不执行
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUPPORTED_EXT = {'.jpg', '.jpeg', '.png', '.webp'}
PROMPT_PATH = PROJECT_ROOT / 'prompts' / 'tagger_audit_prompt.md'
LOG_FILE = PROJECT_ROOT / 'logs' / 'audit_log.csv'
TIMEOUT = 80  # 秒

# API 配置
API_URL = 'https://openrouter.ai/api/v1/chat/completions'
MODEL = 'qwen/qwen3.6-35b-a3b'


def load_prompt() -> str:
    if not PROMPT_PATH.exists():
        print(f"[错误] 提示词文件不存在: {PROMPT_PATH}")
        sys.exit(1)
    return PROMPT_PATH.read_text(encoding='utf-8').strip()


def encode_image(image_path: Path) -> str:
    with open(image_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


def image_mime(path: Path) -> str:
    ext = path.suffix.lower()
    return {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'webp': 'image/webp'}.get(ext, 'image/jpeg')


def call_llm(system_prompt: str, user_prompt: str, image_b64: str, mime: str, api_key: str) -> str | None:
    """
    调用 OpenRouter API，发送图片 + 当前标签给 LLM，返回修正后标签。
    超时 80s，失败返回 None。
    """
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
        'HTTP-Referer': 'https://github.com/hermes-agent',
    }

    payload = {
        'model': MODEL,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'image_url',
                        'image_url': {'url': f'data:{mime};base64,{image_b64}'}
                    },
                    {
                        'type': 'text',
                        'text': user_prompt
                    }
                ]
            }
        ],
        'temperature': 0.1,  # 低温度以保证确定性
        'max_tokens': 4096,  # 推理模型需要更多的 token
    }

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(API_URL, data=data, headers=headers, method='POST')

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            content = result.get('choices', [{}])[0].get('message', {}).get('content')
            if not content:
                # 推理模型的 content 可能在 reasoning 字段
                reasoning = result.get('choices', [{}])[0].get('message', {}).get('reasoning')
                if reasoning:
                    content = reasoning
                else:
                    err = result.get('error', {}).get('message', 'unknown')
                    print(f"\n  [API返回异常] {err}")
                    return None
            content = content.strip()
            # 清理可能的 markdown 包裹
            if content.startswith('```'):
                lines = content.split('\n')
                content = '\n'.join(lines[1:-1]).strip()
            return content
    except urllib.error.HTTPError as e:
        print(f"  [HTTP错误] {e.code}: {e.read().decode()[:200]}")
    except urllib.error.URLError as e:
        print(f"  [网络错误] {e.reason}")
    except json.JSONDecodeError as e:
        print(f"  [JSON解析错误] {e}")
    except Exception as e:
        print(f"  [未知错误] {e}")

    return None


def log_write(entries: list[list]):
    """写入 CSV 日志（追加模式）"""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    header = not LOG_FILE.exists()
    with open(LOG_FILE, 'a', encoding='utf-8', newline='') as f:
        if header:
            f.write('timestamp,image,original_count,new_count,status,error\n')
        for row in entries:
            f.write(','.join(str(v) for v in row) + '\n')


def main():
    parser = argparse.ArgumentParser(description='多模态 LLM 审计修正 Tagger 标签')
    parser.add_argument('--dataset', required=True, help='数据集名称')
    parser.add_argument('--api-key', help='OpenRouter API Key（也可设环境变量 OPENROUTER_API_KEY）')
    parser.add_argument('--dry-run', action='store_true', help='仅展示不执行')
    parser.add_argument('--output', help='输出目录（默认: datasets/角色名/images_audited/）')
    parser.add_argument('--image', help='单图模式：指定图片文件名（不含路径，如 000001）')
    parser.add_argument('--start-from', type=int, default=1, help='从第几张开始（1-indexed, 默认 1）')
    parser.add_argument('--limit', type=int, default=0, help='最多处理几张（0 = 全部）')
    args = parser.parse_args()

    # API Key
    api_key = args.api_key or os.environ.get('OPENROUTER_API_KEY', '')
    # 尝试从 .env 文件读取
    if not api_key:
        env_path = PROJECT_ROOT / '.env'
        if env_path.exists():
            for line in env_path.read_text(encoding='utf-8').splitlines():
                line = line.strip()
                if line.startswith('OPENROUTER_API_KEY='):
                    val = line.split('=', 1)[1].strip().strip('"').strip("'")
                    if val and val != '请在此填入你的API Key':
                        api_key = val
    if not api_key and not args.dry_run:
        print("[错误] 未提供 API Key。请通过 --api-key 参数或 OPENROUTER_API_KEY 环境变量设置。")
        sys.exit(1)

    # 数据集路径
    images_dir = PROJECT_ROOT / 'datasets' / args.dataset / 'images'
    out_dir = Path(args.output) if args.output else (images_dir.parent / 'images_audited')
    if not images_dir.exists():
        print(f"[错误] images 目录不存在: {images_dir}")
        sys.exit(1)

    # 按编号排序
    image_files = sorted(
        [f for f in images_dir.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED_EXT],
        key=lambda p: p.name
    )
    if not image_files:
        print(f"[错误] images 中没有图片: {images_dir}")
        sys.exit(1)

    total = len(image_files)
    
    # 单图模式
    if args.image:
        matched = [f for f in image_files if f.stem == args.image or f.name == args.image]
        if not matched:
            print(f"[错误] 未找到图片: {args.image}")
            sys.exit(1)
        to_process = matched
        img_idx = 1
        img_total = 1
        print(f"单图模式: {to_process[0].name}")
    else:
        start = max(0, args.start_from - 1)
        end = min(total, start + args.limit) if args.limit > 0 else total
        to_process = image_files[start:end]
        img_idx = start + 1
        img_total = end
        print(f"批量模式: {len(to_process)} 张 (第 {start+1} ~ {end} 张)")

    # 加载提示词
    system_prompt = load_prompt()
    if args.dry_run:
        print(f"[提示词预览] 长度: {len(system_prompt)} 字符")
        print("="*60)
        print(system_prompt[:500])
        print("..." if len(system_prompt) > 500 else "")
        print("="*60)

    total = len(image_files)
    print(f"数据集: {args.dataset}")
    print(f"图片总数: {total}")
    print(f"本次处理: {len(to_process)} 张")
    print(f"API: {MODEL} @ {API_URL}")
    print(f"超时: {TIMEOUT}s")
    print(f"输出: {out_dir}")
    print(f"日志: {LOG_FILE}")
    if args.dry_run:
        print("\n[dry-run 模式] 仅展示，不执行 API 调用")
        sys.exit(0)
    print("="*60)

    # 开始处理
    success = 0
    failed = 0
    skipped = 0
    log_entries = []
    start_time = time.time()

    for idx, img_path in enumerate(to_process, start=img_idx):
        txt_path = images_dir / f"{img_path.stem}.txt"
        if not txt_path.exists():
            print(f"  [{idx:3d}] ⏭️  {img_path.name} — 无 .txt 文件，跳过")
            log_entries.append([datetime.now().isoformat(), img_path.name, 0, 0, 'skipped', 'no_txt'])
            skipped += 1
            continue

        # 读取当前标签
        current_tags = txt_path.read_text(encoding='utf-8').strip()
        original_count = len([t for t in current_tags.split(', ') if t.strip()])

        # 构造 user prompt
        user_prompt = f"请审计并修正以下标签列表（仅输出逗号分隔的标签，不要额外文字）：\n\n原始标签：\n{current_tags}"

        if not args.dry_run:
            print(f"  [{idx:3d}/{img_total}] 📝 {img_path.name} ({original_count} tags) → 请求中...", end=' ', flush=True)

            image_b64 = encode_image(img_path)
            mime = image_mime(img_path)

            result = call_llm(system_prompt, user_prompt, image_b64, mime, api_key)

            if result:
                new_count = len([t for t in result.split(', ') if t.strip() and not t.startswith('@')])
                # 确保触发词在最前面
                if not result.startswith('@'):
                    result = f"@cierra-rabit, {result}"
                # 写入输出目录
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir / f"{img_path.stem}.txt"
                out_path.write_text(result + '\n', encoding='utf-8')
                success += 1
                elapsed = time.time() - start_time
                print(f"✅ {new_count} tags ({elapsed:.0f}s)")
                log_entries.append([datetime.now().isoformat(), img_path.name, original_count, new_count, 'success', ''])
            else:
                failed += 1
                print(f"❌ 失败")
                log_entries.append([datetime.now().isoformat(), img_path.name, original_count, 0, 'failed', 'API_error'])

            # 每处理完 10 张，写一次日志
            if len(log_entries) >= 10:
                log_write(log_entries)
                log_entries = []

            # 避免 API 限流（极短间隔）
            time.sleep(0.5)

    # 写入剩余日志
    if log_entries:
        log_write(log_entries)

    # 汇总
    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"处理完成: {success} 成功, {failed} 失败, {skipped} 跳过")
    print(f"耗时: {elapsed:.0f}s")
    print(f"日志: {LOG_FILE}")


if __name__ == '__main__':
    main()
