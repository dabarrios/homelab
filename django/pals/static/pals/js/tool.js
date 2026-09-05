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
let savedBreedingPlans = [];
let loadedBreedingPlanId = '';
let restoredFormState = false;
let restoredResult = false;
let lastBreedingResult = null;
let lastRenderedResult = null;

const CUSTOM_PROFILES_KEY = 'pals.customProfiles.v1';
const BUILT_IN_PROFILE_NAMES_KEY = 'pals.builtInProfileNames.v1';
const SAVED_BREEDING_PLANS_KEY = 'pals.savedBreedingPlans.v1';
const MODULE_FORM_STATE_KEY = `pals.formState.${moduleKey}.v1`;
const BUILT_IN_PROFILES = [
  {value: 'manual', label: 'Manual passives', locked: false},
  {value: 'work_speed', label: 'Best work speed', locked: true},
  {value: 'ranch_drops_focus', label: 'Ranch drops focus', locked: true},
];
const BUILT_IN_PROFILE_PASSIVES = {
  work_speed: [
    ['Demon’s Hand', 90],
    ['Remarkable Craftsmanship', 75],
    ['Artisan', 50],
    ['Work Slave', 30],
  ],
  ranch_drops_focus: [
    ['Ranch Master', 0],
    ['Farmhand', 0],
    ['Remarkable Craftsmanship', 75],
    ['Artisan', 50],
  ],
};
const DEFAULT_PASSIVE_HINTS = {
  breeding: {
    passives: 'Pick from known passives in your loaded roster.',
  },
  ivs: {
    passives: 'Every selected passive is bred naturally unless added below.',
  },
};
const POSITIVE_PASSIVE_FALLBACKS = new Set([
  "Demon's Hand",
  "Demon’s Hand",
]);
const GOLD_PASSIVE_FALLBACKS = new Set([
  'Farmhand',
]);

function apiUrl(path) {
  return `${apiBase}${path.startsWith('/') ? path : `/${path}`}`;
}

function assetUrl(path) {
  if (!path || !path.startsWith('/assets/pals/')) return path;
  return `${assetBase}/${encodeURIComponent(path.split('/').pop())}`;
}

async function api(path, fetchOptions = {}) {
  const headers = new Headers(fetchOptions.headers);
  const method = (fetchOptions.method || 'GET').toUpperCase();
  if (!['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method)) {
    const token = document.querySelector('meta[name="csrf-token"]')?.content;
    if (!token) throw new Error('Refresh this page before submitting changes.');
    headers.set('X-CSRFToken', token);
  }
  const response = await fetch(apiUrl(path), {...fetchOptions, headers, credentials: 'same-origin', mode: 'same-origin'});
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

function postJson(path, payload) {
  return api(path, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload),
  });
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
  if (POSITIVE_PASSIVE_FALLBACKS.has(passive)) return 'positive';
  if (GOLD_PASSIVE_FALLBACKS.has(passive)) return 'gold';
  return options.passiveMeta?.[passive]?.tone || 'neutral';
}

