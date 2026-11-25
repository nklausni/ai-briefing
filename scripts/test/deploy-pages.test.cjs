const { test } = require('node:test');
const assert = require('node:assert/strict');
const { create, wait } = require('../deploy-pages.cjs');

function fixture(replies) {
  const requests = [];
  const outputs = {};
  return {
    requests, outputs, context: { repo: { owner: 'example', repo: 'test' }, sha: 'test-sha' },
    core: { getIDToken: async () => 'test-token', setSecret() {}, warning() {},
      setOutput(key, value) { outputs[key] = value; } },
    github: { async request(route, params) {
      requests.push({ route, params });
      assert.ok(replies.length, 'Unexpected request: ' + route);
      const reply = replies.shift();
      if (reply instanceof Error) throw reply;
      return { data: reply };
    } },
  };
}

test('deploys the upload receipt without listing artifacts, then waits for that deployment', async () => {
  const api = fixture([{ id: 'd1', page_url: 'https://example.test' },
    Object.assign(new Error('not visible yet'), { status: 404 }), { status: 'deploying' }, { status: 'succeed' }]);
  await create(api, '15001754071');
  await wait(api, api.outputs.deployment_id, async () => {});
  assert.equal(api.requests[0].route, 'POST /repos/{owner}/{repo}/pages/deployments');
  assert.equal(api.requests[0].params.artifact_id, 15001754071);
  assert.equal(api.requests[0].params.pages_build_version, api.context.sha);
  assert.equal(api.requests[0].params.oidc_token, 'test-token');
  assert.equal(api.outputs.page_url, 'https://example.test');
  for (const { route, params } of api.requests.slice(1)) {
    assert.equal(route, 'GET /repos/{owner}/{repo}/pages/deployments/{pages_deployment_id}');
    assert.equal(params.pages_deployment_id, 'd1');
  }
});

test('missing upload receipt stops before the first request', async () => {
  const api = fixture([]);
  await assert.rejects(create(api, ''), /valid Pages artifact ID/);
  assert.equal(api.requests.length, 0);
});

test('reports a terminal Pages error and never creates a second deployment', async () => {
  const api = fixture([{ status: 'deployment_content_failed' }]);
  await assert.rejects(wait(api, 'd2'), /deployment_content_failed/);
  assert.equal(api.requests.length, 1);
});
