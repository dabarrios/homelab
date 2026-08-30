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
let ranchDropsCache = null;

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
  const text = await response.text();
  let payload;
  try {
    payload = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(text.slice(0, 240).trim() || `${response.status} ${response.statusText}`);
  }
  if (!response.ok || payload.error) throw new Error(payload.error || `${response.status} ${response.statusText}`);
  return payload;
}

function setText(selector, text) {
  const element = $(selector);
  if (element) element.textContent = text || '';
}

function setLiveStatus(text, tone = 'muted', title = '') {
  const element = $('#liveStatus');
  if (!element) return;
  element.textContent = text || '';
  element.dataset.tone = tone;
  element.title = title || '';
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
  if (button) {
    button.textContent = next === 'dark' ? '☀' : '☾';
    button.setAttribute('aria-label', next === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
    button.title = next === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';
  }
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

const EMPTY_STATES = {
  breeding: {
    title: 'Build a breeding plan',
    lead: 'Choose a target Pal and the passives you want.',
    hint: 'Select your target Pal and desired passives, then click Optimize.',
    features: [
      ['Optimized Path', 'Finds a practical route to collect your desired passives.'],
      ['Resource Aware', 'Uses owned Pals and implant inventory when enabled.'],
      ['Multiple Routes', 'Compares clean, fast, and practical breeding options.'],
    ],
  },
  ivs: {
    title: 'Find IV parents',
    lead: 'Pick a target Pal and final passives to compare parent pairs.',
    hint: 'Choose the final passives, then calculate IVs.',
    features: [
      ['Parent Coverage', 'Highlights pairs with the best HP, Attack, and Defense support.'],
      ['Implant Aware', 'Ignores passives you plan to add later when enabled.'],
      ['Junk Tracking', 'Keeps unwanted passives visible before you commit.'],
    ],
  },
  work: {
    title: 'Pick a work skill to find the best worker.',
    lead: 'We will analyze all Pals, show the top choices, and let you send any candidate to Breeding.',
    hint: 'Select a work skill and click Find Workers to see the best Pal.',
    features: [
      ['Best Overall Pick', 'The strongest practical worker for the selected skill.'],
      ['Best Dark-Type Pick', 'Top Dark-type option for night uptime.'],
      ['Condensed Levels', 'Shows base to fully condensed work suitability.'],
      ['Breed From Here', 'Open Breeding with the worker and work-speed profile already selected.'],
    ],
  },
  ranch: {
    title: 'Choose a ranch drop to get started.',
    lead: 'We will find the best Pal to ranch this item, show every producer, and let you send any producer to Breeding.',
    hint: 'Select a ranch drop and click Find Ranchers to see the best Pal.',
    features: [
      ['Best Rancher', 'The strongest producer for the selected drop appears first.'],
      ['All Drop Sources', 'See every Pal that can produce the item, including drop data.'],
      ['Breed From Here', 'Open Breeding with the producer and ranch profile already selected.'],
    ],
  },
  bases: {
    title: 'Plan your perfect base team.',
    lead: 'Set your team mode, configure your base sites, and choose the team size.',
    hint: 'Configure your base and team settings, then build your best team.',
    features: [
      ['Optimal Team', 'The best Pal lineup for your base needs.'],
      ['Role Coverage', 'See all work skills and how they are covered.'],
      ['Alternatives', 'View other strong team compositions.'],
      ['Breeding Path', 'Breed from here for any missing Pals.'],
    ],
  },
};

function emptyStateHtml(key = moduleKey) {
  const state = EMPTY_STATES[key] || EMPTY_STATES.breeding;
  const focusedState = key === 'work' ? `
    <div class="empty-hero empty-focused-hero">
      <div class="empty-work-state">
        <div class="empty-tool-icon empty-work-icon" aria-hidden="true">
          <span></span>
        </div>
        <h3>${escapeHtml(state.title)}</h3>
        <p>${escapeHtml(state.lead)}</p>
        <div class="empty-work-divider"><span></span><b class="empty-divider-work-mark"></b><span></span></div>
        <div class="empty-work-features empty-work-features-wide">
          ${state.features.map(([title, text], index) => `<div><i class="empty-feature-icon empty-feature-icon-${index + 1}" aria-hidden="true"></i><b>${escapeHtml(title)}</b><span>${escapeHtml(text)}</span></div>`).join('')}
        </div>
        <p class="empty-hint">${escapeHtml(state.hint)}</p>
      </div>
    </div>` : key === 'ranch' ? `
    <div class="empty-hero empty-focused-hero">
      <div class="empty-ranch-state">
        <div class="empty-ranch-icon" aria-hidden="true">
          <span class="barn-roof"></span>
          <span class="barn-body"></span>
          <span class="barn-door"></span>
          <span class="barn-fence"></span>
        </div>
        <h3>${escapeHtml(state.title)}</h3>
        <p>${escapeHtml(state.lead)}</p>
        <div class="empty-work-divider empty-ranch-divider"><span></span><b>◇</b><span></span></div>
        <div class="empty-work-features empty-ranch-features">
          ${state.features.map(([title, text]) => `<div><b>${escapeHtml(title)}</b><span>${escapeHtml(text)}</span></div>`).join('')}
        </div>
        <p class="empty-hint">${escapeHtml(state.hint)}</p>
      </div>
    </div>` : key === 'bases' ? `
    <div class="empty-hero empty-focused-hero empty-bases-hero">
      <div class="empty-bases-state">
        <div class="empty-bases-icon" aria-hidden="true">
          <span class="base-tower"></span>
          <span class="base-wall"></span>
          <span class="base-gate"></span>
        </div>
        <h3>${escapeHtml(state.title)}</h3>
        <p>${escapeHtml(state.lead)}</p>
        <p>Then click Build Best Team to see the optimal lineup.</p>
        <div class="empty-base-flow" aria-hidden="true">
          <div class="empty-base-step empty-base-step-sites"><i></i><b>1. Detect Base Sites</b><span>Read your base structure and work sites.</span></div>
          <em></em>
          <div class="empty-base-step empty-base-step-rules"><i></i><b>2. Apply Constraints</b><span>Your team mode and worker count guide the build.</span></div>
          <em></em>
          <div class="empty-base-step empty-base-step-team"><i></i><b>3. Optimize Team</b><span>Analyze all Pals to find the best combination.</span></div>
          <em></em>
          <div class="empty-base-step empty-base-step-best"><i></i><b>4. Best Team</b><span>Get role coverage and breeding handoffs.</span></div>
        </div>
        <div class="empty-work-features empty-base-features empty-work-features-wide">
          ${state.features.map(([title, text], index) => `<div><i class="empty-feature-icon empty-base-feature-icon-${index + 1}" aria-hidden="true"></i><b>${escapeHtml(title)}</b><span>${escapeHtml(text)}</span></div>`).join('')}
        </div>
        <p class="empty-hint">${escapeHtml(state.hint)}</p>
      </div>
    </div>` : '';
  if (focusedState) return focusedState;
  const diagram = key === 'ivs' ? `
      <div class="empty-diagram empty-diagram-ivs">
        <div class="empty-card iv-empty-card">
          <strong>Parent A</strong>
          <span>HP <em>-</em></span>
          <span>Attack <em>-</em></span>
          <span>Defense <em>-</em></span>
        </div>
        <div class="empty-plus">+</div>
        <div class="empty-card iv-empty-card">
          <strong>Parent B</strong>
          <span>HP <em>-</em></span>
          <span>Attack <em>-</em></span>
          <span>Defense <em>-</em></span>
        </div>
        <div class="empty-arrow"></div>
        <div class="empty-target iv-empty-target">
          <strong>Target Pal</strong>
          <span>HP <em>-</em></span>
          <span>Attack <em>-</em></span>
          <span>Defense <em>-</em></span>
        </div>
        <div class="empty-goal-card">
          <strong>Goal</strong>
          <span>Max IVs in selected stats</span>
          <i>☆ ☆ ☆ ☆ ☆</i>
        </div>
      </div>` : `
      <div class="empty-diagram">
        <div class="empty-card">
          <strong>${key === 'work' ? 'Candidate A' : key === 'ranch' ? 'Producer A' : 'Parent A'}</strong>
          <i></i><i></i><i></i>
        </div>
        <div class="empty-plus">+</div>
        <div class="empty-card">
          <strong>${key === 'work' ? 'Candidate B' : key === 'ranch' ? 'Producer B' : 'Parent B'}</strong>
          <i></i><i></i><i></i>
        </div>
        <div class="empty-arrow"></div>
        <div class="empty-target"><strong>${key === 'bases' ? 'Base Team' : key === 'work' ? 'Best Pick' : key === 'ranch' ? 'Selected Drop' : 'Target Pal'}</strong><span>?</span></div>
      </div>`;
  return `
    <div class="empty-hero">
      <div class="empty-icon" aria-hidden="true">
        <span></span><span></span><span></span>
      </div>
      <h3>${escapeHtml(state.title)}</h3>
      <p>${escapeHtml(state.lead)}</p>
      ${diagram}
      <div class="empty-features">
        ${state.features.map(([title, text]) => `<div><b>${escapeHtml(title)}</b><span>${escapeHtml(text)}</span></div>`).join('')}
      </div>
      <p class="empty-hint">${escapeHtml(state.hint)}</p>
    </div>`;
}

function showEmptyState() {
  const results = $('#results');
  if (!results) return;
  results.classList.add('results-empty');
  results.innerHTML = emptyStateHtml(moduleKey);
  setText('#resultCount', '');
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
    const selected = select.value;
    select.innerHTML = bases.length
      ? bases.map(base => `<option value="${escapeHtml(base.id)}">${escapeHtml(base.displayName || base.customName || base.defaultName || base.label || base.name || base.id)}</option>`).join('')
      : '<option value="">No bases found</option>';
    if (selected && [...select.options].some(option => option.value === selected)) select.value = selected;
  });
  updateBaseLabelField();
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
  menu.innerHTML = matches.map(value => {
    const tone = type === 'passives' || type === 'passive' ? passiveTone(value) : '';
    return `<button type="button" data-suggest-value="${escapeHtml(value)}">${tone ? `<span class="passive-dot ${tone}"></span>` : ''}<span>${escapeHtml(value)}</span></button>`;
  }).join('');
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
    return `<button type="button" data-suggest-passive="${escapeHtml(passive)}"><span class="passive-dot ${tone}"></span><span>${escapeHtml(passive)}</span></button>`;
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
    input.focus();
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
  renderPassiveSuggestions(picker);
  input.focus();
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
  menu.innerHTML = matches.map(passive => `<button type="button" data-inventory-choice="${escapeHtml(passive)}"><span class="passive-dot ${passiveTone(passive)}"></span><span>${escapeHtml(passive)}</span></button>`).join('');
  menu.classList.toggle('open', matches.length > 0);
}

