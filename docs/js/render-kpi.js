/* Chart.js 4.4.1 is loaded globally from the CDN <script> in index.html */

import { state, $, pct, esc, windowTasks, repoInScope } from './data.js';
import {
  LEVELS, META, UNTAGGED_COLOR, INK, VIOLATION_META, median, fmtHours,
  statsFromTasks, weekL3pct, fillGaps, metaInWindow, defectsInScope,
} from './aggregate.js?v=i18n-20260922-1';
import { t, LOCALE } from './i18n/index.js';

const MODE_LABEL = { auto: t('kpi.mode.auto'), manual: t('kpi.mode.manual') };
const METHOD_LABEL = {
  label: t('kpi.method.label'), rule: t('kpi.method.rule'),
  trailer: t('kpi.method.trailer'), inference: t('kpi.method.inference'),
};
const EVENT_LABEL = {
  deployments: t('kpi.events.deployments'), tags: t('kpi.events.tags'), releases: t('kpi.events.releases'),
};

function setDelta(el, curr, prev, unitKey) {
  if (curr == null || prev == null) { el.textContent = ''; return; }
  const d = curr - prev;
  const cls = Math.abs(d) < 0.05 ? 'flat' : d > 0 ? 'up' : 'down';
  el.className = 'delta ' + cls;
  const unit = unitKey ? t(`kpi.units.${unitKey}`) : '';
  el.textContent = t('kpi.delta', { arrow: d >= 0 ? '▲' : '▼', value: Math.abs(d).toFixed(1), unit });
}

export function renderKPIs(cur, prev) {
  const l3 = pct(cur.l3plus, cur.tagged);
  $('kpiL3').innerHTML = l3 == null ? '–' : `${l3}<span class="unit">%</span>`;
  setDelta($('kpiL3d'), l3 && +l3, pct(prev.l3plus, prev.tagged) && +pct(prev.l3plus, prev.tagged), 'pp');

  const loc = pct(cur.insAi, cur.insTotal);
  $('kpiLoc').innerHTML = loc == null ? '–' : `${loc}<span class="unit">%</span>`;
  setDelta($('kpiLocd'), loc && +loc, pct(prev.insAi, prev.insTotal) && +pct(prev.insAi, prev.insTotal), 'pp');

  $('kpiTasks').textContent = cur.tagged.toLocaleString(LOCALE);
  $('kpiTasksSub').textContent = t('kpi.tasksSub', {
    n: cur.total,
    count: cur.total.toLocaleString(LOCALE),
    mode: MODE_LABEL[state.data.mode] || state.data.mode || '–',
  });
  setDelta($('kpiTasksd'), cur.tagged, prev.total ? prev.tagged : null, 'count');

  const cov = pct(cur.tagged, cur.total);
  const covEl = $('kpiCov');
  covEl.innerHTML = cov == null ? '–' : `${cov}<span class="unit">%</span>`;
  covEl.classList.toggle('warned', cov != null && +cov < 80);
  $('kpiCovSub').textContent = t('kpi.untaggedSub', { n: cur.untagged, count: cur.untagged.toLocaleString(LOCALE) });
  setDelta($('kpiCovd'), cov && +cov, pct(prev.tagged, prev.total) && +pct(prev.tagged, prev.total), 'pp');
}

