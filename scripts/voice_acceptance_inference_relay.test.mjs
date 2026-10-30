import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

// The Railway Function uses Bun's versioned import. The test copies it beside
// the installed pinned jose package with the equivalent Node import specifier.
globalThis.Bun = {env: {}};
const source = await fs.readFile(new URL('./voice_acceptance_inference_relay.ts', import.meta.url), 'utf8');
const target = process.env.RELAY_TEST_MODULE || path.join(os.tmpdir(), 'voice-relay-test/relay.mjs');
await fs.writeFile(target, source.replace('"jose@6.1.0"', '"jose"'));
const {allowedClaims, makeHandler} = await import(pathToFileURL(target).href);
const claims = {repository_id: '1219502745', repository: 'cesarbohjr/gravitre-saas-backend', actor_id: '108694295',
  sub: 'repo:cesarbohjr/gravitre-saas-backend:environment:acceptance', event_name: 'pull_request', ref: 'refs/pull/587/merge',
  head_ref: 'feat/phase2-dialogue-intelligence', workflow_ref: 'cesarbohjr/gravitre-saas-backend/.github/workflows/voice-gates-2-3.yml@refs/pull/587/merge'};
const env = {ACCEPTANCE_EXPIRES_AT: '2000', ANTHROPIC_API_KEY: 'test-provider-secret'};
function request(body = {model: 'claude-sonnet-4-6', max_tokens: 8, messages: [{role: 'user', content: 'test'}]}, route='/v1/messages') {
  return new Request('https://relay.invalid'+route, {method:'POST', headers:{'x-api-key':'oidc-proof'}, body:JSON.stringify(body)});
}
test('only exact repository, owner actor, workflow, environment and PR identity allowed', () => {
  assert.equal(allowedClaims(claims), true);
  for (const key of Object.keys(claims)) assert.equal(allowedClaims({...claims,[key]:'foreign'}), false, key);
});
test('expired relay cannot contact provider', async () => {
  const handler=makeHandler({env,now:()=>2001,verify:async()=>claims,upstream:()=>assert.fail('provider called')});
  assert.equal((await handler(request())).status,410);
});
test('invalid OIDC and foreign claims fail before provider access',async()=>{
  for(const verify of [async()=>{throw Error('invalid');},async()=>({...claims,actor_id:'other'})]){
    const handler=makeHandler({env,now:()=>1,verify,upstream:()=>assert.fail('provider called')});
    assert.ok([401,403].includes((await handler(request())).status));
  }
});
test('unauthorized endpoint and oversized token budget fail before provider access', async()=>{
  const handler=makeHandler({env,now:()=>1,verify:async()=>claims,upstream:()=>assert.fail('provider called')});
  assert.equal((await handler(request(undefined,'/v1/admin'))).status,404);
  assert.equal((await handler(request({model:'claude-sonnet-4-6',max_tokens:99999,messages:[]}))).status,400);
});
test('valid proof forwards only to fixed Anthropic endpoint and injects Railway key',async()=>{
  let count=0;
  const handler=makeHandler({env,now:()=>1,verify:async()=>claims,upstream:async(url,options)=>{
    count++;assert.equal(url,'https://api.anthropic.com/v1/messages');
    assert.equal(options.headers['x-api-key'],env.ANTHROPIC_API_KEY);
    return Response.json({content:[{text:'test reply'}]});
  }});
  const response=await handler(request());assert.equal(response.status,200);
  assert.equal(count,1);assert.equal(response.headers.get('x-api-key'),null);
});
