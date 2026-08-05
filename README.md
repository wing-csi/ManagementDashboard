# ManagementDashboard

一個中央 repo,用 config 連接任意數量嘅 GitHub repos,經 API 讀取 commits + merged PRs,自動判別每個 task 嘅 AI 自動化水平(L1–L5),再出合併 dashboard。目標 repo **唔使改任何嘢**。

```
config.toml ──▶ GitHub GraphQL API ──▶ 分級(label→trailer→author→rules)──▶ metrics.json ──▶ dashboard(線上 https://management-dashboard-emj.pages.dev 經 Cloudflare Access 登入;或本機經 private data repo)
                (commits + merged PRs)
```

## Setup(一次過)

1. 開一個新 repo(例:`ManagementDashboard`),放入呢度全部檔案 → [github.com/new](https://github.com/new)
2. 開 **fine-grained PAT** → [github.com/settings/personal-access-tokens/new](https://github.com/settings/personal-access-tokens/new)
   (路徑:Settings → Developer settings → Personal access tokens → Fine-grained tokens)
   - Repository access:揀晒你要追蹤嘅 repos
   - Permissions → Repository permissions:**Contents: Read-only** + **Pull requests: Read-only**(Metadata 會自動包)
   - 留意:fine-grained 只揀到你自己 / 你所屬 org 名下嘅 repos;追第三者個人帳號嘅 private repo 要改用 [classic token](https://github.com/settings/tokens/new)(`repo` scope)
3. Hub repo 新增 secret `GH_METRICS_TOKEN` → [github.com/wing-csi/ManagementDashboard/settings/secrets/actions](https://github.com/wing-csi/ManagementDashboard/settings/secrets/actions)
   (路徑:hub repo → Settings → Secrets and variables → Actions → New repository secret)
   (如果只追 public repos,可以跳過 2–3,workflow 預設 token 已經夠)

   **要加多個 token?**(例:追第三者 private repo 要 classic PAT,唔想成個 collector 用闊權 token)
   - 同一頁 New repository secret 再開一個,例:`GH_TOKEN_CRM`
   - workflow(`collect.yml`)嘅 collect step `env:` 加一行:`GH_TOKEN_CRM: ${{ secrets.GH_TOKEN_CRM }}`
   - `config.toml` 對應 repo 加:`token_env = "GH_TOKEN_CRM"` — 其他 repos 照用預設 token
   - env 缺失會即刻報錯,唔會靜靜 fallback 用錯 token
4. 改 [`config.toml`](https://github.com/wing-csi/ManagementDashboard/blob/main/config.toml) 加返你嘅 repos
5. **唔使開 Pages** — Phase 0 已經將 publish 步驟由 `collect.yml` 拎走;而家 CI 每日跑 test + collect,結果先寫入 CI runner 嘅 `/tmp`,再 push 去私有 data repo(`wing-csi/ManagementDashboard-data`),唔會出公海。但**停用 Pages 本身仲要人手做**:repo Settings → Pages → Source 揀 None,呢步未必做咗,自己查:
   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" https://wing-csi.github.io/ManagementDashboard/data/metrics.json
   ```
   `404` = 已停用;`200` = 仲喺度出緊街,要即刻去 repo Settings 關 Pages。想睇 dashboard 見下面「線上睇」(Cloudflare Access 登入)或者「Private 模式」(本機 http server)。
6. 開 Cloudflare Pages + Access(想線上睇先需要,做法見下面「線上睇」),然後喺 hub repo 加兩個 secret:`CLOUDFLARE_API_TOKEN`、`CLOUDFLARE_ACCOUNT_ID`
7. 手動 run 一次 `collect` → [Actions tab](https://github.com/wing-csi/ManagementDashboard/actions/workflows/collect.yml) → Run workflow,之後每日自動更新。一次 run 有兩個去向:push 去私有 data repo,同埋 deploy 上 Cloudflare Pages。本機 dashboard 唔會自動起,睇下面「Private 模式」

> 步驟 3、4、7 嘅 link 係呢個 hub(`wing-csi/ManagementDashboard`)嘅;第二個 hub 就將 path 換成自己個 repo。PAT 記得設 expiration 同定期 rotate。

## 版面(五個分頁)

Dashboard 分咗五個分頁。Masthead、四個 filter 同分頁列釘喺頂(sticky),所以
scroll 到幾底都改到 repo / branch / 成員 / window,唔使碌返上去。

| 分頁 | 入面有咩 |
|---|---|
| **總覽** | Management summary(交付狀態 / data health / scope / forecast)、Executive attention、主 KPI、DORA、每週趨勢 |
| **品質** | RAG 燈、品質 × 自動化、各 Level 修復佔比、Defect 追蹤 |
| **項目 & 團隊** | 項目進度(milestones / 延誤 / 建議)、Repo 概覽、貢獻者 |
| **產品 & 發佈** | Roadmap / epics、release readiness、產品採用、客戶成果指標 |
| **Tasks** | 最近 Tasks — 搜尋(title / author / branch)、Level + 狀態篩選、每頁 25 行 |

**分享某個分頁**:URL 後面加 `#quality`、`#projects`、`#product`、`#tasks`(`#overview` 係
預設)。認唔到嘅 hash 會落返總覽。分頁狀態同 `?owner=` 係兩回事 — hash 係
「睇緊邊頁」,`?owner=` 係「filter 緊邊個」,兩者互不干涉,可以一齊用:
`?owner=Wing#quality`。鍵盤:Tab 去到分頁列之後,用 ←/→/Home/End 揀。

**列印**:`@media print` 會強制五個 panel 全部顯示,所以印出嚟仍然係完整報告,
唔會淨係印咗當前分頁。但 Tasks 表格只會印到**已經載入嘅行**(預設 25)— 想印晒
就先㩒幾次「載入更多」。

## 指標字典 — 每個數點計、代表咩

**通用機制**:「今日」= 數據 `generated_at` 嗰日;window(近 30/60/90/180 日)以佢倒數;「前一段」= 緊接之前、同樣長度嘅 window;「週」= ISO 週(星期一開始);repo 下拉 filter 影響所有數字。Task = merged PR,或者冇 associated PR 嘅 direct commit(auto mode,唔會重複計)。

### Management summary

總覽最頂係一層規則式管理摘要,唔係黑箱綜合分。缺 planning scope、Issues 收集失敗或
快照過期時,交付狀態一定係 **Unknown**,唔會當綠燈。已知異常仍然會留喺 Executive
attention 逐項顯示同連返 GitHub / plan file。

| 數字 | 點計 | 防誤導守則 |
|---|---|---|
| Portfolio delivery | 每 repo 先判 On track / At risk / Off track / Unknown,portfolio 取最需要注意嘅狀態 | stale 或缺 planning data 唔會出 On track |
| Data health | `generated_at` 年齡 + top-level errors + `repo_meta[].issues_error` + planning/history 覆蓋 | 超過 48 小時出不可關閉 banner |
| Current plan scope | 所有 plan 現時總 task;有 history 嗰部分再將逐次 `total` 上落分開計 gross added / removed | 無 history 照顯示 current scope,但唔會作 baseline / churn |
| Forecast coverage | 有 planning scope 嘅 repo 入面,幾多個有至少 7 日歷史同正完成速度 | 冇速度就顯示不可用,唔會作一個日期 |

預測公式係 `剩餘 task ÷ 觀測完成速度`,投射日期由最後觀測點向前。history 少、scope
改過或觀測期短會降 confidence;呢個係 trend projection,唔係承諾日期。Scope change 同
forecast 都只食 `plan_file` history,GitHub milestone 本身冇歷史就唔會扮有。

### 主 KPI 行

| 數字 | 公式 | 代表咩 | 留意 |
|---|---|---|---|
| L3+ 自動化佔比 | (L3+L4+L5) ÷ **已分級** tasks × 100 | task 由 agent 主導完成嘅比例 — 成個 dashboard 嘅北極星 | 分母唔包未分級,覆蓋率低時呢個數會失真 |
| 出碼率(近似) | L2–L5 tasks 嘅 additions ÷ 全部 additions × 100 | 代碼產出中 AI 參與嘅行數佔比 | task 級近似:L1 同未分級成個 task 當人手,唔係字面「AI 打咗幾多行」 |
| 已分級 Tasks | window 內有 level 嘅 task 數 | 產出量(已量度部分) | sub 顯示總數 + mode |
| 分級覆蓋率 | 已分級 ÷ 全部 × 100 | 指標可信度 | < 80% 變黃 + 出 alert |
| ▲▼ vs 前一段 | 今段數值 − 前一段數值 | 趨勢方向 | pt = percentage point;前一段冇數就唔顯示 |

### DORA 行

| 數字 | 公式 | 代表咩 | 留意 |
|---|---|---|---|
| 部署頻率 | 部署事件 ÷ 週數。事件來源 fallback:Deployments API → version tags(名 match `tag_pattern`,預設 `^v?\d`)→ Releases | 交付節奏 | < 1 次/週改顯示整數次數 +「平均每 X 週 1 次」;sub 註明來源 |
| Lead Time(至 merge) | merged PR 嘅 (mergedAt − createdAt) 中位數,小時;≥48h 轉日 | 由開 PR 到落 main 嘅速度 | **唔係到 production**;solo self-merge 會好細,有真 review flow 先有比較意義 |
| 回退密度 | 補救 tasks ÷ window 內全部 tasks × 100 | 幾多產出係用嚟補救之前嘅改動,而唔係推進新工作 | 分子分母都係 task,所以 person / repo filter 之下照樣成立。**唔好同 DORA 變更失敗率基準比** — 佢分母係部署次數 |
| MTTR(proxy) | fix / hotfix / revert 前綴 **PR** 嘅 lead time 中位數 | 幾快落到修復 | 只計 PR;direct commit 嘅 fix 冇 lead time |

**回退密度點樣認一個 task 係「補救」**([`isRemediation()`](docs/js/aggregate.js)):任何一個訊號成立就計 —
title 以 `revert` / `rollback` 開頭、title 有 `hotfix` / `regression` / `撤回` / `回退`、
或者 branch 係 `hotfix/*` / `patch/*` / `bugfix/*`。branch 訊號係必要嘅:真正嘅 hotfix commit
叫 `fix: hotfix v2.6.0 — 21 bug fixes`,靠 title 前綴永遠捉唔到。

例外(**唔算**補救):revert 一個 `docs` / `chore` / `style` / `test` / `ci` / `build` commit,
或者 revert 一次撳錯咗嘅 `Merge branch …` — 呢啲係開發途中嘅 churn,冇出過生產。
例外淨係收窄 revert 訊號:hotfix branch 上面一個 `Revert "docs: …"` 仍然計。

已知限制:分不清「revert 一個已出生產嘅 feature」同「revert 一個未 release 嘅 feature」——
collector 冇 task 對 release 嘅歸屬。真正嘅 DORA 變更失敗率需要 per-deployment 記錄,
而 14 個 repo 之中只有 2 個有 tag、0 個有 Deployments API 記錄。

### 自動化水平分佈

光譜條按**全部** task 比例(未分級 = 斜紋);L3 門檻線位置 = (未分級+L1+L2) ÷ 全部。下面每行:L1–L5 嘅 % 以**已分級**做分母,未分級嗰行以全部做分母(所以有 \*)。右上「分級來源」= label / trailer / author / rule / inference 各判咗幾多個 — 代表可信度層級:label/trailer 係明確聲稱,inference 係行為推斷。

### 每週圖

Bar = 該週 task 數(按 level 疊,週一起計,冇數嘅週補零);黑線 = 該週 L3+ ÷ 該週已分級 × 100(右軸)。

### 異常提醒(全部閾值)

| 條件 | 顏色 |
|---|---|
| 最後兩個有數嘅週,L3+ 佔比環比跌 ≥10pt / 升 ≥10pt | 紅 / 藍 |
| 分級覆蓋率 < 80% | 黃 |
| 本段 L3+ ≥30% 而前一段 <30%(突破里程碑) | 藍 |
| 近兩週 L4+L5 = 0,而 window 內曾經有 | 黃 |
| 修復佔比較前一段升 ≥15pt 且本段 ≥30% | 黃 |
| 每類治理 violation 一條(見治理 section) | 紅線紅 / 警告黃 |
| N 個 task 嘅 level 聲稱同 PR 行為矛盾(suspect) | 黃 |
| 有 repo 收集失敗 | 黃 |

最多顯示 6 條,紅線排先。週環比喺 task 量少時會好跳 — 睇趨勢線好過睇單週。

### 品質 × 自動化

| 數字 | 公式 | 代表咩 | 留意 |
|---|---|---|---|
| RAG 燈 | 紅:security critical>0 或 CI pass<75%;黃:high>0 或 CI pass<90%;綠:其餘;灰:無 CI checks 又無 quality file | repo 健康一眼睇 | CI pass rate = rollup SUCCESS 嘅 PR ÷ 有 rollup 嘅 PR;coverage / security 數字嚟自 `quality_file` |
| 修復佔比 | title match `^(fix|hotfix|revert)\b` 嘅 tasks ÷ 全部 × 100 | 工作有幾多係執手尾 | 量度**工作構成**,唔係「AI 錯誤率」— fix 修嘅可能係任何 level 引入嘅問題 |
| PR 打回率 | 收過 ≥1 個 merge 之前嘅 human `CHANGES_REQUESTED` 嘅 PR ÷ **有人 review 過**嘅 PR × 100 | 字面意義嘅「被打回重做」 | 直接嚟自 GitHub review 記錄,冇得靠估;merge 之後先嚟嘅 CHANGES_REQUESTED 唔算(code 已經出咗,冇嘢返工過);分母淨計**有人 review 過**嘅 PR — 冇人睇過嘅 PR 根本冇得被打回,計落分母只會令個率虛低,作者 review 自己個 PR 唔算;冇 PR flow 顯示「無 PR」,有 PR 但全部未經人 review 就顯示「此範圍內無經 review 嘅 PR」——即係話成個 repo merge 晒啲嘢都冇人睇過 |
| 平均返工輪數 | 被打回 PR 嘅打回**輪數**中位數 | 一個 PR 被踢返嚟幾多轉 | 一輪 = 中間冇新 push 嘅一批打回;兩個 reviewer 打回同一個 push 算一輪 |
| 返工周轉時間 | 第一次打回 → merge 嘅中位時數 | 返工要幾耐先搞掂 | 量度成段返工期,唔係最後一輪 |
| PR 接受率 | merged ÷ (merged + window 內 close 咗冇 merge) × 100 | 提出嘅改動有幾多被接納 | |
| 有效 tasks / 週 | additions ≥10 行嘅 tasks ÷ 週數 | 撇除 typo 級改動嘅真實產出節奏 | 閾值 10 行寫死喺 dashboard,想改就改 `meaningful` 嗰行 |
| 缺陷率 | window 內 `found:` 落喺窗口嘅缺陷 ÷ **全 repo** 同窗口 task 數 × 100;副標另外報未修積壓 | 每交付一批工作走出幾多缺陷 | 要 config 設 `defect_file`,冇設就顯示 `–`(唔係 0%)。分母永遠全 repo — defect.md 冇 author 維度,揀咗人只會亮「全 repo 範圍」,個數唔變 |

### 缺陷登記冊 `defect.md`

GitHub Issues 喺呢個 org 冇訊號(14 個 repo 得 1 個有 issues 數據,而佢 open / closed 都係 0),所以缺陷改為逐個 repo 手寫一個 markdown 登記冊,config 設 `defect_file = "docs/defects.md"`。

```markdown
# 未修
- [ ] 匯出 CSV 中文亂碼 !P1 found:2026-07-14
- [ ] 登入後 token 冇 refresh !P0 found:2026-07-20

# 已修
- [x] 資產統計金額用咗股數 !P1 found:2026-07-02 fixed:2026-07-05 fixed-by:Wing
```

- **打勾係狀態嘅唯一真相**。一個 `- [ ]` 就算擺喺「已修」標題下面都仍然算未修 — heading 純粹俾人分組,唔咁定義嘅話兩個訊號打交就冇得判。
- 標記:`!P0`–`!P3` severity(沿用 plan file 同一條 regex)、`found:YYYY-MM-DD`、`fixed:YYYY-MM-DD`、`fixed-by:Name`。`fixed-by:` 會餵 Repo 概覽嘅 Defect 修復 pie;已修但冇寫會歸入「已修 · 未指定」,未修則獨立一塊,所以 pie 分母永遠係登記冊全部 defects。
- **`found:` 可以唔寫**。冇日期嘅項目照樣入未修積壓(積壓係快照,唔需要日期),但入唔到窗口比率,而卡上會講明「N 個冇 found: 日期」。默默截走會令個率虛低而你睇唔出。
- 冇任何 checkbox 嘅檔案當「冇登記冊」處理,唔會當成「零缺陷」。
- 上限 500 條,超過會喺卡上標「清單已截斷」。
- **登記冊唔一定要住喺 default branch。** 唔想 markdown 撈埋落 app 嘅 main,就開一條 branch(例 `docs/management-dashboard-registers`)擺 `plan.md` + `defect.md`,再 config 設 `registers_ref`。冇設 `registers_ref` 嘅話,GitHub contents API 一律派 default branch,兩個檔都 404,而 404 會靜靜變「呢個 repo 冇登記冊」 — 卡照樣顯示 `–`,你唔會知係設定錯咗定真係冇。條 branch 只俾兩份登記冊用,唔會入 `branches`(即係唔會計多咗 commits),而表同今日建議條 link 亦會指返嗰條 branch,唔係 `HEAD`。
- Parser 係 [`parse_defect_markdown()`](scripts/collect_github.py),刻意獨立於 `parse_plan_markdown()` — 後者服務緊 完成度、今日建議、異常 tasks 同 Defect 追蹤,而且只保留未打勾嘅項目;為咗一張新卡去改佢嘅 return shape,等於將四個行緊嘅畫面一齊擺上枱。兩者只共用標記 regex。
| 各 Level 修復佔比 | 該 level 入面 fix tasks ÷ 該 level tasks | 「自動化越高係咪越多手尾」嘅切面 | 樣本細時波動大 |

### 項目進度(Issues / Milestones)

| 數字 | 公式 | 代表咩 | 留意 |
|---|---|---|---|
| 完成度 | 有 `plan_file`:checked ÷ 全部 checkboxes;否則 closed issues ÷ (open + closed) | project 推進程度(scope 來源決定可信度) | Issues 模式下**分母 = 已開嘅 issues,唔係 project 全貌**;現時 snapshot,唔受 window selector 影響 |
| 風險燈 | 紅:有 issue 嘅 milestone due 已過;黃:呆滯(>14 日冇 update)÷ open ≥30%;綠:其餘;灰:未用 Issues | 交付風險 | |
| Milestone bar | closed ÷ (open + closed);due 過咗變紅 + ⚠ | 每階段進度 | |
| 異常 tasks | 延誤 = milestone due < 今日(顯示遲咗 N 日);呆滯 = updated 距今 >14 日 | 要跟進嘅嘢 | 最多 6 個,延誤排先 |
| 今日建議 | score = 過期日數×3 + priority label(P0/urgent/critical=40;P1/high=25;P2/medium=10)+ `bug` label +15 + min(60, 年齡日數)×0.3,取 top 5 | deterministic 優先排序,唔係 AI 估 | priority 用 issue label 表達;想改權重就改 dashboard `PRIORITY_RE` / `issueScore` |

**完成度嘅前提:成個 project plan 要拆晒落 Issues。** 個 % 嘅分母係「已開咗嘅 issues」,唔係 project 實際 scope — 如果邊做邊開 issue,佢量度嘅只係已知 backlog 嘅消化率,會系統性高估進度;而每次補開新 issues,% 會回跌 — 呢個唔係 bug,係 scope 浮現緊。想個 % 反映真進度:

- **或者用 plan file**:config 設 `plan_file = "docs/project-plan.md"`,collector 讀 markdown checkboxes(`- [ ]` 未做 / `- [x]` 做咗),`#` heading 做 section 出 progress bars — 啱晒 plan 本身喺 markdown 嘅 workflow(例如 project brief)。task / heading 可以帶 inline 標記:`due:YYYY-MM-DD`(task 級 override section 級)、`start:YYYY-MM-DD`(**只喺 heading 有效**,宣告項目起點,多過一個取最早)、`!P0`/`!P1`/`!P2`、`#bug`;task 另外可加 `assignee:Name`。有咗呢啲,「異常 tasks」、「今日建議」、**Defect 追蹤**同 Repo 概覽嘅 Plan 工作分配 pie 都食到 plan file。工作分配嘅公式係該人 task 數 ÷ plan 全部 checkboxes,未寫 assignee 嘅會歸入「未指定」,所以永遠加埋 100%。冇標記嘅 plain checkbox 仍然入完成度;plan tasks 冇「更新時間」概念,所以呆滯偵測仍然只有 Issues 做到。
- 以 **milestone 做 scope 單位** — 開新階段時,一次過將該階段全部 tasks 拆晒做 issues 掛入 milestone、設 due date。咁 milestone bar 先係可信嘅完成度,repo 級總 % 只當參考(佢永遠受「未開嘅嘢睇唔到」影響)。
- 未估到細節嘅探索性工作,開一個 placeholder issue(例:`spike: X 方案調研`),令 scope 至少喺個分母度。
- 見到 % 跌,先問「係咪開咗新 issues」,唔好直接當退步。

### 項目 Burndown

設咗 `plan_file` 嘅 repo,每個喺「項目 & 團隊」多一張 burndown 卡。**唔使加任何 config** — 兩條軸都由已有嘅嘢讀返嚟:

| 軸 | 來源 |
|---|---|
| 起點 | 三層:`plan.md` heading 嘅 `start:` → repo 第一個 commit → 第一日改過 `plan.md`。用咗邊層,卡上會寫明 |
| 每一點 | target repo 入面 `plan.md` 嘅**commit 歷史**(每日最後一個 commit,經同一個 parser 重新讀一次) |
| 目標日 | `plan.md` 自己嘅 `due:` — heading 上面嗰個優先(就算佢比其他 task due 仲早都算),否則取全部 checkbox 最遲嗰個(**打咗勾嘅照計**) |

三條線:**剩餘**(`total − done`,觀測之間拉平)、**總 scope**(`total`)、**理想**(由起點 scope 直線落到目標日嘅 0)。總 scope 條線係故意要有嘅 —— 完成度 % 回跌通常係 scope 浮現,唔係退步,冇呢條線個現象只會令人誤會。

同「項目進度」一樣,burndown **唔跟** window selector(30/60/90/180)。

**讀之前要知:**

- **解像度 = `plan.md` 嘅 commit 頻率。** 一星期 commit 一次就一星期一點。個檔幾時改過,係我哋唯一真正觀測到嘅嘢。
- **起點行三層 fallback。** `plan.md` 個 heading 寫住 `start:YYYY-MM-DD` 就用佢(多過一個取最早);冇寫就用 repo 第一個 commit;連佢都攞唔到(空 repo、API 讀唔到)先至用第一日改過 `plan.md` 嗰日。條軸、理想線同 SPI 三樣都跟呢個起點 —— 所以一份開檔遲過 repo 嘅 `plan.md` 唔寫 `start:` 嘅話,理想線會過斜、SPI 會偏樂觀。
- **起點早過第一個觀測嘅話,中間嗰段留白,唔畫線。** 嗰段時間我哋一個數都冇量度過;拉一條平線過去就等於話你聽「開檔第一日就已經有 N 個 task、一個都未做」,而一條作出嚟嘅線同一條真線,喺畫面上分唔開。
- **`start:` 寫錯咗唔會靜靜哋跌走。** 唔係一個畫得出嘅日期(日曆上唔存在,或者離遠到爆條軸),又或者遲過第一個觀測(即係同 git 記錄矛盾 —— 採用佢就要切走真正量度過嘅點),兩種都唔採用,跌落下一層,而卡上會講明係邊一種。
- **歷史封頂 150 個觀測日。** 多過就淨係留返最新嗰 150 日,連理想線嘅起點(佢錨住嗰個 scope)都會跟住搬去現存最舊嗰一日,唔再係項目真正嘅起點;呢種情況卡會標「歷史已截斷」提你,唔會靜靜搬線唔通知。同一個標示亦都會喺另外兩種「攞唔晒」嘅情況出:撞到 20 版嘅揭版上限,或者中途有一版讀唔到。三種都係「`history[0]` 未必係起點」,所以共用同一句 —— 呢個 flag 寧願報多過報少。
- **目標日多數係推斷出嚟**(最遲嗰個 task due),除非有人喺 heading 明文寫。想寫死就喺 heading 加 `due:YYYY-MM-DD`。
- **冇理想線嘅時候,卡一定會講明係邊個原因。** 三種:`plan.md` 冇寫 `due:`;寫咗但個日期用唔到 —— 可能係唔存在嘅日子(例如 `due:2026-13-01`,collector 會喺 log 出 warning 兼且唔收),亦可能係日曆上啱但荒謬到畫唔到嘅年份(例如 `due:2926-09-18`,呢種 collector **唔會**出聲,係前端擋);寫咗一個唔遲過起點嘅日期(例如一份喺死線之後先開檔嘅補救計劃)—— 三種要改嘅嘢唔同,所以唔會用同一句打發。
- **重寫過歷史(force push / squash)嘅 plan branch 會失真** —— commits API 只見到現存嘅 history。
- **讀唔到歷史,卡唔會靜靜消失或者畫一條假嘅平線。** Collector 呢次讀唔到就寫 `history_error`,卡照出但唔畫圖,出張卡講明(例:「攞唔到 plan.md 嘅 commit 歷史」);同「呢份數據仲未有呢個 feature」(`history`、`history_error` 兩個 key 都冇,成張卡唔出)分得開 —— 兩種情況睇落唔一樣。
- **登記冊住喺自己條 branch 嘅話,`registers_ref` 一樣管住 burndown 嘅歷史查詢。** Ref 錯咗令 `plan.md` 本身都讀唔到嘅話,成張卡都唔會出(同冇設 `registers_ref` 嗰種 404 一樣);如果淨係嗰次歷史攞唔到(例如 commits API 派空 list),就係上面嗰種 `history_error` 卡,卡照出,唔係卡消失。

### Plan Timeline 條

同一張卡入面,burndown 下面多一條時間軸,答「邊件事、幾時到期」。**唔使加任何 config**,同 burndown 食同一份數據:

| 嘢 | 來源 |
|---|---|
| 條 bar(計劃窗口) | 解析咗嘅起點(見上面三層)→ `due:` 推斷出嚟嘅目標日 |
| 每一粒 marker | `plan.open_tasks[]` 每個未做 task 嘅 `due:` |
| SPI | 完成 % ÷ 時間流逝 %。≥1 追得上、0.8–1 落後、<0.8 嚴重落後 |

Marker 顏色**淨係**講急切度(過期 / ≤7 日 / ≤14 日 / 之後);`!P1` 同 `#bug` 喺 tooltip 入面。同一日嘅 task 合成一粒,個數字就係嗰日有幾多件事。

**讀之前要知:**

- **條線只畫未做嘅 task。** `open_tasks` 得未打勾嗰啲,所以做完嘅嘢唔會留低痕跡 —— task 一路做完,條線一路變疏,就算冇任何嘢 slip 都一樣。「變疏」唔等於「順利」。
- **上限 50 個。** 一份超過 50 個未做 task 嘅 plan,條線會唔齊。
- **目標日多數係推斷嘅**(最遲嗰個 task due),同 burndown 一樣。冇一個用得嘅目標日就冇 SPI、冇「剩幾多日」,而條 bar 改為畫到今日 —— 卡上會講明係邊一種。
- **同 burndown 一樣唔跟** window selector(30/60/90/180)。

### Defect 追蹤

兩個來源合埋同一個表,未修嘅排先:

| 來源 | 點寫 | 行為 |
|---|---|---|
| GitHub Issues | issue 打 `bug` label(要**完全等於** `bug`,`bugs` / `type:bug` 唔會 match) | Open 同最近 closed 都入,狀態顯示「未修」/ Fixed;Assignee、Due 跟 issue |
| Plan file | config 設 `plan_file`,markdown 寫**未打勾** checkbox 加 `#bug` | 只有未打勾嘅入表(所以永遠係「未修」);打勾即代表修好,會由表消失 |
| 缺陷登記冊 | config 設 `defect_file`,見上面 `defect.md` 格式 | **唯一有「已修」嗰半嘅來源** — 打咗勾嘅項目照樣入表,標 Fixed;亦係 缺陷率 嘅數據來源 |

**Plan file 寫法(直接 copy 改):**

```markdown
## Issue board

- [ ] P-01 · CI · `lint` 呢個 required check 空跑,實際乜都檢查唔到 #bug !P1 due:2026-07-17 assignee:Wing
- [ ] P-02 · docs · README 寫 3 個 required checks,ruleset 實際要 5 個 #bug !P2 due:2026-07-22 assignee:Tony
- [ ] P-03 · CI · Actions 全部用浮動 major tag,又冇 Dependabot #bug !P3 due:2026-09-18
- [x] P-00 · src · 打咗勾嘅會由 Defect 表消失(當已修好) #bug !P2 due:2026-07-01
```

| 標記 | 作用 | 冇寫會點 |
|---|---|---|
| `#bug` | 標明係 defect | checkbox 只入完成度,唔會出現喺 Defect 表 |
| `!P1` / `!P2` / `!P3` | Severity → High / Medium / Low(`!P0` 亦當 High) | Severity 欄顯示 `—` |
| `due:YYYY-MM-DD` | Due 欄。寫喺 `#` heading 就成個 section 共用,task 自己寫會 override | Due 欄顯示 `–` |
| `assignee:Name` | Assignee 欄 + Repo 概覽 Plan 工作分配 pie | Assignee 顯示 `–`,pie 歸入「未指定」 |

`P-01 · CI ·` 呢類前綴純粹係你自己嘅編號同分類,dashboard 原樣顯示、唔會解析 — 想點編都得。

**Severity 對照**(issue label 同 plan 標記共用同一套):`critical` / `high` / `P0` / `P1` → **High**;`medium` / `P2` → **Medium**;`low` / `P3` / `P4` → **Low**;乜都冇 → **—**。

**幾點要知:**

- 表最多顯示 10 行,右上角會寫實際總數(例:`11 項,顯示頭 10`),唔會靜靜截走。
- Defect 登記冊已修項目嘅 Assignee 欄顯示 `fixed-by:`;plan task 顯示 `assignee:`。兩個 marker 都接受可選嘅 `@` 前綴,但名中間唔可以有空格。
- Plan file 睇唔到「已修好」歷史(打勾就消失)。想睇 Fixed 記錄要用 Issues — closed 嘅 `bug` issue 會以 Fixed 狀態留喺表入面。
- 兩個來源可以同時用:同一個 repo 可以一邊開 issues、一邊喺 plan file 記,兩邊都會入表。

### 最近 Tasks 表格標記

| 標記 | 意思 |
|---|---|
| `#N` / hex | PR 號 / commit sha,click 去 GitHub |
| `↩N` | 呢個 PR 被打回(merge 之前嘅 CHANGES_REQUESTED)N 輪 |
| ⚠(黃) | level 聲稱同 PR 行為矛盾,hover 見原因(唔會自動降級) |
| ⛔(紅) | 中咗治理紅線,hover 見邊條 |
| !(黃) | 中咗治理警告(未經 review / 超大 PR),hover 見邊條 |

表格可將 Level 同狀態一齊收窄。狀態包括紅線、治理警告、Level 矛盾、被打回同
CI 失敗;再輸入搜尋字會同時套用。每頁顯示 25 rows,下面註明篩選後總數。

## 使用注意(點樣用得其所)

1. **樣本細,統計會跳** — 十幾個 task 嘅情況下,中位數、週環比一兩個 task 就擺動好大。睇趨勢線,唔好睇單點;異常提醒當「提你去睇」,唔好當結論。
2. **量度嘅係流程 metadata,唔係 code 質量** — dashboard 見到「點樣做」同「聲稱咩」,見唔到 code 本身好唔好。要接埋 CI 嘅 coverage / security(`quality_file`)先算完整畫面。
3. **指標一變 target 就會被玩(Goodhart)** — 為衝 L3+ 亂加 trailer、為部署頻率狂打 tag,呢啲都做得到。`verify_claim` 捉到部分聲稱同行為嘅矛盾,但最好嘅防線係 norm:**指標用嚟了解同改善,唔用嚟考核人**。同其他人(例如 Tony)分享前講明呢點。
4. **Proxy 就係 proxy** — CFR / MTTR 係近似;Lead Time 係「至 merge」唔係「至 production」;solo self-merge 之下 lead time 極短係 flow 嘅反映,唔係效率奇蹟。卡面標明 proxy 嘅數,唔好攞去同業界 benchmark 硬比。
5. **兩套時間邏輯** — tasks / DORA / 品質跟 window selector 郁;項目進度(Issues)係**現時 snapshot**,轉 30/90 日佢唔會變。
6. **分級靠 convention 同 assumption** — trailer / label 要紀律先準;abci-crm 嘅 L2 係 config 寫明嘅先驗假設(`no_evidence_level`),如果嗰邊工作方式變咗,assumption 要跟住更新。所有 assumption 都喺 config 度,可以 audit。
7. **公開性** — hub public 嘅話,所有 tracked repo 嘅 commit titles / branch 名 / issue titles 都公開。追 private repo 前先諗清楚(見 Private 模式)。
8. **數據新鮮度** — 每日跑一次,以 header 嘅 generated_at 為準;超過 48 小時會出不可關閉提示,Management summary 亦會變 Unknown。本機跑就用返「本地跑」個 flow 重新生成,瀏覽器仲顯示舊數據先 hard refresh(Ctrl+Shift+R)。

## 分級規則(priority 由高至低)

| 優先 | 來源 | 例子 | 適合 |
|---|---|---|---|
| 1 | PR label | `ai-level/L3` | PR flow,喺 GitHub UI 直接搞掂 |
| 2 | Trailer | commit message 或 PR body 加 `AI-Level: L3` | commit flow / Claude Code 自動寫 |
| 3 | Author 對應 | config 入面 `"my-agent[bot]" = "L5"` | agent bot auto-merge pipeline |
| 4 | Smart inference | 由 PR 行為推斷(下表) | 完全唔想人手標記 |
| 5 | Heuristic rules | message 含 `Co-Authored-By: Claude` → L3 | 兜底 |

五樣都冇 → 計「未分級」,反映喺覆蓋率 KPI。接受 `L3` / `l3` / `3` 寫法。

### Smart inference 判級邏輯(PRs only)

| 觀察到嘅 PR 行為 | 推斷 |
|---|---|
| agent bot 開 + 零人工 review + bot merge / auto-merge | L5 |
| agent bot 開 + 人工只係最後 approve | L4 |
| agent bot 開 + 有 `CHANGES_REQUESTED` / review threads | L3 |
| 人開 PR,全部 commits 有 AI footer,冇 review 來回,diff 有 test files | L4 |
| 全部 AI commits 但冇 test | L3 |
| AI / 人手 commits 混雜,或者有中途 review 把關 | L3 |
| AI commits 只佔少數(< 50%),冇 review 來回 | L2 |
| 完全冇 AI 痕跡(冇 footer、唔係 bot 開) | `no_evidence_level`(預設未分級) |

### SOP 模式(設定 `sop_paths` 後啟用)

如果 project 有正式 SOP(例:AIFlowTesting 嘅 plan → approval → tests-first → reviews → commit 流程),`testcases/` 記錄就係成條流程嘅指紋 — 有呢個 artifact 即係行咗流程,唔使靠 AI footer:

| diff 觸及 `sop_paths`(例:testcases/) | L3 — 行咗 SOP 流程(流程含 plan checkpoint,所以係 L3 唔係 L4)|
|---|---|
| 有 AI footer 但冇 SOP artifact | L2 — ad-hoc prompting,冇跟流程 |
| 乜證據都冇 | `no_evidence_level`(設 "L1" = 假設有 inline assist)|
| agent bot pipeline | 照舊 L4 / L5(bot 判級優先過 SOP 判級)|

Plan 本身唔會落 repo(SOP 話 plan 係 session 內俾你 approve),所以用 testcase log 做流程證據。想 plan 都留底,可以叫 planner 將 plan 寫入 `docs/plans/` 再加落 `sop_paths`。

驗證方面 SOP 模式加多一條:聲稱 L3+ 但 diff 冇 SOP artifact → `suspect:sop-artifacts-missing` — 呢個就係「聲稱行咗流程,但 plan / test case 記錄喺邊?」嘅自動化版本。

### 直接 commit 到 main(冇 PR)嘅判級

Direct commit 冇 PR 行為信號,判級階梯係:

| 證據 | 判定 |
|---|---|
| `AI-Level` trailer / author 對應 | 照聲稱(explicit 永遠優先) |
| Claude footer(SOP 模式) | L2 — 有 agent 證據,但繞過咗 PR/SOP flow,當 ad-hoc |
| message 似 AI 寫(stylometry) | L2 `inference:ai-style-message` |
| message 似人手快打 | `no_evidence_level`(L1) |

Stylometry 用 4 個結構特徵計分(conventional prefix、body ≥80 字元、subject ≥40 字元、有 bullet points),中 2 個當 AI 寫。長度計算 CJK 字元當雙倍 — 一個中文字頂兩三個英文字元,唔加權會系統性壓低中文 message 嘅分數。「fix typo」一句嘢 = 0 分 → 人手;典型 Claude Code message = 3–4 分。呢層係全套最弱嘅證據 — 可以呃、會有誤判 — 所以排喺最後做兜底,亦唔參與 claim verification。

**準確度 caveat**:L2/L3/L4 嘅真正分別在 coding session 入面(幾多次人工介入、邊個跑 verification),git/GitHub 只記錄結果,所以 inference 係推斷唔係觀測。最準嘅做法始終係喺 CLAUDE.md 叫 Claude Code commit 時自動寫 `AI-Level` trailer — agent 自己最清楚個 session 發生咗咩,而且完全唔使你人手做嘢。兩樣並存冇衝突:trailer 永遠優先,inference 做 safety net。

### 分級真確性(claim vs behaviour)

Trailer / label 係「聲稱」,唔係證明 — 任何人都打到 `AI-Level: L4`。所以 collector 會用 GitHub 記錄咗、冇得抵賴嘅人工活動去交叉驗證每個聲稱:

| 聲稱 | 但觀察到 | 判定 |
|---|---|---|
| L5 | PR 由人開 / 有人 review / 人手 merge | `suspect:l5-claim-on-human-pipeline` |
| L4 / L5 | 有 `CHANGES_REQUESTED` 或 review threads | `suspect:human-gates-observed` |
| L4 / L5 | AI footer commits 同無 footer commits 混雜 | `suspect:mixed-authorship` |
| L4 | diff 冇 test files(改動 >50 行) | `suspect:no-tests-in-diff` |

Suspect **唔會自動降級** — dashboard 表格會有 ⚠ 標記 + 異常提醒,由你覆核。方向係單向嘅:GitHub 見到嘅人工介入可以推翻誇大聲稱,但推翻唔到低報(session 入面嘅介入 GitHub 睇唔到)。Standalone commit 嘅 trailer 冇 PR 行為可以對,計 unverifiable。

Solo 自用,對手係自己嘅懶散,交叉驗證已經夠。如果將來變成團隊指標、有 gaming 誘因,按次序升級:
1. Agent 用獨立 GitHub App / bot 帳號 commit + 開 PR — GitHub 層面證明來源,人冒認唔到
2. Commit signing 分兩條 key(人一條、agent 環境一條),collector 可以查 signature
3. Claude Code hook 喺 commit 時寫 session attestation(turn 數、sha)俾 collector 對數

| Level | 定義 |
|---|---|
| L1 輔助 | 只有 inline completion |
| L2 部分自動 | 人主導,AI 按 prompt 出 block,人逐段 review 組裝 |
| L3 有條件自動 | agent 完成整個 task,中途 ≥1 次人工 checkpoint |
| L4 高度自動 | end-to-end 連 test,人只 review final diff |
| L5 完全自動 | 全程 0 human turn,auto-merge |

## 品質指標(品質 × 自動化)

Dashboard 有一欄量度「自動化程度同輸出質量嘅關係」:

| 指標 | 計法 | 意義 |
|---|---|---|
| 修復佔比 | `fix:` / `hotfix:` / `revert:` 前綴 tasks ÷ 全部 | 工作有幾多係執手尾 |
| PR 打回率 | 收過 merge 之前嘅 `CHANGES_REQUESTED` 嘅 PR ÷ **有人 review 過**嘅 PR | 字面意義嘅「被打回重做」,直接嚟自 GitHub review 記錄 |
| 各 Level 修復佔比 | 每個 level 入面 fix tasks 嘅比例 | 「自動化越高係咪越多手尾」嘅切面 |

表格 Task 欄嘅 `↩N` badge = 呢個 PR 被打回 N 輪;修復佔比較上一段升 ≥15pt 且 ≥30% 會出異常提醒。

Attribution caveat:修復佔比量度嘅係**工作構成**,唔係「AI 寫錯率」— 一個 fix task 修嘅可能係任何 level 引入嘅問題,fix 本身嘅 level 唔代表邊個惹禍。打回率就冇呢個問題,打回打嘅係嗰個 PR 自己。打回只計 merge 之前收到嘅 CHANGES_REQUESTED —— GitHub 容許 review 已經 merge 咗嘅 PR,但嗰陣代碼已經出咗,唔算返工過。分母用「有人 review 過嘅 PR」而唔係全部 merged PR:一個冇人 review 過就 merge 咗嘅 PR(auto-merge、或者中咗「未經 review 就 merge」嗰條治理警告)根本冇機會被打回,擺入分母等同當佢「通過咗 review」。作者 comment 自己個 PR 唔算 review。已經被 dismiss 嘅打回一樣照計 — GitHub 會將佢個 state 改成 `DISMISSED`,但打回呢件事發生過。冇 PR flow 嘅 repo(全 direct commit)打回率會顯示「無 PR」,本身就係一個發現。

## 項目進度(Issues + Milestones)

呢部分嘅數據來源係 **backlog 唔係 git history** — 要喺 target repo 用 GitHub Issues 做 task、Milestone 設 due date 先有數(per-repo `track_issues = false` 可關):

| 顯示 | 計法 |
|---|---|
| 完成度 | 最近到期 milestone 嘅 closed ÷ (open + closed);冇 milestone 就冇分母,如實顯示提示 |
| 剩餘 / 完成 | open issues 總數;本段 close 咗幾多(同埋開咗幾多,睇 backlog 淨流向)|
| 風險度 | RED = 有 issue 掛住逾期 milestone;AMBER = 停滯 ≥3 個或者本段開多過關;GREEN = 其餘 |
| 延誤・停滯 | open issue 嘅 milestone 過咗期,或者 ≥14 日冇 update |
| 今日建議 | rule-based 排序:**逾期 → priority label(P0/P1/urgent...)→ 停滯 → 最舊**,取頭 5 個 |

「今日建議」係規則排序,唔係 AI 判斷 — 規則明文喺 dashboard 標題度,可預測、可 audit。

## 產品 & 發佈成果

呢個分頁將「交付咗幾多」同「產品有冇產生結果」放埋同一頁,但唔會將工程
activity 扮成產品成果:

| 區塊 | 數據來源 / 算法 |
|---|---|
| Roadmap / Epics | GitHub Milestones + `plan_file` headings;顯示完成數 / scope 總數 |
| 發佈次數 | 每個 repo 用 Deployments → tags → Releases fallback,只計目前 window |
| Release readiness | 下一個未完成 milestone(冇就用整份 plan)嘅完成度 + P0/critical blockers + CI pass rate + due date;逾期、blocker 或 CI <75% = At risk,完成 ≥90% 且 CI ≥90% = Ready |
| 產品採用 / 客戶成果 | target repo 自己維護嘅 `outcomes_file`;dashboard 只呈現,唔會由 commits、PR 或 LOC 推算 |
| Outcome coverage | 有有效 `outcomes_file` 嘅 repos ÷ 目前 repo scope |

在 repo 加一份 JSON,再喺 `config.toml` 個 `[[repos]]` entry 設
`outcomes_file = "product/outcomes.json"`:

```json
{
  "updated_at": "2026-07-05",
  "adoption": [
    { "label": "Weekly active accounts", "value": 1840, "unit": " accounts", "change": 12.4, "target": 2000 }
  ],
  "customer": [
    { "label": "Support tickets / 1k orders", "value": 4.6, "unit": " tickets", "change": -11.5, "target": 4, "direction": "down" }
  ]
}
```

`change` 係相對上一個 reporting period 嘅百分比;預設越高越好。成本、處理時間、
support load 呢類越低越好嘅 metric 設 `direction: "down"`。每組可以放多個 metric;
欄位唔完整嘅 row 會略過,成份 file 缺失/JSON 壞咗就如實顯示「未接通」。

## 治理紅線偵測(規範四 / 4.3 高風險檔)

Collector 會對每個 task 做紅線檢查,dashboard 異常提醒逐類匯總、表格 ⛔ 標記涉事 rows(hover 見原因):

| 檢查 | 級別 | 方法 |
|---|---|---|
| 直接 push main | 紅線 | direct commit(冇 PR);per-repo `flag_direct_push = false` 可靜音 |
| commit .env / node_modules / __pycache__ | 紅線 | PR file paths |
| 刪除 GitHub Actions workflow | 紅線 | PR file `changeType: DELETED` 喺 `.github/workflows/` |
| 跨 feature branch 合併 | 紅線 | PR base branch 唔喺受監察名單(`branches` + default)|
| 核心模組欠二次複核 | 紅線 | 設 `core_paths` 後:掂核心路徑但 approvals < 2 |
| 未經 review 就 merge | 警告 | merged PR 零人工 review(「review 不可走過場」嘅底線 proxy;5 分鐘時長量唔到)|
| 超大 PR | 警告 | additions > `max_pr_additions`(「分階段提 PR」proxy)|

**偵測唔到、要另外做嘅**:硬編碼密鑰(要 content scanning — gitleaks / bandit 落 target repo CI,經 `quality_file` 上報);session_id 留存(要 commit / PR convention);分支保護有冇關(讀設定要 admin,但「有 direct push」已間接證明保護冇生效)。

紅線唔會改變 task 嘅 level — 治理係另一條軸,violations 同分級分開報。

## DORA + RAG(擴展指標)

| 指標 | 計法 | 性質 |
|---|---|---|
| 部署頻率 | window 內 Deployments → tags(預設全計)→ Releases fallback 鏈 ÷ 週數 | 直接;tag 有雜音先用 per-repo `tag_pattern` 收窄 |
| Lead Time | PR `createdAt → mergedAt` 中位數 | 直接(**至 merge**,唔係至 production)|
| 回退密度 | 補救 tasks ÷ 全部 tasks | 直接(比率兩邊都係 task);**唔係** DORA 變更失敗率 |
| MTTR | 修復類 task 嘅 lead time 中位數 | **proxy** — 「幾快落到修復」|
| PR 接受率 | merged ÷ (merged + closed 未 merge) | 直接(揀咗人之後顯示 `–`,closed PR 冇 person 維度)|
| 返工周轉時間 | 第一次打回 → merge 中位數 | 直接 |
| 有效 tasks / 週 | 改動 ≥10 行嘅 tasks ÷ 週數 | 直接 |
| 缺陷率 | window 內發現嘅缺陷 ÷ 全 repo 同窗口 task 數 | 直接,但取決於登記冊寫得幾齊 — 冇人記錄就會虛低 |
| CI gate pass rate | PR 最後 commit 嘅 `statusCheckRollup` | 直接(要 repo 有 CI checks)|

**Per-repo RAG**:品質卡頂部每個 repo 一粒燈,hover 見明細。規則:security critical >0 或 CI pass <75% → **RED**;high >0 或 CI pass <90% → **AMBER**;否則 **GREEN**;無 CI 又無 quality file → 灰色「資料不足」。

**Coverage % / security 數字唔喺 GitHub API** — 要 target repo 嘅 CI 寫一個 JSON,config 用 `quality_file` 指住:

```json
{ "coverage": 82.4, "security": { "critical": 0, "high": 1, "medium": 4 } }
```

AIFlowTesting 本身已經跑緊 coverage + bandit(SOP Phase 5),加一個 step 將結果寫入呢個 file commit 返 repo 就接通。冇呢個 file,RAG 淨用 CI pass rate 判,coverage / security 明細留空。

## 線上睇(Cloudflare Pages + Access)

Dashboard 已經上線:**https://management-dashboard-emj.pages.dev**

開個 URL,輸入你嘅 email,收一封一次性驗證碼(One-time PIN)郵件,入碼就睇到。
唔使密碼、唔使裝任何嘢、任何裝置都得。只有名單內嘅 email 入到;`/data/metrics.json`
一樣受保護,未登入直接開只會 302 去 Cloudflare 登入頁(2026-07-28 實測)。

- **數據更新**:同 private data repo 共用一條 nightly pipeline —— `collect.yml`
  最尾一步用 wrangler 將 `docs/` 直接 upload,每日 05:00 HKT。頁面數據以 header
  嘅 `generated_at` 為準。
- **加人 / 減人**:Cloudflare Zero Trust → Access → Applications →
  `management-dashboard-emj.pages.dev` → policy「Dashboard viewers」改 email 名單,
  即時生效,唔使重新 deploy。
- **兩個 Access application(留意)**:Cloudflare 鎖死咗 Pages 自動建立嗰個 app
  只能綁 preview wildcard,所以 production 係另開一個:

  | Application | 保護 | Policy |
  |---|---|---|
  | 自動建立(Pages「Restrict previews」) | `*.management-dashboard-emj.pages.dev` | Allow Members — **淨係 Cloudflare 帳號成員** |
  | 手動建立(self-hosted) | `management-dashboard-emj.pages.dev` | Dashboard viewers — 3 個指定 email |

  即係名單上嘅同事入到 production,入唔到 preview URL。CI 用 `--branch=main`
  只出 production,所以實際用唔到 preview,唔影響日常。
- **CI 紅咗、step 叫 `Deploy dashboard to Cloudflare Pages`**:多數係
  `CLOUDFLARE_API_TOKEN` 過期或者未設。個 step 有 guard,secret 唔見會即刻報
  `::error::` 收工,唔會靜靜跳過。換 token:Cloudflare My Profile → API Tokens →
  **Create Custom Token**(範本清單冇 Pages 嗰項),權限只揀
  **Account → Cloudflare Pages → Edit**,Account Resources 限返呢個帳號 → 貼落
  repo Settings → Secrets and variables → Actions。
- **兩個去向各自死得**:private data repo 同 Cloudflare Pages 係互為 fallback,所以
  `collect.yml` 唔會一邊跌就拖埋另一邊。`DATA_REPO_PAT` 過期只會令 data repo 嗰兩步
  紅,Cloudflare deploy 照跑,網站照有當日數據(反方向本來就成立 —— deploy 排喺
  publish 之後,wrangler 死唔會影響已經 push 好嘅 data repo)。**但 collector 自己
  爆咗就兩邊都唔會出**:deploy 條件釘死 `steps.collect.outcome == 'success'`,寧願
  留住舊數據,都好過派一份殘缺嘅 `metrics.json` 當今日嘅數。
- **睇唔出數據舊咗**:上面嗰句「唔會拖垮」係講 pipeline,唔係講版面。真係兩邊都
  跌嘅話,Pages 會繼續派上一次 deploy 嘅嘢,而頁面**除咗 header 個 `generated_at`
  之外冇任何提示**。懷疑啲數字唔郁,第一件事係對下 `generated_at`。
- **設定記錄**:Pages project 名 `management-dashboard`(所以 workflow 個
  `--project-name` 唔受 hostname 影響);Access team domain
  `summer-mud-0e86.cloudflareaccess.com`。詳細落成記錄同取捨見
  `specs/2026-07-28-phase-2-cloudflare-pages-access-design.md`。

## Private 模式

**被追蹤 repo 係 private** — 必須 fine-grained PAT(Contents: Read + Pull requests: Read,Repository access 揀埋嗰個 repo)存做 `GH_METRICS_TOKEN`。留意 fine-grained PAT 只揀到**你自己或你所屬 org** 名下嘅 repo — 追第三者個人帳號嘅 private repo(你係 collaborator)要改用 classic PAT(`repo` scope),或者將 repo 搬入共同 org。

**Pages publish pipeline 已經停用,GitHub Pages 開關本身要人手關** — 呢個係「hub repo 唔好經 Pages 曝露 private repo 資料」嗰道防線,做法見上面 Setup 步驟 5(curl 查 404/200)。留意呢度講嘅係 hub 呢個 repo 嘅 Pages,同下面講嘅「metrics 私有 data repo」係兩回事。

**Metrics 數據而家收埋喺另一個 private repo** — `wing-csi/ManagementDashboard-data`。`collect.yml` 每日自動跑 test + collect 之後,會將 `metrics.json` push 落嗰個 private repo(唔會再經 hub 呢邊嘅 Pages 出街)。Phase 1 嗰句「唔加第三方服務」**已經由 Phase 2 取代** —— 同一份 metrics 而家亦都 deploy 上 Cloudflare Pages,擺喺 Access 後面(見上面「線上睇」)。呢個本機流程保留做 fallback:唔想靠 Cloudflare、或者冇網嗰陣照用得。行呢條路要先係 `ManagementDashboard-data` 嘅 collaborator,問維護者(wing-csi)攞 access。

**第一次(得做一次)—— clone 落嚟,擺喺呢個 repo 隔籬**(即係 `../ManagementDashboard-data`,唔係入面):
```bash
git clone https://github.com/wing-csi/ManagementDashboard-data.git ../ManagementDashboard-data
```

**之後日常刷新,三行搞掂**:
```bash
git -C ../ManagementDashboard-data pull
python3 scripts/sync_data.py
python3 -m http.server -d docs 8000   # http://localhost:8000
```

`docs/index.html` 用緊 ES modules,直接雙擊個檔案用 `file://` 打開會俾瀏覽器 CORS 擋晒,一定要用返上面嗰個 http server。

**唔使再自己手動跑 collector** — CI 而家每日 05:00 HKT 自動幫 data repo 刷新一次。想睇仲新鮮過 nightly 嗰份數據,人手跑都仲得,一樣要 `GH_METRICS_TOKEN`(追埋 benegg 嗰堆 repo 就仲要 `BEN_GH_METRICS_TOKEN`):
```bash
export GH_METRICS_TOKEN=github_pat_xxx
export BEN_GH_METRICS_TOKEN=github_pat_xxx   # 冇追 benegg repos 可以唔設
python3 scripts/collect_github.py --config config.toml --out docs/data/metrics.json
python3 -m http.server -d docs 8000
```

`docs/data/metrics.json` 呢個 public repo 一直加咗入 `.gitignore`,千祈唔好手動 `git add -f` 或者用其他方式將佢 commit 返入去 —— 佢可能含 private repo 嘅 commit titles、branch 名。

留意:2026-07-27 之前嘅歷史 commit(嗰堆 `chore: update metrics [skip ci]`)仍然喺 git history 入面帶住呢個檔案 —— 呢個 repo public,所以歷史數據依然可以經 git history 讀到;清 history(rewrite / squash)係刻意留返做未做嘅 follow-up,唔係今次 Phase 0 範圍。

## config.toml 參考

| Key | 預設 | 說明 |
|---|---|---|
| `window_days` | 180 | 回溯幾多日 |
| `mode` | `auto` | `auto` = PRs + 冇 PR 嘅 commits(唔重複計);`pr` / `commits` 單一來源 |
| `repos[].name` | — | `owner/name` |
| `repos[].branch` | default branch | 單條 branch(只影響 commits)|
| `repos[].branches` | — | **多 branch 監察**:`["main", "develop"]` — 逐條掃,共享 commits 去重(首名 branch 優先);同時做「跨 branch 合併」紅線嘅放行名單(自動加埋 default branch)|
| `repos[].plan_file` | — | project plan markdown 路徑;checkboxes 做完成度 scope,帶 `#bug` 嘅入 Defect 追蹤 |
| `repos[].defect_file` | — | 缺陷登記冊 markdown 路徑(例 `docs/defects.md`);餵 缺陷率 同 Defect 追蹤。唔設就當呢個 repo 冇登記冊 |
| `repos[].registers_ref` | default branch | `plan_file` + `defect_file` 由邊條 branch 讀(例 `docs/registers`)。登記冊唔想 merge 入 main 就用呢個 — 只影響呢兩個檔,唔會加入 commits 統計 |
| `repos[].token_env` | `GH_METRICS_TOKEN` | 呢個 repo 改用另一個 env var 嘅 token(least privilege;workflow env 要傳入) |
| `repos[].no_evidence_level` 等 | 跟全局 | 每個 repo 可獨立 override `no_evidence_level` / `sop_paths` / `rules` / `agent_authors`(例:已知 AI 輔助但冇 SOP convention 嘅 repo 設 `no_evidence_level = "L2"`、`sop_paths = []`) |
| `classify.label_prefix` | `ai-level/` | PR label 前綴 |
| `classify.trailer_key` | `AI-Level` | trailer key |
| `classify.exclude_authors` | 3 個常見 bot | 完全唔計呢啲 author |
| `classify.smart_inference` | `true` | 用 PR 行為信號推斷 level(見上表) |
| `classify.agent_authors` | `[]` | 呢啲 login 當 coding agent(`*[bot]` 自動當 agent) |
| `classify.sop_paths` | `[]` | SOP artifact 路徑 prefix,設定後啟用 SOP 模式(見上) |
| `classify.no_evidence_level` | `""` | 零證據時嘅預設 level(`"L1"` 或留空 = 未分級) |
| `classify.author_levels` | `{}` | author login → level |
| `classify.rules` | Claude Code 兩條 | 子字串 match → level,由上至下 |
| `people` | `{}` | 身份合併:`正式名 = [身份...]`(見下) |
| `repos[].owner` | — | 項目負責人;repo select 會多一組「按負責人」(見下) |

## 負責人 / 貢獻者 filter

masthead 多咗個**貢獻者** `<select>`,揀咗之後成個 dashboard 收窄到嗰個人。
另外 repo select 會按 `owner` 分組,所以「邊個做嘅」同「邊個孭嘅項目」係兩條
獨立嘅軸,可以夾埋用(例:Wing 嘅項目、Tony 做嘅嘢)。

### `[people]` — 身份合併(必要)

一個人可以有幾個身份:PR 用 GitHub login,但**冇 link GitHub 帳號嘅 commit 會
fallback 去 git display name**(`collect_github.py:515-517`),所以同一個人會喺
名單出現兩次。實際數據入面 `wing-csi`(repo owner 帳號)同 `wing2036`
(呢部機嘅 collaborator credential)就係同一個人,兩邊各有幾百 / 幾十個 task —
唔合併嘅話,揀 `wing-csi` 會靜靜哋漏咗 `wing2036` 嗰批,而且冇任何提示。

```toml
[people]
Wing = ["wing-csi", "wing2036"]
```

冇列出嘅身份照原樣做一個人。**驗證好嚴,以下情況會令成個收集失敗**(exit 非零、
講明邊個出事、而且喺寫 `metrics.json` 之前就停):同一個身份列咗喺兩個人下面、
空 list、或者非字串。錯咗嘅 alias 會靜靜哋拆散或者夾埋人哋嘅工作量,
比收唔到數更差。

Alias 係**宣告**出嚟,唔係估:`metrics.json` 冇 author email 可以夾。

### `repos[].owner` — 項目負責人

```toml
[[repos]]
name = "benegg/BoostBank-ReactNative-SMEApp"
owner = "Wing"        # 寫正式名或者佢任何一個身份都得
```

寫錯名(例 `"Wng"`)只會出 **warning**,唔會 fail — 因為「負責人從來唔 commit」
係好正常嘅情況(例如經理)。冇任何 repo 設 `owner` 嘅話,「按負責人」嗰組唔會出現。

### 揀咗人之後,邊啲數字唔會跟住變

有啲區塊根本冇「人」呢個維度。與其扮到有,不如講清楚:

| 區塊 | 行為 |
|---|---|
| 主 KPI、水平分佈、每週圖、異常提醒、品質四格、commit types、月度活躍、最近 Tasks | 跟住收窄 |
| DORA Lead Time / MTTR / 回退密度 | 跟住收窄(本身就係 task 計) |
| 部署頻率、品質 RAG、項目進度、Defect 追蹤、語言構成 | **維持全 repo 數字**,並標示「全 repo 範圍」 |
| 貢獻者 | 維持全隊,只係將揀咗嗰個 highlight — 佢係比較視角,亦係揀人嘅入口 |

eyebrow 會加上「· 負責人 X」,免得 filter 咗嘅畫面被當成全隊數字。

### 分享連結

揀完人個 URL 會變成 `?owner=Wing`,可以直接 bookmark 或者傳俾人。
`?owner=` 係**唔可信輸入**:淨係攞去同已知名單比對,配唔到就靜靜哋當「全部成員」,
永遠唔會 render 出嚟。舊 bookmark 指住已經冇咗嘅人,只會退回全部,唔會報錯。

> `metrics.json` 要 collector 行過先有 `people`。舊數據冇呢個 key 嘅時候,
> dropdown 會列原始 author 名(`wing-csi` 同 `wing2036` 分開兩行)—
> 呢個係設計上嘅向後兼容 fallback,唔係 bug。

## 本地跑

日常流程(CI 已經每日 05:00 HKT 幫手刷新私有 data repo,呢度只係拉最新數據落嚟睇):

```bash
git -C ../ManagementDashboard-data pull
python3 scripts/sync_data.py
python3 -m http.server -d docs 8000   # 開 http://localhost:8000
```

第一次冇 `../ManagementDashboard-data` 呢個目錄,要先 clone 一次(要 collaborator 權限,詳情見上面「Private 模式」):
```bash
git clone https://github.com/wing-csi/ManagementDashboard-data.git ../ManagementDashboard-data
```

`docs/index.html` 用緊 ES modules,唔可以直接雙擊個檔案用 `file://` 開嚟睇(瀏覽器 CORS 擋晒),一定要用返上面個 http server。`docs/data/metrics.json` 已經 gitignore,唔會亦唔應該 commit 返入呢個 public repo。想自己跑 collector 攞新過 nightly 嘅數據,做法同所需 token 見上面「Private 模式」。

測試(唔使 network):`python3 -m pytest scripts/ -q`

## 指標定義

- **L3+ 佔比** = (L3+L4+L5) ÷ 已分級 tasks
- **出碼率(近似)** = L2–L5 tasks 嘅 additions ÷ 全部 additions(L1 當人手計,想改就調 dashboard 同 collector 嘅 `AI_LOC_LEVELS`)
- **覆蓋率** = 已分級 ÷ 全部 tasks

指標睇 trend 為主;分級 rules 定咗之後唔好改,先有得比較。
