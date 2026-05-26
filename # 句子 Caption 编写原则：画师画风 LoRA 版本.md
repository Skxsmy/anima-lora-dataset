# 句子 Caption 编写原则：画师画风 LoRA 版本

## 1. 目的

句子 caption 的作用是用自然语言描述图片中的可见内容，让训练模型理解画面主体、构图、动作、场景和基本视觉关系。

对于画师画风 LoRA，句子 caption 的核心目标不是复述所有细节，而是让固定触发词绑定画风，同时让句子描述图片中“实际看得见的内容”。

推荐基本结构：

    @style_trigger. The image shows [subject] [action/composition] in [scene], with [lighting or major visual element].

示例：

    @aki_style. The image shows a girl sitting by a window in a bedroom, with soft afternoon light.

---

## 2. 基本原则

句子 caption 应遵守以下原则：

1. 只描述画面事实。
2. 不写主观评价。
3. 不写剧情脑补。
4. 不写看不见的信息。
5. 不写真实画师名。
6. 不写具体角色名，除非训练目标明确需要。
7. 不写作品名，除非训练目标明确需要。
8. 不堆质量词。
9. 不堆推理 prompt 常用词。
10. 不每张图重复相同的长风格描述。
11. 每张图使用同一个画风触发词。
12. 触发词放在句子最前面。
13. 每张 caption 建议 1–2 句。
14. 每张 caption 建议 15–45 个英文词。
15. 句子应简洁、稳定、可批量处理。
16. 不写任何the image shows 之类的短语

---

## 3. 画风触发词

每张 caption 最前面都应放置统一画风触发词。

推荐格式：

    @style_trigger

示例：

    @aki_style
    @cover_style
    @cel_style
    @watercolor_style

推荐句式：

    @aki_style. The image shows a girl sitting at a desk in a classroom.

不推荐：

    The image shows a girl sitting at a desk in a classroom. @aki_style

原因：

- 触发词放在最前面更稳定。
- 所有训练图应保持一致格式。
- 触发词应专门负责绑定画风。

---

## 4. 句子 Caption 应该包含什么

句子 caption 优先描述以下内容：

### 4.1 画面主体

包括：

- 人物
- 动物
- 建筑
- 房间
- 街道
- 风景
- 道具
- 无人物场景

示例：

    The image shows a girl standing in a classroom.
    The image shows an empty city street at night.
    The image shows a cat sitting on a windowsill.

---

### 4.2 人物数量

如果图片中有人物，应写出大致数量。

示例：

    The image shows a girl sitting by a window.
    The image shows two girls standing together on a street.
    The image shows a group of people walking through a city.

如果没有人物，可以写：

    The image shows an empty classroom with desks and windows.
    The image shows a forest path under sunlight.

---

### 4.3 构图

可以描述：

- close-up
- upper body
- full body
- wide shot
- side view
- profile view
- viewed from above
- viewed from below

示例：

    The image shows a girl in an upper body portrait, looking toward the viewer.
    The image shows a full body view of a girl standing on a rooftop.
    The image shows a wide shot of an empty street at night.

---

### 4.4 动作与姿态

可以描述：

- standing
- sitting
- walking
- running
- lying down
- holding something
- looking at viewer
- looking away
- turning around
- reaching forward

示例：

    The image shows a girl sitting on a bed and looking toward the viewer.
    The image shows a boy walking through a rainy street.
    The image shows a girl holding an umbrella at night.

---

### 4.5 场景

可以描述：

- bedroom
- classroom
- cafe
- street
- city
- forest
- beach
- rooftop
- train station
- room
- sky
- building

示例：

    The image shows a girl standing in a classroom near a window.
    The image shows an empty cafe interior with tables and chairs.
    The image shows a city street at night with rain and neon lights.

---

### 4.6 时间、天气、光照

明显存在时可以描述：

- day
- night
- sunset
- rain
- snow
- sunlight
- soft light
- window light
- backlighting
- neon light

示例：

    The image shows a girl standing on a rooftop at sunset.
    The image shows a rainy city street at night with neon lights.
    The image shows a bedroom lit by soft morning light.

---

### 4.7 服装大类

可以保留服装大类，但不需要描述过多细节。

