import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile, mkdir, writeFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),{chromium}=require('../tmp/ui-tools/node_modules/playwright');

// Static assets only: this test never imports the server or opens health records.
const fixture=`<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/app.css"><body><main style="padding:24px"><form id="composer"><textarea id="message" rows="3">手写草稿</textarea><div id="voice-status" role="status"></div><button id="voice" type="button">语音输入</button><button id="voice-cancel" type="button" hidden>取消录音</button><button id="send">发送</button></form></main><script type="module">
import {setupVoice} from '/voice.js';
window.qa={calls:[],events:[],sources:[],inputs:0,sends:0,throwStart:false};
const input=document.querySelector('#message');
input.addEventListener('input',()=>qa.inputs++);
document.querySelector('form').onsubmit=e=>{e.preventDefault();qa.sends++;};
window.addEventListener('zhiheng-voice-busy',e=>qa.events.push(e.detail));
window.SpeechRecognition=class{constructor(){throw new Error('Android must use its native bridge');}};
window.installVoiceBridge=()=>window.zhihengNativeVoice={
start:id=>{qa.calls.push(['start',id]);if(qa.throwStart)throw new Error('bridge unavailable');},
stop:()=>qa.calls.push(['stop']),cancel:()=>qa.calls.push(['cancel']),keyboard:()=>qa.calls.push(['keyboard'])};
if(!location.search.includes('late'))installVoiceBridge();
setupVoice(input,document.querySelector('#voice'),document.querySelector('#voice-cancel'),document.querySelector('#voice-status'),s=>qa.sources.push(s),{nativeAckTimeoutMs:3000,nativeResultTimeoutMs:5000,bridgeTimeoutMs:3000});
window.voiceEvent=(name,data)=>window.dispatchEvent(new CustomEvent('zhiheng-voice-'+name,{detail:data}));
window.qa.ready=true;
</script></body></html>`;
const assetMap={'/voice.js':new URL('../voice.js',import.meta.url),'/app.css':new URL('../app.css',import.meta.url)};
const server=createServer(async(req,res)=>{
 try{const path=new URL(req.url,'http://localhost').pathname;
  if(assetMap[path]){res.writeHead(200,{'Content-Type':path.endsWith('.js')?'text/javascript; charset=utf-8':'text/css; charset=utf-8'});res.end(await readFile(assetMap[path]));}
  else if(path==='/'){res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});res.end(fixture);}
  else{res.writeHead(404);res.end();}
 }catch{res.writeHead(500);res.end();}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const base=`http://127.0.0.1:${server.address().port}`;
