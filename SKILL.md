---
name: doc-atlas
description: Turn one or more documents (PDF / Word / PPT / Excel / HTML / EPUB / Markdown…) into a single, polished, offline, self-contained HTML dashboard — a left fixed table-of-contents tree and right-side modular content (executive summary, big key-metric cards, logic/relationship diagrams, data charts, conflict comparison, chapter details). Use when the user has document files and wants to "distill / merge / visualize / make sense of / lay out / build a panel from" them. It highly distills the key points so the reader need not open the source, keeps every claim traceable back to file + page, and foregrounds the logic/relationship diagram as the centerpiece.
---

# 多格式文档 → 可视化信息面板（doc-atlas）

把一份或多份文档（PDF / Word / PPT / Excel / HTML / EPUB / Markdown…）**归一化为 Markdown 中间层 → 跨文件梳理合并成一个统一知识结构（model.json）→ 渲染成一个离线可开的单文件 `dashboard.html`**：左侧固定目录树，右侧按需出现的模块化内容（关键指标卡、核心要点、逻辑/关系图、数据图表、冲突对照、章节详情）。

**三条核心价值（一切取舍围绕它们）**：
1. **高度炼化**——读者看面板就够了，不必再翻原文；若做得杂乱无章，那还不如直接看 PDF。
2. **准确可溯**——零幻觉、每个数字/结论都能指回「哪个文件第几页」，不确定就诚实标注。
3. **逻辑图是主角**——把文档的核心逻辑/因果/关系做成醒目的大图，这是本工具最大的卖点。

**路径模型（重要）**：命令在**用户的文档文件夹里**运行（即当前工作目录 `cwd`，里面放着用户的 PDF/文档），**不要 `cd` 进 skill 目录**。脚本一律用绝对路径 `"$SKILL_DIR/scripts/..."` 调用；所有产物写到用户文件夹下的 `./doc-atlas-out/`。`SKILL_DIR` = 本 skill 的安装目录（即本 `SKILL.md` 所在目录），开工前设一次：

```bash
SKILL_DIR="$HOME/.claude/skills/doc-atlas"   # 本 skill 安装目录（按实际位置改）
OUT="./doc-atlas-out"                          # 产物目录，落在用户当前文件夹下
```

---

## 何时用本 skill

- 用户给了文档文件，并希望「梳理内容 / 生成面板 / 可视化总结 / 理清逻辑 / 多文件合并梳理」。
- 单文件也可用（跳过跨文件去重部分）；多文件时跨文件合并是核心价值。

**输出放哪**：默认建在用户当前文件夹下的 `./doc-atlas-out/`（里面含 `workspace/`、`model.json`、`dashboard.html`）；若用户指定了目录就沿用。

---

## 工作流总览（六步）

0. **定语言 + 扫描确认**：**先问用户要哪种语言的面板**，再扫描当前文件夹、与用户确认纳入哪些文件。
1. **归一化**：每个被确认的文件 → `workspace/<name>/{content.md, assets/, meta.json}`（PDF 表格走结构化抽取保数值列）。
2. **梳理合并（核心）**：通读、去重 / 识冲突 / 互补 / 判关系，重组成 `model.json`；写完做**完整性批判第二遍**并填 `distillation_report` 自检。
3. **事实核查（对抗式）**：对**对外/高风险**文档，派 subagent **回原件证伪**，修正 `❌/➖` 后再渲染（低风险单文件可内联自查）。
4. **渲染**：`model.json (+workspace) → dashboard.html`（单文件、离线）。
5. **自检交付**：无头校验无报错、抽查溯源，并把炼化体检/核查结论讲给用户。

---

## 阶段零：先定语言，再扫描确认（顺序不能反）

### 0.1 先问输出语言（关键，必须在扫描之前做）

`/doc-atlas` 一旦生效，**第一件事不是扫描，而是问用户：想要哪种语言的面板？** 这一步决定了后面所有 AI 撰写的文案（执行摘要、要点、章节标题与小结、图表标签）用什么语言。用 AskUserQuestion（或直接提问）给出常见选项：

> 你想要哪种语言的信息面板？ **① 中文 ② English ③ 跟随文档原语言 ④ 其他（请说明）**

