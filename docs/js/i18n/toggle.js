/**
 * Renders a two-item segmented text control (`EN | 繁`) and mounts it as the
 * LAST child of `.controls` in the masthead, after `#stamp`.
 *
 * Deliberately not a fifth `<select>`: the masthead already has four filter
 * selects, and a fifth would read as another data filter rather than a
 * language switch. Styled like `.stamp` — mono, --fs-xs, muted — so it
 * reads as chrome rather than competing with the filters.
 *
 * The `EN` / `繁` labels are language autonyms, not translated copy — each
 * name is always shown in its own language regardless of which one is
 * active, the same convention every language switcher uses. They are not
 * routed through t().
 *
 * Clicking reloads the page rather than swapping text live. Roughly ten
 * module-level `const` maps across the render-*.js modules are built once,
 * at import time, from the active dictionary; keeping the language live
 * would mean converting every one of them to a lazy getter. A full reload
 * keeps them `const` and keeps this change small — do not "optimise" this
 * into a live swap without doing that conversion first.
 */
import { LANG, STORAGE_KEY, langUrl } from './index.js';

const LANGS = [
  { code: 'en', label: 'EN' },
  { code: 'zh', label: '繁' },
];

function selectLanguage(lang) {
  try {
    localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    // Private-browsing / blocked-cookie contexts — the ?lang= param still
    // works for this load, it just won't persist to the next one.
  }
  history.replaceState(null, '', langUrl(lang));
  location.reload();
}

export function mountLanguageToggle(root = document) {
  const controls = root.querySelector('.controls');
  if (!controls) return null;

  const wrap = document.createElement('div');
  wrap.className = 'lang-toggle';
  wrap.id = 'langToggle';
  wrap.setAttribute('role', 'group');
  wrap.setAttribute('aria-label', 'Language / 語言');

  LANGS.forEach(({ code, label }, i) => {
    if (i > 0) {
      const sep = document.createElement('span');
      sep.className = 'lang-sep';
      sep.textContent = '|';
      sep.setAttribute('aria-hidden', 'true');
      wrap.appendChild(sep);
    }
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'lang-btn';
    btn.dataset.lang = code;
    btn.textContent = label;
    const active = code === LANG;
    btn.setAttribute('aria-pressed', String(active));
    btn.classList.toggle('is-active', active);
    btn.addEventListener('click', () => selectLanguage(code));
    wrap.appendChild(btn);
  });

  controls.appendChild(wrap);
  return wrap;
}
