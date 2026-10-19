import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {writeFile} from 'node:fs/promises';
const require=createRequire(import.meta.url),{chromium}=require('../tmp/ui-tools/node_modules/playwright');
const browser=await chromium.launch({headless:true,channel:'msedge'}),rows=[],errors=[];
const url=process.argv[2]||'http://127.0.0.1:8806';
async function geometry(page){return page.evaluate(()=>{
 const box=node=>{const r=node.getBoundingClientRect();return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,width:r.width,height:r.height};};
 const composer=box(document.querySelector('#composer'));
 const cards=[...document.querySelectorAll('.chat-starters button')].map(node=>({...box(node),text:node.querySelector('strong').textContent}));
 return {scrollY,innerHeight,visualHeight:visualViewport?.height,header:box(document.querySelector('.workspace>header')),composer,cards,
  keyboard:document.body.classList.contains('chat-keyboard-open'),overflow:document.documentElement.scrollWidth>innerWidth,
  draft:document.querySelector('#message').value,send:box(document.querySelector('#send'))};
});}
try{
 for(const viewport of [{width:360,height:568},{width:320,height:640},{width:390,height:844},{width:844,height:390},{width:640,height:360}]){
  const page=await browser.newPage({viewport});page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url);await page.getByText('数据已连接',{exact:true}).waitFor();await page.waitForTimeout(220);
  const g=await geometry(page);
  assert.equal(g.cards.length,4);assert.equal(g.overflow,false);
  for(const card of g.cards){
   assert(card.height>=44&&card.width>=44,'44px touch target: '+JSON.stringify(card));
   assert(card.top>=g.header.bottom-1&&card.bottom<=g.composer.top-8,'starter obscured: '+JSON.stringify(g));
  }
  assert(g.send.height>=44&&g.send.bottom<=viewport.height,'send visible: '+JSON.stringify(g.send));
  const draft='我已有草稿：晚上下班很饿，不能吃花生。';await page.locator('#message').fill(draft);
  await page.locator('[data-starter]').first().click();assert.equal(await page.locator('#message').inputValue(),draft);
  const chooser=page.waitForEvent('filechooser');await page.locator('[data-start-report]').click();await chooser;
  assert.equal(await page.locator('#message').inputValue(),draft);
  await page.screenshot({path:`tmp/welcome-0.4.43-${viewport.width}x${viewport.height}.png`});
  rows.push({case:'four_visible_starters_and_draft',viewport,passed:true,geometry:g});
  if(viewport.width<=390){
   await page.locator('#message').focus();
   await page.evaluate(()=>{
    window.qaViewportHeight=Math.max(230,innerHeight-260);
    Object.defineProperty(window.visualViewport,'height',{configurable:true,get:()=>window.qaViewportHeight});
    window.visualViewport.dispatchEvent(new Event('resize'));
   });
   await page.waitForTimeout(200);const keyboard=await geometry(page);
   assert(keyboard.keyboard);assert.equal(keyboard.draft,draft);assert(keyboard.composer.top>=0);
   assert(keyboard.composer.bottom<=keyboard.visualHeight+1,'composer above simulated keyboard');
   assert(keyboard.send.top>=0&&keyboard.send.bottom<=keyboard.visualHeight+1,'send above simulated keyboard');
   assert(await page.locator('.chat-welcome').isHidden(),'welcome collapses while typing');
   await page.evaluate(()=>{window.qaViewportHeight=innerHeight;document.querySelector('#message').blur();window.visualViewport.dispatchEvent(new Event('resize'));});
   await page.waitForTimeout(180);const restored=await geometry(page);
   assert(!restored.keyboard);assert.equal(restored.draft,draft);
   for(const card of restored.cards)assert(card.bottom<=restored.composer.top-8,'cards restore after keyboard closes');
   rows.push({case:'keyboard_260px_draft_and_send',viewport,passed:true,geometry:keyboard});
   await page.locator('#message').focus();
   await page.evaluate(()=>delete window.visualViewport.height);
   await page.setViewportSize({width:viewport.width,height:viewport.height-260});
   await page.waitForTimeout(200);const resized=await geometry(page);
   assert(resized.keyboard);assert.equal(resized.draft,draft);
   assert(resized.composer.top>=0&&resized.send.bottom<=resized.innerHeight+1,'Android adjustResize keeps draft and send visible');
   await page.setViewportSize(viewport);await page.locator('#message').blur();await page.waitForTimeout(180);
   const resizedRestored=await geometry(page);
   assert(!resizedRestored.keyboard);assert.equal(resizedRestored.draft,draft);
   for(const card of resizedRestored.cards)assert(card.bottom<=resizedRestored.composer.top-8,'adjustResize restore keeps starters visible');
   rows.push({case:'android_adjust_resize_260px',viewport,passed:true,geometry:resized});
  }
  await page.close();
 }
 assert.deepEqual(errors,[]);await writeFile('tmp/mobile-welcome-layout-0.4.43.json',JSON.stringify(rows,null,2));console.log(JSON.stringify(rows));
}finally{await browser.close();}
