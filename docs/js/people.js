/* Identity resolution for the contributor filter.
 *
 * One human can appear under several identities: PR authors are GitHub logins,
 * but commit authors fall back to the raw git display name when no GitHub
 * account resolves. Aliases are declared in config.toml [people] and arrive
 * here via metrics.json, rather than being guessed — metrics.json carries no
 * author email to key on.
 */

/** {"Wing": ["wing-csi", "wing2036"]} -> Map{"wing-csi" => "Wing", ...} */
export function buildPersonIndex(peopleMap) {
  const index = new Map();
  for (const [person, identities] of Object.entries(peopleMap || {})) {
    for (const identity of identities || []) index.set(identity, person);
  }
  return index;
}

/** Canonical person for an author, falling back to the author itself. */
export function personOf(author, index) {
  if (!author) return '';
  return index.get(author) || author;
}

/** [{person, count}] for tasks passing `inScope`, busiest first. */
export function personOptions(tasks, index, inScope) {
  const counts = new Map();
  for (const t of tasks || []) {
    if (!t.author || !inScope(t)) continue;
    const person = personOf(t.author, index);
    counts.set(person, (counts.get(person) || 0) + 1);
  }
  return [...counts.entries()]
    .map(([person, count]) => ({ person, count }))
    .sort((a, b) => b.count - a.count || (a.person < b.person ? -1 : 1));
}
