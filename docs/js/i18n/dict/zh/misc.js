/**
 * i18n dictionary — namespace: misc
 * Language: zh (Traditional Chinese / Cantonese)
 * Feeds: catch-all for copy not owned by another namespace — panel headings,
 *        card-notes, table headers and filter controls in docs/index.html
 *        (owned by this track: TRACK A / static chrome), plus
 *        docs/js/staleness.js.
 *
 * Every value below is copy-pasted byte-for-byte from the literal it
 * replaces — that is what keeps scripts/test_frontend_snapshot.py and the
 * rest of the existing zh-default suite green. Do not retype by hand.
 */
export default Object.freeze({
  // <h2> headings
  h2ManagementAttention: '管理層需關注',
  h2ProjectOutlook: '項目前景',
  h2SpectrumDistribution: '自動化水平分佈',
  h2WeeklyMixTrend: '每週工作構成 × L3+ 趨勢',
  h2Alerts: '異常提醒',
  h2QualityAutomation: '品質 × 自動化',
  h2DefectTracking: '缺陷追蹤',
  h2ProjectProgress: '項目進度',
  h2RepoOverview: '程式庫概覽',
  h2ReleaseReadiness: '發佈準備狀態',
  h2RecentTasks: '最近工作',
  // shared between the <h2> and the <div class="label"> that repeat it
  roadmapEpics: '路線圖 / 大型工作項',

  // .card-note
  cardNoteAttentionScope: '逾期 · 數據失敗 · 預測 · CI · 治理紅線',
  cardNoteProjectOutlook: '規則式狀態 · 無資料一律標示為「未知」',
  cardNoteWeeklyMix: '長條 = 每週工作數 · 折線 = L3+ %',
  cardNoteQuality: 'fix / hotfix / revert 標題前綴 · PR 打回輪數（以推送分隔）',
  cardNoteDefectSourcePrefix: '來源：有 bug 標籤的 GitHub Issue + 計劃檔 ',
  cardNoteDefectSourceSuffix: ' · 未修優先 · ',
  cardNoteProjectProgress: '來源：GitHub Issue / 里程碑 · 完成度以已建立的 Issue 計算',
  cardNoteRepoOverview: '程式語言按位元組計算 · 月度活躍度不受統計範圍影響',
  cardNoteReleaseReadiness: '範圍完成度 · 阻礙項目 · CI · 期限 · 上次發佈',
  cardNoteTasksTable: '每項工作顯示所屬 PR · 直接提交標示為無 PR',

  // .proj-h
  projHLateWork: '異常工作（延誤 / 呆滯 >14 日）',
  projHTodayPriority: '今日建議優先處理',
  projHCodebase: '程式碼庫（語言構成）',
  projHCommitTypes: '提交類型（統計範圍內）',
  projHMonthlyActivity: '月度活躍(全收集範圍)',
  projHContributors: '貢獻者',

  // .label
  labelPortfolioDelivery: '項目組合交付',
  labelDataHealth: '數據健康狀態',
  labelCurrentScope: '目前計劃範圍',
  labelForecastCoverage: '預測覆蓋率',
  labelL3Hero: 'L3+ 自動化佔比 — 北極星',
  labelLocApprox: '出碼率（近似）',
  labelClassifiedTasks: '已分級工作',
  labelClassificationCoverage: '分級覆蓋率',
  labelReleaseCount: '發佈次數',
  labelReadyToRelease: '可發佈',
  labelOutcomeDataCoverage: '成果數據覆蓋率',
  labelDefectRate: '缺陷率',
  labelReworkShare: '修復佔比',
  labelChangesRequestedRate: 'PR 打回率',
  labelReworkTurnaround: '返工周轉時間',
  labelPrAcceptRate: 'PR 接受率',
  labelEffectiveTasksPerWeek: '每週有效工作數',
  labelReworkByLevel: '各級別的修復佔比',

  // <th>
  thId: '編號',
  thRepo: '程式庫',
  thSeverity: '嚴重程度',
  thDescription: '描述',
  thStatus: '狀態',
  thOwner: '負責人',
  thDeadline: '期限',
  thDate: '日期',
  thAuthor: '作者',
  thPr: '所屬 PR',
  thBranch: '分支',
  thTitle: '標題',
  thLevel: '級別',
  thDelta: '± 行數',

  // level / status filter buttons
  filterAll: '全部',
  levelNone: '未分級',
  statusRedline: '紅線',
  statusWarning: '治理警告',
  statusSuspect: '級別矛盾',
  statusCiFail: 'CI 失敗',
  levelFilterLabel: '級別',
  statusFilterLabel: '狀態',

  // task search
  taskSearchPlaceholder: '搜尋標題 / 作者 / 分支 / PR',
  taskSearchAriaLabel: '搜尋工作',

  // docs/js/staleness.js — {days} is the interpolated age in days
  staleMessage: '數據係 {days} 日前嘅舊快照；所有「今日」、逾期同預測都以舊數據為準。請到 GitHub Actions 檢查最近的收集及部署工作流程。',
  unreadableMessage: '讀唔到數據嘅時間戳，所以唔知呢頁係幾時嘅數。請檢查 metrics.json 的 generated_at 欄位。',
  futureMessage: '數據嘅時間戳喺未來，本機或數據收集器的時間唔啱。呢頁所有「今日」、過期同 SPI 都信唔過。',

  // Follow-up sweep: remaining static text in docs/index.html
  managementSummaryAriaLabel: '管理摘要',
  subL3Hero: '工作由 AI 代理主導完成的比例',
  subLocApprox: 'L2+ 工作插入行數佔比',
  thresholdL3: 'L3 自動化門檻',
  ragHintPrefix: '灰燈 = 無品質信號（PR 需要有 CI 檢查，或在設定檔指定 ',
  ragHintSuffix: '）— 詳見 README 品質指標',
  scopeNoteRagFullRepo: '紅黃綠燈為全程式庫範圍',
  subEffectiveTasks: '改動 ≥10 行的工作',
  scopeNoteFullRepo: '全程式庫範圍',
  h3PlanAssignment: 'Plan 工作分配',
  pPlanAssignmentDesc: 'assignee:Name / @GitHub-handle task 數 ÷ plan 總 task 數 · 未標記則使用程式庫負責人',
  h3DefectFix: 'Defect 修復分佈',
  pDefectFixDesc: 'fixed-by:Name · 未修亦計入總數',
  subRoadmapEpics: '里程碑 + 計劃分段',
  subReleaseCount: '目前統計範圍 · 依次採用部署、標籤或發佈記錄',
  subReadyToRelease: '已準備 / 有計劃範圍的程式庫',
  subOutcomeDataCoverage: '有成果數據檔 / 範圍內程式庫',
  loadMore: '載入更多',
});
