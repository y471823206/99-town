# 久久光合社信息架构与数据模型

版本：v0.1
日期：2026-07-04
状态：Draft

---

## 1. 核心原则

久久光合社的核心不是“把文件放到不同栏目里”，而是做一个可持续生长的策展系统。

核心原则：

```text
资产库 = 唯一数据源
作品长廊 = 成品策展
天机阁 = 方法 / skill 解释
久久小镇 = 创作过程和居民生活
意图工坊 = 未来的“我也想要”
```

同一份内容只存一份。不同板块只是从不同视角引用它，不复制它。

示例：

```text
一篇微信教程文章
  原始文件在资产库
  成品展示在作品长廊
  提炼方法进入天机阁
  创作过程展示在久久小镇
  未来可从意图工坊被复刻
```

---

## 2. 信息架构

### 2.1 顶层结构

```text
久久光合社
  首页
  作品长廊
  天机阁
  久久小镇
  资产库
  意图工坊
```

### 2.2 首页

首页负责建立第一印象：

- 久久是谁。
- 久久如何用 AI 创作。
- 久久小镇是什么。
- 近期精选作品。
- 当前小镇状态。
- 进入作品长廊、天机阁、久久小镇的入口。

首页核心文案建议：

```text
久久光合社
一个由 AI、作品和生活共同生长的地方。
```

### 2.3 作品长廊

作品长廊展示“成品”和“精选”。

分类：

- 图片
- 视频
- 文章
- 小镇生活

分类原则：

- 一级分类固定为：图片、视频、文章、小镇生活。
- 二级分类不提前锁死，根据真实作品动态生成，由久久或北北策展命名。
- 居民、skill、展示板块不作为一级分类。
- 同一作品可以有一个主分类，同时通过标签或关联关系出现在天机阁/久久小镇。

二级分类示例：

| 一级分类 | 二级分类 |
|---|---|
| 图片 | 猫是命、小红书封面、信息图 |
| 视频 | 混剪、教程、口播、创意、信息流 |
| 文章 | 教程、成长、AI |
| 小镇生活 | 小镇晨报、小镇晚报、奏折、自评、产品体验报告 |

列表页展示：

- 标题。
- 缩略图或预览。
- 内容类型。
- 创作居民。
- 发布时间。
- 关联 skill。
- 久久评价。

详情页展示：

- 作品正文或嵌入预览。
- 作品故事。
- 关联任务。
- 创作居民。
- 使用 skill。
- 关联资产。
- 评价记录。
- “我也想要”入口，未来版本开放。

### 2.4 天机阁

天机阁展示“方法”和“能力”。

它不重复展示完整作品，而是解释作品背后的方法：

- skill 是什么。
- 谁装备了它。
- 它解决什么问题。
- 它来自哪里。
- 它产出了哪些代表作品。
- 它如何从久久评价中进化。

分类：

- 写作方法
- 视觉方法
- 自媒体方法
- 小镇治理方法
- 工程维护方法
- AI 工作流

### 2.5 久久小镇

久久小镇展示“过程”和“生活”。

第一阶段只读展示：

- 小镇地图。
- 居民状态。
- 最近任务。
- 北北奏折。
- 近期作品。
- skill 奖励动态。

未来阶段：

- 访客进入小镇参观。
- 访客查看居民档案。
- 访客看到小镇生活流。
- 部分居民可被授权调用。

### 2.6 资产库

资产库是唯一数据源和后台管理中心。

资产包括：

- 作品文件。
- 图片素材。
- 文章素材。
- prompt。
- skill。
- 模板。
- 任务记录。
- 评价记录。
- 居民产出记录。

资产库主要给久久和北北使用，不一定作为公开页面完整展示。

### 2.7 意图工坊

意图工坊承载未来“看见即所得”。

流程：

```text
访客看到作品
  -> 点击“我也想要”
  -> 选择风格 / 居民 / skill
  -> 提交意图
  -> 北北转成悬赏
  -> 居民协作产出
  -> 产出进入资产库
  -> 精选后进入作品长廊
```

MVP 不开放访客调用，只预留数据结构。

---

## 3. 核心实体

