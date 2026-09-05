const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '../static/pals/js/tool.js'), 'utf8');
const context = vm.createContext({
  assetUrl: value => value,
  speciesInitials: name => name.slice(0, 2),
  renderTypeChips: () => '',
  passiveTone: () => 'positive',
  breedUrl: () => '/pals/breeding/',
});
for (const name of ['escapeHtml', 'resultCard', 'renderWorkLevelValue', 'renderWorkSkillPills', 'passiveBarHtml', 'renderBases', 'renderBaseWorker']) {
  const start = source.indexOf(`function ${name}(`);
  assert.ok(start >= 0, name);
  const end = source.indexOf('\n}', start) + 2;
  vm.runInContext(source.slice(start, end), context);
}
const worker = {
  name: 'Worker', plannerSlot: 1, plannerRole: 'mining',
  plannerLevels: {mining: 3}, ownedCount: 1,
  work: [{key: 'mining', label: 'Mining', level: 3, fullyCondensedLevel: 7}],
  plannerLocation: 'Palbox 2', plannerLevel: 50, plannerGender: 'Female',
  plannerPassives: ['Artisan'], plannerCondensationStars: 2,
};

test('base plans render assigned workers, not JSON, without mutating the payload', () => {
  const data = {base: {displayName: 'Ore Base'}, plannerMode: 'ideal', maxWorkers: 15, recommendations: [worker]};
  const before = JSON.stringify(data);
  const html = context.renderBases(data);
  assert.match(html, /Ore Base/);
  assert.match(html, /Slot 1/);
  assert.match(html, /Mining/);
  assert.match(html, /Worker/);
  assert.match(html, />Breed</);
  assert.doesNotMatch(html, /json-output/);
  assert.equal(JSON.stringify(data), before);
});

test('right-now workers show current levels, location and passives', () => {
  const html = context.renderBases({plannerMode: 'right_now', recommendations: [worker]});
  assert.match(html, /Palbox 2/);
  assert.match(html, /Artisan/);
  assert.match(html, /<strong>3<\/strong>/);
  assert.doesNotMatch(html, /3 -&gt; 7|>Breed</);
});

test('empty plans, gaps and errors render readable escaped messages', () => {
  assert.match(context.renderBases({recommendations: []}), /No workers match/);
  assert.match(context.renderBases({gaps: [{label: 'Cooling', covered: 0, wanted: 1}]}), /Cooling: 0 \/ 1/);
  const html = context.renderBases({error: '<script>bad</script>'});
  assert.match(html, /No base plan/);
  assert.doesNotMatch(html, /<script>/);
});
