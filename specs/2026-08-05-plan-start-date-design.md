# Plan 起點:三層 fallback

**日期:** 2026-08-05
**狀態:** 已實作(`f37c3eb` … `22b3908`),全套測試 411 passed
**改動範圍:** `plan-dates.js` 嘅 `resolvePlanWindow()` + 兩個新 collector 欄位 + 一個新 `plan.md` marker
**影響:** [Burndown 卡](2026-08-04-project-burndown-chart-design.md) 同
[Plan timeline 條](2026-08-04-plan-timeline-design.md) 兩張圖一齊跟

## 1. 問題

條軸嘅起點而家係 `plan.history[0].date`([`plan-dates.js:61`](../docs/js/plan-dates.js)),
即係**第一日有 commit 改過 `plan.md`**。呢個唔係項目開始。

實測 AIFlowTesting:條軸由 `2026-07-28` 起,而嗰日就係 PR
`docs: make plan.md issue board a machine-readable checklist` —— 即係 `plan.md`
變成 checklist 格式嗰日。同一個 repo 嘅 tag 早喺 `2026-06-16` 就有。條軸缺咗
六個星期,而畫面上冇任何嘢講得出呢件事。

三個下游全部跟住錯:

| 跟起點嘅嘢 | 出面 |
|---|---|
| 條軸左邊 | `burndownSeries()` 個 `dayRange(start, end)` |
| 理想線 | 錨喺 `history[0].total`,由 index 0 拉到 `dueIndex` |
| SPI | `elapsed = (今日 − start) / (due − start)` |

即係話「起點遲咗」會令理想線**過斜**、SPI **過靚**。兩樣都係向樂觀嗰邊錯。

## 2. 決定

| 決定 | 揀咗 |
|---|---|
| 起點來源 | 三層:`plan.md` 個 `start:` → repo 第一個 commit → 第一個 plan 觀測 |
| repo 開檔點計 | **第一個 commit**(唔係 `createdAt`)—— 語意上先至係「第一日有嘢做」 |
| `start:` 遲過第一個觀測 | **唔採用**,跌落下一層,並且喺卡上講明 |
| 起點到第一個觀測之間 | **留白**,唔畫線 |
| 理想線 / SPI | **一齊跟**新起點 |
| Schema | `schema_version` 維持 **2** —— 兩個新 key 都係 optional |

### 2.1 點解 `start:` 遲過觀測就唔信佢

一個遲過第一個觀測嘅 `start:` 係同數據直接矛盾:`plan.md` 話「六月一號開始」,
但 git 話五月三號已經 commit 過呢份 plan。採用佢就要**切走**真正量度過嘅觀測點,
而個圖會睇落完全正常 —— 冇線,又冇講,正正係 burndown spec §7 唔准嘅嘢。

但係靜靜哋 `min()` 落去一樣唔得:`plan.md` 打錯咗嘅嘢會永遠冇人知。所以取
**唔採用 + 出聲**,同 codebase 現有嘅 `dueReason` 一套做法一致。

### 2.2 點解留白唔 carry-back

Carry-back 一條平線好睇,而且條線由頭到尾連住。但佢等於斷言「開檔第一日就已經
有 N 個 task、一個都未做」,而我哋**冇量度過**嗰段時間。呢個同收集端刻意唔 pad
平坦日子(`plan_history.py` docstring)係同一個原則:一條作出嚟嘅線同一條真線,
喺畫面上分唔開。

好彩實作上係免費嘅 —— `burndownSeries()` 個 `cur` 喺撞到第一個觀測之前係 `null`,
`remaining` / `scope` 已經 push `null`,而 `spanGaps: false` 令 Chart.js 唔會駁過去。

### 2.3 點解 SPI 一齊跟

SPI 讀做「用咗幾多時間,做完幾多嘢」。時間嘅分母應該係**計劃窗口**,唔係「我哋
幾時開始有記錄」。錨返第一個觀測會令一個做咗三個月、上個星期先開 `plan.md` 嘅
項目報一個近乎完美嘅 SPI。

