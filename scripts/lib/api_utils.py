#!/usr/bin/env python3
"""
共享 API 工具 — audit_batch.py 和 caption.py 共用。
"""

import os
import sys
from pathlib import Path


def load_prompt(path: Path) -> str:
    """从文件读取系统提示词"""
    return path.read_text(encoding='utf-8').strip()


def resolve_prompt_path(project_root: Path, base_name: str, mode: str) -> Path:
    """根据 mode 解析 prompt 文件路径。

    查找 prompts/<base_name>_<mode>.md。
    文件不存在时打印清晰错误并退出，决不回退到其他 prompt。
    """
    path = project_root / 'prompts' / f'{base_name}_{mode}.md'
    if not path.exists():
        print(f"[错误] 找不到 mode='{mode}' 对应的 prompt 文件: {path}")
        print(f"[提示] 请创建该文件，或确认 mode 名称拼写正确。")
        print(f"[提示] 可用的 prompt 文件:")
        prompts_dir = project_root / 'prompts'
        if prompts_dir.exists():
            for f in sorted(prompts_dir.glob('*.md')):
                print(f"  - {f.name}")
        sys.exit(1)
    return path


def get_api_key(project_root: Path) -> str:
    """获取 OpenRouter API Key。
    优先级：环境变量 OPENROUTER_API_KEY > 项目 .env 文件
    """
    key = os.environ.get('OPENROUTER_API_KEY', '')
    if not key:
        env_path = project_root / '.env'
        if env_path.exists():
            for line in env_path.read_text(encoding='utf-8').splitlines():
                line = line.strip()
                if line.startswith('OPENROUTER_API_KEY='):
                    val = line.split('=', 1)[1].strip().strip('"').strip("'")
                    if val and val != '请在此填入你的API Key':
                        key = val
    return key
