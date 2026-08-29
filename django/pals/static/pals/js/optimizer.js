const state = {
  species: [],
  passives: [],
  owners: [],
  selectedPassives: [],
  selectedImplantPassives: [],
  passivesByOwner: {},
  passiveMeta: {},
  speciesMeta: {},
  workTypes: [],
  baseSites: null,
  baseSitesLoading: null,
  baseSettings: {},
  implantInventory: {},
  ivTargetPals: [],
  ivTargetLoadSeq: 0,
  mode: 'breed',
  formsByMode: {
    breed: {owner: 'David', target: '', passives: [], genderPreference: 'any', breedingProfile: 'manual', ivPreference: 'none', ivGoal: 'none', workType: 'mining', workDisplay: 'all'},
    iv: {owner: 'David', target: '', passives: [], implantPassives: [], includeImplants: true, genderPreference: 'any', breedingProfile: 'manual', ivPreference: 'none', ivGoal: 'perfect', workType: 'mining', workDisplay: 'all', ivTargetInstance: ''},
    work: {owner: 'David', target: '', passives: [], genderPreference: 'any', breedingProfile: 'manual', ivPreference: 'none', ivGoal: 'none', workType: '', workDisplay: 'all', workIncludeInsomnia: false, baseId: ''},
    ranch: {owner: 'David', target: '', passives: [], genderPreference: 'any', breedingProfile: 'manual', ivPreference: 'none', ivGoal: 'none', workType: 'farming', workDisplay: 'all', workIncludeInsomnia: false, ranchSearch: '', ranchItem: ''},
    base: {owner: 'David', target: '', passives: [], genderPreference: 'any', breedingProfile: 'manual', ivPreference: 'none', ivGoal: 'none', workType: 'mining', workDisplay: 'all', baseId: '', basePlannerMode: 'ideal', maxWorkers: 15},
  },
  plansByMode: {breed: null, iv: null, work: null, ranch: null, base: null},
  lastPlan: null,
  lastBreedSignature: '',
  lastAutoRouteName: '',
  savedRoutes: [],
  modeBackStack: [],
  modeForwardStack: [],
  customProfiles: [],
  builtInProfileNames: {},
  editingProfileId: '',
  editingBuiltInProfileValue: '',
  editingProfilePassives: [],
  live: {
    refreshing: false,
    statusPoll: null,
    sawRefreshInProgress: false,
    observedRefreshAt: '',
  }
};
const $ = id => document.getElementById(id);
const API_BASE = (window.PALS_API_BASE || '/api').replace(/\/$/, '');
const ASSET_BASE = (window.PALS_ASSET_BASE || '/assets/pals').replace(/\/$/, '');
const THEME_KEY = 'pals.theme';

function apiUrl(path) {
  return path.startsWith('/api/') ? `${API_BASE}${path.slice(4)}` : path;
}

function assetUrl(path) {
  if (!path || !path.startsWith('/assets/pals/')) return path;
  return `${ASSET_BASE}/${encodeURIComponent(path.split('/').pop())}`;
}

function applyTheme(theme) {
  const nextTheme = theme === 'light' ? 'light' : 'dark';
  document.documentElement.dataset.theme = nextTheme;
  localStorage.setItem(THEME_KEY, nextTheme);
  const button = $('themeToggle');
  if (button) {
    button.textContent = nextTheme === 'light' ? 'Dark' : 'Light';
    button.setAttribute('aria-pressed', String(nextTheme === 'light'));
  }
}

function initTheme() {
  const saved = localStorage.getItem(THEME_KEY) || 'dark';
  applyTheme(saved);
  $('themeToggle')?.addEventListener('click', () => {
    applyTheme(document.documentElement.dataset.theme === 'light' ? 'dark' : 'light');
  });
}

function setStatus(el, message, kind = '') {
  el.textContent = message;
  const isHelper = el.classList.contains('helper') || el.dataset.role === 'helper';
  if (isHelper && !message) {
    el.className = 'helper';
    el.dataset.role = 'helper';
    return;
  }
  const base = isHelper ? 'helper status' : 'status';
  el.className = kind ? `${base} ${kind}` : base;
  if (isHelper) el.dataset.role = 'helper';
}

function showToast(message, kind = 'good') {
  const toast = $('toast');
  toast.textContent = message;
  toast.className = `toast show ${kind}`;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    toast.className = 'toast';
  }, 3200);
}


function breedSignature(owner, target, passives) {
  return JSON.stringify({
    owner: String(owner || '').toLowerCase(),
    target: String(target || '').toLowerCase(),
    passives: [...(passives || [])].map(matchKey).sort(),
  });
}

function currentFormFromUi() {
  const includeInsomnia = state.mode === 'ranch'
    ? Boolean($('ranchIncludeInsomnia')?.checked)
    : Boolean($('workIncludeInsomnia')?.checked);
  return {
    owner: $('owner')?.value || 'David',
    target: $('target')?.value || '',
    passives: [...state.selectedPassives],
    implantPassives: [...state.selectedImplantPassives],
    includeImplants: Boolean($('includeImplants')?.checked),
    genderPreference: $('genderPreference')?.value || 'any',
    breedingProfile: $('breedingProfile')?.value || 'manual',
    ivPreference: 'none',
    ivGoal: $('ivGoal')?.value || 'none',
    ivTargetInstance: $('ivTargetInstance')?.value || '',
    workType: $('workType')?.value || '',
    workDisplay: $('workDisplay')?.value || 'all',
    workIncludeInsomnia: includeInsomnia,
    ranchSearch: $('ranchSearch')?.value || '',
    ranchItem: state.formsByMode[state.mode]?.ranchItem || '',
    baseId: $('baseSelect')?.value || '',
    basePlannerMode: $('basePlannerMode')?.value || 'ideal',
    maxWorkers: Math.min(15, Math.max(1, Number($('baseWorkerCount')?.value || 15))),
  };
}
function saveCurrentForm() {
  state.formsByMode[state.mode] = currentFormFromUi();
}

function applyFormToUi(form) {
  if (!form) return;
  if ($('owner').options.length && form.owner) $('owner').value = form.owner;
  $('target').value = form.target || '';
  state.selectedPassives = [...(form.passives || [])];
  state.selectedImplantPassives = [...(form.implantPassives || [])].filter(passive => state.selectedPassives.includes(passive));
  $('genderPreference').value = form.genderPreference || 'any';
  if ($('breedingProfile')) $('breedingProfile').value = form.breedingProfile || 'manual';
  if ($('breedingProfile') && !profileValueExists(form.breedingProfile || 'manual')) $('breedingProfile').value = 'manual';
  updateProfileToolbar();
  $('ivGoal').value = form.ivGoal === 'perfect' || state.mode === 'iv' ? 'perfect' : form.ivGoal || 'none';
  if ($('ivTargetInstance')) $('ivTargetInstance').value = form.ivTargetInstance || '';
  if ($('includeImplants')) $('includeImplants').checked = form.includeImplants !== false;
  updateInsomniaAvailability();
  if ($('workType') && form.workType) $('workType').value = form.workType;
  if ($('workDisplay') && form.workDisplay) $('workDisplay').value = form.workDisplay === 'known' ? 'all' : form.workDisplay;
  if ($('workIncludeInsomnia')) $('workIncludeInsomnia').checked = Boolean(form.workIncludeInsomnia);
  if ($('ranchSearch')) $('ranchSearch').value = form.ranchSearch || '';
  if ($('ranchIncludeInsomnia')) $('ranchIncludeInsomnia').checked = Boolean(form.workIncludeInsomnia);
  if ($('baseSelect') && form.baseId) $('baseSelect').value = form.baseId;
  if ($('basePlannerMode')) $('basePlannerMode').value = form.basePlannerMode || 'ideal';
  if ($('baseWorkerCount')) $('baseWorkerCount').value = Math.min(15, Math.max(1, Number(form.maxWorkers || 15)));
  updatePassiveOptions(false);
  renderPassives();
  setTargetValidity(canonicalMatch(state.species, $('target')?.value || '').value ? 'valid' : '');
  updateActiveForm();
}
function updateActiveForm() {
  saveCurrentForm();
  updateRouteName();
}

function modeLabel(mode) {
  if (mode === 'iv') return 'IV Improvement';
  if (mode === 'work') return 'Work Suitability';
  if (mode === 'ranch') return 'Ranch Drops';
  if (mode === 'base') return 'Base Planner';
  return 'Breeding Tree';
}

function updateHistoryNav() {
  const back = $('navBack');
  const forward = $('navForward');
  if (!back || !forward) return;
  const ranchDetail = state.mode === 'ranch' && Boolean(state.formsByMode.ranch?.ranchItem);
  const previousMode = state.modeBackStack[state.modeBackStack.length - 1];
  const nextMode = state.modeForwardStack[state.modeForwardStack.length - 1];
  back.disabled = !previousMode && !ranchDetail;
  forward.disabled = !nextMode;
  back.title = ranchDetail ? 'Back to ranch drops' : previousMode ? `Back to ${modeLabel(previousMode)}` : 'Back';
  forward.title = nextMode ? `Forward to ${modeLabel(nextMode)}` : 'Forward';
}

function rememberModeTransition(nextMode) {
  if (nextMode === state.mode) return;
  state.modeBackStack.push(state.mode);
  if (state.modeBackStack.length > 20) state.modeBackStack.shift();
  state.modeForwardStack = [];
}

function navigateModeHistory(direction) {
  if (direction === 'back' && state.mode === 'ranch' && state.formsByMode.ranch?.ranchItem) {
    state.formsByMode.ranch.ranchItem = '';
    if (state.plansByMode.ranch) renderRanchDrops(state.plansByMode.ranch);
    updateHistoryNav();
    updateRouteName();
    return;
  }
  const from = direction === 'back' ? state.modeBackStack : state.modeForwardStack;
  const to = direction === 'back' ? state.modeForwardStack : state.modeBackStack;
  const nextMode = from.pop();
  if (!nextMode) return;
  to.push(state.mode);
  setMode(nextMode, {recordHistory: false});
}

const WORK_SPEED_PROFILE_PASSIVES = [
  {name: 'Demon’s Hand', speed: 90, priority: 0},
  {name: 'Remarkable Craftsmanship', speed: 75, priority: 1},
  {name: 'Artisan', speed: 50, priority: 2},
  {name: 'Work Slave', speed: 30, priority: 3},
  {name: 'Lucky', speed: 20, priority: 4},
  {name: 'Serious', speed: 20, priority: 5},
  {name: 'Conceited', speed: 10, priority: 6},
];
const INSOMNIA_PASSIVE = 'Insomnia';
const RANCH_DROPS_PRIORITY_PASSIVES = ['Ranch Master', 'Farmhand'];
const CUSTOM_PROFILES_KEY = 'palworldBreeding.customProfiles.v1';
const BUILT_IN_PROFILE_NAMES_KEY = 'palworldBreeding.builtInProfileNames.v1';
const CONTROLS_WIDTH_KEY = 'palworldBreeding.controlsWidth.v1';
const MIN_CONTROLS_WIDTH = 320;
const MAX_CONTROLS_WIDTH = 720;
const BUILT_IN_PROFILE_OPTIONS = [
  {value: 'manual', label: 'Manual Passives'},
  {value: 'work_speed', label: 'Best Work Speed'},
  {value: 'ranch_drops_focus', label: 'Ranch Drops Focus'},
];

function isDarkType(types = []) {
  return (types || []).some(type => matchKey(type) === 'dark');
}

function profileOptionValue(profile) {
  return `custom:${profile.id}`;
}

function customProfileByValue(value) {
  if (!String(value || '').startsWith('custom:')) return null;
  const id = String(value).slice('custom:'.length);
  return state.customProfiles.find(profile => profile.id === id) || null;
}

function profileValueExists(value) {
  return BUILT_IN_PROFILE_OPTIONS.some(option => option.value === value) || Boolean(customProfileByValue(value));
}

function builtInProfileLabel(value) {
  const option = BUILT_IN_PROFILE_OPTIONS.find(item => item.value === value);
  return state.builtInProfileNames[value] || option?.label || 'Profile';
}

function isAutoProfile(value) {
  return ['work_speed', 'ranch_drops_focus'].includes(value);
}

function profilePriorityPassives(profile) {
  return profile === 'ranch_drops_focus' ? RANCH_DROPS_PRIORITY_PASSIVES : [];
}

function loadCustomProfiles() {
  try {
    const raw = localStorage.getItem(CUSTOM_PROFILES_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    state.customProfiles = Array.isArray(parsed)
      ? parsed.map(profile => ({
        id: String(profile.id || `${Date.now()}-${Math.random().toString(16).slice(2)}`),
        name: String(profile.name || 'Custom Profile'),
        passives: [...new Set(profile.passives || [])].filter(Boolean).slice(0, 4),
      }))
      : [];
  } catch {
    state.customProfiles = [];
  }
}

function persistCustomProfiles() {
  localStorage.setItem(CUSTOM_PROFILES_KEY, JSON.stringify(state.customProfiles));
}

function loadBuiltInProfileNames() {
  try {
    const parsed = JSON.parse(localStorage.getItem(BUILT_IN_PROFILE_NAMES_KEY) || '{}');
    state.builtInProfileNames = Object.fromEntries(
      Object.entries(parsed)
        .filter(([value, name]) => BUILT_IN_PROFILE_OPTIONS.some(option => option.value === value && value !== 'manual') && String(name || '').trim())
        .map(([value, name]) => [value, String(name).trim().slice(0, 60)])
    );
  } catch {
    state.builtInProfileNames = {};
  }
}

function persistBuiltInProfileNames() {
  localStorage.setItem(BUILT_IN_PROFILE_NAMES_KEY, JSON.stringify(state.builtInProfileNames));
}

function profileOptionItems() {
  return [
    ...BUILT_IN_PROFILE_OPTIONS.map(option => ({...option, label: builtInProfileLabel(option.value)})),
    ...state.customProfiles.map(profile => ({value: profileOptionValue(profile), label: profile.name})),
  ];
}

function renderProfileOptions(selected = $('breedingProfile')?.value || 'manual') {
  const select = $('breedingProfile');
  if (!select) return;
  select.innerHTML = profileOptionItems()
    .map(option => `<option value="${escapeHtml(option.value)}">${escapeHtml(option.label)}</option>`)
    .join('');
  select.value = profileValueExists(selected) ? selected : 'manual';
  updateProfileToolbar();
}

function setProfileDropdownOpen(open) {
  const wrap = document.querySelector('.profile-select-wrap');
  const button = $('profileDropdownButton');
  const menu = $('profileDropdownMenu');
  if (!wrap || !button) return;
  wrap.classList.toggle('open', open);
  menu?.classList.toggle('hidden', !open);
  button.setAttribute('aria-expanded', open ? 'true' : 'false');
  if (open) {
    syncProfileDropdown();
    const selected = menu?.querySelector('.profile-dropdown-option.selected');
    selected?.focus();
  }
}

function syncProfileDropdown() {
  const select = $('breedingProfile');
  const label = $('profileDropdownLabel');
  const menu = $('profileDropdownMenu');
  if (!select || !label || !menu) return;
  const value = select.value || 'manual';
  const options = profileOptionItems();
  const selected = options.find(option => option.value === value) || options[0];
  label.textContent = selected?.label || 'Manual Passives';
  menu.innerHTML = options.map(option => `
    <button
      class="profile-dropdown-option${option.value === value ? ' selected' : ''}"
      type="button"
      role="option"
      aria-selected="${option.value === value ? 'true' : 'false'}"
      data-profile-value="${escapeHtml(option.value)}"
    >${escapeHtml(option.label)}</button>
  `).join('');
  menu.querySelectorAll('.profile-dropdown-option').forEach(optionButton => {
    optionButton.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      const nextValue = optionButton.getAttribute('data-profile-value') || 'manual';
      if (select.value !== nextValue) {
        select.value = nextValue;
        select.dispatchEvent(new Event('change', {bubbles: true}));
      } else {
        syncProfileDropdown();
      }
      setProfileDropdownOpen(false);
      $('profileDropdownButton')?.focus();
    });
  });
}

function updateProfileToolbar() {
  const button = $('editProfile');
  const value = $('breedingProfile')?.value || '';
  if (button) button.disabled = !(customProfileByValue(value) || (isAutoProfile(value) && builtInProfileLabel(value)));
  syncProfileDropdown();
}

function bestAvailableWorkSpeedPassives(owner = $('owner')?.value || 'David', options = {}) {
  const available = new Set(state.passivesByOwner[owner] || []);
  const useInsomnia = options.includeInsomnia && available.has(INSOMNIA_PASSIVE) && !isDarkType(options.targetTypes);
  const priorityPassives = [...new Set(options.priorityPassives || [])];
  const forced = priorityPassives
    .filter(passive => available.has(passive))
    .slice(0, useInsomnia ? 3 : 4);
  const selected = WORK_SPEED_PROFILE_PASSIVES
    .filter(passive => available.has(passive.name))
    .filter(passive => !forced.includes(passive.name))
    .sort((a, b) => b.speed - a.speed || a.priority - b.priority)
    .slice(0, Math.max(0, (useInsomnia ? 3 : 4) - forced.length))
    .map(passive => passive.name);
  selected.unshift(...forced);
  if (useInsomnia) {
    selected.push(INSOMNIA_PASSIVE);
  }
  return selected;
}

