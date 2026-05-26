# Tagger 输出后处理原则：画师画风 LoRA

## 1. 目标

画风 LoRA 的 caption 目标不是精确复述每张图的全部细节，而是让模型知道画面里大致有什么，同时把统一画风绑定到固定触发词上。

画风 LoRA 的 caption 应该保留：

- 主体信息
- 人物数量
- 基本构图
- 基本场景
- 基本动作
- 必要的光照或时间信息

画风 LoRA 的 caption 应该删除：

- 真实画师 tag
- 具体角色 tag
- 作品或系列 tag
- 质量词
- 平台来源残留
- 水印、签名、文字相关 tag
- 过细的服装零件
- 过细的身体部位
- 明显错误 tag

推荐最终结构：

```text
@style_trigger, subject, composition, action, scene, lighting
```

示例：

```text
@style_trigger, 1girl, solo, upper body, looking at viewer, bedroom, sitting, window light
```

---

## 2. 触发词原则

每张 caption 都应使用同一个画风触发词。

推荐格式：

```text
@style_trigger
```

示例：

```text
@aki_style
@cover_style
@cel_style
@watercolor_style
```

触发词应放在 caption 最前面。

正确示例：

```text
@aki_style, 1girl, solo, upper body, bedroom, sitting, window light
```

不推荐：

```text
1girl, solo, upper body, bedroom, sitting, window light, @aki_style
```

不建议使用普通词作为触发词，例如：

```text
anime
manga
illustration
beautiful
soft
clean
style
cel shading
watercolor
```

也不建议使用真实画师名作为自定义触发词，除非训练目标明确是调用该画师在基模中的已有先验。

---

## 3. Tagger 输出不能直接使用

自动 tagger 的输出只能作为初稿。  
用于画风 LoRA 前，需要进行后处理。

主要原因：

1. tagger 可能识别出错误角色。
2. tagger 可能识别出错误画师。
3. tagger 可能识别出错误作品。
4. tagger 会输出很多与画风训练无关的 meta tag。
5. tagger 可能输出平台、水印、签名、文字相关 tag。
6. tagger 会输出过多细碎物体或服装零件。
7. caption 太长会削弱画风触发词的集中作用。

画风 LoRA 的 caption 应遵循：

```text
少而准，优先保留画面结构信息。
```

推荐每张 caption 控制在：

```text
8–25 个有效 tag
```

复杂场景可以适当增加，但不建议无脑保留 50 个以上 tag。

---

## 4. 应该保留的 tag 类型

### 4.1 人物数量

保留人物数量 tag。

常见可保留：

```text
1girl
1boy
2girls
2boys
multiple girls
multiple boys
solo
no humans
```

这些 tag 有助于区分画面主体规模。

---

### 4.2 基本主体

保留画面主要主体。

可保留：

```text
girl
boy
woman
man
animal
cat
dog
dragon
robot
monster
landscape
building
room
street
forest
sky
```

如果已经有 `1girl`、`1boy`，通常不必再保留泛化的 `girl`、`boy`。

---

### 4.3 构图与视角

保留构图和视角 tag。

可保留：

```text
portrait
upper body
cowboy shot
full body
close-up
wide shot
from above
from below
side view
profile
looking at viewer
looking away
dynamic angle
```

这些 tag 对画风 LoRA 有价值，因为画师风格通常不仅体现在笔触上，也体现在构图习惯上。

---

### 4.4 场景与环境

保留主要场景 tag。

可保留：

```text
indoors
outdoors
bedroom
classroom
city
street
cafe
forest
beach
sky
night
sunset
rain
snow
window
desk
chair
sofa
bookshelf
building
```

场景 tag 不需要过细。  
例如：

```text
classroom
```

通常比下面这一长串更有用：

```text
chalkboard, desk, chair, window, curtain, book, pencil case, floor tile
```

除非这些物体是画面的主要组成部分，否则不需要全部保留。

---

### 4.5 动作与姿态

保留主要动作和姿态。

可保留：

```text
standing
sitting
lying
walking
running
jumping
holding
reaching
turning around
arms crossed
hand on face
smile
crying
angry
sleeping
```

动作和姿态 tag 有助于避免画风触发词绑定到单一姿势或单一构图。

---

### 4.6 光照与时间

明显存在时可以保留。

可保留：

```text
day
night
sunset
backlighting
soft lighting
rim light
dramatic lighting
dim lighting
```