把用户的选择记为 `UI_LANG`，并贯穿全程：
- `meta.ui_lang` = 用户选择；`meta.content_lang` = 文档主要语言（二者可不同）。
- **所有 AI 撰写的叙述性文案一律用 `UI_LANG`**（哪怕原文是另一种语言，也要在炼化时翻译/转写成 `UI_LANG`）。
- **事实保真不受影响**：数字、专有名词、逐字引用（quotes）保留原文，可在 `UI_LANG` 里补一句释义；溯源角标（文件名/页码）原样。
- 用户没明确表态时，缺省 = 跟随文档主要语言。

**确认了语言之后**，再进入 0.2 扫描。

### 0.2 扫描目标文件夹

```bash
/usr/bin/python3 "$SKILL_DIR/scripts/scan_docs.py" .        # 或换成用户指定的文件夹路径
```

`scan_docs.py` 递归列出当前文件夹里所有候选文档（pdf / word / ppt / excel / html / epub / md / txt…），自动跳过隐藏目录、`.venv`、`node_modules`、`doc-atlas-out` 以及含 `SKILL.md` 的 skill 包目录。

### 0.3 与用户确认要纳入哪些

拿到清单后**必须与用户确认，不要擅自全量开跑**：

1. 把编号清单（文件名 / 类型 / 大小）原样呈现给用户。
2. 明确询问：**这些是否都要纳入梳理整合？要去掉哪些？有没有遗漏（比如埋在子目录里的）？**
3. 多文件时顺便问一句它们大概什么关系（同主题不同版本 / 时间序列 / 总分 / 互相引用），有助于阶段二定合并策略。
4. **等用户确认后**，用确认过的文件清单进入阶段一。

---

## 阶段一：归一化为 Markdown 中间层

### 1.0 环境检查与按需安装（首次使用，必须先征得用户同意）

归一化需要 markitdown + pymupdf（装在 `.venv` 里，约 290MB）。**先静默检查是否已就绪**：

```bash
VENV_PY="$SKILL_DIR/.venv/bin/python"
if [ -x "$VENV_PY" ] && "$VENV_PY" -c "import markitdown, fitz" 2>/dev/null; then
  echo READY
else
  echo NEED_INSTALL
fi
```

- 输出 `READY` → 环境已装好，直接进入 1.1，**不要重复安装**。
- 输出 `NEED_INSTALL` → **停下来，向用户说明并征求同意，绝不擅自安装**：
  > 首次使用需要安装文档解析依赖（markitdown + PyMuPDF，约 290MB，1–2 分钟，装到 `$SKILL_DIR/.venv`）。是否现在安装？
  - **用户同意** → 跑 `bash "$SKILL_DIR/scripts/bootstrap.sh"`，装完再继续 1.1。
  - **用户拒绝** → **不安装、也不继续**。明确告诉用户：没有这些依赖就无法解析文档，本次到此为止，等愿意安装时再来。不要尝试绕过或用系统 python 硬跑（markitdown 装不进系统 3.9）。

### 1.1 逐个文件归一化

对**每个被确认的**输入文件跑归一化（脚本用绝对路径调，人留在用户文件夹里）：

```bash
"$VENV_PY" "$SKILL_DIR/scripts/normalize.py" "输入文件.pdf" --out "$OUT/workspace/"
# 产出： $OUT/workspace/<name>/{content.md, assets/, meta.json}
```

三件套各司其职，缺一不可（Markdown 本身会丢页码和图片，靠后两者补回**溯源能力**）：
- `content.md` — markitdown 输出的正文；**PDF 的表格另由 PyMuPDF 按行×列结构化抽取，追加在文末「结构化抽取的表格」一节**（保住数值列），是阶段二的唯一阅读对象。
- `assets/` — 用 PyMuPDF 等额外提取的有信息量图片（图表 / 流程图 / 示意图），供 model 的 `image` block 引用。
- `meta.json` — 标题→页码/位置映射、文件名、页数、字数、文档类型、日期、`tables`（表格登记：页码+行列数+置信度）、`table_extraction`（整体表格抽取状态），是所有 `SourceRef` 能指回"哪个文件第几页"的依据。

**表格保真很关键**：很多"看似原文没写"的数值，其实是 markitdown 把表格列打乱/丢列造成的。`normalize.py` 用 `page.find_tables()` 把表格重抽成二维 Markdown 表并登记置信度——阶段二据此判断「原文确实没有」还是「我们没抽好、要回看 PDF 原图」（见阶段二纪律）。