export function renderSpectrum(cur) {
  const strip = $('strip');
  const legend = $('legend');
  strip.innerHTML = '';
  legend.innerHTML = '';
  const parts = Object.entries(cur.methods).sort((a, b) => b[1] - a[1])
    .map(([k, v]) => `${METHOD_LABEL[k] || k} ${v}`);
  $('specNote').textContent = t('kpi.specNote', { tagged: cur.tagged, total: cur.total }) + (parts.length ? ' · ' + parts.join(' · ') : '');

  const total = cur.total || 1;
  const segs = [{ key: 'untagged', n: cur.untagged }].concat(LEVELS.map((l) => ({ key: l, n: cur.byLevel[l] })));
  for (const seg of segs) {
    if (!seg.n) continue;
    const div = document.createElement('div');
    const share = (seg.n / total) * 100;
    div.className = 'seg' + (seg.key === 'untagged' ? ' untagged' : META[seg.key].dark ? ' dark' : '');
    div.style.flex = `0 0 ${share}%`;
    if (seg.key !== 'untagged') div.style.background = META[seg.key].color;
    div.innerHTML = `<span>${share >= 7 ? (seg.key === 'untagged' ? '—' : seg.key) : ''}</span>`;
    div.title = `${seg.key === 'untagged' ? t('levels.untagged') : seg.key + ' ' + META[seg.key].name}: ${seg.n} (${share.toFixed(1)}%)`;
    strip.appendChild(div);
  }
  const below = cur.untagged + cur.byLevel.L1 + cur.byLevel.L2;
  $('threshold').style.left = `${(below / total) * 100}%`;
  $('threshold').style.display = cur.total ? 'block' : 'none';

  const rows = LEVELS.map((l) => ({ key: l, n: cur.byLevel[l] })).concat([{ key: 'untagged', n: cur.untagged }]);
  for (const r of rows) {
    const isU = r.key === 'untagged';
    const share = cur.tagged && !isU ? (r.n / cur.tagged) * 100 : cur.total && isU ? (r.n / cur.total) * 100 : 0;
    const row = document.createElement('div');
    row.className = 'row';
    row.innerHTML = `
      <span class="lv"><span class="dot" style="background:${isU ? UNTAGGED_COLOR : META[r.key].color}"></span>${isU ? '—' : r.key}</span>
      <span class="lv-name">${isU ? t('levels.untagged') : META[r.key].name}</span>
      <span class="bar-track"><span class="bar-fill" style="width:${share}%;background:${isU ? UNTAGGED_COLOR : META[r.key].color}"></span></span>
      <span class="n">${r.n}</span>
      <span class="p">${share.toFixed(1)}%${isU ? '*' : ''}</span>`;
    legend.appendChild(row);
  }

  // 縮細版嘅 strip,擺入 hero card:個總數同佢嘅構成一齊睇到,唔使隔住 300px。
  // 只計已分級 levels — hero 講嘅係 L3+ ÷ 已分級,加返未分級會同個分母唔一致。
  $('heroSpark').innerHTML = LEVELS
    .filter((l) => cur.byLevel[l] > 0)
    .map((l) => `<span style="flex:${cur.byLevel[l]};background:${META[l].color}"></span>`)
    .join('');
}

export function renderChart(weeklyRows) {
  if (typeof Chart === 'undefined') return; // CDN 未 load 到,唔好阻住其他區塊
  const filled = fillGaps(weeklyRows);
  const labels = filled.map((w) => w.week_start.slice(5));
  const dataFor = (l) => filled.map((w) => w.by_level[l] || 0);
  const line = filled.map((w) => { const v = weekL3pct(w); return v == null ? null : +v.toFixed(1); });

  if (state.chart) state.chart.destroy();
  Chart.defaults.font.family = "'IBM Plex Mono', monospace";
  Chart.defaults.font.size = 10.5;
  Chart.defaults.color = '#6A7370';

  state.chart = new Chart($('weeklyChart'), {
    data: {
      labels,
      datasets: [
        ...LEVELS.map((l) => ({ type: 'bar', label: l, data: dataFor(l), backgroundColor: META[l].color, stack: 's', borderRadius: 2 })),
        { type: 'bar', label: t('levels.untagged'), data: filled.map((w) => w.untagged || 0), backgroundColor: UNTAGGED_COLOR, stack: 's', borderRadius: 2 },
        { type: 'line', label: 'L3+ %', data: line, borderColor: INK, backgroundColor: INK, yAxisID: 'y2', tension: 0, pointRadius: 4, pointBorderColor: '#FFFFFF', pointBorderWidth: 1.5, borderWidth: 2, spanGaps: false },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: 'index', intersect: false },
      plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, boxHeight: 10, padding: 12 } } },
      scales: {
        x: { stacked: true, grid: { display: false } },
        y: { stacked: true, beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: t('kpi.chartYAxis') } },
        y2: { position: 'right', min: 0, max: 100, grid: { drawOnChartArea: false }, ticks: { callback: (v) => v + '%' } },
      },
    },
  });
}

