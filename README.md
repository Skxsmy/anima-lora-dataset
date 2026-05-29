# Anima LoRA 数据集准备工具

把原始图片变成 LoRA 训练数据。支持画风 LoRA 和角色 LoRA，通过切换模式适配不同的训练目标。

## 安装

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

下载 PixAi Tagger 模型（必须）：

```bash
pip install huggingface-hub
huggingface-cli download 1038lab/pixai-tagger \
    pixai-tagger_v0.9.safetensors tags_v0.9_13k.json \
    --local-dir models/PixelAI_tagger/
```

配置 API：

```bash
cp .env.example .env
```

编辑 `.env`，至少填 `LLM_API_KEY`。如果你用 OpenAI 或其他兼容接口，顺便改 `LLM_API_BASE` 和 `LLM_MODEL`。

| 变量 | 必填 | 默认值 |
|------|------|--------|
| `LLM_API_KEY` | 是 | |
| `LLM_API_BASE` | 否 | `https://openrouter.ai/api/v1` |
| `LLM_MODEL` | 否 | `qwen/qwen3.6-35b-a3b` |

## 快速开始

六步走完。以画风 LoRA 为例，触发词是 `cierra-rabit`：

```bash
# 1. 图片丢进 datasets/cierra/，脚本自动编号
python scripts/process_raw.py --dataset cierra

# 2. 检查分辨率，超大图等比缩到 1024px
python scripts/check_resolution.py --dataset cierra
python scripts/check_resolution.py --dataset cierra --apply

# 3. PixAi 自动打标
python scripts/tag_images.py --dataset cierra --trigger "cierra-rabit"

# 4. LLM 审查标签，删掉画师名、角色名、质量词等
python scripts/audit_batch.py --dataset cierra --mode style --trigger "cierra-rabit"

# 5. 生成英文 caption（至少两句）
python scripts/caption.py --dataset cierra --mode style

# 6. 合成最终训练数据
python scripts/merge_tags_captions.py --dataset cierra
```

输出的 `datasets/cierra/merged/` 目录可以直接喂给训练脚本。

### 角色 LoRA 示例

角色 LoRA 的触发词通常不含 `@`，如 `alice_cierra`：

```bash
python scripts/audit_batch.py --dataset "alice(cierra-rabit)" --mode character --trigger "alice_cierra" --shuffle
```

`--trigger` 传入什么就原样写入文件，不做任何自动加工（不会自动加 `@`）。

## 每一步做了什么

### 1. process_raw.py

把原始图片编号复制到 `images/`。原始文件备份到 `raw/`。支持 jpg、png、webp。

### 2. check_resolution.py

扫描 `images/` 目录。长边超过 1536px 的等比缩到 1024px。短边小于 512px 的提醒你删除。先不加 `--apply` 看报告，确认后再执行。

### 3. tag_images.py

用 PixAi Tagger 识别每张图的内容，生成 Danbooru 格式标签。每个 `.jpg` 旁边生成同名 `.txt`。标签不包含触发词。

### 4. audit_batch.py

把 PixAi 标签发给 LLM 审查。LLM 会看图，删掉画师名、角色名、作品名、质量词、水印等不该出现的东西，只留下构图、动作、场景、服装大类。处理结果写入 `images_audited/`。

需要传 `--mode` 指定处理策略。需要传 `--trigger` 指定触发词（原样写入，不自动加 `@`）。

可选参数：

| 参数 | 作用 |
|------|------|
| `--shuffle` | 注入触发词前随机打乱所有标签顺序 |
| `--no-skip` | 忽略日志，强制全部重跑 |
| `--start-from N` | 从第 N 张开始 |
| `--limit N` | 只处理 N 张 |
| `--concurrency N` | 并发数（默认 10） |

### 5. caption.py

给每张图生成英文自然语言描述，至少两句。描述画面中实际看到的内容，不写画风词、不写剧情、不写 "The image shows" 这类引导句。

同样需要 `--mode`。

### 6. merge_tags_captions.py

把审查后的标签和 caption 合并成一行，复制图片到 `merged/`。格式：

```
@cierra-rabit, 2girls, sitting, ...
Two blonde girls sit together against a white background.
```

## 处理模式

`audit_batch.py` 和 `caption.py` 通过 `--mode` 切换策略。不同模式对应 `prompts/` 下不同的 prompt 文件。

内置两种模式：

| 模式 | 用途 | 区别 |
|------|------|------|
| `style` | 画风 LoRA | 删角色名和画师名，保留构图场景光照 |
| `character` | 角色 LoRA | 保留瞳色发色配饰等角色特征，每张图按实际发型服装写 |

### 自定义模式

在 `prompts/` 下创建两个文件：

```
prompts/tagger_audit_prompt_<你的模式名>.md
prompts/caption_prompt_<你的模式名>.md
```

然后用 `--mode 你的模式名` 即可。文件不存在会报错退出。

Prompt 文件的输出要求：

- 审计 prompt：LLM 必须输出纯逗号分隔标签，不加触发词，不加解释
- Caption prompt：LLM 必须输出纯英文句子，不加格式标记

参考 `prompts/` 下已有的四个文件来写。

## 日志

每个数据集有一份日志 `logs/audit_<数据集名>.csv`，记录了每张图在每个步骤的处理状态。想重跑某张图，在 CSV 里把对应的 `needs_reaudit` 或 `needs_recaption` 改成 `true` 再跑脚本，脚本只处理标记了的图片。

初始化或同步日志：

```bash
python scripts/audit_batch.py --dataset 数据集名 --init
```