### 3.1 Asset

资产是系统的唯一底层内容单位。

一切可存档内容都先是 asset：

- HTML 文件。
- Markdown 文件。
- 图片。
- 视频。
- 音频。
- prompt。
- skill 文件。
- 文章草稿。
- 设计模板。

### 3.2 Work

作品是进入作品长廊的策展项。

不是所有 asset 都是 work。只有被选中展示的成品才成为 work。

### 3.3 Method

方法是天机阁中的方法论或可复用流程。

一个 method 可以来自：

- 一篇教程。
- 一次成功任务。
- 一条 skill。
- 一组评价沉淀。

### 3.4 Skill

skill 是可被居民学习和装备的能力。

skill 可以是：

- Codex/AionUI skill。
- Hermes skill。
- 居民自己的经验卡。
- 从文章教程中提炼出的操作方法。

### 3.5 Resident

居民是小镇里的长期 agent。

MVP 常驻居民：

- 北北：守护灵，总调度。
- 阿程：工程师。
- 阿画：设计师。
- 小文：写作者。
- 小匠：skill 管家。

### 3.6 Task

任务是居民生产内容和系统变化的过程记录。

一个 task 可以产出多个 asset，也可以关联一个 work。

### 3.7 Review

评价是久久对居民或作品的反馈。

评价会影响：

- 积分。
- skill 沉淀。
- 作品是否进入作品长廊。
- 居民未来表现。

---

## 4. 数据表建议

### 4.1 `assets`

当前项目已有 `assets` 表，后续应扩展为真正的唯一资产表。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | TEXT | 资产 ID |
| title | TEXT | 资产标题 |
| asset_type | TEXT | html/md/image/video/audio/prompt/skill/template |
| file_path | TEXT | 本地文件路径或相对路径 |
| source | TEXT | town_output/manual/import/generated |
| resident_id | TEXT | 主要创作居民 |
| task_id | TEXT | 来源任务 |
| created_at | TEXT | 创建时间 |
| updated_at | TEXT | 更新时间 |
| visibility | TEXT | private/unlisted/public |
| metadata | TEXT | JSON 扩展字段 |

### 4.2 `works`

作品长廊策展表。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | TEXT | 作品 ID |
| asset_id | TEXT | 主资产 ID |
| title | TEXT | 对外展示标题 |
| slug | TEXT | URL slug |
| work_type | TEXT | image/article/comic/video/music/report/experiment |
| gallery_category | TEXT | 一级分类：图片/视频/文章/小镇生活 |
| gallery_subcategory | TEXT | 二级分类，由作品动态生成，如猫是命/小镇晨报/奏折 |
| summary | TEXT | 摘要 |
| cover_asset_id | TEXT | 封面资产 |
| curator_note | TEXT | 策展说明 |
| status | TEXT | draft/published/archived |
| featured | INTEGER | 是否精选 |
| published_at | TEXT | 发布时间 |

### 4.3 `methods`

天机阁方法表。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | TEXT | 方法 ID |
| title | TEXT | 方法名 |
| method_type | TEXT | writing/design/workflow/engineering/governance |
| summary | TEXT | 方法摘要 |
| source_asset_id | TEXT | 来源文章/教程/作品 |
| related_skill_id | TEXT | 关联 skill |
| resident_id | TEXT | 主要适用居民 |
| status | TEXT | draft/active/deprecated |
| created_at | TEXT | 创建时间 |

### 4.4 `skills_catalog`

skill 目录表。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | TEXT | skill ID |
| name | TEXT | skill 名称 |
| source | TEXT | local/github/hermes/manual |
| skill_path | TEXT | 本地路径 |
| description | TEXT | 描述 |
| role_fit | TEXT | 适合角色 |
| status | TEXT | available/testing/equipped/deprecated |
| created_at | TEXT | 创建时间 |

### 4.5 `asset_links`

统一关联表，避免重复存储。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | TEXT | 关联 ID |
| asset_id | TEXT | 资产 ID |
| target_type | TEXT | work/method/skill/task/resident/collection |
| target_id | TEXT | 目标 ID |
| relation_type | TEXT | source/output/cover/reference/example/derived_from |
| created_at | TEXT | 创建时间 |

