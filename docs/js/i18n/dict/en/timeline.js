/**
 * i18n dictionary — namespace: timeline
 * Language: en (English)
 * Feeds: docs/js/render-timeline.js and docs/js/timeline.js.
 *
 * Wording follows specs/i18n-terminology.md where a term appears there.
 * Terms not in that table are decided locally, consistently with its tone.
 */
export default Object.freeze({
  spiLabel: 'SPI {spi} · {band}',
  band: {
    onTrack: 'Keeping up',
    behind: 'Behind',
    seriouslyBehind: 'Seriously behind',
  },
  noSpi: {
    noDue: 'plan.md has no due: — no SPI',
    dueUnusable: "plan.md's due: is not a valid date — no SPI",
    dueNotAfterStart: 'due: is not after the start — no SPI',
    notStarted: 'Not started',
    noTasks: 'plan.md has no tasks',
    default: 'No SPI',
  },
  daysLeft: '{n} d left',
  daysLate: '{n} d late',
  overdueCount: { one: '{n} task overdue', other: '{n} tasks overdue' },
  note: {
    onlyUnfinished: 'This line only shows unfinished work',
    allDone: 'Nothing left',
    noDues: "plan.md's tasks have no due: dates",
    noDue: 'No target date — the timeline runs up to today',
    dueUnusable: 'Target date is not a valid date — the timeline runs up to today',
    dueNotAfterStart: "Target date is not after the plan's start — the timeline runs up to today",
    invalidDues: {
      one: "{n} task's due: is not a valid date — not drawn",
      other: "{n} tasks' due: are not valid dates — not drawn",
    },
  },
});