async function addInventoryPassive(panel) {
  const input = panel.querySelector('[data-inventory-input]');
  const status = panel.querySelector('[data-inventory-status]');
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
  if (status) {
    status.textContent = `${match.value} added.`;
    status.className = 'field-hint valid';
  }
  input.focus();
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
  const entries = Object.entries(options.implantInventory || {}).sort(([a], [b]) => a.localeCompare(b));
  const availableCount = entries.filter(([, item]) => item?.infinite || Number(item?.count || 0) > 0).length;
  $$('[data-inventory-summary]').forEach(summary => {
    summary.textContent = entries.length
      ? `${entries.length} implant passive${entries.length === 1 ? '' : 's'} tracked.`
      : 'No implant passives inventoried yet.';
  });
  $$('[data-implant-inventory]').forEach(panel => {
    const list = panel.querySelector('[data-inventory-list]');
    if (!list) return;
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
  $$('[data-open-implant-inventory]').forEach(button => {
    button.addEventListener('click', () => {
      $('#implantInventoryModal')?.classList.remove('hidden');
      $('#implantInventoryModal [data-inventory-input]')?.focus();
    });
  });
  $('#closeImplantInventory')?.addEventListener('click', () => $('#implantInventoryModal')?.classList.add('hidden'));
  $('#implantInventoryModal')?.addEventListener('click', event => {
    if (event.target === $('#implantInventoryModal')) $('#implantInventoryModal')?.classList.add('hidden');
  });
  $$('[data-implant-inventory]').forEach(panel => {
    const input = panel.querySelector('[data-inventory-input]');
    const status = panel.querySelector('[data-inventory-status]');
    input?.addEventListener('input', () => renderInventorySuggestions(panel));
    input?.addEventListener('keydown', event => {
      if (event.key === 'Enter') {
        event.preventDefault();
        addInventoryPassive(panel).catch(error => {
          if (status) status.textContent = error.message;
        });
      }
    });
    input?.addEventListener('blur', () => {
      window.setTimeout(() => panel.querySelector('[data-inventory-menu]')?.classList.remove('open'), 120);
    });
    panel.querySelector('[data-inventory-add]')?.addEventListener('click', async () => {
      await addInventoryPassive(panel);
    });
    panel.addEventListener('click', async event => {
      const choice = event.target.closest('[data-inventory-choice]')?.dataset.inventoryChoice;
      if (choice) {
        input.value = choice;
        await saveInventoryPassive(choice, {infinite: true, count: 0});
        input.value = '';
        panel.querySelector('[data-inventory-menu]')?.classList.remove('open');
        input.focus();
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

function initFreshCopyToggle() {
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-show-fresh-copy]');
    if (!button) return;
    const tree = document.querySelector('[data-fresh-copy-tree]');
    if (!tree) return;
    tree.classList.remove('hidden');
    button.hidden = true;
    tree.scrollIntoView({block: 'nearest', behavior: 'smooth'});
  });
}

function resultCard(title, body, meta = '') {
  return `<article class="result-card"><h3>${escapeHtml(title)}</h3>${meta ? `<p class="result-meta">${escapeHtml(meta)}</p>` : ''}<div>${body}</div></article>`;
}

function renderJson(data) {
  return `<pre class="json-output">${escapeHtml(JSON.stringify(data, null, 2))}</pre>`;
}

function palboxLocationText(node) {
  if (node.box) return `Box ${node.box}, slot ${node.slot}`;
  return locationText(node);
}

function readyFinishCandidate(data) {
  const finalPassives = new Set(data.finalPassives || []);
  const implantPassives = new Set(data.implantPassives || []);
  if (!finalPassives.size || !implantPassives.size) return null;
  return (data.alreadyOwned?.results || []).find(candidate => {
    const owned = new Set(candidate.passives || []);
    const missing = [...finalPassives].filter(passive => !owned.has(passive));
    return missing.length > 0 && missing.every(passive => implantPassives.has(passive));
  }) || null;
}

function renderReadyFinishCard(candidate, data) {
  const finalPassives = data.finalPassives || [];
  const owned = new Set(candidate.passives || []);
  const implantPassives = new Set(data.implantPassives || []);
  const present = finalPassives.filter(passive => owned.has(passive));
  const missingImplants = finalPassives.filter(passive => !owned.has(passive) && implantPassives.has(passive));
  const junk = candidate.junk || [];
  return `
    <article class="ready-finish-card">
      <div class="ready-kicker"><span class="ready-star" aria-hidden="true"></span>Best Option</div>
      <div class="ready-head">
        <div>
          <h3>Ready to Finish</h3>
          <p>Use your owned ${escapeHtml(candidate.species)} and implant the missing passive.</p>
        </div>
        <div class="ready-metrics">
          <span><b>Breeding Steps</b><strong>0</strong></span>
          <span><b>Junk Pals</b><strong>${escapeHtml(junk.length)}</strong></span>
        </div>
      </div>
      <div class="ready-grid">
        <div class="ready-pal-summary">
          <div class="pal-avatar ready-avatar">${candidate.icon ? `<img src="${escapeHtml(assetUrl(candidate.icon))}" alt="">` : escapeHtml(speciesInitials(candidate.species))}</div>
          <div>
            <h4>${escapeHtml(candidate.species)}</h4>
            <p>${escapeHtml(palboxLocationText(candidate))}</p>
            <span class="role-badge owned">Already owned</span>
          </div>
        </div>
        <div class="ready-progress">
          <span>Progress</span>
          <strong>${escapeHtml(present.length)} / ${escapeHtml(finalPassives.length)} <em>final passives present</em></strong>
          <p>${escapeHtml(missingImplants.length)} implant${missingImplants.length === 1 ? '' : 's'} needed</p>
        </div>
        <div class="ready-missing">
          <span>Missing Passive</span>
          <div class="passive-list ready-passive-list">
            ${missingImplants.map(passive => `<span class="passive-bar implant-missing ${passiveTone(passive)}" tabindex="0" data-passive-tooltip="${escapeHtml(passive)}"><span>${escapeHtml(passive)}</span></span>`).join('')}
          </div>
          <p>Available in implant inventory</p>
        </div>
      </div>
      <div class="ready-passives">
        <span>Passives</span>
        <div class="passive-list ready-passive-list">
          ${present.map(passive => `<span class="passive-bar ${passiveTone(passive)}" tabindex="0" data-passive-tooltip="${escapeHtml(passive)}"><span>${escapeHtml(passive)}</span></span>`).join('')}
          ${missingImplants.map(passive => `<span class="passive-bar implant-missing ${passiveTone(passive)}" tabindex="0" data-passive-tooltip="${escapeHtml(passive)}"><span>${escapeHtml(passive)}</span></span>`).join('')}
        </div>
      </div>
      <div class="ready-actions">
        <button type="button" class="card-action ready-fresh-copy" data-show-fresh-copy>Breed a fresh copy instead</button>
      </div>
    </article>`;
}

function renderBreeding(data) {
  const groups = data.groups || [];
  if (!groups.length) return renderJson(data);
  const group = groups.find(item => (item.results || []).length) || groups[0];
  const route = (group.results || [])[0];
  if (!route) return '<div class="results-empty">No route found. Try fewer desired passives or upload a fresher save.</div>';
  const readyCandidate = readyFinishCandidate(data);
  if (readyCandidate) {
    return `
      <section class="result-group">
        ${renderReadyFinishCard(readyCandidate, data)}
        <article class="route-card fresh-copy-card hidden" data-fresh-copy-tree>
          <div class="route-header">
            <div>
              <h3>Fresh Copy</h3>
              <p>This breeds a new ${escapeHtml(route.species)} with all requested passives.</p>
            </div>
            <div class="badges">
              <span>${escapeHtml(route.steps || 0)} steps</span>
              <span class="${(route.junk || []).length ? 'bad' : 'good'}">${(route.junk || []).length} junk</span>
            </div>
          </div>
          <div class="breed-tree">${renderBreedTree(route, true)}</div>
        </article>
      </section>`;
  }
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
  if (!query) return emptyStateHtml('ranch');
  if (items.length === 1) {
    window.history.replaceState({}, '', `/pals/ranch/${slugify(items[0].name)}/`);
    window.PALS_RANCH_ITEM_SLUG = slugify(items[0].name);
    return renderRanch(data);
  }
  return `<div class="ranch-item-grid">${items.slice(0, 8).map(renderRanchItemCard).join('')}</div>`;
}

function renderBases(data) {
  if (data.error) return resultCard('No base plan', escapeHtml(data.error));
  return renderJson(data);
}

function selectedBaseOption() {
  const selectedId = document.querySelector('.js-base')?.value || '';
  return (options.baseSites?.bases || []).find(base => base.id === selectedId) || null;
}

function updateBaseLabelField() {
  const input = $('#baseLabel');
  if (!input) return;
  const base = selectedBaseOption();
  input.value = base?.customName || '';
  input.disabled = !base;
  $('#saveBaseLabel')?.toggleAttribute('disabled', !base);
  setText('#baseLabelHint', base ? 'Save a local display name for the selected base.' : 'Sync a save with bases before naming them.');
}

async function saveBaseLabel() {
  const base = selectedBaseOption();
  if (!base) return;
  const label = ($('#baseLabel')?.value || '').trim();
  const result = await api('/base-labels', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({baseId: base.id, label}),
  });
  options.baseSites = await api('/base-work-sites');
  fillOptions();
  setText('#baseLabelHint', result.ok ? 'Base name saved.' : 'Base name was not saved.');
}

function renderResult(data) {
  const renderers = {breeding: renderBreeding, ivs: renderIvs, work: renderWork, ranch: renderRanch, bases: renderBases};
  $('#results').classList.remove('results-empty');
  $('#results').innerHTML = (renderers[moduleKey] || renderJson)(data);
  const count = data.total || data.totalItems || data.rosterCount || (data.groups || []).length || '';
  setText('#resultCount', moduleKey === 'breeding' ? 'Top route' : count ? `${count} result${count === 1 ? '' : 's'}` : '');
}

async function ranchDropsData() {
  if (ranchDropsCache) return ranchDropsCache;
  const owner = encodeURIComponent($('.js-owner')?.value || 'David');
  ranchDropsCache = await api(`/ranch-drops?owner=${owner}`);
  return ranchDropsCache;
}

async function renderRanchDropSuggestions(field) {
  const input = field.querySelector('input[name="search"]');
  const menu = field.querySelector('[data-ranch-drop-menu]');
  const query = String(input?.value || '').trim().toLowerCase();
  if (!query) {
    menu.innerHTML = '';
    menu.classList.remove('open');
    return;
  }
  const data = await ranchDropsData();
  const matches = (data.items || [])
    .filter(item => item.name.toLowerCase().includes(query))
    .slice(0, 8);
  menu.innerHTML = matches.map(item => `<button type="button" data-ranch-drop="${escapeHtml(item.name)}"><span>${escapeHtml(item.name)}</span><em>${escapeHtml(item.count)} Pal${item.count === 1 ? '' : 's'}</em></button>`).join('');
  menu.classList.toggle('open', matches.length > 0);
}

function initRanchDropSearch() {
  const field = $('[data-ranch-drop-search]');
  if (!field) return;
  const input = field.querySelector('input[name="search"]');
  input?.addEventListener('input', () => renderRanchDropSuggestions(field).catch(error => setText('#toolStatus', error.message)));
  input?.addEventListener('keydown', async event => {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    const data = await ranchDropsData();
    const query = String(input.value || '').trim().toLowerCase();
    const matches = (data.items || []).filter(item => item.name.toLowerCase().includes(query));
    if (matches.length === 1) {
      input.value = matches[0].name;
      window.PALS_RANCH_ITEM_SLUG = slugify(matches[0].name);
      window.history.replaceState({}, '', `/pals/ranch/${slugify(matches[0].name)}/`);
      field.querySelector('[data-ranch-drop-menu]')?.classList.remove('open');
      $('#toolForm')?.requestSubmit();
    }
  });
  input?.addEventListener('blur', () => {
    window.setTimeout(() => field.querySelector('[data-ranch-drop-menu]')?.classList.remove('open'), 120);
  });
  field.addEventListener('click', event => {
    const drop = event.target.closest('[data-ranch-drop]')?.dataset.ranchDrop;
    if (!drop) return;
    input.value = drop;
    window.PALS_RANCH_ITEM_SLUG = slugify(drop);
    window.history.replaceState({}, '', `/pals/ranch/${slugify(drop)}/`);
    field.querySelector('[data-ranch-drop-menu]')?.classList.remove('open');
    $('#toolForm')?.requestSubmit();
  });
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
      const includeSelf = data.includeSelfBreeders ? '1' : '0';
      result = await api(`/ranch-drops?owner=${encodeURIComponent(data.owner || 'David')}&includeSelfBreeders=${includeSelf}`);
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
  if (!status.configured) {
    setLiveStatus('Live save not configured', 'muted');
    return;
  }
  setLiveStatus(status.ok ? 'Live save ready' : 'Live save unavailable', status.ok ? 'good' : 'bad', status.path || '');
}

async function refreshLiveSave() {
  setLiveStatus('Syncing save...', 'active');
  const result = await api('/live-save/refresh', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({force: true}),
  });
  setLiveStatus(result.ok ? `Synced ${result.rosterCount || 0} Pals` : result.error || 'Sync failed', result.ok ? 'good' : 'bad');
  options = await api('/options');
  ranchDropsCache = null;
  fillOptions();
}

async function uploadSave(file) {
  if (!file) return;
  const form = new FormData();
  form.append('files', file, file.webkitRelativePath || file.name);
  setLiveStatus('Uploading save...', 'active', file.name);
  const response = await fetch(apiUrl('/upload-save'), {method: 'POST', body: form});
  const text = await response.text();
  let result;
  try {
    result = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(text.slice(0, 240).trim() || `${response.status} ${response.statusText}`);
  }
  if (!response.ok || !result.ok) throw new Error(result.error || 'Upload failed.');
  setLiveStatus(`Imported ${result.rosterCount || 0} Pals`, 'good', file.name);
  options = await api('/options');
  ranchDropsCache = null;
  fillOptions();
}

async function init() {
  setTheme(localStorage.getItem('pals.theme') || 'dark');
  $('#toolForm')?.addEventListener('submit', submitTool);
  initSuggestFields();
  initPassivePickers();
  initPassiveTooltips();
  initProfiles();
  initImplantInventories();
  initFreshCopyToggle();
  initRanchDropSearch();
  $('#refreshLiveSave')?.addEventListener('click', () => refreshLiveSave().catch(error => setLiveStatus(error.message, 'bad')));
  $('#saveUpload')?.addEventListener('change', event => uploadSave(event.target.files?.[0]).catch(error => setLiveStatus(error.message, 'bad')));
  $('.js-base')?.addEventListener('change', updateBaseLabelField);
  $('#saveBaseLabel')?.addEventListener('click', () => saveBaseLabel().catch(error => setText('#baseLabelHint', error.message)));
  options = await api('/options');
  fillOptions();
  showEmptyState();
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
