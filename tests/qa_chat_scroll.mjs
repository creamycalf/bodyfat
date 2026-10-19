import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {writeFile} from 'node:fs/promises';

const require=createRequire(import.meta.url);
const {chromium}=require('../tmp/ui-tools/node_modules/playwright');
const url=process.argv[2]||'http://127.0.0.1:8798';
const browser=await chromium.launch({headless:true,channel:'msedge'});
const report={passed:false,fixture:'isolated synthetic chat/image responses',checks:[],failures:[],screenshots:[]};
const errors=[];
let activePage;

async function check(name,task){
 try{const evidence=await task();report.checks.push({name,passed:true,...(evidence||{})});}
 catch(error){report.failures.push({name,error:error.message});report.checks.push({name,passed:false});console.error(name+': '+error.message);}
}
async function ready(page){
 await page.waitForFunction(()=>document.querySelector('#connection')?.textContent==='数据已连接');
 await page.waitForFunction(()=>getComputedStyle(document.querySelector('#composer')).position==='fixed');
}
async function waitDone(page){
 await page.waitForFunction(()=>!document.querySelector('.thinking-status')&&!document.querySelector('#send').disabled);
 await page.waitForTimeout(220);
}
async function send(page,text){
 await page.locator('#message').fill(text);await page.locator('#send').click();await waitDone(page);
}
async function geometry(page){
 return page.evaluate(()=>{
  const composer=document.querySelector('#composer').getBoundingClientRect();
  const anchor=document.querySelector('#chat-end')?.getBoundingClientRect();
  const latest=document.querySelector('#messages')?.lastElementChild?.getBoundingClientRect();
  const send=document.querySelector('#send'),button=send.getBoundingClientRect();
  const viewport=window.visualViewport;
  return {scrollY,documentHeight:document.documentElement.scrollHeight,viewportHeight:innerHeight,
   visualHeight:viewport?.height,visualOffset:viewport?.offsetTop,
   composerTop:composer.top,composerBottom:composer.bottom,
   anchorBottom:anchor?.bottom,anchorGap:anchor?composer.top-anchor.bottom:null,
   latestBottom:latest?.bottom,latestGap:latest?composer.top-latest.bottom:null,
   sendUsable:button.top>=0&&button.bottom<=innerHeight&&send.contains(document.elementFromPoint(button.x+button.width/2,button.y+button.height/2)),
   overflow:document.documentElement.scrollWidth>innerWidth,
   keyboardOpen:document.body.classList.contains('chat-keyboard-open'),
   latestButtonVisible:!!document.querySelector('#chat-latest')&&!document.querySelector('#chat-latest').hidden};
 });
}
async function assertAnchored(page,label){
 // No scroll commands are used in this helper: positioning must be provided by the app.
 await page.waitForTimeout(180);
 const g=await geometry(page);
 assert.equal(g.overflow,false,label+' has horizontal overflow');
 assert.equal(g.sendUsable,true,label+' send control is covered: '+JSON.stringify(g));
 assert(g.anchorGap!==null,label+' has no latest-content anchor');
 assert(g.anchorGap>=11&&g.anchorGap<=22,label+' anchor must finish above input: '+JSON.stringify(g));
 assert(g.latestGap>=11&&g.latestGap<50,label+' latest content is obscured or far from input: '+JSON.stringify(g));
 assert.equal(g.latestButtonVisible,false,label+' still offers Return to latest while following');
 return g;
}
async function screenshot(page,name){
 const path='tmp/'+name+'-0.4.34.png';await page.screenshot({path});report.screenshots.push(path);
}
async function upload(page,image,text){
 await page.locator('#photo-file').setInputFiles({name:'scroll-fixture.png',mimeType:'image/png',buffer:Buffer.from(image,'base64')});
 await page.locator('#pending-attachment').waitFor({state:'visible'});
 await page.locator('#message').fill(text);await page.locator('#send').click();
 await page.locator('#pending-attachment').waitFor({state:'hidden'});
 await page.locator('.image-inline-progress').last().waitFor();
 await waitDone(page);
}
async function release(page){
 await page.evaluate(async()=>{const r=await fetch('/__qa__/release',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({fail:false})});if(!r.ok)throw Error('fixture release failed');});
}

