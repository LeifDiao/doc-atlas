# model.json 数据模型说明

`model.json` 是 **阶段二（信息梳理与多文件整合）唯一的产出物**，也是渲染器
`scripts/render_dashboard.py` 唯一的输入 IR。渲染器把它注入到
`templates/dashboard.html` 的数据位，前端 app 通过
`JSON.parse(document.getElementById('dashboard-data').textContent)` 读取整个对象。

设计原则一句话：**顶层每个可选字段就是一个"按需出现"的模块**——给了就渲染，不给就不渲染。
因此"这份文档集要不要画图 / 要不要图表 / 要不要冲突区"的自由度，完全由 AI 在产出
`model.json` 时决定，而不是写死在模板里。

机器可读约束见 `schema/model.schema.json`（JSON Schema draft-07）。本文件是它的人类可读版，
末尾附一个**完整可渲染示例**。

---

## 1. 顶层结构

| 字段 | 必填 | 说明 |
|---|---|---|
| `meta` | 是 | 面板元信息：标题、语言、统计、执行摘要 |
| `files` | 是（≥1） | 源文件清单，每个有稳定 `id`，被所有溯源引用 |
| `highlights` | 否（强烈建议 4–6） | 首屏关键指标卡，大号数字条（L1 概览层） |
| `file_relations` | 否 | 文件关系图，**仅多文件时有意义**；单文件可为 `null` 或省略 |
| `distillation_report` | 否（建议给） | 炼化体检表，交付时讲给用户的可信度指标 |
| `conflicts` | 否 | 跨文件冲突点对照 |
| `keypoints` | 否（建议 5–10） | 全局重点要点 |
| `diagrams` | 否 | 全局关系图区（Mermaid，整行大尺寸 + 点击放大） |
| `charts` | 否 | 全局数据图表区（Chart.js） |
| `quotes` | 否 | 金句卡片池，可被章节内 `quote` block 引用 |
| `outline` | 是（≥1） | 统一大纲树（合并后的主题树，**不是按文件罗列**） |
| `chapters` | 是（≥1） | 一级章节详情区，每个对应一个一级 `outline` 节点 |

> Schema 对每个对象都开了 `additionalProperties:false`，所以**字段名必须零偏差**；
> 但凡契约里出现过的字段都被接受，不会更严。

---

## 2. 公共类型

### 2.1 `SourceRef`（溯源引用，贯穿全文）

```jsonc
{ "file_id": "f2", "page": 12 }          // 有页码
{ "file_id": "f1", "loc": "Slide 4" }    // 无页码用 loc："§2.1" / "Slide 4" / "Sheet1!B2"
```

