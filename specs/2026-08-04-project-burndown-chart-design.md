# 項目級 Burndown 圖

**日期:** 2026-08-04
**狀態:** 設計已批,未實作

## 1. 問題

「項目 & 團隊」分頁而家答到「而家做咗幾多」——完成度 %、milestone bar、延誤同呆滯清單。答唔到嘅係**「趨勢係點」**:剩低嘅工作係咪收緊?追唔追得上死線?scope 係咪一路發散?

呢個唔係渲染問題,係數據問題。`metrics.json` 由頭到尾係一個**快照**:一個 `generated_at`、一個窗口內嘅 `tasks[]`、一個 `repo_meta[repo].plan = {done, total, sections, open_tasks}`。入面**冇任何歷史**。Burndown 本質上係時間序列,所以要新開一條上游數據流。

而 `plan.md` 本身亦冇時間維度:一個 `- [x]` 話你知**乜嘢**做完咗,永遠唔會話你知**幾時**做完。時間軸一定要另有來源。

## 2. 決定

| 決定 | 揀咗 |
|---|---|
| Scope 單位 | 逐個 repo 嘅 `plan_file` checkboxes(剩餘 = 未打勾) |
| 時間軸來源 | target repo 入面 `plan.md` 嘅 **git commit 歷史** |
| 目標日 | `plan.md` 讀返:heading 級 `due:` 優先,否則全部 checkbox 最遲嗰個 |
| X 軸範圍 | plan 起點 → 目標日,今日標線 |
| 新代碼位置 | 新 module `scripts/plan_history.py`,輸出摺返入現有 `metrics.json` |

**唔加任何 config key。** 兩個已經設咗 `plan_file` 嘅 repo 開箱即用。

### 2.1 點解係 plan.md 而唔係 Issues

沿用 [`defect-register`](2026-07-30-defect-register-design.md) 量過嘅同一組數:14 個 tracked repo 之中得一個有 issues 數據,而佢 open / closed 都係 0。以 Issues 做 scope 嘅 burndown 今日一定係空白。`plan_file` 係呢個 org 唯一有訊號嘅 scope 來源。

冇設 `plan_file` 嘅 repo **唔會**出圖 —— 唔係出一條零線。「未設 plan file」同「冇剩低嘢做」係兩件事。

### 2.2 時間軸:三條路

| 方案 | 做法 | 否決理由 |
|---|---|---|
| A | 夜更 job 每日 append 一行入 data repo 嘅 `history.json` | 出街嗰日個圖係空,要等幾個星期先有形。而且睇唔到過去。漏跑或者跑兩次會靜靜哋歪咗條線,冇任何人睇得出 |
| B | 行返 `ManagementDashboard-data` 自己嘅 git log,由每個舊 `metrics.json` 讀 `plan.done/total` | 歷史只去到 2026-07-27(9 個 commit)。而且將 collector 綁死喺自己輸出 repo 嘅 git 結構上 |
| **C** | **行 target repo 入面 `plan.md` 嘅 commit 歷史** | **採用** |

C 係**追溯**嘅:第一次跑就已經有完整歷史,一路去到 `plan.md` 開檔嗰日。亦係**無狀態**嘅 —— 冇一個會腐爛、會走樣嘅檔案要維護,重跑一次永遠得返同一條線。代價係每次夜更多幾個 API call,詳見 §4.1。

### 2.3 目標日:點解取「最遲」而唔係「最早」或者 heading

實測 `wing-csi/AIFlowTesting/plan.md`:H1 係 `# Remediation plan — detected issues`,**冇 `due:`**;11 個 checkbox 每個都有,由 `2026-07-10` 到 `2026-09-18`。即係話「只讀 heading」呢條規則喺唯一一個有真 plan 嘅 repo 度會出唔到理想線。

**要數埋打咗勾嘅 task。** 只計未打勾嘅話,每次剔走一個遲 due 嘅項目,目標日就會向前跳 —— 條理想線會喺你 burn 緊嘅時候自己郁,「追唔追得上」就冇得答。

