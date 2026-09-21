/**
 * i18n dictionary — namespace: management
 * Language: zh (Traditional Chinese / Cantonese)
 * Feeds: docs/js/render-management.js and docs/js/management.js.
 *
 * Values here are copy-pasted verbatim from the literals they replace —
 * 478 existing tests assert on this exact Chinese output. Do not retype.
 * Do not add keys here without a matching key in
 * docs/js/i18n/dict/en/management.js.
 */
export default Object.freeze({
  status: {
    onTrack: '進度正常',
    atRisk: '存在風險',
    offTrack: '偏離計劃',
    unknown: '未知',
  },
  health: {
    healthy: '最新',
    attention: '需要關注',
    stale: '已過時',
    unreadable: '未知',
    future: '時鐘不一致',
    unknown: '未知',
  },
  confidence: {
    actual: '實際',
    high: '高',
    medium: '中',
    low: '低',
  },
  forecastReason: {
    noPlan: '未有計劃',
    notEnoughHistory: '觀測點不足',
    historyTooShort: '歷史少過 7 日',
    noObservedProgress: '未觀測到完成進度',
  },
  headline: {
    countOffTrack: { one: '{n} 個偏離計劃', other: '{n} 個偏離計劃' },
    countAtRisk: { one: '{n} 個存在風險', other: '{n} 個存在風險' },
    countUnknown: { one: '{n} 個未知', other: '{n} 個未知' },
    countOnTrack: { one: '{n} 個進度正常', other: '{n} 個進度正常' },
    planningRatio: '{planning}/{repos} 有計劃',
    historyRatio: '{planHistory}/{repos} 有歷史',
    errorsCount: { one: '{n} 個錯誤', other: '{n} 個錯誤' },
  },
  scope: {
    noNetChange: '範圍無淨變動',
    netChange: '範圍淨變動 {net}',
    added: '新增 {n}',
    removed: '移除 {n}',
    historyRatio: '{historyRepos}/{scopeRepos} 有歷史',
    planCount: { one: '{n} 個計劃', other: '{n} 個計劃' },
    noHistory: '無範圍歷史',
    noPlanHistory: '未有計劃歷史',
  },
  forecast: {
    lateCount: { one: '{n} 個預測延誤', other: '{n} 個預測延誤' },
    reposWithScope: '有計劃範圍的程式庫',
    noScope: '未有計劃範圍',
    complete: '已完成',
    unavailable: '預測不可用',
    projected: '預測 {date} · {confidence}信心',
    lateSuffix: ' · 遲過目標日',
  },
  project: {
    scopeChange: '範圍 {net}',
    noKnownRisk: '冇已知風險',
    ownerSuffix: ' · 負責人 {owner}',
    emptyScope: '此範圍內沒有程式庫。',
  },
  attention: {
    empty: '目前冇需要即時跟進嘅已知項目。',
    staleDataTitle: '儀表板數據唔新鮮',
    generatedAtDetail: '產生時間 {ts}',
    issueCollectionFailedTitle: {
      one: '{n} 個程式庫收集唔到 GitHub Issue',
      other: '{n} 個程式庫收集唔到 GitHub Issue',
    },
    repoCollectionFailedTitle: '程式庫收集失敗',
    dueDetail: '{repo} · 期限 {due}',
    forecastLateTitle: '{repo} 預測遲過目標日',
    forecastLateDetail: '預測 {projected} · 期限 {due} · {confidence}信心',
    redlineLabel: '治理紅線',
    ciFailLabel: 'CI 失敗',
    repoLabelDetail: '{repo} · {label}',
  },
  reasons: {
    staleSnapshot: '快照唔新鮮',
    issueCollectionFailed: 'GitHub Issue 收集失敗',
    highOverdue: { one: '{n} 個高優先項目逾期', other: '{n} 個高優先項目逾期' },
    duePassed: '計劃目標日已過',
    overdueCount: { one: '{n} 個項目逾期', other: '{n} 個項目逾期' },
    staleIssues: { one: '{n} 個 GitHub Issue 呆滯', other: '{n} 個 GitHub Issue 呆滯' },
    spi: 'SPI {spi}',
    ciPass: 'CI {pct}%',
    redlines: { one: '{n} 個治理紅線', other: '{n} 個治理紅線' },
  },
});
