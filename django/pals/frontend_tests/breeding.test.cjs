const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '../static/pals/js/tool.js'), 'utf8');
function renderer(extra = {}) {
  const context = vm.createContext({
    readyFinishCandidates: () => [{species: 'Owned match'}],
    renderProfileResultNotice: () => '',
    renderReadyFinishCards: () => '<div>Implant existing Pal</div>',
    renderBreedTree: route => `<div>Pair: ${route.parents.map(p => p.species).join(' + ')}</div>`,
    ...extra,
  });
  for (const name of ['escapeHtml', 'renderBlockedBreeding', 'renderBreeding', 'initFreshCopyToggle']) {
    const start = source.indexOf(`function ${name}(`);
    assert.ok(start >= 0, name);
    vm.runInContext(source.slice(start, source.indexOf('\n}', start) + 2), context);
  }
  return context;
}
const owned = {species: 'Owned match', parents: []};
const route = {species: 'Shroomer Noct', parents: [{species: 'Male'}, {species: 'Female'}]};

function cardRenderer() {
  const context = renderer({
    readyFinishCandidates: () => [],
    passiveTone: () => 'neutral',
    lucideIconHtml: () => '',
    genderLabel: () => ({symbol: ''}),
    speciesInitials: () => 'ES',
    renderTypeChips: () => '',
    formatIv: value => value,
  });
  for (const name of ['locationText', 'displayPassives', 'displayJunk', 'passiveBarHtml', 'renderPassiveBars', 'renderPalNode', 'renderBreedTree']) {
    const start = source.indexOf(`function ${name}(`);
    assert.ok(start >= 0, name);
    vm.runInContext(source.slice(start, source.indexOf('\n}', start) + 2), context);
  }
  return context;
}

const sword = {
  species: 'Enchanted Sword', box: 1, slot: 20, parents: [],
  passives: ['Burly Body'], desired: [], junk: ['Burly Body'],
  hpIv: 92, attackIv: 29, defenseIv: 38,
};
const swordPlan = {
  finalPassives: ['Idiosyncratic', 'Reload Master', 'Stronghold Strategist', 'Vanguard'],
  implantPassives: ['Stronghold Strategist', 'Vanguard'],
};

test('blocked goal explains missing donor and shows a factual partial breeding tree', () => {
  const html = cardRenderer().renderBreeding({...swordPlan, target: 'Enchanted Sword', achievable: false,
    noRoute: {missingPassives: ['Idiosyncratic'], sourceSpecies: ['Enchanted Sword', 'Illuminant Slime'],
      partialPassives: ['Reload Master'], partialResults: [{...sword, desired: ['Reload Master'], parents: [sword, sword]}]},
    groups: [{slug: 'existing_target', results: [sword]}],
  });
  assert.match(html, /Missing breeding donor/);
  assert.match(html, /Obtain Idiosyncratic/);
  assert.match(html, /Optional progress: breed for Reload Master/);
  assert.match(html, /This prepares only part of your goal/);
  assert.doesNotMatch(html, /Best Existing Target|Recommended Route|implant-plan/);
  assert.equal((html.match(/data-passive-tooltip="Idiosyncratic"/g) || []).length, 0);
});

test('search exhaustion does not claim a missing inheritance source', () => {
  const html = renderer().renderBreeding({achievable: false, noRoute: {missingPassives: [], partialResults: []}});
  assert.match(html, /This does not prove that no route exists/);
  assert.doesNotMatch(html, /Missing breeding donor|Obtain/);
});

test('incomplete owned fallback shows actual passives and identifies the missing route', () => {
  const html = cardRenderer().renderBreeding({...swordPlan, achievable: false, groups: [
    {slug: 'recommended', results: []},
    {slug: 'existing_target', results: [sword]},
  ]});
  assert.match(html, /Best Existing Target/);
  assert.match(html, /No complete breeding route found/);
  assert.match(html, /Box 1, slot 20/);
  assert.match(html, /Burly Body/);
  assert.match(html, /OWNED/);
  assert.doesNotMatch(html, /Idiosyncratic|Reload Master|Stronghold Strategist|Vanguard|FINAL EGG|Recommended Route/);
});

test('complete owned root still shows its actual passives', () => {
  const html = cardRenderer().renderPalNode({...sword, passives: ['Idiosyncratic', 'Reload Master', 'Burly Body']}, true, swordPlan);
  assert.match(html, /Burly Body/);
  assert.match(html, /Idiosyncratic/);
  assert.match(html, /OWNED/);
  assert.doesNotMatch(html, /FINAL EGG|implant-plan/);
});

test('planned offspring retains final goal and implants while its owned parents stay factual', () => {
  const html = cardRenderer().renderBreedTree({...sword, parents: [sword, sword]}, true, swordPlan);
  assert.match(html, /FINAL EGG/);
  assert.match(html, /Idiosyncratic/);
  assert.match(html, /Reload Master/);
  assert.match(html, /Stronghold Strategist/);
  assert.match(html, /Vanguard/);
  assert.equal((html.match(/implant-plan/g) || []).length, 1);
  assert.equal((html.match(/<span>OWNED<\/span>/g) || []).length, 2);
  assert.match(html, /Burly Body/);
});

test('breed anyway renders parents even when an owned or implant-ready match exists', () => {
  const html = renderer().renderBreeding({breedAnyway: true, groups: [{results: [owned, route]}]});
  assert.match(html, /Pair: Male \+ Female/);
  assert.doesNotMatch(html, /Implant existing Pal/);
});

test('breed anyway does not fall back to a standalone owned Pal', () => {
  const html = renderer().renderBreeding({breedAnyway: true, groups: [{results: [owned]}]});
  assert.match(html, /No breeding pair or setup route found/);
});

test('default implant-ready presentation remains available', () => {
  const html = renderer().renderBreeding({groups: [{results: [owned]}]});
  assert.match(html, /Implant existing Pal/);
});

test('fresh-copy action enables and persists the option before submitting', () => {
  const events = [];
  let click;
  const field = {checked: false, dispatchEvent: event => events.push(event.type)};
  const context = renderer({
    Event: class { constructor(type) { this.type = type; } },
    document: {
      addEventListener: (_, callback) => { click = callback; },
      querySelector: () => field,
    },
    $: () => ({requestSubmit: () => events.push('submit')}),
  });
  context.initFreshCopyToggle();
  click({target: {closest: () => ({})}});
  assert.equal(field.checked, true);
  assert.deepEqual(events, ['change', 'submit']);
});
