/**
 * Language resolution + the `t()` lookup/interpolation/pluralisation core.
 *
 * LANG/LOCALE resolve SYNCHRONOUSLY at module evaluation — straight off
 * `location.search` and `localStorage`, with no DOM query beyond that and
 * no network call. The static `DICT` import below does not break that
 * guarantee: ES module imports are resolved and evaluated before this
 * module's own top-level statements run, so by the time LANG is computed
 * the dictionary data already sits in memory. It exists purely to supply
 * data to `t()`; it plays no part in *how* LANG itself is resolved.
 *
 * Resolution order: `?lang=` query param -> `localStorage.dashboardLang` ->
 * `'zh'`. Only 'zh' and 'en' are accepted at each source — anything else
 * (missing, typo'd, a stale third value) falls through to the next source
 * rather than being treated as a hard error, so a bad querystring can never
 * strand the page in a dead state.
 *
 * With no `lang` param anywhere, this must resolve to 'zh' and the page
 * must render byte-for-byte identical to before i18n existed — that is the
 * override-layer contract the rest of the rollout depends on.
 */
import DICT from './dict/index.js';

export const STORAGE_KEY = 'dashboardLang';

const SUPPORTED = new Set(['zh', 'en']);

function fromQuery() {
  const v = new URLSearchParams(location.search).get('lang');
  return SUPPORTED.has(v) ? v : null;
}

function fromStorage() {
  // localStorage throws in private-browsing / blocked-cookie contexts (and
  // in some locked-down embeds) — a language preference must never be able
  // to take the whole page down.
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    return SUPPORTED.has(v) ? v : null;
  } catch {
    return null;
  }
}

export const LANG = fromQuery() || fromStorage() || 'zh';

// Explicit locale for later toLocaleString()/toLocaleDateString() call sites
// — 'zh-Hant' rather than bare 'zh' because Traditional (Hant) vs Simplified
// (Hans) changes number/date formatting conventions in some locales.
export const LOCALE = LANG === 'en' ? 'en' : 'zh-Hant';

/**
 * Plural convention: a dictionary leaf is either a plain string, or an
 * object `{ one, other }`. For the object form, `t()` selects the branch
 * with `params.n === 1 ? one : other` — the only distinction any dictionary
 * in this project needs. Chinese has no grammatical plural, so a zh leaf's
 * `{ one, other }` pair is free to hold the same string twice; the *shape*
 * stays uniform across both languages so the selection logic never has to
 * know which language it's running under.
 */
function selectPlural(value, params) {
  if (typeof value !== 'object' || value === null) return value;
  const { one, other } = value;
  return params && params.n === 1 ? one : other;
}

function interpolate(str, params) {
  if (!params) return str;
  return str.replace(/\{(\w+)\}/g, (match, name) => (
    Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : match
  ));
}

function lookup(dict, lang, key) {
  const langDict = dict[lang];
  if (langDict == null) return undefined;
  let node = langDict;
  for (const part of key.split('.')) {
    if (node == null || typeof node !== 'object') return undefined;
    node = node[part];
  }
  return node;
}

/**
 * Pure translation core, exported mainly so tests can exercise lookup,
 * interpolation and pluralisation against a synthetic dictionary. Every
 * real namespace ships empty in Phase 1a (string extraction is later
 * work), so testing `t()` end-to-end against production data could only
 * ever exercise the missing-key path — this lets the logic itself be
 * proven correct regardless of when real copy lands.
 */
export function translate(dict, lang, key, params) {
  const raw = lookup(dict, lang, key);
  if (raw === undefined) {
    console.warn(`[i18n] missing key "${key}" for lang "${lang}"`);
    return key;
  }
  const selected = selectPlural(raw, params);
  if (selected === undefined) {
    // e.g. `raw` was an object but not a valid { one, other } plural leaf.
    console.warn(`[i18n] missing key "${key}" for lang "${lang}"`);
    return key;
  }
  return interpolate(String(selected), params);
}

/** `t(key, params)` — looks up `key` in the active-language dictionary. */
export function t(key, params) {
  return translate(DICT, LANG, key, params);
}

/**
 * Builds a URL that mutates ONLY the `lang` param — `?owner=` and the
 * `#hash` must round-trip untouched. Mirrors the param-scoped mutation
 * `syncOwnerParam()` does for `?owner=` in docs/js/main.js.
 */
export function langUrl(lang) {
  const url = new URL(location.href);
  url.searchParams.set('lang', lang);
  return url;
}
