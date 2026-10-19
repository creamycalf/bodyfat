import {createRequire} from 'node:module';
import {mkdir} from 'node:fs/promises';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const {chromium}=require('C:/Users/lxx/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
await mkdir('tmp/direction-prototype-qa',{recursive:true});
const browser=await chromium.launch({headless:true});
try {
 const p=await browser.newPage();const errors=[];const requests=[];
 p.on('pageerror',e=>errors.push(e.message));p.on('request',r=>requests.push(r.url()));
 await p.goto('http://127.0.0.1:8796');
 for(const width of [1440,390]){
  await p.setViewportSize({width,height:960});
  for(let n=0;n<5;n++){
   await p.locator('.scenario').nth(n).click();
   for(const view of ['chat','today','plan','profile']){
    await p.locator(`#nav button[onclick="go('${view}')"]`).click();
    assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`overflow ${width}/${n}/${view}`);
    if(n===0&&view==='chat'||n===1&&view==='profile'||n===4&&['today','plan'].includes(view))await p.screenshot({path:`tmp/direction-prototype-qa/${n}-${view}-${width}.png`,fullPage:true});
   }
  }
  await p.locator('.scenario').nth(2).click();
  assert.match(await p.locator('#actual-energy').innerText(),/未计入/);
  await p.getByRole('button',{name:'整盘吃了一半',exact:true}).click();
  assert.match(await p.locator('#actual-energy').innerText(),/300–380/);
  await p.getByRole('button',{name:'整盘吃了一半',exact:true}).click();
  await p.getByRole('button',{name:'查看档案 →',exact:true}).click();
  assert.match(await p.locator('#content').innerText(),/实际摄入 · 1 条/);
  await p.locator('.scenario').nth(3).click();
  await p.getByRole('button',{name:'更正：整盘都吃了',exact:true}).click();
  assert.match(await p.locator('#actual-energy').innerText(),/600–760/);
  await p.getByRole('button',{name:'我还没吃，只是看看',exact:true}).click();
  assert.match(await p.locator('#actual-energy').innerText(),/未计入/);
  await p.screenshot({path:`tmp/direction-prototype-qa/food-${width}.png`,fullPage:true});
  assert.equal(await p.locator('.food-photo img').evaluate(img=>img.complete&&img.naturalWidth>0),true);
  await p.locator('.scenario').nth(4).click();
  await p.getByRole('button',{name:'改前 / 改后 ↗'}).click();
  await p.locator('dialog').waitFor({state:'visible'});
  await p.screenshot({path:`tmp/direction-prototype-qa/compare-${width}.png`,fullPage:true});
  await p.getByRole('button',{name:'关闭 ×'}).click();
 }
 assert.deepEqual(errors,[]);
 assert.ok(requests.every(url=>url.startsWith('http://127.0.0.1:8796/')),'Unexpected external or production request');
 console.log(JSON.stringify({ok:true,widths:[1440,390],pageStates:40,errors,requests:requests.length}));
} finally {await browser.close()}
