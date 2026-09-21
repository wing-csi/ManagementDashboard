/**
 * i18n dictionary — namespace: burndown
 * Language: zh (Traditional Chinese / Cantonese)
 * Feeds: docs/js/render-burndown.js and docs/js/burndown.js.
 *
 * Every value here must stay byte-identical to the literal it replaced in
 * render-burndown.js — scripts/test_frontend_burndown.py pins 38 assertions
 * against this exact copy.
 */
export default Object.freeze({
  na: '—',
  caption: {
    singlePoint: '只有一個觀測點,未成趨勢',
    truncated: '歷史已截斷,理想線由現存最早嗰個觀測起計',
    backfilled: '完成趨勢由 {tasks} 項 task done: 日期回填（覆蓋 {pct}%）；scope 變動只計真實 plan snapshot',
  },
  idealCaption: {
    noDue: 'plan.md 冇 due: — 冇理想線',
    dueUnusable: 'plan.md 個 due: 唔係一個有效日期 — 冇理想線',
    dueNotAfterStart: 'due: 唔遲過起點,拉唔出理想線',
    default: '冇理想線',
  },
  startCaption: {
    plan: '起點:plan.md start:',
    repo: '起點:repo 第一個 commit',
    observation: '起點:第一次改 plan.md',
  },
  startReasonCaption: {
    startUnusable: 'plan.md 個 start: 唔係一個畫得出嘅日期',
    startAfterHistory: 'start: 遲過第一個觀測,冇採用',
  },
  forecastReason: {
    noPlan: '未有計劃範圍',
    notEnoughHistory: '需要最少 2 個觀測點',
    historyTooShort: '需要最少 7 日歷史',
    noObservedProgress: '未觀測到完成速度',
  },
  statusLabel: {
    complete: '已完成',
    onTrack: '按計劃',
    atRisk: '有風險',
    offTrack: '落後計劃',
    unknown: '趨勢未明',
  },
  target: {
    label: '目標日',
    dateInvalid: 'plan.md 日期無效',
    dueNotAfterStart: '目標日唔遲過起點',
    notSet: 'plan.md 未設定',
    cannotCompute: '未能計算剩餘日數',
    daysLeft: '剩 {n} 日',
    overdueDays: '逾期 {n} 日',
  },
  scope: {
    label: '範圍變動',
    noBaseline: '未有歷史基線',
    sinceDate: '由 {date} 起',
    fromStart: '起點',
    detail: '{prefix} {baseline} → 現在 {current}',
  },
  forecast: {
    label: '預測完成',
    completeValue: '已完成',
    actualResult: '實際結果',
    unavailable: '暫時不可用',
    rateDetail: '{rate} 項／週 · {confidence}信心',
    confidenceHigh: '高',
    confidenceMedium: '中',
    confidenceLow: '低',
    late: ' · 遲 {n} 日',
    early: ' · 早 {n} 日',
    onTime: ' · 準時',
  },
  headline: {
    allComplete: '計劃範圍已全部完成',
    behind: '實際進度比今日計劃落後 {n} 個百分點',
    ahead: '實際進度比今日計劃領先 {n} 個百分點',
    onIdeal: '實際進度貼合理想線',
    insufficientData: '現有資料未足以判斷進度差距',
    // Chinese has no grammatical plural, so both branches hold the same
    // string — the shape stays uniform with en so the selection logic never
    // has to know which language it is running under.
    aboveIdeal: { one: '比理想線多 {n} 項未完成', other: '比理想線多 {n} 項未完成' },
    overdueCount: { one: '{n} 項工作已過期', other: '{n} 項工作已過期' },
  },
  summary: {
    progressLabel: '完成進度',
    progressDetail: '{done} / {total} 已完成',
    remainingLabel: '剩餘工作',
    remainingDetail: '項未完成',
  },
  source: {
    backfilledKind: 'task done: 日期 + commit 歷史',
    commitKind: 'commit 歷史',
    asOf: '數據截至 {date} · 每日 05:00 HKT 更新',
    prefix: '來源：{link} {kind}',
  },
  chart: {
    ariaLabel: '{repo} 剩餘工作燃盡圖',
    headTitle: '剩餘工作趨勢',
    headHint: '數字愈接近 0 愈好',
    emptyTitle: '未有足夠觀測畫趨勢',
    emptyHint: '目前只有 1 個 plan.md 歷史點；上面嘅進度同期限仍然可用。',
    datasetRemaining: '剩餘',
    datasetScope: '範圍上限',
    datasetIdeal: '理想剩餘',
    yAxisTitle: '工作數',
    tooltipLabel: '{label}：{value} 項',
    todayLabel: '今日',
  },
  details: {
    summary: { one: '查看 {n} 項未完成工作的期限', other: '查看 {n} 項未完成工作的期限' },
  },
});