export function renderAlerts(weeklyRows, cur, prev) {
  const list = $('alertList');
  list.innerHTML = '';
  const alerts = [];
  const active = weeklyRows.filter((w) => weekL3pct(w) != null);

  if (active.length >= 2) {
    const a = weekL3pct(active[active.length - 2]);
    const b = weekL3pct(active[active.length - 1]);
    const d = b - a;
    if (d <= -10) {
      alerts.push({
        sig: 'red',
        t: t('kpi.alerts.l3DownTitle', { n: Math.abs(d).toFixed(0) }),
        d: t('kpi.alerts.l3DownDetail', { a: a.toFixed(0), b: b.toFixed(0) }),
      });
    } else if (d >= 10) {
      alerts.push({
        sig: 'ink',
        t: t('kpi.alerts.l3UpTitle', { n: d.toFixed(0) }),
        d: t('kpi.alerts.l3UpDetail', { a: a.toFixed(0), b: b.toFixed(0) }),
      });
    }
  }
  const cov = cur.total ? (cur.tagged / cur.total) * 100 : null;
  if (cov != null && cov < 80) {
    alerts.push({
      sig: 'amber',
      t: t('kpi.alerts.lowCoverageTitle', { n: cov.toFixed(0) }),
      d: t('kpi.alerts.lowCoverageDetail'),
    });
  }

  const curPct = cur.tagged ? (cur.l3plus / cur.tagged) * 100 : null;
  const prevPct = prev.tagged ? (prev.l3plus / prev.tagged) * 100 : null;
  if (curPct != null && prevPct != null && curPct >= 30 && prevPct < 30) {
    alerts.push({
      sig: 'ink',
      t: t('kpi.alerts.l3MilestoneTitle'),
      d: t('kpi.alerts.l3MilestoneDetail', { cur: curPct.toFixed(1), prev: prevPct.toFixed(1) }),
    });
  }
  const lastTwo = active.slice(-2);
  const hi = (w) => (w.by_level.L4 || 0) + (w.by_level.L5 || 0);
  if (lastTwo.length === 2 && lastTwo.every((w) => hi(w) === 0) && (cur.byLevel.L4 + cur.byLevel.L5) > 0) {
    alerts.push({
      sig: 'amber',
      t: t('kpi.alerts.noHighAutonomyTitle'),
      d: t('kpi.alerts.noHighAutonomyDetail'),
    });
  }
  const vtypes = Object.entries(cur.violationCounts)
    .sort((a, b) => ((VIOLATION_META[b[0]] || {}).red ? 1 : 0) - ((VIOLATION_META[a[0]] || {}).red ? 1 : 0) || b[1] - a[1]);
  for (const [type, n] of vtypes) {
    const vm = VIOLATION_META[type] || { label: type, red: false };
    alerts.push({
      sig: vm.red ? 'red' : 'amber',
      t: t('kpi.alerts.violationTitle', {
        n, label: vm.label, prefix: vm.red ? t('kpi.alerts.redLine') : t('kpi.alerts.warning'),
      }),
      d: vm.red ? t('kpi.alerts.violationRedDetail') : t('kpi.alerts.violationWarnDetail'),
    });
  }
  const cf = cur.total ? (cur.fixTasks / cur.total) * 100 : null;
  const pf = prev.total ? (prev.fixTasks / prev.total) * 100 : null;
  if (cf != null && pf != null && cf - pf >= 15 && cf >= 30) {
    alerts.push({
      sig: 'amber',
      t: t('kpi.alerts.reworkUpTitle', { n: (cf - pf).toFixed(0) }),
      d: t('kpi.alerts.reworkUpDetail', { pf: pf.toFixed(0), cf: cf.toFixed(0) }),
    });
  }
  if (cur.suspects > 0) {
    alerts.push({
      sig: 'amber',
      t: t('kpi.alerts.suspectTitle', { n: cur.suspects }),
      d: t('kpi.alerts.suspectDetail'),
    });
  }
  if (state.data.errors && state.data.errors.length) {
    alerts.push({
      sig: 'amber',
      t: t('kpi.alerts.collectionFailedTitle', { n: state.data.errors.length }),
      // Raw, not esc()'d: the li.innerHTML sink below escapes every alert's
      // text once. Escaping here as well double-encodes a collector error
      // containing & < > or " into visible &amp; on screen.
      d: state.data.errors[0],
    });
  }

  if (!alerts.length) {
    list.innerHTML = `<li><span></span><span class="empty">${t('kpi.alerts.none')}</span></li>`;
    return;
  }
  for (const a of alerts.slice(0, 6)) {
    const li = document.createElement('li');
    // esc() on the composed strings, not just on their interpolated parts:
    // a.d can carry a governance-violation type straight from metrics.json
    // (aggregate.js falls back to the raw type when it is not in
    // VIOLATION_META), and that vocabulary is the collector's to widen.
    li.innerHTML = `<span class="sig ${esc(a.sig)}"></span><span><div class="t">${esc(a.t)}</div><div class="d">${esc(a.d)}</div></span>`;
    list.appendChild(li);
  }
}