function activeTargetTypes() {
  return speciesTypes(canonicalMatch(state.species, $('target')?.value || '').value || $('target')?.value || '');
}

function updateInsomniaAvailability() {
  const darkTarget = state.mode === 'breed' && isDarkType(activeTargetTypes());
  for (const id of ['workIncludeInsomnia', 'ranchIncludeInsomnia']) {
    const input = $(id);
    if (!input) continue;
    input.disabled = darkTarget;
    input.closest('.night-work-option')?.classList.toggle('disabled', darkTarget);
    if (darkTarget) input.checked = false;
  }
}

async function reachableProfilePassives(profile, owner, options = {}) {
  const target = options.target || canonicalMatch(state.species, $('target')?.value || '').value || $('target')?.value || '';
  if (!target || !isAutoProfile(profile)) return null;
  return api('/api/profile-passives', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      owner,
      target,
      breedingProfile: profile,
      includeInsomnia: Boolean(options.includeInsomnia),
      genderPreference: $('genderPreference')?.value || 'any',
    }),
  });
}

async function applyBreedingProfile(profile = $('breedingProfile')?.value || 'manual', owner = $('owner')?.value || 'David', options = {}) {
  const custom = customProfileByValue(profile);
  if (custom) {
    state.selectedPassives = [...custom.passives];
    state.selectedImplantPassives = state.selectedImplantPassives.filter(passive => state.selectedPassives.includes(passive));
    renderPassives();
    updateActiveForm();
    setStatus($('passiveHint'), `Profile "${custom.name}" applied: ${custom.passives.join(', ') || 'no passives'}.`, 'good');
    return custom.passives.length > 0;
  }
  if (!isAutoProfile(profile)) return false;
  const includeInsomnia = Object.hasOwn(options, 'includeInsomnia')
    ? Boolean(options.includeInsomnia)
    : Boolean($('workIncludeInsomnia')?.checked || state.formsByMode[state.mode]?.workIncludeInsomnia);
  const priorityPassives = profilePriorityPassives(profile);
  let passives = null;
  const targetTypes = options.targetTypes || activeTargetTypes();
  const target = options.target || canonicalMatch(state.species, $('target')?.value || '').value || $('target')?.value || '';
  if (target) {
    try {
      const profileData = await reachableProfilePassives(profile, owner, {target, includeInsomnia, targetTypes});
      passives = profileData?.selected || [];
    } catch {
      passives = null;
    }
  }
  if (!passives) {
    passives = bestAvailableWorkSpeedPassives(owner, {includeInsomnia, targetTypes, priorityPassives});
  }
  state.selectedPassives = passives;
  state.selectedImplantPassives = state.selectedImplantPassives.filter(passive => state.selectedPassives.includes(passive));
  renderPassives();
  updateActiveForm();
  const profileName = builtInProfileLabel(profile);
  const missingPriorityPassives = priorityPassives.filter(passive => !passives.includes(passive));
  const missingPriority = missingPriorityPassives.length > 0;
  setStatus($('passiveHint'), passives.length
    ? `${profileName} profile: ${passives.join(', ')}.${missingPriority ? ` Missing priority passive${missingPriorityPassives.length === 1 ? '' : 's'}: ${missingPriorityPassives.join(', ')}.` : ''}`
    : 'No matching profile passives are currently available for this owner.', missingPriority ? 'warn' : passives.length ? 'good' : 'warn');
  return passives.length > 0;
}

function respectManualPassiveEdit() {
  const current = $('breedingProfile')?.value || 'manual';
  if (!['breed', 'iv'].includes(state.mode) || current === 'manual') return;
  $('breedingProfile').value = 'manual';
  updateProfileToolbar();
  setStatus($('passiveHint'), 'Switched to manual selection to preserve your passive changes.', 'working');
}

async function goToBreedingFor(card) {
  if (!card?.name) return;
  if (card.requiresOwnedSeed && !card.ownedCount) {
    showToast(`${card.name} needs an owned copy before breeding routes can work.`, 'warn');
  }
  const owner = $('owner')?.value || 'David';
  const includeInsomnia = (state.mode === 'work' && Boolean($('workIncludeInsomnia')?.checked))
    || (state.mode === 'ranch' && Boolean($('ranchIncludeInsomnia')?.checked));
  const dark = isDarkType(card.types || []);
  let breedingProfile = state.mode === 'ranch' ? 'ranch_drops_focus' : 'work_speed';
  let passives = bestAvailableWorkSpeedPassives(owner, {
    includeInsomnia: includeInsomnia && !dark,
    targetTypes: card.types || [],
    priorityPassives: profilePriorityPassives(breedingProfile),
  });
  try {
    const profileData = await reachableProfilePassives(breedingProfile, owner, {
      target: card.name,
      includeInsomnia: includeInsomnia && !dark,
      targetTypes: card.types || [],
    });
    if (profileData?.selected?.length) passives = profileData.selected;
  } catch {
    // Keep the local availability-based fallback if the route-aware profile lookup fails.
  }
  if (includeInsomnia) {
    if (dark) {
      showToast(`${card.name} is dark type, so Insomnia is not needed.`, 'warn');
    } else if (!passives.includes(INSOMNIA_PASSIVE)) {
      showToast(`No owned ${INSOMNIA_PASSIVE} passive found for ${owner}.`, 'warn');
    }
  }
  state.formsByMode.breed = {
    ...state.formsByMode.breed,
    owner,
    target: card.name,
    passives,
    breedingProfile,
    workIncludeInsomnia: includeInsomnia && !dark,
    genderPreference: 'any',
  };
  setMode('breed');
  applyFormToUi(state.formsByMode.breed);
  if (!includeInsomnia || !dark) showToast(`Breeding target set to ${card.name}.`, 'good');
}

function setControlsCollapsed(collapsed) {
  const layout = document.querySelector('.layout');
  if (!layout) return;
  layout.classList.toggle('controls-collapsed', collapsed);
}

function toggleControlsPanel() {
  const layout = document.querySelector('.layout');
  setControlsCollapsed(!layout?.classList.contains('controls-collapsed'));
}

function clampControlsWidth(value) {
  return Math.min(MAX_CONTROLS_WIDTH, Math.max(MIN_CONTROLS_WIDTH, Number(value) || 430));
}

function setControlsWidth(value, persist = true) {
  const layout = document.querySelector('.layout');
  if (!layout) return;
  const width = clampControlsWidth(value);
  layout.style.setProperty('--controls-width', `${width}px`);
  if (persist) localStorage.setItem(CONTROLS_WIDTH_KEY, String(width));
}

function restoreControlsWidth() {
  const saved = Number(localStorage.getItem(CONTROLS_WIDTH_KEY) || 430);
  setControlsWidth(saved, false);
}

function initControlsResize() {
  const handle = $('controlsResizeHandle');
  const layout = document.querySelector('.layout');
  if (!handle || !layout) return;
  handle.addEventListener('pointerdown', event => {
    if (window.matchMedia('(max-width: 820px)').matches) return;
    event.preventDefault();
    handle.setPointerCapture(event.pointerId);
    handle.classList.add('dragging');
    document.body.classList.add('resizing-controls');
    const onMove = moveEvent => {
      const rect = layout.getBoundingClientRect();
      setControlsWidth(moveEvent.clientX - rect.left);
    };
    const onUp = upEvent => {
      handle.releasePointerCapture(upEvent.pointerId);
      handle.classList.remove('dragging');
      document.body.classList.remove('resizing-controls');
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp, {once: true});
  });
}

async function api(path, options) {
  const res = await fetch(apiUrl(path), options);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

function updatePassiveOptions(showRemoval = true) {
  const owner = $('owner').value;
  state.passives = state.passivesByOwner[owner] || state.passives || [];
  fillDatalist('passiveList', state.passives);
  const available = new Set(state.passives);
  const before = state.selectedPassives.length;
  state.selectedPassives = state.selectedPassives.filter(passive => available.has(passive));
  if (state.selectedPassives.length !== before) {
    if (showRemoval) setStatus($('passiveHint'), 'Removed selected passives that are not present for this owner.', 'warn');
    renderPassives();
  }
}
function fillDatalist(id, values) {
  const el = $(id);
  el.innerHTML = values.map(v => `<option value="${escapeHtml(v)}"></option>`).join('');
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
}

function passiveTooltipLines(passive, extraLines = []) {
  const meta = state.passiveMeta[passive] || {};
  const desc = String(meta.desc || '').trim();
  const effectLines = desc
    ? desc.split(/\s*,\s*/).map(line => line.replace(/\s*\(ToSelf\)\s*/g, '').trim()).filter(Boolean)
    : [];
  return [passive, ...effectLines, ...extraLines.filter(Boolean)];
}

function passiveTooltipAttrs(passive, tone = passiveTone(passive), extraLines = []) {
  return `data-passive-tooltip="${escapeHtml(JSON.stringify(passiveTooltipLines(passive, extraLines)))}" data-passive-tone="${escapeHtml(tone)}"`;
}

function applyPassiveTooltip(el, passive, tone = passiveTone(passive), extraLines = []) {
  el.dataset.passiveTooltip = JSON.stringify(passiveTooltipLines(passive, extraLines));
  el.dataset.passiveTone = tone;
}

function tooltipClassForTone(tone) {
  return ['positive', 'gold', 'negative', 'neutral'].includes(tone) ? tone : 'positive';
}

function renderPassiveTooltipContent(tooltip, lines, tone) {
  tooltip.className = `passive-tooltip ${tooltipClassForTone(tone)}`;
  tooltip.innerHTML = '';
  const title = document.createElement('strong');
  title.textContent = lines[0] || '';
  tooltip.appendChild(title);
  for (const line of lines.slice(1)) {
    const row = document.createElement('span');
    row.innerHTML = escapeHtml(line).replace(/([+-]\d+(?:\.\d+)?%)/g, '<em>$1</em>');
    tooltip.appendChild(row);
  }
}

function positionPassiveTooltip(tooltip, anchor) {
  const rect = anchor.getBoundingClientRect();
  const margin = 10;
  const tooltipRect = tooltip.getBoundingClientRect();
  let left = rect.left + rect.width / 2 - tooltipRect.width / 2;
  left = Math.max(margin, Math.min(left, window.innerWidth - tooltipRect.width - margin));
  let top = rect.bottom + 8;
  if (top + tooltipRect.height + margin > window.innerHeight) {
    top = rect.top - tooltipRect.height - 8;
  }
  tooltip.style.left = `${Math.round(left)}px`;
  tooltip.style.top = `${Math.round(Math.max(margin, top))}px`;
}

function showPassiveTooltip(anchor) {
  const raw = anchor?.dataset?.passiveTooltip;
  if (!raw) return;
  let lines = [];
  try {
    lines = JSON.parse(raw);
  } catch {
    lines = raw.split('\n');
  }
  lines = Array.isArray(lines) ? lines.filter(Boolean) : [];
  if (!lines.length) return;
  let tooltip = document.querySelector('.passive-tooltip');
  if (!tooltip) {
    tooltip = document.createElement('div');
    tooltip.setAttribute('role', 'tooltip');
    document.body.appendChild(tooltip);
  }
  renderPassiveTooltipContent(tooltip, lines, anchor.dataset.passiveTone);
  tooltip.classList.add('visible');
  positionPassiveTooltip(tooltip, anchor);
}

function hidePassiveTooltip() {
  document.querySelector('.passive-tooltip')?.classList.remove('visible');
}

function sortedPassivesForDisplay(passives = []) {
  const toneOrder = {positive: 0, gold: 1, neutral: 2, negative: 3};
  return [...passives].sort((a, b) => {
    const toneA = passiveTone(a);
    const toneB = passiveTone(b);
    return (toneOrder[toneA] ?? 2) - (toneOrder[toneB] ?? 2) || a.localeCompare(b);
  });
}

function renderPassives() {
  const wrap = $('selectedPassives');
  wrap.innerHTML = '';
  for (const passive of sortedPassivesForDisplay(state.selectedPassives)) {
    const implantPlanned = state.mode === 'iv' && $('includeImplants')?.checked && state.selectedImplantPassives.includes(passive);
    const chip = document.createElement('span');
    const tone = passiveTone(passive);
    chip.className = `chip ${tone}${implantPlanned ? ' implant-chip' : ''}`;
    applyPassiveTooltip(chip, passive, tone, state.mode === 'iv' ? ['Click to plan implant use.'] : []);
    if (state.mode === 'iv') {
      chip.type = 'button';
      chip.onclick = () => openImplantPlanner(passive);
    }
    const name = document.createElement('span');
    name.className = 'chip-name';
    name.textContent = implantPlanned ? `${passive} · Implant` : passive;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'chip-remove';
    btn.innerHTML = '<span aria-hidden="true">&times;</span>';
    btn.setAttribute('aria-label', `Remove ${passive}`);
    btn.title = `Remove ${passive}`;
    btn.onclick = event => {
      event.stopPropagation();
      respectManualPassiveEdit();
      state.selectedPassives = state.selectedPassives.filter(p => p !== passive);
      state.selectedImplantPassives = state.selectedImplantPassives.filter(p => p !== passive);
      renderPassives();
      updateActiveForm();
    };
    chip.append(name, btn);
    wrap.appendChild(chip);
  }
}

function implantRecord(passive) {
  return state.implantInventory?.[passive] || {infinite: false, count: 0};
}

function implantLabel(passive) {
  const record = implantRecord(passive);
  return record.infinite ? 'infinite' : `${Number(record.count || 0)} owned`;
}

async function saveImplantInventoryEntry(passive, infinite, count) {
  const data = await api('/api/implant-inventory', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({passive, infinite, count})
  });
  state.implantInventory = data.inventory || {};
  return data;
}

function setImplantPlanned(passive, planned) {
  const selected = new Set(state.selectedImplantPassives);
  if (planned) selected.add(passive);
  else selected.delete(passive);
  state.selectedImplantPassives = [...selected].filter(name => state.selectedPassives.includes(name));
  renderPassives();
  renderImplantPlanner();
  updateActiveForm();
}

function renderImplantPlanner(focusPassive = '') {
  const list = $('implantGoalList');
  if (!list) return;
  if (!state.selectedPassives.length) {
    list.innerHTML = '<div class="empty compact-empty">Choose target passives first.</div>';
    return;
  }
  list.innerHTML = sortedPassivesForDisplay(state.selectedPassives).map(passive => {
    const planned = state.selectedImplantPassives.includes(passive);
    const record = implantRecord(passive);
    return `
      <div class="implant-goal-row ${passive === focusPassive ? 'focused' : ''}" data-implant-passive="${escapeHtml(passive)}">
        <strong>${escapeHtml(passive)}</strong>
        <label class="inline-check"><input type="checkbox" data-implant-use ${planned ? 'checked' : ''}> Use implant</label>
        <label class="inline-check"><input type="checkbox" data-implant-infinite ${record.infinite ? 'checked' : ''}> Infinite</label>
        <input type="number" min="0" value="${escapeHtml(record.infinite ? 1 : record.count || 0)}" data-implant-count aria-label="${escapeHtml(passive)} implant count" ${record.infinite ? 'disabled' : ''}>
      </div>`;
  }).join('');
  list.querySelectorAll('[data-implant-passive]').forEach(row => {
    const passive = row.dataset.implantPassive || '';
    const useInput = row.querySelector('[data-implant-use]');
    const infiniteInput = row.querySelector('[data-implant-infinite]');
    const countInput = row.querySelector('[data-implant-count]');
    const saveRow = async () => {
      countInput.disabled = infiniteInput.checked;
      await saveImplantInventoryEntry(passive, infiniteInput.checked, countInput.value);
      setImplantPlanned(passive, useInput.checked);
      setStatus($('implantStatus'), `${passive} implant settings saved.`, 'good');
    };
    useInput.addEventListener('change', () => saveRow().catch(err => setStatus($('implantStatus'), err.message, 'bad')));
    infiniteInput.addEventListener('change', () => saveRow().catch(err => setStatus($('implantStatus'), err.message, 'bad')));
    countInput.addEventListener('change', () => saveRow().catch(err => setStatus($('implantStatus'), err.message, 'bad')));
  });
}

function openImplantPlanner(focusPassive = '') {
  if (state.mode !== 'iv') return;
  if ($('includeImplants')) $('includeImplants').checked = true;
  renderImplantPlanner(focusPassive);
  $('implantModal')?.classList.remove('hidden');
}

function closeImplantPlanner() {
  $('implantModal')?.classList.add('hidden');
}

