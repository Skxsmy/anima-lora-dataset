#!/usr/bin/env python3
"""
批量并发审计脚本：调用 OpenRouter API 审计全部图片标签。

运行逻辑：
  1. 启动时扫描 images/，获得全部图片列表
  2. 读取日志（CSV）作为已处理记录；无日志则从 images_audited/ 重建
  3. --skip（默认）跳过 audited=true 且 needs_reaudit=false 的图片
  4. 并发处理缺失图片，每完成一张更新日志（合并新旧记录，覆写排序）

用法:
  python scripts/audit_batch.py --dataset cierra --mode style --trigger "@cierra-rabit"
  python scripts/audit_batch.py --dataset cierra --mode style --trigger "@cierra-rabit" --start-from 101 --limit 100
  python scripts/audit_batch.py --dataset cierra --mode style --trigger "@cierra-rabit" --no-skip
  python scripts/audit_batch.py --dataset cierra --init                    # 仅初始化日志
"""

import argparse
import base64
import json
import random
import re
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# 共享工具
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.log_utils import load_log, write_log, init_log
from lib.api_utils import load_prompt, get_api_key, resolve_prompt_path, get_api_base, get_model

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUPPORTED_EXT = {'.jpg', '.jpeg', '.png', '.webp'}
TIMEOUT = 80


# ============================================================
# 工具函数
# ============================================================

def _extract_clean_tags(content: str, reasoning: str, trigger_word: str = '') -> str:
    """从 content/reasoning 中提取干净的标签字符串。返回 '' 表示无法提取。"""

    def looks_clean(t: str) -> bool:
        t = t.strip()
        if not t:
            return False
        if not t.startswith('@') and not t[0].isascii():
            return False
        if any('\u4e00' <= c <= '\u9fff' for c in t):
            return False
        if t.count(',') < 2:
            return False
        return True

    def extract_last_tags(t: str) -> str:
        blocks = re.findall(r'```(?:text|plain|csv)?\s*\n?(.+?)```', t, re.DOTALL)
        for block in reversed(blocks):
            block = block.strip()
            if looks_clean(block):
                return block
        backtick_lines = re.findall(r'`([^`]+)`', t)
        for bt in reversed(backtick_lines):
            bt = bt.strip()
            if looks_clean(bt):
                return bt
        if trigger_word:
            idx = t.rfind(trigger_word)
            if idx >= 0:
                tail = t[idx:].split('\n')[0].strip()
                if looks_clean(tail):
                    return tail
        return ''

    if looks_clean(content):
        return content
    from_content = extract_last_tags(content)
    if from_content:
        return from_content
    if looks_clean(reasoning):
        return reasoning
    from_reasoning = extract_last_tags(reasoning)
    if from_reasoning:
        return from_reasoning
    return ''


def _build_log_entry(img_path: Path, audited_path: Path, images_dir: Path) -> dict:
    """从已有的审计输出文件构建一条日志条目"""
    stem = img_path.stem
    original_txt = images_dir / f"{stem}.txt"
    orig_cnt = 0
    if original_txt.exists():
        orig_cnt = len([t for t in original_txt.read_text('utf-8').strip().split(',')
                       if t.strip() and not t.startswith('@')])
    content = audited_path.read_text('utf-8').strip()
    new_cnt = len([t for t in content.split(',') if t.strip() and not t.startswith('@')])
    ts = datetime.fromtimestamp(audited_path.stat().st_mtime).isoformat()
    return {
        'timestamp': ts,
        'image': img_path.name,
        'original_count': orig_cnt,
        'new_count': new_cnt,
        'audited': 'true',
        'needs_reaudit': 'false',
        'error': '',
    }


def rebuild_log_from_audited(output_dir: Path, images_dir: Path) -> dict:
    """从 images_audited/ 的有效输出重建日志，返回日志条目字典。"""
    result = {}
    for audited in sorted(output_dir.glob("*.txt"), key=lambda p: p.stem):
        stem = audited.stem
        img_path = None
        for ext in ['.jpg', '.jpeg', '.png', '.webp']:
            p = images_dir / f"{stem}{ext}"
            if p.exists():
                img_path = p
                break
        if img_path is None:
            continue
        content = audited.read_text('utf-8').strip()
        if any('\u4e00' <= c <= '\u9fff' for c in content):
            continue
        if len(content) > 1000 or len(content) < 10:
            continue
        if not content.startswith('@'):
            continue
        if content.count(',') < 2:
            continue
        entry = _build_log_entry(img_path, audited, images_dir)
        result[img_path.name] = entry
    return result


def get_image_name(image_path: Path) -> str:
    """返回图片在日志中使用的名称"""
    return image_path.name


# ============================================================
# API 调用
# ============================================================