**扫描版 PDF 的 OCR 回退**：当 PDF 是扫描件、markitdown 提不出文字层时，`normalize.py` 会自动走 OCR 回退把图片页转成文本（OCR 结果置信度较低，阶段二引用时倾向标注「（待核实）」）。

> 用 `$VENV_PY`（py3.11）做归一化；render / selfcheck 一律用系统 `/usr/bin/python3`（见阶段四、五）。两者不要混用。

---

## 阶段二：信息梳理与多文件整合（核心，AI 亲自做）

通读 `$OUT/workspace/*/content.md` 与各自 `meta.json`，**重新组织内容，而不是逐文件摘要**。详细方法见 `references/merge-and-structure.md`，要点：

- **去重**：同一概念/事实在多个文件出现 → 合并为一个节点，`sources` 标注所有出处。
- **识冲突**：同一事实说法不一致（数字/日期/结论）→ 不要静默选一个，写进 `conflicts[]`，列出各方 `positions` 与出处，给 `resolution` 和 `confidence`。
- **互补**：A 讲概述、B 讲细节 → 组织成同一章节的不同层级，而非两个并列章节。
- **判文件关系**：同主题不同版本？时间序列？总分？互相引用？据此定合并策略；多文件时填 `file_relations.mermaid`。

把合并结果写成唯一中间产物 **`$OUT/model.json`**（顶层 IR）。字段语义、调色板与完整示例见 `references/model-schema.md`，机器约束见 `schema/model.schema.json`：

- 必填：`meta`、`files`、`outline`、`chapters`；其余（`highlights`/`conflicts`/`keypoints`/`diagrams`/`charts`/`quotes`/`file_relations`/`distillation_report`）**按需出现**——给了才渲染，这就是右侧模块化的自由度。
- `outline` 是合并后的统一主题树（`1` / `1.1` / `1.2.1`），不是按文件罗列；每个一级 `outline` 节点对应一个 `chapters[]`。
- `chapters[].blocks` 从调色板自由编排：`paragraph` / `callout` / `keypoints` / `metric` / `quote` / `diagram`(Mermaid) / `chart`(Chart.js) / `table` / `image` / `subsections`。某章节有没有逻辑图/图表，全看它含不含对应 block。
- 每个 `SourceRef` 至少给 `page` 或 `loc` 之一，`file_id` 必须匹配某个 `files[].id`。

### 2.1 三层阅读模型（炼化 = 让人一眼看懂）

让每份 model.json 天然分三层，模板按层级默认展开/折叠，这样读者「10 秒抓主线、细节按需展开」：

| 层级 | 内容 | model.json 落点 | 默认呈现 |
|---|---|---|---|
| **L1 概览** | ≤5 句执行摘要 + 4–6 个核心数字 | `meta.executive_summary` + `highlights[]` | 首屏直接显示 |
| **L2 要点** | high/medium 要点、核心逻辑图、核心图表 | `keypoints[]` / `diagrams[]` / `charts[]` | 默认显示 |
| **L3 细节** | 章节正文、参数表、工况表、质保表 | `chapters[].blocks` | 章节体默认折叠，点开才看 |

- **`highlights[]`（顶层，强烈建议给）**：把全篇 4–6 个最关键数字做成首屏大号指标卡（如「8 小时 / 纯电驻车」「<3% / 占整车重」「22 万 / 10 年累计节省」）。这是"极少内容获取主要"的最直接实现。
- 章节内也可用 `metric` block 给局部关键数字一个大字号出口。
- 关键数字不要只埋在段落里——能抽成 `highlights` / `metric` / `chart` 的就抽出来。

### 2.2 逻辑/关系图是主角（核心卖点，务必做足）

- 通读后先问自己：**这份文档集的核心逻辑是什么？**（因果链 / 流程 / 决策树 / 组织关系 / 价值传导）把它做成 `diagrams[]` 里一张**主图**——清晰、信息量足、能讲清主线。宁可一张扎实的大图，也别堆十张零碎小图。
- 模板会把 `diagrams[]` / `file_relations` **整行大尺寸渲染并支持点击放大**，所以图要经得起放大看：节点命名清楚、箭头有动词标签、层次分明。
- 凡内容里出现**关系或顺序**就考虑画图（`flowchart` 流程/因果、`mindmap` 概念分解、`sequenceDiagram` 时序）；只是几条并列事实则用 `keypoints`，别硬画。
- 多文件时 `file_relations.mermaid` 画文件之间的关系（版本迭代/引用/互补）；内容主题关系进 `diagrams[]`。

