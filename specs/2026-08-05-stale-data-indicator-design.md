# 數據過期提示條

**日期:** 2026-08-05
**狀態:** 設計已批,未實作
**來源:** `28db7df`(deploy 唔再被 data repo 拖死)之後剩低嗰個窿 —— pipeline 層面
補好咗,版面層面補唔到。

## 1. 問題

Nightly pipeline 兩個去向而家各自死得(`28db7df`),但**兩邊一齊死嘅時候版面完全
睇唔出**:Cloudflare Pages 會繼續派上一次 deploy 嘅嘢,而個 dashboard 除咗 header
一個 12px muted mono 嘅 `generated_at` 之外,冇任何提示。

真正麻煩嘅唔係「數字舊咗」,係**成個版面會靜靜哋改咗「今日」係邊日**:

| 邊度 | 做緊乜 |
|---|---|
| `docs/js/data.js:71` | `refDate()` —— 成個 window selector(30/60/90/180)由 `generated_at` 數返轉頭 |
| `docs/js/render-burndown.js:68` | burndown 條今日線 |
| `docs/js/render-project.js:29` | milestone 嘅 late 判斷 |
| `docs/js/render-timeline.js`(經 `timelineStrip`) | timeline 條今日線、SPI、「幾多個過期」 |

即係話數據一舊,**冇嘢會新變成過期、條今日線會凍喺半路、SPI 唔再郁**。成個版面
內部一致、完全合理,但對緊一個錯嘅日期。呢種錯難捉得多 —— 冇一樣嘢睇落壞咗。

## 2. 決定

| 決定 | 揀咗 |
|---|---|
| 做乜 | **淨係出提示,唔掂啲數** —— `refDate()` 同所有由日期推出嚟嘅嘢一律唔改 |
| 過期線 | 超過 **48 小時** |
| 擺喺邊 | header 同 tabs 中間一條 banner,每個分頁都見到 |
| Demo 模式 | **完全唔出** |
| 「而家」邊度嚟 | browser 個 clock,但**由 caller 傳入**,唔喺模組入面 call `Date.now()` |

### 2.1 點解係 48 小時,唔係 24

Pipeline 每日 05:00 HKT 行,即係 **21:00 UTC**。所以一日入面大部分時間,最新可能
嘅數據本身就已經 20 幾個鐘頭大 —— 呢個係正常,唔係過期。一條「超過 24 鐘」嘅規矩
會**每日下晝都嘈一次**,而嘈得滯嘅提示等於冇提示。

48 鐘代表至少一次 nightly run 真係冇出到嘢,亦都唔使喺代碼度寫死個 cron 時間
(`config.toml` 本身冇呢個資料)。

### 2.2 點解唔改 `refDate()`

改用 browser clock 做「今日」睇落更加正確,但會**改晒每一個日期相關數字嘅意思**,
而且所有釘住 fixture `generated_at` 做今日嘅現有測試會一鋪過紅晒。呢份設計揀最細
嗰個改動:啲數字維持自我一致,由 banner 講「唔好信佢哋幾新」。

### 2.3 點解 demo 模式唔出

`docs/data/demo-data.js` 個 `generated_at` 係 `2026-07-06T21:00:00+00:00` —— 死咗
喺度嘅假數據,佢幾大唔代表任何嘢。喺度長期掛住一條過期 banner,只會訓練啲人當
banner 透明,連帶真係過期嗰陣都唔會望。Demo 模式本身已經有 `#demoBadge` 講緊。

## 3. 模組

一個新嘅純模組 `docs/js/staleness.js` —— 冇 DOM、冇 import,同 `plan-dates.js`、
`timeline.js` 一樣可以獨立測:

```
staleness(generatedAt: string|null, nowMs: number) -> { status, ageDays }
```

**`nowMs` 由 caller 傳入,唔喺入面 call `Date.now()`** —— 呢點係整份設計最食重嘅
決定。模組入面自己攞當前時間嘅話,測試就冇得釘住「而家」,而所有用固定 fixture 嘅
test 會隨住月曆行前而慢慢變紅(`metrics-fixture-burndown.json` 釘咗
`2026-08-04`,到 2026-08-06 就會過 48 鐘)。同 `burndownSeries(plan, todayStr)`
同 `timelineStrip(plan, todayStr)` 收 today 做參數,係同一個做法。

### 3.0 `ageDays` 點計

門檻用**毫秒**判,唔用日數判 —— `age > 48 * 3600e3`。`ageDays` 淨係攞嚟寫嗰句
「N 日前」,係 `Math.floor(ageMs / 864e5)`。

分開兩樣嘢係因為兩者撞界嗰陣答案唔同:啱啱 48 鐘係 `fresh`(唔算 `>`),但
`ageDays` 已經係 2。用日數判門檻嘅話,49 鐘同 71 鐘都係「2 日」,一個應該出、一個
唔應該出,就會分唔開。