def process_one(image_path: Path, output_dir: Path, system_prompt: str,
                api_key: str, api_base: str, model: str,
                trigger_word: str = '', shuffle_tags: bool = False) -> dict:
    """处理单张图片，返回结果字典。字段 audited='true' 表示成功。"""
    txt_path = image_path.parent / f"{image_path.stem}.txt"
    img_name = get_image_name(image_path)
    result = {
        'image': img_name,
        'timestamp': datetime.now().isoformat(),
        'original_count': 0,
        'new_count': 0,
        'audited': 'false',
        'error': ''
    }

    if not txt_path.exists():
        result['error'] = 'no_txt'
        return result

    current_tags = txt_path.read_text(encoding='utf-8').strip()
    original_count = len([t for t in current_tags.split(', ') if t.strip()])
    result['original_count'] = original_count

    user_prompt = f"请审计并修正以下标签列表（仅输出逗号分隔的标签，不要额外文字）：\n\n原始标签：\n{current_tags}"

    with open(image_path, 'rb') as f:
        image_b64 = base64.b64encode(f.read()).decode()

    ext = image_path.suffix.lower()
    mime = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'webp': 'image/webp'}.get(ext, 'image/jpeg')

    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {
                'role': 'user',
                'content': [
                    {'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,{image_b64}'}},
                    {'type': 'text', 'text': user_prompt}
                ]
            }
        ],
        'temperature': 0.1,
        'max_tokens': 4096,
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

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = json.loads(resp.read().decode('utf-8'))
            msg = body.get('choices', [{}])[0].get('message', {})
            content = (msg.get('content') or '').strip()
            reasoning = (msg.get('reasoning') or '').strip()

            answer = _extract_clean_tags(content, reasoning, trigger_word=trigger_word)
            if not answer:
                result['error'] = 'no_clean_tags_in_response'
                return result

            # 随机打乱标签顺序（在注入触发词之前）
            if shuffle_tags:
                tags = [t.strip() for t in answer.split(',') if t.strip()]
                random.shuffle(tags)
                answer = ', '.join(tags)

            # 在 LLM 输出前面添加用户指定的触发词
            answer = f"{trigger_word}, {answer}"

            output_dir.mkdir(parents=True, exist_ok=True)
            out_path = output_dir / f"{image_path.stem}.txt"
            out_path.write_text(answer + '\n', encoding='utf-8')
            new_count = len([t for t in answer.split(', ') if t.strip() and t.strip() != trigger_word.strip()])
            result['new_count'] = new_count
            result['audited'] = 'true'
            return result

    except urllib.error.HTTPError as e:
        err_body = e.read().decode()[:200]
        result['error'] = f'HTTP_{e.code}: {err_body}'
    except urllib.error.URLError as e:
        result['error'] = f'NET: {e.reason}'
    except json.JSONDecodeError:
        result['error'] = 'JSON_decode_error'
    except Exception as e:
        result['error'] = str(e)[:100]

    return result


