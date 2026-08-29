const apiBase = (window.PALS_API_BASE || '/pals/api').replace(/\/$/, '');
const assetBase = (window.PALS_ASSET_BASE || '/pals/assets/pals').replace(/\/$/, '');
const moduleKey = window.PALS_INITIAL_MODULE || document.querySelector('.pals-tool')?.dataset.module || 'breeding';
const $ = selector => document.querySelector(selector);
const $$ = selector => Array.from(document.querySelectorAll(selector));

let options = {};
const passiveSelections = {passives: [], implantPassives: []};

function apiUrl(path) {
  return `${apiBase}${path.startsWith('/') ? path : `/${path}`}`;
}

function assetUrl(path) {
  if (!path || !path.startsWith('/assets/pals/')) return path;
  return `${assetBase}/${encodeURIComponent(path.split('/').pop())}`;
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

function canonicalMatch(values, value) {
  const query = String(value || '').trim().toLowerCase();
  if (!query) return {value: '', reason: 'empty'};
  const exact = (values || []).find(item => item.toLowerCase() === query);
  if (exact) return {value: exact, reason: 'exact'};
  const starts = (values || []).filter(item => item.toLowerCase().startsWith(query));
  if (starts.length === 1) return {value: starts[0], reason: 'prefix'};
  if (starts.length > 1) return {value: '', reason: 'ambiguous', matches: starts.slice(0, 5)};
  const includes = (values || []).filter(item => item.toLowerCase().includes(query));
  if (includes.length === 1) return {value: includes[0], reason: 'contains'};
  if (includes.length > 1) return {value: '', reason: 'ambiguous', matches: includes.slice(0, 5)};
  return {value: '', reason: 'missing'};
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

function passiveTone(passive) {
  return options.passiveMeta?.[passive]?.tone || 'neutral';
}

function passiveRank(tone) {
  if (tone === 'negative') return 'v';
  if (tone === 'gold') return '^^^';
  if (tone === 'positive') return '^^^+';
  return '^';
}

function speciesInitials(name) {
  return String(name || '?').split(/\s+/).map(part => part[0]).join('').slice(0, 2).toUpperCase();
}

function genderLabel(node) {
  const value = node.displayGender || node.gender || '';
  if (value === 'Male') return {symbol: 'M', text: 'Male', className: 'male'};
  if (value === 'Female') return {symbol: 'F', text: 'Female', className: 'female'};
  if (value === 'Either') return {symbol: '', text: 'Any gender', className: ''};
  return {symbol: '', text: value || '', className: ''};
}

function locationText(node) {
  if (node.box) return `Box ${node.box}, slot ${node.slot}`;
  if (node.location === 'bred intermediate') return 'Bred intermediate';
  if (node.location === 'final parent route') return 'Final breed';
  const location = node.location || '';
  const baseSlot = node.baseSlot ?? node.base_slot;
  if (baseSlot != null && location && !/\bslot\s+\d+\b/i.test(location)) return `${location}, slot ${baseSlot}`;
  return location || 'Unknown location';
}

function displayPassives(node, isRoot = false) {
  return (isRoot || node.parents?.length) ? (node.desired || []) : (node.passives || []);
}

function displayJunk(node, isRoot = false) {
  return (isRoot || node.parents?.length) ? [] : (node.junk || []);
}

function renderPassiveBars(node, isRoot = false) {
  const passives = displayPassives(node, isRoot);
  if (!passives.length) return '<div class="passive-list empty-passives">No passives</div>';
  const junk = new Set(displayJunk(node, isRoot));
  return `<div class="passive-list">${passives.map(passive => {
    const tone = passiveTone(passive);
    return `<span class="passive-bar ${tone}"><span>${escapeHtml(passive)}</span>${junk.has(passive) ? '<em>Junk</em>' : ''}<b>${passiveRank(tone)}</b></span>`;
  }).join('')}</div>`;
}

function renderTypeChips(types = []) {
  return types.length ? `<div class="type-row">${types.map(type => `<span>${escapeHtml(type)}</span>`).join('')}</div>` : '';
}

function renderPalNode(node, isRoot = false) {
  const role = isRoot ? 'FINAL EGG' : node.parents?.length ? 'BREED FIRST' : 'OWNED';
  const roleClass = role === 'OWNED' ? 'owned' : role === 'FINAL EGG' ? 'target' : 'breed';
  const gender = genderLabel(node);
  const junk = displayJunk(node, isRoot);
  return `
    <article class="pal-node ${roleClass}">
      <div class="pal-main">
        <div class="pal-avatar">${node.icon ? `<img src="${escapeHtml(assetUrl(node.icon))}" alt="">` : escapeHtml(speciesInitials(node.species))}</div>
        <div class="pal-copy">
          <h4>${escapeHtml(node.species)} ${gender.symbol ? `<span class="gender ${escapeHtml(gender.className)}">${gender.symbol}</span>` : ''}</h4>
          <p>${escapeHtml(locationText(node))}</p>
          ${renderTypeChips(node.types || [])}
        </div>
      </div>
      ${renderPassiveBars(node, isRoot)}
      <div class="node-foot">
        <span class="role-badge ${roleClass}">${role}</span>
        <span>IV ${escapeHtml(node.hpIv ?? '?')}/${escapeHtml(node.attackIv ?? '?')}/${escapeHtml(node.defenseIv ?? '?')}</span>
        <span>${(node.desired || []).length}/${(node.desired || []).length + (node.missing || []).length} desired</span>
        <span>${junk.length} junk</span>
      </div>
      ${junk.length ? `<p class="junk-text">Junk: ${escapeHtml(junk.join(', '))}</p>` : ''}
    </article>`;
}

function renderBreedTree(node, isRoot = false) {
  const parents = node.parents?.length
    ? `<div class="branch"><div class="children">${node.parents.map(parent => renderBreedTree(parent)).join('')}</div></div>`
    : '';
  return `<div class="tree-node">${renderPalNode(node, isRoot)}${parents}</div>`;
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

function renderPassivePicker(picker) {
  const key = picker.dataset.picker;
  const chips = picker.querySelector('[data-passive-chips]');
  const hidden = picker.querySelector(`input[name="${key}"]`);
  const selected = passiveSelections[key] || [];
  hidden.value = selected.join(',');
  chips.innerHTML = selected.map(passive => {
    const tone = passiveTone(passive);
    return `<button type="button" class="passive-chip ${tone}" data-remove-passive="${escapeHtml(passive)}">${escapeHtml(passive)} <span>${passiveRank(tone)}</span></button>`;
  }).join('');
}

function renderPassiveSuggestions(picker) {
  let list = picker.querySelector('[data-passive-suggestions]');
  if (!list) {
    list = document.createElement('span');
    list.className = 'passive-suggestions';
    list.dataset.passiveSuggestions = '';
    picker.querySelector('.passive-input-row')?.after(list);
  }
  const input = picker.querySelector('[data-passive-input]');
  const query = String(input.value || '').trim().toLowerCase();
  if (!query) {
    list.innerHTML = '';
    list.classList.remove('open');
    return;
  }
  const selected = new Set(passiveSelections[picker.dataset.picker] || []);
  const matches = (options.passives || [])
    .filter(passive => !selected.has(passive))
    .filter(passive => passive.toLowerCase().includes(query))
    .slice(0, 8);
  list.innerHTML = matches.map(passive => {
    const tone = passiveTone(passive);
    return `<button type="button" data-suggest-passive="${escapeHtml(passive)}"><span class="passive-dot ${tone}"></span>${escapeHtml(passive)}<em>${escapeHtml(tone)}</em></button>`;
  }).join('');
  list.classList.toggle('open', matches.length > 0);
}

function addPassive(picker) {
  const key = picker.dataset.picker;
  const input = picker.querySelector('[data-passive-input]');
  const hint = picker.querySelector('[data-passive-hint]');
  const match = canonicalMatch(options.passives || [], input.value);
  if (!match.value) {
    hint.textContent = match.reason === 'ambiguous' ? `Matches: ${match.matches.join(', ')}. Keep typing.` : 'No known passive matches that text.';
    hint.className = 'field-hint invalid';
    return;
  }
  const selected = passiveSelections[key] || [];
  if (selected.includes(match.value)) {
    hint.textContent = `${match.value} is already selected.`;
    hint.className = 'field-hint';
    input.value = '';
    return;
  }
  if (selected.length >= 4) {
    hint.textContent = 'A Pal can only have 4 final passives.';
    hint.className = 'field-hint invalid';
    return;
  }
  passiveSelections[key] = [...selected, match.value];
  input.value = '';
  hint.textContent = `${match.value} added.`;
  hint.className = 'field-hint valid';
  renderPassivePicker(picker);
}

function initPassivePickers() {
  $$('[data-picker]').forEach(picker => {
    picker.querySelector('[data-passive-add]')?.addEventListener('click', () => addPassive(picker));
    picker.querySelector('[data-passive-input]')?.addEventListener('keydown', event => {
      if (event.key === 'Enter') {
        event.preventDefault();
        addPassive(picker);
      }
    });
    picker.querySelector('[data-passive-input]')?.addEventListener('input', () => renderPassiveSuggestions(picker));
    picker.addEventListener('click', event => {
      const suggested = event.target.closest('[data-suggest-passive]')?.dataset.suggestPassive;
      if (suggested) {
        picker.querySelector('[data-passive-input]').value = suggested;
        addPassive(picker);
        renderPassiveSuggestions(picker);
        return;
      }
      const passive = event.target.closest('[data-remove-passive]')?.dataset.removePassive;
      if (!passive) return;
      const key = picker.dataset.picker;
      passiveSelections[key] = (passiveSelections[key] || []).filter(item => item !== passive);
      renderPassivePicker(picker);
    });
    renderPassivePicker(picker);
  });
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
    const routes = group.results || [];
    const body = routes.length
      ? routes.slice(0, 3).map((route, index) => `
        <article class="route-card">
          <div class="route-header">
            <div>
              <h3>Option ${index + 1}: ${escapeHtml(route.species)}</h3>
              <p>${escapeHtml(route.label || '')}</p>
            </div>
            <div class="badges">
              <span>${escapeHtml(route.breedCount || route.steps || 0)} eggs</span>
              <span>${escapeHtml(route.suggestedCakeType || 'Cake')} x${escapeHtml(route.suggestedCakes || 0)}</span>
              <span class="${(route.junk || []).length ? 'bad' : 'good'}">${(route.junk || []).length} junk</span>
            </div>
          </div>
          <div class="breed-tree">${renderBreedTree(route, true)}</div>
        </article>`).join('')
      : '<div class="results-empty">No option found for this category.</div>';
    return `<section class="result-group"><div class="group-heading"><h3>${escapeHtml(group.title)}</h3><p>${escapeHtml(group.description || '')}</p></div>${body}</section>`;
  }).join('');
}

function renderIvs(data) {
  if (data.error) return resultCard('No IV plan', escapeHtml(data.error));
  const pairs = data.pairs || data.parentPairs || [];
  if (!pairs.length) return renderJson(data);
  return pairs.slice(0, 8).map((pair, index) => `
    <article class="route-card iv-card">
      <div class="route-header">
        <div>
          <h3>Option ${index + 1}</h3>
          <p>100 support: HP ${escapeHtml(pair.hp100Support || 0)}x / ATK ${escapeHtml(pair.attack100Support || 0)}x / DEF ${escapeHtml(pair.defense100Support || 0)}x</p>
        </div>
        <div class="badges">
          <span>${escapeHtml(pair.doublePerfectCoverage || 0)} doubled</span>
          <span class="${(pair.junk || []).length ? 'bad' : 'good'}">${(pair.junk || []).length} junk</span>
        </div>
      </div>
      <div class="iv-pair-grid">${(pair.parents || []).map(parent => renderPalNode(parent)).join('')}</div>
      ${(pair.junk || []).length ? `<p class="junk-text">Junk in parent pool: ${escapeHtml(pair.junk.join(', '))}</p>` : ''}
    </article>`).join('');
}

function renderWork(data) {
  const cards = (data.groups || []).flatMap(group => (group.cards || []).map(card => ({...card, group: group.title})));
  if (!cards.length) return renderJson(data);
  return cards.slice(0, 24).map(card => resultCard(
    card.name,
    `<div class="pal-main">
      <div class="pal-avatar">${card.icon ? `<img src="${escapeHtml(assetUrl(card.icon))}" alt="">` : escapeHtml(speciesInitials(card.name))}</div>
      <div class="pal-copy">
        ${renderTypeChips(card.types || [])}
        <dl class="stat-grid"><dt>Work</dt><dd>${escapeHtml(card.selectedWorkLabel)} ${escapeHtml(card.selectedLevel)}</dd><dt>Size</dt><dd>${escapeHtml(card.sizeGroup || card.size)}</dd><dt>Owned</dt><dd>${escapeHtml(card.ownedCount || 0)}</dd></dl>
      </div>
    </div>`,
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
  initPassivePickers();
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
