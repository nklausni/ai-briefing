const { setTimeout: sleep } = require('node:timers/promises');

const deployments = '/repos/{owner}/{repo}/pages/deployments';
const deployment = deployments + '/{pages_deployment_id}';
const terminalErrors = new Set([
  'deployment_failed', 'deployment_content_failed', 'deployment_cancelled', 'deployment_lost',
]);

async function create({ github, context, core }, artifactId) {
  if (!/^\d+$/.test(artifactId) || !Number.isSafeInteger(Number(artifactId)) || Number(artifactId) < 1) {
    throw new Error('Upload did not return a valid Pages artifact ID');
  }
  const token = await core.getIDToken();
  core.setSecret(token);
  const { data } = await github.request('POST ' + deployments, {
    ...context.repo, artifact_id: Number(artifactId), pages_build_version: context.sha, oidc_token: token,
  });
  if (!data.id) throw new Error('Missing Pages deployment ID');
  core.setOutput('deployment_id', data.id);
  core.setOutput('page_url', data.page_url);
}

async function wait({ github, context, core }, id, delay = sleep) {
  const params = { ...context.repo, pages_deployment_id: id };
  const deadline = Date.now() + 600_000;
  while (Date.now() < deadline) {
    let status;
    try {
      const { data } = await github.request('GET ' + deployment, params);
      status = data.status;
    } catch (error) {
      if (![404, 408, 429, 500, 502, 503, 504].includes(error.status)) throw error;
      core.warning('Pages status temporarily unavailable (HTTP ' + error.status + ')');
    }
    if (status === 'succeed') return;
    if (terminalErrors.has(status)) {
      core.setOutput('terminal', 'true');
      throw new Error('Pages deployment ' + id + ': ' + status);
    }
    await delay(5000);
  }
  throw new Error('Pages deployment ' + id + ' exceeded ten minutes');
}

module.exports = { create, wait };