function passiveDescription(passive) {
  return options.passiveMeta?.[passive]?.desc || 'No description available.';
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

function displayPassives(node, isRoot = false, plan = null) {
  if (isRoot && plan?.finalPassives?.length) return plan.finalPassives;
  return (isRoot || node.parents?.length) ? (node.desired || []) : (node.passives || []);
}

function displayJunk(node, isRoot = false) {
  return (isRoot || node.parents?.length) ? [] : (node.junk || []);
}

function passiveBarHtml(passive, {implant = false, junk = false} = {}) {
  const tone = passiveTone(passive);
  const suffix = implant
    ? `<em class="implant-badge">${lucideIconHtml('dna', 'passive-badge-svg')}<span>Implant</span></em>`
    : junk ? `<em class="junk-badge">${lucideIconHtml('trash-2', 'passive-badge-svg')}<span>Junk</span></em>` : '';
  return `<span class="passive-bar ${implant ? 'implant-missing' : ''} ${tone}" tabindex="0" data-passive-tooltip="${escapeHtml(passive)}"><span>${escapeHtml(passive)}</span>${suffix}</span>`;
}

function renderPassiveBars(node, isRoot = false, plan = null) {
  const implantPassives = new Set(plan?.implantPassives || []);
  const naturalPassives = isRoot && plan?.finalPassives?.length
    ? (plan.finalPassives || []).filter(passive => !implantPassives.has(passive))
    : displayPassives(node, isRoot, plan);
  const plannedImplants = (isRoot || node.parents?.length)
    ? (plan?.finalPassives || []).filter(passive => implantPassives.has(passive))
    : [];
  const passives = isRoot ? naturalPassives : displayPassives(node, isRoot, plan);
  const junk = new Set(displayJunk(node, isRoot));
  const naturalLabel = node.parents?.length && !isRoot ? '<span class="passive-list-label">Needs</span>' : '';
  const naturalBars = passives.map(passive => passiveBarHtml(passive, {junk: junk.has(passive)})).join('');
  const implantRow = plannedImplants.length
    ? `<div class="passive-list passive-list-labeled implant-plan"><span class="passive-list-label">Implant</span><span class="passive-list-items">${plannedImplants.map(passive => passiveBarHtml(passive, {implant: true})).join('')}</span></div>`
    : '';
  const extraHint = node.parents?.length && plannedImplants.length
    ? '<div class="breed-passive-hint">Extra passives OK - replaceable by implants.</div>'
    : '';
  const emptyText = !isRoot && !node.parents?.length ? 'No passives' : 'No natural passives needed';
  const naturalRow = passives.length
    ? `<div class="passive-list ${naturalLabel ? 'passive-list-labeled' : ''}">${naturalLabel}${naturalLabel ? `<span class="passive-list-items">${naturalBars}</span>` : naturalBars}</div>`
    : `<div class="passive-list empty-passives">${emptyText}</div>`;
  return `${naturalRow}${implantRow}${extraHint}`;
}

function renderTypeChips(types = []) {
  return types.length ? `<div class="type-row">${types.map(type => `<span>${escapeHtml(type)}</span>`).join('')}</div>` : '';
}

function speciesMeta(name) {
  return options.speciesMeta?.[name] || {};
}

function speciesMatches(query) {
  const normalized = String(query || '').trim().toLowerCase();
  if (!normalized) return [];
  return (options.species || [])
    .filter(value => value.toLowerCase().includes(normalized))
    .slice(0, 8);
}

function exactSpeciesName(value) {
  const normalized = String(value || '').trim().toLowerCase();
  if (!normalized) return '';
  return (options.species || []).find(species => species.toLowerCase() === normalized) || '';
}

function speciesAvatarHtml(name) {
  const meta = speciesMeta(name);
  if (meta.icon) {
    return `<img src="${escapeHtml(assetUrl(meta.icon))}" alt="">`;
  }
  return `<span>${escapeHtml(speciesInitials(name))}</span>`;
}

function renderSpeciesSuggestion(name) {
  const meta = speciesMeta(name);
  return `
    <button type="button" class="species-suggest-row" data-suggest-value="${escapeHtml(name)}">
      <span class="species-suggest-avatar">${speciesAvatarHtml(name)}</span>
      <span class="species-suggest-copy">
        <span>${escapeHtml(name)}</span>
        ${renderTypeChips(meta.types || [])}
      </span>
    </button>`;
}

function ensureSpeciesSelectedTypes(field) {
  let selected = field.querySelector('[data-species-selected]');
  if (selected) return selected;
  selected = document.createElement('span');
  selected.className = 'species-selected-types hidden';
  selected.dataset.speciesSelected = '';
  field.append(selected);
  return selected;
}

function ensureSpeciesSelectedAvatar(field) {
  let selected = field.querySelector('[data-species-avatar]');
  if (selected) return selected;
  selected = document.createElement('span');
  selected.className = 'species-selected-avatar hidden';
  selected.dataset.speciesAvatar = '';
  field.prepend(selected);
  return selected;
}

function updateSpeciesSelection(field) {
  if (field.dataset.suggest !== 'species') return;
  const input = field.querySelector('[data-suggest-input]');
  const selected = ensureSpeciesSelectedTypes(field);
  const avatar = ensureSpeciesSelectedAvatar(field);
  const species = exactSpeciesName(input?.value || '');
  if (!species) {
    selected.innerHTML = '';
    avatar.innerHTML = '';
    selected.classList.add('hidden');
    avatar.classList.add('hidden');
    field.classList.remove('has-species-type');
    field.classList.remove('has-species-avatar');
    return;
  }
  const meta = speciesMeta(species);
  avatar.innerHTML = speciesAvatarHtml(species);
  avatar.classList.remove('hidden');
  selected.innerHTML = renderTypeChips(meta.types || []);
  selected.classList.toggle('hidden', !(meta.types || []).length);
  field.classList.toggle('has-species-type', (meta.types || []).length > 0);
  field.classList.add('has-species-avatar');
  clearSpeciesWarning(field);
}

function updateAllSpeciesSelections() {
  $$('[data-suggest="species"]').forEach(updateSpeciesSelection);
}

function clearSpeciesWarning(field) {
  const input = field.querySelector('[data-suggest-input]');
  const warning = field.parentElement?.querySelector('[data-species-warning]');
  input?.removeAttribute('aria-invalid');
  field.classList.remove('is-invalid');
  warning?.classList.add('hidden');
}

function showSpeciesWarning(field, message) {
  const input = field.querySelector('[data-suggest-input]');
  let warning = field.parentElement?.querySelector('[data-species-warning]');
  if (!warning) {
    warning = document.createElement('span');
    warning.className = 'field-hint invalid species-warning hidden';
    warning.dataset.speciesWarning = '';
    warning.setAttribute('role', 'alert');
    field.parentElement?.append(warning);
  }
  input?.setAttribute('aria-invalid', 'true');
  field.classList.add('is-invalid');
  warning.innerHTML = `<span aria-hidden="true">!</span><span>${escapeHtml(message)}</span>`;
  warning.title = message;
  warning.classList.remove('hidden');
}

function validateTargetSpecies() {
  const targetInput = document.querySelector('[name="target"]');
  if (!targetInput) return true;
  const field = targetInput.closest('[data-suggest="species"]');
  if (!field) return true;
  const value = String(targetInput.value || '').trim();
  if (!value) {
    showSpeciesWarning(field, 'Choose a target Pal before running this tool.');
    return false;
  }
  if (exactSpeciesName(value)) {
    updateSpeciesSelection(field);
    return true;
  }
  const matches = speciesMatches(value);
  const suffix = matches.length
    ? ` Did you mean ${matches.slice(0, 3).join(', ')}?`
    : ' Start typing and choose a Pal from the list.';
  showSpeciesWarning(field, `Unknown target species: ${value}.${suffix}`);
  return false;
}

function validateSpeciesFieldOnExit(field) {
  if (field.dataset.suggest !== 'species') return;
  const input = field.querySelector('[data-suggest-input]');
  const value = String(input?.value || '').trim();
  if (!value) {
    clearSpeciesWarning(field);
    return;
  }
  if (exactSpeciesName(value)) {
    updateSpeciesSelection(field);
    return;
  }
  const matches = speciesMatches(value);
  const suffix = matches.length
    ? ` Did you mean ${matches.slice(0, 3).join(', ')}?`
    : ' Start typing and choose a Pal from the list.';
  showSpeciesWarning(field, `Unknown target species: ${value}.${suffix}`);
  showEmptyState();
  setText('#toolStatus', 'Check the target species.');
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
    features: [
      ['Optimized Path', 'Finds a practical route to collect your desired passives.'],
      ['Resource Aware', 'Uses owned Pals and implant inventory when enabled.'],
      ['Multiple Routes', 'Compares clean, fast, and practical breeding options.'],
    ],
  },
  ivs: {
    title: 'Find IV parents',
    lead: 'Pick a target Pal and final passives to compare parent pairs.',
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

const EMPTY_STATE_ICON_NAMES = {
  breeding: 'git-fork',
  ivs: 'dna',
  work: 'wrench',
  ranch: 'candy',
  bases: 'castle',
};

const WORK_FEATURE_ICONS = {
  'Best Overall Pick': 'star',
  'Best Dark-Type Pick': 'moon',
  'Condensed Levels': 'layers',
  'Breed From Here': 'network',
};

const BREEDING_FEATURE_ICONS = {
  'Optimized Path': 'route',
  'Resource Aware': 'package-check',
  'Multiple Routes': 'git-fork',
};

const RANCH_FEATURE_ICONS = {
  'Best Rancher': 'award',
  'All Drop Sources': 'package-open',
  'Breed From Here': 'network',
};

const IV_FEATURE_ICONS = {
  'Parent Coverage': 'heart-handshake',
  'Implant Aware': 'syringe',
  'Junk Tracking': 'trash-2',
};

const BASE_STEP_ICONS = {
  sites: 'search',
  rules: 'settings-2',
  team: 'users-round',
  best: 'crown',
};

const BASE_FEATURE_ICONS = {
  'Optimal Team': 'users-round',
  'Role Coverage': 'badge-check',
  Alternatives: 'shuffle',
  'Breeding Path': 'network',
};

const LUCIDE_ICON_PATHS = {
  'git-fork': `
    <circle cx="12" cy="18" r="3"></circle>
    <circle cx="6" cy="6" r="3"></circle>
    <circle cx="18" cy="6" r="3"></circle>
    <path d="M18 9v2c0 .6-.4 1-1 1H7c-.6 0-1-.4-1-1V9"></path>
    <path d="M12 12v3"></path>
  `,
  award: `
    <path d="m15.477 12.89 1.515 8.526a.5.5 0 0 1-.81.47l-3.58-2.687a1 1 0 0 0-1.197 0l-3.586 2.686a.5.5 0 0 1-.81-.469l1.514-8.526"></path>
    <circle cx="12" cy="8" r="6"></circle>
  `,
  'package-open': `
    <path d="M12 22v-9"></path>
    <path d="M15.17 2.21a1.67 1.67 0 0 1 1.63 0L21 4.57a1.93 1.93 0 0 1 0 3.36L8.82 14.79a1.655 1.655 0 0 1-1.64 0L3 12.43a1.93 1.93 0 0 1 0-3.36z"></path>
    <path d="M20 13v3.87a2.06 2.06 0 0 1-1.11 1.83l-6 3.08a1.93 1.93 0 0 1-1.78 0l-6-3.08A2.06 2.06 0 0 1 4 16.87V13"></path>
    <path d="M21 12.43a1.93 1.93 0 0 0 0-3.36L8.83 2.2a1.64 1.64 0 0 0-1.63 0L3 4.57a1.93 1.93 0 0 0 0 3.36l12.18 6.86a1.636 1.636 0 0 0 1.63 0z"></path>
  `,
  route: `
    <circle cx="6" cy="19" r="3"></circle>
    <path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15"></path>
    <circle cx="18" cy="5" r="3"></circle>
  `,
  'package-check': `
    <path d="M12 22V12"></path>
    <path d="m16 17 2 2 4-4"></path>
    <path d="M21 11.127V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.729l7 4a2 2 0 0 0 2 .001l1.32-.753"></path>
    <path d="M3.29 7 12 12l8.71-5"></path>
    <path d="m7.5 4.27 8.997 5.148"></path>
  `,
  star: `
    <path d="M11.525 2.295a.53.53 0 0 1 .95 0l2.31 4.679a2.123 2.123 0 0 0 1.595 1.16l5.166.756a.53.53 0 0 1 .294.904l-3.736 3.638a2.123 2.123 0 0 0-.611 1.878l.882 5.14a.53.53 0 0 1-.771.56l-4.618-2.428a2.122 2.122 0 0 0-1.973 0L6.396 21.01a.53.53 0 0 1-.77-.56l.881-5.139a2.122 2.122 0 0 0-.611-1.879L2.16 9.795a.53.53 0 0 1 .294-.906l5.165-.755a2.122 2.122 0 0 0 1.597-1.16z"></path>
  `,
  moon: `
    <path d="M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 8.268 8.268c.344-.215.825-.004.803.401"></path>
  `,
  'trash-2': `
    <path d="M10 11v6"></path>
    <path d="M14 11v6"></path>
    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"></path>
    <path d="M3 6h18"></path>
    <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
  `,
  'circle-check-big': `
    <path d="M21.801 10A10 10 0 1 1 17 3.335"></path>
    <path d="m9 11 3 3L22 4"></path>
  `,
  'circle-off': `
    <path d="m2 2 20 20"></path>
    <path d="M8.35 2.69a10 10 0 0 1 12.96 12.96"></path>
    <path d="M19.08 19.08A10 10 0 1 1 4.92 4.92"></path>
  `,
  'list-checks': `
    <path d="m3 7 2 2 4-4"></path>
    <path d="m3 17 2 2 4-4"></path>
    <path d="M13 6h8"></path>
    <path d="M13 12h8"></path>
    <path d="M13 18h8"></path>
  `,
  'cake-slice': `
    <path d="M16 13H3"></path>
    <path d="M16 17H3"></path>
    <path d="M7 21h10a4 4 0 0 0 4-4V7a2 2 0 0 0-2-2h-2.07a2 2 0 0 1-1.66-.9l-.54-.8a2 2 0 0 0-3.32 0l-.54.8A2 2 0 0 1 9.21 5H7a4 4 0 0 0-4 4v8a4 4 0 0 0 4 4Z"></path>
    <path d="M7 8v.01"></path>
    <path d="M11 8v.01"></path>
    <path d="M15 8v.01"></path>
  `,
  egg: `
    <path d="M12 22c6.23-.05 9.96-6.55 6.89-12.23L13.4 2.85a1.64 1.64 0 0 0-2.8 0L5.1 9.77C2.04 15.45 5.77 21.95 12 22Z"></path>
  `,
  'map-pin': `
    <path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"></path>
    <circle cx="12" cy="10" r="3"></circle>
  `,
  info: `
    <circle cx="12" cy="12" r="10"></circle>
    <path d="M12 16v-4"></path>
    <path d="M12 8h.01"></path>
  `,
  crosshair: `
    <circle cx="12" cy="12" r="10"></circle>
    <line x1="22" x2="18" y1="12" y2="12"></line>
    <line x1="6" x2="2" y1="12" y2="12"></line>
    <line x1="12" x2="12" y1="6" y2="2"></line>
    <line x1="12" x2="12" y1="22" y2="18"></line>
  `,
  'arrow-right-circle': `
    <circle cx="12" cy="12" r="10"></circle>
    <path d="M8 12h8"></path>
    <path d="m12 8 4 4-4 4"></path>
  `,
  'triangle-alert': `
    <path d="m21.73 18-8-14a2 2 0 0 0-3.46 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"></path>
    <path d="M12 9v4"></path>
    <path d="M12 17h.01"></path>
  `,
  flag: `
    <path d="M4 22V4a1 1 0 0 1 .4-.8C5.733 2.2 7.067 2.2 8.4 3.2c1.333 1 2.667 1 4 0 1.333-1 2.667-1 4 0 1.333 1 2.667 1 4 0A1 1 0 0 1 22 4v11a1 1 0 0 1-.4.8c-1.333 1-2.667 1-4 0-1.333-1-2.667-1-4 0-1.333 1-2.667 1-4 0-1.333-1-2.667-1-4 0A1 1 0 0 0 4 16.6"></path>
  `,
  'circle-check': `
    <circle cx="12" cy="12" r="10"></circle>
    <path d="m16 9-5.5 5.5L8 12"></path>
  `,
  'badge-check': `
    <path d="M3.85 8.62a4 4 0 0 1 4.78-4.77 4 4 0 0 1 6.74 0 4 4 0 0 1 4.78 4.78 4 4 0 0 1 0 6.74 4 4 0 0 1-4.77 4.78 4 4 0 0 1-6.75 0 4 4 0 0 1-4.78-4.77 4 4 0 0 1 0-6.76Z"></path>
    <path d="m16 9-5.5 5.5L8 12"></path>
  `,
  'heart-handshake': `
    <path d="M19.414 14.414C21 12.828 22 11.5 22 9.5a5.5 5.5 0 0 0-9.591-3.676.6.6 0 0 1-.818.001A5.5 5.5 0 0 0 2 9.5c0 2.3 1.5 4 3 5.5l5.535 5.362a2 2 0 0 0 2.879.052 2.12 2.12 0 0 0-.004-3 2.124 2.124 0 1 0 3-3 2.124 2.124 0 0 0 3.004 0 2 2 0 0 0 0-2.828l-1.881-1.882a2.41 2.41 0 0 0-3.409 0l-1.71 1.71a2 2 0 0 1-2.828 0 2 2 0 0 1 0-2.828l2.823-2.762"></path>
  `,
  syringe: `
    <path d="m18 2 4 4"></path>
    <path d="m17 7 3-3"></path>
    <path d="M19 9 8.7 19.3c-1 1-2.5 1-3.4 0l-.6-.6c-1-1-1-2.5 0-3.4L15 5"></path>
    <path d="m9 11 4 4"></path>
    <path d="m5 19-3 3"></path>
    <path d="m14 4 6 6"></path>
  `,
  dna: `
    <path d="m10 16 1.5 1.5"></path>
    <path d="m14 8-1.5-1.5"></path>
    <path d="M15 2c-1.798 1.998-2.518 3.995-2.807 5.993"></path>
    <path d="m16.5 10.5 1 1"></path>
    <path d="m17 6-2.891-2.891"></path>
    <path d="M2 15c6.667-6 13.333 0 20-6"></path>
    <path d="m20 9 .891.891"></path>
    <path d="M3.109 14.109 4 15"></path>
    <path d="m6.5 12.5 1 1"></path>
    <path d="m7 18 2.891 2.891"></path>
    <path d="M9 22c1.798-1.998 2.518-3.995 2.807-5.993"></path>
  `,
  search: `
    <path d="m21 21-4.34-4.34"></path>
    <circle cx="11" cy="11" r="8"></circle>
  `,
  'settings-2': `
    <path d="M14 17H5"></path>
    <path d="M19 7h-9"></path>
    <circle cx="17" cy="17" r="3"></circle>
    <circle cx="7" cy="7" r="3"></circle>
  `,
  'users-round': `
    <path d="M18 21a8 8 0 0 0-16 0"></path>
    <circle cx="10" cy="8" r="5"></circle>
    <path d="M22 20c0-3.37-2-6.5-4-8a5 5 0 0 0-.45-8.3"></path>
  `,
  shuffle: `
    <path d="m18 14 4 4-4 4"></path>
    <path d="m18 2 4 4-4 4"></path>
    <path d="M2 18h1.973a4 4 0 0 0 3.3-1.7l5.454-8.6a4 4 0 0 1 3.3-1.7H22"></path>
    <path d="M2 6h1.972a4 4 0 0 1 3.6 2.2"></path>
    <path d="M22 18h-6.041a4 4 0 0 1-3.3-1.8l-.359-.45"></path>
  `,
  network: `
    <rect x="16" y="16" width="6" height="6" rx="1"></rect>
    <rect x="2" y="16" width="6" height="6" rx="1"></rect>
    <rect x="9" y="2" width="6" height="6" rx="1"></rect>
    <path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3"></path>
    <path d="M12 12V8"></path>
  `,
  crown: `
    <path d="M11.562 3.266a.5.5 0 0 1 .876 0L15.39 8.87a1 1 0 0 0 1.516.294L21.183 5.5a.5.5 0 0 1 .798.519l-2.834 10.246a1 1 0 0 1-.956.734H5.81a1 1 0 0 1-.957-.734L2.02 6.02a.5.5 0 0 1 .798-.519l4.276 3.664a1 1 0 0 0 1.516-.294z"></path>
    <path d="M5 21h14"></path>
  `,
  layers: `
    <path d="M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83z"></path>
    <path d="M2 12a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 12"></path>
    <path d="M2 17a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 17"></path>
  `,
  'corner-right-up': `
    <path d="m10 9 5-5 5 5"></path>
    <path d="M4 20h7a4 4 0 0 0 4-4V4"></path>
  `,
  wrench: `
    <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.106-3.105c.32-.322.863-.22.983.218a6 6 0 0 1-8.259 7.057l-7.91 7.91a1 1 0 0 1-2.999-3l7.91-7.91a6 6 0 0 1 7.057-8.259c.438.12.54.662.219.984z"></path>
  `,
  candy: `
    <path d="M10 7v10.9"></path>
    <path d="M14 6.1V17"></path>
    <path d="M16 7V3a1 1 0 0 1 1.707-.707 2.5 2.5 0 0 0 2.152.717 1 1 0 0 1 1.131 1.131 2.5 2.5 0 0 0 .717 2.152A1 1 0 0 1 21 8h-4"></path>
    <path d="M16.536 7.465a5 5 0 0 0-7.072 0l-2 2a5 5 0 0 0 0 7.07 5 5 0 0 0 7.072 0l2-2a5 5 0 0 0 0-7.07"></path>
    <path d="M8 17v4a1 1 0 0 1-1.707.707 2.5 2.5 0 0 0-2.152-.717 1 1 0 0 1-1.131-1.131 2.5 2.5 0 0 0-.717-2.152A1 1 0 0 1 3 16h4"></path>
  `,
  castle: `
    <path d="M10 5V3"></path>
    <path d="M14 5V3"></path>
    <path d="M15 21v-3a3 3 0 0 0-6 0v3"></path>
    <path d="M18 3v8"></path>
    <path d="M18 5H6"></path>
    <path d="M22 11H2"></path>
    <path d="M22 9v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9"></path>
    <path d="M6 3v8"></path>
  `,
};

function lucideIconHtml(name, className = 'empty-state-svg') {
  const iconPaths = LUCIDE_ICON_PATHS[name] || LUCIDE_ICON_PATHS['git-fork'];
  return `<svg class="${escapeHtml(className)}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${iconPaths}</svg>`;
}

function emptyStateIconHtml(key) {
  const iconName = EMPTY_STATE_ICON_NAMES[key] || EMPTY_STATE_ICON_NAMES.breeding;
  return lucideIconHtml(iconName);
}

function emptyStateHtml(key = moduleKey) {
  const stateKey = EMPTY_STATES[key] ? key : 'breeding';
  const state = EMPTY_STATES[stateKey];
  const focusedState = stateKey === 'work' ? `
    <div class="empty-hero empty-focused-hero">
      <div class="empty-work-state">
        <div class="empty-tool-icon empty-state-icon empty-state-icon-work" aria-hidden="true">${emptyStateIconHtml('work')}</div>
        <h3>${escapeHtml(state.title)}</h3>
        <p>${escapeHtml(state.lead)}</p>
        <div class="empty-work-divider"><span></span><b class="empty-divider-work-mark"></b><span></span></div>
        <div class="empty-work-features empty-work-features-wide">
          ${state.features.map(([title, text]) => `<div><i class="empty-feature-icon empty-feature-lucide" aria-hidden="true">${lucideIconHtml(WORK_FEATURE_ICONS[title] || 'star', 'empty-feature-svg')}</i><b>${escapeHtml(title)}</b><span>${escapeHtml(text)}</span></div>`).join('')}
        </div>
        <p class="empty-hint">${escapeHtml(state.hint)}</p>
      </div>
    </div>` : stateKey === 'ranch' ? `
    <div class="empty-hero empty-focused-hero">
      <div class="empty-ranch-state">
        <div class="empty-ranch-icon empty-state-icon empty-state-icon-ranch" aria-hidden="true">${emptyStateIconHtml('ranch')}</div>
        <h3>${escapeHtml(state.title)}</h3>
        <p>${escapeHtml(state.lead)}</p>
        <div class="empty-work-divider empty-ranch-divider"><span></span><b>◇</b><span></span></div>
        <div class="empty-work-features empty-ranch-features">
          ${state.features.map(([title, text]) => `<div><i class="empty-feature-icon empty-feature-lucide empty-ranch-feature-lucide" aria-hidden="true">${lucideIconHtml(RANCH_FEATURE_ICONS[title] || 'award', 'empty-feature-svg')}</i><b>${escapeHtml(title)}</b><span>${escapeHtml(text)}</span></div>`).join('')}
        </div>
        <p class="empty-hint">${escapeHtml(state.hint)}</p>
      </div>
    </div>` : stateKey === 'bases' ? `
    <div class="empty-hero empty-focused-hero empty-bases-hero">
      <div class="empty-bases-state">
        <div class="empty-bases-icon empty-state-icon empty-state-icon-bases" aria-hidden="true">${emptyStateIconHtml('bases')}</div>
        <h3>${escapeHtml(state.title)}</h3>
        <p>${escapeHtml(state.lead)}</p>
        <p>Then click Build Best Team to see the optimal lineup.</p>
        <div class="empty-base-flow" aria-hidden="true">
          <div class="empty-base-step empty-base-step-sites"><i class="empty-base-step-icon">${lucideIconHtml(BASE_STEP_ICONS.sites, 'empty-base-step-svg')}</i><b>1. Detect Base Sites</b><span>Read your base structure and work sites.</span></div>
          <em></em>
          <div class="empty-base-step empty-base-step-rules"><i class="empty-base-step-icon">${lucideIconHtml(BASE_STEP_ICONS.rules, 'empty-base-step-svg')}</i><b>2. Apply Constraints</b><span>Your team mode and worker count guide the build.</span></div>
          <em></em>
          <div class="empty-base-step empty-base-step-team"><i class="empty-base-step-icon">${lucideIconHtml(BASE_STEP_ICONS.team, 'empty-base-step-svg')}</i><b>3. Optimize Team</b><span>Analyze all Pals to find the best combination.</span></div>
          <em></em>
          <div class="empty-base-step empty-base-step-best"><i class="empty-base-step-icon">${lucideIconHtml(BASE_STEP_ICONS.best, 'empty-base-step-svg')}</i><b>4. Best Team</b><span>Get role coverage and breeding handoffs.</span></div>
        </div>
        <div class="empty-work-features empty-base-features empty-work-features-wide">
          ${state.features.map(([title, text]) => `<div><i class="empty-feature-icon empty-feature-lucide empty-base-feature-lucide" aria-hidden="true">${lucideIconHtml(BASE_FEATURE_ICONS[title] || 'users-round', 'empty-feature-svg')}</i><b>${escapeHtml(title)}</b><span>${escapeHtml(text)}</span></div>`).join('')}
        </div>
        <p class="empty-hint">${escapeHtml(state.hint)}</p>
      </div>
    </div>` : '';
  if (focusedState) return focusedState;
  const splitFeatureIcons = stateKey === 'breeding' ? BREEDING_FEATURE_ICONS : stateKey === 'ivs' ? IV_FEATURE_ICONS : null;
  const featureHtml = splitFeatureIcons
    ? `
      <div class="empty-work-divider empty-split-divider empty-${stateKey}-divider"><span></span><b>${emptyStateIconHtml(stateKey)}</b><span></span></div>
      <div class="empty-work-features empty-split-features empty-${stateKey}-features">
        ${state.features.map(([title, text]) => `<div><i class="empty-feature-icon empty-feature-lucide empty-${stateKey}-feature-lucide" aria-hidden="true">${lucideIconHtml(splitFeatureIcons[title] || 'git-fork', 'empty-feature-svg')}</i><b>${escapeHtml(title)}</b><span>${escapeHtml(text)}</span></div>`).join('')}
      </div>`
    : `
      <div class="empty-features">
        ${state.features.map(([title, text]) => `<div><b>${escapeHtml(title)}</b><span>${escapeHtml(text)}</span></div>`).join('')}
      </div>`;
  const diagram = stateKey === 'ivs' ? `
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
          <span>HP <em>100</em></span>
          <span>Attack <em>100</em></span>
          <span>Defense <em>100</em></span>
        </div>
        <div class="empty-goal-card">
          <strong>Goal</strong>
          <span>Max IVs in selected stats</span>
          <i>☆ ☆ ☆ ☆ ☆</i>
        </div>
      </div>` : `
      <div class="empty-diagram">
        <div class="empty-card">
          <strong>${stateKey === 'work' ? 'Candidate A' : stateKey === 'ranch' ? 'Producer A' : 'Parent A'}</strong>
          <i></i><i></i><i></i>
        </div>
        <div class="empty-plus">+</div>
        <div class="empty-card">
          <strong>${stateKey === 'work' ? 'Candidate B' : stateKey === 'ranch' ? 'Producer B' : 'Parent B'}</strong>
          <i></i><i></i><i></i>
        </div>
        <div class="empty-arrow"></div>
        <div class="empty-target"><strong>${stateKey === 'bases' ? 'Base Team' : stateKey === 'work' ? 'Best Pick' : stateKey === 'ranch' ? 'Selected Drop' : 'Target Pal'}</strong><span>?</span></div>
      </div>`;
  return `
    <div class="empty-hero">
      <div class="empty-icon empty-state-icon empty-state-icon-${stateKey}" aria-hidden="true">${emptyStateIconHtml(stateKey)}</div>
      <h3>${escapeHtml(state.title)}</h3>
      <p>${escapeHtml(state.lead)}</p>
      ${diagram}
      ${featureHtml}
      ${splitFeatureIcons ? '' : `<p class="empty-hint">${escapeHtml(state.hint)}</p>`}
    </div>`;
}

function showEmptyState() {
  const results = $('#results');
  if (!results) return;
  results.classList.add('results-empty');
  results.innerHTML = emptyStateHtml(moduleKey);
  setText('#resultCount', '');
}

function renderPalNode(node, isRoot = false, plan = null) {
  isRoot = isRoot && Boolean(node.parents?.length);
  const role = isRoot ? 'FINAL EGG' : node.parents?.length ? 'BREED FIRST' : 'OWNED';
  const roleClass = role === 'OWNED' ? 'owned' : role === 'FINAL EGG' ? 'target' : 'breed';
  const roleIcon = roleClass === 'owned' ? lucideIconHtml('circle-check', 'badge-svg') : '';
  const gender = genderLabel(node);
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
      ${renderPassiveBars(node, isRoot, plan)}
      <div class="node-foot">
        <span class="role-badge ${roleClass}">${roleIcon}<span>${role}</span></span>
        <span>IV ${formatIv(node.hpIv)}/${formatIv(node.attackIv)}/${formatIv(node.defenseIv)}</span>
      </div>
    </article>`;
}

function renderBreedTree(node, isRoot = false, plan = null) {
  const parents = node.parents?.length
    ? `<div class="branch"><div class="children">${node.parents.map(parent => renderBreedTree(parent, false, plan)).join('')}</div></div>`
    : '';
  return `<div class="tree-node">${renderPalNode(node, isRoot, plan)}${parents}</div>`;
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
  restoreModuleFormState();
  applyUrlPrefill();
  updateAllSpeciesSelections();
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

function loadSavedBreedingPlans() {
  try {
    savedBreedingPlans = JSON.parse(localStorage.getItem(SAVED_BREEDING_PLANS_KEY) || '[]');
    if (!Array.isArray(savedBreedingPlans)) savedBreedingPlans = [];
  } catch {
    savedBreedingPlans = [];
  }
}

function saveSavedBreedingPlans() {
  localStorage.setItem(SAVED_BREEDING_PLANS_KEY, JSON.stringify(savedBreedingPlans));
}

function currentFormState() {
  const form = $('#toolForm');
  const data = {};
  if (form) {
    Array.from(form.elements).forEach(field => {
      if (!field.name || field.type === 'file') return;
      data[field.name] = field.type === 'checkbox' ? Boolean(field.checked) : field.value;
    });
  }
  return {
    values: data,
    passives: [...passiveSelections.passives],
    implantPassives: [...passiveSelections.implantPassives],
    result: moduleKey === 'breeding' && lastBreedingResult ? lastBreedingResult : null,
  };
}

function applyFormState(state) {
  if (!state?.values) return;
  const form = $('#toolForm');
  if (!form) return;
  Object.entries(state.values).forEach(([name, value]) => {
    const field = form.elements[name];
    if (!field) return;
    if (window.RadioNodeList && field instanceof RadioNodeList) {
      [...field].forEach(item => {
        if (item.type === 'checkbox' || item.type === 'radio') item.checked = String(item.value) === String(value);
      });
    } else if (field.type === 'checkbox') {
      field.checked = Boolean(value);
    } else {
      field.value = value;
    }
  });
  if (Array.isArray(state.passives)) passiveSelections.passives = state.passives.slice(0, 4);
  if (Array.isArray(state.implantPassives)) passiveSelections.implantPassives = state.implantPassives.slice(0, 4);
  document.querySelectorAll('[data-picker="passives"], [data-picker="implantPassives"]').forEach(renderPassivePicker);
  updateProfileHint();
  syncCustomSelects();
  updateAllSpeciesSelections();
}

function saveModuleFormState() {
  const form = $('#toolForm');
  if (!form) return;
  try {
    localStorage.setItem(MODULE_FORM_STATE_KEY, JSON.stringify(currentFormState()));
  } catch {
    return;
  }
}

function markFormChanged() {
  if (moduleKey === 'breeding') lastBreedingResult = null;
  saveModuleFormState();
}

function clearToolForm() {
  const form = $('#toolForm');
  if (!form) return;
  const owners = new Map($$('.js-owner').map(select => [select, select.value]));
  form.reset();
  owners.forEach((value, select) => {
    if ([...select.options].some(option => option.value === value)) select.value = value;
  });

  passiveSelections.passives = [];
  passiveSelections.implantPassives = [];
  form.querySelectorAll('[data-picker]').forEach(picker => {
    const key = picker.dataset.picker;
    const hint = picker.querySelector('[data-passive-hint]');
    const input = picker.querySelector('[data-passive-input]');
    passiveSelections[key] = [];
    if (input) input.value = '';
    if (hint) {
      hint.textContent = DEFAULT_PASSIVE_HINTS[moduleKey]?.[key] || '';
      hint.className = 'field-hint';
    }
    picker.querySelector('[data-passive-suggestions]')?.classList.remove('open');
    renderPassivePicker(picker);
  });

  if (moduleKey === 'breeding') {
    loadedBreedingPlanId = '';
    renderProfileOptions('manual');
    renderSavedBreedingPlanOptions();
    setBreedingPlanStatus('');
  }
  if (moduleKey === 'bases') updateBaseLabelField();
  if (moduleKey === 'ranch') {
    window.PALS_RANCH_ITEM_SLUG = '';
    if (window.location.pathname !== '/pals/ranch/') window.history.replaceState({}, '', '/pals/ranch/');
  }

  document.querySelectorAll('[data-suggest-menu], [data-ranch-drop-menu], [data-passive-suggestions]').forEach(menu => {
    menu.innerHTML = '';
    menu.classList.remove('open');
  });
  document.querySelectorAll('[data-suggest="species"]').forEach(field => {
    clearSpeciesWarning(field);
    updateSpeciesSelection(field);
  });
  hidePassiveTooltip();
  lastBreedingResult = null;
  restoredResult = false;
  setText('#toolStatus', '');
  showEmptyState();
  syncCustomSelects();
  saveModuleFormState();
}

function restoreModuleFormState() {
  if (restoredFormState) return;
  restoredFormState = true;
  if (moduleKey === 'breeding' && window.location.search) return;
  try {
    const state = JSON.parse(localStorage.getItem(MODULE_FORM_STATE_KEY) || 'null');
    applyFormState(state);
    if (moduleKey === 'breeding' && state?.result) {
      renderResult(state.result);
      restoredResult = true;
      setText('#toolStatus', 'Restored saved view.');
    }
  } catch {
    return;
  }
}

function defaultBreedingPlanName() {
  const target = exactSpeciesName(formData().target) || formData().target || 'Breeding setup';
  return String(target).trim().replace(/\s+/g, ' ').slice(0, 60) || 'Breeding setup';
}

function renderSavedBreedingPlanOptions(selected = '') {
  const select = $('#savedBreedingPlan');
  if (!select) return;
  select.innerHTML = [
    '<option value="">Choose profile...</option>',
    ...savedBreedingPlans.map(plan => `<option value="${escapeHtml(plan.id)}">${escapeHtml(plan.name)}</option>`),
  ].join('');
  select.value = savedBreedingPlans.some(plan => plan.id === selected) ? selected : '';
  updateSavedBreedingPlanControls();
  updateCustomSelect(select);
}

function updateSavedBreedingPlanControls() {
  const selectedPlanId = $('#savedBreedingPlan')?.value || '';
  const hasSelectedPlan = Boolean(selectedPlanId);
  $('#loadBreedingPlan')?.toggleAttribute('disabled', !hasSelectedPlan);
  $('#deleteBreedingPlan')?.toggleAttribute('disabled', !hasSelectedPlan);
  $('#renameBreedingPlan')?.toggleAttribute('disabled', !loadedBreedingPlanId || selectedPlanId !== loadedBreedingPlanId);
}

function setBreedingPlanStatus(text, tone = '') {
  const status = $('#breedingPlanStatus');
  if (!status) return;
  status.textContent = text || '';
  status.classList.toggle('valid', tone === 'good');
  status.classList.toggle('invalid', tone === 'bad');
}

function saveBreedingPlan() {
  if (moduleKey !== 'breeding') return;
  const input = $('#breedingPlanName');
  const name = (input?.value || defaultBreedingPlanName()).trim().slice(0, 60);
  const state = currentFormState();
  const result = lastBreedingResult ? JSON.parse(JSON.stringify(lastBreedingResult)) : null;
  let plan = savedBreedingPlans.find(item => item.name.toLowerCase() === name.toLowerCase());
  if (plan) {
    if (plan.id !== loadedBreedingPlanId) {
      const shouldOverride = window.confirm(`A profile named "${name}" already exists. Override it?`);
      if (!shouldOverride) {
        setBreedingPlanStatus('Save canceled.', 'bad');
        return;
      }
    }
    plan.state = state;
    plan.result = result;
    plan.savedAt = new Date().toISOString();
  } else {
    plan = {id: `${Date.now()}-${Math.random().toString(16).slice(2)}`, name, state, result, savedAt: new Date().toISOString()};
    savedBreedingPlans.push(plan);
  }
  loadedBreedingPlanId = plan.id;
  saveSavedBreedingPlans();
  renderSavedBreedingPlanOptions(plan.id);
  if (input) input.value = name;
  setBreedingPlanStatus('Pal profile saved.', 'good');
}

function loadBreedingPlan() {
  const id = $('#savedBreedingPlan')?.value || '';
  const plan = savedBreedingPlans.find(item => item.id === id);
  if (!plan) return;
  loadedBreedingPlanId = plan.id;
  applyFormState(plan.state);
  if ($('#breedingPlanName')) $('#breedingPlanName').value = plan.name;
  saveModuleFormState();
  if (plan.result) {
    lastBreedingResult = JSON.parse(JSON.stringify(plan.result));
    renderResult(lastBreedingResult);
    setText('#toolStatus', '');
    setBreedingPlanStatus('Loaded saved setup.');
  } else {
    showEmptyState();
    setBreedingPlanStatus('Loaded saved setup.');
  }
  updateSavedBreedingPlanControls();
}

function deleteBreedingPlan() {
  const id = $('#savedBreedingPlan')?.value || '';
  const plan = savedBreedingPlans.find(item => item.id === id);
  if (!plan) return;
  savedBreedingPlans = savedBreedingPlans.filter(item => item.id !== id);
  if (loadedBreedingPlanId === id) loadedBreedingPlanId = '';
  saveSavedBreedingPlans();
  renderSavedBreedingPlanOptions();
  setBreedingPlanStatus(`Deleted ${plan.name}.`);
}

function renameBreedingPlan() {
  const plan = savedBreedingPlans.find(item => item.id === loadedBreedingPlanId);
  const input = $('#breedingPlanName');
  const name = (input?.value || '').trim().slice(0, 60);
  if (!plan || !name) return;
  const duplicate = savedBreedingPlans.find(item => item.id !== plan.id && item.name.toLowerCase() === name.toLowerCase());
  if (duplicate) {
    const shouldOverride = window.confirm(`A profile named "${name}" already exists. Override it?`);
    if (!shouldOverride) {
      setBreedingPlanStatus('Rename canceled.', 'bad');
      return;
    }
    savedBreedingPlans = savedBreedingPlans.filter(item => item.id !== duplicate.id);
  }
  plan.name = name;
  plan.savedAt = new Date().toISOString();
  saveSavedBreedingPlans();
  renderSavedBreedingPlanOptions(plan.id);
  setBreedingPlanStatus('Pal profile saved.', 'good');
}

function initBreedingPlans() {
  if (moduleKey !== 'breeding') return;
  loadSavedBreedingPlans();
  renderSavedBreedingPlanOptions();
  $('#saveBreedingPlan')?.addEventListener('click', saveBreedingPlan);
  $('#renameBreedingPlan')?.addEventListener('click', renameBreedingPlan);
  $('#loadBreedingPlan')?.addEventListener('click', loadBreedingPlan);
  $('#deleteBreedingPlan')?.addEventListener('click', deleteBreedingPlan);
  $('#savedBreedingPlan')?.addEventListener('change', updateSavedBreedingPlanControls);
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
    passiveSelections.passives = [...custom.passives];
    $$('[data-picker="passives"]').forEach(renderPassivePicker);
  }
  hint.textContent = custom ? 'Profile loaded.' : builtIn?.locked ? 'Selects passives automatically when optimizing.' : '';
}

function applySelectedProfile() {
  updateProfileHint();
  markFormChanged();
}

function switchToManualProfileForPassiveEdit(picker) {
  if (picker.dataset.picker !== 'passives') return;
  const select = $('#breedingProfile');
  if (!select || select.value === 'manual') return;
  select.value = 'manual';
  updateCustomSelect(select);
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
  if (!input || !menu) return;
  const query = String(input.value || '').trim().toLowerCase();
  if (!query) {
    menu.innerHTML = '';
    menu.classList.remove('open');
    updateSpeciesSelection(field);
    clearSpeciesWarning(field);
    return;
  }
  const matches = type === 'species'
    ? speciesMatches(query)
    : (options.passives || []).filter(value => value.toLowerCase().includes(query)).slice(0, 8);
  menu.innerHTML = matches.map(value => {
    if (type === 'species') return renderSpeciesSuggestion(value);
    const tone = type === 'passives' || type === 'passive' ? passiveTone(value) : '';
    return `<button type="button" data-suggest-value="${escapeHtml(value)}">${tone ? `<span class="passive-dot ${tone}"></span>` : ''}<span>${escapeHtml(value)}</span></button>`;
  }).join('');
  menu.classList.toggle('open', matches.length > 0);
  updateSpeciesSelection(field);
  if (type === 'species') clearSpeciesWarning(field);
}

function selectSuggestion(field, value) {
  const input = field.querySelector('[data-suggest-input]');
  const menu = field.querySelector('[data-suggest-menu]');
  if (!input) return;
  input.value = value;
  menu?.classList.remove('open');
  input.dispatchEvent(new Event('change', {bubbles: true}));
  updateSpeciesSelection(field);
}

function initSuggestFields() {
  $$('[data-suggest]').forEach(field => {
    const input = field.querySelector('[data-suggest-input]');
    input?.addEventListener('input', () => renderSuggestions(field));
    input?.addEventListener('focus', () => renderSuggestions(field));
    input?.addEventListener('change', () => validateSpeciesFieldOnExit(field));
    input?.addEventListener('invalid', event => {
      if (field.dataset.suggest !== 'species') return;
      event.preventDefault();
      showSpeciesWarning(field, 'Choose a target Pal before running this tool.');
      showEmptyState();
      setText('#toolStatus', 'Check the target species.');
    });
    input?.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        field.querySelector('[data-suggest-menu]')?.classList.remove('open');
        return;
      }
      if (event.key !== 'Enter') return;
      const type = field.dataset.suggest;
      const value = input.value || '';
      const matches = type === 'species'
        ? speciesMatches(value)
        : (options.passives || []).filter(item => item.toLowerCase().includes(String(value).trim().toLowerCase())).slice(0, 8);
      const exact = type === 'species'
        ? exactSpeciesName(value)
        : (options.passives || []).find(item => item.toLowerCase() === String(value).trim().toLowerCase()) || '';
      const selection = exact || (matches.length === 1 ? matches[0] : '');
      if (!selection) {
        if (type !== 'species') return;
        event.preventDefault();
        field.querySelector('[data-suggest-menu]')?.classList.remove('open');
        validateSpeciesFieldOnExit(field);
        return;
      }
      event.preventDefault();
      selectSuggestion(field, selection);
    });
    input?.addEventListener('blur', () => {
      window.setTimeout(() => {
        field.querySelector('[data-suggest-menu]')?.classList.remove('open');
        validateSpeciesFieldOnExit(field);
      }, 120);
    });
    field.addEventListener('click', event => {
      const value = event.target.closest('[data-suggest-value]')?.dataset.suggestValue;
      if (!value) return;
      selectSuggestion(field, value);
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
  const add = picker.querySelector('[data-passive-add]');
  if (add) add.disabled = selected.length >= 4;
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
  switchToManualProfileForPassiveEdit(picker);
  input.value = '';
  hint.textContent = `${match.value} added.`;
  hint.className = 'field-hint valid';
  renderPassivePicker(picker);
  renderPassiveSuggestions(picker);
  markFormChanged();
  input.focus();
}

function initPassivePickers() {
  $$('[data-picker]').forEach(picker => {
    picker.querySelector('[data-passive-add]')?.addEventListener('click', () => addPassive(picker));
    picker.querySelector('[data-passive-clear]')?.addEventListener('click', () => {
      switchToManualProfileForPassiveEdit(picker);
      passiveSelections[picker.dataset.picker] = [];
      picker.querySelector('[data-passive-hint]').textContent = 'Selected passives cleared.';
      picker.querySelector('[data-passive-hint]').className = 'field-hint';
      renderPassivePicker(picker);
      markFormChanged();
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
      switchToManualProfileForPassiveEdit(picker);
      passiveSelections[key] = (passiveSelections[key] || []).filter(item => item !== passive);
      renderPassivePicker(picker);
      markFormChanged();
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
  const response = await postJson('/implant-inventory', {passive, ...patch});
  options.implantInventory = response.inventory || {};
  renderImplantInventories();
}

function renderImplantInventories() {
  const entries = Object.entries(options.implantInventory || {}).sort(([a], [b]) => a.localeCompare(b));
  const availableCount = entries.filter(([, item]) => item?.infinite || Number(item?.count || 0) > 0).length;
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

function refreshPassiveColorSurfaces() {
  $$('[data-picker]').forEach(renderPassivePicker);
  renderImplantInventories();
  renderPassiveColors();
  if (lastRenderedResult) renderResult(lastRenderedResult);
}

function renderPassiveColorSuggestions(panel) {
  const input = panel.querySelector('[data-color-input]');
  const menu = panel.querySelector('[data-color-menu]');
  const query = String(input?.value || '').trim().toLowerCase();
  if (!query) {
    menu.innerHTML = '';
    menu.classList.remove('open');
    return;
  }
  const matches = (options.passives || [])
    .filter(passive => passive.toLowerCase().includes(query))
    .slice(0, 8);
  menu.innerHTML = matches.map(passive => `<button type="button" data-color-choice="${escapeHtml(passive)}"><span class="passive-dot ${passiveTone(passive)}"></span><span>${escapeHtml(passive)}</span><em>${escapeHtml(options.passiveColorOverrides?.[passive] ? 'Override' : 'Default')}</em></button>`).join('');
  menu.classList.toggle('open', matches.length > 0);
}

async function savePassiveColor(passive, tone, remove = false) {
  const response = await postJson('/passive-colors', {passive, tone, delete: remove});
  options.passiveColorOverrides = response.overrides || {};
  options.passiveMeta = response.passiveMeta || options.passiveMeta || {};
  refreshPassiveColorSurfaces();
}

async function savePassiveColorFromPanel(panel) {
  const input = panel.querySelector('[data-color-input]');
  const tone = panel.querySelector('[data-color-tone]')?.value || 'neutral';
  const status = panel.querySelector('[data-color-status]');
  const match = canonicalMatch(options.passives || [], input?.value || '');
  if (!match.value) {
    if (status) {
      status.textContent = match.reason === 'ambiguous' ? `Matches: ${match.matches.join(', ')}. Keep typing.` : 'No known passive matches that text.';
      status.className = 'field-hint invalid';
    }
    return;
  }
  await savePassiveColor(match.value, tone);
  input.value = '';
  renderPassiveColorSuggestions(panel);
  if (status) {
    status.textContent = `${match.value} set to ${tone}.`;
    status.className = 'field-hint valid';
  }
  input.focus();
}

function renderPassiveColors() {
  const entries = Object.entries(options.passiveColorOverrides || {}).sort(([a], [b]) => a.localeCompare(b));
  $$('[data-passive-colors]').forEach(panel => {
    const list = panel.querySelector('[data-color-list]');
    if (!list) return;
    list.innerHTML = entries.length ? entries.map(([passive, tone]) => `
      <div class="passive-color-row">
        <span class="passive-chip ${passiveTone(passive)}" tabindex="0" data-passive-tooltip="${escapeHtml(passive)}">${escapeHtml(passive)}</span>
        <span class="passive-color-tone"><span class="passive-dot ${escapeHtml(tone)}"></span>${escapeHtml(tone)}</span>
        <button type="button" class="chip-remove" data-color-delete="${escapeHtml(passive)}" aria-label="Reset ${escapeHtml(passive)}">x</button>
      </div>`).join('') : '<p class="field-hint">No passive color overrides saved.</p>';
    const status = panel.querySelector('[data-color-status]');
    if (status && !status.textContent) status.textContent = entries.length ? `${entries.length} passive color override${entries.length === 1 ? '' : 's'} saved.` : '';
  });
}

function initPassiveColors() {
  $$('[data-open-passive-colors]').forEach(button => {
    button.addEventListener('click', () => {
      $('#passiveColorsModal')?.classList.remove('hidden');
      renderPassiveColors();
      $('#passiveColorsModal [data-color-input]')?.focus();
    });
  });
  $('#closePassiveColors')?.addEventListener('click', () => $('#passiveColorsModal')?.classList.add('hidden'));
  $('#passiveColorsModal')?.addEventListener('click', event => {
    if (event.target === $('#passiveColorsModal')) $('#passiveColorsModal')?.classList.add('hidden');
  });
  $$('[data-passive-colors]').forEach(panel => {
    const input = panel.querySelector('[data-color-input]');
    const status = panel.querySelector('[data-color-status]');
    input?.addEventListener('input', () => renderPassiveColorSuggestions(panel));
    input?.addEventListener('keydown', event => {
      if (event.key === 'Enter') {
        event.preventDefault();
        savePassiveColorFromPanel(panel).catch(error => {
          if (status) {
            status.textContent = error.message;
            status.className = 'field-hint invalid';
          }
        });
      }
    });
    input?.addEventListener('blur', () => {
      window.setTimeout(() => panel.querySelector('[data-color-menu]')?.classList.remove('open'), 120);
    });
    panel.querySelector('[data-color-save]')?.addEventListener('click', () => {
      savePassiveColorFromPanel(panel).catch(error => {
        if (status) {
          status.textContent = error.message;
          status.className = 'field-hint invalid';
        }
      });
    });
    panel.addEventListener('click', event => {
      const choice = event.target.closest('[data-color-choice]')?.dataset.colorChoice;
      if (choice) {
        input.value = choice;
        panel.querySelector('[data-color-menu]')?.classList.remove('open');
        input.focus();
        return;
      }
      const deleted = event.target.closest('[data-color-delete]')?.dataset.colorDelete;
      if (deleted) {
        savePassiveColor(deleted, 'neutral', true).catch(error => {
          if (status) {
            status.textContent = error.message;
            status.className = 'field-hint invalid';
          }
        });
      }
    });
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
    const field = document.querySelector('[name="breedAnyway"]');
    if (!field) return;
    field.checked = true;
    field.dispatchEvent(new Event('change', {bubbles: true}));
    $('#toolForm').requestSubmit();
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

function readyFinishCandidates(data) {
  const finalPassives = new Set(data.finalPassives || []);
  const implantPassives = new Set(data.implantPassives || []);
  if (!finalPassives.size || !implantPassives.size) return [];
  const candidates = data.readyToFinish?.results || data.alreadyOwned?.results || [];
  return candidates.filter(candidate => {
    const owned = new Set(candidate.passives || []);
    const missing = [...finalPassives].filter(passive => !owned.has(passive));
    return missing.length > 0 && missing.every(passive => implantPassives.has(passive));
  });
}

function renderReadyFinishCards(candidates, data) {
  const finalPassives = data.finalPassives || [];
  const implantPassives = new Set(data.implantPassives || []);
  const top = candidates[0] || {};
  const candidateCards = candidates.map(candidate => {
    const owned = new Set(candidate.passives || []);
    const present = finalPassives.filter(passive => owned.has(passive));
    const missingImplants = finalPassives.filter(passive => !owned.has(passive) && implantPassives.has(passive));
    const replaceable = candidate.junk || [];
    return `
      <article class="ready-option-card">
        <div class="ready-pal-summary">
          <div class="pal-avatar ready-avatar">${candidate.icon ? `<img src="${escapeHtml(assetUrl(candidate.icon))}" alt="">` : escapeHtml(speciesInitials(candidate.species))}</div>
          <div>
            <h4>${escapeHtml(candidate.species)} ${candidate.displayGender ? `<span class="gender ${escapeHtml(String(candidate.displayGender).toLowerCase())}">${escapeHtml(candidate.displayGender)}</span>` : ''}</h4>
            <p>${escapeHtml(palboxLocationText(candidate))}</p>
            <span class="role-badge owned">${lucideIconHtml('circle-check', 'badge-svg')}<span>Already owned</span></span>
          </div>
        </div>
        <div class="ready-progress">
          <span>Breed for</span>
          <div class="passive-list ready-passive-list">
            ${present.map(passive => `<span class="passive-bar ${passiveTone(passive)}" tabindex="0" data-passive-tooltip="${escapeHtml(passive)}"><span>${escapeHtml(passive)}</span></span>`).join('')}
          </div>
        </div>
        <div class="ready-missing">
          <span>Add later</span>
          <div class="passive-list ready-passive-list">
            ${missingImplants.map(passive => `<span class="passive-bar implant-missing ${passiveTone(passive)}" tabindex="0" data-passive-tooltip="${escapeHtml(passive)}"><span>${escapeHtml(passive)}</span><em class="implant-badge">${lucideIconHtml('dna', 'passive-badge-svg')}<span>Implant</span></em></span>`).join('')}
          </div>
        </div>
        <div class="ready-passives ready-option-passives">
          <span>Final passives</span>
          <div class="passive-list ready-passive-list">
            ${present.map(passive => `<span class="passive-bar ${passiveTone(passive)}" tabindex="0" data-passive-tooltip="${escapeHtml(passive)}"><span>${escapeHtml(passive)}</span></span>`).join('')}
            ${missingImplants.map(passive => `<span class="passive-bar implant-missing ${passiveTone(passive)}" tabindex="0" data-passive-tooltip="${escapeHtml(passive)}"><span>${escapeHtml(passive)}</span><em class="implant-badge">${lucideIconHtml('dna', 'passive-badge-svg')}<span>Implant</span></em></span>`).join('')}
          </div>
          ${replaceable.length ? `<p class="ready-replaceable">Replaceable: ${escapeHtml(replaceable.join(', '))}</p>` : ''}
        </div>
      </article>`;
  }).join('');
  return `
    <article class="ready-finish-card">
      <div class="ready-kicker"><span class="ready-star" aria-hidden="true"></span>Best Option</div>
      <div class="ready-head">
        <div>
          <h3>Ready to Finish</h3>
          <p>Use an owned ${escapeHtml(top.species || 'Pal')} and implant the missing passive${finalPassives.length === 1 ? '' : 's'}.</p>
        </div>
      </div>
      <div class="ready-options-grid">${candidateCards}</div>
      <div class="ready-actions">
        <button type="button" class="card-action ready-fresh-copy" data-show-fresh-copy>Breed a fresh copy instead</button>
      </div>
    </article>`;
}

function renderBlockedBreeding(data) {
  const diagnosis = data.noRoute;
  const missing = diagnosis.missingPassives || [];
  const partial = diagnosis.partialResults?.[0];
  const partialPlan = {finalPassives: diagnosis.partialPassives || [], implantPassives: []};
  return `<section class="result-group">
    ${renderProfileResultNotice(data)}
    <div class="group-heading">
      <h3>${missing.length ? 'Missing breeding donor' : 'No complete route found'}</h3>
      ${missing.length ? `
        <p>Get a compatible ${escapeHtml(missing.join(', '))} donor, then sync and rerun.</p>
      ` : '<p>The current search found no complete breeding plan with your owned Pals and selected settings. This does not prove that no route exists. Check available parent genders, or try fewer desired passives.</p>'}
    </div>
    ${partial ? `<article class="route-card">
      <div class="route-header"><div>
        <h3>Optional progress: breed for ${escapeHtml(diagnosis.partialPassives.join(', '))}</h3>
        <p>This prepares only part of your goal. You still need ${escapeHtml(missing.join(', '))} from a compatible donor.</p>
      </div></div>
      <div class="breed-tree">${renderBreedTree(partial, true, partialPlan)}</div>
    </article>` : ''}
  </section>`;
}

function renderBreeding(data) {
  if (data.achievable === false && data.noRoute) return renderBlockedBreeding(data);
  const groups = (data.groups || []).map(group => data.breedAnyway
    ? {...group, results: (group.results || []).filter(route => route.parents?.length === 2)}
    : group);
  if (data.breedAnyway && !groups.some(group => group.results?.length)) {
    return '<div class="results-empty">No breeding pair or setup route found for these passives in the current search.</div>';
  }
  if (!groups.length) return renderJson(data);
  const group = groups.find(item => (item.results || []).length) || groups[0];
  const route = (group.results || [])[0];
  if (!route) return '<div class="results-empty">No route found. Try fewer desired passives or upload a fresher save.</div>';
  const readyCandidates = readyFinishCandidates(data);
  const profileNotice = renderProfileResultNotice(data);
  if (readyCandidates.length && !data.breedAnyway) {
    return `
      <section class="result-group">
        ${profileNotice}
        ${renderReadyFinishCards(readyCandidates, data)}
      </section>`;
  }
  return `
    <section class="result-group">
      ${profileNotice}
      <div class="group-heading">
        <h3>${group.slug === 'existing_target' ? 'Best Existing Target' : 'Recommended Route'}</h3>
        <p>${escapeHtml(group.description || 'Best practical option from the current search.')}</p>
        ${group.slug === 'existing_target' ? '<p>No complete breeding route found for the requested passives.</p>' : ''}
      </div>
        <article class="route-card">
          <div class="route-header">
            <div>
              <h3>${escapeHtml(route.species)}</h3>
            </div>
          </div>
          <div class="breed-tree">${renderBreedTree(route, true, data)}</div>
        </article>
    </section>`;
}

function renderProfileResultNotice(data) {
  const selected = data.profileSelectedPassives || [];
  const ideal = data.profileIdealPassives || [];
  const finalPassives = data.finalPassives || [];
  const implantPassives = new Set(data.implantPassives || []);
  const breedFor = finalPassives.filter(passive => !implantPassives.has(passive));
  const addLater = finalPassives.filter(passive => implantPassives.has(passive));
  const hasImplantPlan = addLater.length > 0;
  if (!selected.length && !ideal.length && !data.profileDisclaimer && !hasImplantPlan) return '';
  return `
    <div class="profile-result-notice">
      <div class="profile-result-summary">
        <div class="profile-result-title">
          <span class="profile-result-icon" aria-hidden="true">★</span>
          <strong>Passive profile result</strong>
        </div>
        ${data.profileDisclaimer ? `<p>${escapeHtml(data.profileDisclaimer)}</p>` : ''}
        ${hasImplantPlan ? `<p>${data.achievable === false ? 'Your goal includes implants to add after breeding.' : 'Implant inventory is included in this route; some final passives are planned for after breeding.'}</p>` : ''}
      </div>
      <div class="profile-result-grid">
        ${ideal.length ? `<section><b>Absolute target</b>${profileResultPassiveList(ideal)}</section>` : ''}
        ${selected.length ? `<section><b>Using</b>${profileResultPassiveList(selected)}</section>` : ''}
        ${hasImplantPlan ? `<section><b>Breed for</b>${profileResultPassiveList(breedFor)}</section>` : ''}
        ${hasImplantPlan ? `<section><b>Add later</b>${profileResultPassiveList(addLater, implantPassives)}</section>` : ''}
      </div>
    </div>`;
}

function profileResultPassiveList(passives, implantPassives = new Set()) {
  return `
    <span class="passive-list compact">
      ${(passives || []).map(passive => `<span class="passive-bar ${implantPassives.has(passive) ? 'implant-missing' : ''} ${passiveTone(passive)}" tabindex="0" data-passive-tooltip="${escapeHtml(passive)}"><span>${escapeHtml(passive)}</span>${implantPassives.has(passive) ? `<em class="implant-badge">${lucideIconHtml('dna', 'passive-badge-svg')}<span>Implant</span></em>` : ''}</span>`).join('')}
    </span>`;
}

function renderIvs(data) {
  if (data.error) return resultCard('No IV plan', escapeHtml(data.error));
  if (data.alphaOnly) return renderIvAlphaOnly(data);
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

function renderIvStat(label, value) {
  return `<span><b>${escapeHtml(label)}</b><strong>${escapeHtml(value)}</strong></span>`;
}

function renderIvAlphaOwnedMatch(card, requestedPassives = []) {
  const gender = genderLabel(card);
  const passiveSet = requestedPassives.length ? requestedPassives : (card.passives || []);
  return `
    <article class="iv-alpha-owned route-card">
      <div class="iv-alpha-section-title">${lucideIconHtml('circle-check', 'iv-alpha-title-icon')}<h3>Owned Match</h3></div>
      <div class="iv-alpha-owned-grid">
        <div class="iv-alpha-pal">
          <div class="pal-avatar iv-alpha-avatar">${card.icon ? `<img src="${escapeHtml(assetUrl(card.icon))}" alt="">` : escapeHtml(speciesInitials(card.species))}</div>
          <div>
            <h4>${escapeHtml(card.species)} ${gender.symbol ? `<span class="gender ${gender.className}" title="${gender.text}">${escapeHtml(gender.symbol)}</span>` : ''}</h4>
            <p class="iv-alpha-location">${lucideIconHtml('map-pin', 'iv-alpha-inline-icon')}<span>${escapeHtml(locationText(card))}</span></p>
            <span class="role-badge ${card.isAlpha ? 'alpha' : 'non-alpha'}">${lucideIconHtml(card.isAlpha ? 'crown' : 'circle-off', 'badge-svg')}<span>${card.isAlpha ? 'Alpha' : 'Non-Alpha'}</span></span>
          </div>
        </div>
        <div class="iv-alpha-block">
          <strong>Target Passives</strong>
          <div class="passive-list compact">${passiveSet.map(passive => passiveBarHtml(passive)).join('')}</div>
        </div>
        <div class="iv-alpha-block">
          <strong>${lucideIconHtml('dna', 'iv-alpha-inline-icon')}<span>IVs</span></strong>
          <div class="iv-alpha-stats">
            ${renderIvStat('HP', card.hpIv)}
            ${renderIvStat('ATK', card.attackIv)}
            ${renderIvStat('DEF', card.defenseIv)}
          </div>
        </div>
      </div>
    </article>`;
}

function renderIvAlphaOnly(data) {
  const alpha = data.alphaOnly;
  const missing = alpha.missing?.length ? alpha.missing.join(', ') : 'None';
  const steps = alpha.nextSteps || [];
  return `
    <section class="iv-alpha-result">
      <div class="iv-alpha-hero ${alpha.state === 'complete' ? 'complete' : ''}">
        <div class="iv-alpha-hero-copy">
          <span class="iv-alpha-hero-icon">${lucideIconHtml('circle-check-big', 'iv-alpha-hero-svg')}</span>
          <div>
            <h3>${escapeHtml(alpha.title)}</h3>
            <p>${escapeHtml(alpha.message)}</p>
          </div>
        </div>
        <span class="iv-alpha-missing">${lucideIconHtml('crown', 'badge-svg')}<span>Missing: ${escapeHtml(missing)}</span></span>
      </div>
      ${renderIvAlphaOwnedMatch(alpha.ownedMatch || {}, data.requestedPassives || [])}
      <article class="iv-alpha-next route-card">
        <div class="iv-alpha-section-title">${lucideIconHtml('list-checks', 'iv-alpha-title-icon')}<h3>Next Steps (Alpha Only)</h3></div>
        <div class="iv-alpha-step-grid">
          ${steps.map((step, index) => `
            <div class="iv-alpha-step ${step.primary ? 'primary' : ''}">
              <span>${lucideIconHtml(step.icon || 'circle-check', 'iv-alpha-step-icon')}</span>
              <div>
                <h4>${index + 1}. ${escapeHtml(step.title)}</h4>
                <p>${escapeHtml(step.detail)}</p>
              </div>
            </div>`).join('')}
        </div>
        <div class="iv-alpha-notes">
          <div>${lucideIconHtml('info', 'iv-alpha-note-icon')}<p><strong>Why Special Cake?</strong><span>${escapeHtml(alpha.recommendedCakeReason || '')}</span></p></div>
          <div>${lucideIconHtml('info', 'iv-alpha-note-icon')}<p><strong>Why Broncherry + Broncherry Aqua?</strong><span>Fully condensed Broncherry + Broncherry Aqua guarantee Alpha eggs while you continue hatching from the solved pair.</span></p></div>
        </div>
      </article>
      ${alpha.parentPoolWarning ? `
        <div class="iv-alpha-warning">
          ${lucideIconHtml('triangle-alert', 'iv-alpha-warning-icon')}
          <div>
            <h3>If your breeding pair has extra passives</h3>
            <p>Your owned ${escapeHtml(data.target)} meets the target, but Special Cake is only ideal when the parent passive pool is exactly the ${escapeHtml((data.naturalPassives || []).length)} target passives.</p>
          </div>
        </div>` : ''}
    </section>`;
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
  const owned = card.ownedCount ? `<span class="role-badge owned">${lucideIconHtml('circle-check', 'badge-svg')}<span>Own: ${escapeHtml(card.ownedCount)}</span></span>` : '<span class="role-badge">Not owned</span>';
  const breedable = card.requiresOwnedSeed
    ? '<span class="badge self-breed">Self-Breed Only</span>'
    : card.breedable ? `<span class="badge good">${lucideIconHtml('circle-check', 'badge-svg')}<span>Breedable</span></span>` : '<span class="badge bad">Not breedable</span>';
  const size = card.sizeKnown ? `${card.sizeGroup} (${card.size})` : 'Unknown size';
  const unavailable = card.unavailableReason ? `<p class="work-seed-warning">${escapeHtml(card.unavailableReason)}</p>` : '';
  const recommendationIcon = recommendation?.role === 'dark' || /dark/i.test(recommendation?.title || '') ? 'moon' : 'star';
  const recHead = recommendation ? `
    <div class="work-rec-head">
      <div>
        <div class="work-rec-kicker">${lucideIconHtml(recommendationIcon, 'work-rec-kicker-icon')}<span>${escapeHtml(recommendation.title)}</span></div>
      </div>
      ${renderBreedAction(card, profile)}
    </div>` : '';
  return `
    <article class="work-pal-card ${compact ? 'compact' : ''} ${recommendation ? 'work-rec-card' : ''}">
      ${recHead}
      ${recommendation ? '' : renderBreedAction(card, profile)}
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
  const workers = data.recommendations || [];
  const gaps = data.gaps || [];
  const ownedOnly = data.plannerMode === 'right_now';
  return `
    <div class="group-heading">
      <h3>${escapeHtml(data.base?.displayName || 'Base workers')}</h3>
      <p>${ownedOnly ? 'Right now' : 'Ideal team'} · ${workers.length} / ${escapeHtml(data.maxWorkers || 15)} workers</p>
    </div>
    ${gaps.length ? `<div class="owned-notice"><strong>Unfilled roles</strong><span>${gaps.map(gap => `${escapeHtml(gap.label)}: ${escapeHtml(gap.covered)} / ${escapeHtml(gap.wanted)}`).join(' · ')}</span></div>` : ''}
    ${workers.length ? `<div class="work-card-grid base-worker-grid">${workers.map(card => renderBaseWorker(card, ownedOnly)).join('')}</div>` : '<div class="empty">No workers match the selected roles and owner.</div>'}`;
}

function renderBaseWorker(card, ownedOnly) {
  const role = card.plannerRole || card.selectedWork;
  const work = (card.work || []).map(entry => ({
    ...entry,
    level: card.plannerLevels?.[entry.key] ?? entry.level,
    fullyCondensedLevel: null,
    projectedFullyCondensedLevel: null,
  }));
  const roleLabel = work.find(entry => entry.key === role)?.label || role || 'Worker';
  return `
    <article class="work-pal-card compact base-worker-card">
      <div class="group-heading"><strong>Slot ${escapeHtml(card.plannerSlot)} · ${escapeHtml(roleLabel)}</strong></div>
      <div class="pal-main">
        <div class="pal-avatar">${card.icon ? `<img src="${escapeHtml(assetUrl(card.icon))}" alt="">` : escapeHtml(speciesInitials(card.name))}</div>
        <div class="pal-copy"><h3>${escapeHtml(card.name)}</h3>${renderTypeChips(card.types || [])}</div>
      </div>
      ${renderWorkSkillPills(work, role)}
      ${ownedOnly ? `<div class="base-worker-details"><span>${escapeHtml(card.plannerLocation || 'Unknown location')}</span><span>Level ${escapeHtml(card.plannerLevel ?? 0)} · ${escapeHtml(card.plannerGender || 'Unknown gender')} · ${escapeHtml(card.plannerCondensationStars ?? 0)} stars</span></div>
        ${(card.plannerPassives || []).length ? `<div class="passive-list">${card.plannerPassives.map(passive => passiveBarHtml(passive)).join('')}</div>` : ''}` : `<div class="node-foot"><span class="role-badge">${card.ownedCount ? `Own: ${escapeHtml(card.ownedCount)}` : 'Not owned'}</span><a class="card-action" href="${escapeHtml(breedUrl(card, role === 'farming' ? 'ranch_drops_focus' : 'work_speed'))}">Breed</a></div>`}
    </article>`;
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
  const result = await postJson('/base-labels', {baseId: base.id, label});
  options.baseSites = await api('/base-work-sites');
  fillOptions();
  setText('#baseLabelHint', result.ok ? 'Base name saved.' : 'Base name was not saved.');
}

function renderResult(data) {
  const renderers = {breeding: renderBreeding, ivs: renderIvs, work: renderWork, ranch: renderRanch, bases: renderBases};
  lastRenderedResult = data;
  if (moduleKey === 'breeding') lastBreedingResult = data;
  $('#results').classList.remove('results-empty');
  $('#results').innerHTML = (renderers[moduleKey] || renderJson)(data);
  const count = data.total || data.totalItems || data.rosterCount || (data.groups || []).length || '';
  setText('#resultCount', data.alphaOnly ? '' : moduleKey === 'breeding' ? (data.achievable === false ? '' : 'Top route') : count ? `${count} result${count === 1 ? '' : 's'}` : '');
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

function initFormStatePersistence() {
  const form = $('#toolForm');
  if (!form) return;
  form.addEventListener('input', event => {
    if (event.target.closest('#breedingPlanName, #savedBreedingPlan')) return;
    markFormChanged();
  });
  form.addEventListener('change', event => {
    if (event.target.closest('#breedingPlanName, #savedBreedingPlan')) return;
    markFormChanged();
  });
}

async function submitTool(event) {
  event.preventDefault();
  if (!validateTargetSpecies()) {
    showEmptyState();
    setText('#toolStatus', 'Check the target species.');
    return;
  }
  setText('#toolStatus', 'Running...');
  $('#results').innerHTML = '';
  const data = formData();
  try {
    let result;
    if (moduleKey === 'breeding') {
      const customProfile = customProfileByValue(data.breedingProfile);
      const finalPassives = customProfile ? customProfile.passives : splitList(data.passives);
      result = await postJson('/optimize', {
        owner: data.owner || 'David',
        target: data.target,
        passives: finalPassives,
        includeImplants: Boolean(data.includeImplants),
        includeInsomnia: Boolean(data.includeInsomnia),
        breedAnyway: Boolean(data.breedAnyway),
        implantPassives: selectedImplantPassives(finalPassives, Boolean(data.includeImplants)),
        genderPreference: data.genderPreference || 'any',
        breedingProfile: customProfile ? 'manual' : data.breedingProfile || 'manual',
        routePreference: 'best_overall',
      });
    } else if (moduleKey === 'ivs') {
      const finalPassives = splitList(data.passives);
      result = await postJson('/improve-ivs', {
        owner: data.owner || 'David',
        target: data.target,
        passives: finalPassives,
        implantPassives: selectedImplantPassives(finalPassives, Boolean(data.includeImplants)),
        genderPreference: data.genderPreference || 'any',
        ivGoal: 'perfect',
        requireAlpha: Boolean(data.requireAlpha),
      });
    } else if (moduleKey === 'work') {
      const includeSelf = data.includeSelfBreeders ? '1' : '0';
      result = await api(`/work-suitability?owner=${encodeURIComponent(data.owner || 'David')}&work=${encodeURIComponent(data.work || '')}&includeSelfBreeders=${includeSelf}`);
    } else if (moduleKey === 'ranch') {
      const includeSelf = data.includeSelfBreeders ? '1' : '0';
      result = await api(`/ranch-drops?owner=${encodeURIComponent(data.owner || 'David')}&includeSelfBreeders=${includeSelf}`);
    } else if (moduleKey === 'bases') {
      result = await postJson('/base-planner', {
        owner: data.owner || 'David',
        baseId: data.baseId || '',
        plannerMode: data.plannerMode || 'ideal',
        maxWorkers: Number(data.maxWorkers || 15),
        settings: {},
      });
    }
    renderResult(result);
    saveModuleFormState();
    setText('#toolStatus', 'Done.');
  } catch (error) {
    $('#results').classList.add('results-empty');
    $('#results').textContent = error.message;
    setText('#toolStatus', 'Failed.');
  }
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
  const result = await postJson('/live-save/refresh', {force: true});
  setLiveStatus(result.ok ? `Synced ${result.rosterCount || 0} Pals` : result.error || 'Sync failed', result.ok ? 'good' : 'bad');
  options = await api('/options');
  ranchDropsCache = null;
  fillOptions();
}

async function uploadSave(file) {
  if (!file) return;
  const form = new FormData();
  form.append('files', file, file.name);
  form.append('relativePaths', JSON.stringify([file.webkitRelativePath || file.name]));
  setLiveStatus('Uploading save...', 'active', file.name);
  const result = await api('/upload-save', {method: 'POST', body: form});
  if (!result.ok) throw new Error(result.error || 'Upload failed.');
  setLiveStatus(`Imported ${result.rosterCount || 0} Pals`, 'good', file.name);
  options = await api('/options');
  ranchDropsCache = null;
  fillOptions();
}

async function init() {
  setTheme(localStorage.getItem('pals.theme') || 'dark');
  $('#toolForm')?.addEventListener('submit', submitTool);
  $('#clearToolForm')?.addEventListener('click', clearToolForm);
  initSuggestFields();
  initPassivePickers();
  initPassiveTooltips();
  initProfiles();
  initBreedingPlans();
  initImplantInventories();
  initPassiveColors();
  initFreshCopyToggle();
  initRanchDropSearch();
  initFormStatePersistence();
  $('#refreshLiveSave')?.addEventListener('click', () => refreshLiveSave().catch(error => setLiveStatus(error.message, 'bad')));
  $('#saveUpload')?.addEventListener('change', event => uploadSave(event.target.files?.[0]).catch(error => setLiveStatus(error.message, 'bad')));
  $('.js-base')?.addEventListener('change', updateBaseLabelField);
  $('#saveBaseLabel')?.addEventListener('click', () => saveBaseLabel().catch(error => setText('#baseLabelHint', error.message)));
  options = await api('/options');
  fillOptions();
  if (!restoredResult) showEmptyState();
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
