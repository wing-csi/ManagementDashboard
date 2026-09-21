# English terminology — authoritative

One source of truth for the English UI copy. Several agents fill the `docs/js/i18n/dict/en/*`
namespaces in parallel; without this file they would each invent a different English word for
「品質」 and the dashboard would read as if four people wrote it.

**If a string is in this table, use it exactly.** If you need a term that is not here, add a row
in the same commit rather than deciding it locally.

## Hard constraint: tab labels stay short

`docs/css/dashboard.css` records that the tab bar already overflows at 375px **in Chinese**, by
34px and 58px. English labels run 2–4× wider (「品質」 2 chars → "Quality" 7). Tab labels are
therefore **one word each** — no ampersands, no second noun — even though the Chinese has two.

| Chinese | English | Note |
|---|---|---|
| 總覽 | Overview | |
| 品質 | Quality | |
| 項目 & 團隊 | Projects | NOT "Projects & Team" — too wide |
| 產品 & 發佈 | Product | NOT "Product & Release" — too wide |
| 工作 | Tasks | |

## Autonomy levels (`aggregate.js` META)

Borrowed from the SAE driving-automation scale, so the English uses that vocabulary.

| Level | Chinese | English |
|---|---|---|
| L1 | 輔助 | Assisted |
| L2 | 部分自動 | Partial |
| L3 | 有條件自動 | Conditional |
| L4 | 高度自動 | High |
| L5 | 完全自動 | Full |
| — | 未分級 | Unclassified |

## Delivery status (`render-management.js` STATUS)

| Chinese | English |
|---|---|
| 進度正常 | On track |
| 存在風險 | At risk |
| 偏離計劃 | Off track |
| 未知 | Unknown |

## Data health (`render-management.js` HEALTH)

| Key | Chinese | English |
|---|---|---|
| healthy | 最新 | Current |
| attention | 需要關注 | Needs attention |
| stale | 已過時 | Stale |
| unreadable | 未知 | Unknown |
| future | 時鐘不一致 | Clock mismatch |
| unknown | 未知 | Unknown |

> **Note for the runbook:** the demo script quotes this as 「已過期」, but the code renders
> 「已過時」. The script is already wrong today, before any translation. English is "Stale".

## Forecast confidence (`render-management.js` CONFIDENCE / FORECAST_REASON)

| Chinese | English |
|---|---|
| 實際 | Actual |
| 高 / 中 / 低 | High / Medium / Low |
| 未有計劃 | No plan |
| 觀測點不足 | Too few observations |
| 歷史少過 7 日 | Under 7 days of history |
| 未觀測到完成進度 | No observed progress |

## Filters and chrome

| Chinese | English |
|---|---|
| 自動化水平儀 | Autonomy Gauge |
| GITHUB 數據監測 | GITHUB TELEMETRY |
| 示範數據 · 手動要求（?demo=1） | Demo data · explicitly requested (?demo=1) |
| 程式庫 | Repository |
| 分支 | Branch |
| 貢獻者 | Contributor |
| 統計範圍 | Time window |
| 全部程式庫 | All repositories |
| 全部分支 | All branches |
| 全部成員 | All contributors |
| 近 {n} 日 | Last {n} days |
| 按負責人 | By owner |
| 個別程式庫 | Individual repositories |
| {owner} 的項目 ({n}) | {owner}'s projects ({n}) |
| 負責人 {name} | Owner {name} |
| {n} 個程式庫 | {n} repositories |
| 搜尋標題 / 作者 / 分支 / PR | Search title / author / branch / PR |
| 選擇單一程式庫後才可篩選分支 | Select a single repository to filter by branch |
| 載入數據失敗。 | Failed to load data. |
| 需要登入。 | Sign-in required. |
| 網絡錯誤 | network error |
| 產生於 {ts} | Generated {ts} |

## Core metrics

| Chinese | English |
|---|---|
| L3+ 佔比 | L3+ share |
| 出碼率（近似） | AI-written code (approx.) |
| 分級覆蓋率 | Classification coverage |
| 有效 tasks/週 | Effective tasks / week |
| 修復佔比 | Rework share |
| PR 打回率 | Changes-requested rate |
| PR 接受率 | PR acceptance rate |
| 部署頻率 | Deployment frequency |
| 變更失敗率 | Change failure rate |
| 完成度 | Completion |
| 逾期 | Overdue |
| 呆滯 | Stalled |

## Units and number formatting

Never build these by concatenation — word order differs from Chinese.

| Chinese pattern | English |
|---|---|
| `{h} 小時` | `{h} h` |
| `{d} 日` | `{d} d` |
| `平均每 {weeks} 週 1 次` | `avg. 1 every {weeks} weeks` |
| `{n} 個百分點` | `{n} pp` |
| `{n} 個項目逾期` | `{n} project overdue` / `{n} projects overdue` |
| `{n} 項工作` | `{n} task` / `{n} tasks` |

Dates: Chinese renders `08/06`. **English must not** — "08/06" reads as either 8 June or
6 August and a client will read it wrong on a projector. English uses an explicit month:
`06 Aug`.

`toLocaleString` must always receive the explicit `LOCALE` exported by `docs/js/i18n/index.js`.
Calling it with no locale argument (as `render-kpi.js:31` does today) silently formats
differently depending on the viewer's browser.
