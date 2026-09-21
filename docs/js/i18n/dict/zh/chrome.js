/**
 * i18n dictionary — namespace: chrome
 * Language: zh (Traditional Chinese / Cantonese)
 * Feeds: docs/index.html (masthead, tabs, filters, load-error banner,
 *        footer) and the dynamic chrome built in docs/js/main.js (eyebrow,
 *        repo/branch/contributor select options, footStamp).
 *
 * Every value below is copy-pasted byte-for-byte from the literal it
 * replaces — that is what keeps scripts/test_frontend_snapshot.py and the
 * rest of the existing zh-default suite green. Do not retype by hand.
 */
export default Object.freeze({
  title: 'AI 自動化水平儀',
  brand: '自動化水平儀',
  telemetry: 'GITHUB 數據監測',
  demoBadge: '示範數據 · 手動要求（?demo=1）',

  repoAriaLabel: '程式庫',
  branchAriaLabel: '分支',
  contributorAriaLabel: '貢獻者',
  windowAriaLabel: '統計範圍',

  window30: '近 30 日',
  window60: '近 60 日',
  window90: '近 90 日',
  window180: '近 180 日',

  tablistAriaLabel: '儀表板分頁',
  tabOverview: '總覽',
  tabQuality: '品質',
  tabProjects: '項目 & 團隊',
  tabProduct: '產品 & 發佈',
  tabTasks: '工作',

  loadErrorTitle: '載入數據失敗。',
  loadErrorSignedOut: '未登入或者工作階段已過期？',
  loadErrorRelogin: '重新登入',
  loadErrorDemoHint: '。想睇示範數據：',

  footerSource: '資料來源：GitHub GraphQL API → scripts/collect_github.py → GitHub Actions（每日驗證）→ 本機檢視',

  // Built dynamically in docs/js/main.js
  repoCount: { one: '{n} 個程式庫', other: '{n} 個程式庫' },
  ownerLabel: '負責人 {name}',
  byOwnerGroup: '按負責人',
  individualReposGroup: '個別程式庫',
  ownerProjectsOption: '{owner} 的項目 ({n})',
  allRepos: '全部程式庫',
  allBranches: '全部分支',
  allContributors: '全部成員',
  branchSelectTitle: '選擇單一程式庫後才可篩選分支',
  signInRequired: '需要登入。',
  networkError: '網絡錯誤',
  loadErrorDetailWrapped: '（{detail}）',
  generatedAt: '產生於 {ts}',

  // DORA strip — kept in chrome (not kpi) because docs/index.html is
  // exclusively this track's file; see specs/i18n-terminology.md Core metrics.
  doraDeployFreq: '部署頻率',
  doraLeadTime: '前置時間（至合併）',
  doraLeadTimeSub: 'PR 開啟 → 合併時間中位數',
  doraChangeFailureRate: '回退密度',
  doraChangeFailureRateSub: '補救工作 ÷ 全部工作',
  doraMttr: 'MTTR（近似）',
  doraMttrSub: '修復類工作的前置時間中位數',
});