代價要企硬講清楚:**呢個改動會令 SPI 即刻變差**,尤其係啲老 repo。AIFlowTesting
由 `2026-06-16` 計起、今日 `2026-08-05`、`done = 0`,SPI 就係 `0`。呢個係準確嘅。

## 3. 三層解析

`resolvePlanWindow(plan)` 回多兩個欄位:

```
{start, startSource, startReason, due, dueReason}
```

`firstObs = history[0].date`。逐層試,第一個過關嘅贏:

| 層 | 來源 | 過關條件 | `startSource` |
|---|---|---|---|
| B | `plan.start_min` | 真日曆日 **且** `≤ firstObs` **且** `spanDays(佢, firstObs) ≤ MAX_DAYS` | `'plan'` |
| C | `plan.repo_first_commit` | 同上 | `'repo'` |
| A | `firstObs` | 永遠成立 | `'observation'` |

`startReason` **淨係**講「宣告咗但唔採用」,唔係「用咗邊層」——「冇宣告」唔係一個錯:

| 值 | 意思 |
|---|---|
| `null` | 冇宣告 `start:`,或者宣告咗而且採用咗 |
| `'start-unusable'` | 寫咗,但唔係一個畫得出嘅日期 —— 日曆上唔存在,**或者**離遠到畫唔落條軸 |
| `'start-after-history'` | 寫咗,但遲過第一個觀測 |

`'start-unusable'` 一個字覆蓋兩種失敗,係**刻意**同現有嘅 `due-unusable` 對稱:
[`plan-dates.js:67`](../docs/js/plan-dates.js) 個 `usable` 一樣係 `realDate()` 同
`spanDays() ≤ MAX_DAYS` 兩個條件 `&&` 埋一齊。對用家嚟講兩者要做嘅嘢一樣 ——
去 `plan.md` 改返個日期。

C 層失敗**唔會**有 reason:`repo_first_commit` 唔係人手寫嘅,攞唔到就係攞唔到,
冇嘢叫人去改。

### 3.1 MAX_DAYS 要喺起點嗰邊都閘一次

而家個 `MAX_DAYS` 閘淨係驗 `due`([`plan-dates.js:68`](../docs/js/plan-dates.js))。
起點以前係 git 嚟嘅,可信;而家 B 層係人手輸入。一個 `start:1900-01-01` 會叫
`dayRange()` 生四萬幾個日期,而 `dayRange` 個 cap 係**剪尾**嘅 —— 剪走今日同
死線,比起唔採用衰好多。所以每一層 candidate 都要過同一個 span 閘。

`history` 依然係硬前提:零觀測就零卡(`no-history`)。所以 `history[0]` 永遠喺度
做包底,三層永遠有得跌。

## 4. 數據來源(collector)

### 4.1 `start:` marker

同 `due:` 對稱,寫喺 heading:

```markdown
# Issue board start:2026-06-16 due:2026-09-18
```

| 規矩 | 理由 |
|---|---|
| **只認 heading 級** | 一個 task 嘅「開始日」唔係項目起點;`due:` 收 task 級係因為要砌 marker,起點冇呢個需要 |
| 多過一個取 `min()` | 對稱於 `due:` 取 `max()`:最早宣告嘅開始 + 最遲宣告嘅結束 = 最闊嘅宣告窗口 |
| 過日曆驗證 | 同 `due:` 一樣係未驗證嘅外部輸入;`2026-02-30` 過得 regex |
| `_clean_plan_title()` 要 strip | 否則 section title 會帶住 `start:2026-06-16` 出街 |

現有嘅 `_calendar_dues(values, source)` 改名做 `_calendar_dates(values, source, marker)`,
warning 文字帶返 marker 名 —— 兩個 marker 唔可以共用一句講 `due_max` 嘅說話。

輸出:`plan.start_min`(str 或 `None`)。

### 4.2 Repo 第一個 commit

新 module `scripts/repo_start.py`,形狀跟足 `plan_history.py`(注入 client、
唔 import `collect_github`、獨立可測):