### 4.6 `collections`

策展专题。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | TEXT | 专题 ID |
| title | TEXT | 专题名 |
| description | TEXT | 说明 |
| collection_type | TEXT | gallery/series/topic/town_life |
| status | TEXT | draft/published |
| sort_order | INTEGER | 排序 |

### 4.7 `collection_items`

专题内容。

| 字段 | 类型 | 说明 |
|---|---|---|
| collection_id | TEXT | 专题 ID |
| item_type | TEXT | work/asset/method/resident |
| item_id | TEXT | 内容 ID |
| sort_order | INTEGER | 排序 |
| note | TEXT | 策展备注 |

---

## 5. 与现有小镇表的关系

现有表不应推倒重来。

| 现有表 | 保留用途 | 与新模型关系 |
|---|---|---|
| `agents` | 小镇居民事实账本 | 后续可同步到 `residents` 或直接作为居民表 |
| `tasks` | 任务记录 | task 产出 asset |
| `scores` | 评分记录 | 可映射为 review |
| `feedback_log` | skill 沉淀队列 | review 到 skill 的处理日志 |
| `suggestions` | 北北奏折和治理建议 | 可展示在久久小镇生活流 |
| `assets` | 当前资产列表 | 升级为唯一资产表 |
| `logs` | 小镇事件 | 可用于小镇生活流 |

建议策略：

```text
短期：保留现有表，新增 works/methods/asset_links 等策展表。
中期：逐步增强 assets 表，成为统一资产源。
长期：将居民、任务、作品、skill、评价统一为可查询图谱。
```

---

## 6. town_output 入库规则

### 6.1 自动扫描

扫描目录：

```text
D:\北北\99-town\town_output
```

根据扩展名判断类型：

| 扩展名 | asset_type |
|---|---|
| `.html` | html |
| `.md` | markdown |
| `.png/.jpg/.webp` | image |
| `.mp4/.mov` | video |
| `.mp3/.wav` | audio |

### 6.2 类型推断

根据文件名和内容关键词初步分类：

| 关键词 | work_type |
|---|---|
| 海报、每日一图、配色 | image |
| 四格、漫画 | comic |
| 日报、夜话、文章、推文 | article |
| 产品、需求、体验报告 | report |
| 技能、检查清单、沉淀 | method |

### 6.3 入库状态

每个扫描到的文件默认进入资产库：

```text
asset.status = private
```

北北或久久精选后，创建 work：

```text
work.status = published
```

---

## 7. v0.1 页面清单

### 7.1 必做页面

| 页面 | 目标 |
|---|---|
| 首页 | 建立久久光合社的第一印象 |
| 作品长廊列表 | 按类型展示精选作品 |
| 作品详情页 | 展示作品、居民、skill、评价 |
| 久久小镇入口 | 展示小镇和居民状态 |
| 资产库后台列表 | 管理 `town_output` 入库资产 |

### 7.2 可后置页面

| 页面 | 后置原因 |
|---|---|
| 天机阁首页 | 需要先整理 skill 和 method 数据 |
| 居民详情页 | 需要独立居民记忆和评价数据更稳定 |
| 意图工坊 | 需要权限和调度机制稳定 |
| 游戏化小镇 | 需要先确定信息架构和内容数据 |

---

## 8. v0.1 不做什么

- 不开放访客直接调用居民。
- 不做复杂登录系统。
- 不做完整电商/支付。
- 不做社群功能。
- 不做复杂 3D 小镇。
- 不把同一内容复制到多个板块。

---

## 9. 下一步

建议下一步按这个顺序执行：

1. 为 `town_output/` 建资产索引脚本。
2. 生成第一批 `assets` 元数据。
3. 基于 `docs/curation/featured-works.json` 中的 13 个手选作品生成 `works`。
4. 做作品长廊低保真页面。
5. 做作品详情页低保真页面。
6. 再补天机阁的 method/skill 数据。

这会让久久光合社先成为一个可看的策展站，再逐步变成可互动、可复刻、可调用居民的小镇系统。
