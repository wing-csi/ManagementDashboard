/**
 * i18n dictionary — namespace: product
 * Language: zh (Traditional Chinese / Cantonese)
 * Feeds: docs/js/render-product.js and docs/data/demo-outcomes.js.
 *
 * Every value here must stay byte-identical to the literal it replaced in
 * render-product.js — scripts/test_frontend_i18n_table.py asserts against
 * this exact copy. `outcomes.*` entries are new copy introduced alongside
 * the render-product.js outcomes section (there is no pre-existing literal
 * to match byte-for-byte), but must still read naturally in zh.
 *
 * Plural leaves keep the `{ one, other }` shape on BOTH languages even
 * though zh has no grammatical plural — see docs/js/i18n/index.js.
 */
export default Object.freeze({
  readiness: {
    ready: '已準備',
    onTrack: '進度正常',
    watch: '需要留意',
    atRisk: '存在風險',
    unavailable: '未有範圍',
  },
  sourceLabel: {
    milestone: '里程碑',
    plan: '計劃',
  },

  readinessEmpty: '此範圍內沒有程式庫。',
  roadmapEmpty: '未有里程碑或計劃分段。',
  noCiData: 'CI 無數據',
  ciValue: 'CI {value}%',
  noDueDate: '未設期限',
  dueLabel: '期限 {due}',
  noReleaseHistory: '未有發佈記錄',
  lastReleaseLabel: '上次發佈 {date}',
  noScope: '未有里程碑 / 計劃範圍',
  blockerCount: { one: '{n} 個阻礙項目', other: '{n} 個阻礙項目' },
  roadmapShown: '顯示 {shown} / {total}',
  roadmapCount: { one: '{n} 個大型工作項', other: '{n} 個大型工作項' },

  outcomesTitle: '成果數據',
  outcomesEmpty: '此範圍內沒有成果數據。',
  outcomes: {
    weeklyActiveAccounts: { label: '每週活躍帳戶', unit: { one: '{value} 個帳戶', other: '{value} 個帳戶' } },
    activationWithin7Days: { label: '7 日內完成啟用', unit: '{value}%' },
    reconciliationTime: { label: '對帳時間', unit: '{value} 小時' },
    supportRequestsPer1kOrders: { label: '每千張訂單的支援請求', unit: { one: '{value} 張', other: '{value} 張' } },
    monthlyActiveFilers: { label: '每月活躍報稅者', unit: { one: '{value} 位使用者', other: '{value} 位使用者' } },
    pdfExportUsage: { label: 'PDF 匯出使用率', unit: '{value}%' },
    avgTimeSaved: { label: '平均節省時間', unit: '{value} 分鐘' },
    taxCheckSuccessRate: { label: '報稅檢查成功率', unit: '{value}%' },
  },
});
