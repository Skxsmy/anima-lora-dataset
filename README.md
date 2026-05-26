# Anima LoRA 数据集准备管道

画师画风 LoRA 的训练数据准备工具。从原始图片到可直接训练的 `merged/` 目录，一条龙。

## 一次完整的工作流长什么样

以 cierra 画师为例（cierra-rabit 是自定义触发词）：

```bash
# 1. 把图片丢进去就行
python scripts/process_raw.py --dataset cierra

# 2. 自动打标（PixAi 识别画面内容，生成 Danbooru 标签）
python scripts/tag_images.py --dataset cierra --trigger "cierra-rabit"

# 3. LLM 清理标签（去掉画师名、角色名、质量词、过细零件等）
python scripts/audit_batch.py --dataset cierra

# 4. 生成自然语言描述（给每张图写一句英文 caption）
python scripts/caption.py --dataset cierra

# 5. 合成最终训练数据
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

### 2. PixAi 打标 — `tag_images.py`

对每张图跑 PixAi Tagger，识别画面中的元素、动作、场景，输出 Danbooru 格式标签。每个 `.jpg` 旁边生成一个同名的 `.txt`。

```
@cierra-rabit, 1girl, solo, upper_body, looking_at_viewer, bedroom, sitting, window_light
```

### 3. LLM 审计 — `audit_batch.py`

自动标签里有很多不该出现在画风 LoRA 里的东西。LLM 会检查每张图的实际画面，把下面这些清理掉：

- 真实画师名（让自定义触发词专心绑定画风）
- 具体角色名（不要让画风绑定到特定人物）
- 作品/系列名
- 质量词（masterpiece、best quality 等）
- 平台水印、签名、文字残留
- 过细的服装零件和身体部位
- 明显识别错误的标签

留下的：主体、人数、构图、动作、场景、明显的服装大类、光照。

### 4. 句子 Caption — `caption.py`

为每张图生成一句自然语言英文描述，描述画面中实际看到的内容。不写 "The image shows" 这类引导语，不谈剧情，不堆风格词。

```
Two blonde girls sit together against a white background. The girl on the left has blue eyes and wears a white dress with a red bow and frills, looking forward.
```

### 5. 合成训练数据 — `merge_tags_captions.py`

把清理后的标签和句子 caption 合并为一行，同时复制图片到 `merged/`。这个目录里的内容可以直接喂给训练脚本。

```
@cierra-rabit, 2girls, cowboy_shot, sitting, looking_at_another, blonde_hair, long_hair.
Two blonde girls sit together against a white background.
```

## 日志

所有步骤共用一份日志 `logs/audit_<画风>.csv`，每列对应一个处理阶段。跑完之后可以快速查看哪些图片需要重跑：

```bash
# 查看有多少图还没 caption
grep -c "needs_caption,true" logs/audit_cierra.csv

# 查看 caption 长度异常的图（过短）
awk -F, '$10 < 20 && $10 > 0' logs/audit_cierra.csv
```

## 从头开始一个新数据集

```bash
# 1. 激活环境
source venv/bin/activate

# 2. 丢图片进去
python scripts/process_raw.py --dataset 新画风
# → 提示"没有图片"，脚本已经建好目录了
# → 把图片复制到 datasets/新画风/ 里
# → 再跑一次 process_raw.py

# 3. 触发词随意定，建议不要用真实画师名
python scripts/tag_images.py --dataset 新画风 --trigger "my_trigger"

# 4-6. 同上
python scripts/audit_batch.py --dataset 新画风
python scripts/caption.py --dataset 新画风
python scripts/merge_tags_captions.py --dataset 新画风
```
