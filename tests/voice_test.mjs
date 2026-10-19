import assert from 'node:assert/strict';
import {setupVoice} from '../voice.js';

class Element extends EventTarget {
 constructor(tag='div'){super();this.tagName=tag.toUpperCase();this.value='';this.disabled=false;this.hidden=false;this.readOnly=false;this.children=[];this.dataset={};this.style={};this.ownerDocument=document;this._text='';this.attributes={};}
 set textContent(v){this._text=String(v);this.children=[];}get textContent(){return this._text+this.children.map(x=>x.textContent||'').join('');}
 set innerHTML(v){this._text=String(v);this.children=[];}get innerHTML(){return this._text;}
 append(...children){this.children.push(...children);}appendChild(child){this.append(child);return child;}
 replaceChildren(...children){this._text='';this.children=children;}
 setAttribute(k,v){this.attributes[k]=String(v);if(k.startsWith('data-'))this.dataset[k.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]=String(v);}
 getAttribute(k){return this.attributes[k]??null;}removeAttribute(k){delete this.attributes[k];}
 focus(){document.activeElement=this;}
 querySelector(selector){return this.children.find(c=>selector==='button'?c.tagName==='BUTTON':selector==='[data-voice-keyboard]'&&('voiceKeyboard' in c.dataset))||null;}
}
const document={activeElement:null,createElement:tag=>new Element(tag),createTextNode:text=>({textContent:text}),defaultView:null};
globalThis.document=document;
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const opts={nativeAckTimeoutMs:25,nativeResultTimeoutMs:150,processingTimeoutMs:25,browserTimeoutMs:2000,bridgeTimeoutMs:25};
let cleanup,checks=0;
function environment(extra={}){
 cleanup?.destroy();
 const w=new EventTarget();Object.assign(w,{navigator:{userAgent:'Desktop QA'},isSecureContext:true,CustomEvent,Event,setTimeout,clearTimeout},extra);globalThis.window=w;document.defaultView=w;
 const input=new Element('textarea'),button=new Element('button'),cancel=new Element('button'),status=new Element();input.value='已有草稿';const sources=[],busy=[],events=[];
 input.addEventListener('input',e=>events.push(e));w.addEventListener('zhiheng-voice-busy',e=>busy.push(e.detail.busy));
 cleanup=setupVoice(input,button,cancel,status,s=>sources.push(s),opts);
 return {w,input,button,cancel,status,sources,busy,events,emit:(name,data)=>w.dispatchEvent(new CustomEvent('zhiheng-voice-'+name,{detail:data}))};
}
let latest;
class Recognition {constructor(){latest=this;}start(){this.onstart?.();}stop(){this.onend?.();}abort(){this.onend?.();}}
const speech=text=>({results:[Object.assign([{transcript:text}],{isFinal:true})]});
{
 const e=environment({SpeechRecognition:Recognition});e.button.onclick();latest.onresult(speech('今天体重七十八公斤'));
 assert.equal(e.input.value,'已有草稿\n今天体重七十八公斤');assert(e.events.length);
 e.cancel.onclick();assert.equal(e.input.value,'已有草稿');assert.equal(e.cancel.hidden,true);assert.equal(e.input.readOnly,false);
 e.button.onclick();latest.onresult(speech('未完成识别'));latest.onerror({error:'network'});
 assert.equal(e.input.value,'已有草稿');assert.match(e.status.textContent,/连接失败|网络/);
 e.button.onclick();latest.onerror({error:'not-allowed'});assert.match(e.status.textContent,/权限|隐私|麦克风/);
 e.button.onclick();const stale=latest;stale.onerror({error:'network'});e.button.onclick();const current=latest;
 stale.onend();stale.onresult(speech('旧结果'));stale.onerror({error:'not-allowed'});
 assert.equal(e.cancel.hidden,false);current.onresult(speech('新识别'));assert.equal(e.input.value,'已有草稿\n新识别');
 current.onend();assert.equal(e.sources.at(-1),'voice');assert.equal(e.input.readOnly,false);assert.equal(e.busy.at(-1),false);checks+=6;
}
{
 const e=environment({SpeechRecognition:Recognition,isSecureContext:false});e.button.onclick();assert.match(e.status.textContent,/HTTPS|安全/);assert.equal(e.input.value,'已有草稿');checks++;
}
{
 const e=environment({SpeechRecognition:Recognition});e.input.disabled=true;e.button.onclick();assert.equal(e.busy.length,0);assert.equal(e.input.value,'已有草稿');checks++;
}
function native(extra={}){
 const calls=[];const e=environment({navigator:{userAgent:'ZhihengAndroid (Android; wv)'},zhihengNativeExpected:true,SpeechRecognition:class{constructor(){throw Error('Native WebView must not start Web Speech');}},zhihengNativeVoice:{start:id=>calls.push(['start',id]),stop:()=>calls.push(['stop']),cancel:()=>calls.push(['cancel']),keyboard:()=>calls.push(['keyboard'])},...extra});
 e.calls=calls;e.start=()=>{e.button.onclick();return calls.filter(c=>c[0]==='start').at(-1)?.[1];};return e;
}
{
 const e=native(),id=e.start();assert(id);assert.equal(e.input.readOnly,true);assert.equal(e.cancel.hidden,false);
 e.emit('state',{id,state:'ready'});e.emit('state',{id,state:'listening',canStop:true});assert.equal(e.button.disabled,false);
 e.button.onclick();assert.equal(e.calls.at(-1)[0],'stop');e.emit('state',{id,state:'processing'});
 e.emit('result',{id,text:'今天散步了'});assert.equal(e.input.value,'已有草稿\n今天散步了');assert.equal(e.sources.at(-1),'voice');assert(e.events.length);
 assert.equal(e.busy.at(-1),false);assert.equal(e.input.readOnly,false);assert.equal(e.cancel.hidden,true);checks+=4;
 const cancelled=e.start(),draft=e.input.value;e.cancel.onclick();assert.equal(e.calls.at(-1)[0],'cancel');
 e.emit('result',{id:cancelled,text:'取消后的结果'});assert.equal(e.input.value,draft);
 const fresh=e.start();e.emit('state',{id:cancelled,state:'listening'});e.emit('result',{id:cancelled,error:'旧失败'});
 assert.equal(e.cancel.hidden,false);e.emit('result',{id:fresh,text:'新的结果'});assert.equal(e.input.value,draft+'\n新的结果');checks+=2;
}
{
 const e=native(),id=e.start();e.emit('result',{id,error:'没有语音服务',code:'NO_SERVICE',fallback:true});
 assert.equal(e.input.value,'已有草稿');assert.equal(e.busy.at(-1),false);
 const keyboard=e.status.querySelector('[data-voice-keyboard]');assert(keyboard);keyboard.onclick();
 assert.equal(e.calls.at(-1)[0],'keyboard');assert.equal(document.activeElement,e.input);
 const next=e.start();e.emit('result',{id:next,text:'   '});assert.equal(e.input.value,'已有草稿');assert.equal(e.cancel.hidden,true);checks+=2;
}
{
 const e=native({zhihengNativeVoice:{start:()=>{throw Error('bridge failure');},cancel:()=>{},keyboard:()=>{}}});
 e.button.onclick();assert.equal(e.input.value,'已有草稿');assert.equal(e.input.readOnly,false);assert.equal(e.cancel.hidden,true);assert.equal(e.busy.at(-1),false);checks++;
}
{
 const e=native(),id=e.start();await sleep(50);assert.equal(e.input.value,'已有草稿');assert.equal(e.cancel.hidden,true);assert.equal(e.input.readOnly,false);assert.equal(e.busy.at(-1),false);
 e.emit('result',{id,text:'启动超时后迟到的文字'});assert.equal(e.input.value,'已有草稿');
 const next=e.start();assert(next&&next!==id);e.emit('state',{id:next,state:'listening',canStop:true});e.emit('result',{id:next,text:'重试成功'});
 assert.equal(e.input.value,'已有草稿\n重试成功');checks+=2;
}
{
 const e=native(),id=e.start();e.emit('state',{id,state:'listening',canStop:true});await sleep(180);
 assert.equal(e.input.value,'已有草稿');assert.equal(e.cancel.hidden,true);assert.equal(e.input.readOnly,false);assert.equal(e.busy.at(-1),false);
 e.emit('result',{id,text:'处理超时后迟到的文字'});assert.equal(e.input.value,'已有草稿');checks++;
}
{
 const e=native({zhihengNativeVoice:undefined});e.button.onclick();assert.equal(e.calls.length,0);
 e.w.zhihengNativeVoice={start:id=>e.calls.push(['start',id]),cancel:()=>{},keyboard:()=>{}};e.emit('ready',{});
 const id=e.calls[0]?.[1];assert(id);e.emit('state',{id,state:'listening',canStop:true});e.emit('result',{id,text:'桥接已就绪'});
 assert.equal(e.input.value,'已有草稿\n桥接已就绪');checks++;
}
{
 const e=native({zhihengNativeVoice:undefined});e.button.onclick();await sleep(50);assert.equal(e.cancel.hidden,true);assert.equal(e.input.readOnly,false);assert.equal(e.busy.at(-1),false);
 e.w.zhihengNativeVoice={start:id=>e.calls.push(['start',id]),cancel:()=>{},keyboard:()=>{}};e.emit('ready',{});assert.equal(e.calls.length,0,'Late bridge readiness cannot restart a timed-out request');checks++;
}
{
 const e=native(),id=e.start();e.emit('state',{id,state:'listening',canStop:true,text:'今天吃了'});
 assert.equal(e.input.value,'已有草稿\n今天吃了','Live transcription must be visible inside the input');
 e.emit('state',{id,state:'listening',canStop:true,text:'今天吃了鸡肉'});
 assert.equal(e.input.value,'已有草稿\n今天吃了鸡肉','Revised hypotheses replace the previous preview without duplication');
 cleanup.finish();assert.equal(e.calls.at(-1)[0],'stop');
 e.emit('state',{id,state:'listening',canStop:true,text:'停止后迟到的预览'});assert.equal(e.button.disabled,true);
 await sleep(50);assert.equal(e.input.value,'已有草稿\n今天吃了鸡肉');assert.equal(e.input.readOnly,false);
 assert.equal(e.busy.at(-1),false);assert.equal(e.sources.at(-1),'voice');assert.match(e.status.textContent,/超时.*保留.*核对/);
 e.input.value+='，已核对';e.emit('result',{id,text:'迟到的最终结果'});assert.equal(e.input.value,'已有草稿\n今天吃了鸡肉，已核对');checks+=4;
}
{
 const e=native(),id=e.start();e.emit('state',{id,state:'listening',canStop:true,text:'应该取消的文字'});
 e.cancel.onclick();assert.equal(e.input.value,'已有草稿');assert.deepEqual(e.sources,[]);checks++;
 const next=e.start();e.emit('state',{id:next,state:'listening',canStop:true,text:'已经识别出来的文字'});
 e.emit('result',{id:next,error:'收尾失败'});assert.equal(e.input.value,'已有草稿\n已经识别出来的文字');assert.equal(e.input.readOnly,false);checks++;
}
cleanup?.destroy();
console.log(JSON.stringify({passed:true,checks,coverage:['draft preservation','input events','Web Speech stale callbacks','native stop/cancel','native stale callbacks','synchronous failure','ack/result/bridge timeouts','retry','keyboard fallback','disabled input']}));
