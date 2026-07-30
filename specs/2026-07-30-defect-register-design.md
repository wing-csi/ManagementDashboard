# 缺陷登記冊 `defect.md` 同 缺陷率 卡

**日期:** 2026-07-30
**狀態:** 已實作(254 tests green)

## 1. 問題

Dashboard 有一個 Defect 追蹤表,來源係「issues 帶 `bug` label」加「plan file 帶 `#bug` 嘅未打勾項目」。實際上佢係空嘅。

量過真數據:14 個 tracked repo 之中,得 `wing-csi/AIFlowTesting` 一個有 issues 數據,而佢 `open_total` 同 `closed_total` **都係 0**。即係話任何以 GitHub Issues 做分子嘅缺陷指標,今日一定係空白。

plan file 嗰條路亦補唔到:[`parse_plan_markdown()`](../scripts/collect_github.py) 只會將**未打勾**嘅 task 放入 `open_tasks`。打咗勾嘅只係加大 `done` / `total` 計數器,佢個 `#bug` 標記會掉咗。所以「已修」嗰半根本冇保留過 —— 而一個比率兩邊都要。

## 2. 決定

逐個 repo 手寫一個 markdown 登記冊,config 用 `defect_file` 指路,配一個**獨立**嘅 parser。

考慮過三條路:

| 方案 | 做法 | 否決理由 |
|---|---|---|
| A | 擴充 `parse_plan_markdown()` 令佢保留打咗勾嘅項目 | 個 parser 同時服務 完成度、今日建議、異常 tasks 同 Defect 追蹤。為一張新卡去改佢嘅 return shape,等於將四個行緊嘅畫面一齊擺上枱 |
| B | Markdown table(`\| ID \| 描述 \| Severity \| Found \| Fixed \|`) | 欄位最清晰,但冇咗 `- [ ]` → `- [x]` 嘅手感。用家要求明確係「用得似 GitHub issues」 |
| **C** | **保留 checkbox 語法,獨立 parser,共用標記 regex** | **採用** |

C 拎到 B 嘅隔離同 A 嘅熟悉度,代價只係兩個 function 共用幾條 regex。爆炸半徑收窄到只有新代碼。

## 3. 格式

```markdown
# 未修
- [ ] 匯出 CSV 中文亂碼 !P1 found:2026-07-14
- [ ] 登入後 token 冇 refresh !P0 found:2026-07-20

# 已修
- [x] 資產統計金額用咗股數 !P1 found:2026-07-02 fixed:2026-07-05
```

**打勾係狀態嘅唯一真相。** 一個 `- [ ]` 擺喺「已修」標題下面仍然算未修;heading 純粹俾人分組。兩個訊號指住同一個事實就一定會有打交嘅一日,而嗰陣冇規則可以判。

標記:`!P0`–`!P3`(重用 `PLAN_PRIO_RE`)、`found:YYYY-MM-DD`、`fixed:YYYY-MM-DD`。

**`found:` 係可選。** 冇日期嘅項目**保留**,唔會掉。佢照樣入未修積壓 —— 積壓係快照,唔需要日期 —— 但入唔到窗口比率,而卡上會報「N 個冇 found: 日期」。喺 parser 度靜靜哋掉走會令個率虛低,而冇任何人睇得出。

冇任何 checkbox 嘅檔案回 `None`,唔會回一個空登記冊:「冇登記冊」同「零缺陷」係兩件事。上限 500 條,超過設 `truncated: true` 並喺卡上標明。

## 4. Schema

`schema_version` 留喺 **2** —— 純新增欄位,同 `people` / `repo_meta[].owner` 嘅先例一致。

```json
"repo_meta": {
  "acme/alpha": {
    "defects": {
      "path": "docs/defects.md",
      "truncated": false,
      "items": [
        {"title": "匯出 CSV 中文亂碼", "severity": "P1",
         "found": "2026-07-14", "fixed": null, "open": true}
      ]
    }
  }
}
```

每個 item 一定帶齊全部 key(冇嘅係 `null`),前端唔使分「absent」同「null」。

## 5. 收集端

`scripts/collect_github.py` 新增:

- `DEFECT_FOUND_RE` / `DEFECT_FIXED_RE` / `DEFECT_CAP = 500`
- `_clean_defect_title()` — 剝走標記
- `parse_defect_markdown(text) -> dict | None`
- `fetch_defect_file(client, repo, path) -> dict | None` — 檔案唔存在 / 讀唔到 / 唔係登記冊都回 `None`,同 `fetch_plan_file` 同一個 contract:一個冇登記冊嘅 repo 唔係錯,佢只係冇貢獻

