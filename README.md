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