export function renderDora(cur, meta) {
  const deployEvents = meta.deployments || meta.tags || meta.releases;
  const src = meta.deployments ? 'deployments' : meta.tags ? 'tags' : 'releases';
  const weeks = state.windowDays / 7;
  if (!deployEvents) {
    $('dDeploy').textContent = '–';
    $('dDeploySub').textContent = t('kpi.dora.noRecords');
  } else if (deployEvents / weeks >= 1) {
    $('dDeploy').innerHTML = (deployEvents / weeks).toFixed(1) + t('kpi.units.perWeek');
    $('dDeploySub').textContent = t('kpi.dora.deploySub', { n: deployEvents, label: EVENT_LABEL[src] });
  } else {
    $('dDeploy').innerHTML = deployEvents + t('kpi.units.times');
    $('dDeploySub').textContent = t('kpi.dora.deploySubLow', {
      days: state.windowDays,
      label: EVENT_LABEL[src],
      weeks: (weeks / deployEvents).toFixed(1),
    });
  }
  $('dLead').innerHTML = fmtHours(median(cur.leads));
  // 回退密度 — 補救 task ÷ 同一個窗口同範圍內嘅全部 task。
  //
  // 舊版係「變更失敗率(proxy)」= revert/hotfix commit ÷ 部署事件,而佢唔係一個
  // 比率:分子數 commit、分母數 git tag,一次失敗嘅 release 出五個 revert commit
  // 就計成五次失敗;而且分母嘅 deployments||tags||releases fallback 係全 repo
  // 加總之後才 short-circuit,所以只有兩個有 tag 嘅 repo 進到分母,分子卻橫跨
  // 十四個。實際資料讀到 72%,而 DORA 連 low performer 都只係 46–60% —
  // 要用 Math.min(…, 100) 夾住先唔會出 >100%,呢個 clamp 本身就係證據。
  //
  // 兩邊都係 task 之後,佢天然 ≤ 100%,亦唔再需要「淨係全員視角先計」:
  // person filter 之下分子分母一齊收窄,比率照樣成立。
  const rd = pct(cur.remedyTasks, cur.total, 0);
  $('dCfr').innerHTML = rd == null ? '–' : `${rd}<span class="unit">%</span>`;
  $('dCfrSub').textContent = cur.total
    // 短過 `revert / hotfix / regression` — 嗰句喺 16px 之下會斷成兩三行,
    // 而且斷喺 slash 中間。訊號集嘅細節喺 README,唔使塞落一格 DORA 卡。
    ? t('kpi.dora.remedySub', { n: cur.remedyTasks, total: cur.total })
    : t('kpi.dora.noWorkInScope');
  $('dMttr').innerHTML = fmtHours(median(cur.fixLeads));
}