可以写：

- school uniform
- dress
- coat
- hoodie
- suit
- kimono
- armor
- casual clothes

示例：

    The image shows a girl in a school uniform sitting in a classroom.
    The image shows a woman in a dress standing in a garden.
    The image shows a boy in a hoodie walking down a city street.

不建议写过多细碎结构：

    lace-trimmed collar, silver button, folded cuff, double zipper, tiny bow, pleated hem

除非这些是图片的主要视觉内容。

---

## 5. 句子 Caption 不应该包含什么

### 5.1 不写主观评价

删除以下类型表达：

- beautiful
- amazing
- gorgeous
- stunning
- perfect
- masterpiece
- best quality
- high quality
- professional artwork

错误示例：

    @aki_style. A beautiful masterpiece anime illustration with amazing colors and perfect composition.

正确示例：

    @aki_style. The image shows a girl standing on a rooftop at sunset, looking toward the viewer.

---

### 5.2 不写推理 Prompt 口号

不要写：

- masterpiece
- best quality
- ultra detailed
- 8k
- highly detailed
- absurdres
- score_9
- perfect anatomy
- cinematic lighting

错误示例：

    @aki_style. Masterpiece, best quality, ultra detailed anime illustration of a girl.

正确示例：

    @aki_style. The image shows a girl sitting by a classroom window, viewed from the waist up.

---

### 5.3 不写剧情脑补

不要写图片中看不见的故事、心理活动或设定。

错误示例：

    @aki_style. A lonely girl remembers her painful past while waiting for someone important.

正确示例：

    @aki_style. The image shows a girl standing alone at a train station at night.

---

### 5.4 不写看不见的信息

不要写无法从画面确认的信息。

错误示例：

    @aki_style. The image shows a brave princess from a fallen kingdom.

正确示例：

    @aki_style. The image shows a girl wearing a dress standing in a castle hallway.

---

### 5.5 不写真实画师名

画风 LoRA 的触发词应由自定义触发词承担，不应依赖真实画师名。

错误示例：

    @aki_style. The image is drawn by a famous artist and shows a girl in a bedroom.

正确示例：

    @aki_style. The image shows a girl sitting in a bedroom near a window.

---

### 5.6 不写具体角色名

如果目标是纯画风 LoRA，通常不写具体角色名。

错误示例：

    @aki_style. The image shows Hatsune Miku standing on a stage.

正确示例：

    @aki_style. The image shows a girl with long twin tails standing on a stage.

---

### 5.7 不写作品名

如果目标是纯画风 LoRA，通常不写作品或系列名。

错误示例：

    @aki_style. The image shows a character from Genshin Impact standing in a fantasy city.

正确示例：

    @aki_style. The image shows a girl standing in a fantasy city with tall buildings and soft light.

---

### 5.8 不每张都堆同一串风格词

不要每张都重复写：

    clean lineart, soft shading, delicate colors, detailed eyes, anime style

原因：

- 这些词会分散画风触发词的作用。
- 模型可能把风格绑定到普通词上，而不是绑定到自定义触发词上。
- 画风 LoRA 应该主要由触发词控制。

错误示例：

    @aki_style. The image has beautiful clean lineart, soft shading, delicate colors, detailed eyes, and an amazing anime style.

正确示例：

    @aki_style. The image shows a girl sitting in a bedroom near a window, with books and soft afternoon light.

---

## 6. 推荐句式

### 6.1 人物图

模板：

    @style_trigger. The image shows [number/subject] [pose/action] in [scene], with [composition or lighting].

示例：

    @aki_style. The image shows a girl sitting at a desk in a classroom, viewed from the waist up.
    @aki_style. The image shows a boy standing on a city street at night, looking away.
    @aki_style. The image shows a girl in a dress standing in a garden under soft sunlight.

---

### 6.2 多人图

模板：

    @style_trigger. The image shows [number/subjects] [interaction/action] in [scene].

示例：

    @aki_style. The image shows two girls standing together on a city street at night.
    @aki_style. The image shows several students sitting in a classroom.
    @aki_style. The image shows two people walking through a rainy street.

---

### 6.3 背景图