`collect_repo` 加一個分支,擺喺現有 `plan_file` 分支隔籬:

```python
if repo_cfg.get("defect_file"):
    meta["defects"] = fetch_defect_file(client, repo, repo_cfg["defect_file"])
```

`parse_plan_markdown` / `fetch_plan_file` / `collect_issues` / `fetch_repo_meta` **完全冇改**。

## 6. 前端

### `defectsInScope()`(aggregate.js)

回 `{found, open, undated, truncated, hasData}`。只負責數,唔計比率 —— 分母交返俾 caller。

- `found` — `found:` 落喺 window 內嘅缺陷數(比率分子)
- `open` — 未修數,**唔受窗口限制**。一個 2019 年開到今日嘅 bug,正正就係積壓要顯示嘅嘢
- `undated` — 冇 `found:` 嘅數,由 UI 講明

### 缺陷率卡(品質格)

值 = `pct(found, repoWideTaskCount())`,副標 = `N 個 X 日內發現 / M 個 task · K 個未修`,再按需要加「N 個冇 found: 日期」同「清單已截斷」。

**分母永遠全 repo。** 呢個係成個設計最重要嘅一條。`defect.md` 冇 author 維度,所以「全 repo 缺陷 ÷ 一個人嘅 task」就係 [變更失敗率舊版](2026-07-28-owner-contributor-filter-design.md) 犯過嗰個錯:分子分母唔同範圍,唔係一個比率。`repoWideTaskCount()` 用 `repoRag()` 同一招 save/restore `state.person`。揀咗人之後個數唔變,改為亮起「全 repo 範圍」。

Repo filter **會**收窄兩邊 —— repo 係登記冊有嘅維度。

### 空狀態

| 情況 | 顯示 |
|---|---|
| 冇 repo 設 `defect_file` | `–` + 「未有 repo 設定 defect_file」 |
| 有登記冊,窗口內冇發現 | `0.0%` |
| 有登記冊,window 內冇 task | `–`(分母 0),副標照報積壓 |

`–` 同 `0.0%` 一定要分得開:後者主張「呢個 window 交付咗嘢而一個缺陷都冇」,係一個強好多嘅講法。

### Defect 追蹤表

登記冊做第三個來源,同 issues、plan `#bug` 並排。佢係唯一有「已修」嗰半嘅來源,所以打咗勾嘅照樣入表,標 `Fixed`。`severity` 入 `labels` 餵現有嘅 `sev()` 映射,`due` 用 `fixed || found`。

## 7. 測試

| 檔案 | 覆蓋 |
|---|---|
| `scripts/test_defect_parser.py`(15) | 打勾勝過 heading、已修保留、標記解析同次序無關、大小寫正規化、缺標記回 `null`、無日期保留、無 checkbox 回 `None`、截斷宣告、fetch 錯誤路徑 |
| `scripts/test_frontend_defects.py`(12) | 比率算術、副標三個數、窗口外缺陷入積壓唔入比率、person filter 唔改分母、scope note 亮起、repo filter 收窄兩邊、三個空狀態、截斷標示、表格收到登記冊條目同 Fixed 狀態 |

Fixture `metrics-fixture-defects.json`:10 個 task、5 個缺陷(3 個窗口內發現、4 個未修、1 個無日期)→ 30.0%。Wing 佔 6 個 task —— 如果分母跟住 person filter 收窄,個卡會讀成 50%,所以嗰個 test 真係抓得住。

`rendered-baseline.json` 唔使重生:佢捕捉嘅八個 section 冇 `#qDefect` 亦冇 `#defectRows`。

## 8. 已知限制

- **登記冊寫得幾齊決定個數有幾真。** 冇人記錄就虛低。呢個係手動流程無得避嘅,已寫入 README。
- **`found:` 靠人手填。** 冇同 commit / PR 對齊,所以「發現日期」係自報。
- **未接 severity 加權。** P0 同 P3 喺比率入面同重。要分就要再設計。
- **仍然唔係 DORA 變更失敗率。** 嗰個要 per-deployment 記錄;12 / 14 個 repo 冇 tag,0 個有 Deployments API 記錄。
