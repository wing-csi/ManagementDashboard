# 逐 repo Plan Timeline 條

**日期:** 2026-08-04
**狀態:** 設計已批,未實作
**來源:** [移植決定紀錄](2026-08-04-ported-graphs-decision.md) Group B(Gantt + SPI + 四象限)

## 1. 問題

[Burndown 卡](2026-08-04-project-burndown-chart-design.md)答到「剩低幾多、追唔追得上」,
但答唔到 **「邊件事、幾時到期」**。`plan.md` 每個 task 都寫住 `due:`,收集端亦已經
連 `priority` 同 `#bug` 一齊放咗入 `plan.open_tasks[]` —— 但成個 dashboard 冇一個地方
畫得出佢哋喺時間軸上面嘅位置。今日想知邊四個 task 過咗期,要自己去 repo 揭 `plan.md`。

同時,完成度 % 講唔到**快定慢**。「40% 做完」喺項目行咗 20% 同 80% 嘅時候意思啱啱相反。

## 2. 決定

| 決定 | 揀咗 |
|---|---|
| Scope 單位 | 逐個有 `plan_file` 嘅 repo 一條,擺入該 repo 現有嗰張 burndown 卡 |
| Marker 來源 | `plan.open_tasks[].due` |
| Marker 編碼 | **淨係**用日期急切度上色;`priority` / `#bug` / 標題入 tooltip |
| 進度指標 | SPI = 完成 % ÷ 時間流逝 %,同「剩幾多日」、「幾多個過期」一齊擺 header |
| 渲染 | 純 CSS 百分比定位,**唔用 Chart.js** |
| 上游改動 | **零** —— 冇新 collector 代碼、冇新 config key、冇新 schema 欄位 |

### 2.1 點解唔係 portfolio Gantt(一 repo 一行)

原本嘅諗法係一條共用時間軸,一個 repo 一行,睇晒 14 個項目點樣重疊。**實測否決**:

- `config.toml` 得**兩個** repo 設咗 `plan_file`(`:17`、`:138`)。一條「portfolio」
  Gantt today 就係兩行。
- GitHub milestones 喺呢個 org **完全係空**:14 個 repo 全部 `milestones: 0`、
  `open_total: 0`、`closed_total: 0`。同 [defect-register](2026-07-30-defect-register-design.md)
  同 burndown 度量到嘅係同一組數。所以 marker 唔可以由 `issues.milestones[]` 嚟。
- 退一步用 `plan.sections[]` 做行都唔得:AIFlowTesting 成份 plan 得**一個** section
  (`Issue board`,11 個 task 全部喺入面)。

即係話「跨項目比較」嘅價值今日係零,而**單一 repo 嘅 task due 反而好密** ——
AIFlowTesting 11 個 task 每個都有 `due:`,由 `2026-07-10` 到 `2026-09-18`。
所以價值喺**一個 repo 之內**,唔係之間。呢個同 burndown 一模一樣嘅結論,
所以行返同一個 pattern:一個 plan repo,一張卡。

### 2.2 點解四象限縮成一行 header

移植清單原本有個 Delivery / Schedule / Team / Quality 四格卡。逐格對返我哋嘅數據:

| 格 | 我哋有乜 |
|---|---|
| Time | 就係呢條 timeline + SPI 本身 |
| Resource | assignee 分配要 Excel PM 數據,冇;淨返 top-author %,喺 `tasks[].author` |
| Scope | `plan.done/total` + defects —— 已經喺「項目」chips 同「品質」分頁 |
| Quality | commit 質素 %、defects、redlines —— 四樣全部已經喺「品質」分頁 |

四格入面一格重複咗本設計其餘部分,一格填唔滿,兩格重複緊現有分頁。原版有價值係因為
佢個 dashboard 冇第二個橫切視角;我哋有。所以**淨係留低唔喺畫面上嘅嗰個信號** ——
排程 —— 做 header 一行。

## 3. 數據

全部已經喺 `metrics.json` 入面,**唔使改 collector**:

| 嘢 | 來源 |
|---|---|
| 計劃起點 `start` | `plan.history[0].date` |
| 計劃終點 `due` | `plan.due_max`,要過日曆驗證 |
| Markers | `plan.open_tasks[].due` |
| 完成度 | `plan.done` / `plan.total` |
| 今日 | `state.data.generated_at.slice(0, 10)` —— 同 burndown 同一個定義 |

**`open_tasks` 得未打勾嘅,而且封頂 50。** 兩件事都要喺卡上講:打完勾嘅 task
會喺條線度**消失**,所以呢條線係「仲有乜嘢喺前面」,唔係「成個項目嘅里程碑」。
task 一路做完,條線一路變疏 —— 就算冇任何嘢 slip 都一樣。唔講嘅話,
「變疏」睇落似「順利」,但佢兩者根本唔同。