async function saveFreeformImplant() {
  const input = $('implantPassiveInput');
  const match = canonicalMatch(state.passives, input.value || '');
  if (!match.value) {
    setStatus($('implantStatus'), match.reason === 'ambiguous' ? `Matches: ${match.matches.join(', ')}. Keep typing.` : 'Choose a known passive.', 'warn');
    return;
  }
  await saveImplantInventoryEntry(match.value, $('implantInfinite')?.checked, $('implantCount')?.value || 0);
  input.value = '';
  if (state.selectedPassives.includes(match.value)) {
    setImplantPlanned(match.value, true);
  } else {
    renderImplantPlanner();
  }
  setStatus($('implantStatus'), `${match.value} saved to implant inventory.`, 'good');
}

function renderProfileEditorPassives() {
  const wrap = $('profilePassives');
  if (!wrap) return;
  wrap.innerHTML = '';
  for (const passive of state.editingProfilePassives) {
    const chip = document.createElement('span');
    const tone = passiveTone(passive);
    chip.className = `chip ${tone}`;
    applyPassiveTooltip(chip, passive, tone);
    const name = document.createElement('span');
    name.className = 'chip-name';
    name.textContent = passive;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'chip-remove';
    btn.innerHTML = '<span aria-hidden="true">&times;</span>';
    btn.setAttribute('aria-label', `Remove ${passive}`);
    btn.title = `Remove ${passive}`;
    btn.onclick = () => {
      state.editingProfilePassives = state.editingProfilePassives.filter(item => item !== passive);
      renderProfileEditorPassives();
    };
    chip.append(name, btn);
    wrap.appendChild(chip);
  }
}

function closeProfileEditor() {
  $('profileModal')?.classList.add('hidden');
  state.editingProfileId = '';
  state.editingBuiltInProfileValue = '';
  state.editingProfilePassives = [];
}

function openProfileEditor(profile = null) {
  const modal = $('profileModal');
  if (!modal) return;
  const selectedValue = $('breedingProfile')?.value || '';
  const builtInValue = profile ? '' : isAutoProfile(selectedValue) ? selectedValue : '';
  const current = profile || customProfileByValue(selectedValue);
  const builtIn = builtInValue ? BUILT_IN_PROFILE_OPTIONS.find(option => option.value === builtInValue) : null;
  const locked = Boolean(builtIn);
  state.editingProfileId = current?.id || '';
  state.editingBuiltInProfileValue = builtInValue;
  state.editingProfilePassives = current ? [...current.passives] : [];
  if (!current && !builtIn) state.editingProfilePassives = [...state.selectedPassives].slice(0, 4);
  $('profileEditorTitle').textContent = current || builtIn ? 'Edit Profile' : 'Add Profile';
  $('profileName').value = current?.name || (builtIn ? builtInProfileLabel(builtInValue) : '');
  $('profilePassiveInput').value = '';
  $('profilePassiveInput').disabled = locked;
  $('addProfilePassive').disabled = locked;
  $('useCurrentPassives').disabled = locked;
  for (const id of ['profilePassiveInput', 'addProfilePassive', 'useCurrentPassives']) {
    $(id)?.setAttribute('title', locked ? 'This built-in profile has fixed passive logic. Only its display name can be changed.' : '');
  }
  $('deleteProfile').classList.toggle('hidden', !current);
  $('profileLockedNotice')?.classList.toggle('hidden', !locked);
  renderProfileEditorPassives();
  setStatus(
    $('profileStatus'),
    locked
      ? 'Built-in profile logic is hardcoded. Rename only.'
      : current ? 'Edit this profile or update its passives.' : 'Add up to 4 passives, then save.',
    locked ? 'warn' : undefined
  );
  modal.classList.remove('hidden');
  $('profileName').focus();
}

function addProfilePassive() {
  const input = $('profilePassiveInput');
  const match = canonicalMatch(state.passives, input.value);
  if (!match.value) {
    const detail = match.reason === 'ambiguous'
      ? `More than one match: ${match.matches.join(', ')}.`
      : 'No known passive matches that text.';
    setStatus($('profileStatus'), detail, match.reason === 'ambiguous' ? 'warn' : 'bad');
    return;
  }
  if (state.editingProfilePassives.includes(match.value)) {
    setStatus($('profileStatus'), `${match.value} is already in this profile.`, 'warn');
    return;
  }
  if (state.editingProfilePassives.length >= 4) {
    setStatus($('profileStatus'), 'A profile can use up to 4 passives.', 'warn');
    return;
  }
  state.editingProfilePassives.push(match.value);
  input.value = '';
  renderProfileEditorPassives();
  setStatus($('profileStatus'), `Added ${match.value}.`, 'good');
}

function saveProfile() {
  const name = ($('profileName')?.value || '').trim();
  if (!name) {
    setStatus($('profileStatus'), 'Name this profile before saving.', 'warn');
    return;
  }
  if (state.editingBuiltInProfileValue) {
    state.builtInProfileNames[state.editingBuiltInProfileValue] = name.slice(0, 60);
    persistBuiltInProfileNames();
    renderProfileOptions(state.editingBuiltInProfileValue);
    updateActiveForm();
    closeProfileEditor();
    setStatus($('passiveHint'), `Profile renamed to "${name}".`, 'good');
    return;
  }
  const passives = [...new Set(state.editingProfilePassives)].slice(0, 4);
  if (!passives.length) {
    setStatus($('profileStatus'), 'Add at least one passive before saving.', 'warn');
    return;
  }
  let profile = state.customProfiles.find(item => item.id === state.editingProfileId);
  if (profile) {
    profile.name = name;
    profile.passives = passives;
  } else {
    profile = {id: `${Date.now()}-${Math.random().toString(16).slice(2)}`, name, passives};
    state.customProfiles.push(profile);
  }
  persistCustomProfiles();
  renderProfileOptions(profileOptionValue(profile));
  state.selectedPassives = [...passives];
  renderPassives();
  updateActiveForm();
  closeProfileEditor();
  setStatus($('passiveHint'), `Profile "${name}" applied.`, 'good');
}

function deleteProfile() {
  const profile = state.customProfiles.find(item => item.id === state.editingProfileId);
  if (!profile) return;
  state.customProfiles = state.customProfiles.filter(item => item.id !== profile.id);
  persistCustomProfiles();
  renderProfileOptions('manual');
  $('breedingProfile').value = 'manual';
  closeProfileEditor();
  updateActiveForm();
  setStatus($('passiveHint'), `Deleted profile "${profile.name}".`, 'good');
}

function matchKey(value) {
  return String(value || '').trim().toLowerCase().replace(/[\s_-]+/g, ' ');
}

function canonicalMatch(values, query) {
  const q = query.trim().toLowerCase();
  const qKey = matchKey(query);
  if (!q) return {value: '', reason: 'empty'};
  const exact = values.find(v => v.toLowerCase() === q || matchKey(v) === qKey);
  if (exact) return {value: exact};
  const starts = values.filter(v => v.toLowerCase().startsWith(q) || matchKey(v).startsWith(qKey));
  if (starts.length === 1) return {value: starts[0]};
  if (starts.length > 1) return {value: '', reason: 'ambiguous', matches: starts.slice(0, 5)};
  const contains = values.filter(v => v.toLowerCase().includes(q) || matchKey(v).includes(qKey));
  if (contains.length === 1) return {value: contains[0]};
  if (contains.length > 1) return {value: '', reason: 'ambiguous', matches: contains.slice(0, 5)};
  return {value: '', reason: 'unknown'};
}

function exactCanonicalMatch(values, query) {
  const q = query.trim().toLowerCase();
  const qKey = matchKey(query);
  if (!q) return '';
  return values.find(v => v.toLowerCase() === q || matchKey(v) === qKey) || '';
}

function exactTargetFromField() {
  const raw = $('target')?.value || '';
  return /\s$/.test(raw) ? '' : exactCanonicalMatch(state.species, raw);
}

function clearIvTargetChoices(message = 'Choose a species first, then select the exact owned Pal.') {
  state.ivTargetLoadSeq += 1;
  state.ivTargetPals = [];
  if ($('ivTargetInstance')) $('ivTargetInstance').innerHTML = '';
  renderIvSelectedTarget();
  renderIvTargetPicker();
  if ($('ivTargetHint')) setStatus($('ivTargetHint'), message, 'warn');
}

function setTargetValidity(kind = '') {
  const wrap = document.querySelector('.target-input-wrap');
  if (!wrap) return;
  wrap.classList.toggle('valid', kind === 'valid');
  wrap.classList.toggle('invalid', kind === 'invalid');
}

function selectedTargetTypes() {
  const target = $('target')?.value || '';
  const match = canonicalMatch(state.species, target);
  return match.value ? speciesTypes(match.value) : [];
}

function warnIfInsomniaOnDarkTarget(passives = state.selectedPassives) {
  if (!passives.includes(INSOMNIA_PASSIVE) || !isDarkType(selectedTargetTypes())) return false;
  const target = canonicalMatch(state.species, $('target')?.value || '').value || 'this dark Pal';
  setStatus($('passiveHint'), `${target} is dark type, so ${INSOMNIA_PASSIVE} is not needed for night uptime.`, 'warn');
  return true;
}

function resolveTarget() {
  const input = $('target');
  const hint = $('targetHint');
  const match = canonicalMatch(state.species, input.value);
  if (!match.value) {
    const detail = match.reason === 'ambiguous'
      ? `More than one Pal matches: ${match.matches.join(', ')}. Keep typing.`
      : 'No known Pal matches that text.';
    setStatus(hint, detail, match.reason === 'ambiguous' ? 'warn' : 'bad');
    setTargetValidity(match.reason === 'empty' ? '' : 'invalid');
    return '';
  }
  input.value = match.value;
  setStatus(hint, '');
  setTargetValidity('valid');
  updateActiveForm();
  updateInsomniaAvailability();
  warnIfInsomniaOnDarkTarget();
  return match.value;
}
function addPassive() {
  const input = $('passiveInput');
  const hint = $('passiveHint');
  const match = canonicalMatch(state.passives, input.value);
  if (!match.value) {
    const detail = match.reason === 'ambiguous'
      ? `More than one match: ${match.matches.join(', ')}.`
      : 'No known passive matches that text.';
    setStatus(hint, detail, match.reason === 'ambiguous' ? 'warn' : 'bad');
    return;
  }
  if (state.selectedPassives.includes(match.value)) {
    setStatus(hint, `${match.value} is already selected.`, 'warn');
    input.value = match.value;
    return;
  }
  if (state.selectedPassives.length >= 4) {
    setStatus(hint, 'A build can use up to 4 desired passives.', 'warn');
    return;
  }
  respectManualPassiveEdit();
  state.selectedPassives.push(match.value);
  input.value = '';
  if (match.value === INSOMNIA_PASSIVE && warnIfInsomniaOnDarkTarget()) {
    showToast(`${INSOMNIA_PASSIVE} is not needed on dark Pals.`, 'warn');
  } else {
    setStatus(hint, `Added ${match.value}.`, 'good');
  }
  renderPassives();
  updateActiveForm();
}

function speciesInitials(name) {
  return (name || '?')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map(part => part[0].toUpperCase())
    .join('') || '?';
}

function typeClass(type) {
  return `type-${matchKey(type).replace(/\s+/g, '-')}`;
}

function inlineIcon(kind) {
  const icons = {
    neutral: '<circle cx="12" cy="12" r="6"></circle><circle cx="12" cy="12" r="2.2"></circle>',
    fire: '<path d="M13 2 C17 7 9 8 15 13 C17 15 16 20 12 21 C8 20 6 17 8 13 C9 10 13 8 13 2 Z"></path>',
    water: '<path d="M12 2 C17 8 19 12 19 16 C19 20 16 22 12 22 C8 22 5 20 5 16 C5 12 7 8 12 2 Z"></path>',
    grass: '<path d="M4 14 C5 7 12 3 20 4 C19 12 15 19 8 20 C9 16 13 12 17 8 C12 10 8 12 4 14 Z"></path>',
    electric: '<path d="M13 1 L4 14 H11 L9 23 L20 9 H13 Z"></path>',
    ice: '<path d="M12 2 V22 M4 6 L20 18 M20 6 L4 18 M7 4 L12 7 L17 4 M7 20 L12 17 L17 20"></path>',
    ground: '<path d="M3 19 L8 8 L12 14 L16 5 L21 19 Z"></path>',
    dark: '<path d="M17 3 C11 4 7 8 7 13 C7 17 10 20 14 21 C8 22 3 18 3 12 C3 6 9 1 17 3 Z"></path>',
    dragon: '<path d="M5 18 C8 9 13 5 20 4 C17 7 18 10 21 12 C15 12 13 16 14 21 C11 17 8 17 5 18 Z"></path>',
    kindling: '<path d="M13 2 C16 6 10 8 15 12 C18 15 16 21 12 22 C8 21 6 18 8 14 C9 11 13 9 13 2 Z"></path>',
    watering: '<path d="M4 13 C7 9 10 14 13 10 C15 8 18 8 21 11 M5 17 C8 13 11 18 14 14 C16 12 18 12 21 15"></path>',
    planting: '<path d="M12 21 V10 M12 13 C8 13 5 10 5 6 C9 6 12 8 12 13 Z M12 11 C16 11 19 8 19 4 C15 4 12 7 12 11 Z"></path>',
    handiwork: '<path d="M8 21 V10 M8 10 L5 13 M8 10 L11 13 M12 20 V8 M12 8 L9 11 M12 8 L15 11 M16 19 V7 M16 7 L13 10 M16 7 L19 10"></path>',
    gathering: '<path d="M12 3 V21 M7 7 L12 3 L17 7 M7 12 L12 8 L17 12 M7 17 L12 13 L17 17"></path>',
    mining: '<path d="M14 4 L20 10 M18 8 L9 21 L5 17 L18 8 Z M4 6 L8 2 L12 6 L8 10 Z"></path>',
    farming: '<path d="M6 5 H8 V20 M12 5 H14 V20 M18 5 H20 V20 M4 10 H22 M4 15 H22"></path>',
    lumbering: '<path d="M5 19 H19 M8 19 V10 C8 7 10 5 12 5 C14 5 16 7 16 10 V19 M7 12 H17"></path>',
    medicine: '<path d="M9 5 H15 L18 11 L12 21 L6 11 Z M8 11 H16 M12 7 V17"></path>',
    cooling: '<path d="M12 2 V22 M4 6 L20 18 M20 6 L4 18 M7 4 L12 7 L17 4 M7 20 L12 17 L17 20"></path>',
    transporting: '<path d="M3 7 H14 V17 H3 Z M14 10 H19 L22 13 V17 H14 Z M7 20 A2 2 0 1 0 7 16 A2 2 0 0 0 7 20 Z M18 20 A2 2 0 1 0 18 16 A2 2 0 0 0 18 20 Z"></path>',
  };
  const body = icons[kind] || icons.neutral;
  return `<svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true">${body}</svg>`;
}

function typeIcon(type) {
  return inlineIcon(matchKey(type));
}

function renderTypeChips(types = []) {
  const clean = (types || []).filter(Boolean);
  if (!clean.length) return '';
  return `<div class="type-row">${clean.map(type => `
    <span class="type-chip ${typeClass(type)}" title="${escapeHtml(type)} type">
      <span class="type-mark">${typeIcon(type)}</span>
      <span>${escapeHtml(type)}</span>
    </span>
  `).join('')}</div>`;
}

function speciesTypes(name) {
  return state.speciesMeta[name]?.types || [];
}

function genderLabel(node) {
  const value = node.displayGender || node.gender || '';
  if (value === 'Male') return {symbol: '♂', text: 'Male', className: 'male'};
  if (value === 'Female') return {symbol: '♀', text: 'Female', className: 'female'};
  if (value === 'Either') return {symbol: '', text: 'Any gender', className: ''};
  return {symbol: '', text: value || '', className: ''};
}

function locationText(node) {
  if (node.box) return `Box ${node.box}, slot ${node.slot}`;
  if (node.location === 'bred intermediate') return 'Bred intermediate';
  if (node.location === 'final parent route') return 'Final breed';
  const location = node.location || '';
  const baseSlot = node.baseSlot ?? node.base_slot;
  if (baseSlot != null && location && !/\bslot\s+\d+\b/i.test(location)) {
    return `${location}, slot ${baseSlot}`;
  }
  return location;
}

function breedLabel(count) {
  const value = Number(count || 0);
  return `${value} egg${value === 1 ? '' : 's'}`;
}

function cakeLabel(count, type = 'Cake') {
  const value = Number(count || 0);
  const cakeType = type || 'Cake';
  return `${cakeType} x${value}`;
}

function generationLabel(steps) {
  const value = Number(steps || 0);
  return `${value} generation${value === 1 ? '' : 's'}`;
}

function nodeRole(node, isRoot) {
  if (isRoot) return 'FINAL EGG';
  if (node.parents?.length) return 'BREED FIRST';
  return 'OWNED';
}

function isBredNode(node, isRoot) {
  return isRoot || Boolean(node.parents?.length);
}

function displayPassives(node, isRoot) {
  return isBredNode(node, isRoot) ? node.desired : node.passives;
}

function displayJunk(node, isRoot) {
  return isBredNode(node, isRoot) ? [] : node.junk;
}

