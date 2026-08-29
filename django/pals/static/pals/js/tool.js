const apiBase = (window.PALS_API_BASE || '/pals/api').replace(/\/$/, '');
const moduleKey = window.PALS_INITIAL_MODULE || document.querySelector('.pals-tool')?.dataset.module || 'breeding';
const $ = selector => document.querySelector(selector);
const $$ = selector => Array.from(document.querySelectorAll(selector));

let options = {};

function apiUrl(path) {
  return `${apiBase}${path.startsWith('/') ? path : `/${path}`}`;
}

async function api(path, fetchOptions = {}) {
  const response = await fetch(apiUrl(path), fetchOptions);
  const payload = await response.json();
  if (!response.ok || payload.error) throw new Error(payload.error || `${response.status} ${response.statusText}`);
  return payload;
}

function setText(selector, text) {
  const element = $(selector);
  if (element) element.textContent = text || '';
}

function splitList(value) {
  return String(value || '')
    .split(/[\n,]+/)
    .map(item => item.trim())
    .filter(Boolean)
    .slice(0, 4);
}

function formData() {
  return Object.fromEntries(new FormData($('#toolForm')).entries());
}

function setTheme(theme) {
  const next = theme === 'dark' ? 'dark' : 'light';
  document.documentElement.dataset.theme = next;
  localStorage.setItem('pals.theme', next);
  const button = $('#themeToggle');
  if (button) button.textContent = next === 'dark' ? 'Light' : 'Dark';
}

function optionList(values) {
  return (values || []).map(value => `<option value="${escapeHtml(value)}"></option>`).join('');
}

function selectOptions(values, selected = '') {
  return (values || [])
    .map(value => {
      const item = typeof value === 'string' ? {key: value, label: value} : value;
      return `<option value="${escapeHtml(item.key)}" ${item.key === selected ? 'selected' : ''}>${escapeHtml(item.label)}</option>`;
    })
    .join('');
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[char]);
}

function fillOptions() {
  $('#speciesList').innerHTML = optionList(options.species);
  $('#passiveList').innerHTML = optionList(options.passives);
  $$('.js-owner').forEach(select => {
    select.innerHTML = selectOptions(options.owners || ['David'], 'David');
  });
  $$('.js-work-type').forEach(select => {
    select.innerHTML = '<option value="">Choose work skill</option>' + selectOptions(options.workTypes || [], 'mining');
  });
  $$('.js-base').forEach(select => {
    const bases = options.baseSites?.bases || [];
    select.innerHTML = bases.length
      ? bases.map(base => `<option value="${escapeHtml(base.id)}">${escapeHtml(base.label || base.name || base.id)}</option>`).join('')
      : '<option value="">No decoded bases found</option>';
  });
  setText('#palsMeta', `${options.rosterCount || 0} Pals loaded | breeding data ${options.dataVersion || 'unknown'}`);
}

function resultCard(title, body, meta = '') {
  return `<article class="result-card"><h3>${escapeHtml(title)}</h3>${meta ? `<p class="result-meta">${escapeHtml(meta)}</p>` : ''}<div>${body}</div></article>`;
}

function renderJson(data) {
  return `<pre class="json-output">${escapeHtml(JSON.stringify(data, null, 2))}</pre>`;
}

function renderBreeding(data) {
  const groups = data.groups || [];
  if (!groups.length) return renderJson(data);
  return groups.map(group => {
    const routes = group.routes || group.cards || group.results || [];
    const routePreview = routes.slice(0, 3).map(route => {
      const title = route.title || route.name || route.label || `${route.totalEggs || route.eggs || '?'} eggs`;
      const meta = route.quality || route.summary || route.note || '';
      return `<li><strong>${escapeHtml(title)}</strong>${meta ? `<span>${escapeHtml(meta)}</span>` : ''}</li>`;
    }).join('');
    return resultCard(group.title || group.key || 'Route group', `<ul class="compact-list">${routePreview || '<li>No route candidates.</li>'}</ul>`, group.description || '');
  }).join('');
}

function renderIvs(data) {
  if (data.error) return resultCard('No IV plan', escapeHtml(data.error));
  const pairs = data.pairs || data.parentPairs || [];
  if (!pairs.length) return renderJson(data);
  return pairs.slice(0, 8).map(pair => {
    const title = pair.title || pair.label || pair.name || 'Parent pair';
    const meta = pair.scoreText || pair.summary || '';
    return resultCard(title, renderJson(pair), meta);
  }).join('');
}

function renderWork(data) {
  const cards = (data.groups || []).flatMap(group => (group.cards || []).map(card => ({...card, group: group.title})));
  if (!cards.length) return renderJson(data);
  return cards.slice(0, 24).map(card => resultCard(
    card.name,
    `<dl class="stat-grid"><dt>Work</dt><dd>${escapeHtml(card.selectedWorkLabel)} ${escapeHtml(card.selectedLevel)}</dd><dt>Size</dt><dd>${escapeHtml(card.size)}</dd><dt>Owned</dt><dd>${escapeHtml(card.ownedCount || 0)}</dd></dl>`,
    card.group,
  )).join('');
}

