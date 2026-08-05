/* Chart.js 4.4.1 is loaded globally from the CDN <script> in index.html */

import { state, $, pct, esc, windowTasks, repoInScope } from './data.js';
import {
  LEVELS, META, UNTAGGED_COLOR, INK, VIOLATION_META, median, fmtHours,
  statsFromTasks, weekL3pct, fillGaps, metaInWindow, defectsInScope,
} from './aggregate.js?v=zh-20260805-3';

const MODE_LABEL = { auto: '自動', manual: '手動' };
const METHOD_LABEL = { label: '標籤', rule: '規則', trailer: '尾註', inference: '推斷' };
const EVENT_LABEL = { deployments: '部署', tags: '標籤', releases: '發佈' };

function setDelta(el, curr, prev, unit) {
  if (curr == null || prev == null) { el.textContent = ''; return; }
  const d = curr - prev;
  const cls = Math.abs(d) < 0.05 ? 'flat' : d > 0 ? 'up' : 'down';
  el.className = 'delta ' + cls;
  el.textContent = `${d >= 0 ? '▲' : '▼'} ${Math.abs(d).toFixed(1)}${unit}，較上一段`;
}

export function renderKPIs(cur, prev) {
  const l3 = pct(cur.l3plus, cur.tagged);
  $('kpiL3').innerHTML = l3 == null ? '–' : `${l3}<span class="unit">%</span>`;
  setDelta($('kpiL3d'), l3 && +l3, pct(prev.l3plus, prev.tagged) && +pct(prev.l3plus, prev.tagged), ' 個百分點');

  const loc = pct(cur.insAi, cur.insTotal);
  $('kpiLoc').innerHTML = loc == null ? '–' : `${loc}<span class="unit">%</span>`;
  setDelta($('kpiLocd'), loc && +loc, pct(prev.insAi, prev.insTotal) && +pct(prev.insAi, prev.insTotal), ' 個百分點');

  $('kpiTasks').textContent = cur.tagged.toLocaleString();
  $('kpiTasksSub').textContent = `共 ${cur.total.toLocaleString()} 項工作 · 模式：${MODE_LABEL[state.data.mode] || state.data.mode || '–'}`;
  setDelta($('kpiTasksd'), cur.tagged, prev.total ? prev.tagged : null, ' 個');

  const cov = pct(cur.tagged, cur.total);
  const covEl = $('kpiCov');
  covEl.innerHTML = cov == null ? '–' : `${cov}<span class="unit">%</span>`;
  covEl.classList.toggle('warned', cov != null && +cov < 80);
  $('kpiCovSub').textContent = `未分級 ${cur.untagged} 項工作`;
  setDelta($('kpiCovd'), cov && +cov, pct(prev.tagged, prev.total) && +pct(prev.tagged, prev.total), ' 個百分點');
}

