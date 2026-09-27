import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {competitionDirections,competitionCreationTasks,competitionFeeStatus} from './src/competition-results.ts';
const feed=JSON.parse(readFileSync(new URL('./public/feed.json',import.meta.url),'utf8'));
const rows=competitionDirections(feed);
assert.equal(feed.items.length,106);
assert.ok(rows.length>106);
const bound=rows.find(r=>r.bindingEvidence?.quote);
assert.ok(bound);assert.ok(competitionCreationTasks(bound).every(t=>t.submissionFormat));
assert.equal(competitionFeeStatus({fee:'免费参赛，可选证书收费100元'}),'free');
assert.ok(rows.some(r=>r.designTypes?.includes('海报')));
console.log(rows.length+' directions; bound deliverables and fee boundary OK');
import {scenarios} from './src/scenarios.ts';
assert.equal(new Set(scenarios.map(s=>s.id)).size,4);
for(const scene of scenarios){
 assert.ok(scene.question && scene.reply);
 assert.ok(scene.resultIds.length<=5);
 for(const id of scene.resultIds)assert.ok(rows.some(r=>r.id===id),'Missing preset result '+id);
}
const poster=scenarios.find(s=>s.id==='poster');
assert.ok(poster.resultIds.every(id=>{const r=rows.find(r=>r.id===id);return r.designTypes.includes('海报')&&r.deadline>='2026-09-22'&&r.deadline<='2026-10-22';}));
assert.equal(scenarios.find(s=>s.id==='empty').resultIds.length,0);
assert.ok(rows.find(r=>r.id===scenarios.find(s=>s.id==='bound').resultIds[0]).bindingEvidence.quote.includes('同时完成'));
assert.ok(!/<(?:input|textarea)\b/i.test(readFileSync(new URL('./index.html',import.meta.url),'utf8')));
console.log('Preset conversations, snapshot dates, bound evidence and no free input OK');
