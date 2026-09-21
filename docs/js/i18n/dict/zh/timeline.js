/**
 * i18n dictionary — namespace: timeline
 * Language: zh (Traditional Chinese / Cantonese)
 * Feeds: docs/js/render-timeline.js and docs/js/timeline.js.
 *
 * Every value here must stay byte-identical to the literal it replaced in
 * render-timeline.js — scripts/test_frontend_timeline.py pins assertions
 * against this exact copy.
 */
export default Object.freeze({
  spiLabel: 'SPI {spi} · {band}',
  band: {
    onTrack: '追得上',
    behind: '落後',
    seriouslyBehind: '嚴重落後',
  },
  noSpi: {
    noDue: 'plan.md 冇 due: — 冇 SPI',
    dueUnusable: 'plan.md 個 due: 唔係一個有效日期 — 冇 SPI',
    dueNotAfterStart: 'due: 唔遲過起點 — 冇 SPI',
    notStarted: '未開始',
    noTasks: 'plan.md 冇工作',
    default: '冇 SPI',
  },
  daysLeft: '剩 {n} 日',
  daysLate: '遲咗 {n} 日',
  overdueCount: { one: '{n} 項工作過咗期', other: '{n} 項工作過咗期' },
  note: {
    onlyUnfinished: '條線只畫未做嘅工作',
    allDone: '冇嘢剩低',
    noDues: 'plan.md 的工作冇寫 due:',
    noDue: '冇目標日，時間條畫到今日為止',
    dueUnusable: '目標日唔係一個有效日期，時間條畫到今日為止',
    dueNotAfterStart: '目標日唔遲過計劃起點，時間條畫到今日為止',
    invalidDues: {
      one: '{n} 項工作的 due: 唔係有效日期，冇畫',
      other: '{n} 項工作的 due: 唔係有效日期，冇畫',
    },
  },
});
