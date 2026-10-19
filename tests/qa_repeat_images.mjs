// Queue/timeline regression checks. Full mobile interaction: qa_image_chat_ui.mjs.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const source=await readFile(new URL('../image-jobs-ui.js',import.meta.url),'utf8');
const {watchImageJobs,conversationTurns}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const job={id:'first',media_id:'photo-1',status:'succeeded',conversation_id:'chat',created_at:'2026-10-12T10:00:00',client_message_id:'image-job-first',result:{client_message_id:'image-job-first'}};
let attempts=0,failFetch=false,states=[];
const watcher=watchImageJobs(async()=>{if(failFetch)throw Error('offline');return {jobs:[job]};},async()=>{if(++attempts===1)throw Error('temporary state failure');},()=>{},state=>states.push(structuredClone(state)));
watcher.stop();await tick();
assert.match(states.at(-1).error,/重新读取回复/);
await watcher.poll();assert.equal(attempts,2);assert.equal(states.at(-1).error,'');
const publications=states.length;await watcher.poll();assert.equal(attempts,2);assert.equal(states.length,publications);
failFetch=true;await watcher.poll();assert.equal(states.at(-1).jobs[0].id,'first');assert.match(states.at(-1).error,/重连/);
failFetch=false;await watcher.poll();assert.equal(states.at(-1).error,'');

// An in-flight old response cannot remove the photo just accepted after upload.
let resolvePoll,raceState;
const race=watchImageJobs(()=>new Promise(resolve=>{resolvePoll=resolve;}),async()=>{},()=>{},state=>{raceState=structuredClone(state);});
race.stop();race.accept({...job,status:'pending',result:null});resolvePoll({jobs:[]});await tick();
assert.equal(raceState.jobs.length,1);assert.equal(raceState.jobs[0].status,'pending');
const nextPoll=race.poll();resolvePoll({jobs:[job]});await nextPoll;assert.equal(raceState.jobs[0].status,'succeeded');
const deletedPoll=race.poll();resolvePoll({jobs:[]});await deletedPoll;assert.deepEqual(raceState.jobs,[]);

const messages=[
 {id:'plain',role:'user',text:'后来补充',created_at:'2026-10-12T10:00:05'},
 {id:'plain-answer',role:'assistant',created_at:'2026-10-12T10:00:06'},
 {id:'image-job-first',role:'user',media_id:'photo-1',created_at:'2026-10-12T10:00:20'},
 {id:'image-answer',role:'assistant',created_at:'2026-10-12T10:00:21'}
];
const second={...job,id:'second',media_id:'photo-2',client_message_id:'image-job-second',created_at:'2026-10-12T10:00:10',status:'running',result:null};
const other={...job,id:'other',conversation_id:'other-chat'};
const before=conversationTurns(messages.slice(0,2),[{...job,status:'running',result:null},second,other],'chat');
const after=conversationTurns(messages,[job,second,other],'chat');
assert.deepEqual(before.map(t=>t.key),['image-job-first','plain','image-job-second']);
assert.deepEqual(after.map(t=>t.key),before.map(t=>t.key));
assert.equal(after[0].assistant.id,'image-answer');assert.equal(after[1].assistant.id,'plain-answer');
assert.equal(after[2].assistant,null);assert.equal(after.length,3);
assert.equal(conversationTurns(messages,[],'chat').length,2);
console.log('Passed: result refresh recovery, stable polling, upload race, deleted jobs, two-image order, conversation isolation, historical turns.');
