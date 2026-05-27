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


def _read_env(project_root: Path) -> dict:
    """读取 .env 文件，返回 {KEY: value} 字典。"""
    env = {}
    env_path = project_root / '.env'
    if not env_path.exists():
        return env
    for line in env_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, val = line.partition('=')
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if val:
            env[key] = val
    return env


def get_api_key(project_root: Path) -> str:
    """获取 API Key。
    优先级：环境变量 LLM_API_KEY > .env 文件中的 LLM_API_KEY
    """
    key = os.environ.get('LLM_API_KEY', '')
    if not key:
        env = _read_env(project_root)
        key = env.get('LLM_API_KEY', '')
    return key


def get_api_base(project_root: Path) -> str:
    """获取 API Base URL（不含 /chat/completions 后缀）。
    优先级：环境变量 LLM_API_BASE > .env 文件 > 默认 OpenRouter
    """
    base = os.environ.get('LLM_API_BASE', '')
    if not base:
        env = _read_env(project_root)
        base = env.get('LLM_API_BASE', '')
    if not base:
        base = 'https://openrouter.ai/api/v1'
    return base.rstrip('/')


def get_model(project_root: Path) -> str:
    """获取模型名称。
    优先级：环境变量 LLM_MODEL > .env 文件 > 默认 qwen/qwen3.6-35b-a3b
    """
    model = os.environ.get('LLM_MODEL', '')
    if not model:
        env = _read_env(project_root)
        model = env.get('LLM_MODEL', '')
    if not model:
        model = 'qwen/qwen3.6-35b-a3b'
    return model
