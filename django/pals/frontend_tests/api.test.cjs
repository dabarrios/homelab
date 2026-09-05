const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '../static/pals/js/tool.js'), 'utf8');
function client({token = 'page-token', response = {ok: true}, status = 200} = {}) {
  const calls = [];
  const context = vm.createContext({
    Headers, FormData,
    document: {querySelector: () => token ? {content: token} : null},
    apiUrl: route => `/pals/api${route}`,
    setLiveStatus: () => {}, fillOptions: () => {},
    fetch: async (url, options) => {
      calls.push({url, options});
      return {ok: status < 400, status, statusText: 'Failure', text: async () => JSON.stringify(response)};
    },
  });
  for (const name of ['api', 'postJson', 'uploadSave']) {
    const signature = source.includes(`async function ${name}(`) ? `async function ${name}(` : `function ${name}(`;
    const start = source.indexOf(signature);
    assert.ok(start >= 0, name);
    vm.runInContext(source.slice(start, source.indexOf('\n}', start) + 2), context);
  }
  return {context, calls};
}

test('JSON posts serialize flags and attach the page CSRF token', async () => {
  const {context, calls} = client();
  await context.postJson('/optimize', {breedAnyway: true, target: 'Shroomer Noct'});
  const {options} = calls[0];
  assert.equal(options.method, 'POST');
  assert.equal(options.headers.get('Content-Type'), 'application/json');
  assert.equal(options.headers.get('X-CSRFToken'), 'page-token');
  assert.deepEqual(JSON.parse(options.body), {breedAnyway: true, target: 'Shroomer Noct'});
  assert.equal(options.mode, 'same-origin');
  assert.equal(options.credentials, 'same-origin');
});

test('GET requests need no CSRF token', async () => {
  const {context, calls} = client({token: null});
  await context.api('/options');
  assert.equal(calls[0].options.headers.has('X-CSRFToken'), false);
});

test('unsafe requests without a page token stop before fetch', async () => {
  const {context, calls} = client({token: null});
  await assert.rejects(context.postJson('/base-labels', {}), /Refresh this page/);
  assert.equal(calls.length, 0);
});

test('multipart requests retain their body and browser-generated content type', async () => {
  const {context, calls} = client();
  const body = new FormData();
  body.append('relativePaths', '["Players/player.sav"]');
  await context.api('/upload-save', {method: 'POST', body});
  assert.equal(calls[0].options.body, body);
  assert.equal(calls[0].options.headers.has('Content-Type'), false);
  assert.equal(calls[0].options.headers.get('X-CSRFToken'), 'page-token');
});

test('save uploads send the relative path separately from the filename', async () => {
  const {context, calls} = client();
  const file = new File(['save bytes'], 'player.sav');
  file.webkitRelativePath = 'Players/player.sav';
  await context.uploadSave(file);
  assert.equal(calls[0].options.body.get('files').name, 'player.sav');
  assert.equal(calls[0].options.body.get('relativePaths'), '["Players/player.sav"]');
  assert.equal(calls[0].options.headers.get('X-CSRFToken'), 'page-token');
});

test('server failures still reach the caller', async () => {
  const {context} = client({response: {error: 'Invalid plan'}, status: 400});
  await assert.rejects(context.postJson('/optimize', {}), /Invalid plan/);
});
