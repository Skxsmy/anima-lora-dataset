# Anima LoRA 数据集准备管道

画师画风 LoRA 的端到端数据集准备工具链。工具层与数据层分离，支持多个角色/画风数据集。

## 项目结构

```
anima-lora-dataset/
├── scripts/                         # 工具脚本
│   ├── process_raw.py               # 1. 图片摄入与编号
│   ├── tag_images.py                # 2. PixAi 自动打标
│   ├── audit_batch.py               # 3. LLM 审计清理标签
│   ├── caption.py                   # 4. 句子 Caption 生成
│   ├── merge_tags_captions.py       # 5. 合成 tags + caption → merged/
│   └── lib/
│       └── log_utils.py             # 共享日志工具（所有脚本共用）
├── prompts/                         # LLM prompt 模板
│   ├── tagger_audit_prompt.md       # 标签审计 prompt
│   └── caption_prompt.md            # 句子 Caption 生成 prompt
├── datasets/                        # 数据层：每个画风一个子目录
│   └── <dataset>/
│       ├── raw/                     # 原始待处理图片（第一步用）
│       ├── images/                  # 训练图片 + PixAi 输出的 .txt 标签
│       ├── images_audited/          # LLM 审计清理后的标签
│       ├── captions/                # 生成的句子 caption
│       └── merged/                  # 合成后的训练数据（tags + caption + 图片）
├── logs/                            # 统一日志（所有处理阶段共用）
│   └── audit_<dataset>.csv
├── venv/                            # Python 虚拟环境
└── requirements.txt                 # 依赖
```

## 工作流

所有脚本共用一份日志文件 `logs/audit_<dataset>.csv`，每列对应一个处理阶段：

| 列 | 写入者 | 作用 |
|---|---|---|
| `original_count` / `new_count` | audit_batch | 标签数统计 |
| `needs_reaudit` | audit_batch | 标记需要重新审计的图片 |
| `caption_length` | caption | 生成的 caption 词数 |
| `needs_caption` / `needs_recaption` | caption | 标记需要生成/重新生成 caption |
| `merged` | merge_tags_captions | 标记是否已合成 |

每个脚本只修改自己的列，不破坏其他列。

### 0. 创建数据集 & 环境准备

每个画风格一个数据集目录。运行 `process_raw.py` 会自动创建目录结构：

```bash
# 1. 创建新数据集（自动生成 datasets/<dataset>/raw/ + images/）
python scripts/process_raw.py --dataset <dataset>

# 2. 按提示将原始图片放入 raw/，然后再次运行
python scripts/process_raw.py --dataset <dataset>

# 3. 激活环境
source venv/bin/activate
pip install -r requirements.txt
```

执行后目录结构：

```
datasets/
├── <dataset>/             # 画风数据集
│   ├── raw/               # ← 放你的原始图片
│   ├── images/            # ← 自动生成（编号后的图片）
│   ├── images_audited/    # ← 自动生成
│   ├── captions/          # ← 自动生成
│   └── merged/            # ← 自动生成
└── ...
```

### 1. 图片摄入

将原始图片放入 `datasets/<dataset>/raw/`，然后运行：

```bash
python scripts/process_raw.py --dataset <dataset>
```

自动验证图片完整性，按 `000001.jpg` 格式统一编号复制到 `images/`，并生成 `mapping.csv`。

### 2. PixAi 自动打标

```bash
python scripts/tag_images.py --dataset <dataset> --trigger "<trigger>"
```

对 `images/` 中的每张图片调用 PixAi Tagger 生成 Danbooru 标签，写入 `images/*.txt`。

参数：
- `--trigger`：画风触发词（如 `cierra-rabit`），自动加 `@` 前缀

### 3. LLM 审计清理标签

```bash
# 首次运行（处理全部）
python scripts/audit_batch.py --dataset <dataset>

# 增量：只跑指定范围
python scripts/audit_batch.py --dataset <dataset> --start-from 50 --limit 10

# 强制重跑特定图片（先标记 needs_reaudit=true，再运行）
python scripts/audit_batch.py --dataset <dataset>
```

清理规则：
- 修正人物数量标签（`1girl`/`solo`/`2girls` 等）
- 删除真实画师名、角色名、作品名
- 删除质量词、平台残留、水印签名
- 删除过细的身体部位和服装零件
- 删除明显错误的标签
- 保留主体、人数、构图、动作、场景、明显光照

输出写入 `images_audited/*.txt`。

### 4. 句子 Caption 生成

```bash
# 生成全部
python scripts/caption.py --dataset <dataset>

# 只测几张
python scripts/caption.py --dataset <dataset> --start-from 1 --limit 3

# 重跑特定图片（先标记 needs_recaption=true，再运行）
python scripts/caption.py --dataset <dataset>
```

生成规则见 `prompts/caption_prompt.md` 和 `# 句子 Caption 编写原则：画师画风 LoRA 版本.md`。

输出写入 `captions/*.txt`。

### 5. 合成训练数据

```bash
python scripts/merge_tags_captions.py --dataset <dataset>
```

将审计后标签和句子 caption 合并为一行，同时复制图片到 `merged/`。

合并格式：

```
@trigger, tag1, tag2, tag3. Natural language caption sentence.
```

示例：

```
@cierra-rabit, 2girls, cowboy_shot, sitting, looking_at_another, blonde_hair, long_hair. Two blonde girls sit together against a white background, with the girl on the left looking forward and the girl on the right looking at her with a smile.
```

输出到 `merged/`：每张图一个 `.txt` + 图片副本，可直接用于训练。

## 日志管理

日志文件 `logs/audit_<dataset>.csv` 记录所有处理阶段的进度。

```bash
# 查看处理进度
python3 -c "
import csv
from pathlib import Path
log = Path('logs/audit_<dataset>.csv')
reader = csv.DictReader(log.read_text().splitlines())
rows = list(reader)
print(f'总数: {len(rows)}')
print(f'需审计: {sum(1 for r in rows if r[\"needs_reaudit\"]==\"true\")}')
print(f'需 caption: {sum(1 for r in rows if r[\"needs_caption\"]==\"true\")}')
print(f'已合并: {sum(1 for r in rows if r[\"merged\"]==\"true\")}')
"
```

## 参考文档

- `Tagger 输出后处理原则：画师画风 LoRA.md` — 标签后处理规范
- `# 句子 Caption 编写原则：画师画风 LoRA 版本.md` — 句子 Caption 规范