/** window 內全 repo 嘅 task 數 — 刻意唔受 person filter 影響。
 *  同 repoRag() 一樣嘅 save/restore:repo 層面嘅分母唔可以變成某個人嘅。 */
function repoWideTaskCount() {
  const saved = state.person;
  state.person = 'all';
  const n = windowTasks().length;
  state.person = saved;
  return n;
}

function repoRag(repo) {
  const saved = state.repo;
  const savedPerson = state.person;
  state.repo = repo;
  state.person = 'all';   // RAG 係 repo 級指標:唔可以變成某個人嘅 CI pass rate
  const cur = statsFromTasks(windowTasks());
  const meta = metaInWindow();
  state.repo = saved;
  state.person = savedPerson;
  const q = meta.quality[repo] || null;
  const ciRate = cur.ciTotal ? (cur.ciPass / cur.ciTotal) * 100 : null;
  const sec = (q && q.security) || {};
  let color = '#9AA5A0', label = t('kpi.rag.insufficient');
  if (ciRate != null || q) {
    if ((sec.critical || 0) > 0 || (ciRate != null && ciRate < 75)) { color = 'var(--alert)'; label = t('kpi.rag.red'); }
    else if ((sec.high || 0) > 0 || (ciRate != null && ciRate < 90)) { color = 'var(--warn)'; label = t('kpi.rag.amber'); }
    else { color = '#2E7D4F'; label = t('kpi.rag.green'); }
  }
  const bits = [];
  if (ciRate != null) bits.push(t('kpi.rag.ciRate', { rate: ciRate.toFixed(0), pass: cur.ciPass, total: cur.ciTotal }));
  if (q && q.coverage != null) bits.push(t('kpi.rag.coverage', { coverage: q.coverage }));
  if (q && q.security) bits.push(t('kpi.rag.security', { critical: sec.critical || 0, high: sec.high || 0, medium: sec.medium || 0 }));
  if (!bits.length) bits.push(t('kpi.rag.noData'));
  return { color, label, tip: bits.join(' · ') };
}

export function renderRag() {
  const row = $('ragRow');
  row.innerHTML = '';
  let grey = 0, shown = 0;
  for (const repo of (state.data.repos || [])) {
    if (!repoInScope(repo)) continue;
    const r = repoRag(repo);
    shown++;
    if (r.label === t('kpi.rag.insufficient')) grey++;
    const el = document.createElement('span');
    el.className = 'chip-rag';
    el.title = r.tip;
    el.innerHTML = `<span class="dotg" style="background:${r.color}"></span>${esc(repo.split('/').pop())} <span style="color:var(--muted)">${r.label}</span>`;
    row.appendChild(el);
  }
  $('ragHint').style.display = grey > 0 && grey >= shown / 2 ? 'block' : 'none';
}

