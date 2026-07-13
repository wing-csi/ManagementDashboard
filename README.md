# ManagementDashboard

一個中央 repo,用 config 連接任意數量嘅 GitHub repos,經 API 讀取 commits + merged PRs,自動判別每個 task 嘅 AI 自動化水平(L1–L5),再出合併 dashboard。目標 repo **唔使改任何嘢**。

```
config.toml ──▶ GitHub GraphQL API ──▶ 分級(label→trailer→author→rules)──▶ metrics.json ──▶ Pages dashboard
                (commits + merged PRs)
```

## Setup(一次過)

1. 開一個新 repo(例:`ManagementDashboard`),放入呢度全部檔案
2. 開 **fine-grained PAT**:Settings → Developer settings → Fine-grained tokens
   - Repository access:揀晒你要追蹤嘅 repos
   - Permissions:**Contents: Read** + **Pull requests: Read**(Metadata 會自動包)
3. Hub repo → Settings → Secrets → Actions → 新增 `GH_METRICS_TOKEN`
   (如果只追 public repos,可以跳過 2–3,預設 token 已經夠)
4. 改 `config.toml` 加返你嘅 repos
5. Settings → **Pages → Source = GitHub Actions**
6. Actions tab → 手動 run 一次 `collect`,之後每日自動更新

## 指標字典 — 每個數點計、代表咩

**通用機制**:「今日」= 數據 `generated_at` 嗰日;window(近 30/60/90/180 日)以佢倒數;「前一段」= 緊接之前、同樣長度嘅 window;「週」= ISO 週(星期一開始);repo 下拉 filter 影響所有數字。Task = merged PR,或者冇 associated PR 嘅 direct commit(auto mode,唔會重複計)。

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
| 變更失敗率(proxy) | `revert` / `hotfix` 前綴 tasks ÷ 部署事件 × 100 | 部署後要回滾嘅比例 | proxy — 冇 incident 系統下嘅近似;冇部署記錄顯示 – |
| MTTR(proxy) | fix / hotfix / revert 前綴 **PR** 嘅 lead time 中位數 | 幾快落到修復 | 只計 PR;direct commit 嘅 fix 冇 lead time |

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
| PR 打回率 | 收過 ≥1 個 human `CHANGES_REQUESTED` 嘅 PR ÷ merged PRs × 100 | 字面意義嘅「被打回重做」 | 直接嚟自 GitHub review 記錄,冇得靠估;冇 PR flow 顯示「無 PR」 |
| PR 接受率 | merged ÷ (merged + window 內 close 咗冇 merge) × 100 | 提出嘅改動有幾多被接納 | |
| 有效 tasks / 週 | additions ≥10 行嘅 tasks ÷ 週數 | 撇除 typo 級改動嘅真實產出節奏 | 閾值 10 行寫死喺 dashboard,想改就改 `meaningful` 嗰行 |
| 各 Level 修復佔比 | 該 level 入面 fix tasks ÷ 該 level tasks | 「自動化越高係咪越多手尾」嘅切面 | 樣本細時波動大 |

### 項目進度(Issues / Milestones)

| 數字 | 公式 | 代表咩 | 留意 |
|---|---|---|---|
| 完成度 | closed issues ÷ (open + closed) × 100 | **已知 backlog 嘅消化率** | **分母 = 已開嘅 issues,唔係 project 全貌**;現時 snapshot,唔受 window selector 影響 |
| 風險燈 | 紅:有 issue 嘅 milestone due 已過;黃:呆滯(>14 日冇 update)÷ open ≥30%;綠:其餘;灰:未用 Issues | 交付風險 | |
| Milestone bar | closed ÷ (open + closed);due 過咗變紅 + ⚠ | 每階段進度 | |
| 異常 tasks | 延誤 = milestone due < 今日(顯示遲咗 N 日);呆滯 = updated 距今 >14 日 | 要跟進嘅嘢 | 最多 6 個,延誤排先 |
| 今日建議 | score = 過期日數×3 + priority label(P0/urgent/critical=40;P1/high=25;P2/medium=10)+ `bug` label +15 + min(60, 年齡日數)×0.3,取 top 5 | deterministic 優先排序,唔係 AI 估 | priority 用 issue label 表達;想改權重就改 dashboard `PRIORITY_RE` / `issueScore` |

**完成度嘅前提:成個 project plan 要拆晒落 Issues。** 個 % 嘅分母係「已開咗嘅 issues」,唔係 project 實際 scope — 如果邊做邊開 issue,佢量度嘅只係已知 backlog 嘅消化率,會系統性高估進度;而每次補開新 issues,% 會回跌 — 呢個唔係 bug,係 scope 浮現緊。想個 % 反映真進度:

- 以 **milestone 做 scope 單位** — 開新階段時,一次過將該階段全部 tasks 拆晒做 issues 掛入 milestone、設 due date。咁 milestone bar 先係可信嘅完成度,repo 級總 % 只當參考(佢永遠受「未開嘅嘢睇唔到」影響)。
- 未估到細節嘅探索性工作,開一個 placeholder issue(例:`spike: X 方案調研`),令 scope 至少喺個分母度。
- 見到 % 跌,先問「係咪開咗新 issues」,唔好直接當退步。

### 最近 Tasks 表格標記

| 標記 | 意思 |
|---|---|
| `#N` / hex | PR 號 / commit sha,click 去 GitHub |
| `↩N` | 呢個 PR 被打回(CHANGES_REQUESTED)N 次 |
| ⚠(黃) | level 聲稱同 PR 行為矛盾,hover 見原因(唔會自動降級) |
| ⛔(紅) | 中咗治理紅線,hover 見邊條 |

表格最多顯示 80 rows,下面註明總數。

## 使用注意(點樣用得其所)

1. **樣本細,統計會跳** — 十幾個 task 嘅情況下,中位數、週環比一兩個 task 就擺動好大。睇趨勢線,唔好睇單點;異常提醒當「提你去睇」,唔好當結論。
2. **量度嘅係流程 metadata,唔係 code 質量** — dashboard 見到「點樣做」同「聲稱咩」,見唔到 code 本身好唔好。要接埋 CI 嘅 coverage / security(`quality_file`)先算完整畫面。
3. **指標一變 target 就會被玩(Goodhart)** — 為衝 L3+ 亂加 trailer、為部署頻率狂打 tag,呢啲都做得到。`verify_claim` 捉到部分聲稱同行為嘅矛盾,但最好嘅防線係 norm:**指標用嚟了解同改善,唔用嚟考核人**。同其他人(例如 Tony)分享前講明呢點。
4. **Proxy 就係 proxy** — CFR / MTTR 係近似;Lead Time 係「至 merge」唔係「至 production」;solo self-merge 之下 lead time 極短係 flow 嘅反映,唔係效率奇蹟。卡面標明 proxy 嘅數,唔好攞去同業界 benchmark 硬比。
5. **兩套時間邏輯** — tasks / DORA / 品質跟 window selector 郁;項目進度(Issues)係**現時 snapshot**,轉 30/90 日佢唔會變。
6. **分級靠 convention 同 assumption** — trailer / label 要紀律先準;abci-crm 嘅 L2 係 config 寫明嘅先驗假設(`no_evidence_level`),如果嗰邊工作方式變咗,assumption 要跟住更新。所有 assumption 都喺 config 度,可以 audit。
7. **公開性** — hub public 嘅話,所有 tracked repo 嘅 commit titles / branch 名 / issue titles 都公開。追 private repo 前先諗清楚(見 Private 模式)。
8. **數據新鮮度** — 每日跑一次,以 header 嘅 generated_at 為準;Pages 有 cache,唔對數先 hard refresh(Ctrl+Shift+R)。

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
| PR 打回率 | 收過 `CHANGES_REQUESTED` 嘅 PR ÷ 全部 PR | 字面意義嘅「被打回重做」,直接嚟自 GitHub review 記錄 |
| 各 Level 修復佔比 | 每個 level 入面 fix tasks 嘅比例 | 「自動化越高係咪越多手尾」嘅切面 |

表格 Task 欄嘅 `↩N` badge = 呢個 PR 被打回 N 次;修復佔比較上一段升 ≥15pt 且 ≥30% 會出異常提醒。

Attribution caveat:修復佔比量度嘅係**工作構成**,唔係「AI 寫錯率」— 一個 fix task 修嘅可能係任何 level 引入嘅問題,fix 本身嘅 level 唔代表邊個惹禍。打回率就冇呢個問題,打回打嘅係嗰個 PR 自己。冇 PR flow 嘅 repo(全 direct commit)打回率會顯示「無 PR」,本身就係一個發現。

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

## 治理紅線偵測(規範四 / 4.3 高風險檔)

Collector 會對每個 task 做紅線檢查,dashboard 異常提醒逐類匯總、表格 ⛔ 標記涉事 rows(hover 見原因):

| 檢查 | 級別 | 方法 |
|---|---|---|
| 直接 push main | 紅線 | direct commit(冇 PR);per-repo `flag_direct_push = false` 可靜音 |
| commit .env / node_modules / __pycache__ | 紅線 | PR file paths |
| 刪除 GitHub Actions workflow | 紅線 | PR file `changeType: DELETED` 喺 `.github/workflows/` |
| 跨 feature branch 合併 | 紅線 | PR base branch ≠ default branch |
| 核心模組欠二次複核 | 紅線 | 設 `core_paths` 後:掂核心路徑但 approvals < 2 |
| 未經 review 就 merge | 警告 | merged PR 零人工 review(「review 不可走過場」嘅底線 proxy;5 分鐘時長量唔到)|
| 超大 PR | 警告 | additions > `max_pr_additions`(「分階段提 PR」proxy)|