不要每张图都人工添加同一组光照词。  
只有图片中确实明显存在时才保留。

---

### 4.7 服装大类

可以保留服装大类。

可保留：

```text
school uniform
dress
suit
hoodie
coat
jacket
kimono
armor
swimsuit
casual clothes
```

画风 LoRA 通常不需要保留过细服装结构。  
服装细节更适合人物 LoRA 或服装 LoRA。

---

## 5. 应该删除的 tag 类型

### 5.1 真实画师 tag

删除自动识别出的真实画师 tag。

例如：

```text
@known_artist
artist name
by artist
```

原因：画风 LoRA 应由自定义触发词承担画风锚点。

应该使用：

```text
@style_trigger
```

而不是让真实画师 tag 和你的自定义触发词同时承担画风信息。

例外情况：如果目标是利用基模中已有的某个画师先验，可以保留真实画师 tag。但这会改变训练目标，不再是纯自定义画风锚点。

---

### 5.2 具体角色 tag

通常删除具体角色名。

例如：

```text
hatsune miku
asuna
rem
saber
specific character name
```

原因：画风 LoRA 不应该学习某个固定角色。  
如果保留大量角色 tag，画风 LoRA 容易同时绑定角色信息。

例外情况：如果目标是训练“某角色的某画师版本”，那就不是纯画风 LoRA，而是角色与画风混合目标，应单独处理。

---

### 5.3 作品 / 系列 tag

通常删除作品或系列 tag。

例如：

```text
vocaloid
fate
genshin impact
blue archive
touhou
copyright name
series name
```

原因：画风 LoRA 不应绑定到特定作品设定。  
如果作品 tag 大量保留，推理时可能带出该作品的人物、服饰或世界观元素。

---

### 5.4 质量词

删除质量词。

例如：

```text
masterpiece
best quality
high quality
absurdres
highres
lowres
bad quality
worst quality
official art
scan
screenshot
```

这些词更适合推理时使用，不适合作为画风 caption 的核心内容。

---

### 5.5 平台和来源残留

删除平台、来源、水印、签名、用户名相关 tag。

例如：

```text
twitter username
pixiv username
signature
watermark
logo
sample watermark
artist name
commentary
```

如果图片中确实存在大量文字或水印，应由数据集整理者决定是否保留该图。  
caption 中通常不建议保留这些 tag。

---

### 5.6 文字相关 tag

通常删除文字相关 tag。

例如：

```text
text
speech bubble
subtitle
manga text
translation request
letterboxed
caption
logo
sign
```

如果训练目标是封面、海报、漫画页排版，可以另行决定是否保留。  
如果训练目标是纯绘画风格，通常删除。

---

### 5.7 Rating / 安全分级 tag

一般删除。

例如：

```text
safe
sensitive
questionable
explicit
rating:safe
rating:general
```

这些是数据管理信息，不是画面风格信息。

---

### 5.8 年份 / 时间 meta tag

一般删除。

例如：

```text
2020
2021
2022
2023
2024
2025
newest
recent
old
classic
```

除非目标是训练某个年代的风格，否则不保留。

---

### 5.9 过细的身体部位 tag

通常删除过细身体部位。

例如：

```text
nose
mouth
eyelashes
fingernails
teeth
ear
eyebrow
collarbone
knee
elbow
```

除非该部位是画面主要特征，否则不需要保留。

---

### 5.10 过细的服装零件 tag

通常删除过细服装零件。

例如：

```text
button
zipper
lace trim
collar
cuffs
belt buckle
pleated skirt
single sleeve
detached sleeves
shoe bow
```

画风 LoRA 保留服装大类即可。  
服装结构细节更适合人物 LoRA 或服装 LoRA。

---

### 5.11 明显错误 tag

删除任何与图片不符的 tag。

例如图片里没有以下内容，但 tagger 输出了：

```text
cat
weapon
wings
horns
glasses
hat
tail
flower
book
```

则应删除。

---

## 6. 可选保留的 tag 类型

### 6.1 色彩 tag

颜色倾向明显时可以少量保留。

例如：

```text
monochrome
grayscale
limited palette
pastel colors
vivid colors
warm colors
cool colors
```

不要每张图都强行添加颜色 tag。  
只有颜色倾向确实明显时才保留。

---

### 6.2 线稿 / 上色 tag

可以少量保留，但不要每张图都重复堆叠。

例如：

```text
lineart
sketch
flat color
cel shading
painting
watercolor
monochrome
```

