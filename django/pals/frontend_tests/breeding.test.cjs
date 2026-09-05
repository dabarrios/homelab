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
  for (const name of ['escapeHtml', 'renderBreeding', 'initFreshCopyToggle']) {
    const start = source.indexOf(`function ${name}(`);
    assert.ok(start >= 0, name);
    vm.runInContext(source.slice(start, source.indexOf('\n}', start) + 2), context);
  }
  return context;
}
const owned = {species: 'Owned match', parents: []};
const route = {species: 'Shroomer Noct', parents: [{species: 'Male'}, {species: 'Female'}]};

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