let browser;const checks=[],errors=[];
try{
 browser=await chromium.launch({headless:true,channel:'msedge'});
 const page=await browser.newPage({viewport:{width:390,height:844},userAgent:'Mozilla/5.0 (Linux; Android 14; Phone Build/UP1A; wv) AppleWebKit/537.36 Version/4.0 Chrome/120.0.0.0 Mobile Safari/537.36'});
 page.on('pageerror',e=>errors.push(e.message));
 const ready=()=>page.waitForFunction(()=>window.qa?.ready);
 const state=(id,state)=>page.evaluate(v=>voiceEvent('state',v),{id,state,canStop:state==='listening'});
 const result=v=>page.evaluate(v=>voiceEvent('result',v),v);
 const start=async()=>{await page.locator('#voice').click();return page.evaluate(()=>qa.calls.filter(c=>c[0]==='start').at(-1)?.[1]);};
 await page.goto(base);await ready();
 const first=await start();assert(first);assert.equal(await page.locator('#voice-cancel').isVisible(),true);
 assert.match(await page.locator('#voice').innerText(),/等待|准备|打开|启动/);
 await state(first,'ready');await state(first,'listening');
 assert.match(await page.locator('#voice').innerText(),/停止|完成录入/);
 assert.equal(await page.locator('#voice').isEnabled(),true,'The user can stop a native recording');
 await page.locator('#voice').click();assert.equal(await page.evaluate(()=>qa.calls.at(-1)[0]),'stop');
 await state(first,'processing');assert.match(await page.locator('#voice-status').innerText(),/识别|处理|整理|等待/);
 await result({id:first,text:'今天散步三十分钟'});
 assert.equal(await page.locator('#message').inputValue(),'手写草稿\n今天散步三十分钟');
 assert.equal(await page.evaluate(()=>qa.sends),0);assert.equal(await page.evaluate(()=>qa.inputs)>0,true);
 assert.equal(await page.evaluate(()=>qa.sources.at(-1)),'voice');
 assert.equal(await page.evaluate(()=>qa.events.at(-1)?.busy),false);
 assert.equal(await page.locator('#voice-cancel').isVisible(),false);
 checks.push('Native ready, listening, stop, processing and result; draft input event; no automatic send');
 const draft=await page.locator('#message').inputValue(),cancelled=await start();
 await page.locator('#voice-cancel').click();await result({id:cancelled,text:'已取消的错误回填'});
 assert.equal(await page.locator('#message').inputValue(),draft);
 const current=await start();await result({id:cancelled,error:'旧会话超时'});await state(current,'listening');
 assert.equal(await page.locator('#voice-cancel').isVisible(),true);
 await result({id:current,text:'新的识别'});assert.equal(await page.locator('#message').inputValue(),draft+'\n新的识别');
 checks.push('Cancellation and stale terminal callbacks preserve the draft and a newer session');
 const failed=await start(),saved=await page.locator('#message').inputValue();
 await result({id:failed,error:'手机没有可用语音识别服务',code:'NO_SERVICE',fallback:true});
 assert.equal(await page.locator('#message').inputValue(),saved);
 const keyboard=page.locator('#voice-status button');await keyboard.waitFor();
 assert.match(await keyboard.innerText(),/输入法|键盘/);await keyboard.click();
 assert.equal(await page.evaluate(()=>qa.calls.at(-1)[0]),'keyboard');
 assert.equal(await page.locator('#message').evaluate(el=>document.activeElement===el),true);
 checks.push('Unavailable service offers a working keyboard voice entry');
 const empty=await start();await result({id:empty,text:'   '});
 assert.equal(await page.locator('#message').inputValue(),saved);
 assert.equal(await page.evaluate(()=>qa.events.at(-1)?.busy),false);
 await page.evaluate(()=>qa.throwStart=true);await start();
 assert.equal(await page.locator('#message').inputValue(),saved);
 assert.equal(await page.evaluate(()=>qa.events.at(-1)?.busy),false);
 await page.evaluate(()=>qa.throwStart=false);
 await page.locator('#message').evaluate(el=>el.disabled=true);
 const before=await page.evaluate(()=>qa.calls.filter(c=>c[0]==='start').length);
 await page.locator('#voice').click();assert.equal(await page.evaluate(()=>qa.calls.filter(c=>c[0]==='start').length),before);
 await page.locator('#message').evaluate(el=>el.disabled=false);
 checks.push('Empty results, synchronous bridge errors and disabled drafts are safe and recoverable');
 await page.goto(base+'?late=1');await ready();await page.locator('#voice').click();
 assert.equal(await page.evaluate(()=>qa.calls.length),0);
 await page.evaluate(()=>{installVoiceBridge();voiceEvent('ready',{});});
 await page.waitForFunction(()=>qa.calls.some(c=>c[0]==='start'));
 const lateId=await page.evaluate(()=>qa.calls.find(c=>c[0]==='start')[1]);
 await state(lateId,'listening');await result({id:lateId,text:'桥接就绪后的识别'});
 assert.equal(await page.locator('#message').inputValue(),'手写草稿\n桥接就绪后的识别');
 checks.push('Android waits for the native bridge instead of starting unsupported Web Speech');
 const appArg=process.argv.find(x=>x.startsWith('--app-url='));
 if(appArg){
  const app=await browser.newPage({viewport:{width:390,height:844},userAgent:'ZhihengAndroid (Linux; Android 14; wv)'}),requests=[];
  app.on('pageerror',e=>errors.push(e.message));app.on('request',r=>{if(r.url().endsWith('/api/work/chat-stream'))requests.push(r.postDataJSON());});
  await app.addInitScript(()=>{
   window.voiceQA={calls:[]};window.zhihengNativeExpected=true;
   window.zhihengNativeVoice={start:id=>voiceQA.calls.push(['start',id]),stop:()=>voiceQA.calls.push(['stop']),cancel:()=>voiceQA.calls.push(['cancel']),keyboard:()=>voiceQA.calls.push(['keyboard'])};
   localStorage.setItem('zhiheng-session-v2','voice-ui-'+crypto.randomUUID());
  });
  await app.goto(appArg.slice('--app-url='.length));await app.getByText('数据已连接',{exact:true}).waitFor();
  const appDone=()=>app.waitForFunction(()=>!document.querySelector('#send').disabled&&!document.querySelector('.thinking-status'));
  const appEvent=(name,data)=>app.evaluate(({name,data})=>window.dispatchEvent(new CustomEvent('zhiheng-voice-'+name,{detail:data})),{name,data});
  const appStart=async()=>{await app.locator('#voice').click();return app.evaluate(()=>voiceQA.calls.filter(c=>c[0]==='start').at(-1)[1]);};
  await app.locator('#message').fill('语音界面验收的历史对话');await app.locator('#send').click();await appDone();
  await app.locator('#new-chat').click();
  const activeCid=await app.evaluate(()=>localStorage.getItem('zhiheng-session-v2'));
  await app.locator('#message').fill('原有的待发送草稿');const appId=await appStart();
  for(const id of ['send','photo','camera'])assert.equal(await app.locator('#'+id).isDisabled(),true,id+' disabled during recording');
  assert.equal(await app.locator('#message').evaluate(el=>el.readOnly),true);
  const countBefore=requests.length;
  await app.locator('#message').press('Enter');assert.equal(requests.length,countBefore);
  await app.locator('#new-chat').click();assert.equal(await app.evaluate(()=>localStorage.getItem('zhiheng-session-v2')),activeCid);
  await app.locator('#open-history').click();
  await app.locator('#history [data-conversation]').filter({hasText:'语音界面验收的历史对话'}).click();
  assert.equal(await app.evaluate(()=>localStorage.getItem('zhiheng-session-v2')),activeCid,'History cannot move the draft while a recording is active');
  await app.locator('#close-history').click();
  await appEvent('state',{id:appId,state:'listening',canStop:true});await appEvent('result',{id:appId,text:'今天步行了三十分钟'});
  await appDone();assert.equal(requests.length,countBefore);assert.equal(await app.locator('#message').inputValue(),'原有的待发送草稿\n今天步行了三十分钟');
  for(const id of ['send','photo','camera'])assert.equal(await app.locator('#'+id).isEnabled(),true,id+' restored after recognition');
  await app.locator('#send').click();await appDone();assert.equal(requests.at(-1).input_source,'voice');assert.equal(requests.at(-1).conversation_id,activeCid);
  await app.locator('#message').fill('取消后保留的草稿');const appCancelled=await appStart();await app.locator('#voice-cancel').click();
  await appEvent('result',{id:appCancelled,text:'已取消的结果'});assert.equal(await app.locator('#message').inputValue(),'取消后保留的草稿');
  for(const id of ['send','photo','camera'])assert.equal(await app.locator('#'+id).isEnabled(),true,id+' restored after cancellation');
  const appFailed=await appStart();await appEvent('result',{id:appFailed,error:'没有可用语音服务',fallback:true});
  assert.equal(await app.locator('#message').inputValue(),'取消后保留的草稿');
  await app.locator('[data-voice-keyboard]').click();assert.equal(await app.evaluate(()=>voiceQA.calls.at(-1)[0]),'keyboard');
  assert.equal(await app.locator('#message').evaluate(el=>el===document.activeElement),true);
  checks.push('Actual app: recording guards Send/Enter/photos/camera/new chat/history; terminal and cancel recover; manual Send carries voice source');
  await app.screenshot({path:'tmp/voice-app-ui-0.4.36.png'});await app.close();
 }
 assert.deepEqual(errors,[]);
 await mkdir('tmp',{recursive:true});await page.screenshot({path:'tmp/voice-ui-0.4.36.png'});
 await writeFile('tmp/voice-ui-0.4.36.json',JSON.stringify({passed:true,checks,browserErrors:errors},null,2));
 console.log(JSON.stringify({passed:true,checks}));
}finally{await browser?.close();await new Promise(resolve=>server.close(resolve));}