function isJunkPassive(passive, node, isRoot = false) {
  return displayJunk(node, isRoot).includes(passive);
}

function passiveTone(passive, node, isRoot = false) {
  return state.passiveMeta[passive]?.tone || 'neutral';
}

function passiveArrows(tone) {
  if (tone === 'negative') return '▼';
  if (tone === 'gold') return '▲▲▲';
  if (tone === 'positive') return '▲▲▲+';
  return '▲';
}
function renderPassiveBars(node, isRoot = false) {
  const passives = displayPassives(node, isRoot);
  if (!passives.length) return '<div class="passive-list empty-passives">No passives</div>';
  return `<div class="passive-list">${passives.map(passive => {
    const tone = passiveTone(passive, node, isRoot);
    const arrows = passiveArrows(tone);
    return `
      <span class="passive-bar ${tone}" ${passiveTooltipAttrs(passive, tone)}>
        <span class="passive-name">${escapeHtml(passive)}</span>
        ${isJunkPassive(passive, node, isRoot) ? '<span class="junk-pill">Junk</span>' : ''}
        ${arrows ? `<span class="passive-rank">${arrows}</span>` : ''}
      </span>
    `;
  }).join('')}</div>`;
}

function renderPalNode(node, isRoot = false) {
  const role = nodeRole(node, isRoot);
  const roleClass = role === 'OWNED' ? 'owned' : role === 'FINAL EGG' ? 'target' : 'breed';
  const gender = genderLabel(node);
  const visibleJunk = displayJunk(node, isRoot);
  const junk = visibleJunk.length ? `<div class="node-warning junk-text">Junk: ${escapeHtml(visibleJunk.join(', '))}</div>` : '';
  return `
    <div class="pal-node ${roleClass}">
      <div class="pal-main">
        <div class="pal-avatar">${node.icon ? `<img src="${escapeHtml(assetUrl(node.icon))}" alt="">` : escapeHtml(speciesInitials(node.species))}</div>
        <div class="pal-copy">
          <div class="pal-title">${escapeHtml(node.species)} ${gender.symbol ? `<span class="gender ${escapeHtml(gender.className)}">${gender.symbol}</span>` : ''}</div>
          <div class="pal-subtitle">${escapeHtml(locationText(node))}</div>
          ${renderTypeChips(node.types || speciesTypes(node.species))}
          ${gender.text ? `<div class="pal-gender-text ${escapeHtml(gender.className)}">${escapeHtml(gender.text)}</div>` : ''}
        </div>
      </div>
      ${renderPassiveBars(node, isRoot)}
      <div class="node-foot">
        <span class="role-badge ${roleClass}">${role}</span>
        <span>${node.desired.length}/${node.desired.length + node.missing.length} desired</span>
        <span>${visibleJunk.length} junk</span>
      </div>
      ${junk}
    </div>`;
}

function renderBreedTree(node, isRoot = false) {
  const children = node.parents?.length
    ? `<div class="branch"><div class="children">${node.parents.map(parent => renderBreedTree(parent)).join('')}</div></div>`
    : '';
  return `<div class="tree-node">${renderPalNode(node, isRoot)}${children}</div>`;
}

function renderResultCard(r, idx, totalDesired) {
  const visibleJunk = displayJunk(r, true);
  const clean = visibleJunk.length === 0;
  const complete = r.missing.length === 0;
  const summary = complete
    ? `${generationLabel(r.steps)} · ${visibleJunk.length} junk`
    : `${r.desired.length}/${totalDesired} desired · missing ${r.missing.length}`;
  const progressNotes = r.progressNotes?.length
    ? `<div class="progress-notes">${r.progressNotes.map(note => `<span>${escapeHtml(note)}</span>`).join('')}</div>`
    : '';
  return `
    <article class="result route-card">
      <div class="route-header">
        <div>
          <h3>Option ${idx + 1}: ${escapeHtml(r.species)}</h3>
          <p>${escapeHtml(summary)}</p>
        </div>
        <div class="badges route-badges">
          <span class="badge ${complete ? 'good' : 'warn'}">${r.desired.length}/${totalDesired} desired</span>
          <span class="badge ${clean ? 'good' : 'bad'}">${visibleJunk.length} junk</span>
          <span class="badge">${generationLabel(r.steps)}</span>
        </div>
      </div>
      ${progressNotes}
      <div class="breed-tree">${renderBreedTree(r, true)}</div>
    </article>`;
}

function ivSummary(item) {
  return `HP ${item.hpIv} / ATK ${item.attackIv} / DEF ${item.defenseIv}`;
}

function renderIvPalCard(pal, compact = false) {
  const sex = pal.gender === 'Male' ? '♂' : pal.gender === 'Female' ? '♀' : '';
  const sexClass = pal.gender === 'Male' ? 'male' : pal.gender === 'Female' ? 'female' : '';
  const junk = pal.junk?.length ? `<div class="node-warning junk-text">Junk: ${escapeHtml(pal.junk.join(', '))}</div>` : '';
  return `
    <div class="iv-pal-card ${compact ? 'compact' : ''}">
      <div class="pal-main">
        <div class="pal-avatar">${pal.icon ? `<img src="${escapeHtml(assetUrl(pal.icon))}" alt="">` : escapeHtml(speciesInitials(pal.species))}</div>
        <div class="pal-copy">
          <div class="pal-title">${escapeHtml(pal.species)} ${sex ? `<span class="gender ${sexClass}">${sex}</span>` : ''}</div>
          <div class="pal-subtitle">${escapeHtml(locationText(pal))}</div>
          ${renderTypeChips(pal.types || speciesTypes(pal.species))}
        </div>
      </div>
      ${renderPassiveBars(pal, false)}
      <div class="iv-grid">
        <span><strong>${escapeHtml(pal.hpIv)}</strong> HP</span>
        <span><strong>${escapeHtml(pal.attackIv)}</strong> ATK</span>
        <span><strong>${escapeHtml(pal.defenseIv)}</strong> DEF</span>
        <span><strong>${escapeHtml(pal.avgIv)}</strong> AVG</span>
      </div>
      <div class="node-foot">
        <span class="role-badge owned">OWNED</span>
        <span>${pal.desired.length}/${pal.desired.length + pal.missing.length} desired</span>
        <span>${pal.junk.length} junk</span>
      </div>
      ${junk}
    </div>`;
}

function renderIvPair(pair, idx) {
  const clean = pair.junk.length === 0;
  const complete = pair.missing.length === 0;
  const supportText = `100 support: HP ${pair.hp100Support || 0}x / ATK ${pair.attack100Support || 0}x / DEF ${pair.defense100Support || 0}x`;
  return `
    <article class="result iv-pair-card">
      <div class="route-header">
        <div>
          <h3>Option ${idx + 1}</h3>
          <p>${escapeHtml(supportText)}</p>
        </div>
        <div class="badges route-badges">
          <span class="badge ${complete ? 'good' : 'warn'}">${pair.desired.length}/${pair.desired.length + pair.missing.length} desired</span>
          <span class="badge">${escapeHtml(pair.doublePerfectCoverage || 0)} doubled</span>
          <span class="badge ${clean ? 'good' : 'bad'}">${pair.junk.length} junk</span>
        </div>
      </div>
      <div class="iv-pair-grid">
        ${pair.parents.map(parent => renderIvPalCard(parent, true)).join('')}
      </div>
      ${pair.junk.length ? `<div class="node-warning junk-text">Junk in parent pool: ${escapeHtml(pair.junk.join(', '))}</div>` : ''}
    </article>`;
}

function renderIvResults(data) {
  state.lastPlan = data.error ? null : data;
  state.plansByMode.iv = state.lastPlan;
  updateRouteName();
  const results = $('results');
  if (data.error) {
    $('summary').textContent = data.error;
    results.innerHTML = `<div class="empty">${escapeHtml(data.error)}</div>`;
    return;
  }
  $('summary').textContent = `${data.targetCount} owned ${data.target} considered for perfect IV breeding.`;
  const genderNote = data.genderPreference && data.genderPreference !== 'any'
    ? `<span>Gender preference: ${escapeHtml(data.genderPreference)}. Matching gender count: ${data.matchingGenderCount}.</span>`
    : '';
  const implantNote = data.implantPassives?.length
    ? `<span>Planned implants: ${escapeHtml(data.implantPassives.join(', '))}.</span>`
    : '';
  const method = `<div class="owned-notice"><strong>Method</strong><span>Breed one recommended pair. Keep a child with the desired natural passives and more 100-IV categories, then sync and repeat.</span>${implantNote}${genderNote}</div>`;
  const pairs = data.pairs.length
    ? `<section class="result-group"><div class="group-heading compact-heading"><h3>Recommended Pairs</h3></div><div class="iv-options-grid">${data.pairs.map((pair, idx) => renderIvPair(pair, idx)).join('')}</div></section>`
    : '<div class="empty">No compatible same-species IV pairs found.</div>';
  const matching = data.matchingPals.length
    ? `<details class="result-group result-details"><summary><span>Owned Goal-Passive Pals</span><strong>${data.matchingPals.length}</strong></summary><p>Owned ${escapeHtml(data.target)} with exactly the requested passive set.</p><div class="iv-card-grid">${data.matchingPals.map(pal => renderIvPalCard(pal)).join('')}</div></details>`
    : `<details class="result-group result-details"><summary><span>Owned Goal-Passive Pals</span><strong>0</strong></summary><p>No owned ${escapeHtml(data.target)} currently has exactly the requested passive set.</p></details>`;
  results.innerHTML = `${method}${pairs}${matching}`;
}

function ivTargetOptionLabel(pal) {
  const passives = pal.passives?.length ? pal.passives.join(', ') : 'No passives';
  return `${pal.gender || '?'} | ${ivSummary(pal)} | ${pal.location || 'Owned'} | ${passives}`;
}

function selectedIvTargetPal() {
  const selectedId = $('ivTargetInstance')?.value || state.formsByMode.iv?.ivTargetInstance || '';
  return state.ivTargetPals.find(pal => (pal.selectionId || pal.instanceId) === selectedId) || null;
}

function renderIvSelectedTarget() {
  const wrap = $('ivSelectedTarget');
  if (!wrap) return;
  const pal = selectedIvTargetPal();
  wrap.innerHTML = pal
    ? renderIvTargetChoiceCard(pal, pal.selectionId || pal.instanceId, true, {showAction: false})
    : '<div class="empty compact">No target Pal selected.</div>';
}

function renderCompactPassiveList(passives = []) {
  if (!passives.length) return '<div class="iv-compact-passives empty-passives">No passives</div>';
  return `<div class="iv-compact-passives">${sortedPassivesForDisplay(passives).map(passive => (
    `<span class="iv-compact-passive ${passiveTone(passive)}" ${passiveTooltipAttrs(passive)}>${escapeHtml(passive)}</span>`
  )).join('')}</div>`;
}

function renderIvTargetChoiceCard(pal, id, selected, options = {}) {
  const sex = pal.gender === 'Male' ? '♂' : pal.gender === 'Female' ? '♀' : '';
  const sexClass = pal.gender === 'Male' ? 'male' : pal.gender === 'Female' ? 'female' : '';
  const showAction = options.showAction !== false;
  return `
    <article class="iv-target-card ${selected ? 'selected' : ''}">
      <div class="pal-main">
        <div class="pal-avatar">${pal.icon ? `<img src="${escapeHtml(assetUrl(pal.icon))}" alt="">` : escapeHtml(speciesInitials(pal.species))}</div>
        <div class="pal-copy">
          <div class="pal-title">${escapeHtml(pal.species)} ${sex ? `<span class="gender ${sexClass}">${sex}</span>` : ''}</div>
          <div class="pal-subtitle">${escapeHtml(locationText(pal))}</div>
        </div>
      </div>
      ${renderCompactPassiveList(pal.passives || [])}
      <div class="iv-grid compact">
        <span><strong>${escapeHtml(pal.hpIv)}</strong> HP</span>
        <span><strong>${escapeHtml(pal.attackIv)}</strong> ATK</span>
        <span><strong>${escapeHtml(pal.defenseIv)}</strong> DEF</span>
        <span><strong>${escapeHtml(pal.avgIv)}</strong> AVG</span>
      </div>
      ${showAction ? `<button type="button" class="iv-target-select" data-iv-target="${escapeHtml(id)}">${selected ? 'Selected' : 'Select'}</button>` : ''}
    </article>`;
}

function ivTargetBucketTitle(pal) {
  const location = pal.location || '';
  if (pal.box) return `Palbox Box ${pal.box}`;
  if (/^party\b/i.test(location)) return 'Party';
  if (/^base\b/i.test(location) || !/palbox|storage|party/i.test(location)) return `Base: ${location || 'Unknown'}`;
  return location || 'Other';
}

function ivTargetBuckets() {
  const selectedId = $('ivTargetInstance')?.value || '';
  const bucketMap = new Map();
  for (const pal of state.ivTargetPals) {
    const id = pal.selectionId || pal.instanceId;
    const title = id === selectedId ? 'Selected Target' : ivTargetBucketTitle(pal);
    if (!bucketMap.has(title)) {
      bucketMap.set(title, {title, open: title === 'Selected Target' || title === 'Party' || title.startsWith('Base:'), pals: []});
    }
    bucketMap.get(title).pals.push(pal);
  }
  const bucketRank = bucket => {
    if (bucket.title === 'Selected Target') return [0, bucket.title];
    if (bucket.title === 'Party') return [1, bucket.title];
    if (bucket.title.startsWith('Base:')) return [2, bucket.title];
    if (bucket.title.startsWith('Palbox Box ')) {
      const box = Number((bucket.title.match(/Box (\d+)/) || [])[1] || 999);
      return [3, box];
    }
    return [4, bucket.title];
  };
  return [...bucketMap.values()]
    .sort((a, b) => {
      const ar = bucketRank(a);
      const br = bucketRank(b);
      return ar[0] - br[0] || String(ar[1]).localeCompare(String(br[1]), undefined, {numeric: true});
    });
}

function closeIvTargetPicker() {
  $('ivTargetModal')?.classList.add('hidden');
}

function renderIvTargetPicker() {
  const cards = $('ivTargetCards');
  if (!cards) return;
  const selectedId = $('ivTargetInstance')?.value || '';
  const buckets = ivTargetBuckets();
  cards.innerHTML = buckets.length
    ? buckets.map(bucket => `
        <details class="iv-target-section" ${bucket.open ? 'open' : ''}>
          <summary>${escapeHtml(bucket.title)} <span>${bucket.pals.length}</span></summary>
          <div class="iv-target-section-list">
            ${bucket.pals.map(pal => {
              const id = pal.selectionId || pal.instanceId;
              return renderIvTargetChoiceCard(pal, id, id === selectedId);
            }).join('')}
          </div>
        </details>
      `).join('')
    : '<div class="empty compact">No owned Pals of this species were found.</div>';
  cards.querySelectorAll('.iv-target-select').forEach(button => {
    button.addEventListener('click', () => {
      $('ivTargetInstance').value = button.dataset.ivTarget || '';
      state.formsByMode.iv.ivTargetInstance = $('ivTargetInstance').value || '';
      renderIvSelectedTarget();
      renderIvTargetPicker();
      updateActiveForm();
      closeIvTargetPicker();
    });
  });
}

function openIvTargetPicker() {
  renderIvTargetPicker();
  $('ivTargetModal')?.classList.remove('hidden');
}

async function loadOwnedTargetPals() {
  if (state.mode !== 'iv') return;
  const select = $('ivTargetInstance');
  const hint = $('ivTargetHint');
  const target = exactTargetFromField();
  if (!target) {
    clearIvTargetChoices();
    return;
  }
  const requestSeq = ++state.ivTargetLoadSeq;
  const owner = $('owner')?.value || 'David';
  try {
    await preloadBaseSites();
  } catch {
    // Base names are helpful context, but target loading should still work without decoded base metadata.
  }
  const data = await api(`/api/owned-target-pals?owner=${encodeURIComponent(owner)}&target=${encodeURIComponent(target)}`);
  const currentTarget = exactTargetFromField();
  if (requestSeq !== state.ivTargetLoadSeq || currentTarget !== target) return;
  state.ivTargetPals = data.pals || [];
  const previous = state.formsByMode.iv?.ivTargetInstance || select.value || '';
  select.innerHTML = '<option value=""></option>' + state.ivTargetPals.map(pal => (
    `<option value="${escapeHtml(pal.selectionId || pal.instanceId)}">${escapeHtml(ivTargetOptionLabel(pal))}</option>`
  )).join('');
  if (previous && [...select.options].some(option => option.value === previous)) {
    select.value = previous;
  } else {
    select.value = '';
  }
  state.formsByMode.iv.ivTargetInstance = select.value || '';
  renderIvSelectedTarget();
  renderIvTargetPicker();
  setStatus(
    hint,
    data.count
      ? `${data.count} owned ${data.target} found. The selected Pal's passives become the preservation target.`
      : `No owned ${data.target} found for ${owner}.`,
    data.count ? 'good' : 'warn'
  );
  updateActiveForm();
}