try{
 for(const width of [320,390,1280]){
  const context=await browser.newContext({viewport:{width,height:844}});
  const page=await context.newPage();activePage=page;
  page.on('pageerror',e=>errors.push({width,error:e.message}));page.on('dialog',d=>d.accept());
  await page.addInitScript(id=>localStorage.setItem('zhiheng-session-v2',id),'scroll-ui-'+width+'-'+Date.now());
  await page.goto(url);await ready(page);
  await send(page,'滚动验收长回复：请用合成内容检查聊天位置。');
  await check(width+' long reply anchors without test scrolling',async()=>{
   assert.match(await page.locator('.chat-turn .assistant').last().innerText(),/第 30 段/);
   return assertAnchored(page,width+' long reply');
  });
  await screenshot(page,'chat-scroll-long-'+width);
  await page.locator('#message').fill('滚动验收慢回复：检查等待位置。');await page.locator('#send').click();
  await page.locator('.thinking-status').waitFor();
  await check(width+' pending reply remains above input',()=>assertAnchored(page,width+' pending reply'));
  await waitDone(page);
  await check(width+' final short reply replaces pending at bottom',()=>assertAnchored(page,width+' final reply'));
  await check(width+' reload opens historical conversation at latest',async()=>{
   await page.reload();await ready(page);await page.locator('.chat-turn').last().waitFor();
   return assertAnchored(page,width+' restored history');
  });
  if(width<760){
   await page.locator('#message').focus();await page.setViewportSize({width,height:450});
   await page.waitForFunction(()=>document.body.classList.contains('chat-keyboard-open'));
   await check(width+' shrinking viewport keeps latest above keyboard',()=>assertAnchored(page,width+' keyboard viewport'));
   await screenshot(page,'chat-scroll-keyboard-'+width);
   await page.setViewportSize({width,height:844});
   await page.waitForFunction(()=>!document.body.classList.contains('chat-keyboard-open'));
   await check(width+' keyboard dismissal preserves latest position',()=>assertAnchored(page,width+' restored viewport'));
  }
  if(width===390){
   const image=await page.evaluate(()=>{const c=document.createElement('canvas');c.width=480;c.height=360;const x=c.getContext('2d');x.fillStyle='#dde7d6';x.fillRect(0,0,480,360);x.fillStyle='#ba8d56';x.beginPath();x.ellipse(240,180,150,110,0,0,Math.PI*2);x.fill();return c.toDataURL('image/png').split(',')[1];});
   await upload(page,image,'滚动验收图片：分析后的卡片应完整露出。');
   await check('image pending state anchors after upload',()=>assertAnchored(page,'image pending'));
   await release(page);await page.locator('[data-chat-image-summary]').waitFor({timeout:15000});
   await page.locator('#reply-photo').waitFor({state:'visible'});
   await check('image completion and photo quote growth keep latest visible',()=>assertAnchored(page,'image complete'));
   await screenshot(page,'chat-scroll-image-complete');
   await check('closing report preserves chat bottom position',async()=>{
    const before=await geometry(page);
    await page.locator('[data-open-report]').last().click();await page.locator('.chat-report-dialog').waitFor();
    await page.waitForTimeout(3300);await page.locator('[data-close-report]').click();
    await page.locator('.chat-report-dialog').waitFor({state:'detached'});await page.waitForTimeout(220);
    const after=await assertAnchored(page,'report closed');
    assert(Math.abs(after.scrollY-before.scrollY)<3,'Dialog changed the conversation position: '+JSON.stringify({before,after}));
    return after;
   });
   await check('manual upward scrolling stays put during image polling',async()=>{
    await page.mouse.move(150,220);await page.mouse.wheel(0,-550);await page.waitForTimeout(350);
    const before=await geometry(page);assert(before.anchorGap< -250,'Manual scroll did not leave latest content: '+JSON.stringify(before));
    assert.equal(before.latestButtonVisible,true,'Return to latest missing while reading history');
    await page.waitForTimeout(4200);const after=await geometry(page);
    assert(Math.abs(after.scrollY-before.scrollY)<3,'Polling moved historical reading position: '+JSON.stringify({before,after}));
    assert.equal(after.latestButtonVisible,true);
    return {before,after};
   });
   await check('Return to latest button restores anchor',async()=>{await page.locator('#chat-latest').click();return assertAnchored(page,'Return to latest');});
   await page.locator('#reply-photo [data-clear-photo]').click();
   await page.locator('#message').fill('滚动验收慢回复：等待中上翻旧消息，完成后保留阅读位置。');
   await page.locator('#send').click();await page.locator('.thinking-status').waitFor();await page.waitForTimeout(200);
   await check('reply completion respects manual reading position',async()=>{
    await page.mouse.move(150,220);await page.mouse.wheel(0,-500);await page.waitForTimeout(250);const before=await geometry(page);
    assert.equal(before.latestButtonVisible,true);
    await waitDone(page);await page.waitForTimeout(3300);const after=await geometry(page);
    assert(Math.abs(after.scrollY-before.scrollY)<3,'Completed reply pulled reader down: '+JSON.stringify({before,after}));
    assert(after.anchorGap< -250,'Historical reading ended at latest content');
    return {before,after};
   });
   await check('sending from history returns to latest automatically',async()=>{
    await send(page,'继续聊天，发送应恢复跟随。');return assertAnchored(page,'send from history');
   });
  }
  await context.close();activePage=null;
 }
 await check('no browser runtime errors',()=>{assert.deepEqual(errors,[]);return {errors};});
}catch(error){
 report.failures.push({name:'setup or dependent flow',error:error.stack||error.message});
 if(activePage)await screenshot(activePage,'chat-scroll-failure').catch(()=>{});
}finally{
 report.passed=report.failures.length===0;
 await writeFile('tmp/chat-scroll-0.4.34.json',JSON.stringify(report,null,2));
 console.log(JSON.stringify(report,null,2));await browser.close();
 if(!report.passed)process.exitCode=1;
}