如果所有图片本来就是同一画风，通常可以少写这些词，让 `@style_trigger` 负责绑定风格。

如果每张图都写：

```text
clean lineart, soft shading, delicate colors, detailed eyes
```

模型可能把风格拆散绑定到这些普通 tag 上，而不是集中绑定到 `@style_trigger`。

---

### 6.3 画面类型 tag

可按需要保留。

例如：

```text
illustration
manga page
comic
poster
cover
character sheet
concept art
background art
```

需要谨慎处理。  
如果不想训练封面排版，就不要大量保留 `poster`、`cover`。  
如果不想训练漫画页结构，就不要大量保留 `manga page`、`comic`。

---

## 7. 多画师版本处理原则

### 7.1 目标是单一画师画风

如果目标是训练单一画师画风，数据集中应尽量只保留该画师或该视觉方向一致的图片。

caption 使用：

```text
@style_trigger, subject, composition, action, scene
```

不要保留其他画师名。  
不要混入明显不同视觉方向的图片。

---

### 7.2 目标是某一系列的综合视觉风格

如果目标是训练某一系列的综合视觉风格，可以混入多个画师版本，但整体视觉方向应保持一致。

应避免把以下差异极大的类型全部混入同一个触发词：

```text
厚涂
赛璐璐
Q版
漫画线稿
写实渲染
低饱和插画
高饱和海报
```

如果差异很大，建议拆成多个风格 LoRA 或多个触发词：

```text
@style_cel
@style_paint
@style_manga
@style_chibi
```

---

### 7.3 目标是“某角色的画师版本”

如果数据目标是“某角色在某画师笔下的版本”，这不是纯画风 LoRA，而是角色与画风混合目标。

这种情况下应先决定：

```text
是否要训练角色身份
是否要训练画师画风
是否要训练某个固定版本
是否要把人物 LoRA 和画风 LoRA 分开
```

如果目标是纯画风 LoRA，不建议保留具体角色 tag。

---

## 8. 后处理顺序

建议按以下顺序处理 tagger 输出：

1. 添加统一画风触发词到最前。
2. 删除真实画师 tag。
3. 删除具体角色 tag。
4. 删除作品 / 系列 tag。
5. 删除质量词。
6. 删除平台来源残留。
7. 删除水印、签名、文字相关 tag。
8. 删除 rating、安全分级、年份等 meta tag。
9. 删除明显错误 tag。
10. 合并重复或近义 tag。
11. 保留人物数量、主体、构图、场景、动作。
12. 只在必要时保留光照、色彩、画面类型 tag。
13. 控制最终 caption 长度。
14. 抽样检查图片与 caption 是否匹配。

---

## 9. 推荐 caption 结构

推荐结构：

```text
@style_trigger, 人物数量/主体, 构图, 动作, 场景, 光照/时间
```

人物图示例：

```text
@style_trigger, 1girl, solo, upper body, looking at viewer, bedroom, sitting, window light
```

场景图示例：

```text
@style_trigger, no humans, forest, path, sunlight, wide shot, outdoors
```

多人图示例：

```text
@style_trigger, 2girls, full body, street, night, walking, rain
```

室内图示例：

```text
@style_trigger, 1boy, sitting, cafe, table, window, afternoon light
```

背景图示例：

```text
@style_trigger, no humans, city street, night, rain, neon lights, buildings, wide shot
```

---

## 10. 不推荐 caption 结构

不推荐：

```text
@style_trigger, masterpiece, best quality, highres, official art, artist name, known character, known series, twitter username, signature, 1girl, solo, long hair, eyelashes, fingernails, button, zipper, collar, school uniform, looking at viewer, smile, absurdres
```

问题：

- 质量词太多
- 真实画师 tag 污染
- 角色 tag 污染
- 作品 tag 污染
- 平台来源残留未删除
- 签名、水印、文字相关 tag 未删除
- 服装细节过多
- 身体细节过多
- meta tag 过多
- 有效画面信息被噪声淹没

---

## 11. 简化规则

如果只保留一版规则，可以使用以下原则：

```text
保留：主体、人数、构图、动作、场景、明显光照
删除：真实画师、角色名、作品名、质量词、meta、平台残留、水印、签名、文字、错误 tag
控制：每张 8–25 个有效 tag
固定：每张最前面都放同一个 @style_trigger
```

画风 LoRA 的重点是让 `@style_trigger` 学到统一视觉风格，而不是让 caption 复述每个细节。
```