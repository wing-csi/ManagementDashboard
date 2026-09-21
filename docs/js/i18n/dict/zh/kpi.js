/**
 * i18n dictionary — namespace: kpi
 * Language: zh (Traditional Chinese / Cantonese)
 * Feeds: docs/js/render-kpi.js.
 *
 * Every zh value here is a verbatim copy of the literal it replaces in
 * docs/js/render-kpi.js / docs/js/aggregate.js — do not retype, and do not
 * "clean up" punctuation (fullwidth vs halfwidth chars are intentional).
 */
export default Object.freeze({
  mode: {
    auto: '自動',
    manual: '手動',
  },
  method: {
    label: '標籤',
    rule: '規則',
    trailer: '尾註',
    inference: '推斷',
  },
  events: {
    deployments: '部署',
    tags: '標籤',
    releases: '發佈',
  },
  delta: '{arrow} {value}{unit}，較上一段',
  units: {
    pp: ' 個百分點',
    count: ' 個',
    perWeek: '<span class="unit">次/週</span>',
    times: '<span class="unit">次</span>',
  },
  fmtHours: {
    hours: '{h}<span class="unit">小時</span>',
    days: '{d}<span class="unit">日</span>',
  },
  tasksSub: {
    one: '共 {count} 項工作 · 模式：{mode}',
    other: '共 {count} 項工作 · 模式：{mode}',
  },
  untaggedSub: {
    one: '未分級 {count} 項工作',
    other: '未分級 {count} 項工作',
  },
  specNote: '已分級 {tagged} / {total}',
  chartYAxis: '工作數',
  alerts: {
    l3DownTitle: 'L3+ 佔比週環比下跌 {n} 個百分點',
    l3DownDetail: '{a}% → {b}%。檢查工作類型有無轉變，或者測試框架 / 工具鏈出咗問題。',
    l3UpTitle: 'L3+ 佔比週環比上升 {n} 個百分點',
    l3UpDetail: '{a}% → {b}%。',
    lowCoverageTitle: '分級覆蓋率偏低（{n}%）',
    lowCoverageDetail: '為 PR 加上 ai-level 標籤，或在提交 / PR 內文加上 AI-Level 尾註，否則指標會失真。',
    l3MilestoneTitle: 'L3+ 佔比突破 30% 里程碑',
    l3MilestoneDetail: '本段 {cur}%，上一段 {prev}%。',
    noHighAutonomyTitle: '近兩週無 L4+ 工作',
    noHighAutonomyDetail: '高度自動化流程（端對端流程 + 自動驗證）可能已停用。',
    redLine: '紅線',
    warning: '警告',
    violationTitle: {
      one: '{prefix}：{n} 項工作 {label}',
      other: '{prefix}：{n} 項工作 {label}',
    },
    violationRedDetail: '規範四紅線 — 需要審核並跟進；表格以 ⛔ 標記涉事列。',
    violationWarnDetail: '表格以 ⛔ 標記涉事列。',
    reworkUpTitle: '修復佔比上升 {n} 個百分點',
    reworkUpDetail: '{pf}% → {cf}%，可能係前一段輸出嘅質量問題浮現緊。',
    suspectTitle: {
      one: '{n} 項工作的級別聲稱與 PR 行為有矛盾',
      other: '{n} 項工作的級別聲稱與 PR 行為有矛盾',
    },
    suspectDetail: '表格以 ⚠ 標記相關列：聲稱 L4/L5，但觀察到人工介入（審核 / 混合提交 / 無測試），建議覆核。',
    collectionFailedTitle: {
      one: '{n} 個程式庫收集失敗',
      other: '{n} 個程式庫收集失敗',
    },
    none: '暫無異常,指標喺正常範圍。',
  },
  dora: {
    noRecords: '無標籤 / 發佈 / 部署記錄',
    deploySub: {
      one: '{n} 次（{label}）',
      other: '{n} 次（{label}）',
    },
    deploySubLow: '{days} 日內（{label}）· 平均每 {weeks} 週 1 次',
    noWorkInScope: '此範圍內無工作',
    remedySub: {
      one: '{n} / {total} 項工作屬補救',
      other: '{n} / {total} 項工作屬補救',
    },
  },
  rag: {
    insufficient: '資料不足',
    red: '紅',
    amber: '黃',
    green: '綠',
    ciRate: 'CI 通過率 {rate}%（{pass}/{total}）',
    coverage: '測試覆蓋率 {coverage}%',
    security: '安全性：嚴重 {critical} / 高 {high} / 中 {medium}',
    noData: '無 CI 檢查 / 品質數據檔',
  },
  quality: {
    fixSub: '{fix} 項修復 / 回退工作，共 {total} 項',
    reworkSub: '{n} / {total} 個經審核的 PR 被打回',
    reworkMedianRounds: ' · 中位 {n} 輪',
    noReviewedPRs: '此範圍內無經審核的 PR',
    noPRs: '此範圍內無 PR',
    turnSubCounted: {
      one: '由第一次打回到合併 · {n} 個 PR',
      other: '由第一次打回到合併 · {n} 個 PR',
    },
    turnSubPostMerge: '被打回的 PR 都是在合併後才收到打回，無返工時間可計',
    turnSubNone: '此範圍內無被打回嘅 PR',
    acceptNeedsAllScope: '需要全員範圍（已關閉 PR 無人員維度）',
    acceptSub: '{merged} 個已合併 / {closed} 個已關閉但未合併',
    noDefectFile: '未有程式庫設定缺陷數據檔',
    defectFoundBit: '{found} 個在 {days} 日內發現 / {denom} 項工作',
    defectOpenBit: '{n} 個未修',
    defectUndatedBit: '{n} 個無發現日期',
    defectTruncatedBit: '清單已截斷',
    noClassifiedWork: '未有已分級工作',
  },
  violations: {
    'direct-push-main': '直接推送到受監察分支（冇 PR）',
    'forbidden-files': '提交咗 .env / node_modules / __pycache__',
    'workflow-deleted': '刪除咗 GitHub Actions 工作流程',
    'cross-branch-merge': '跨功能分支合併',
    'core-without-double-review': '核心模組改動欠二次複核',
    'merged-without-review': '未經任何審核就合併',
    'oversized-pr': '超大 PR（欠分階段提交）',
  },
});
