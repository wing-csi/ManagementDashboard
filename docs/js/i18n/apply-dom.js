/**
 * Applies translations to static markup already in the DOM.
 *
 * `[data-i18n="key"]`                      -> el.textContent = t(key)
 * `[data-i18n-attr="attr:key,attr2:key2"]` -> el.setAttribute(attr, t(key))
 *   for each comma-separated `attr:key` pair — needed for `aria-label`,
 *   `placeholder`, `title`, none of which `textContent` can reach.
 *
 * No markup carries either attribute yet: Phase 1a ships i18n
 * infrastructure only, string extraction is later work by other agents.
 * Calling this today therefore walks zero matching elements and changes
 * nothing — but it is still called unconditionally, in both languages, on
 * every load, so the code path itself is exercised now rather than only
 * once real data-i18n attributes land on real markup.
 */
import { t } from './index.js';

function applyTextNodes(root) {
  for (const el of root.querySelectorAll('[data-i18n]')) {
    el.textContent = t(el.dataset.i18n);
  }
}

function applyAttrNodes(root) {
  for (const el of root.querySelectorAll('[data-i18n-attr]')) {
    const spec = el.dataset.i18nAttr || '';
    for (const pair of spec.split(',')) {
      const [attr, key] = pair.split(':').map((s) => s.trim());
      if (!attr || !key) continue;
      el.setAttribute(attr, t(key));
    }
  }
}

export function applyDom(root = document) {
  applyTextNodes(root);
  applyAttrNodes(root);
}