function workLevelText(entry) {
  if (entry.fullyCondensedLevel) return `${entry.label} Lv. ${entry.level} -> ${entry.fullyCondensedLevel}`;
  return `${entry.label} Lv. ${entry.level} -> needs verification`;
}

function workClass(key) {
  return `work-${matchKey(key).replace(/\s+/g, '-')}`;
}

function renderWorkSkillPills(work, verified = false, selectedWork = '') {
  const orderedWork = selectedWork
    ? [...work].sort((a, b) => {
        if (a.key === selectedWork && b.key !== selectedWork) return -1;
        if (b.key === selectedWork && a.key !== selectedWork) return 1;
        return 0;
      })
    : work;
  return `<div class="work-skill-list">${orderedWork.map(entry => {
    const currentOnly = Boolean(entry.currentOnly);
    const finalValue = verified && entry.fullyCondensedLevel ? entry.fullyCondensedLevel : 'Verify';
    const title = currentOnly
      ? 'Current owned-Pal work level used by Right now mode.'
      : verified ? 'Source-verified fully condensed level' : `Projected value was ${entry.projectedFullyCondensedLevel || 'unknown'}, but this is hidden until verified.`;
    const selected = entry.key === selectedWork;
    const plannerCurrent = Number(entry.plannerCurrentLevel || 0);
    const plannerMaximum = Number(entry.plannerMaximumLevel || 0);
    const atMaximum = plannerCurrent > 0 && plannerMaximum > 0 && plannerCurrent >= plannerMaximum;
    const value = plannerCurrent > 0
      ? atMaximum
        ? `<strong class="owned-work-level">${escapeHtml(plannerCurrent)}</strong><span class="max-work-badge">MAX</span>`
        : `<strong class="owned-work-level">${escapeHtml(plannerCurrent)}</strong><span class="work-level-projection">-&gt; ${escapeHtml(plannerMaximum || finalValue)}</span>`
      : currentOnly
        ? `<strong>${escapeHtml(entry.level)}</strong>`
        : `<strong>${escapeHtml(entry.level)} -&gt; ${escapeHtml(finalValue)}</strong>`;
    return `
      <span class="work-skill-pill ${verified ? 'verified' : 'unverified'} ${workClass(entry.key)} ${selected ? 'selected-work' : 'secondary-work'}" title="${escapeHtml(title)}">
        <span class="work-skill-name"><span class="work-mark ${workClass(entry.key)}">${inlineIcon(entry.key)}</span>${escapeHtml(entry.label)}</span>
        <span class="work-level-value">${value}</span>
      </span>
    `;
  }).join('')}</div>`;
}

function renderWorkCard(card, compact = false, recommendation = null) {
  const actionPayload = encodeURIComponent(JSON.stringify({name: card.name, key: card.key, types: card.types || []}));
  const groupCount = Number(card.plannerGroupCount || 0);
  const isPlannerCard = groupCount > 0 || Boolean(card.plannerInstances);
  const titleName = groupCount > 1 ? `${card.name} x${groupCount}` : card.name;
  const owned = groupCount > 1 ? `<span class="role-badge owned">Use: ${groupCount}</span>` : card.ownedCount ? `<span class="role-badge owned">Own: ${card.ownedCount}</span>` : '<span class="role-badge">Not owned</span>';
  const breedable = card.requiresOwnedSeed
    ? '<span class="badge self-breed" title="This Pal cannot be bred from other species. You need an owned copy first, then breed it with the same species.">Self-Breed Only</span>'
    : card.breedable ? '<span class="badge good">Breedable</span>' : '<span class="badge bad">Not breedable</span>';
  const breedabilityPill = compact && !card.requiresOwnedSeed ? '' : breedable;
  const verified = card.workCondensationSource === 'verified';
  const typeChips = renderTypeChips(card.types || []);
  const size = card.sizeKnown ? `${card.sizeGroup} (${card.size})` : 'Unknown size';
  const seedWarning = card.unavailableReason
    ? `<div class="work-seed-warning"><strong>Owned copy required</strong><span>${escapeHtml(card.unavailableReason)}</span></div>`
    : '';
  const recHead = recommendation ? `
      <div class="work-rec-head">
        <div>
          <div class="work-rec-kicker">${escapeHtml(recommendation.title)}</div>
          <div class="work-rec-reason">${escapeHtml(recommendation.reason || '')}</div>
        </div>
        <button type="button" class="card-action breed-corner-action" data-breed-card="${actionPayload}">Breed</button>
      </div>` : '';
  return `
    <article class="work-pal-card ${compact ? 'compact' : ''} ${recommendation ? 'work-rec-card' : ''}">
      ${recommendation ? recHead : `<button type="button" class="card-action breed-corner-action" data-breed-card="${actionPayload}">Breed</button>`}
      <div class="pal-main">
        <div class="pal-avatar">${card.icon ? `<img src="${escapeHtml(assetUrl(card.icon))}" alt="">` : escapeHtml(speciesInitials(card.name))}</div>
        <div class="pal-copy">
          <div class="pal-title">${escapeHtml(titleName)}</div>
          <div class="pal-subtitle">${escapeHtml(size)}</div>
          ${typeChips}
        </div>
      </div>
      ${renderWorkSkillPills(card.work, verified, card.selectedWork)}
      ${seedWarning}
      <div class="node-foot">${owned}${breedabilityPill}</div>
    </article>`;
}

function renderRecommendation(rec) {
  if (!rec?.card) return '';
  return renderWorkCard(rec.card, true, rec);
}

function maxWorkRows(recommendations) {
  return Math.max(1, ...recommendations.map(rec => rec?.card?.work?.length || 0));
}

function workCardVisible(card) {
  const display = $('workDisplay')?.value || 'all';
  if (display === 'owned' && !card.ownedCount) return false;
  return true;
}

function filteredWorkGroups(data) {
  return (data.groups || []).map(group => {
    const cards = group.cards.filter(workCardVisible);
    return {...group, cards};
  }).filter(group => group.cards.length);
}

function workFinalLevel(card) {
  return Number(card?.selectedFullyCondensedLevel || card?.selectedLevel || 0);
}

function compareKeys(a, b) {
  const len = Math.max(a.length, b.length);
  for (let i = 0; i < len; i += 1) {
    const av = a[i];
    const bv = b[i];
    if (av === bv) continue;
    if (typeof av === 'string' || typeof bv === 'string') return String(av).localeCompare(String(bv));
    return Number(av) - Number(bv);
  }
  return 0;
}

function sortWorkCards(cards, keyFn) {
  return [...cards].sort((a, b) => compareKeys(keyFn(a), keyFn(b)));
}

const POPULAR_WORK_PICKS = {
  handiwork: 'Anubis',
  mining: 'Anubis',
};

function workRecommendationEligible(card) {
  return !card?.unavailableReason;
}

function frontendWorkRecommendations(cards, selectedWork) {
  if (!cards.length) return [];
  const recommendable = cards.filter(workRecommendationEligible);
  const pickPool = recommendable.length ? recommendable : cards;
  const popularName = POPULAR_WORK_PICKS[selectedWork];
  const popular = popularName ? pickPool.find(card => card.name === popularName) : null;
  const practical = popular || sortWorkCards(pickPool, card => [
    -workFinalLevel(card),
    ['S', 'M'].includes(card.size) ? 0 : ['XS', 'L'].includes(card.size) ? 1 : 2,
    card.workCount || 99,
    card.ownedCount ? 0 : 1,
    card.name || '',
  ])[0];
  const sizeRank = {XS: 0, S: 1, M: 2, L: 3, XL: 4};
  const bestForSizes = sizes => sortWorkCards(pickPool.filter(card => sizes.includes(card.size)), card => [
    -workFinalLevel(card),
    -Number(card.selectedLevel || 0),
    card.workCount || 99,
    card.ownedCount ? 0 : 1,
    sizeRank[card.size] ?? 99,
    card.name || '',
  ])[0];
  const dark = sortWorkCards(pickPool.filter(card => isDarkType(card.types || [])), card => [
    -workFinalLevel(card),
    -Number(card.selectedLevel || 0),
    ['S', 'M'].includes(card.size) ? 0 : ['XS', 'L'].includes(card.size) ? 1 : 2,
    card.workCount || 99,
    card.ownedCount ? 0 : 1,
    card.name || '',
  ])[0];
  return [
    {title: 'Recommended', reason: popular ? 'Common practical choice for this work skill.' : 'Best practical mix of final level, footprint, focus, and ownership.', card: practical},
    {title: 'Best Dark', reason: 'Best dark-type option for this work skill; dark Pals do not need Insomnia for night uptime.', card: dark},
    {title: 'Best XL', reason: 'Highest selected work level among XL Pals.', card: bestForSizes(['XL'])},
    {title: 'Best L', reason: 'Highest selected work level among L Pals.', card: bestForSizes(['L'])},
    {title: 'Best Medium', reason: 'Highest selected work level among Medium (M) Pals.', card: bestForSizes(['M'])},
    {title: 'Best Small', reason: 'Highest selected work level among Small (S) Pals.', card: bestForSizes(['S'])},
    {title: 'Best XS', reason: 'Highest selected work level among Extra Small (XS) Pals.', card: bestForSizes(['XS'])},
  ].filter(rec => rec.card);
}

async function loadWorkSuitability() {
  saveCurrentForm();
  const owner = encodeURIComponent($('owner')?.value || 'David');
  const selectedWork = $('workType')?.value || '';
  if (!selectedWork) {
    state.plansByMode.work = null;
    state.lastPlan = null;
    emptyModeMessage('work');
    updateRouteName();
    return;
  }
  const work = encodeURIComponent(selectedWork);
  const data = await api(`/api/work-suitability?owner=${owner}&work=${work}`);
  state.plansByMode.work = data;
  state.lastPlan = data;
  renderWorkSuitability(data);
}

function renderWorkSuitability(data) {
  const groups = filteredWorkGroups(data);
  const shown = groups.reduce((sum, group) => sum + group.cards.length, 0);
  $('summary').textContent = `${shown} ${data.selectedWorkLabel} candidate(s), ${data.verifiedCondensationCount || 0}/${data.total} with verified fully condensed work data.`;
  const visibleCards = groups.flatMap(group => group.cards);
  const recs = frontendWorkRecommendations(visibleCards, data.selectedWork).filter(rec => rec?.card);
  const primaryRecs = recs.filter(rec => ['Recommended', 'Best Dark'].includes(rec.title));
  const sizeRecs = recs.filter(rec => !['Recommended', 'Best Dark'].includes(rec.title));
  const recWorkRows = maxWorkRows(recs);
  $('results').innerHTML = `
    <div class="owned-notice work-note">
      <strong>${escapeHtml(data.selectedWorkLabel)} Suitability Browser</strong>
      <span>${escapeHtml(data.condensationNote)}</span>
      <span>${escapeHtml(data.sizeSourceNote)}</span>
    </div>
    ${recs.length ? `<section class="work-rec-section" style="--work-row-count: ${recWorkRows}">
      <div class="group-heading"><h3>Top Picks</h3></div>
      ${primaryRecs.length ? `<div class="work-rec-grid primary-picks">${primaryRecs.map(renderRecommendation).join('')}</div>` : ''}
      ${sizeRecs.length ? `<div class="work-rec-subhead">Size Picks</div><div class="work-rec-grid size-picks">${sizeRecs.map(renderRecommendation).join('')}</div>` : ''}
    </section>` : ''}
    ${groups.length ? groups.map(group => `
      <details class="result-group work-group">
        <summary class="group-heading"><h3><span class="disclosure-icon" aria-hidden="true"></span>${escapeHtml(group.title)} (${group.cards.length})</h3></summary>
        <div class="work-card-grid">${group.cards.map(card => renderWorkCard(card)).join('')}</div>
      </details>
    `).join('') : '<div class="empty">No Pals match this work suitability/filter combination.</div>'}
  `;
  document.querySelectorAll('[data-breed-card]').forEach(button => {
    button.addEventListener('click', () => {
      const payload = JSON.parse(decodeURIComponent(button.dataset.breedCard || '%7B%7D'));
      goToBreedingFor(payload);
    });
  });
}

function ranchQuery() {
  return String($('ranchSearch')?.value || state.formsByMode.ranch?.ranchSearch || '').trim().toLowerCase();
}

function ranchItemMatches(item, query) {
  if (!query) return true;
  const haystack = [
    item.name,
    ...(item.pals || []).flatMap(card => [
      card.name,
      card.sizeGroup,
      ...(card.types || []),
      ...(card.ranchDrops || []).map(drop => drop.name),
    ]),
  ].join(' ').toLowerCase();
  return haystack.includes(query);
}

async function loadRanchDrops() {
  saveCurrentForm();
  const owner = encodeURIComponent($('owner')?.value || 'David');
  const data = await api(`/api/ranch-drops?owner=${owner}`);
  state.plansByMode.ranch = data;
  state.lastPlan = data;
  renderRanchDrops(data);
}

function ranchDropMeta(card, itemName = '') {
  const drops = card.ranchDrops || [];
  const selected = itemName ? drops.find(drop => drop.name === itemName) : drops[0];
  if (!selected) return '';
  const amount = selected.min === selected.max ? selected.min : `${selected.min}-${selected.max}`;
  return `<span class="ranch-drop-meta">${escapeHtml(amount)} each · ${escapeHtml(selected.rate)}%</span>`;
}

function renderRanchPalCard(card, itemName = '') {
  const drops = (card.ranchDrops || []).map(drop => `<span class="ranch-drop-chip ${drop.name === itemName ? 'active' : ''}">${escapeHtml(drop.name)}</span>`).join('');
  const partner = card.partnerSkill?.name ? `<span class="ranch-skill-name">${escapeHtml(card.partnerSkill.name)}</span>` : '';
  return renderWorkCard(card, true).replace('</article>', `
      <div class="ranch-drop-row">${drops}${ranchDropMeta(card, itemName)}</div>
      ${partner}
    </article>`);
}

function renderRanchItemCard(item) {
  const best = item.best;
  const icon = best?.icon ? `<img src="${escapeHtml(assetUrl(best.icon))}" alt="">` : escapeHtml(speciesInitials(best?.name || item.name));
  const owned = (item.pals || []).reduce((sum, card) => sum + Number(card.ownedCount || 0), 0);
  return `
    <button type="button" class="ranch-item-card" data-ranch-item="${escapeHtml(item.name)}">
      <span class="ranch-item-icon">${icon}</span>
      <span class="ranch-item-copy">
        <strong>${escapeHtml(item.name)}</strong>
        <span>${escapeHtml(item.count)} ranch Pal${item.count === 1 ? '' : 's'} · ${owned ? `Own: ${owned}` : 'Not owned'}</span>
      </span>
    </button>`;
}

function selectedRanchItem(data) {
  const selected = state.formsByMode.ranch?.ranchItem || '';
  return (data.items || []).find(item => item.name === selected) || null;
}

function renderRanchDrops(data) {
  const query = ranchQuery();
  const items = (data.items || []).filter(item => ranchItemMatches(item, query));
  const selected = selectedRanchItem(data);
  $('summary').textContent = selected
    ? `${selected.count} ranch Pal${selected.count === 1 ? '' : 's'} can produce ${selected.name}.`
    : `${items.length}/${data.totalItems || 0} ranch item(s), ${data.totalPals || 0} Farming/Ranch Pal(s) indexed.`;
  if (selected) {
    const topPick = selected.best ? renderRanchPalCard(selected.best, selected.name) : '';
    const others = (selected.pals || []).filter(card => card.name !== selected.best?.name);
    $('results').innerHTML = `
      <div class="ranch-detail-head">
        <div><h3>${escapeHtml(selected.name)}</h3><p>${escapeHtml(data.sourceNote || '')}</p></div>
      </div>
      ${topPick ? `<section class="work-rec-section ranch-top-pick"><div class="group-heading"><h3>Top Pick</h3></div><div class="work-rec-grid primary-picks">${topPick}</div></section>` : ''}
      <section class="result-group">
        <div class="group-heading"><h3>All Producers</h3><p>Sorted by ownership, Farming level, footprint, and focus.</p></div>
        <div class="work-card-grid ranch-candidate-grid">${(selected.pals || []).map(card => renderRanchPalCard(card, selected.name)).join('')}</div>
      </section>`;
  } else {
    $('results').innerHTML = `
      <div class="owned-notice work-note">
        <strong>Ranch Drops</strong>
        <span>${escapeHtml(data.sourceNote || '')}</span>
      </div>
      ${items.length ? `<div class="ranch-item-grid">${items.map(renderRanchItemCard).join('')}</div>` : '<div class="empty">No ranch drops match that search.</div>'}`;
    document.querySelectorAll('[data-ranch-item]').forEach(button => {
      button.addEventListener('click', () => {
        state.formsByMode.ranch.ranchItem = button.dataset.ranchItem || '';
        renderRanchDrops(data);
        updateHistoryNav();
        updateRouteName();
      });
    });
  }
  document.querySelectorAll('[data-breed-card]').forEach(button => {
    button.addEventListener('click', () => {
      const payload = JSON.parse(decodeURIComponent(button.dataset.breedCard || '%7B%7D'));
      goToBreedingFor(payload);
    });
  });
  updateRouteName();
}