Heading 上面嘅 `due:` 優先過 task —— parser 已經讀緊佢入 `cur_due`,所以想明文寫死個 project 死線,喺 `plan.md` 加一個 heading marker 就得,唔使改 config。

成個 plan 一個 `due:` 都冇 → 冇理想線,圖照出(剩餘 + scope 兩條線),卡上講明點解。

## 3. Parser 改動

`parse_plan_markdown()` 加一個 **`due_max`** 欄位,喺**現有嗰個 single pass** 入面順手計,規則:heading 級 `due:` 優先,否則取全部 checkbox(打勾同未打勾)嘅最大值。

**純新增,唔改 return shape。** 呢個 return 已經餵緊四個行緊嘅畫面(完成度、今日建議、異常 tasks、Defect 追蹤)—— 同 [`defect-register`](2026-07-30-defect-register-design.md) 否決方案 A 一模一樣嘅理由:為一張新卡去郁佢,等於將四個屏幕一齊擺上枱。

## 4. 收集端 `scripts/plan_history.py`

新 module,唔入 `collect_github.py` —— 佢已經 1231 行 / 52 KB,遠超本 repo 800 行上限,而且已經孭住收集、分級同 parsing 三份工。`collect_github.py` 只加 call site 嗰幾行。

逐個有 `plan_file` 嘅 repo:

1. `GET /repos/{repo}/commits?path=<plan_file>&sha=<registers_ref>&per_page=100`
   —— 郁過個 plan 嘅 commit,**釘喺登記冊嗰條 branch**。冇設 `registers_ref` 就唔帶 `sha`,GitHub 派 default branch —— 同 `_contents_path()` 一模一樣嘅契約(AIFlowTesting 就係呢個 case,plan.md 住喺 `main`)。設咗就一定要帶:ref 錯咗個 list 係**空**,唔係錯,而空 list 會靜靜哋變「呢個 repo 冇歷史」。
2. **逐日去重**,每個曆日只留**最後**一個 commit(嗰日收工時嘅狀態)。大部分日子根本冇郁過 plan,所以實際 fetch 數 = 「plan 改過嘅日數」。
3. 每個生還者:fetch 嗰個 sha 嘅 blob → 過現有 `parse_plan_markdown()`。**冇第二個 parser,冇新標記語意。**
4. 上限 150 個 blob,超出掉最舊,並且設 `history_truncated: true`。上限只會令個 flag 著,唔會靜靜哋剪短條線。

**截斷會搬走個起點。** 掉咗最舊嗰批之後,`history[0]` 就唔再係 plan 開檔嗰日,而理想線正正錨喺起點嘅 scope(§6)。所以 `history_truncated` 著嘅時候,卡上除咗標「已截斷」,仲要講明理想線係由**現存最早**嗰個觀測起計 —— 否則條線會扮成由項目開頭度拉出嚟。150 日對現時嘅 plan 嚟講綽綽有餘,呢個係防呆,唔係常態。

**Carry-forward 唔喺收集端做。** collector 只出**真實觀測**——plan 真係改過嗰啲日。將平坦嘅日子焗入 JSON,會令一條階梯函數同真正嘅每日取樣完全分唔開,而且 payload 大幾倍換零資訊。

### 4.1 API 成本

每個 plan repo 每次夜更:1 個 commit-list call + 「plan 改過嘅日數」個 blob call。今日兩個 repo 設咗 `plan_file`。GitHub REST 上限 5000/hr,量級上完全唔成問題。

## 5. Schema

`schema_version` 留喺 **2** —— 純新增欄位,同 `people`、`repo_meta[].owner`、`defects` 嘅先例一致。

```json
"repo_meta": {
  "acme/alpha": {
    "plan": {
      "path": "plan.md",
      "ref": null,
      "done": 0,
      "total": 11,
      "due_max": "2026-09-18",
      "history_truncated": false,
      "history": [
        {"date": "2026-07-28", "done": 0, "total": 11},
        {"date": "2026-08-02", "done": 3, "total": 11}
      ]
    }
  }
}
```

