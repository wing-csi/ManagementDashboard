/**
 * Assembles every namespace file into the two language dictionaries.
 *
 * One file per namespace per language (see docs/js/i18n/dict/{zh,en}/*.js)
 * so parallel agents extracting strings later do not collide on a shared
 * file. This module is the only place that composes them.
 */
import chromeZh from './zh/chrome.js';
import kpiZh from './zh/kpi.js';
import burndownZh from './zh/burndown.js';
import managementZh from './zh/management.js';
import tableZh from './zh/table.js';
import projectZh from './zh/project.js';
import productZh from './zh/product.js';
import timelineZh from './zh/timeline.js';
import levelsZh from './zh/levels.js';
import miscZh from './zh/misc.js';

import chromeEn from './en/chrome.js';
import kpiEn from './en/kpi.js';
import burndownEn from './en/burndown.js';
import managementEn from './en/management.js';
import tableEn from './en/table.js';
import projectEn from './en/project.js';
import productEn from './en/product.js';
import timelineEn from './en/timeline.js';
import levelsEn from './en/levels.js';
import miscEn from './en/misc.js';

const zh = Object.freeze({
  chrome: chromeZh,
  kpi: kpiZh,
  burndown: burndownZh,
  management: managementZh,
  table: tableZh,
  project: projectZh,
  product: productZh,
  timeline: timelineZh,
  levels: levelsZh,
  misc: miscZh,
});

const en = Object.freeze({
  chrome: chromeEn,
  kpi: kpiEn,
  burndown: burndownEn,
  management: managementEn,
  table: tableEn,
  project: projectEn,
  product: productEn,
  timeline: timelineEn,
  levels: levelsEn,
  misc: miscEn,
});

export default Object.freeze({ zh, en });