- `file_id` **必填**，且必须匹配某个 `files[].id`（schema 不强制做交叉引用校验，但你必须保证自洽）。
- `page` / `loc 至少给一个（在已知的前提下）；两者都允许为 `null`。
- 这是面板"每条结论都能指回哪个文件第几页"的能力来源——任何要点 / 大纲节点 / 区块都可挂 `sources`。

### 2.2 枚举

- `importance`：`"high" | "medium" | "low"`（重要度配色）
- `confidence`：`"high" | "medium" | "low"`（冲突结论置信度）
- `tone`：`"info" | "warn" | "success" | "danger"`（callout 配色）

---

## 3. 各字段详解

### 3.1 `meta`

```jsonc
{
  "title": "面板标题",
  "content_lang": "zh",          // 文档主要语言
  "ui_lang": "zh",               // 界面语言（跟随用户），缺省 = content_lang
  "generated_at": "2026-06-05",  // ISO 日期，可为 null（渲染器可补当天）
  "stats": {                     // file_count 必填，其余可为 null
    "file_count": 2, "total_pages": 47, "total_words": 18600, "reading_minutes": 62
  },
  "executive_summary": ["...", "..."]   // 3–5 句，至少 1 句
}
```

### 3.1b `highlights`（首屏关键指标卡，强烈建议）

全篇 4–6 个最关键数字，渲染成首屏大号数字条（紧跟执行摘要）。`MetricItem`：

```jsonc
"highlights": [
  { "value": "8 小时", "label": "纯电驻车制冷", "sources": [{ "file_id": "f1", "page": 3 }] },
  { "value": "< 3%",   "label": "系统占整车重量", "sub": "满载工况", "importance": "high",
    "sources": [{ "file_id": "f1", "page": 7 }] },
  { "value": "22 万",  "label": "10 年累计节省 / 车", "sub": "纯节油口径" },
  { "value": "5–8 年", "label": "静态回收期" }
]
```

- `value` 大字号（保留单位/区间/符号，如 `"< 3%"`、`"5–8 年"`）；`label` 一句话说明；`sub` 可选附注（口径/条件）。
- 关键数字不要只埋在段落里——能上首屏的就抽进 `highlights`。章节内的局部关键数字用 `metric` block（同一 `MetricItem` 形态）。

### 3.1c `distillation_report`（炼化体检表，建议给）

把"这份面板是否真的把原文炼化到位"变成看得见的指标，交付时讲给用户，是"可以信它、不必回去翻 PDF"的依据：

```jsonc
"distillation_report": {
  "source_words": 3901,                 // 原文字数（各 meta.json 汇总）
  "compression_ratio": "约 6:1",        // 原文字数 : model 正文字数；~3:1–10:1 为宜
  "section_coverage": "11/11 章已映射", // 每个源章节至少落到一个 outline 节点；须 100%
  "claims_with_source": "100%（0 条无源）",
  "todo_ratio": "3 处待核实 / 约 60 数据点 ≈ 5%",  // >10% 先回查表格再交付
  "derived_numbers": 4,                 // 自己推算的数字条数（应全部带推算依据）
  "unmapped_source_blocks": [],         // 源里没被收进 model 的内容（应为空或给理由）
  "fact_check": "已核 23 条、修正 3 条、补回 2 条遗漏（阶段二·五）"
}
```

所有字段可选；给了就在面板"炼化体检"区以小指标展示。阈值纪律见 `merge-and-structure.md` §9。

### 3.2 `files`

每个文件：`id`(稳定)、`name`、`type`(`pdf|docx|pptx|xlsx|html|epub|md|…`，不封闭枚举)、
可选 `pages|words|date|role`。`role` 用一句话写它在文件集中的角色（"概述" / "最新版" /
"时间序列起点"），多文件梳理时尤其重要。

### 3.3 `file_relations`（仅多文件）

`{ "mermaid": "...", "note": "..."|null }`。画各文件如何覆盖 / 引用 / 互补 / 迭代。

### 3.4 `conflicts`

同一事实在不同文件说法不一致时，**不要静默选一个**，而是列出来：

```jsonc
{
  "id": "c1", "topic": "2024 全年营收",
  "positions": [                              // ≥2 个出处不同的说法
    { "value": "38 亿（外推）", "source": { "file_id": "f1", "loc": "Slide 9" } },
    { "value": "41.2 亿（实际）", "source": { "file_id": "f2", "page": 12 } }
  ],
  "resolution": "采用白皮书口径，因其更新更晚且为实际值",  // 可为 null
  "confidence": "high"                                    // 可为 null
}
```

### 3.5 `keypoints`（建议 5–10）

`{ id, text, kind?, importance, sources[] }`。`kind` 是自由标签（`结论|数字|定义|风险|…`）。

### 3.6 `diagrams` / `charts`（全局区）

- `diagrams[]`：`{ id, title, kind?, mermaid, caption?, sources[] }`，`kind` 如 `flowchart|mindmap|sequence`。
- `charts[]`：`{ id, title, caption?, chartjs, sources[] }`，其中 `chartjs` 必须是一个**合法的
  Chart.js 配置对象**（至少含 `type` 和 `data`，可选 `options`）。

全局区的图 / 图表可在章节里用 `diagram_id` / `chart_id` **复用**，避免重复定义。

### 3.7 `quotes`

`{ id, text, attribution?, source }`。金句池，章节里用 `{ "type":"quote", "quote_id":"q1" }` 引用。

### 3.8 `outline`（统一大纲树）

递归结构 `OutlineNode = { id, title, summary?, importance, sources[], children? }`：

- `id` 用层级编号 `"1" / "1.1" / "1.2.1"`，渲染成左侧目录树。
- 这是**合并去重后的主题树**，不是把每个文件的目录拼起来。
- `children` 可任意深度（示例做到 3 层）。

### 3.9 `chapters`（一级章节详情）

`Chapter = { id, title, importance, sources[], blocks[] }`：

- `id` **对应某个一级 `outline` 节点的 id**（如 outline 的 `"1"` ↔ chapter 的 `"1"`）。
- `blocks` 是**有序区块数组**，AI 从下面的调色板自由编排——这是右侧内容灵活度的来源。
  某章节有没有逻辑图 / 图表 / 表格，完全取决于它含不含对应 block。

---

## 4. Block 调色板

渲染器按 `type` 逐块渲染。`quote` / `diagram` / `chart` 三类各有"引用全局"和"内联"两种写法。

| `type` | 形态 | 关键字段 |
|---|---|---|
| `paragraph` | 段落 | `md`，可选 `sources` |
| `callout` | 提示框 | `tone`(必填)、`md`(必填)、可选 `title`、`sources` |
| `keypoints` | 要点列表 | `items[]`，每项 `{ text, importance, sources? }` |
| `metric` | 大号指标卡组 | `items[]`，每项 `{ value, label, sub?, importance?, sources? }`，可选 `title`、`sources` |
| `quote`（引用） | 引用金句池 | `quote_id` → 指向 `quotes[].id` |
| `quote`（内联） | 就地金句 | `text`(必填)、可选 `attribution`、`source` |
| `diagram`（引用） | 引用全局图 | `diagram_id` → 指向 `diagrams[].id` |
| `diagram`（内联） | 就地 Mermaid | `mermaid`(必填)、可选 `title`、`caption`、`sources` |
| `chart`（引用） | 引用全局图表 | `chart_id` → 指向 `charts[].id` |
| `chart`（内联） | 就地 Chart.js | `chartjs`(必填)、可选 `title`、`caption`、`sources` |
| `table` | 表格 | `columns[]`、`rows[][]`(单元格为 string 或 number)、可选 `title`、`sources` |
| `image` | 图片 | `src`(必填，workspace 下相对/绝对路径)、可选 `caption`、`source` |
| `subsections` | 子节点摘要卡 | `items[]`，每项 `{ id, title, summary, importance, sources }` |

> **图片处理**：`image.src` 写 workspace 下的相对路径（如 `f2/assets/revenue_trend.png`）或绝对路径。
> 渲染器先按绝对路径找、再按 `workspace/src` 找，读到后**替换为 `data:` URI 内嵌**；
> app JS 永远只拿到 dataURI，离线可打开。缺图不报错，渲染占位并 stderr 警告。

> **metric block**：把章节内的局部关键数字做成大号卡片组，`items` 与顶层 `highlights` 同为 `MetricItem`：
> ```jsonc
> { "type": "metric", "title": "核心经济账", "items": [
>     { "value": "22 万", "label": "10 年累计节省 / 车", "sub": "纯节油口径", "sources": [{ "file_id": "f1", "page": 10 }] },
>     { "value": "5–8 年", "label": "静态回收期" }
> ]}
> ```

---

## 5. 完整可渲染示例

下面是一个**多文件**场景（2 个 files、1 个 file_relations、1 个 conflict、6 个 keypoints、
1 个 Mermaid diagram、1 个 chart、1 个 quote、3 层 outline、2 个 chapters），章节 `blocks`
覆盖了 **全部 11 种 block 变体**（paragraph / callout / keypoints / quote(引用) / quote(内联) /
diagram(引用) / diagram(内联) / chart(引用) / table / image / subsections），其中含一个指向
workspace 相对路径的 `image` block。本示例已用 `schema/model.schema.json` 校验通过，且所有
`file_id / quote_id / diagram_id / chart_id` 与 chapter↔outline 对应关系均自洽。

```json
{
  "meta": {
    "title": "2024 年云业务季度复盘与年度展望",
    "content_lang": "zh",
    "ui_lang": "zh",
    "generated_at": "2026-06-05",
    "stats": {
      "file_count": 2,
      "total_pages": 47,
      "total_words": 18600,
      "reading_minutes": 62
    },
    "executive_summary": [
      "两份文件分别为 Q3 季度复盘（PPT）与年度战略白皮书（PDF），共同围绕云业务增长展开。",
      "全年营收口径在两份文件中存在不一致（38 亿 vs 41 亿），已在冲突区标注并倾向采用较新的白皮书口径。",
      "核心结论：云业务连续四个季度双位数增长，但毛利率受基础设施投入拖累，2025 年以提效为主线。",
      "建议优先关注三大风险：客户集中度、汇率波动、数据中心电力成本。"
    ]
  },
  "files": [
    {
      "id": "f1",
      "name": "Q3-云业务复盘.pptx",
      "type": "pptx",
      "pages": 22,
      "words": 5200,
      "date": "2024-10-15",
      "role": "时间序列起点 / 季度视角"
    },
    {
      "id": "f2",
      "name": "2024-云业务年度白皮书.pdf",
      "type": "pdf",
      "pages": 25,
      "words": 13400,
      "date": "2025-01-20",
      "role": "最新版 / 主干口径"
    }
  ],
  "file_relations": {
    "mermaid": "flowchart LR\n  f1[\"Q3 复盘 PPT\\n季度视角\"] -->|数据汇入更新| f2[\"年度白皮书 PDF\\n主干口径\"]\n  f2 -.->|修正全年营收口径| f1",
    "note": "白皮书发布晚于季度复盘，全年口径以白皮书为准；季度趋势细节仍以复盘 PPT 为来源。"
  },
  "conflicts": [
    {
      "id": "c1",
      "topic": "2024 全年云业务营收",
      "positions": [
        {
          "value": "约 38 亿元（截至 Q3 外推估算）",
          "source": { "file_id": "f1", "loc": "Slide 9" }
        },
        {
          "value": "41.2 亿元（全年实际）",
          "source": { "file_id": "f2", "page": 12 }
        }
      ],
      "resolution": "采用白皮书 41.2 亿元口径：发布更晚且为实际而非外推，季度复盘为 Q3 时点的全年预估。",
      "confidence": "high"
    }
  ],
  "keypoints": [
    {
      "id": "k1",
      "text": "云业务连续四个季度营收双位数同比增长，Q4 增速 18%。",
      "kind": "数字",
      "importance": "high",
      "sources": [
        { "file_id": "f2", "page": 8 },
        { "file_id": "f1", "loc": "Slide 5" }
      ]
    },
    {
      "id": "k2",
      "text": "2024 全年云业务营收 41.2 亿元，占公司总营收 34%。",
      "kind": "数字",
      "importance": "high",
      "sources": [{ "file_id": "f2", "page": 12 }]
    },
    {
      "id": "k3",
      "text": "毛利率同比下降 2.1 个百分点，主因新建数据中心折旧与电力成本上升。",
      "kind": "结论",
      "importance": "high",
      "sources": [{ "file_id": "f2", "page": 15 }]
    },
    {
      "id": "k4",
      "text": "前五大客户贡献营收占比达 47%，客户集中度风险显著。",
      "kind": "风险",
      "importance": "medium",
      "sources": [{ "file_id": "f2", "page": 19 }]
    },
    {
      "id": "k5",
      "text": "“云原生优先”定义为：新增工作负载默认部署于容器与 Serverless 平台。",
      "kind": "定义",
      "importance": "medium",
      "sources": [{ "file_id": "f1", "loc": "Slide 14" }]
    },
    {
      "id": "k6",
      "text": "2025 年战略主线由“规模扩张”切换为“单位经济模型提效”。",
      "kind": "结论",
      "importance": "high",
      "sources": [{ "file_id": "f2", "page": 22 }]
    }
  ],
  "diagrams": [
    {
      "id": "d1",
      "title": "云业务增长驱动因素关系图",
      "kind": "flowchart",
      "mermaid": "flowchart TD\n  A[客户上云需求] --> B[营收增长]\n  C[基础设施投入] --> D[毛利率承压]\n  B --> E[2025 提效战略]\n  D --> E\n  E --> F[单位经济模型优化]",
      "caption": "营收增长与成本承压共同推动 2025 年提效战略。",
      "sources": [
        { "file_id": "f2", "page": 21 },
        { "file_id": "f1", "loc": "Slide 18" }
      ]
    }
  ],
  "charts": [
    {
      "id": "ch1",
      "title": "四个季度云业务营收（亿元）",
      "caption": "数据来源以白皮书全年口径校准。",
      "chartjs": {
        "type": "bar",
        "data": {
          "labels": ["Q1", "Q2", "Q3", "Q4"],
          "datasets": [
            {
              "label": "营收（亿元）",
              "data": [9.1, 9.8, 10.6, 11.7]
            }
          ]
        },
        "options": {
          "responsive": true,
          "plugins": { "legend": { "position": "top" } }
        }
      },
      "sources": [{ "file_id": "f2", "page": 9 }]
    }
  ],
  "quotes": [
    {
      "id": "q1",
      "text": "增长不是目的，可持续的单位经济模型才是。",
      "attribution": "CFO 在年度战略章节",
      "source": { "file_id": "f2", "page": 23 }
    }
  ],
  "outline": [
    {
      "id": "1",
      "title": "业务表现",
      "summary": "2024 全年与各季度的营收、增速与毛利表现。",
      "importance": "high",
      "sources": [
        { "file_id": "f2", "page": 8 },
        { "file_id": "f1", "loc": "Slide 5" }
      ],
      "children": [
        {
          "id": "1.1",
          "title": "营收与增速",
          "summary": "连续四个季度双位数增长，全年 41.2 亿元。",
          "importance": "high",
          "sources": [{ "file_id": "f2", "page": 9 }],
          "children": [
            {
              "id": "1.1.1",
              "title": "季度营收明细",
              "summary": "Q1–Q4 逐季营收与环比。",
              "importance": "medium",
              "sources": [{ "file_id": "f1", "loc": "Slide 6" }]
            }
          ]
        },
        {
          "id": "1.2",
          "title": "盈利能力",
          "summary": "毛利率同比下降 2.1pp。",
          "importance": "high",
          "sources": [{ "file_id": "f2", "page": 15 }]
        }
      ]
    },
    {
      "id": "2",
      "title": "战略与风险",
      "summary": "2025 提效主线与三大风险。",
      "importance": "high",
      "sources": [{ "file_id": "f2", "page": 22 }],
      "children": [
        {
          "id": "2.1",
          "title": "2025 战略主线",
          "summary": "由规模扩张切换为提效。",
          "importance": "high",
          "sources": [{ "file_id": "f2", "page": 22 }]
        },
        {
          "id": "2.2",
          "title": "主要风险",
          "summary": "客户集中度、汇率、电力成本。",
          "importance": "medium",
          "sources": [{ "file_id": "f2", "page": 19 }]
        }
      ]
    }
  ],
  "chapters": [
    {
      "id": "1",
      "title": "业务表现",
      "importance": "high",
      "sources": [
        { "file_id": "f2", "page": 8 },
        { "file_id": "f1", "loc": "Slide 5" }
      ],
      "blocks": [
        {
          "type": "paragraph",
          "md": "2024 年云业务**连续四个季度双位数增长**，全年营收按白皮书口径为 41.2 亿元，占公司总营收约 34%。",
          "sources": [{ "file_id": "f2", "page": 12 }]
        },
        {
          "type": "keypoints",
          "items": [
            {
              "text": "Q4 同比增速 18%，为全年最高。",
              "importance": "high",
              "sources": [{ "file_id": "f2", "page": 8 }]
            },
            {
              "text": "毛利率同比下降 2.1 个百分点。",
              "importance": "high",
              "sources": [{ "file_id": "f2", "page": 15 }]
            }
          ]
        },
        {
          "type": "chart",
          "chart_id": "ch1"
        },
        {
          "type": "table",
          "title": "逐季营收与环比",
          "columns": ["季度", "营收（亿元）", "环比"],
          "rows": [
            ["Q1", 9.1, "—"],
            ["Q2", 9.8, "+7.7%"],
            ["Q3", 10.6, "+8.2%"],
            ["Q4", 11.7, "+10.4%"]
          ],
          "sources": [{ "file_id": "f1", "loc": "Slide 6" }]
        },
        {
          "type": "callout",
          "tone": "warn",
          "title": "口径提示",
          "md": "全年营收存在 38 亿 / 41.2 亿两种口径，详见冲突区，本章统一采用白皮书 41.2 亿。",
          "sources": [{ "file_id": "f2", "page": 12 }]
        },
        {
          "type": "image",
          "src": "f2/assets/revenue_trend.png",
          "caption": "白皮书原图：四季度营收趋势曲线。",
          "source": { "file_id": "f2", "page": 9 }
        },
        {
          "type": "subsections",
          "items": [
            {
              "id": "1.1",
              "title": "营收与增速",
              "summary": "连续四个季度双位数增长，全年 41.2 亿元。",
              "importance": "high",
              "sources": [{ "file_id": "f2", "page": 9 }]
            },
            {
              "id": "1.2",
              "title": "盈利能力",
              "summary": "毛利率同比下降 2.1pp，主因基础设施折旧。",
              "importance": "high",
              "sources": [{ "file_id": "f2", "page": 15 }]
            }
          ]
        }
      ]
    },
    {
      "id": "2",
      "title": "战略与风险",
      "importance": "high",
      "sources": [{ "file_id": "f2", "page": 22 }],
      "blocks": [
        {
          "type": "paragraph",
          "md": "2025 年战略主线由“规模扩张”切换为“单位经济模型提效”，强调云原生优先与成本结构优化。",
          "sources": [{ "file_id": "f2", "page": 22 }]
        },
        {
          "type": "diagram",
          "diagram_id": "d1"
        },
        {
          "type": "diagram",
          "title": "风险传导（内联）",
          "mermaid": "flowchart LR\n  R1[客户集中度] --> X[营收稳定性]\n  R2[汇率波动] --> X\n  R3[电力成本] --> Y[毛利率]\n  X --> Z[2025 提效目标]\n  Y --> Z",
          "caption": "三大风险对营收稳定性与毛利的传导路径。",
          "sources": [{ "file_id": "f2", "page": 19 }]
        },
        {
          "type": "quote",
          "quote_id": "q1"
        },
        {
          "type": "quote",
          "text": "把每一分基础设施投入都换成可衡量的单位产出。",
          "attribution": "战略章节小结",
          "source": { "file_id": "f2", "page": 24 }
        }
      ]
    }
  ]
}
```

---

## 6. 产出 `model.json` 时的自查清单

1. `files[].id` 唯一稳定；所有 `SourceRef.file_id` 都能在 `files` 中找到。
2. 每个 `chapters[].id` 等于某个**一级** `outline` 节点的 `id`。
3. `quote_id / diagram_id / chart_id` 引用的全局对象确实存在。
4. `charts[].chartjs` 是合法 Chart.js 配置（有 `type` 和 `data`）；Mermaid 文本语法正确。
5. `image.src` 指向 workspace 内真实存在的图片（相对 workspace 或绝对路径）。
6. 枚举值只用允许集合：`importance/confidence ∈ {high,medium,low}`、`tone ∈ {info,warn,success,danger}`。
7. 字段名零偏差（schema `additionalProperties:false`，多写字段会校验失败）。
8. 单文件场景：`file_relations` 给 `null` 或省略；不要硬造文件关系。