模板：

    @style_trigger. The image shows [place/environment], with [major objects, light, or weather].

示例：

    @aki_style. The image shows an empty cafe interior with tables, chairs, windows, and warm light.
    @aki_style. The image shows a forest path under sunlight, viewed from a wide angle.
    @aki_style. The image shows a city street at night with rain, neon lights, and tall buildings.

---

### 6.4 动态图

模板：

    @style_trigger. The image shows [subject] [dynamic action] in [scene].

示例：

    @aki_style. The image shows a girl running through a rainy street at night.
    @aki_style. The image shows a boy jumping across a rooftop under the evening sky.
    @aki_style. The image shows a girl turning around in a classroom.

---

### 6.5 室内图

模板：

    @style_trigger. The image shows [subject] in [indoor place], with [objects or light].

示例：

    @aki_style. The image shows a girl sitting on a bed in a bedroom, with soft light from a window.
    @aki_style. The image shows an empty classroom with desks, windows, and warm sunlight.
    @aki_style. The image shows a boy sitting in a cafe near a table and window.

---

### 6.6 无人物图

模板：

    @style_trigger. The image shows [environment], with [major objects or lighting].

示例：

    @aki_style. The image shows an empty street at night with rain and neon signs.
    @aki_style. The image shows a quiet bedroom with a bed, curtains, and morning light.
    @aki_style. The image shows a forest clearing with sunlight passing through the trees.

---

## 7. 推荐长度

每张 caption 建议：

    1–2 句
    15–45 个英文词

太短的问题：

    @aki_style. A girl.

问题：信息不足。

太长的问题：

    @aki_style. The image shows a beautiful young anime girl with extremely delicate eyes and perfect soft shading in a highly detailed room full of many objects, amazing colors, wonderful lighting, elegant brushwork, and a dreamy atmosphere.

问题：

- 主观评价太多
- 风格词太多
- 信息噪声太多
- 不利于稳定训练

更合适：

    @aki_style. The image shows a girl sitting in a bedroom near a window, with books and soft afternoon light.

---

## 8. 混合 Tag + 句子 Caption

如果需要混合 tag 和句子，推荐结构：

    @style_trigger, key tags. Natural language sentence.

示例：

    @aki_style, 1girl, upper body, bedroom, sitting. The image shows a girl sitting by a window in a bedroom, with soft afternoon light.

    @aki_style, no humans, city street, night, rain. The image shows an empty street at night with neon lights and wet pavement.

    @aki_style, 2girls, classroom, standing. The image shows two girls standing together in a classroom near a window.

不推荐：

    @aki_style, 1girl, solo, long hair, blue eyes, school uniform, sitting, window, desk, chair, curtain, book, bag, floor, wall, light, shadow, smile, looking at viewer, upper body, masterpiece, best quality. The image is a beautiful anime masterpiece with amazing clean lineart and wonderful soft colors.

问题：

- tag 过多
- 质量词污染
- 主观评价过多
- 句子信息重复
- 风格词堆叠过度

---

## 9. 自动句子 Caption 的后处理原则

如果使用 JoyCaption 或其他 VLM 批量生成句子，应进行后处理。

### 9.1 删除内容

删除以下内容：

- 真实画师名
- 具体角色名
- 作品名
- 主观评价
- 质量词
- 剧情脑补
- 情绪脑补
- 看不见的设定
- 过度风格分析
- 平台、水印、签名描述
- 每张重复出现的空泛风格词

### 9.2 保留内容

保留以下内容：

- 主体
- 人数
- 构图
- 动作
- 场景
- 明显物体
- 明显光照
- 天气或时间

### 9.3 统一格式

所有 caption 建议统一为：

    @style_trigger. The image shows ...

不要混用过多不同开头。

推荐：

    @aki_style. The image shows a girl sitting by a window in a bedroom.

不推荐同一数据集中混杂：

    This artwork depicts...
    A beautiful illustration of...
    We can see...
    There is...
    The picture appears to be...
    This masterpiece shows...

统一句式更利于批量清洗和检查。

---

## 10. 好坏对比

### 10.1 主观评价问题

错误：

    @aki_style. A beautiful high quality anime masterpiece with amazing detailed eyes and perfect soft shading.

