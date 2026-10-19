import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),{chromium}=require('../tmp/ui-tools/node_modules/playwright');

// Only local static assets and a deterministic native bridge. No microphone,
// personal health records, remote model service, or proxy is used by this test.
const fixture=`<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/app.css"><body><main style="padding:24px"><form id="composer"><textarea id="message" rows="3">已有草稿</textarea><div id="voice-status" role="status"></div><button id="voice" type="button">语音输入</button><button id="voice-cancel" type="button" hidden>取消录音</button><button id="send">发送</button></form></main><script type="module">
import {setupVoice} from '/voice.js';
window.qa={calls:[],busy:[],sources:[],inputs:0,sends:0};
window.zhihengNativeExpected=true;
window.SpeechRecognition=class {constructor(){throw Error('Android offline voice must not invoke Web Speech');}};
window.zhihengNativeVoice={start:id=>qa.calls.push(['start',id]),stop:()=>qa.calls.push(['stop']),cancel:()=>qa.calls.push(['cancel']),keyboard:()=>qa.calls.push(['keyboard'])};
const input=document.querySelector('#message');input.addEventListener('input',()=>qa.inputs++);
document.querySelector('form').onsubmit=e=>{e.preventDefault();qa.sends++;};
window.addEventListener('zhiheng-voice-busy',e=>qa.busy.push(e.detail.busy));
setupVoice(input,document.querySelector('#voice'),document.querySelector('#voice-cancel'),document.querySelector('#voice-status'),s=>qa.sources.push(s),{nativeAckTimeoutMs:3000,nativeResultTimeoutMs:6000});
window.voiceEvent=(name,data)=>window.dispatchEvent(new CustomEvent('zhiheng-voice-'+name,{detail:data}));
window.qa.ready=true;
</script></body></html>`;
const assets={'/voice.js':new URL('../voice.js',import.meta.url),'/app.css':new URL('../app.css',import.meta.url)};
const server=createServer(async(req,res)=>{try{
 const path=new URL(req.url,'http://127.0.0.1').pathname;
 if(assets[path]){res.writeHead(200,{'Content-Type':path.endsWith('.js')?'text/javascript; charset=utf-8':'text/css; charset=utf-8'});res.end(await readFile(assets[path]));}
 else if(path==='/'){res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});res.end(fixture);}
 else{res.writeHead(404);res.end();}
}catch{res.writeHead(500);res.end();}});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const base=`http://127.0.0.1:${server.address().port}`;
const checks=[],errors=[],remoteRequests=[];let browser;
try{
 browser=await chromium.launch({headless:true,channel:'msedge'});
 const context=await browser.newContext({viewport:{width:390,height:844},userAgent:'ZhihengAndroid (Linux; Android 14; wv)'});
 context.on('request',r=>{if(!r.url().startsWith('http://127.0.0.1:')&&!r.url().startsWith('data:'))remoteRequests.push(r.url());});
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base);await page.waitForFunction(()=>qa.ready);
 const event=(name,data)=>page.evaluate(({name,data})=>voiceEvent(name,data),{name,data});
 const state=(id,state,text='')=>event('state',{id,state,text,engine:'offline',canStop:state==='listening'});
 const result=data=>event('result',{engine:'offline',...data});
 const start=async()=>{await page.locator('#voice').click();return page.evaluate(()=>qa.calls.filter(c=>c[0]==='start').at(-1)[1]);};
 const first=await start();await state(first,'ready');
 assert.match(await page.locator('#voice-status').innerText(),/离线/,'Preparation must explain the installed offline model');
 await state(first,'preparing');assert.equal(await page.locator('#voice-cancel').isVisible(),true);
 await state(first,'listening');assert.match(await page.locator('#voice-status').innerText(),/离线|无需联网/);
 assert.equal(await page.locator('#voice').isEnabled(),true);assert.equal(await page.locator('#message').evaluate(el=>el.readOnly),true);
 await state(first,'listening','今天 中午 吃了 鸡肉');
 assert.equal(await page.locator('#message').inputValue(),'已有草稿\n今天 中午 吃了 鸡肉','Live hypotheses must appear in the input');
 assert.match(await page.locator('#voice-status').innerText(),/输入框|完成录入/);
 await page.locator('#voice').click();assert.equal(await page.evaluate(()=>qa.calls.at(-1)[0]),'stop');
 await state(first,'processing');await result({id:first,text:'今天中午吃了鸡肉和米饭'});
 assert.equal(await page.locator('#message').inputValue(),'已有草稿\n今天中午吃了鸡肉和米饭');
 assert.equal(await page.evaluate(()=>qa.sends),0);assert.equal(await page.evaluate(()=>qa.sources.at(-1)),'voice');
 assert.equal(await page.evaluate(()=>qa.busy.at(-1)),false);assert.equal(await page.locator('#voice-cancel').isVisible(),false);
 checks.push('Offline preparation is explained; live transcription fills input; Complete replaces preview with final text without sending');
 const saved=await page.locator('#message').inputValue(),cancelled=await start();await state(cancelled,'preparing');
 await page.locator('#voice-cancel').click();await state(cancelled,'listening','被取消的结果');await result({id:cancelled,text:'被取消的结果'});
 assert.equal(await page.locator('#message').inputValue(),saved);
 const newer=await start();await state(newer,'listening');await result({id:cancelled,error:'旧录音超时',fallback:true});
 assert.equal(await page.locator('#voice-cancel').isVisible(),true);await result({id:newer,text:'走了三十分钟'});
 assert.equal(await page.locator('#message').inputValue(),saved+'\n走了三十分钟');
 checks.push('Cancelling during model preparation invalidates states/results; an older result cannot terminate a new recording');
 const failed=await start(),beforeFailure=await page.locator('#message').inputValue();
 await result({id:failed,error:'离线中文语音资源暂不可用，请使用输入法语音。',code:'VOICE_MODEL_UNAVAILABLE',fallback:true});
 assert.equal(await page.locator('#message').inputValue(),beforeFailure);await page.locator('[data-voice-keyboard]').click();
 assert.equal(await page.evaluate(()=>qa.calls.at(-1)[0]),'keyboard');assert.equal(await page.locator('#message').evaluate(el=>el===document.activeElement),true);
 const permission=await start();await result({id:permission,error:'请允许麦克风权限后重试。',code:'VOICE_PERMISSION_DENIED',fallback:true});
 assert.equal(await page.locator('#message').inputValue(),beforeFailure);assert.equal(await page.evaluate(()=>qa.sends),0);
 checks.push('Model and permission failures preserve drafts and offer keyboard dictation without invoking a cloud recognizer');
 const appArg=process.argv.find(arg=>arg.startsWith('--app-url='));
 if(appArg){
  const app=await context.newPage(),chatRequests=[];app.on('pageerror',e=>errors.push(e.message));
  app.on('request',r=>{if(r.url().endsWith('/api/work/chat-stream'))chatRequests.push(r.postDataJSON());});
  await app.addInitScript(()=>{
   window.zhihengNativeExpected=true;window.voiceQA={calls:[]};
   window.SpeechRecognition=class {constructor(){throw Error('Offline Android must not start Web Speech');}};
   window.zhihengNativeVoice={start:id=>voiceQA.calls.push(['start',id]),stop:()=>voiceQA.calls.push(['stop']),cancel:()=>voiceQA.calls.push(['cancel']),keyboard:()=>voiceQA.calls.push(['keyboard'])};
   localStorage.setItem('zhiheng-session-v2','offline-voice-ui-'+crypto.randomUUID());
  });
  await app.goto(appArg.slice('--app-url='.length));await app.getByText('数据已连接',{exact:true}).waitFor();
  const appDone=()=>app.waitForFunction(()=>!document.querySelector('#send').disabled&&!document.querySelector('.thinking-status'));
  const appEvent=(name,data)=>app.evaluate(({name,data})=>window.dispatchEvent(new CustomEvent('zhiheng-voice-'+name,{detail:{engine:'offline',...data}})),{name,data});
  const appStart=async()=>{await app.locator('#voice').click();return app.evaluate(()=>voiceQA.calls.filter(c=>c[0]==='start').at(-1)[1]);};
  await app.locator('#message').fill('等待发送的原有草稿');const appId=await appStart(),count=chatRequests.length;
  await appEvent('state',{id:appId,state:'preparing',canStop:false});assert.match(await app.locator('#voice-status').innerText(),/离线/);
  for(const id of ['send','photo','camera'])assert.equal(await app.locator('#'+id).isDisabled(),true,id+' must be locked during offline recording');
  const cid=await app.evaluate(()=>localStorage.getItem('zhiheng-session-v2'));await app.locator('#new-chat').click();
  assert.equal(await app.evaluate(()=>localStorage.getItem('zhiheng-session-v2')),cid);await app.locator('#message').press('Enter');assert.equal(chatRequests.length,count);
  await appEvent('state',{id:appId,state:'listening',canStop:true,text:'我 今天 散步'});
  assert.equal(await app.locator('#message').inputValue(),'等待发送的原有草稿\n我 今天 散步');
  assert.equal(await app.locator('#send').isEnabled(),true);assert.equal(await app.locator('#send').innerText(),'完成录入');
  await app.screenshot({path:'tmp/offline-voice-recording-0.4.38.png'});
  await app.locator('#send').click();assert.equal(await app.evaluate(()=>voiceQA.calls.at(-1)[0]),'stop');assert.equal(chatRequests.length,count,'Complete must never send an unreviewed transcript');
  await appEvent('state',{id:appId,state:'processing',canStop:false});await appEvent('result',{id:appId,text:'我今天散步三十分钟'});await appDone();
  assert.equal(chatRequests.length,count);assert.equal(await app.locator('#message').inputValue(),'等待发送的原有草稿\n我今天散步三十分钟');
  for(const id of ['send','photo','camera'])assert.equal(await app.locator('#'+id).isEnabled(),true,id+' must recover after offline final result');
  await app.locator('#send').click();await appDone();assert.equal(chatRequests.at(-1).input_source,'voice');assert.equal(chatRequests.at(-1).conversation_id,cid);
  checks.push('Actual app: live transcript in input, main Complete button stops recording, final Send submits voice text only on explicit confirmation');
  // Compact phones and an open keyboard must keep the primary completion control visible.
  for(const viewport of [{width:320,height:640},{width:390,height:440}]){
   await app.setViewportSize(viewport);await app.locator('#message').fill('');const id=await appStart();
   await appEvent('state',{id,state:'listening',canStop:true,text:'今天想出去走一走'});
   const button=app.locator('#send'),rect=await button.boundingBox();assert(rect&&rect.x>=0&&rect.x+rect.width<=viewport.width&&rect.y>=0&&rect.y+rect.height<=viewport.height,'Complete stays in the visible viewport');
   await button.click();await appEvent('result',{id,text:'今天想出去走一走'});await appDone();
   assert.equal(await button.innerText(),'发送');assert.equal(await app.locator('#message').evaluate(el=>el.readOnly),false);
  }
  checks.push('Primary Complete button remains visible on 320px phone and keyboard-height viewport; editing and Send recover');
  await app.setViewportSize({width:390,height:844});await app.locator('#message').fill('超时前的草稿');const slow=await appStart(),beforeTimeout=chatRequests.length;
  await appEvent('state',{id:slow,state:'listening',canStop:true,text:'今天走了三十分钟'});await app.locator('#send').click();
  await app.waitForFunction(()=>!document.querySelector('#send').disabled,{},{timeout:18000});
  assert.equal(await app.locator('#message').inputValue(),'超时前的草稿\n今天走了三十分钟');
  assert.match(await app.locator('#voice-status').innerText(),/超时.*保留.*核对/);assert.equal(chatRequests.length,beforeTimeout);
  await app.locator('#message').fill('今天走了三十分钟，已核对');await appEvent('result',{id:slow,text:'迟到的错误覆盖'});
  assert.equal(await app.locator('#message').inputValue(),'今天走了三十分钟，已核对');await app.locator('#send').click();await appDone();
  assert.equal(chatRequests.at(-1).text,'今天走了三十分钟，已核对');assert.equal(chatRequests.at(-1).input_source,'voice');
  checks.push('Actual app: stalled final callback recovers within 15 seconds, preserves preview for editing, ignores late results and can send normally');
  await mkdir('tmp',{recursive:true});await app.screenshot({path:'tmp/offline-voice-app-ui-0.4.38.png'});await app.close();
 }
 assert.deepEqual(errors,[]);assert.deepEqual(remoteRequests,[],'Voice interaction must make no external network requests');
 await mkdir('tmp',{recursive:true});await page.screenshot({path:'tmp/offline-voice-ui-0.4.38.png'});
 await writeFile('tmp/offline-voice-ui-0.4.38.json',JSON.stringify({passed:true,checks,browserErrors:errors,remoteRequests},null,2));
 console.log(JSON.stringify({passed:true,checks}));
}finally{await browser?.close();await new Promise(resolve=>server.close(resolve));}
