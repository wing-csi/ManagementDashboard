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
| 完全冇 AI 痕跡(冇 footer、唔係 bot 開) | 未分級 |

**準確度 caveat**:L2/L3/L4 嘅真正分別在 coding session 入面(幾多次人工介入、邊個跑 verification),git/GitHub 只記錄結果,所以 inference 係推斷唔係觀測。最準嘅做法始終係喺 CLAUDE.md 叫 Claude Code commit 時自動寫 `AI-Level` trailer — agent 自己最清楚個 session 發生咗咩,而且完全唔使你人手做嘢。兩樣並存冇衝突:trailer 永遠優先,inference 做 safety net。

| Level | 定義 |
|---|---|
| L1 輔助 | 只有 inline completion |
| L2 部分自動 | 人主導,AI 按 prompt 出 block,人逐段 review 組裝 |
| L3 有條件自動 | agent 完成整個 task,中途 ≥1 次人工 checkpoint |
| L4 高度自動 | end-to-end 連 test,人只 review final diff |
| L5 完全自動 | 全程 0 human turn,auto-merge |

## config.toml 參考

| Key | 預設 | 說明 |
|---|---|---|
| `window_days` | 180 | 回溯幾多日 |
| `mode` | `auto` | `auto` = PRs + 冇 PR 嘅 commits(唔重複計);`pr` / `commits` 單一來源 |
| `repos[].name` | — | `owner/name` |
| `repos[].branch` | default branch | 只影響 commits 讀邊條 branch |
| `classify.label_prefix` | `ai-level/` | PR label 前綴 |
| `classify.trailer_key` | `AI-Level` | trailer key |
| `classify.exclude_authors` | 3 個常見 bot | 完全唔計呢啲 author |
| `classify.smart_inference` | `true` | 用 PR 行為信號推斷 level(見上表) |
| `classify.agent_authors` | `[]` | 呢啲 login 當 coding agent(`*[bot]` 自動當 agent) |
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
