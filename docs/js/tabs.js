/** Tab navigation for the dashboard's five panels.
 *
 * Panels are hidden with the `hidden` attribute, never removed: every render
 * module resolves its targets by id and must keep working while its panel is
 * off-screen. innerHTML and textContent writes do not need layout, so a hidden
 * panel renders correctly — with one exception, the Chart.js canvas, which
 * sizes from its client box. That is what `tab:shown` is for.
 */
const TABS = ['overview', 'quality', 'projects', 'product', 'tasks'];
const DEFAULT_TAB = 'overview';

const tabEl = (name) => document.getElementById(`tab-${name}`);
const panelEl = (name) => document.getElementById(`panel-${name}`);

export function activate(name, { focus = false } = {}) {
  const target = TABS.includes(name) ? name : DEFAULT_TAB;
  for (const t of TABS) {
    const on = t === target;
    const el = tabEl(t);
    el.setAttribute('aria-selected', String(on));
    // roving tabindex: the tablist is one tab stop, arrows move within it
    el.tabIndex = on ? 0 : -1;
    panelEl(t).hidden = !on;
  }
  const active = tabEl(target);
  // Five tabs need horizontal scrolling on a phone. A hash deep-link does not
  // focus the tab, so the browser will not reveal it for us; keep the active
  // label inside the tablist without moving the page vertically.
  const list = active.parentElement;
  const tabRect = active.getBoundingClientRect();
  const listRect = list.getBoundingClientRect();
  if (tabRect.left < listRect.left) list.scrollLeft -= listRect.left - tabRect.left;
  else if (tabRect.right > listRect.right) list.scrollLeft += tabRect.right - listRect.right;
  if (focus) active.focus();
  // The hash is view state and ?owner= is data state — rewrite only the hash.
  // replaceState does not fire hashchange, so this cannot loop.
  if (location.hash.slice(1) !== target) {
    history.replaceState(null, '', `${location.pathname}${location.search}#${target}`);
  }
  document.dispatchEvent(new CustomEvent('tab:shown', { detail: { tab: target } }));
}

function onKeydown(e) {
  const i = TABS.indexOf(e.currentTarget.dataset.tab);
  if (i < 0) return;
  const next = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: TABS.length - 1 }[e.key];
  if (next === undefined) return;
  e.preventDefault();
  activate(TABS[(next + TABS.length) % TABS.length], { focus: true });
}

export function initTabs() {
  for (const t of TABS) {
    tabEl(t).addEventListener('click', () => activate(t));
    tabEl(t).addEventListener('keydown', onKeydown);
  }
  activate(location.hash.slice(1));
  window.addEventListener('hashchange', () => activate(location.hash.slice(1)));
}