### 2.3 图表语义不要丢

- **区间数据用区间表达**：如噪音「≥70 / <50」别画成定值 70/50（会误导）；用区间/堆叠，或在标签标「≥ / <」。
- **不同口径的并列柱要标清**：如「一次性投资 vs 10 年累计」并列时，标题/坐标轴/caption 必须醒目标注口径，避免被误读为同期可比。

### 2.4 炼化纪律（让"高度炼化"看得见、靠得住）

**"高度炼化" ≠ "变短"**，它要同时满足：①跨文件/跨章去重；②升维归纳（从"原文怎么说"升到"结论/因果/对比"）；③关键信息（数字/标准号/参数/前置条件）零丢失且溯源；④重要性分级反映"对决策的重要性"。

- **完整性批判第二遍（必做）**：第一遍写完 model.json 后，**重读 source 自问**："哪个**重要数字 / 前置条件 / 结论**原文有、model 却没有？" 把找到的补回去，循环到"再读一遍也挑不出新的"。
- **填 `distillation_report` 并自检阈值**（顶层可选字段，强烈建议给，交付时讲给用户）：
  - `section_coverage` **必须 = 100%**（每个源章节至少映射到一个 outline 节点），缺章回去补。
  - `todo_ratio > 10%` → **先别交付**：多半是表格数值列没抽好（看 `meta.tables` / `table_extraction`），回查 PDF 原图能补的补回来。
  - `claims_with_source < 100%` → 有无源声明，要么补源要么删。
  - `compression_ratio` 落在 ~3:1 到 ~10:1 才算"既炼又不漏"；接近 1:1 = 只是搬运。
- **"待核实" 只用于「原文确实没写」**，**严禁用于「本工具没抽出来」**。后者要回查原件（`meta.json` 的页码 / `assets/` 原图 / 用 Read 工具 pages 参数读原 PDF）补回真值；分不清就当成"要回查"，不要默默标"待核实"后被当成"原文没有"。

**纪律**：一切结论溯源、不编造；超长文档**分批读**再汇总，别漏后半部分。写完建议**对照 `schema/model.schema.json` 自检**结构合法再进入阶段三。

---

## 阶段二·五：事实核查（对抗式，回原件证伪）

draft 出 `model.json` 后、渲染之前，**加一道独立核查闸**——目标是**找错**，不是确认。按风险/规模分档，别对所有任务都开多 agent：

| 场景 | 核查方式 |
|---|---|
| 单文件、< ~15 页、低风险 | 主 AI **内联自查**（完整性批判第二遍即可，省 token） |
| 单文件、销售/合同/对外/高风险材料 | **1 个 subagent 专职核查** |
| 多文件 / 长文 / 有冲突表 | **按章节 fan-out 多个 subagent 并行核查 + 1 个汇总**，重点查 `conflicts[]` 完整性、跨文件数字一致性 |

给核查 agent 的指令要点：
- **对抗框架**："逐条挑 model.json 里的数字/事实/结论，**默认它可能错**，去原文找反证。"
- **核查清单**：每条 high/medium 的数字与结论，判定 `✅准确 / ⚠️偏差 / ❌错误或幻觉 / ➖遗漏`，并附原文出处。重点查三类：① 幻觉（原文没有却写了）② 遗漏（原文有却没收/误标待核实）③ **派生数字验算**（亲手重算节省额/CO₂/续航小时等，核口径自洽）。
- **关键纪律：核查 agent 必须能读原始文件（Read 工具 pages 参数 / 原图），不能只读 `content.md`**——因为 content.md 可能本身丢了表格数值列，只读它会和阶段二犯同样的盲区。

**核查结果回流**：
- `❌ 错误 / 幻觉` → **必须改**，改完重渲染。
- `➖ 遗漏（原文确有）` → 补进 model.json。
- `⚠️ 偏差 / 口径问题` → 修正，或在文案/`callout` 里显式标注口径。
- 把核查摘要写进 `distillation_report.fact_check`（如"已核 23 条、修正 3 条、补回 2 条遗漏"），阶段五讲给用户。

---

## 阶段三：渲染单文件面板

用**系统 python**（stdlib only）渲染：