`history` 升序。commits API 失敗嘅時候 `history` **唔會出現**(唔係 `[]`)—— 前端要分得出「攞唔到歷史」同「歷史係空」;同一時間 `history_error` 會設做一句人睇得明嘅訊息。兩個 key 互斥,而舊數據兩個都冇(見 §7)。

## 6. 前端

每個有歷史嘅 plan repo 一張卡,擺喺「項目 & 團隊」分頁、milestone bar 下面。Masthead 個 repo filter 照樣收窄。Chart.js 已經載咗(`docs/index.html:7`),用 line chart,新 canvas。

三條線:

| 線 | 計法 | 點解要有 |
|---|---|---|
| 剩餘 | `total − done`,觀測之間 carry-forward | burndown 本體 |
| 總 scope | `total` | README 講明完成度 % 回跌通常係 **scope 浮現**,唔係退步。冇呢條線,個現象只會令人誤會 |
| 理想 | 由 (起點, 起點嘅 total) 直線去 (`due_max`, 0) | 「追唔追得上」 |

X 軸:起點 → `due_max`,今日標一條線,剩餘線去到今日為止(右邊嗰段空白 = 仲有幾多 runway)。理想線錨喺**起點嘅 scope**,唔係今日嘅 —— 所以 scope 加咗幾多,一眼睇得出係兩條線嘅開叉。

**唔跟 window selector**(30/60/90/180),同「項目進度」現有嘅時間邏輯一致,README 已經寫明呢部分係獨立於 window。

## 7. 空狀態

每個都各有講法,冇一個會扮到有圖:

| 情況 | 行為 |
|---|---|
| 冇設 `plan_file` | 呢個 repo 唔出卡 |
| commits API 失敗(`history_error` 著) | 出明文訊息,**唔係**一條平線 |
| 得一個觀測點 | 畫返個點,寫「只有一個觀測點,未成趨勢」,唔畫趨勢線 |
| `plan.md` 冇任何 `due:` | 冇理想線,剩餘 + scope 照出,卡上講明 |
| `history_truncated` | 卡上標明已截斷 |
| 舊 `metrics.json` 兩個 key 都冇 | 成個 section 隱藏 —— 同 `people` 一樣嘅向後兼容 fallback |

**點解要多一個 `history_error`。** 上面兩行喺前端睇落係同一個狀態:兩者都係「冇 `history` key」。淨靠缺席就分唔出「今次攞唔到」同「呢份數據舊到根本未有呢個 feature」—— 而兩者要做嘅嘢啱啱相反(一個要出聲,一個要收埋)。所以 collector 讀唔到歷史嘅時候會明文寫低 `history_error`,舊數據永遠冇呢個 key。

## 8. 測試(TDD,先寫測試)

| 檔案 | 覆蓋 |
|---|---|
| `scripts/test_plan_history.py`(新) | 逐日去重留最後一個 commit;升序;上限 + `history_truncated`;空 commit list 回 `None` 而唔係 `[]` |
| `scripts/test_collect_github.py`(加) | `due_max`:打勾嘅計埋、heading 覆蓋 task、全部冇 `due:` → `None`;`registers_ref` 有帶落 commits API |
| `scripts/test_frontend_burndown.py`(新,playwright) | 三條線齊、今日標線、冇 `due_max` 冇理想線、單點狀態、`history_error` 出訊息但唔出圖、舊 fixture 隱藏 section |

新 fixture `scripts/fixtures/metrics-fixture-burndown.json`,做法沿用 `test_frontend_registers_ref.py`。

## 9. 已知限制

- **歷史嘅解像度 = plan.md 嘅 commit 頻率。** 一星期 commit 一次,就係一星期一點。呢個係老實嘅:個檔幾時改過,係我哋唯一真正觀測到嘅嘢。
- **`plan.md` 開檔之前嘅嘢睇唔到。** 起點係第一個 commit,唔係「項目真正開始嗰日」。plan 中途先開嘅話,個圖由中途開始。
- **重寫過歷史(force push / squash)嘅 plan branch 會失真** —— commits API 只見到現存嘅 history。
- **目標日係推斷出嚟**(最遲 task due),除非有人喺 heading 明文寫。卡上要標明係邊個來源,唔可以扮成一個已宣告嘅死線。