export function renderQuality(cur) {
  const fp = pct(cur.fixTasks, cur.total);
  $('qFix').innerHTML = fp == null ? '–' : `${fp}<span class="unit">%</span>`;
  $('qFixSub').textContent = t('kpi.quality.fixSub', { fix: cur.fixTasks, total: cur.total });
  // 打回率 分母係「有人 review 過」嘅 PR — 冇人 review 過嘅 PR 根本冇得被打回,
  // 擺入分母等同當佢「通過咗 review」。
  const rp = pct(cur.reworkPRs, cur.reviewedPRs);
  $('qRework').innerHTML = rp == null ? '–' : `${rp}<span class="unit">%</span>`;
  if (cur.reviewedPRs) {
    const mr = median(cur.reworkRounds);
    $('qReworkSub').textContent =
      t('kpi.quality.reworkSub', { n: cur.reworkPRs, total: cur.reviewedPRs })
      + (mr == null ? '' : t('kpi.quality.reworkMedianRounds', { n: mr }));
  } else {
    $('qReworkSub').textContent = cur.prTotal
      ? t('kpi.quality.noReviewedPRs')
      : t('kpi.quality.noPRs');
  }

  $('qTurn').innerHTML = fmtHours(median(cur.reworkTurnarounds));
  $('qTurnSub').textContent = cur.reworkTurnarounds.length
    ? t('kpi.quality.turnSubCounted', { n: cur.reworkTurnarounds.length })
    : (cur.reworkPRs
      ? t('kpi.quality.turnSubPostMerge')
      : t('kpi.quality.turnSubNone'));

  const meta = metaInWindow();
  // 一個人嘅 merged PR ÷ 全 repo 嘅 closed PR 唔係一個比率 — closed_unmerged
  // 係 repo 層面 metadata,冇 person 維度(同 變更失敗率 一樣嘅處理)。
  const ap = state.person === 'all'
    ? pct(cur.prTotal, cur.prTotal + meta.closedUnmerged) : null;
  $('qAccept').innerHTML = ap == null ? '–' : `${ap}<span class="unit">%</span>`;
  $('qAcceptSub').textContent = state.person !== 'all'
    ? t('kpi.quality.acceptNeedsAllScope')
    : ((cur.prTotal + meta.closedUnmerged)
      ? t('kpi.quality.acceptSub', { merged: cur.prTotal, closed: meta.closedUnmerged })
      : t('kpi.quality.noPRs'));
  $('qMeaning').textContent = (cur.meaningful / (state.windowDays / 7)).toFixed(1);

  // 缺陷率 — window 內發現嘅缺陷 ÷ 同一個 window 交付嘅 task,加埋未修積壓。
  // 分母用 repoWideTaskCount() 而唔係 cur.total:defect.md 冇 author 維度,
  // 「全 repo 缺陷 ÷ 一個人嘅 task」就係 變更失敗率 舊版嗰個錯。所以揀咗人
  // 之後個數唔會變,改為亮起「全 repo 範圍」。
  const dfx = defectsInScope();
  if (!dfx.hasData) {
    // '–' 係「未設定」。一個實測 0.0% 係一個強好多嘅主張(呢個 window 交付
    // 咗嘢而一個缺陷都冇),兩者一定要分得開。
    $('qDefect').innerHTML = '–';
    $('qDefectSub').textContent = t('kpi.quality.noDefectFile');
  } else {
    const denom = repoWideTaskCount();
    const dr = pct(dfx.found, denom);
    $('qDefect').innerHTML = dr == null ? '–' : `${dr}<span class="unit">%</span>`;
    const bits = [
      t('kpi.quality.defectFoundBit', { found: dfx.found, days: state.windowDays, denom }),
      t('kpi.quality.defectOpenBit', { n: dfx.open }),
    ];
    if (dfx.undated) bits.push(t('kpi.quality.defectUndatedBit', { n: dfx.undated }));
    if (dfx.truncated) bits.push(t('kpi.quality.defectTruncatedBit'));
    $('qDefectSub').textContent = bits.join(' · ');
  }
  const box = $('qLevels');
  box.innerHTML = '';
  for (const l of LEVELS) {
    const n = cur.byLevel[l];
    if (!n) continue;
    const f = cur.fixByLevel[l] || 0;
    const share = (f / n) * 100;
    const row = document.createElement('div');
    row.className = 'qrow';
    row.innerHTML = `<span class="lv"><span class="dot" style="background:${META[l].color}"></span>${l}</span>
      <span class="bar-track"><span class="bar-fill" style="width:${share}%;background:${META[l].color}"></span></span>
      <span class="p">${share.toFixed(0)}% (${f}/${n})</span>`;
    box.appendChild(row);
  }
  if (!box.children.length) box.innerHTML = `<div style="color:var(--muted);font-size:var(--fs-sm)">${t('kpi.quality.noClassifiedWork')}</div>`;
}

/** 標示邊啲區塊喺揀咗人之後,數字仍然係全 repo 範圍。 */
export function setScopeNotes(active) {
  for (const el of document.querySelectorAll('.scope-note')) el.hidden = !active;
}
