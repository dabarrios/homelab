const apiBase = (window.PALS_API_BASE || '/pals/api').replace(/\/$/, '');
const assetBase = (window.PALS_ASSET_BASE || '/pals/assets/pals').replace(/\/$/, '');
const moduleKey = window.PALS_INITIAL_MODULE || document.querySelector('.pals-tool')?.dataset.module || 'breeding';
const $ = selector => document.querySelector(selector);
const $$ = selector => Array.from(document.querySelectorAll(selector));

let options = {};
const passiveSelections = {passives: [], implantPassives: [], profilePassives: []};
let customProfiles = [];
let builtInProfileNames = {};
let editingProfileId = '';
let editingBuiltInProfile = '';

const CUSTOM_PROFILES_KEY = 'pals.customProfiles.v1';
const BUILT_IN_PROFILE_NAMES_KEY = 'pals.builtInProfileNames.v1';
const BUILT_IN_PROFILES = [
  {value: 'manual', label: 'Manual passives', locked: false},
  {value: 'work_speed', label: 'Best work speed', locked: true},
  {value: 'ranch_drops_focus', label: 'Ranch drops focus', locked: true},
];

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

function slugify(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
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

function passiveDescription(passive) {
  return options.passiveMeta?.[passive]?.desc || 'No description available.';
}

function passiveId(passive) {
  return options.passiveMeta?.[passive]?.id || '';
}

function formatPassiveDescription(passive) {
  const desc = passiveDescription(passive).replace(/\s*\((?:ToSelf|None)\)/g, '');
  if (/[.!?]$/.test(desc) || desc.length > 90) return [desc];
  return desc
    .replace(/\s*\((?:ToSelf|None)\)/g, '')
    .split(/\s*,\s*/)
    .map(line => line.replace(/([+-]\d+(?:\.\d+)?)%/g, (_, value) => `${Number(value).toFixed(1)}%`))
    .filter(Boolean);
}

function passiveTooltipHtml(passive) {
  const tone = passiveTone(passive);
  return `
    <div class="passive-tooltip-card ${tone}" role="tooltip">
      <strong>${escapeHtml(passive)}</strong>
      ${formatPassiveDescription(passive).map(line => `<span>${escapeHtml(line)}</span>`).join('')}
    </div>`;
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
    return `<span class="passive-bar ${tone}" tabindex="0" data-passive-tooltip="${escapeHtml(passive)}"><span>${escapeHtml(passive)}</span>${junk.has(passive) ? '<em>Junk</em>' : ''}</span>`;
  }).join('')}</div>`;
}

function renderTypeChips(types = []) {
  return types.length ? `<div class="type-row">${types.map(type => `<span>${escapeHtml(type)}</span>`).join('')}</div>` : '';
}

function breedUrl(card, profile = 'manual') {
  const params = new URLSearchParams({target: card.name || ''});
  if (profile) params.set('profile', profile);
  return `/pals/breeding/?${params.toString()}`;
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
        <span>IV ${formatIv(node.hpIv)}/${formatIv(node.attackIv)}/${formatIv(node.defenseIv)}</span>
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
    select.innerHTML = '<option value="">Choose work skill</option>' + selectOptions(options.workTypes || [], '');
  });
  $$('.js-base').forEach(select => {
    const bases = options.baseSites?.bases || [];
    select.innerHTML = bases.length
      ? bases.map(base => `<option value="${escapeHtml(base.id)}">${escapeHtml(base.label || base.name || base.id)}</option>`).join('')
      : '<option value="">No decoded bases found</option>';
  });
  setText('#palsMeta', `${options.rosterCount || 0} Pals loaded | breeding data ${options.dataVersion || 'unknown'}`);
  renderProfileOptions();
  renderImplantInventories();
  syncCustomSelects();
  applyUrlPrefill();
}

function loadProfiles() {
  try {
    customProfiles = JSON.parse(localStorage.getItem(CUSTOM_PROFILES_KEY) || '[]');
    if (!Array.isArray(customProfiles)) customProfiles = [];
  } catch {
    customProfiles = [];
  }
  try {
    builtInProfileNames = JSON.parse(localStorage.getItem(BUILT_IN_PROFILE_NAMES_KEY) || '{}');
    if (!builtInProfileNames || typeof builtInProfileNames !== 'object') builtInProfileNames = {};
  } catch {
    builtInProfileNames = {};
  }
}

function saveProfiles() {
  localStorage.setItem(CUSTOM_PROFILES_KEY, JSON.stringify(customProfiles));
  localStorage.setItem(BUILT_IN_PROFILE_NAMES_KEY, JSON.stringify(builtInProfileNames));
}

function profileLabel(profile) {
  return builtInProfileNames[profile.value] || profile.label;
}

function selectedProfileValue() {
  return $('#breedingProfile')?.value || 'manual';
}

function customProfileByValue(value) {
  const id = String(value || '').replace(/^custom:/, '');
  return customProfiles.find(profile => profile.id === id) || null;
}

function builtInProfileByValue(value) {
  return BUILT_IN_PROFILES.find(profile => profile.value === value) || null;
}

function renderProfileOptions(selected = selectedProfileValue()) {
  const select = $('#breedingProfile');
  if (!select) return;
  const optionsHtml = [
    ...BUILT_IN_PROFILES.map(profile => `<option value="${escapeHtml(profile.value)}">${escapeHtml(profileLabel(profile))}</option>`),
    ...customProfiles.map(profile => `<option value="custom:${escapeHtml(profile.id)}">${escapeHtml(profile.name)}</option>`),
  ].join('');
  select.innerHTML = optionsHtml;
  select.value = [...select.options].some(option => option.value === selected) ? selected : 'manual';
  updateProfileHint();
  syncCustomSelects();
}

function updateProfileHint() {
  const value = selectedProfileValue();
  const hint = $('#profileHint');
  if (!hint) return;
  const custom = customProfileByValue(value);
  const builtIn = builtInProfileByValue(value);
  if (custom) {
    hint.textContent = `Uses saved passives: ${custom.passives.join(', ') || 'none selected yet'}.`;
  } else if (builtIn?.locked) {
    hint.textContent = 'Built-in profile: the app chooses passives with built-in logic. You can rename this profile, but the selection rules stay managed by the app.';
  } else {
    hint.textContent = 'Manual passives lets you choose each passive yourself.';
  }
}

function applySelectedProfile() {
  const custom = customProfileByValue(selectedProfileValue());
  if (!custom) {
    updateProfileHint();
    return;
  }
  passiveSelections.passives = [...custom.passives].slice(0, 4);
  document.querySelectorAll('[data-picker="passives"]').forEach(renderPassivePicker);
  updateProfileHint();
}

function openProfileEditor(profileValue = selectedProfileValue()) {
  const modal = $('#profileModal');
  if (!modal) return;
  const custom = customProfileByValue(profileValue);
  const builtIn = builtInProfileByValue(profileValue);
  editingProfileId = custom?.id || '';
  editingBuiltInProfile = builtIn?.locked ? builtIn.value : '';
  $('#profileEditorTitle').textContent = custom || editingBuiltInProfile ? 'Edit Passive Profile' : 'Add Passive Profile';
  $('#profileName').value = custom?.name || (builtIn ? profileLabel(builtIn) : '');
  passiveSelections.profilePassives = custom ? [...custom.passives] : [...passiveSelections.passives];
  const locked = Boolean(editingBuiltInProfile);
  $('#profileLockedNotice')?.classList.toggle('hidden', !locked);
  $('#profilePassiveFields')?.classList.toggle('hidden', locked);
  $('#deleteProfile').hidden = !custom;
  setText('#profileStatus', locked ? 'This is a built-in profile. Rename it if you want a friendlier label; the app-managed rules stay unchanged.' : 'Choose up to 4 passives for this profile.');
  document.querySelectorAll('[data-picker="profilePassives"]').forEach(renderPassivePicker);
  modal.classList.remove('hidden');
  $('#profileName')?.focus();
}

function closeProfileEditor() {
  $('#profileModal')?.classList.add('hidden');
  editingProfileId = '';
  editingBuiltInProfile = '';
}

function saveProfile() {
  const name = ($('#profileName')?.value || '').trim();
  if (!name) {
    setText('#profileStatus', 'Name this passive profile before saving.');
    return;
  }
  if (editingBuiltInProfile) {
    builtInProfileNames[editingBuiltInProfile] = name.slice(0, 60);
    saveProfiles();
    renderProfileOptions(editingBuiltInProfile);
    closeProfileEditor();
    return;
  }
  const passives = [...new Set(passiveSelections.profilePassives)].slice(0, 4);
  if (!passives.length) {
    setText('#profileStatus', 'Add at least one passive before saving.');
    return;
  }
  let profile = customProfiles.find(item => item.id === editingProfileId);
  if (profile) {
    profile.name = name.slice(0, 60);
    profile.passives = passives;
  } else {
    profile = {id: `${Date.now()}-${Math.random().toString(16).slice(2)}`, name: name.slice(0, 60), passives};
    customProfiles.push(profile);
  }
  passiveSelections.passives = [...passives];
  saveProfiles();
  renderProfileOptions(`custom:${profile.id}`);
  document.querySelectorAll('[data-picker="passives"]').forEach(renderPassivePicker);
  closeProfileEditor();
}

function deleteProfile() {
  const profile = customProfiles.find(item => item.id === editingProfileId);
  if (!profile) return;
  customProfiles = customProfiles.filter(item => item.id !== profile.id);
  saveProfiles();
  renderProfileOptions('manual');
  closeProfileEditor();
}

function initProfiles() {
  loadProfiles();
  renderProfileOptions();
  $('#breedingProfile')?.addEventListener('change', applySelectedProfile);
  $('#addProfile')?.addEventListener('click', () => openProfileEditor('manual'));
  $('#editProfile')?.addEventListener('click', () => openProfileEditor(selectedProfileValue()));
  $('#saveProfile')?.addEventListener('click', saveProfile);
  $('#deleteProfile')?.addEventListener('click', deleteProfile);
  $('#closeProfileEditor')?.addEventListener('click', closeProfileEditor);
  $('#profileModal')?.addEventListener('click', event => {
    if (event.target === $('#profileModal')) closeProfileEditor();
  });
}

function formatIv(value) {
  if (value === null || value === undefined || value === '') return '?';
  return String(Math.round(Number(value)));
}

function renderSuggestions(field) {
  const type = field.dataset.suggest;
  const input = field.querySelector('[data-suggest-input]');
  const menu = field.querySelector('[data-suggest-menu]');
  const query = String(input.value || '').trim().toLowerCase();
  if (!query) {
    menu.innerHTML = '';
    menu.classList.remove('open');
    return;
  }
  const values = type === 'species' ? options.species || [] : options.passives || [];
  const matches = values
    .filter(value => value.toLowerCase().includes(query))
    .slice(0, 8);
  menu.innerHTML = matches.map(value => `<button type="button" data-suggest-value="${escapeHtml(value)}">${escapeHtml(value)}</button>`).join('');
  menu.classList.toggle('open', matches.length > 0);
}

function initSuggestFields() {
  $$('[data-suggest]').forEach(field => {
    const input = field.querySelector('[data-suggest-input]');
    input?.addEventListener('input', () => renderSuggestions(field));
    input?.addEventListener('blur', () => {
      window.setTimeout(() => field.querySelector('[data-suggest-menu]')?.classList.remove('open'), 120);
    });
    field.addEventListener('click', event => {
      const value = event.target.closest('[data-suggest-value]')?.dataset.suggestValue;
      if (!value) return;
      input.value = value;
      field.querySelector('[data-suggest-menu]').classList.remove('open');
    });
  });
}

function renderPassivePicker(picker) {
  const key = picker.dataset.picker;
  const chips = picker.querySelector('[data-passive-chips]');
  const hidden = picker.querySelector(`input[name="${key}"]`);
  const selected = passiveSelections[key] || [];
  hidden.value = selected.join(',');
  chips.innerHTML = selected.map(passive => {
    const tone = passiveTone(passive);
    return `
      <span class="passive-chip ${tone}" tabindex="0" data-passive-tooltip="${escapeHtml(passive)}">
        <span>${escapeHtml(passive)}</span>
        <button type="button" class="chip-remove" data-remove-passive="${escapeHtml(passive)}" aria-label="Remove ${escapeHtml(passive)}">x</button>
      </span>`;
  }).join('');
  const clear = picker.querySelector('[data-passive-clear]');
  if (clear) clear.hidden = selected.length === 0;
}

function positionPassiveTooltip(anchor) {
  const tooltip = $('#passiveTooltip');
  if (!tooltip || tooltip.classList.contains('hidden')) return;
  const rect = anchor.getBoundingClientRect();
  const tip = tooltip.getBoundingClientRect();
  const gap = 10;
  let left = rect.left;
  let top = rect.top - tip.height - gap;
  if (top < 8) top = rect.bottom + gap;
  if (left + tip.width > window.innerWidth - 8) left = window.innerWidth - tip.width - 8;
  if (left < 8) left = 8;
  tooltip.style.left = `${left}px`;
  tooltip.style.top = `${top}px`;
}

function showPassiveTooltip(anchor) {
  const passive = anchor.dataset.passiveTooltip;
  const tooltip = $('#passiveTooltip');
  if (!passive || !tooltip) return;
  tooltip.innerHTML = passiveTooltipHtml(passive);
  tooltip.className = `floating-passive-tooltip ${passiveTone(passive)}`;
  positionPassiveTooltip(anchor);
}

function hidePassiveTooltip() {
  const tooltip = $('#passiveTooltip');
  if (tooltip) tooltip.className = 'floating-passive-tooltip hidden';
}

function initPassiveTooltips() {
  document.addEventListener('pointerover', event => {
    const anchor = event.target.closest('[data-passive-tooltip]');
    if (anchor) showPassiveTooltip(anchor);
  });
  document.addEventListener('pointerout', event => {
    const anchor = event.target.closest('[data-passive-tooltip]');
    if (anchor && !anchor.contains(event.relatedTarget)) hidePassiveTooltip();
  });
  document.addEventListener('focusin', event => {
    const anchor = event.target.closest('[data-passive-tooltip]');
    if (anchor) showPassiveTooltip(anchor);
  });
  document.addEventListener('focusout', event => {
    if (event.target.closest('[data-passive-tooltip]')) hidePassiveTooltip();
  });
  window.addEventListener('scroll', hidePassiveTooltip, true);
  window.addEventListener('resize', hidePassiveTooltip);
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
    picker.querySelector('[data-passive-clear]')?.addEventListener('click', () => {
      passiveSelections[picker.dataset.picker] = [];
      picker.querySelector('[data-passive-hint]').textContent = 'Selected passives cleared.';
      picker.querySelector('[data-passive-hint]').className = 'field-hint';
      renderPassivePicker(picker);
    });
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
      event.stopPropagation();
      const key = picker.dataset.picker;
      passiveSelections[key] = (passiveSelections[key] || []).filter(item => item !== passive);
      renderPassivePicker(picker);
    });
    renderPassivePicker(picker);
  });
}

function availableInventoryPassives() {
  const inventory = options.implantInventory || {};
  return Object.entries(inventory)
    .filter(([, item]) => item?.infinite || Number(item?.count || 0) > 0)
    .map(([passive]) => passive);
}

function selectedImplantPassives(finalPassives, includeImplants) {
  if (!includeImplants) return [];
  const available = new Set(availableInventoryPassives());
  return finalPassives.filter(passive => available.has(passive));
}

function renderInventorySuggestions(panel) {
  const input = panel.querySelector('[data-inventory-input]');
  const menu = panel.querySelector('[data-inventory-menu]');
  const query = String(input?.value || '').trim().toLowerCase();
  if (!query) {
    menu.innerHTML = '';
    menu.classList.remove('open');
    return;
  }
  const current = new Set(Object.keys(options.implantInventory || {}));
  const matches = (options.passives || [])
    .filter(passive => !current.has(passive))
    .filter(passive => passive.toLowerCase().includes(query))
    .slice(0, 8);
  menu.innerHTML = matches.map(passive => `<button type="button" data-inventory-choice="${escapeHtml(passive)}">${escapeHtml(passive)}</button>`).join('');
  menu.classList.toggle('open', matches.length > 0);
}

async function saveInventoryPassive(passive, patch) {
  const response = await api('/implant-inventory', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({passive, ...patch}),
  });
  options.implantInventory = response.inventory || {};
  renderImplantInventories();
}

function renderImplantInventories() {
  $$('[data-implant-inventory]').forEach(panel => {
    const list = panel.querySelector('[data-inventory-list]');
    if (!list) return;
    const entries = Object.entries(options.implantInventory || {}).sort(([a], [b]) => a.localeCompare(b));
    list.innerHTML = entries.length ? entries.map(([passive, item]) => `
      <div class="implant-row">
        <span class="passive-chip ${passiveTone(passive)}" tabindex="0" data-passive-tooltip="${escapeHtml(passive)}">${escapeHtml(passive)}</span>
        <label class="inventory-toggle"><input type="checkbox" data-inventory-infinite="${escapeHtml(passive)}" ${item.infinite ? 'checked' : ''}> Infinite</label>
        <input type="number" min="0" value="${escapeHtml(item.infinite ? 0 : item.count || 0)}" data-inventory-count="${escapeHtml(passive)}" ${item.infinite ? 'disabled' : ''}>
        <button type="button" class="chip-remove" data-inventory-delete="${escapeHtml(passive)}" aria-label="Remove ${escapeHtml(passive)}">x</button>
      </div>`).join('') : '<p class="field-hint">No implant passives inventoried yet.</p>';
    const status = panel.querySelector('[data-inventory-status]');
    if (status) status.textContent = entries.length ? `${entries.length} implant passive${entries.length === 1 ? '' : 's'} inventoried.` : '';
  });
}

function initImplantInventories() {
  $$('[data-implant-inventory]').forEach(panel => {
    const input = panel.querySelector('[data-inventory-input]');
    const status = panel.querySelector('[data-inventory-status]');
    input?.addEventListener('input', () => renderInventorySuggestions(panel));
    input?.addEventListener('blur', () => {
      window.setTimeout(() => panel.querySelector('[data-inventory-menu]')?.classList.remove('open'), 120);
    });
    panel.querySelector('[data-inventory-add]')?.addEventListener('click', async () => {
      const match = canonicalMatch(options.passives || [], input?.value || '');
      if (!match.value) {
        if (status) {
          status.textContent = match.reason === 'ambiguous' ? `Matches: ${match.matches.join(', ')}. Keep typing.` : 'No known passive matches that text.';
          status.className = 'field-hint invalid';
        }
        return;
      }
      await saveInventoryPassive(match.value, {infinite: true, count: 0});
      input.value = '';
      renderInventorySuggestions(panel);
    });
    panel.addEventListener('click', async event => {
      const choice = event.target.closest('[data-inventory-choice]')?.dataset.inventoryChoice;
      if (choice) {
        input.value = choice;
        await saveInventoryPassive(choice, {infinite: true, count: 0});
        input.value = '';
        panel.querySelector('[data-inventory-menu]')?.classList.remove('open');
        return;
      }
      const deleted = event.target.closest('[data-inventory-delete]')?.dataset.inventoryDelete;
      if (deleted) await saveInventoryPassive(deleted, {delete: true});
    });
    panel.addEventListener('change', async event => {
      const passive = event.target.dataset.inventoryInfinite;
      if (!passive) return;
      const existing = options.implantInventory?.[passive] || {};
      await saveInventoryPassive(passive, {infinite: event.target.checked, count: existing.count || 0});
    });
    panel.addEventListener('input', event => {
      const passive = event.target.dataset.inventoryCount;
      if (!passive) return;
      window.clearTimeout(event.target._inventoryTimer);
      event.target._inventoryTimer = window.setTimeout(() => {
        saveInventoryPassive(passive, {infinite: false, count: event.target.value}).catch(error => {
          if (status) status.textContent = error.message;
        });
      }, 350);
    });
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
  const group = groups.find(item => (item.results || []).length) || groups[0];
  const route = (group.results || [])[0];
  if (!route) return '<div class="results-empty">No route found. Try fewer desired passives or upload a fresher save.</div>';
  return `
    <section class="result-group">
      <div class="group-heading">
        <h3>Recommended Route</h3>
        <p>${escapeHtml(group.description || 'Best practical option from the current search.')}</p>
      </div>
        <article class="route-card">
          <div class="route-header">
            <div>
              <h3>${escapeHtml(route.species)}</h3>
            </div>
            <div class="badges">
              <span class="${(route.junk || []).length ? 'bad' : 'good'}">${(route.junk || []).length} junk</span>
            </div>
          </div>
          <div class="breed-tree">${renderBreedTree(route, true)}</div>
        </article>
    </section>`;
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

function finalWorkLevel(card) {
  return card?.selectedFullyCondensedLevel || card?.selectedProjectedFullyCondensedLevel || card?.selectedLevel || '';
}

function renderWorkLevelValue(entry, selected = false) {
  const finalLevel = entry.fullyCondensedLevel || entry.projectedFullyCondensedLevel || entry.level || '';
  const finalText = finalLevel && Number(finalLevel) !== Number(entry.level) ? `${entry.level} -> ${finalLevel}` : `${entry.level}`;
  return selected ? `<strong>${escapeHtml(finalText)}</strong>` : escapeHtml(finalText);
}

function renderWorkSkillPills(work = [], selectedWork = '') {
  if (!work.length) return '';
  return `<div class="work-skill-list">${work.map(entry => {
    const selected = entry.key === selectedWork;
    const verified = entry.fullyCondensedLevel !== null && entry.fullyCondensedLevel !== undefined;
    return `
      <span class="work-skill-pill ${selected ? 'selected-work' : 'secondary-work'} ${verified ? 'verified' : 'projected'}">
        <span>${escapeHtml(entry.label)}</span>
        <span>${renderWorkLevelValue(entry, selected)}</span>
      </span>`;
  }).join('')}</div>`;
}

function renderBreedAction(card, profile) {
  return `<a class="card-action breed-corner-action" href="${escapeHtml(breedUrl(card, profile))}">Breed</a>`;
}

function renderWorkCard(card, compact = false, recommendation = null, profile = 'work_speed') {
  const owned = card.ownedCount ? `<span class="role-badge owned">Own: ${escapeHtml(card.ownedCount)}</span>` : '<span class="role-badge">Not owned</span>';
  const breedable = card.requiresOwnedSeed
    ? '<span class="badge self-breed">Self-Breed Only</span>'
    : card.breedable ? '<span class="badge good">Breedable</span>' : '<span class="badge bad">Not breedable</span>';
  const size = card.sizeKnown ? `${card.sizeGroup} (${card.size})` : 'Unknown size';
  const unavailable = card.unavailableReason ? `<p class="work-seed-warning">${escapeHtml(card.unavailableReason)}</p>` : '';
  const recHead = recommendation ? `
    <div class="work-rec-head">
      <div>
        <div class="work-rec-kicker">${escapeHtml(recommendation.title)}</div>
        <div class="work-rec-reason">${escapeHtml(recommendation.reason || '')}</div>
      </div>
      ${renderBreedAction(card, profile)}
    </div>` : renderBreedAction(card, profile);
  return `
    <article class="work-pal-card ${compact ? 'compact' : ''} ${recommendation ? 'work-rec-card' : ''}">
      ${recHead}
      <div class="pal-main">
        <div class="pal-avatar">${card.icon ? `<img src="${escapeHtml(assetUrl(card.icon))}" alt="">` : escapeHtml(speciesInitials(card.name))}</div>
        <div class="pal-copy">
          <h3>${escapeHtml(card.name)}</h3>
          <p>${escapeHtml(size)}</p>
          ${renderTypeChips(card.types || [])}
        </div>
      </div>
      ${renderWorkSkillPills(card.work || [], card.selectedWork)}
      ${unavailable}
      <div class="node-foot">
        ${owned}
        ${breedable}
        <span>${escapeHtml(card.selectedWorkLabel || 'Work')} ${escapeHtml(card.selectedLevel || '')}${finalWorkLevel(card) && Number(finalWorkLevel(card)) !== Number(card.selectedLevel) ? ` -> ${escapeHtml(finalWorkLevel(card))}` : ''}</span>
      </div>
    </article>`;
}

function recommendationByRole(data, role, fallbackTitle = '') {
  const rec = (data.recommendations || []).find(item => item.role === role || item.title === fallbackTitle);
  return rec?.card ? rec : null;
}

function renderWork(data) {
  const groups = data.groups || [];
  const cards = groups.flatMap(group => group.cards || []);
  if (!cards.length) return data.error ? resultCard('No work results', escapeHtml(data.error)) : renderJson(data);
  const primary = [recommendationByRole(data, 'recommended', 'Recommended'), recommendationByRole(data, 'dark', 'Best Dark')].filter(Boolean);
  return `
    <div class="owned-notice work-note">
      <strong>${escapeHtml(data.selectedWorkLabel || 'Work')} Suitability Browser</strong>
      <span>${escapeHtml(data.condensationNote || '')}</span>
    </div>
    ${primary.length ? `
      <section class="work-rec-section">
        <div class="group-heading"><h3>Top Picks</h3></div>
        <div class="work-rec-grid primary-picks">${primary.map(rec => renderWorkCard(rec.card, true, rec, 'work_speed')).join('')}</div>
      </section>` : ''}
    ${groups.map(group => `
      <details class="result-group work-group">
        <summary class="group-heading"><h3><span class="disclosure-icon" aria-hidden="true"></span>${escapeHtml(group.title)} (${(group.cards || []).length})</h3></summary>
        <div class="work-card-grid">${(group.cards || []).map(card => renderWorkCard(card, false, null, 'work_speed')).join('')}</div>
      </details>`).join('')}`;
}

function selectedRanchItem(data) {
  const slug = window.PALS_RANCH_ITEM_SLUG || '';
  if (slug) return (data.items || []).find(item => slugify(item.name) === slug) || null;
  const params = new URLSearchParams(window.location.search);
  const itemName = params.get('item') || '';
  return itemName ? (data.items || []).find(item => item.name.toLowerCase() === itemName.toLowerCase()) : null;
}

function ranchDropMeta(card, itemName = '') {
  const selected = (card.ranchDrops || []).find(drop => drop.name === itemName) || (card.ranchDrops || [])[0];
  if (!selected) return '';
  const amount = selected.min === selected.max ? selected.min : `${selected.min}-${selected.max}`;
  return `<span class="ranch-drop-meta">${escapeHtml(amount)} each · ${escapeHtml(selected.rate)}%</span>`;
}

function renderRanchPalCard(card, itemName = '') {
  const drops = (card.ranchDrops || []).map(drop => `<span class="ranch-drop-chip ${drop.name === itemName ? 'active' : ''}">${escapeHtml(drop.name)}</span>`).join('');
  const partner = card.partnerSkill?.name ? `<span class="ranch-skill-name">${escapeHtml(card.partnerSkill.name)}</span>` : '';
  return renderWorkCard(card, true, null, 'ranch_drops_focus').replace('</article>', `
      <div class="ranch-drop-row">${drops}${ranchDropMeta(card, itemName)}</div>
      ${partner}
    </article>`);
}

function renderRanchItemCard(item) {
  const best = item.best;
  const icon = best?.icon ? `<img src="${escapeHtml(assetUrl(best.icon))}" alt="">` : escapeHtml(speciesInitials(best?.name || item.name));
  const owned = (item.pals || []).reduce((sum, card) => sum + Number(card.ownedCount || 0), 0);
  return `
    <a class="ranch-item-card" href="/pals/ranch/${escapeHtml(slugify(item.name))}/">
      <span class="ranch-item-icon">${icon}</span>
      <span class="ranch-item-copy">
        <strong>${escapeHtml(item.name)}</strong>
        <span>${escapeHtml(item.count)} ranch Pal${item.count === 1 ? '' : 's'} · ${owned ? `Own: ${owned}` : 'Not owned'}</span>
      </span>
    </a>`;
}

function renderRanch(data) {
  const query = String(formData().search || '').toLowerCase();
  const items = (data.items || []).filter(item => !query || item.name.toLowerCase().includes(query));
  const selected = selectedRanchItem(data);
  if (selected) {
    const others = (selected.pals || []).filter(card => card.name !== selected.best?.name);
    return `
      <div class="ranch-detail-head">
        <div><h3>${escapeHtml(selected.name)}</h3><p>${escapeHtml(data.sourceNote || '')}</p></div>
        <a class="card-action" href="/pals/ranch/">All drops</a>
      </div>
      ${selected.best ? `<section class="work-rec-section ranch-top-pick"><div class="group-heading"><h3>Top Pick</h3></div><div class="work-rec-grid primary-picks">${renderRanchPalCard(selected.best, selected.name)}</div></section>` : ''}
      <section class="result-group">
        <div class="group-heading"><h3>All Producers</h3><p>Sorted by ownership, Farming level, footprint, and focus.</p></div>
        <div class="work-card-grid ranch-candidate-grid">${[selected.best, ...others].filter(Boolean).map(card => renderRanchPalCard(card, selected.name)).join('')}</div>
      </section>`;
  }
  if (!items.length) return '<div class="empty">No ranch drops match that search.</div>';
  return `
    <div class="owned-notice work-note">
      <strong>Ranch Drops</strong>
      <span>${escapeHtml(data.sourceNote || '')}</span>
    </div>
    <div class="ranch-item-grid">${items.map(renderRanchItemCard).join('')}</div>`;
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
  setText('#resultCount', moduleKey === 'breeding' ? 'Top route' : count ? `${count} result${count === 1 ? '' : 's'}` : '');
}

async function submitTool(event) {
  event.preventDefault();
  setText('#toolStatus', 'Running...');
  $('#results').innerHTML = '';
  const data = formData();
  try {
    let result;
    if (moduleKey === 'breeding') {
      const customProfile = customProfileByValue(data.breedingProfile);
      const finalPassives = customProfile ? customProfile.passives : splitList(data.passives);
      result = await api('/optimize', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          owner: data.owner || 'David',
          target: data.target,
          passives: finalPassives,
          implantPassives: selectedImplantPassives(finalPassives, Boolean(data.includeImplants)),
          genderPreference: data.genderPreference || 'any',
          breedingProfile: customProfile ? 'manual' : data.breedingProfile || 'manual',
          routePreference: 'best_overall',
        }),
      });
    } else if (moduleKey === 'ivs') {
      const finalPassives = splitList(data.passives);
      result = await api('/improve-ivs', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          owner: data.owner || 'David',
          target: data.target,
          passives: finalPassives,
          implantPassives: selectedImplantPassives(finalPassives, Boolean(data.includeImplants)),
          genderPreference: data.genderPreference || 'any',
          ivGoal: 'perfect',
        }),
      });
    } else if (moduleKey === 'work') {
      const includeSelf = data.includeSelfBreeders ? '1' : '0';
      result = await api(`/work-suitability?owner=${encodeURIComponent(data.owner || 'David')}&work=${encodeURIComponent(data.work || '')}&includeSelfBreeders=${includeSelf}`);
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
  setText('#toolStatus', 'Reloading...');
  await api('/reload');
  options = await api('/options');
  fillOptions();
  setText('#toolStatus', `Reloaded ${options.rosterCount || 0} Pals.`);
}

function applyUrlPrefill() {
  if (moduleKey !== 'breeding') return;
  const params = new URLSearchParams(window.location.search);
  const target = params.get('target');
  const profile = params.get('profile');
  if (target) {
    const targetInput = document.querySelector('[name="target"]');
    if (targetInput && !targetInput.value) targetInput.value = target;
  }
  if (profile && $('#breedingProfile')) {
    $('#breedingProfile').value = profile;
    applySelectedProfile();
  }
  syncCustomSelects();
}

function syncCustomSelects() {
  $$('select').forEach(select => {
    if (select.dataset.customSelectReady === '1') {
      updateCustomSelect(select);
      return;
    }
    select.dataset.customSelectReady = '1';
    select.classList.add('native-select-hidden');
    const shell = document.createElement('span');
    shell.className = 'custom-select';
    shell.innerHTML = '<button type="button" class="custom-select-button"></button><span class="custom-select-menu"></span>';
    select.after(shell);
    shell.querySelector('button')?.addEventListener('click', () => {
      $$('.custom-select.open').forEach(open => {
        if (open !== shell) open.classList.remove('open');
      });
      shell.classList.toggle('open');
    });
    shell.addEventListener('click', event => {
      const option = event.target.closest('[data-select-value]');
      if (!option) return;
      select.value = option.dataset.selectValue || '';
      select.dispatchEvent(new Event('change', {bubbles: true}));
      shell.classList.remove('open');
      updateCustomSelect(select);
    });
    select.addEventListener('change', () => updateCustomSelect(select));
    updateCustomSelect(select);
  });
}

function updateCustomSelect(select) {
  const shell = select.nextElementSibling?.classList?.contains('custom-select') ? select.nextElementSibling : null;
  if (!shell) return;
  const selected = select.selectedOptions?.[0];
  shell.querySelector('.custom-select-button').textContent = selected?.textContent || 'Choose';
  shell.querySelector('.custom-select-menu').innerHTML = [...select.options].map(option => `
    <button type="button" data-select-value="${escapeHtml(option.value)}" class="${option.value === select.value ? 'is-selected' : ''}">
      ${escapeHtml(option.textContent)}
    </button>`).join('');
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
  setTheme(localStorage.getItem('pals.theme') || 'dark');
  $('#themeToggle')?.addEventListener('click', () => {
    setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
  });
  $('#toolForm')?.addEventListener('submit', submitTool);
  initSuggestFields();
  initPassivePickers();
  initPassiveTooltips();
  initProfiles();
  initImplantInventories();
  $('#reloadData')?.addEventListener('click', () => reloadOptions().catch(error => setText('#toolStatus', error.message)));
  $('#refreshLiveSave')?.addEventListener('click', () => refreshLiveSave().catch(error => setText('#liveStatus', error.message)));
  $('#saveUpload')?.addEventListener('change', event => uploadSave(event.target.files?.[0]).catch(error => setText('#liveStatus', error.message)));
  options = await api('/options');
  fillOptions();
  if (moduleKey === 'ranch' && window.PALS_RANCH_ITEM_SLUG) {
    $('#toolForm')?.requestSubmit();
  }
  loadLiveStatus().catch(() => {});
}

document.addEventListener('click', event => {
  if (!event.target.closest('.custom-select')) {
    $$('.custom-select.open').forEach(shell => shell.classList.remove('open'));
  }
});

init().catch(error => {
  setText('#palsMeta', error.message);
});