const BASE_SETTINGS_KEY = 'palworldBreeding.basePlannerSettings.v1';

function loadBaseSettings() {
  try {
    state.baseSettings = JSON.parse(localStorage.getItem(BASE_SETTINGS_KEY) || '{}') || {};
  } catch {
    state.baseSettings = {};
  }
}

function persistBaseSettings() {
  localStorage.setItem(BASE_SETTINGS_KEY, JSON.stringify(state.baseSettings));
}

function defaultSkillSetting() {
  return {enabled: true, min: '', max: ''};
}

function settingForBase(baseId, skill) {
  const base = state.baseSettings[baseId] || {};
  return {...defaultSkillSetting(), ...(base[skill] || {})};
}

function setBaseSkillSetting(baseId, skill, patch) {
  state.baseSettings[baseId] = state.baseSettings[baseId] || {};
  state.baseSettings[baseId][skill] = {...settingForBase(baseId, skill), ...patch};
  persistBaseSettings();
}

function clampWorkerCount(value) {
  return Math.min(15, Math.max(1, Number(value) || 15));
}

function workerCountForBase(baseId) {
  const stored = state.baseSettings[baseId]?._maxWorkers;
  return clampWorkerCount(stored ?? 15);
}

function currentBaseWorkerCount() {
  const base = selectedBase();
  return clampWorkerCount($('baseWorkerCount')?.value || workerCountForBase(base?.id || ''));
}

function setBaseWorkerCount(baseId, value) {
  const count = clampWorkerCount(value);
  state.baseSettings[baseId] = state.baseSettings[baseId] || {};
  state.baseSettings[baseId]._maxWorkers = count;
  state.formsByMode.base.maxWorkers = count;
  if ($('baseWorkerCount')) $('baseWorkerCount').value = count;
  persistBaseSettings();
  return count;
}

function selectedBase() {
  const id = $('baseSelect')?.value || '';
  return (state.baseSites?.bases || []).find(base => base.id === id) || (state.baseSites?.bases || [])[0] || null;
}

function renderBaseSelectors() {
  const select = $('baseSelect');
  if (!select || !state.baseSites?.bases) return;
  const current = select.value || state.formsByMode.base.baseId || state.baseSites.bases[0]?.id || '';
  select.innerHTML = state.baseSites.bases.map(base => `<option value="${escapeHtml(base.id)}">${escapeHtml(base.displayName)}</option>`).join('');
  if ([...select.options].some(opt => opt.value === current)) select.value = current;
  state.formsByMode.base.baseId = select.value;
  const base = selectedBase();
  if ($('baseLabel')) $('baseLabel').value = base?.customName || '';
  if ($('baseWorkerCount')) $('baseWorkerCount').value = workerCountForBase(base?.id || '');
  renderBaseSkillControls();
}

function baseDefaultMin(base, skill) {
  const demand = base?.demand || {};
  return Number(demand[skill] || 0) > 0 ? '1' : '';
}

function renderBaseSkillControls() {
  const wrap = $('baseSkillControls');
  const base = selectedBase();
  if (!wrap || !base) return;
  const demand = base.demand || {};
  const maxWorkers = currentBaseWorkerCount();
  wrap.innerHTML = state.workTypes.map(work => {
    const setting = settingForBase(base.id, work.key);
    const disabled = !setting.enabled;
    const minValue = setting.min === '' ? baseDefaultMin(base, work.key) : setting.min;
    return `
      <div class="base-skill-row ${disabled ? 'disabled' : ''}" data-base-skill="${escapeHtml(work.key)}">
        <span class="base-skill-title"><span class="work-mark ${workClass(work.key)}">${inlineIcon(work.key)}</span>${escapeHtml(work.label)}</span>
        <span class="base-site-count">${Number(demand[work.key] || 0)}</span>
        <input type="checkbox" ${setting.enabled ? 'checked' : ''} aria-label="Use ${escapeHtml(work.label)}">
        <input type="number" min="0" max="${maxWorkers}" value="${escapeHtml(minValue)}" placeholder="1" aria-label="Minimum ${escapeHtml(work.label)} workers">
        <input type="number" min="0" max="${maxWorkers}" value="${escapeHtml(setting.max)}" placeholder="Auto" aria-label="Maximum ${escapeHtml(work.label)} workers">
      </div>`;
  }).join('');
  wrap.querySelectorAll('[data-base-skill]').forEach(row => {
    const skill = row.dataset.baseSkill;
    const checkbox = row.querySelector('input[type="checkbox"]');
    const inputs = row.querySelectorAll('input[type="number"]');
    checkbox.addEventListener('change', () => {
      setBaseSkillSetting(base.id, skill, {enabled: checkbox.checked});
      row.classList.toggle('disabled', !checkbox.checked);
    });
    inputs[0].addEventListener('change', () => setBaseSkillSetting(base.id, skill, {min: inputs[0].value}));
    inputs[1].addEventListener('change', () => setBaseSkillSetting(base.id, skill, {max: inputs[1].value}));
  });
}

function currentBasePlannerSettings() {
  const base = selectedBase();
  if (!base) return {};
  const settings = {};
  for (const work of state.workTypes) {
    const setting = settingForBase(base.id, work.key);
    const minValue = setting.min === '' ? baseDefaultMin(base, work.key) : setting.min;
    settings[work.key] = {
      enabled: setting.enabled !== false,
      min: minValue === '' ? null : Number(minValue),
      max: setting.max === '' ? null : Number(setting.max),
    };
  }
  return settings;
}

async function preloadBaseSites({force = false} = {}) {
  if (state.baseSites?.ok && !force) return state.baseSites;
  if (state.baseSitesLoading && !force) return state.baseSitesLoading;
  state.baseSitesLoading = api('/api/base-work-sites')
    .then(data => {
      if (data.ok) {
        state.baseSites = data;
        if (state.mode === 'base') renderBaseSelectors();
      }
      return data;
    })
    .finally(() => {
      state.baseSitesLoading = null;
    });
  return state.baseSitesLoading;
}

async function loadBasePlanner() {
  const data = await preloadBaseSites({force: !state.baseSites});
  state.baseSites = data;
  if (!data.ok) {
    $('summary').textContent = data.error || 'Base planner failed.';
    $('results').innerHTML = `<div class="empty">${escapeHtml(data.error || 'No base data found.')}</div>`;
    return;
  }
  renderBaseSelectors();
  if (state.plansByMode.base) renderBasePlanner(state.plansByMode.base);
  else emptyModeMessage('base');
}

async function saveBaseLabel() {
  const base = selectedBase();
  if (!base) return;
  const label = $('baseLabel')?.value || '';
  const data = await api('/api/base-labels', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({baseId: base.id, label})
  });
  if (data.ok) {
    await loadBasePlanner();
    showToast(label.trim() ? 'Base name saved.' : 'Base name cleared.', 'good');
  }
}

async function optimizeBasePlanner() {
  const base = selectedBase();
  if (!base) {
    $('summary').textContent = 'No base selected.';
    return;
  }
  saveCurrentForm();
  $('summary').textContent = `Planning workforce for ${base.displayName}...`;
  $('results').innerHTML = '';
  const data = await api('/api/base-planner', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      baseId: base.id,
      owner: $('owner')?.value || 'David',
      settings: currentBasePlannerSettings(),
      maxWorkers: currentBaseWorkerCount(),
      plannerMode: $('basePlannerMode')?.value || 'ideal',
    })
  });
  state.plansByMode.base = data;
  state.lastPlan = data;
  renderBasePlanner(data);
}

function renderBasePlanner(data) {
  if (!data.ok) {
    $('summary').textContent = data.error || 'Base planner failed.';
    $('results').innerHTML = `<div class="empty">${escapeHtml(data.error || 'No plan found.')}</div>`;
    return;
  }
  const base = data.base;
  const targets = Object.entries(data.targets || {}).filter(([, cfg]) => cfg.enabled && (cfg.min || cfg.demand));
  const modeLabelText = data.plannerMode === 'right_now' ? 'owned-only right now' : 'ideal target';
  const groupedRecommendations = groupPlannerRecommendations(data.recommendations || []);
  $('summary').textContent = `${data.recommendations.length}/${data.maxWorkers} worker slots shown as ${groupedRecommendations.length} grouped card${groupedRecommendations.length === 1 ? '' : 's'} for ${base.displayName} (${modeLabelText}).`;
  const demandCards = targets.map(([key, cfg]) => `
    <div class="base-demand-card ${workClass(key)}">
      <strong><span class="work-mark">${inlineIcon(key)}</span> ${escapeHtml(state.workTypes.find(w => w.key === key)?.label || key)}</strong>
      <span>${cfg.demand || 0} site(s) · target ${cfg.min || 0}${cfg.max ? ` · max ${cfg.max}` : ''}</span>
    </div>`).join('');
  const sites = (base.sites || []).slice(0, 28).map(site => `<span class="site-pill">${escapeHtml(site.name)}</span>`).join('');
  const gaps = data.gaps?.length ? `<div class="owned-notice"><strong>Coverage gaps</strong><span>${data.gaps.map(g => `${g.label}: ${g.covered}/${g.wanted}`).join(' · ')}</span></div>` : '';
  $('results').innerHTML = `
    <div class="owned-notice work-note">
      <strong>${escapeHtml(base.displayName)}</strong>
      <span>${base.siteCount} resolved work site(s), ${base.unresolvedWorkIds || 0} stale/unresolved work id(s). Coordinates: ${base.coords.x}, ${base.coords.y}, ${base.coords.z}.</span>
      <div class="site-list">${sites}</div>
    </div>
    <section class="work-rec-section"><div class="group-heading"><h3>Worker Targets</h3></div><div class="base-summary-grid">${demandCards}</div></section>
    ${gaps}
    <section class="result-group"><div class="group-heading"><h3>Recommended Workforce</h3><p>${data.plannerMode === 'right_now' ? `Owned-only mode: fills ${data.maxWorkers} worker slots from actual owned Pals. Duplicate species are grouped into one card with an x-count.` : `Ideal mode: fills ${data.maxWorkers} worker slots from breedable targets. Duplicate species are grouped into one card with an x-count.`}</p></div>
      <div class="work-card-grid">${groupedRecommendations.map(card => renderPlannerWorkCard(card)).join('')}</div>
    </section>`;
  document.querySelectorAll('[data-breed-card]').forEach(button => {
    button.addEventListener('click', () => goToBreedingFor(JSON.parse(decodeURIComponent(button.dataset.breedCard || '%7B%7D'))));
  });
}

function groupPlannerRecommendations(cards) {
  const byName = new Map();
  for (const card of cards) {
    const key = card.name || '';
    if (!byName.has(key)) {
      byName.set(key, {...card, plannerSlots: [], plannerRoles: [], plannerReasons: [], plannerInstances: [], plannerPassives: []});
    }
    const group = byName.get(key);
    const roleLabel = card.plannerRole ? state.workTypes.find(work => work.key === card.plannerRole)?.label || card.plannerRole : '';
    group.plannerSlots.push({slot: card.plannerSlot, role: roleLabel, roleKey: card.plannerRole});
    group.plannerRoles.push(card.plannerRole);
    group.plannerInstances.push({
      slot: card.plannerSlot,
      role: roleLabel,
      location: card.plannerLocation || '',
      passives: card.plannerPassives || [],
      speedScore: card.plannerPassiveSpeedScore || 0,
      level: card.plannerLevel || '',
      stars: card.plannerCondensationStars ?? '',
    });
    const currentBestScore = group.plannerBestPassiveScore ?? -9999;
    const cardSpeed = card.plannerPassiveSpeedScore || 0;
    if (!group.plannerPassives.length || cardSpeed > currentBestScore) {
      group.plannerPassives = [...(card.plannerPassives || [])].sort();
      group.plannerBestPassiveScore = cardSpeed;
    }
    for (const reason of card.plannerReasons || []) {
      if (!group.plannerReasons.includes(reason)) group.plannerReasons.push(reason);
    }
  }
  for (const group of byName.values()) {
    group.plannerGroupCount = group.plannerSlots.length;
  }
  return [...byName.values()].sort((a, b) => {
    const roleA = a.plannerSlots[0]?.role || '';
    const roleB = b.plannerSlots[0]?.role || '';
    return roleA.localeCompare(roleB) || a.name.localeCompare(b.name);
  });
}

function roleSummary(slots) {
  const counts = new Map();
  for (const item of slots || []) {
    const role = item.role || 'Role';
    counts.set(role, (counts.get(role) || 0) + 1);
  }
  return [...counts.entries()].map(([role, count]) => `${role}${count > 1 ? ` x${count}` : ''}`).join(', ');
}

function renderPlannerPassiveBars(passives) {
  const items = [...new Set(passives || [])].sort();
  if (!items.length) return '';
  return `<div class="planner-passives">${items.map(passive => {
    const tone = passiveTone(passive);
    const arrows = passiveArrows(tone);
    return `<span class="passive-bar ${tone}" ${passiveTooltipAttrs(passive, tone)}><span class="passive-name">${escapeHtml(passive)}</span>${arrows ? `<span class="passive-rank">${arrows}</span>` : ''}</span>`;
  }).join('')}</div>`;
}

function renderPlannerInstances(instances) {
  const rows = (instances || []).slice(0, 4).map(item => {
    const passives = item.passives?.length ? item.passives.join(', ') : 'No passives';
    return `<span class="planner-instance"><em>${escapeHtml(item.location || 'Owned')}</em><br>${escapeHtml(passives)}</span>`;
  }).join('');
  const extra = (instances || []).length > 4 ? `<span class="planner-instance">+${instances.length - 4} more selected instance(s)</span>` : '';
  return rows || extra ? `<div class="planner-instances">${rows}${extra}</div>` : '';
}

function renderPlannerWorkCard(card) {
  const passives = renderPlannerPassiveBars(card.plannerPassives);
  const instances = renderPlannerInstances(card.plannerInstances);
  return renderWorkCard(card).replace('</article>', `${passives}${instances}</article>`);
}

function emptyModeMessage(mode) {
  const title = modeLabel(mode);
  const body = mode === 'work'
      ? 'Choose a work skill to browse candidates by footprint and fully condensed work levels.'
      : mode === 'iv'
        ? 'Choose a species and target passives, then calculate perfect IV breeding pairs.'
      : mode === 'ranch'
        ? 'Search ranch-produced items, then choose a drop to compare Farming/Ranch producers.'
      : mode === 'base'
        ? 'Choose a base, adjust optional worker targets, then run Plan Base.'
        : 'Choose a target and target passives, then run Optimize.';
  $('summary').textContent = body;
  $('results').innerHTML = `<div class="empty mode-empty"><strong>${title}</strong><span>${body}</span></div>`;
}

function restoreModeView() {
  const plan = state.plansByMode[state.mode];
  if (!plan) {
    state.lastPlan = null;
    emptyModeMessage(state.mode);
    updateRouteName();
    return;
  }
  state.lastPlan = plan;
  if (state.mode === 'work') renderWorkSuitability(plan);
  else if (state.mode === 'ranch') renderRanchDrops(plan);
  else if (state.mode === 'iv') renderIvResults(plan);
  else if (state.mode === 'base') renderBasePlanner(plan);
  else renderResults(plan);
  updateRouteName();
}

function updateModeVisibility(mode = state.mode) {
  document.querySelector('.controls')?.classList.toggle('plain-owner-mode', mode === 'work' || mode === 'ranch' || mode === 'base');
  $('modeBreed').classList.toggle('active', mode === 'breed');
  $('modeIv').classList.toggle('active', mode === 'iv');
  $('modeWork').classList.toggle('active', mode === 'work');
  $('modeRanch').classList.toggle('active', mode === 'ranch');
  $('modeBase').classList.toggle('active', mode === 'base');
  $('modeBreed').setAttribute('aria-pressed', String(mode === 'breed'));
  $('modeIv').setAttribute('aria-pressed', String(mode === 'iv'));
  $('modeWork').setAttribute('aria-pressed', String(mode === 'work'));
  $('modeRanch').setAttribute('aria-pressed', String(mode === 'ranch'));
  $('modeBase').setAttribute('aria-pressed', String(mode === 'base'));
  document.querySelectorAll('.work-option').forEach(el => el.classList.toggle('hidden', mode !== 'work'));
  document.querySelectorAll('.ranch-option').forEach(el => el.classList.toggle('hidden', mode !== 'ranch'));
  document.querySelectorAll('.base-option').forEach(el => el.classList.toggle('hidden', mode !== 'base'));
  document.querySelectorAll('.custom-option').forEach(el => el.classList.toggle('hidden', mode === 'work' || mode === 'ranch' || mode === 'base'));
  document.querySelectorAll('.iv-option').forEach(el => el.classList.toggle('hidden', mode !== 'iv'));
  document.querySelectorAll('.owner-gender-row label:nth-child(2)').forEach(el => el.classList.toggle('hidden', mode === 'work' || mode === 'ranch' || mode === 'base'));
  document.querySelectorAll('.breed-option').forEach(el => el.classList.toggle('hidden', mode !== 'breed'));
  document.querySelectorAll('.profile-option').forEach(el => el.classList.toggle('hidden', mode !== 'breed' && mode !== 'iv'));
  $('optimize').classList.toggle('hidden', mode === 'work' || mode === 'ranch');
  $('optimize').textContent = mode === 'base' ? 'Plan Base' : mode === 'iv' ? 'Calculate IVs' : 'Optimize';
}

