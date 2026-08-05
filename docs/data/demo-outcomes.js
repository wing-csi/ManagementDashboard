/** Representative product signals for the demo dashboard.
 * Production data comes from each repo's configured outcomes_file. */
export const DEMO_OUTCOMES = {
  'wing/abci': {
    updated_at: '2026-07-05',
    adoption: [
      { label: '每週活躍帳戶', value: 1840, unit: ' 個帳戶', change: 12.4, target: 2000 },
      { label: '7 日內完成啟用', value: 68, unit: '%', change: 5.2, target: 75 },
    ],
    customer: [
      { label: '對帳時間', value: 2.1, unit: ' 小時', change: -18.0, target: 2, direction: 'down' },
      { label: '每千張訂單的支援請求', value: 4.6, unit: ' 張', change: -11.5, target: 4, direction: 'down' },
    ],
  },
  'wing/hk-tax-helper': {
    updated_at: '2026-07-04',
    adoption: [
      { label: '每月活躍報稅者', value: 612, unit: ' 位使用者', change: 8.7, target: 700 },
      { label: 'PDF 匯出使用率', value: 47, unit: '%', change: 6.1, target: 55 },
    ],
    customer: [
      { label: '平均節省時間', value: 18, unit: ' 分鐘', change: 12.5, target: 20 },
      { label: '報稅檢查成功率', value: 96.8, unit: '%', change: 1.8, target: 98 },
    ],
  },
};