function renderRanch(data) {
  const query = String(formData().search || '').toLowerCase();
  const items = (data.items || []).filter(item => !query || item.name.toLowerCase().includes(query));
  if (!items.length) return renderJson(data);
  return items.map(item => {
    const best = item.best ? `${item.best.name} (${item.best.ownedCount || 0} owned)` : 'No candidate';
    return resultCard(item.name, `<p>Best: ${escapeHtml(best)}</p><p>${escapeHtml(item.count)} ranch candidate(s)</p>`);
  }).join('');
}

function renderBases(data) {
  if (data.error) return resultCard('No base plan', escapeHtml(data.error));
  return renderJson(data);
}

function renderResult(data) {
  const renderers = {breeding: renderBreeding, ivs: renderIvs, work: renderWork, ranch: renderRanch, bases: renderBases};
  $('#results').classList.remove('results-empty');
  $('#results').innerHTML = (renderers[moduleKey] || renderJson)(data);
  const count = data.total || data.totalItems || data.rosterCount || (data.groups || []).length || '';
  setText('#resultCount', count ? `${count} result${count === 1 ? '' : 's'}` : '');
}

async function submitTool(event) {
  event.preventDefault();
  setText('#toolStatus', 'Running...');
  $('#results').innerHTML = '';
  const data = formData();
  try {
    let result;
    if (moduleKey === 'breeding') {
      result = await api('/optimize', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          owner: data.owner || 'David',
          target: data.target,
          passives: splitList(data.passives),
          genderPreference: data.genderPreference || 'any',
          breedingProfile: data.breedingProfile || 'manual',
          routePreference: 'best_overall',
        }),
      });
    } else if (moduleKey === 'ivs') {
      result = await api('/improve-ivs', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          owner: data.owner || 'David',
          target: data.target,
          passives: splitList(data.passives),
          implantPassives: splitList(data.implantPassives),
          genderPreference: data.genderPreference || 'any',
          ivGoal: 'perfect',
        }),
      });
    } else if (moduleKey === 'work') {
      result = await api(`/work-suitability?owner=${encodeURIComponent(data.owner || 'David')}&work=${encodeURIComponent(data.work || '')}`);
      if (data.display === 'owned') {
        result.groups = (result.groups || []).map(group => ({...group, cards: (group.cards || []).filter(card => card.ownedCount)}));
      }
    } else if (moduleKey === 'ranch') {
      result = await api(`/ranch-drops?owner=${encodeURIComponent(data.owner || 'David')}`);
    } else if (moduleKey === 'bases') {
      result = await api('/base-planner', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          owner: data.owner || 'David',
          baseId: data.baseId || '',
          plannerMode: data.plannerMode || 'ideal',
          maxWorkers: Number(data.maxWorkers || 15),
          settings: {},
        }),
      });
    }
    renderResult(result);
    setText('#toolStatus', 'Done.');
  } catch (error) {
    $('#results').classList.add('results-empty');
    $('#results').textContent = error.message;
    setText('#toolStatus', 'Failed.');
  }
}

async function reloadOptions() {
  await api('/reload');
  options = await api('/options');
  fillOptions();
}

async function loadLiveStatus() {
  const status = await api('/live-save/status');
  setText('#liveStatus', status.configured ? `Live save ${status.ok ? 'ready' : 'unavailable'}: ${status.path}` : 'PALWORLD_LIVE_SAVE_DIR is not configured.');
}

async function refreshLiveSave() {
  setText('#liveStatus', 'Syncing...');
  const result = await api('/live-save/refresh', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({force: true}),
  });
  setText('#liveStatus', result.ok ? `Synced ${result.rosterCount || 0} rows.` : result.error || 'Sync failed.');
  options = await api('/options');
  fillOptions();
}

async function uploadSave(file) {
  if (!file) return;
  const form = new FormData();
  form.append('files', file, file.webkitRelativePath || file.name);
  setText('#liveStatus', `Uploading ${file.name}...`);
  const response = await fetch(apiUrl('/upload-save'), {method: 'POST', body: form});
  const result = await response.json();
  if (!response.ok || !result.ok) throw new Error(result.error || 'Upload failed.');
  setText('#liveStatus', `Imported ${result.rosterCount || 0} rows.`);
  options = await api('/options');
  fillOptions();
}

async function init() {
  setTheme(localStorage.getItem('pals.theme') || 'light');
  $('#themeToggle')?.addEventListener('click', () => {
    setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
  });
  $('#toolForm')?.addEventListener('submit', submitTool);
  $('#reloadData')?.addEventListener('click', () => reloadOptions().catch(error => setText('#toolStatus', error.message)));
  $('#refreshLiveSave')?.addEventListener('click', () => refreshLiveSave().catch(error => setText('#liveStatus', error.message)));
  $('#saveUpload')?.addEventListener('change', event => uploadSave(event.target.files?.[0]).catch(error => setText('#liveStatus', error.message)));
  options = await api('/options');
  fillOptions();
  loadLiveStatus().catch(() => {});
}

init().catch(error => {
  setText('#palsMeta', error.message);
});