function setMode(mode, options = {}) {
  const recordHistory = options.recordHistory !== false;
  if (mode === state.mode) {
    updateModeVisibility(mode);
    updateHistoryNav();
    restoreModeView();
    return;
  }
  saveCurrentForm();
  if (recordHistory) rememberModeTransition(mode);
  state.mode = mode;
  updateModeVisibility(mode);
  if (mode !== 'breed') closeProfileEditor();
  applyFormToUi(state.formsByMode[mode]);
  updateHistoryNav();
  restoreModeView();
}

function activateMode(mode) {
  if (mode === state.mode) {
    toggleControlsPanel();
    return;
  }
  setControlsCollapsed(false);
  setMode(mode);
}

function renderResults(data) {
  state.lastPlan = data.error ? null : data;
  state.plansByMode.breed = state.lastPlan;
  updateRouteName();
  const results = $('results');
  if (data.error) {
    $('summary').textContent = data.error;
    results.innerHTML = `<div class="empty">${escapeHtml(data.error)}</div>`;
    return;
  }
  if (isAutoProfile(data.breedingProfile) && data.profileSelectedPassives?.length) {
    state.selectedPassives = [...data.profileSelectedPassives];
    renderPassives();
    updateActiveForm();
  }
  if (data.achievable === false) {
    state.plansByMode.breed = null;
    state.lastPlan = null;
    $('summary').textContent = `No attainable ${data.target} path`;
    results.innerHTML = `
      <div class="unavailable-stage">
        <div class="unavailable-card">
          <strong>You cannot currently achieve ${escapeHtml(data.target)} with the selected passives.</strong>
          <span>${isAutoProfile(data.breedingProfile)
            ? `No owned ${builtInProfileLabel(data.breedingProfile).toLowerCase()} passive combination could be routed to this Pal.`
            : 'Remove one or more desired passives and try again.'}</span>
        </div>
      </div>`;
    return;
  }
  const groups = data.groups || [{title: 'Results', description: '', results: data.results || []}];
  const total = groups.reduce((sum, group) => sum + group.results.length, 0);
  $('summary').textContent = `${total} option(s), owner ${data.owner}, ${data.ownedCount} owned Pals considered.`;
  const owned = data.alreadyOwned;
  const wantsGender = data.genderPreference && data.genderPreference !== 'any';
  const ownedTitle = owned?.count
    ? wantsGender && owned.matchingGenderCount === 0
      ? `You already own ${owned.count} ${data.target} with these passives, but none are ${data.genderPreference}.`
      : `You already own ${wantsGender ? owned.matchingGenderCount : owned.count} matching ${data.target}.`
    : '';
  const ownedNotice = owned?.count
    ? `<div class="owned-notice">
        <strong>${escapeHtml(ownedTitle)}</strong>
        <span>${wantsGender ? `Gender preference: ${escapeHtml(data.genderPreference)}. ` : ''}Breeding routes are still shown in case you want another gender or more copies.</span>
      </div>`
    : '';
  const profileNotice = isAutoProfile(data.breedingProfile)
    ? `<div class="owned-notice profile-notice">
        <strong>${escapeHtml(builtInProfileLabel(data.breedingProfile))}: +${Number(data.profileWorkSpeedBonus || 0)}%</strong>
        <span>${escapeHtml(data.profileDisclaimer || `Using the highest-scoring reachable combination: ${(data.profileSelectedPassives || []).join(', ')}.`)}</span>
      </div>`
    : '';
  if (!total) {
    results.innerHTML = `${ownedNotice}<div class="empty">No path found. Try fewer desired passives or upload a fresher save.</div>`;
    return;
  }
  results.innerHTML = profileNotice + ownedNotice + groups.map(group => `
    <section class="result-group">
      <div class="group-heading">
        <h3>${escapeHtml(group.title)}</h3>
        <p>${escapeHtml(group.description || '')}</p>
      </div>
      ${group.results.length
        ? group.results.map((r, idx) => renderResultCard(r, idx, data.requestedPassives.length)).join('')
        : '<div class="empty compact">No option found for this category.</div>'}
    </section>
  `).join('');
}
const SAVED_ROUTES_KEY = 'palworldBreeding.savedRoutes.v2';
const LEGACY_SAVED_ROUTES_KEYS = ['palworldBreeding.savedRoutes.v1'];

function loadSavedRoutes() {
  try {
    LEGACY_SAVED_ROUTES_KEYS.forEach(key => localStorage.removeItem(key));
    const raw = localStorage.getItem(SAVED_ROUTES_KEY);
    state.savedRoutes = raw ? JSON.parse(raw) : [];
  } catch {
    state.savedRoutes = [];
  }
}

function persistSavedRoutes() {
  localStorage.setItem(SAVED_ROUTES_KEY, JSON.stringify(state.savedRoutes));
}

function renderSavedRoutes() {
  const select = $('savedRoutes');
  if (!select) return;
  const selectedId = select.value;
  select.innerHTML = state.savedRoutes.map(route => {
    const date = route.savedAt ? new Date(route.savedAt).toLocaleDateString() : '';
    return `<option value="${escapeHtml(route.id)}">${escapeHtml(route.name)}${date ? ` (${escapeHtml(date)})` : ''}</option>`;
  }).join('');
  if (selectedId && state.savedRoutes.some(route => route.id === selectedId)) select.value = selectedId;
  const cards = $('savedRouteCards');
  if (cards) {
    cards.innerHTML = state.savedRoutes.length ? state.savedRoutes.map(route => {
      const date = route.savedAt ? new Date(route.savedAt).toLocaleDateString() : 'No date';
      const mode = modeLabel(route.query?.mode || route.plan?.mode || 'breed');
      return `
        <button type="button" class="saved-route-card" data-saved-route="${escapeHtml(route.id)}" role="option" aria-selected="${select.value === route.id}">
          <span class="saved-route-name">${escapeHtml(route.name)}</span>
          <span class="saved-route-meta">${escapeHtml(mode)} · ${escapeHtml(date)}</span>
        </button>
      `;
    }).join('') : '<div class="empty compact">No saved plans yet.</div>';
    cards.querySelectorAll('[data-saved-route]').forEach(button => {
      button.addEventListener('click', () => {
        select.value = button.dataset.savedRoute || '';
        renderSavedRoutes();
      });
      button.addEventListener('dblclick', () => loadSavedRoute().catch(err => setStatus($('savedStatus'), `Load failed: ${err.message}`, 'bad')));
    });
  }
  if ($('savedSummaryCount')) $('savedSummaryCount').textContent = String(state.savedRoutes.length);
  const countText = `${state.savedRoutes.length}/10 saved plans`;
  setStatus($('savedStatus'), state.savedRoutes.length ? countText : 'Saved plans stay in this browser.');
}

function routeDefaultName(plan = state.plansByMode[state.mode]) {
  if (state.mode === 'base') {
    const baseName = plan?.base?.displayName || selectedBase()?.displayName || 'Base';
    const plannerMode = $('basePlannerMode')?.value || plan?.plannerMode || 'ideal';
    const modeName = plannerMode === 'right_now' ? 'Right Now' : 'Ideal';
    return `${baseName} Workforce Plan (${modeName})`;
  }
  if (state.mode === 'work') {
    const workName = plan?.selectedWorkLabel || state.workTypes.find(work => work.key === $('workType')?.value)?.label || 'Work';
    return `${workName} Suitability Browser`;
  }
  if (state.mode === 'ranch') {
    const item = state.formsByMode.ranch?.ranchItem || '';
    return item ? `${item} Ranch Producers` : 'Ranch Drops Browser';
  }
  if (state.mode === 'iv') {
    const target = plan?.target || $('target').value || 'Target';
    return `${target} IV Improvement`;
  }
  const target = plan?.target || $('target').value || 'Breeding path';
  const passives = (plan?.requestedPassives || state.selectedPassives).join(', ');
  return passives ? `${target} (${passives})` : target;
}

function updateRouteName({force = false, name = ''} = {}) {
  const input = $('routeName');
  if (!input) return;
  if (name) {
    input.value = name;
    state.lastAutoRouteName = routeDefaultName(state.plansByMode[state.mode]);
    return;
  }
  const next = routeDefaultName(state.plansByMode[state.mode]);
  const current = input.value || '';
  const canReplace = force || !current.trim() || current === state.lastAutoRouteName;
  state.lastAutoRouteName = next;
  if (canReplace) input.value = next;
}

function saveCurrentRoute() {
  const status = $('savedStatus');
  const plan = state.plansByMode[state.mode];
  if (!plan || plan.error) {
    setStatus(status, `Run ${modeLabel(state.mode)} before saving a plan.`, 'warn');
    return;
  }
  if (state.savedRoutes.length >= 10) {
    setStatus(status, 'Saved path limit reached. Delete one before saving another.', 'warn');
    return;
  }
  const nameInput = $('routeName');
  updateRouteName();
  const name = (nameInput.value || routeDefaultName(plan)).trim();
  const form = currentFormFromUi();
  const route = {
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    name,
    savedAt: new Date().toISOString(),
    query: {
      mode: state.mode,
      ...form,
      baseSettings: state.mode === 'base' ? currentBasePlannerSettings() : undefined,
    },
    plan,
  };
  state.savedRoutes.unshift(route);
  persistSavedRoutes();
  updateRouteName({force: true, name});
  renderSavedRoutes();
  setStatus(status, `Saved "${name}".`, 'good');
}

function selectedSavedRoute() {
  const id = $('savedRoutes').value;
  return state.savedRoutes.find(route => route.id === id);
}

async function loadSavedRoute() {
  const route = selectedSavedRoute();
  const status = $('savedStatus');
  if (!route) {
    setStatus(status, 'Choose a saved plan first.', 'warn');
    return;
  }
  const query = route.query || {};
  const plan = route.plan || {};
  const mode = query.mode || plan.mode || 'breed';
  const defaults = state.formsByMode[mode] || state.formsByMode.breed;
  state.formsByMode[mode] = {
    ...defaults,
    ...query,
    target: query.target || plan.target || defaults.target || '',
    passives: [...(query.passives || plan.requestedPassives || [])],
    ivGoal: query.ivGoal || plan.ivGoal || defaults.ivGoal || 'none',
  };
  if (mode === 'base' && query.baseId && query.baseSettings) {
    state.baseSettings[query.baseId] = Object.fromEntries(
      Object.entries(query.baseSettings).map(([skill, setting]) => [skill, {
        enabled: setting.enabled !== false,
        min: setting.min == null ? '' : String(setting.min),
        max: setting.max == null ? '' : String(setting.max),
      }])
    );
    state.baseSettings[query.baseId]._maxWorkers = clampWorkerCount(query.maxWorkers || 15);
    persistBaseSettings();
  }
  state.plansByMode[mode] = plan;
  state.lastPlan = plan;
  setMode(mode);
  if (mode === 'base' && !state.baseSites) await loadBasePlanner();
  applyFormToUi(state.formsByMode[mode]);
  if (mode === 'base') renderBaseSelectors();
  restoreModeView();
  updateRouteName({force: true, name: route.name});
  const rerunLabel = mode === 'base' ? 'Plan Base' : mode === 'iv' ? 'Calculate IVs' : mode === 'work' || mode === 'ranch' ? 'refresh the browser' : 'Optimize';
  setStatus(status, `Loaded "${route.name}". Re-run ${rerunLabel} if your roster changed.`, 'good');
}

function deleteSavedRoute() {
  const route = selectedSavedRoute();
  const status = $('savedStatus');
  if (!route) {
    setStatus(status, 'Choose a saved plan first.', 'warn');
    return;
  }
  state.savedRoutes = state.savedRoutes.filter(item => item.id !== route.id);
  persistSavedRoutes();
  renderSavedRoutes();
  setStatus(status, `Deleted "${route.name}".`, 'good');
}

function selectedUploadFiles() {
  const folderFiles = Array.from($('saveFolder').files || []);
  if (folderFiles.length) {
    return {label: `${folderFiles.length} folder files`, files: folderFiles};
  }
  const file = $('levelFile').files && $('levelFile').files[0];
  return file ? {label: file.name, files: [file]} : {label: '', files: []};
}

async function uploadLevel() {
  const status = $('uploadStatus');
  const button = $('uploadLevel');
  const upload = selectedUploadFiles();
  if (!upload.files.length) {
    setStatus(status, 'Choose a save folder, .zip, or Level.sav first.', 'warn');
    return;
  }
  const form = new FormData();
  for (const file of upload.files) {
    form.append('files', file, file.webkitRelativePath || file.name);
  }
  button.disabled = true;
  setStatus(status, `Uploading ${upload.label} and decoding. This usually takes 20-90 seconds...`, 'working');
  try {
    const res = await fetch(apiUrl('/api/upload-save'), {method: 'POST', body: form});
    const data = await res.json();
    if (!data.ok) {
      setStatus(status, `Decode failed: ${data.error || 'unknown error'}`, 'bad');
      console.error(data);
      return;
    }
    await loadOptions();
    const input = data.input || {};
    const source = input.levelOnly ? 'Level.sav only' : `${input.players || 0} player save(s), ${input.dps || 0} DPS save(s)`;
    const warning = data.stdout && data.stdout.includes('WARN:') ? ' DPS could not be decoded, so DPS was skipped.' : '';
    const message = `Updated from ${upload.label}: ${data.rosterCount} rows loaded (${source}).${warning}`;
    setStatus(status, message, warning ? 'warn' : 'good');
    showToast(warning ? 'Roster updated; DPS was skipped.' : 'Roster updated successfully.', warning ? 'warn' : 'good');
  } finally {
    button.disabled = false;
  }
}
function formatLiveModified(seconds) {
  if (!seconds) return 'unknown time';
  return new Date(seconds * 1000).toLocaleTimeString([], {hour: 'numeric', minute: '2-digit', second: '2-digit', hour12: true});
}

function formatLiveSyncTime(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value).replace('T', ' ');
  return date.toLocaleString([], {month: 'numeric', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', second: '2-digit', hour12: true});
}

function liveSummary(data) {
  if (!data || !data.ok) {
    const path = data?.path ? ` at ${data.path}` : '';
    return `Live save unavailable${path}.`;
  }
  if (data.refreshing) {
    return `Live save sync running: ${data.fileCount} file(s), latest change ${formatLiveModified(data.latestModified)}.`;
  }
  if (data.lastResult && !data.lastResult.ok) {
    const detail = data.lastResult.errorDetail ? `: ${data.lastResult.errorDetail}` : '';
    return `Last live save sync failed: ${data.lastResult.error || 'unknown error'}${detail}`;
  }
  const refreshed = data.lastRefreshAt ? `
Last sync ${formatLiveSyncTime(data.lastRefreshAt)}.` : '';
  return `Live save ready: ${data.fileCount} file(s), latest change ${formatLiveModified(data.latestModified)}.${refreshed}`;
}

function setLiveStatus(message, kind = '') {
  const el = $('liveStatus');
  if (el) setStatus(el, message, kind);
}

async function refreshLiveSave({force = true} = {}) {
  if (state.live.refreshing) return;
  state.live.refreshing = true;
  $('refreshLiveSave').disabled = true;
  setLiveStatus('Syncing live save from copied files...', 'working');
  try {
    const res = await fetch(apiUrl('/api/live-save/refresh'), {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({force})
    });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      const detail = data.errorDetail ? `: ${data.errorDetail}` : '';
      setLiveStatus(data.refreshing ? 'A live save sync is already running.' : `Sync failed: ${data.error || res.statusText}${detail}`, data.refreshing ? 'working' : 'bad');
      return;
    }
    if (data.skipped) {
      setLiveStatus(data.message || liveSummary(data), 'good');
      return;
    }
    await loadOptions();
    await preloadBaseSites({force: true});
    const warning = data.stdout && data.stdout.includes('WARN:');
    const skippedDps = data.input?.dpsSkipped;
    const message = `Synced live save: ${data.rosterCount} rows loaded. Run Optimize when you want to recalculate.`;
    const suffix = warning ? ' DPS failed and was skipped.' : skippedDps ? ' DPS skipped for faster breeding sync.' : '';
    setLiveStatus(`${message}${suffix}`, warning ? 'warn' : 'good');
    showToast(warning ? 'Live roster synced; DPS failed.' : skippedDps ? 'Live roster synced without DPS.' : 'Live roster synced.', warning ? 'warn' : 'good');
  } catch (err) {
    setLiveStatus(`Sync failed: ${err.message}`, 'bad');
  } finally {
    state.live.refreshing = false;
    $('refreshLiveSave').disabled = false;
  }
}

