/**
 * i18n dictionary — namespace: project
 * Language: zh (Traditional Chinese / Cantonese)
 * Feeds: docs/js/render-project.js.
 *
 * Values here are copy-pasted verbatim from the literals they replace —
 * 478 existing tests assert on this exact Chinese output. Do not retype.
 * Do not add keys here without a matching key in
 * docs/js/i18n/dict/en/project.js.
 */
export default Object.freeze({
  priority: {
    p0: 'P0 / 嚴重',
    high: '高優先',
    medium: '中優先',
  },
  labels: {
    bug: '缺陷',
  },
  overdueDays: { one: '遲咗 {n} 日', other: '遲咗 {n} 日' },
  openDays: { one: '開咗 {n} 日', other: '開咗 {n} 日' },
  chip: {
    owner: '· 負責人 {owner}',
    unspecifiedOwner: '未指定',
    tooltipSourceLabel: '範圍來源：{path}（{done}/{total} 個核取方塊）',
    tooltipWithIssues: ' · 異常 / 建議來自 GitHub Issue',
    tooltipWithoutIssues: ' · 未使用 GitHub Issue，無日期 / 優先級數據',
    completionPlan: '完成度 {pct}%({done}/{total} · plan.md)',
    noIssuesOrPlan: '未使用 GitHub Issue / 計劃檔',
    issueTooltip: '完成 {done} / 剩餘 {open} · 延誤 {overdue} · 呆滯 {stale} · 分母 = 已建立的 GitHub Issue，未拆成 Issue 的範圍無法顯示',
    completionIssues: '完成度 {pct}%({done}/{total})· {risk}',
  },
  risk: {
    high: '高風險',
    medium: '中風險',
    normal: '正常',
  },
  milestone: {
    due: ' · 期限 {due}',
    planLabel: '計劃',
    sectionTooltip: '{title}（{path}）',
  },
  late: {
    staleDays: { one: '{n} 日冇更新', other: '{n} 日冇更新' },
  },
  empty: {
    noPlanningData: '此範圍未有計劃數據 — 可使用 GitHub Issue（每個 Issue 代表一項工作，並在里程碑設定期限），或在設定檔指定計劃檔（Markdown 核取方塊）。',
    noLateWork: '暫無延誤或呆滯的工作。',
    noTodoWork: '無待處理的 GitHub Issue — 待辦事項已清空。',
  },
});