## 4. 時間軸點框

**軸 ≠ 計劃窗口。** 兩樣分開計:

- **計劃窗口** = `start` → `due`。畫成條底 bar,SPI 亦都係用呢兩個日計。
- **軸** = `min(start, 最早嘅有效 marker)` → `max(due, 最遲嘅有效 marker, 今日)`。

`due` 用唔到嘅時候**根本冇計劃窗口** —— 冇終點就冇一個「應該幾時完」。條 bar 改為
由 `start` 拉到今日,讀做「行咗幾耐」而唔係「計劃咗幾耐」,而軸嘅右邊由最遲嗰粒
marker 同今日話事。呢個分別要企硬:畫一條去到今日嘅 bar 而唔講,同扮咗個死線
係今日,喺畫面上係一模一樣嘅。

點解軸要闊過窗口:一個 `due:` 早過 plan 開檔日、或者遲過 `due_max` 嘅 task,
兩樣都係真嘢。軸唔撐開嘅話嗰粒 marker 就會靜靜哋跌出畫面 —— 正正係
burndown `514608b` 修過嗰種「冇畫,又冇講」嘅錯。今日一定要喺軸入面,
否則「過唔過期」冇參照點。

`MAX_DAYS`(3653)照樣管住成條軸,理由同 [`burndown.js:16`](../docs/js/burndown.js) 一樣。

## 5. SPI

```
elapsedPct = (今日 − start) / (due − start)
SPI        = (done / total) / elapsedPct
```

| SPI | 講法 |
|---|---|
| ≥ 1 | 追得上 |
| 0.8 – 1 | 落後 |
| < 0.8 | 嚴重落後 |

**冇 SPI 嘅情況要分得開,同 burndown 個 `idealReason` 用返同一套字**,唔另開一套詞:

- `due` 用唔到(冇寫 / 唔係有效日曆日 / 唔遲過 `start`)→ 冇 SPI,講返係邊個原因。
- 今日 **早過或者等於** `start` → `elapsedPct ≤ 0`,除唔到。出「未開始」,唔出數字。
  (`0/0` 同 `x/0` 兩個都要喺呢度擋死,唔可以流去畫面變 `NaN` 或者 `Infinity`。)

仲有一個要擋嘅:**`total === 0`**。`parse_plan_markdown()` 一個 checkbox 都冇就回
`None`,所以正路入唔到呢度,但一個 `0/0` 流咗落 `done / total` 就係 `NaN`,
而 `NaN` 過得所有 band 比較,最後靜靜哋顯示做「嚴重落後」。冇 task 唔係落後。

Header 另外兩個數:

- **剩幾多日** = `due − 今日`。負數就講「遲咗 N 日」,唔好顯示負數。
  `due` 用唔到就冇呢個數 —— 冇終點就冇「剩幾多」,唔可以拉今日或者最遲嗰粒
  marker 嚟頂替。
- **幾多個過期** = `open_tasks` 入面 `due` 有效而且早過今日嘅數目。呢個同 `due`
  無關,所以就算冇 `due_max` 一樣照出 —— 過咗期就係過咗期。

## 6. Marker

急切度**淨係睇日期**,同「項目」分頁 milestone 行現有嘅 `late` 邏輯一致:

| 距今 | 類 |
|---|---|
| < 0 | 過期 |
| ≤ 7 日 | ≤7d |
| ≤ 14 日 | ≤14d |
| 其他 | later |

`priority`(P0/P1/P2)、`#bug`、同 task 標題入 `title=` tooltip。一粒 marker 一個視覺變數:
11 粒擠喺一條窄軸上面,加多個形狀或者外框就開始讀唔到,而「過唔過期」先係佢主要嘅工。

**同一日嘅 task 合成一粒**,tooltip 列晒(沿用原版 `pmTimelineHTML` 嘅 group-by-date)。

**`due:` 唔係有效日曆日嘅 task 要掉,而且要數低。** collector 個 `PLAN_DUE_RE` 只夾
*形狀*(`\d{4}-\d{2}-\d{2}`),`04b57d2` 加嘅日曆驗證係做喺 `due_max` 度,
`open_tasks[].due` 冇過同一關 —— 所以 `2026-02-30` 入得嚟。靜靜哋掉咗會令
「過期」個數虛低,所以卡上要寫明「N 個 task 嘅 due: 唔係有效日期」。

## 7. 代碼結構