**偵測唔到、要另外做嘅**:硬編碼密鑰(要 content scanning — gitleaks / bandit 落 target repo CI,經 `quality_file` 上報);session_id 留存(要 commit / PR convention);分支保護有冇關(讀設定要 admin,但「有 direct push」已間接證明保護冇生效)。

紅線唔會改變 task 嘅 level — 治理係另一條軸,violations 同分級分開報。

## DORA + RAG(擴展指標)

| 指標 | 計法 | 性質 |
|---|---|---|
| 部署頻率 | window 內 Deployments → version tags(`^v?\d`)→ Releases fallback 鏈 ÷ 週數 | 直接;per-repo 可設 `tag_pattern` 改 tag 過濾規則 |
| Lead Time | PR `createdAt → mergedAt` 中位數 | 直接(**至 merge**,唔係至 production)|
| 變更失敗率 | `revert:` / `hotfix:` tasks ÷ 部署次數 | **proxy** — 冇 incident 數據 |
| MTTR | 修復類 task 嘅 lead time 中位數 | **proxy** — 「幾快落到修復」|
| PR 接受率 | merged ÷ (merged + closed 未 merge) | 直接 |
| 有效 tasks / 週 | 改動 ≥10 行嘅 tasks ÷ 週數 | 直接 |
| CI gate pass rate | PR 最後 commit 嘅 `statusCheckRollup` | 直接(要 repo 有 CI checks)|

**Per-repo RAG**:品質卡頂部每個 repo 一粒燈,hover 見明細。規則:security critical >0 或 CI pass <75% → **RED**;high >0 或 CI pass <90% → **AMBER**;否則 **GREEN**;無 CI 又無 quality file → 灰色「資料不足」。

**Coverage % / security 數字唔喺 GitHub API** — 要 target repo 嘅 CI 寫一個 JSON,config 用 `quality_file` 指住:

```json
{ "coverage": 82.4, "security": { "critical": 0, "high": 1, "medium": 4 } }
```

AIFlowTesting 本身已經跑緊 coverage + bandit(SOP Phase 5),加一個 step 將結果寫入呢個 file commit 返 repo 就接通。冇呢個 file,RAG 淨用 CI pass rate 判,coverage / security 明細留空。

## Private 模式

兩個層面,setup 唔同:

**被追蹤 repo 係 private** — 必須 fine-grained PAT(Contents: Read + Pull requests: Read,Repository access 揀埋嗰個 repo)存做 `GH_METRICS_TOKEN`。留意 fine-grained PAT 只揀到**你自己或你所屬 org** 名下嘅 repo — 追第三者個人帳號嘅 private repo(你係 collaborator)要改用 classic PAT(`repo` scope),或者將 repo 搬入共同 org。

**Hub 本身要 private** — free plan 嘅 private repo 開唔到 Pages,而且就算 Pro,private repo 出嘅 Pages URL 都係公開可達(access-controlled Pages 係 Enterprise 先有)。做法:用 `collect-private.yml` **取代** `collect.yml`(commit-back 模式:workflow 將 `metrics.json` commit 返入 repo,唔行 Pages),本地睇:

```bash
git pull
python3 -m http.server -d docs 8000   # http://localhost:8000
```

反面警告:**hub public + target private = 漏緊嘢** — dashboard 會將 private repo 嘅 commit titles、branch 名公開晒。追 private repo,hub 就應該一齊 private。

## config.toml 參考

| Key | 預設 | 說明 |
|---|---|---|
| `window_days` | 180 | 回溯幾多日 |
| `mode` | `auto` | `auto` = PRs + 冇 PR 嘅 commits(唔重複計);`pr` / `commits` 單一來源 |
| `repos[].name` | — | `owner/name` |
| `repos[].branch` | default branch | 只影響 commits 讀邊條 branch |
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

## 本地跑

```bash
export GH_METRICS_TOKEN=github_pat_xxx
python3 scripts/collect_github.py --config config.toml --out docs/data/metrics.json
python3 -m http.server -d docs 8000   # 開 http://localhost:8000
```

測試(唔使 network):`python3 -m pytest scripts/ -q`

## 指標定義

- **L3+ 佔比** = (L3+L4+L5) ÷ 已分級 tasks
- **出碼率(近似)** = L2–L5 tasks 嘅 additions ÷ 全部 additions(L1 當人手計,想改就調 dashboard 同 collector 嘅 `AI_LOC_LEVELS`)
- **覆蓋率** = 已分級 ÷ 全部 tasks

免費 plan 嘅 **private repo 用唔到 Pages**:hub repo 開 public(dashboard 唔會show source code,只show task titles — 敏感就 keep private + 本地跑),或者升 Pro。

指標睇 trend 為主;分級 rules 定咗之後唔好改,先有得比較。