`status` 唔係 `stale` 嗰陣,`ageDays` 一律 `null` —— 冇時間戳同時間戳喺未來,兩種
情況都冇一個講得出口嘅「幾多日前」。

### 3.1 四個 status

| status | 條件 | Banner |
|---|---|---|
| `fresh` | age ≤ 48h | 冇 |
| `stale` | age > 48h | 「數據係 N 日前嘅」+ 叫人查邊度 |
| `unreadable` | `generated_at` 冇、或者唔係一個真時間戳 | 講明**個時間戳本身**壞咗 |
| `future` | 早過而家超過 1 個鐘 | 講明有個 clock 唔啱 —— 係偏差,唔係過期 |

`unreadable` 同 `future` 唔可以併入 `stale`,因為併咗就係**講緊一件假嘢**:冇時間戳
唔等於數據舊,而未來嘅時間戳代表 browser clock 或者 collector 有問題 —— 兩件事
要改嘅嘢完全唔同。`future` 留 1 個鐘容差,食得起平時嘅 clock skew。

呢個係跟返 timeline spec §8 嗰條「每一個缺席都要自己解釋」:唔畫得出就要講得出
點解,唔可以共用一句。

## 4. 流程

`main.js:79-81` 而家已經喺度砌個 stamp。緊接住嗰度,**而且淨係喺 `state.demo`
係 false 嘅時候**,call `staleness(data.generated_at, Date.now())`,再 toggle 一個
element。Demo 模式根本唔會 call。

## 5. 版面

`</header>` 同 `<div class="tabs">` 中間一個 element:

```html
<div class="stale-banner" id="staleBanner" role="status" hidden></div>
```

- `role="status"` 會禮貌咁報俾 screen reader 聽,唔會搶 focus。
- **唔俾撳走。** 撳得走嘅提示一定俾人撳走,撳走之後就返返去「睇唔見」,即係原本
  要修嗰個問題。

CSS 淨係用現有 token(`--alert`、`--warn`、`--muted`、`--fs-xs`),唔加新 custom
property,亦**唔可以有 font-size 字面值** —— `test_frontend_typography.py` 係喺成個
stylesheet 做 regex,唔係解析 CSS,寫死一個 px 數值(連註釋入面都算)就會紅。

## 6. 測試

| 檔 | 測乜 |
|---|---|
| `scripts/test_staleness_js.py`(新) | 純函數,喺真 browser 入面 import,同 `test_plan_dates_js.py` 一樣。48 鐘界線兩邊都釘、冇時間戳、爛時間戳、未來時間戳 |
| `scripts/test_frontend_staleness.py`(新) | Playwright:過期 fixture 出到 banner、新鮮 fixture 唔出、demo 模式唔出、`role="status"` 在 |

**Fixture 個日期要由 Python 相對 `now` 計出嚟**(`datetime.now(timezone.utc) -
timedelta(days=5)`),唔可以寫死。寫死嘅話呢兩個 test 自己就會變成下一個「今日過,
聽日紅」嘅計時炸彈 —— 正正係 §3 要避開嗰樣嘢。

## 7. 已知限制

- **佢捉 pipeline 停咗,捉唔到 deploy 停咗。** CI 綠燈但 wrangler 靜靜哋乜都冇上到
  嘅話,`generated_at` 照樣行前,banner 唔會出聲。要補呢個窿要一個 deploy 端嘅
  時間戳,係另一件事。
- **淨係入版嗰陣計一次。** `main.js` 得 load 嗰時行一次,之後個 banner 唔會自己
  出現。開住個 tab 過咗個週末返嚟,見到嘅係星期五嗰個判斷 —— 撳 refresh 先啱。
  加個 timer 定期重算得,但係要一直 hold 住個 clock,而呢頁本身就唔係實時嘅嘢。
- **靠 browser 個 clock。** 用家部機時間唔啱就會誤報。`future` 個 status 至少講得出
  係時間對唔上,唔會扮成「數據舊咗」。
- **淨係一級。** 過咗 48 鐘之後,3 日同 30 日係同一種 banner(得個日數唔同)。暫時
  唔分「漏咗一次」同「條 pipeline 死咗」。
- **唔改任何計算。** 過期嗰陣,「過期 task 數」、SPI、條今日線一律照用
  `generated_at` 做今日,即係照舊唔準。Banner 講嘅係「唔好信呢頁幾新」,唔係幫你
  修正啲數。

## 8. 唔喺範圍

- 改 `refDate()` 或者任何由日期推出嚟嘅計算。
- 撳走 banner。
- 第二級嚴重度。
- Deploy 端時間戳。
