import { state, $, esc, loadData, windowTasks, precedingTasks } from './data.js';
import { statsFromTasks, buildWeekly, metaInWindow } from './aggregate.js';
import {
  renderKPIs, renderSpectrum, renderChart, renderAlerts, renderDora,
  renderRag, renderQuality,
} from './render-kpi.js';
import { renderProjects } from './render-project.js';
import { renderOverview, renderDefects, renderTable } from './render-table.js';

export function render() {
  const wt = windowTasks();
  const cur = statsFromTasks(wt);
  const prev = statsFromTasks(precedingTasks());
  const weeklyRows = buildWeekly(wt);
  renderKPIs(cur, prev);
  renderSpectrum(cur);
  renderChart(weeklyRows);
  renderAlerts(weeklyRows, cur, prev);
  renderDora(cur, metaInWindow());
  renderRag();
  renderQuality(cur);
  renderProjects();
  renderOverview(cur);
  renderDefects();
  renderTable();
}

(async function init() {
  const { data, demo } = await loadData();
  state.data = data;
  state.demo = demo;
  $('demoBadge').classList.toggle('on', demo);

  const repos = data.repos || [];
  $('eyebrow').textContent = (repos.length === 1 ? repos[0].toUpperCase() : `${repos.length} REPOS`) + ' · GITHUB TELEMETRY';
  $('repoSel').innerHTML = `<option value="all">全部 repos</option>` +
    repos.map((r) => `<option value="${esc(r)}">${esc(r)}</option>`).join('');

  const ts = data.generated_at.replace('T', ' ').slice(0, 16) + ' UTC';
  $('stamp').textContent = ts;
  $('footStamp').textContent = 'generated ' + ts;

  const rebuildBranches = () => {
    const sel = $('branchSel');
    if (state.repo === 'all') {
      // branch 名喺唔同 repo 之間冇比較意義 — 全部 repos 時鎖死
      state.branch = 'all';
      sel.innerHTML = `<option value="all">全部 branches</option>`;
      sel.disabled = true;
      sel.title = '揀咗單一 repo 先可以 filter branch';
      return;
    }
    sel.disabled = false;
    sel.title = '';
    const set = new Set();
    for (const t of state.data.tasks || []) {
      if (t.repo === state.repo && t.branch) set.add(t.branch);
    }
    const branches = [...set].sort();
    if (state.branch !== 'all' && !set.has(state.branch)) state.branch = 'all';
    sel.innerHTML = `<option value="all">全部 branches</option>` +
      branches.map((b) => `<option value="${esc(b)}"${b === state.branch ? ' selected' : ''}>${esc(b)}</option>`).join('');
  };
  rebuildBranches();
  $('repoSel').addEventListener('change', (e) => { state.repo = e.target.value; rebuildBranches(); render(); });
  $('branchSel').addEventListener('change', (e) => { state.branch = e.target.value; render(); });
  $('windowSel').addEventListener('change', (e) => { state.windowDays = +e.target.value; render(); });
  document.querySelectorAll('thead th.sortable').forEach((th) => th.addEventListener('click', () => {
    const k = th.dataset.key;
    state.sort = { key: k, dir: state.sort.key === k ? -state.sort.dir : -1 };
    renderTable();
  }));
  render();
})();