async function loadLiveSaveStatus() {
  try {
    const data = await api('/api/live-save/status');
    const wasRefreshing = state.live.sawRefreshInProgress;
    state.live.sawRefreshInProgress = Boolean(data.refreshing);
    setLiveStatus(liveSummary(data), data.refreshing ? 'working' : data.ok ? '' : 'bad');
    if (data.refreshing) {
      window.clearTimeout(state.live.statusPoll);
      state.live.statusPoll = window.setTimeout(() => loadLiveSaveStatus(), 3000);
    } else if (data.lastResult?.ok && data.lastRefreshAt && data.lastRefreshAt !== state.live.observedRefreshAt) {
      state.live.observedRefreshAt = data.lastRefreshAt;
      await loadOptions();
      if (wasRefreshing) showToast('Startup live save sync complete.', 'good');
    }
  } catch (err) {
    setLiveStatus(`Live save status failed: ${err.message}`, 'bad');
  }
}

async function loadOptions() {
  const opts = await api('/api/options');
  state.species = opts.species;
  state.passivesByOwner = opts.passivesByOwner || {};
  state.passiveMeta = opts.passiveMeta || {};
  state.speciesMeta = opts.speciesMeta || {};
  state.passives = opts.passives;
  state.owners = opts.owners;
  state.workTypes = opts.workTypes || [];
  state.implantInventory = opts.implantInventory || {};
  if (opts.baseSites?.ok) {
    state.baseSites = opts.baseSites;
  }
  fillDatalist('speciesList', opts.species);
  if ($('workType')) {
    $('workType').innerHTML = '<option value="" disabled selected>Choose work skill</option>'
      + state.workTypes.map(w => `<option value="${escapeHtml(w.key)}">${escapeHtml(w.label)}</option>`).join('');
  }
  $('owner').innerHTML = opts.owners.map(o => `<option value="${escapeHtml(o)}" ${o === state.formsByMode[state.mode].owner ? 'selected' : ''}>${escapeHtml(o)}</option>`).join('');
  renderProfileOptions(state.formsByMode[state.mode].breedingProfile || 'manual');
  applyFormToUi(state.formsByMode[state.mode]);
  updateModeVisibility(state.mode);
  if (state.baseSites?.ok) renderBaseSelectors();
  setTargetValidity(canonicalMatch(state.species, $('target')?.value || '').value ? 'valid' : '');
  $('meta').textContent = `${opts.rosterCount} Pals loaded | breeding data ${opts.dataVersion} generated ${opts.generatedAt}`;
  if (!state.baseSites?.ok) preloadBaseSites().catch(() => {});
}

async function optimize() {
  if (state.mode === 'base') { await optimizeBasePlanner(); return; }
  if (state.mode === 'iv') { await optimizeIvs(); return; }
  const target = resolveTarget();
  if (!target) return;
  saveCurrentForm();
  const activeProfile = $('breedingProfile')?.value || 'manual';
  if (state.mode === 'breed' && isAutoProfile(activeProfile)) {
    await applyBreedingProfile(activeProfile, $('owner')?.value || 'David');
  }
  if (state.mode === 'breed') warnIfInsomniaOnDarkTarget();
  const form = state.formsByMode[state.mode];
  const signature = breedSignature(form.owner, target, form.passives);
  const routePreference = state.mode === 'breed' && state.lastBreedSignature === signature ? 'continue_progress' : 'best_overall';
  const payload = {
    owner: form.owner,
    target,
    passives: form.passives,
    genderPreference: form.genderPreference,
    ivPreference: 'none',
    ivGoal: 'none',
    breedingProfile: form.breedingProfile,
    routePreference,
  };
  const optimizeButton = $('optimize');
  $('summary').textContent = 'Building breeding paths';
  $('results').innerHTML = `
    <div class="optimization-stage" role="status" aria-live="polite">
      <div class="optimization-card">
        <span class="optimization-spinner" aria-hidden="true"></span>
        <strong>Calculating the best breeding routes</strong>
        <span>Comparing clean donors, intermediate species, gender, and total breeding effort.</span>
      </div>
    </div>`;
  optimizeButton.disabled = true;
  try {
    const data = await api('/api/optimize', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    renderResults(data);
    state.lastBreedSignature = signature;
  } finally {
    optimizeButton.disabled = false;
  }
}

async function optimizeIvs() {
  const target = resolveTarget();
  if (!target) return;
  const activeProfile = $('breedingProfile')?.value || 'manual';
  if (isAutoProfile(activeProfile)) {
    await applyBreedingProfile(activeProfile, $('owner')?.value || 'David');
  }
  saveCurrentForm();
  const form = state.formsByMode.iv;
  const implantPassives = form.includeImplants === false ? [] : form.implantPassives.filter(passive => form.passives.includes(passive));
  const payload = {
    owner: form.owner,
    target,
    passives: form.passives,
    implantPassives,
    genderPreference: form.genderPreference,
    ivGoal: 'perfect',
  };
  const optimizeButton = $('optimize');
  $('summary').textContent = 'Building perfect IV breeding pairs';
  $('results').innerHTML = `
    <div class="optimization-stage" role="status" aria-live="polite">
      <div class="optimization-card">
        <span class="optimization-spinner" aria-hidden="true"></span>
        <strong>Finding same-species parent pairs</strong>
        <span>Ranking clean passive pools and duplicated 100-IV support.</span>
      </div>
    </div>`;
  optimizeButton.disabled = true;
  try {
    const data = await api('/api/improve-ivs', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    renderIvResults(data);
  } finally {
    optimizeButton.disabled = false;
  }
}

$('target').addEventListener('input', () => {
  const input = $('target');
  const hint = $('targetHint');
  if (!input.value.trim()) {
    setStatus(hint, 'Choose any target species from the breeding table.');
    setTargetValidity('');
    updateInsomniaAvailability();
    return;
  }
  const hasTrailingSpace = /\s$/.test(input.value);
  const exact = hasTrailingSpace ? '' : exactCanonicalMatch(state.species, input.value);
  const match = exact ? {value: exact} : canonicalMatch(state.species, input.value);
  if (exact) {
    if (state.mode === 'iv' && state.formsByMode.iv?.target !== exact) {
      $('ivTargetInstance').value = '';
      state.formsByMode.iv.ivTargetInstance = '';
    }
    setStatus(hint, '');
    setTargetValidity('valid');
    updateActiveForm();
    updateInsomniaAvailability();
  } else if (match.value) {
    setStatus(hint, `Press Enter to use ${match.value}.`, 'working');
    setTargetValidity('');
    updateInsomniaAvailability();
  } else if (match.reason === 'ambiguous') {
    setStatus(hint, `Matches: ${match.matches.join(', ')}. Keep typing.`, 'warn');
    setTargetValidity('');
    updateInsomniaAvailability();
    if (state.mode === 'iv') clearIvTargetChoices('Finish the exact species name before choosing a target Pal.');
  } else {
    setStatus(hint, 'No known Pal matches that text.', 'bad');
    setTargetValidity('invalid');
    updateInsomniaAvailability();
    if (state.mode === 'iv') clearIvTargetChoices('No exact species selected yet.');
  }
});
$('target').addEventListener('keydown', event => {
  if (event.key === 'Enter') { event.preventDefault(); resolveTarget(); }
});
$('addPassive').onclick = addPassive;
$('passiveInput').addEventListener('input', () => {
  const input = $('passiveInput');
  const hint = $('passiveHint');
  if (!input.value.trim()) {
    setStatus(hint, 'Pick from known passives in your loaded roster.');
    return;
  }
  const match = canonicalMatch(state.passives, input.value);
  if (match.value) {
    setStatus(hint, `Press Enter or Add to use ${match.value}.`, 'working');
  } else if (match.reason === 'ambiguous') {
    setStatus(hint, `Matches: ${match.matches.join(', ')}. Keep typing.`, 'warn');
  } else {
    setStatus(hint, 'No known passive matches that text.', 'bad');
  }
});
$('passiveInput').addEventListener('keydown', event => {
  if (event.key === 'Enter') { event.preventDefault(); addPassive(); }
});
$('clearPassives').onclick = () => {
  respectManualPassiveEdit();
  state.selectedPassives = [];
  state.selectedImplantPassives = [];
  renderPassives();
  updateActiveForm();
};
$('saveFolder').addEventListener('change', () => {
  const files = Array.from($('saveFolder').files || []);
  if (files.length) $('levelFile').value = '';
  setStatus($('uploadStatus'), files.length ? `Selected save folder with ${files.length} files. Click Upload & Refresh Roster to decode it.` : 'Choose a folder, zip, or Level.sav to import.');
});
$('levelFile').addEventListener('change', () => {
  const file = $('levelFile').files && $('levelFile').files[0];
  if (file) $('saveFolder').value = '';
  setStatus($('uploadStatus'), file ? `Selected ${file.name}. Click Upload & Refresh Roster to decode it.` : 'Choose a folder, zip, or Level.sav to import.');
});
$('uploadLevel').onclick = () => uploadLevel().catch(err => setStatus($('uploadStatus'), err.message, 'bad'));
$('refreshLiveSave').onclick = () => refreshLiveSave({force: true});
$('owner').onchange = () => {
  updatePassiveOptions();
  const profile = $('breedingProfile')?.value || 'manual';
  if ((state.mode === 'breed' || state.mode === 'iv') && isAutoProfile(profile)) applyBreedingProfile(profile, $('owner')?.value || 'David').catch(() => {});
  updateActiveForm();
  if (state.mode === 'work') loadWorkSuitability().catch(err => { $('summary').textContent = `Work browser failed: ${err.message}`; });
  if (state.mode === 'ranch') loadRanchDrops().catch(err => { $('summary').textContent = `Ranch browser failed: ${err.message}`; });
  if (state.mode === 'base') optimizeBasePlanner().catch(err => { $('summary').textContent = `Base planner failed: ${err.message}`; });
};
$('genderPreference').onchange = updateActiveForm;
$('breedingProfile').onchange = () => {
  const profile = $('breedingProfile')?.value || 'manual';
  if (profile !== 'manual') {
    applyBreedingProfile(profile, $('owner')?.value || 'David').catch(err => setStatus($('passiveHint'), err.message, 'bad'));
  } else {
    closeProfileEditor();
    setStatus($('passiveHint'), 'Manual passive selection enabled.');
    updateActiveForm();
  }
  updateProfileToolbar();
};
$('profileDropdownButton').onclick = event => {
  event.preventDefault();
  event.stopPropagation();
  const wrap = document.querySelector('.profile-select-wrap');
  setProfileDropdownOpen(!wrap?.classList.contains('open'));
};
$('profileDropdownButton').addEventListener('keydown', event => {
  if (!['ArrowDown', 'ArrowUp'].includes(event.key)) return;
  event.preventDefault();
  setProfileDropdownOpen(true);
});
$('profileDropdownMenu').addEventListener('keydown', event => {
  const options = [...$('profileDropdownMenu').querySelectorAll('.profile-dropdown-option')];
  const current = options.indexOf(document.activeElement);
  if (event.key === 'Escape') {
    event.preventDefault();
    setProfileDropdownOpen(false);
    $('profileDropdownButton')?.focus();
    return;
  }
  if (!['ArrowDown', 'ArrowUp'].includes(event.key) || !options.length) return;
  event.preventDefault();
  const direction = event.key === 'ArrowDown' ? 1 : -1;
  options[(current + direction + options.length) % options.length].focus();
});
$('ivGoal').onchange = updateActiveForm;
$('ivTargetInstance').onchange = updateActiveForm;
$('openIvTargetPicker').onclick = () => openIvTargetPicker();
$('closeIvTargetPicker').onclick = () => closeIvTargetPicker();
$('includeImplants').onchange = () => {
  renderPassives();
  updateActiveForm();
};
$('manageImplants').onclick = () => openImplantPlanner();
$('closeImplantPlanner').onclick = closeImplantPlanner;
$('saveImplantEntry').onclick = () => saveFreeformImplant().catch(err => setStatus($('implantStatus'), err.message, 'bad'));
$('implantInfinite').onchange = () => {
  $('implantCount').disabled = $('implantInfinite').checked;
};
$('workType').onchange = () => loadWorkSuitability().catch(err => { $('summary').textContent = `Work browser failed: ${err.message}`; });
$('workDisplay').onchange = () => { updateActiveForm(); if (state.plansByMode.work) renderWorkSuitability(state.plansByMode.work); };
$('workIncludeInsomnia').onchange = updateActiveForm;
$('ranchSearch').addEventListener('input', () => {
  state.formsByMode.ranch.ranchSearch = $('ranchSearch').value || '';
  if (state.plansByMode.ranch) renderRanchDrops(state.plansByMode.ranch);
  updateActiveForm();
});
$('ranchIncludeInsomnia').onchange = updateActiveForm;
$('baseSelect').onchange = () => {
  updateActiveForm();
  renderBaseSelectors();
  state.plansByMode.base = null;
  state.lastPlan = null;
  emptyModeMessage('base');
  updateRouteName();
};
$('basePlannerMode').onchange = updateActiveForm;
$('baseWorkerCount').onchange = () => {
  const base = selectedBase();
  if (!base) return;
  setBaseWorkerCount(base.id, $('baseWorkerCount').value);
  renderBaseSkillControls();
  updateActiveForm();
};
$('saveBaseLabel').onclick = () => saveBaseLabel().catch(err => showToast(`Base name failed: ${err.message}`, 'bad'));
$('modeBreed').onclick = () => activateMode('breed');
$('modeIv').onclick = () => activateMode('iv');
$('modeWork').onclick = () => {
  activateMode('work');
  if (!state.plansByMode.work) loadWorkSuitability().catch(err => { $('summary').textContent = `Work browser failed: ${err.message}`; });
};
$('modeRanch').onclick = () => {
  activateMode('ranch');
  if (!state.plansByMode.ranch) loadRanchDrops().catch(err => { $('summary').textContent = `Ranch browser failed: ${err.message}`; });
};
$('modeBase').onclick = () => {
  activateMode('base');
  if (!state.baseSites?.ok) loadBasePlanner().catch(err => { $('summary').textContent = `Base planner failed: ${err.message}`; });
};
$('navBack').onclick = () => navigateModeHistory('back');
$('navForward').onclick = () => navigateModeHistory('forward');
$('optimize').onclick = () => optimize().catch(err => {
  $('summary').textContent = `Optimize failed: ${err.message}`;
});
$('reloadBtn').onclick = async () => {
  await api('/api/reload');
  state.baseSites = null;
  await loadOptions();
  await preloadBaseSites({force: true});
};
$('saveRoute').onclick = saveCurrentRoute;
$('loadRoute').onclick = () => loadSavedRoute().catch(err => setStatus($('savedStatus'), `Load failed: ${err.message}`, 'bad'));
$('deleteRoute').onclick = deleteSavedRoute;
$('addProfile').onclick = () => openProfileEditor(null);
$('editProfile').onclick = () => {
  openProfileEditor(customProfileByValue($('breedingProfile')?.value || ''));
};
$('closeProfileEditor').onclick = closeProfileEditor;
$('profileModal').addEventListener('click', event => {
  if (event.target === $('profileModal')) closeProfileEditor();
});
$('ivTargetModal').addEventListener('click', event => {
  if (event.target === $('ivTargetModal')) closeIvTargetPicker();
});
$('implantModal').addEventListener('click', event => {
  if (event.target === $('implantModal')) closeImplantPlanner();
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') setProfileDropdownOpen(false);
  if (event.key === 'Escape' && !$('profileModal')?.classList.contains('hidden')) closeProfileEditor();
  if (event.key === 'Escape' && !$('ivTargetModal')?.classList.contains('hidden')) closeIvTargetPicker();
  if (event.key === 'Escape' && !$('implantModal')?.classList.contains('hidden')) closeImplantPlanner();
});
document.addEventListener('click', event => {
  if (!event.target.closest('.profile-select-wrap')) setProfileDropdownOpen(false);
});
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
$('addProfilePassive').onclick = addProfilePassive;
$('profilePassiveInput').addEventListener('keydown', event => {
  if (event.key === 'Enter') { event.preventDefault(); addProfilePassive(); }
});
$('useCurrentPassives').onclick = () => {
  state.editingProfilePassives = [...state.selectedPassives].slice(0, 4);
  renderProfileEditorPassives();
  setStatus($('profileStatus'), 'Copied current target passives into this profile.', 'good');
};
$('saveProfile').onclick = saveProfile;
$('deleteProfile').onclick = deleteProfile;
loadCustomProfiles();
loadBuiltInProfileNames();
renderProfileOptions();
loadSavedRoutes();
loadBaseSettings();
restoreControlsWidth();
initControlsResize();
renderSavedRoutes();
initTheme();
const initialMode = window.PALS_INITIAL_MODE || 'breed';
if (initialMode !== 'breed') setMode(initialMode, {recordHistory: false});
else emptyModeMessage('breed');
updateHistoryNav();
updateRouteName();

loadOptions().catch(err => {
  $('meta').textContent = err.message;
});
loadLiveSaveStatus();
