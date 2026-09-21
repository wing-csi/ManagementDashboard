/** Representative product signals for the demo dashboard.
 * Production data comes from each repo's configured outcomes_file.
 *
 * `key` indexes docs/js/i18n/dict/{zh,en}/product.js under `outcomes.<key>`,
 * which supplies both the label and the value's unit template per language
 * — never build "value + unit" by concatenation here, render-product.js
 * interpolates it through t() so English word order (unit before/after the
 * number, singular/plural) can differ from Chinese without touching this
 * fixture. */
export const DEMO_OUTCOMES = {
  'wing/abci': {
    updated_at: '2026-07-05',
    adoption: [
      { key: 'weeklyActiveAccounts', value: 1840, change: 12.4, target: 2000 },
      { key: 'activationWithin7Days', value: 68, change: 5.2, target: 75 },
    ],
    customer: [
      { key: 'reconciliationTime', value: 2.1, change: -18.0, target: 2, direction: 'down' },
      { key: 'supportRequestsPer1kOrders', value: 4.6, change: -11.5, target: 4, direction: 'down' },
    ],
  },
  'wing/hk-tax-helper': {
    updated_at: '2026-07-04',
    adoption: [
      { key: 'monthlyActiveFilers', value: 612, change: 8.7, target: 700 },
      { key: 'pdfExportUsage', value: 47, change: 6.1, target: 55 },
    ],
    customer: [
      { key: 'avgTimeSaved', value: 18, change: 12.5, target: 20 },
      { key: 'taxCheckSuccessRate', value: 96.8, change: 1.8, target: 98 },
    ],
  },
};