export function renderSpectrum(cur) {
  const strip = $('strip');
  const legend = $('legend');
  strip.innerHTML = '';
  legend.innerHTML = '';
  const parts = Object.entries(cur.methods).sort((a, b) => b[1] - a[1])
    .map(([k, v]) => `${METHOD_LABEL[k] || k} ${v}`);
  $('specNote').textContent = `已分級 ${cur.tagged} / ${cur.total}` + (parts.length ? ' · ' + parts.join(' · ') : '');

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
    div.title = `${seg.key === 'untagged' ? '未分級' : seg.key + ' ' + META[seg.key].name}: ${seg.n} (${share.toFixed(1)}%)`;
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
      <span class="lv-name">${isU ? '未分級' : META[r.key].name}</span>
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
        { type: 'bar', label: '未分級', data: filled.map((w) => w.untagged || 0), backgroundColor: UNTAGGED_COLOR, stack: 's', borderRadius: 2 },
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
        y: { stacked: true, beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: '工作數' } },
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
    if (d <= -10) alerts.push({ sig: 'red', t: `L3+ 佔比週環比下跌 ${Math.abs(d).toFixed(0)} 個百分點`, d: `${a.toFixed(0)}% → ${b.toFixed(0)}%。檢查工作類型有無轉變，或者測試框架 / 工具鏈出咗問題。` });
    else if (d >= 10) alerts.push({ sig: 'ink', t: `L3+ 佔比週環比上升 ${d.toFixed(0)} 個百分點`, d: `${a.toFixed(0)}% → ${b.toFixed(0)}%。` });
  }
  const cov = cur.total ? (cur.tagged / cur.total) * 100 : null;
  if (cov != null && cov < 80) alerts.push({ sig: 'amber', t: `分級覆蓋率偏低（${cov.toFixed(0)}%）`, d: '為 PR 加上 ai-level 標籤，或在提交 / PR 內文加上 AI-Level 尾註，否則指標會失真。' });

  const curPct = cur.tagged ? (cur.l3plus / cur.tagged) * 100 : null;
  const prevPct = prev.tagged ? (prev.l3plus / prev.tagged) * 100 : null;
  if (curPct != null && prevPct != null && curPct >= 30 && prevPct < 30) {
    alerts.push({ sig: 'ink', t: 'L3+ 佔比突破 30% 里程碑', d: `本段 ${curPct.toFixed(1)}%，上一段 ${prevPct.toFixed(1)}%。` });
  }
  const lastTwo = active.slice(-2);
  const hi = (w) => (w.by_level.L4 || 0) + (w.by_level.L5 || 0);
  if (lastTwo.length === 2 && lastTwo.every((w) => hi(w) === 0) && (cur.byLevel.L4 + cur.byLevel.L5) > 0) {
    alerts.push({ sig: 'amber', t: '近兩週無 L4+ 工作', d: '高度自動化流程（端對端流程 + 自動驗證）可能已停用。' });
  }
  const vtypes = Object.entries(cur.violationCounts)
    .sort((a, b) => ((VIOLATION_META[b[0]] || {}).red ? 1 : 0) - ((VIOLATION_META[a[0]] || {}).red ? 1 : 0) || b[1] - a[1]);
  for (const [type, n] of vtypes) {
    const vm = VIOLATION_META[type] || { label: type, red: false };
    alerts.push({ sig: vm.red ? 'red' : 'amber',
      t: `${vm.red ? '紅線' : '警告'}：${n} 項工作 ${vm.label}`,
      d: vm.red ? '規範四紅線 — 需要審核並跟進；表格以 ⛔ 標記涉事列。' : '表格以 ⛔ 標記涉事列。' });
  }
  const cf = cur.total ? (cur.fixTasks / cur.total) * 100 : null;
  const pf = prev.total ? (prev.fixTasks / prev.total) * 100 : null;
  if (cf != null && pf != null && cf - pf >= 15 && cf >= 30) {
    alerts.push({ sig: 'amber', t: `修復佔比上升 ${(cf - pf).toFixed(0)} 個百分點`, d: `${pf.toFixed(0)}% → ${cf.toFixed(0)}%，可能係前一段輸出嘅質量問題浮現緊。` });
  }
  if (cur.suspects > 0) {
    alerts.push({ sig: 'amber', t: `${cur.suspects} 項工作的級別聲稱與 PR 行為有矛盾`, d: '表格以 ⚠ 標記相關列：聲稱 L4/L5，但觀察到人工介入（審核 / 混合提交 / 無測試），建議覆核。' });
  }
  if (state.data.errors && state.data.errors.length) {
    alerts.push({ sig: 'amber', t: `${state.data.errors.length} 個程式庫收集失敗`, d: esc(state.data.errors[0]) });
  }

  if (!alerts.length) {
    list.innerHTML = '<li><span></span><span class="empty">暫無異常,指標喺正常範圍。</span></li>';
    return;
  }
  for (const a of alerts.slice(0, 6)) {
    const li = document.createElement('li');
    li.innerHTML = `<span class="sig ${a.sig}"></span><span><div class="t">${a.t}</div><div class="d">${a.d}</div></span>`;
    list.appendChild(li);
  }
}