```
GET /repos/{repo}/commits?per_page=1
    → 讀 Link header 個 rel="last",攞 page=N
GET /repos/{repo}/commits?per_page=1&page=N
    → 最舊嗰個 commit → commit.committer.date[:10]
```

| 點 | 決定 |
|---|---|
| 成本 | 固定兩個 request,同 repo 大細無關 |
| 冇 `Link` header | = 得一版 = 得一個 commit,佢就係第一個 |
| Branch | **default branch**(唔落 `sha`)—— 呢個係「repo 開檔」,唔係「plan 條 branch 開檔」 |
| 幾時攞 | **淨係**喺有配置 `plan_file` 嘅 repo 攞;冇 plan 嘅 repo 唔使畀呢兩個 request |
| 失敗 | 空 repo(409)、network、Link 解唔到 —— 一律 `None`,靜靜跌落 A 層 |

`GitHubClient` 要加 `rest_json_links(path) -> (parsed, link)`。而家個 `rest_json()`
掉咗 response header,而分頁總數淨係喺 `Link` 度先有。

輸出:`plan.repo_first_commit`(str 或 `None`)。

### 4.3 向後兼容

`schema_version` 維持 **2**。兩個新 key 都係 optional:

- 舊 `metrics.json` 入面兩個 key 都冇 → 兩層都跌 → 行為同今日一模一樣
- 新 `metrics.json` 撞舊前端 → 多咗兩個冇人讀嘅 key,冇影響

## 5. 兩張圖點變

`burndownSeries()` 同 `timelineStrip()` **嘅計算唔使改** —— 兩個都係由
`resolvePlanWindow()` 攞 `start`,新起點自動流落去。

兩個檔各要加一行 pass-through:渲染層要讀 `startSource` / `startReason`,而
兩個 shaper 嘅 return object 唔會自動帶埋。

要改嘅係**字**。現有三句寫死咗「第一個觀測」,而起點而家可以唔係佢:

| 位置 | 而家 | 改做 |
|---|---|---|
| `IDEAL_CAPTION['due-not-after-start']` | `due: 唔遲過第一個觀測,拉唔出理想線` | `due: 唔遲過起點,拉唔出理想線` |
| `NO_SPI['due-not-after-start']` | `due: 唔遲過第一個觀測 — 冇 SPI` | `due: 唔遲過起點 — 冇 SPI` |
| truncated 句 | `歷史已截斷,理想線由現存最早嗰個觀測起計` | 淨係喺 `startSource === 'observation'` 先出 |

最後嗰句要加條件:歷史截斷咗但起點由 `start:` 或者 repo 第一個 commit 話事嘅時候,
理想線**唔係**由「現存最早嗰個觀測」起計,呢句會變成講錯嘢。

新加嘅字:

| 情況 | 講法 |
|---|---|
| `startSource === 'plan'` | `起點:plan.md start:` |
| `startSource === 'repo'` | `起點:repo 第一個 commit` |
| `startSource === 'observation'` | `起點:第一次改 plan.md` |
| `startReason === 'start-unusable'` | `plan.md 個 start: 唔係一個畫得出嘅日期` |
| `startReason === 'start-after-history'` | `start: 遲過第一個觀測,冇採用` |

出處**每次都出**。同一張圖三個起點來源意思完全唔同,唔講嘅話一張由 repo 開檔拉起
嘅圖同一張由 plan 開檔拉起嘅圖,喺畫面上分唔開。

## 6. 代碼結構

| 檔 | 改乜 |
|---|---|
| `docs/js/plan-dates.js` | `resolvePlanWindow()` 加三層解析 + `startSource` / `startReason` + 起點嗰邊嘅 MAX_DAYS 閘 |
| `docs/js/burndown.js` | 兩個 return object 加 `startSource` / `startReason` pass-through,計算唔改 |
| `docs/js/timeline.js` | 同上,連 `EMPTY` |
| `docs/js/render-burndown.js` | 三句字 + 出處 chip |
| `docs/js/render-timeline.js` | 一句字 |
| `scripts/repo_start.py`(新) | `first_commit_date(client, repo) -> str \| None` |
| `scripts/collect_github.py` | `PLAN_START_RE`、`_calendar_dates()` 改名、`_clean_plan_title()`、`GitHubClient.rest_json_links()`、`collect_repo()` 接兩個新欄位 |