| 檔 | responsibility |
|---|---|
| `docs/js/plan-dates.js`(新) | 由 `burndown.js` 抽出:`realDate`、`spanDays`、`MAX_DAYS`、`resolvePlanWindow(plan, today) -> {start, due, dueReason}` |
| `docs/js/burndown.js`(改) | 改為 import 上面嗰個。**純行為保留** |
| `docs/js/timeline.js`(新) | 純整形,冇 DOM:`timelineStrip(plan, today) -> {...}` |
| `docs/js/render-timeline.js`(新) | `timelineHTML(plan, today) -> string`。唔掂 DOM、唔 querySelector |
| `docs/js/render-burndown.js`(改) | 將上面個 string 塞入佢已經砌緊嗰張卡 |
| `docs/css/dashboard.css`(改) | `.tl-*` classes |

依賴係**單向**嘅:`plan-dates` ← `timeline` ← `render-timeline` ← `render-burndown`。
Chart 嘅生命週期唔郁。

### 7.1 點解要抽 `plan-dates.js`

`realDate`、`spanDays`、`MAX_DAYS` 同 `due_max` 驗證而家係 `burndown.js` 嘅私有嘢,
而且係用咗三個修正 commit 先至啱嘅(`04b57d2`、`514608b`、`9be6968`)。條 timeline
要**一模一樣**嘅語意 —— 兩份各自演化嘅日期驗證,遲早會喺同一個 `metrics.json` 上面
畫出兩個唔同嘅結論。抽出嚟係唯一唔會走樣嘅做法。

抽嘅時候 `test_burndown_js.py` 就係 regression guard:行為冇變,佢應該一個字都唔使改。

### 7.2 點解唔用 Chart.js

Chart.js 4 冇 Gantt / range-bar 型。原版都係用純 CSS 百分比定位(`gantt-bar`,
`left:X%`),我哋跟返:唔使加 CDN script,而且 print / PDF 出到嚟。

## 8. 空狀態

每個都各有講法,一個都唔准靜靜哋消失(沿用 burndown spec §7 嘅規矩):

| 情況 | 行為 |
|---|---|
| 冇設 `plan_file` | 冇卡(維持現狀) |
| 冇 `history`(舊 `metrics.json`) | 成張卡收埋(維持現狀嘅向後兼容) |
| `history_error` 著 | Burndown 已經出咗聲,唔再出條 timeline |
| `due` 用唔到 | Bar 由 `start` 去今日,冇 SPI;caption 用返三個 `dueReason` 講法 |
| 今日 ≤ `start` | 有 bar 有 marker,SPI 出「未開始」 |
| 冇一個 task 有 `due:` | Bar + 今日線,冇 marker,caption 講明 |
| `done === total` | Caption 講「冇嘢剩低」——同「冇 due:」係兩件事,唔可以共用一句 |
| 有 task 個 `due:` 唔係有效日曆日 | 嗰粒唔畫,caption 數低幾多粒 |

## 9. 唔跟 window selector

同 burndown 同「項目進度」一致 —— 30/60/90/180 唔影響呢條線。README 已經寫明
呢部分獨立於 window,新增嘅嘢跟同一個規矩。

## 10. 測試(TDD,先寫測試)

| 檔 | 覆蓋 |
|---|---|
| `scripts/test_timeline_js.py`(新) | `timelineStrip()` 單元測試,喺瀏覽器行,做法沿用 `test_burndown_js.py`:軸撐開過 `due_max` / 早過 `start`;SPI 三個 band;`elapsedPct ≤ 0` 出「未開始」唔出 `Infinity`;過期數目;同日 marker 合併;無效日曆日掉走兼數低 |
| `scripts/test_frontend_timeline.py`(新) | Playwright 渲染,做法沿用 `test_frontend_burndown.py`:八個空狀態逐個有自己嘅字;今日線畫咗;marker 上色分類 |
| `scripts/test_burndown_js.py`(唔改) | `plan-dates.js` 抽取嘅 regression guard |
| `scripts/fixtures/metrics-fixture-burndown.json`(擴充) | `open_tasks[]` 加返啲 `due` / `priority` / `bug` |

基準:今日 `python -m pytest scripts/ -q` 係 **330 passed**。每個 task 只加唔減。

## 11. 已知限制

- **條線淨係講未做嘅嘢。** `open_tasks` 冇打勾嘅先入,所以做完嘅 milestone 唔會留低
  痕跡。呢個係 §3 講嘅取捨,唔係 bug,但卡上要寫。
- **50 個上限。** 一份超過 50 個未做 task 嘅 plan,條線會唔齊。今日兩個 plan repo
  離呢個數好遠。
- **解像度得日。** 同一日嘅 task 分唔開,亦都唔需要分。
- **`due_max` 通常係推斷出嚟嘅**(最遲嗰個 task due),除非有人喺 heading 明文寫。
  即係話「終點」多數係一個 task 嘅日期,唔係一個宣告咗嘅死線 —— 同 burndown
  一樣嘅限制,同一個位要標明。
- **SPI 假設進度同時間係線性。** 一份前重後輕嘅 plan,早期 SPI 會偏低。佢係一個
  訊號,唔係一個判決。
