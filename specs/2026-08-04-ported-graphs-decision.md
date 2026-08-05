# 由 ai-driven-dashboard 移植圖表 — 決定紀錄

**日期:** 2026-08-04
**狀態:** 已決定要移植邊啲,未設計、未實作

## 1. 來源

`ai-driven-dashboard`(本機 `~/Downloads`,未入版本控制)—— 另一個 dashboard,同名嘅
`ManagementDashboard framework` 出身,但行嘅係完全唔同嘅架構。

## 2. 點解唔可以整份搬

兩邊嘅**數據來源**根本唔同:

| | ai-driven-dashboard | ManagementDashboard |
|---|---|---|
| 架構 | 本機 `server.py` + SSE,有後端 | 靜態 GitHub Pages |
| 代碼數據 | 直接行本機 git repo | 夜更 GitHub API collector |
| PM 數據 | **Excel workbook** → `read-project-info.py` → `project-info.json` | 冇 |
| 缺陷 | `defects.csv` | 各 repo 手寫 `defect.md` |

兩個直接後果:

- **Scrum Master 分頁成塊都係 Excel 餵嘅。** Sprint、assignee、planned start/end、
  action item、放假表 —— 一樣都唔係由 git 嚟。呢度冇對應嘅上游,所以成個分頁搬唔過。
- **凡係要後端嘅一律唔要:** SSE 即時更新、activity log、NLQ「問 dashboard」面板、
  snapshot compare、history 時間序列、排程報告。靜態站冇後端,而 history 嗰條路
  [burndown 設計](2026-08-04-project-burndown-chart-design.md) §2.2 已經否決咗。

搬得過嘅係**個別圖表** —— 渲染同埋聚合邏輯 —— 前提係重新指去我哋自己收到嘅數據。

## 3. 揀咗嘅七張圖

| 圖 | 來源 | 餵佢嘅數據 | 改動 | 依賴 |
|---|---|---|---|---|
| Timeline / Gantt | `js/projectinfo.js:79` | `plan.due_max`、`plan.history[0]`、`issues.milestones[].due`、`plan.open_tasks[].due` | **去掉 sprint bands**(冇 sprint 數據);保留 today 線、月份格線、milestone 緊急度着色 | burndown |
| 逐 repo 趨勢線 | `js/charts.js:306` | `tasks[]`(repo / date / additions / deletions) | 一 repo 一條線 + 虛線組合平均;chip 撳住淨睇一個 repo | 冇 |
| SPI 進度指數 | `js/utils.js:154` | `plan.done/total` ÷ 時間流逝 % | 完成度旁邊一個 badge | burndown |
| Bus factor | `js/ui.js:54` | 每 module 嘅 contributor 數 | **要改 collector**(見 §3.1) | 冇 |
| 對比矩陣 | `js/ui.js:248` | 現有各 repo 指標 | 可排序 repo × 指標表,RAG 上色 | 冇 |
| Churn 對稱柱狀 | `js/charts.js:102` | `tasks[].additions` / `.deletions` | 圍住零軸鏡像,逐月 | 冇 |
| 管理四象限 | `js/ui.js:895` | 現有指標重新組合 | Delivery / Schedule / Team / Quality 四格 + RAG 點 | burndown(Schedule 格) |

### 3.1 Bus factor 要改 collector

`collect_github.py:116` 個 GraphQL query **已經攞緊** `files{nodes{path}}`,但淨係用嚟
判斷 `touches_tests`(:441)同 `forbidden-files` violation(:595-598)—— **冇寫出去**。
`tasks[]` 冇任何 path 欄位。

所以 module 級嘅 bus factor 要 collector 新出一個聚合(例如
`repo_meta[repo].modules = {<top-level dir>: {contributors: N}}`)。**冇額外 API 成本**
—— 啲 path 本身已經喺手,淨係多出一個欄位。

退一步嘅 repo 級版本(每個 repo 幾多 contributor)由 `tasks[].author` 直接得,零改動,
但訊號弱好多:14 個 repo 嘅組合裏面,「邊個 module 得一個人掂過」先係要答嗰條問題。

## 4. 否決咗嘅

| 項 | 理由 |
|---|---|
| Burndown 圖本身 | 我哋自己嗰個[設計](2026-08-04-project-burndown-chart-design.md)紮實過:行 `plan.md` 嘅 git 歷史,**追溯**而且**無狀態**。佢嗰個係 Excel 出嚟嘅 sprint 快照 |
| Capacity forecast(assignee × sprint) | 冇 sprint 數據 |
| Health index 綜合分 | 綜合分遮住嘅嘢多過佢答嘅;現有逐 repo RAG chip 已經做緊同一件事 |
| Activity heatmap | 資訊密度低過現有嘅每週圖 |
| 缺陷分項、milestone 清單、進度分軌 | 已經有(品質分頁 / milestone bar / `plan.sections[]`) |
| Action item、放假表 | 冇上游 |
| SSE、activity log、NLQ、snapshot compare、排程報告 | 要後端 |

## 5. 次序

**Burndown 已經出咗街**([實作計劃](plans/2026-08-04-project-burndown.md),六個 task
2026-08-04 全部埋單),所以 `plan.due_max` 同 `plan.history` 今日已經喺 `metrics.json`
入面。Gantt、SPI、同四象限個 Schedule 格 —— 三個唯一有依賴嘅 —— 冇嘢等緊。

下一步:**先寫設計文件**,七張圖一份,講清楚每張擺喺現有四個分頁邊度、空狀態點做、
以及 bus factor 個 `repo_meta[].modules` schema 點加。跟返 burndown 同
defect-register 一樣嘅做法 —— 設計、計劃、然後先寫代碼。