export function renderDora(cur, meta) {
  const deployEvents = meta.deployments || meta.tags || meta.releases;
  const src = meta.deployments ? 'deployments' : meta.tags ? 'tags' : 'releases';
  const weeks = state.windowDays / 7;
  if (!deployEvents) {
    $('dDeploy').textContent = '–';
    $('dDeploySub').textContent = '無標籤 / 發佈 / 部署記錄';
  } else if (deployEvents / weeks >= 1) {
    $('dDeploy').innerHTML = (deployEvents / weeks).toFixed(1) + '<span class="unit">次/週</span>';
    $('dDeploySub').textContent = `${deployEvents} 次（${EVENT_LABEL[src]}）`;
  } else {
    $('dDeploy').innerHTML = deployEvents + '<span class="unit">次</span>';
    $('dDeploySub').textContent = `${state.windowDays} 日內（${EVENT_LABEL[src]}）· 平均每 ${(weeks / deployEvents).toFixed(1)} 週 1 次`;
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
    ? `${cur.remedyTasks} / ${cur.total} 項工作屬補救`
    : '此範圍內無工作';
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
  let color = '#9AA5A0', label = '資料不足';
  if (ciRate != null || q) {
    if ((sec.critical || 0) > 0 || (ciRate != null && ciRate < 75)) { color = 'var(--alert)'; label = '紅'; }
    else if ((sec.high || 0) > 0 || (ciRate != null && ciRate < 90)) { color = 'var(--warn)'; label = '黃'; }
    else { color = '#2E7D4F'; label = '綠'; }
  }
  const bits = [];
  if (ciRate != null) bits.push(`CI 通過率 ${ciRate.toFixed(0)}%（${cur.ciPass}/${cur.ciTotal}）`);
  if (q && q.coverage != null) bits.push(`測試覆蓋率 ${q.coverage}%`);
  if (q && q.security) bits.push(`安全性：嚴重 ${sec.critical || 0} / 高 ${sec.high || 0} / 中 ${sec.medium || 0}`);
  if (!bits.length) bits.push('無 CI 檢查 / 品質數據檔');
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
    if (r.label === '資料不足') grey++;
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
  $('qFixSub').textContent = `${cur.fixTasks} 項修復 / 回退工作，共 ${cur.total} 項`;
  // 打回率 分母係「有人 review 過」嘅 PR — 冇人 review 過嘅 PR 根本冇得被打回,
  // 擺入分母等同當佢「通過咗 review」。
  const rp = pct(cur.reworkPRs, cur.reviewedPRs);
  $('qRework').innerHTML = rp == null ? '–' : `${rp}<span class="unit">%</span>`;
  if (cur.reviewedPRs) {
    const mr = median(cur.reworkRounds);
    $('qReworkSub').textContent =
      `${cur.reworkPRs} / ${cur.reviewedPRs} 個經審核的 PR 被打回`
      + (mr == null ? '' : ` · 中位 ${mr} 輪`);
  } else {
    $('qReworkSub').textContent = cur.prTotal
      ? '此範圍內無經審核的 PR'
      : '此範圍內無 PR';
  }

  $('qTurn').innerHTML = fmtHours(median(cur.reworkTurnarounds));
  $('qTurnSub').textContent = cur.reworkTurnarounds.length
    ? `由第一次打回到合併 · ${cur.reworkTurnarounds.length} 個 PR`
    : (cur.reworkPRs
      ? '被打回的 PR 都是在合併後才收到打回，無返工時間可計'
      : '此範圍內無被打回嘅 PR');

  const meta = metaInWindow();
  // 一個人嘅 merged PR ÷ 全 repo 嘅 closed PR 唔係一個比率 — closed_unmerged
  // 係 repo 層面 metadata,冇 person 維度(同 變更失敗率 一樣嘅處理)。
  const ap = state.person === 'all'
    ? pct(cur.prTotal, cur.prTotal + meta.closedUnmerged) : null;
  $('qAccept').innerHTML = ap == null ? '–' : `${ap}<span class="unit">%</span>`;
  $('qAcceptSub').textContent = state.person !== 'all'
    ? '需要全員範圍（已關閉 PR 無人員維度）'
    : ((cur.prTotal + meta.closedUnmerged)
      ? `${cur.prTotal} 個已合併 / ${meta.closedUnmerged} 個已關閉但未合併`
      : '此範圍內無 PR');
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
    $('qDefectSub').textContent = '未有程式庫設定缺陷數據檔';
  } else {
    const denom = repoWideTaskCount();
    const dr = pct(dfx.found, denom);
    $('qDefect').innerHTML = dr == null ? '–' : `${dr}<span class="unit">%</span>`;
    const bits = [`${dfx.found} 個在 ${state.windowDays} 日內發現 / ${denom} 項工作`,
                  `${dfx.open} 個未修`];
    if (dfx.undated) bits.push(`${dfx.undated} 個無發現日期`);
    if (dfx.truncated) bits.push('清單已截斷');
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
  if (!box.children.length) box.innerHTML = '<div style="color:var(--muted);font-size:var(--fs-sm)">未有已分級工作</div>';
}

/** 標示邊啲區塊喺揀咗人之後,數字仍然係全 repo 範圍。 */
export function setScopeNotes(active) {
  for (const el of document.querySelectorAll('.scope-note')) el.hidden = !active;
}