# ============================================================
# 主流程
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='批量并发审计 Tagger 标签')
    parser.add_argument('--dataset', required=True, help='数据集名称')
    parser.add_argument('--mode', required=False, default=None,
                        help='处理模式 (如 style, character)。对应 prompts/<脚本>_<mode>.md')
    parser.add_argument('--output', help='输出目录（默认: datasets/角色名/images_audited/）')
    parser.add_argument('--concurrency', type=int, default=10, help='并发数（默认: 10）')
    parser.add_argument('--start-from', type=int, default=1, help='起始编号（1-indexed）')
    parser.add_argument('--limit', type=int, default=0, help='处理张数（0=全部）')
    parser.add_argument('--skip', action='store_true', default=True,
                        help='跳过已审计的图片（默认）')
    parser.add_argument('--no-skip', dest='skip', action='store_false',
                        help='忽略日志，强制重跑')
    parser.add_argument('--trigger', required=False,
                        help='触发词，原样插入（如 @cierra-rabit）')
    parser.add_argument('--shuffle', action='store_true', default=False,
                        help='在注入触发词之前随机打乱标签顺序')
    parser.add_argument('--init', action='store_true',
                        help='仅初始化/更新日志文件后退出')
    args = parser.parse_args()

    # --init 模式不需要 --mode
    if not args.init and not args.mode:
        parser.error('非 --init 模式必须提供 --mode')

    api_key = get_api_key(PROJECT_ROOT)
    if not api_key:
        print("[错误] 未找到 API Key（请在 .env 中设置 LLM_API_KEY）")
        sys.exit(1)

    api_base = get_api_base(PROJECT_ROOT)
    model = get_model(PROJECT_ROOT)

    images_dir = PROJECT_ROOT / 'datasets' / args.dataset / 'images'
    if not images_dir.exists():
        print(f"[错误] 目录不存在: {images_dir}")
        sys.exit(1)

    # === --init 模式：仅初始化日志 ===
    if args.init:
        audited_dir = images_dir.parent / 'images_audited'
        captions_dir = images_dir.parent / 'captions'
        merged_dir = images_dir.parent / 'merged'
        log_file = PROJECT_ROOT / 'logs' / f'audit_{args.dataset}.csv'
        init_log(images_dir, audited_dir, captions_dir, log_file, merged_dir)
        return

    if not args.trigger:
        print("[错误] 非 --init 模式必须提供 --trigger")
        sys.exit(1)

    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = images_dir.parent / 'images_audited'

    prompt_path = resolve_prompt_path(PROJECT_ROOT, 'tagger_audit_prompt', args.mode)
    system_prompt = load_prompt(prompt_path)

    # 日志文件：按数据集命名
    log_file = PROJECT_ROOT / 'logs' / f'audit_{args.dataset}.csv'

    # === 1. 获取全部图片 ===
    all_images = sorted(
        [f for f in images_dir.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED_EXT],
        key=lambda p: p.name
    )
    total = len(all_images)

    # start-from / limit 过滤
    name_filter = [f for f in all_images if int(f.stem) >= args.start_from]
    if name_filter:
        start_idx = all_images.index(name_filter[0])
    else:
        start_idx = 0
    end_idx = min(total, start_idx + args.limit) if args.limit > 0 else total
    to_process = all_images[start_idx:end_idx]

    # === 2. 加载/重建日志 ===
    log_entries = load_log(log_file)
    log_source = 'existing_log'
    if not log_entries and output_dir.exists():
        log_entries = rebuild_log_from_audited(output_dir, images_dir)
        log_source = 'rebuilt_from_audited'
    if not log_entries:
        log_source = 'none'

    # === 3. 根据 skip 参数过滤 ===
    if args.skip and log_entries:
        before = len(to_process)
        to_process = [f for f in to_process
                      if get_image_name(f) not in log_entries
                      or log_entries[get_image_name(f)].get('audited', 'false') != 'true'
                      or log_entries[get_image_name(f)].get('needs_reaudit', 'false') == 'true']
        skipped_count = before - len(to_process)
    else:
        skipped_count = 0

    # === 4. 打印概览 ===
    print(f"{'='*60}")
    print(f"并发审计: {args.dataset}  (mode={args.mode})")
    log_label = {'existing_log': '已读日志', 'rebuilt_from_audited': '从输出重建', 'none': '无'}[log_source]
    print(f"日志: {log_file} ({log_label}, {len(log_entries)} 条)")
    print(f"范围: {all_images[start_idx].stem} ~ {all_images[end_idx-1].stem} ({end_idx - start_idx} 张)")
    if args.skip:
        print(f"跳过模式: 开 ({skipped_count} 张已审计)")
    else:
        print(f"跳过模式: 关 (全部重跑)")
    if to_process:
        print(f"需处理: {len(to_process)} 张 ({to_process[0].stem} ~ {to_process[-1].stem})")
    print(f"并发: {args.concurrency}, 超时: {TIMEOUT}s/张")
    print(f"输出: {output_dir}")
    print(f"Prompt: {prompt_path}")
    print(f"API: {api_base} -- {model}")
    print(f"{'='*60}\n")

    if len(to_process) == 0:
        print("全部处理完成，无需运行。")
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
    skipped = 0

    def process_and_report(img_path):
        nonlocal success, failed, skipped
        t0 = time.time()
        img_name = get_image_name(img_path)
        # 从已有记录继承，只覆写 audit 相关字段
        entry = dict(log_entries.get(img_name, {}))
        if not entry:
            entry = {'image': img_name}
        entry.update({
            'image': img_name,
            'timestamp': datetime.now().isoformat(),
            'audited': 'false',
            'needs_reaudit': 'false',
            'error': '',
        })
        # 先写入一次（保证 log_write 有全量条目）
        results[img_name] = entry
        with print_lock:
            write_log(results, log_file)

        r = process_one(img_path, output_dir, system_prompt, api_key, api_base, model, trigger_word=args.trigger, shuffle_tags=args.shuffle)
        elapsed = time.time() - t0

        if r.get('audited') == 'true':
            icon = '✅'
            success += 1
        elif r.get('error') == 'no_txt':
            icon = '⏭️'
            skipped += 1
        else:
            icon = '❌'
            failed += 1

        with print_lock:
            print(f"  {icon} {r['image']:15s} {r['original_count']:2d}→{r['new_count']:2d}  ({elapsed:.0f}s)  {r.get('error', '')}")
            r['timestamp'] = datetime.now().isoformat()
            r['needs_reaudit'] = 'false'
            results[img_name].update(r)
            write_log(results, log_file)
        return r

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = {executor.submit(process_and_report, f): f for f in to_process}
        for future in as_completed(futures):
            future.result()

    elapsed = time.time() - start_time
    avg = elapsed / max(len(to_process), 1)
    print(f"\n{'='*60}")
    print(f"完成: {success} 成功, {failed} 失败, {skipped} 跳过")
    print(f"耗时: {elapsed:.0f}s (平均 {avg:.1f}s/张)")
    print(f"日志: {log_file}")


if __name__ == '__main__':
    main()
