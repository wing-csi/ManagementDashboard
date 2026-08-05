/** Representative product signals for the demo dashboard.
 * Production data comes from each repo's configured outcomes_file. */
export const DEMO_OUTCOMES = {
  'wing/abci': {
    updated_at: '2026-07-05',
    adoption: [
      { label: 'Weekly active accounts', value: 1840, unit: ' accounts', change: 12.4, target: 2000 },
      { label: 'Activated in 7 days', value: 68, unit: '%', change: 5.2, target: 75 },
    ],
    customer: [
      { label: 'Reconciliation time', value: 2.1, unit: ' hours', change: -18.0, target: 2, direction: 'down' },
      { label: 'Support tickets / 1k orders', value: 4.6, unit: ' tickets', change: -11.5, target: 4, direction: 'down' },
    ],
  },
  'wing/hk-tax-helper': {
    updated_at: '2026-07-04',
    adoption: [
      { label: 'Monthly active filers', value: 612, unit: ' users', change: 8.7, target: 700 },
      { label: 'PDF export adoption', value: 47, unit: '%', change: 6.1, target: 55 },
    ],
    customer: [
      { label: 'Average time saved', value: 18, unit: ' min', change: 12.5, target: 20 },
      { label: 'Successful filing checks', value: 96.8, unit: '%', change: 1.8, target: 98 },
    ],
  },
};