```bash
/usr/bin/python3 "$SKILL_DIR/scripts/render_dashboard.py" "$OUT/model.json" "$OUT/dashboard.html" \
  --workspace "$OUT/workspace/" --self-check
```

- 输出是**单文件** `dashboard.html`，**离线可打开**：所有 CSS/JS 内联，所有图片读取后替换为 `data:` URI 内嵌；**仅 Chart.js 与 Mermaid 走 CDN**。
- 图片 `src` 先按绝对路径找，找不到再按 `workspace/src` 找；缺图不报错，渲染占位并在 stderr 警告。
- 退出码 0 = 成功；非 0 = 失败并在 stderr 说明。加了 `--self-check` 会渲染后自动调用 selfcheck（即可省略阶段四的手动调用）。
- 默认 `--template` = `scripts/../templates/dashboard.html`，默认 `--workspace` = `model.json` 所在目录；上面显式写 `--workspace` 更稳。

---

## 阶段四 / 五：自检与交付

若阶段三没带 `--self-check`，单独跑：

```bash
/usr/bin/python3 "$SKILL_DIR/scripts/selfcheck.py" "$OUT/dashboard.html"   # 加 --json 输出机器可读报告
```

- playwright 无头加载，捕获 console error / pageerror，统计 Mermaid 渲染出的 svg 数与 Chart canvas 数，校验注入 JSON 可解析、关键 section 存在；有错误则退出码非 0。
- 浏览器获取顺序：先 `chromium.launch()`，失败再 `channel="chrome"`，再失败降级为静态解析检查并 warn。

**人工抽查**（自检脚本不能替代）：树节点引用的来源页码在 `meta.json` 里真实存在；要点里的数字与原文一致；去重没把不同概念误合并。

**交付**：把 `$OUT/dashboard.html` 给用户，并用 3–5 句话说明：讲了什么、几个文件、最关键的结论/冲突，以及**炼化体检与核查结论**（章节覆盖率、待核实占比、已核/修正了几条）——让用户看得见"为什么可以信这份面板、而不必回去翻 PDF"。

---

## 约束

- **不编造**：所有结论必须能溯源到某个文件的页码/位置；做不到就别写。
- **"待核实" 严格界定**：只用于「原文确实未写 / 来自 OCR / 多源冲突未定」；**不得**用于「本工具没抽出来」——后者必须回查原件补回真值。
- **分批**：单文件 ~100 页以上或 `content.md` 超长时分批读取再汇总，避免遗漏后半部分。
- **语言策略**：`meta.ui_lang`（界面 + AI 撰写文案）跟随**用户在阶段零选定的语言**；`meta.content_lang` 跟随文档主要语言；逐字 `quotes` 保留原文。
- 禁用 localStorage；除 Chart.js / Mermaid 两个 CDN 外不得有其它外链或网络请求。
- **界面风格固定为「纸本」皮肤**：暖米纸 + 蓝色强调（重点/风险保留朱红）+ 无衬线正文 + 数字高亮 + 松密度 + 日读，由 `templates/dashboard.html` 决定；AI 不改皮肤、不提供外观切换面板。

---

## 参考文件索引

- `references/merge-and-structure.md` — 阶段二跨文件去重/冲突/互补/文件关系判定、三层阅读模型、逻辑图主角化、炼化体检与核查的操作指南。
- `references/model-schema.md` — `model.json` 的人类可读说明与完整示例（含 Block 调色板、`highlights`、`metric`、`distillation_report` 用法）。
- `schema/model.schema.json` — `model.json` 的 JSON Schema（draft-07），用于结构自检。
- `scripts/scan_docs.py` — 阶段零：扫描目标文件夹列出候选文档（stdlib only，供与用户确认）。
- `scripts/bootstrap.sh` — 用 uv 建 `.venv`（py3.11）并安装 markitdown + pymupdf。
- `scripts/normalize.py` — 阶段一：单文件 → `workspace/<name>/{content.md, assets/, meta.json}`（含 PDF 表格结构化抽取与扫描件 OCR 回退）。
- `scripts/render_dashboard.py` — 阶段三：`model.json (+workspace)` → 单文件 `dashboard.html`（stdlib only，图片 base64 内嵌）。
- `scripts/selfcheck.py` — 阶段五：playwright 无头校验 `dashboard.html`（stdlib + playwright）。
- `templates/dashboard.html` — 固定单文件前端模板（内联 CSS/JS + `__DASHBOARD_DATA__` JSON 注入位）。