正确：

    @aki_style. The image shows a girl in a school uniform sitting by a classroom window, viewed from the waist up.

---

### 10.2 角色污染问题

错误：

    @aki_style. The image shows Hatsune Miku from Vocaloid standing on a stage.

正确：

    @aki_style. The image shows a girl with long twin tails standing on a stage under bright lights.

---

### 10.3 作品污染问题

错误：

    @aki_style. The image shows a character from Genshin Impact standing in a fantasy city.

正确：

    @aki_style. The image shows a girl standing in a fantasy city with tall buildings and warm light.

---

### 10.4 剧情脑补问题

错误：

    @aki_style. A lonely girl remembers her painful past while waiting for someone important.

正确：

    @aki_style. The image shows a girl standing alone at a train station at night.

---

### 10.5 风格词堆叠问题

错误：

    @aki_style. The image has clean lineart, soft shading, delicate colors, detailed eyes, cinematic lighting, and a beautiful anime style.

正确：

    @aki_style. The image shows a girl sitting at a desk in a bedroom, with books and soft afternoon light.

---

### 10.6 过短问题

错误：

    @aki_style. A room.

正确：

    @aki_style. The image shows an empty bedroom with a bed, curtains, and soft morning light.

---

### 10.7 过长问题

错误：

    @aki_style. The image shows a very beautiful and charming young girl with perfect detailed eyes, soft delicate shading, amazing linework, wonderful colors, a lovely mood, and an extremely detailed classroom background full of objects and cinematic atmosphere.

正确：

    @aki_style. The image shows a girl sitting in a classroom near a window, with desks and soft sunlight.

---

## 11. 不同图片类型的推荐写法

### 11.1 人物半身图

    @aki_style. The image shows a girl in an upper body portrait, looking toward the viewer.

### 11.2 人物全身图

    @aki_style. The image shows a full body view of a girl standing on a street.

### 11.3 人物近景图

    @aki_style. The image shows a close-up portrait of a girl looking toward the viewer.

### 11.4 多人图

    @aki_style. The image shows two girls standing together in a classroom.

### 11.5 室内背景

    @aki_style. The image shows an empty bedroom with a bed, curtains, and soft morning light.

### 11.6 城市场景

    @aki_style. The image shows a city street at night with rain and neon lights.

### 11.7 自然风景

    @aki_style. The image shows a forest path under sunlight, viewed from a wide angle.

### 11.8 海报或封面构图

    @aki_style. The image shows a girl standing in the center of a poster-like composition.

只有在训练目标包含封面或海报排版时，才建议保留 poster-like composition 这类描述。

### 11.9 漫画页或分镜

    @aki_style. The image shows a comic page with multiple panels and character scenes.

只有在训练目标包含漫画页结构时，才建议保留 comic page 或 multiple panels。

---

## 12. 画风 LoRA 的句子 Caption 推荐流程

建议处理顺序：

1. 给每张 caption 最前面添加统一画风触发词。
2. 用一句话描述画面主体。
3. 补充动作或构图。
4. 补充场景。
5. 补充明显光照、天气或时间。
6. 删除主观评价。
7. 删除质量词。
8. 删除真实画师名。
9. 删除具体角色名。
10. 删除作品名。
11. 删除剧情脑补。
12. 删除看不见的信息。
13. 控制句子长度。
14. 抽样检查图片与句子是否一致。

---

## 13. 最终推荐格式

纯句子 caption：

    @style_trigger. The image shows [subject] [action/composition] in [scene], with [lighting or major visual element].

混合 tag + 句子 caption：

    @style_trigger, [key tags]. The image shows [subject] [action/composition] in [scene], with [lighting or major visual element].

---

## 14. 最简规则

如果只保留一版规则，使用以下原则：

    写画面事实。
    不写评价。
    不写剧情脑补。
    不写真实画师名。
    不写具体角色名。
    不写作品名。
    不写质量词。
    不每张重复堆同一串风格词。
    每张 1–2 句。
    触发词放最前。
    画风交给触发词，句子只描述画面内容。

推荐最终句式：

    @style_trigger. The image shows [subject] [action/composition] in [scene], with [lighting or major visual element].