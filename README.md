# Anima LoRA 数据集准备管道

画师画风 LoRA 的训练数据准备工具。从原始图片到可直接训练的 `merged/` 目录，一条龙。

## 一次完整的工作流长什么样

以 cierra 画师为例（cierra-rabit 是自定义触发词）：

```bash
# 1. 把图片丢进去就行
python scripts/process_raw.py --dataset cierra

# 2. 检查分辨率，超大的等比缩到 1024px
python scripts/check_resolution.py --dataset cierra
python scripts/check_resolution.py --dataset cierra --apply   # 确认后执行缩放

# 3. 自动打标（PixAi 识别画面内容，生成 Danbooru 标签）
python scripts/tag_images.py --dataset cierra --trigger "cierra-rabit"

# 4. LLM 清理标签（去掉画师名、角色名、质量词、过细零件等）
python scripts/audit_batch.py --dataset cierra --mode style --trigger cierra-rabit

# 5. 生成自然语言描述（给每张图写至少两句英文 caption）
python scripts/caption.py --dataset cierra --mode style

# 6. 合成最终训练数据
python scripts/merge_tags_captions.py --dataset cierra
```

## 每步在做什么

### 1. 图片摄入 — `process_raw.py`

把原始图片丢进 `datasets/<画风>/` 目录里，脚本会自动把它们挪到 `raw/`、编号复制到 `images/`。

```
datasets/<画风>/           ← 你把图片丢这
├── raw/                   ← 原始文件存档（自动创建）
└── images/                ← 编号后的训练图片（自动创建）
    ├── 000001.jpg
    ├── 000002.jpg
    └── ...
```

### 2. 分辨率检查 — `check_resolution.py`

扫描 `images/` 目录，报告每张图的分辨率。长边超过 1536px 的会建议缩放到 1024px。先用 `--apply` 看一眼报告，确认后再加 `--apply` 执行。

```
[↓ 需缩放] 长边 > 1536px (3 张):
  📏 000007.png  2048x1536 → 1024x768
  📏 000012.png  2560x1440 → 1024x576
  📏 000023.png  1920x1920 → 1024x1024
```

### 3. PixAi 打标 — `tag_images.py`

对每张图跑 PixAi Tagger，识别画面中的元素、动作、场景，输出 Danbooru 格式标签。每个 `.jpg` 旁边生成一个同名的 `.txt`。

```
@cierra-rabit, 1girl, solo, upper_body, looking_at_viewer, bedroom, sitting, window_light
```

### 4. LLM 审计 — `audit_batch.py`

自动标签里有很多不该出现在画风 LoRA 里的东西。LLM 会检查每张图的实际画面，把下面这些清理掉：

- 真实画师名（让自定义触发词专心绑定画风）
- 具体角色名（不要让画风绑定到特定人物）
- 作品/系列名
- 质量词（masterpiece、best quality 等）
- 平台水印、签名、文字残留
- 过细的服装零件和身体部位
- 明显识别错误的标签

留下的：主体、人数、构图、动作、场景、明显的服装大类、光照。

### 5. 句子 Caption — `caption.py`

为每张图生成至少两句自然语言英文描述，描述画面中实际看到的内容。不写 "The image shows" 这类引导语，不谈剧情，不堆风格词。

```
Two blonde girls sit together against a white background. The girl on the left has blue eyes and wears a white dress with a red bow and frills, looking forward.
```

### 6. 合成训练数据 — `merge_tags_captions.py`

把清理后的标签和句子 caption 合并为一行，同时复制图片到 `merged/`。这个目录里的内容可以直接喂给训练脚本。

```
@cierra-rabit, 2girls, cowboy_shot, sitting, looking_at_another, blonde_hair, long_hair.
Two blonde girls sit together against a white background.
```

## 处理模式（Mode）

`audit_batch.py` 和 `caption.py` 通过 `--mode` 参数切换处理策略。不同模式对应 `prompts/` 下不同的 prompt 文件，决定 LLM 如何处理标签和生成 caption。

### 内置模式

| 模式 | 用途 | 审计重点 | Caption 风格 |
|------|------|---------|-------------|
| `style` | 画师画风 LoRA | 删角色名/画师名/作品名，保留构图/场景/光照 | 纯自然语言，不写触发词，不写引导句 |
| `character` | 人物角色 LoRA | 保留角色核心特征（瞳色/发色/配饰），按图片实际保留发型和服装 | 描述角色特征+外观+姿态+场景，至少 2 句 |

### 添加自定义模式

如果你想训练其他类型的 LoRA（如服装、场景、道具），可以添加自己的模式。只需在 `prompts/` 下创建两个文件：

```
prompts/tagger_audit_prompt_<mode>.md    ← LLM 审计标签用
prompts/caption_prompt_<mode>.md         ← LLM 生成 caption 用
```

**文件命名规则：** `prompts/<脚本基名>_<mode>.md`。`--mode my_mode` 会查找 `tagger_audit_prompt_my_mode.md` 和 `caption_prompt_my_mode.md`。找不到对应文件会直接报错退出。

**编写 prompt 的注意事项：**
- `audit_batch.py` 期望 LLM 输出**纯逗号分隔标签**（不加触发词、不加解释）
- `caption.py` 期望 LLM 输出**纯英文自然语言句子**（不加格式标记、不加代码块）
- 参考项目根目录下的 4 份 spec 文档了解画风和角色模式的编写思路
- 参考 `prompts/` 下的已有文件作为模板

## 日志

所有步骤共用一份日志 `logs/audit_<画风>.csv`，每列对应一个处理阶段。跑完之后可以快速查看哪些图片需要重跑：

```bash
# 查看有多少图需要重新生成 caption
grep -c "needs_recaption,true" logs/audit_cierra.csv

# 查看 caption 长度异常的图（过短）
awk -F, '$11 < 20 && $11 > 0' logs/audit_cierra.csv
```

## 从头开始一个新数据集

### 环境准备（仅第一次）

```bash
# 1. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 下载模型文件（二选一，PixAi Tagger 必须）
pip install huggingface-hub
huggingface-cli download 1038lab/pixai-tagger \
    pixai-tagger_v0.9.safetensors tags_v0.9_13k.json \
    --local-dir models/PixelAI_tagger/

# OppaiOracle 是可选的补充 tagger
# huggingface-cli download Grio43/OppaiOracle \
#     V1.1_onnx/model.onnx selected_tags.csv \
#     --local-dir models/OppaiOracle/

# 4. 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的 OpenRouter API Key
# 从 https://openrouter.ai/keys 获取
```

### 处理数据集

```bash
# 1. 丢图片进去
python scripts/process_raw.py --dataset 新画风
# → 提示"没有图片"，脚本已经建好目录了
# → 把图片复制到 datasets/新画风/ 里
# → 再跑一次 process_raw.py

# 2. 检查分辨率（超大图缩到 1024px）
python scripts/check_resolution.py --dataset 新画风
python scripts/check_resolution.py --dataset 新画风 --apply

# 3. 自动打标
python scripts/tag_images.py --dataset 新画风 --trigger "my_trigger"

# 4. LLM 审计标签（--mode style 画风 / character 角色）
python scripts/audit_batch.py --dataset 新画风 --mode style --trigger my_trigger

# 5. 生成句子 caption
python scripts/caption.py --dataset 新画风 --mode style

# 6. 合成训练数据
python scripts/merge_tags_captions.py --dataset 新画风
```