依賴維持單向,`repo_start.py` 同 `plan_history.py` 平排,兩個都唔識 `collect_github`。

## 7. 空狀態

沿用 burndown spec §7:一個都唔准靜靜哋消失。

| 情況 | 行為 |
|---|---|
| 冇 `start:`、攞到 repo 第一個 commit | 用 C 層,caption 出 `起點:repo 第一個 commit` |
| 冇 `start:`、攞唔到 repo 第一個 commit | 用 A 層,caption 出 `起點:第一次改 plan.md` |
| `start:` 唔係有效日曆日 | 跌落下一層,caption 同時出 reason 同新起點出處 |
| `start:` 遲過第一個觀測 | 同上 |
| `start:` 早到 span 過 `MAX_DAYS` | 跌落下一層,reason 出 `start-unusable`(同「唔係有效日曆日」共用一句) |
| 起點早過第一個觀測 | 中間留白,兩條線都由第一個觀測先開始畫 |
| 舊 `metrics.json`(兩個 key 都冇) | A 層,同今日一模一樣 |

## 8. 測試(TDD,先寫測試)

基準:今日 `python -m pytest scripts/ -q` 係 **369 passed**(行足 12 分鐘)。
每個 task 只加唔減。

| 檔 | 覆蓋 |
|---|---|
| `scripts/test_repo_start.py`(新) | Link header 解析;單版 repo(冇 Link);空 repo 409;壞 Link;request 數目係 2 |
| `scripts/test_collect_github.py`(擴充) | `start:` 解析;heading-only(task 級唔收);多個取 `min()`;無效日曆日丟棄兼出 warning;title 清理;`due:` 現有行為 regression |
| `scripts/test_plan_dates_js.py`(擴充) | 三層優先次序;`start-unusable`;`start-after-history`;起點嗰邊 MAX_DAYS 閘;C 層失敗冇 reason;舊 `metrics.json` 跌返 A |
| `scripts/test_burndown_js.py`(擴充) | 起點到第一個觀測之間 `remaining` / `scope` 全 `null`;理想線由新起點起、斜率跟住變 |
| `scripts/test_timeline_js.py`(擴充) | SPI 用新起點;bar 由新起點畫;`due-not-after-start` 而家係對起點講 |
| `scripts/test_frontend_burndown.py`(擴充) | 三個出處字句;兩個 `startReason` 字句;truncated 句嘅新條件 |
| `scripts/test_frontend_timeline.py`(擴充) | 改咗嘅 `NO_SPI` 字句 |
| `scripts/fixtures/metrics-fixture-burndown.json`(擴充) | 加 `start_min` / `repo_first_commit`,覆蓋三層各一個 repo |

## 9. 已知限制

- **老 repo 會即刻變紅。** 冇 `start:` 嘅 repo 全部跌落 C 層,條軸可能由一兩年前
  拉起,SPI 插到近 0。呢個技術上準確,而且喺個別 `plan.md` 補返 `start:` 就即刻
  蓋過 —— 但落之前要知會咁。
- **repo 第一個 commit ≠ 呢份 plan 嘅開始。** 一個 repo 入面第二期先開嘅 plan,
  C 層會拉得太前。`start:` 就係為咗呢個 case 而存在,C 層只係一個好過 A 層嘅預設。
- **兩個額外 request。** 逐個有 `plan_file` 嘅 repo 每次收集畀兩個 REST request。
  今日兩個 plan repo,即係 +4。
- **`Link` header 係 GitHub 嘅實作細節。** 佢係文檔化嘅分頁機制,但唔係 response
  body 嘅一部分。佢消失嘅話 C 層靜靜哋跌返落 A —— 冇線索,唯一嘅徵狀係條軸縮返。
- **起點解像度得日。** 同 `history` 一樣,冇需要更幼。
