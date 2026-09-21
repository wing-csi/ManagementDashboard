/**
 * i18n dictionary — namespace: table
 * Language: zh (Traditional Chinese / Cantonese)
 * Feeds: docs/js/render-table.js.
 *
 * Every value here must stay byte-identical to the literal it replaced in
 * render-table.js — scripts/test_frontend_i18n_table.py and the wider
 * frontend suite assert against this exact copy.
 */
export default Object.freeze({
  typeLabel: {
    feat: '功能', fix: '修復', hotfix: '緊急修復', revert: '回退', refactor: '重構',
    test: '測試', docs: '文件', chore: '雜項', build: '建置', ci: 'CI', perf: '效能',
    style: '格式', other: '其他',
  },
  unassigned: '未指定',
  fixedUnassigned: '已修 · 未指定',

  pie: {
    planLabel: '計劃工作',
    planSub: '項工作',
    planEmpty: '未有可用分配數據 — 請設定程式庫負責人或工作負責人。',
    defectLabel: '缺陷',
    defectSub: '{n} 已修',
    defectEmpty: '未有缺陷數據 — 可使用有 bug 標籤的 GitHub Issue、計劃檔 #bug 或缺陷登記冊。',
    unfixed: '未修',
  },

  overview: {
    noLanguageData: '無語言數據',
    repoSize: '程式庫大小 {mb} MB（Git）',
    noWorkInScope: '此範圍內無工作',
    noData: '無數據',
    taskCountSuffix: ' 項工作',
    scopeShare: '佔此範圍 {pct}%',
  },

  defects: {
    severityHigh: '高',
    severityMedium: '中',
    severityLow: '低',
    countCapped: '{n} 項,顯示頭 {cap}',
    count: '{n} 項',
    planSource: '計劃',
    statusOpen: '未修',
    statusFixed: '已修',
    emptyPrefix: '無缺陷 — 可建立有 bug 標籤的 GitHub Issue，或在計劃檔寫入 ',
    emptyCode: '- [ ] … #bug !P1 due:2026-08-01',
  },

  row: {
    directCommitTooltip: '直接提交 · 無所屬 PR',
    noPr: '無 PR',
    commitTooltip: '提交 {id}',
    prAriaLabel: 'PR #{id}',
    emptyTable: '此範圍內無工作',
    shownCount: '顯示 {shown} / {total} 項工作',
  },
});
