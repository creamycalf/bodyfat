import {createRequire} from 'node:module';
import {mkdir} from 'node:fs/promises';
import assert from 'node:assert/strict';
const {chromium}=createRequire(import.meta.url)('C:/Users/lxx/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
await mkdir('tmp/journey-qa',{recursive:true});
const browser=await chromium.launch({headless:true});
try{const p=await browser.newPage();const errors=[];p.on('pageerror',e=>errors.push(e.message));
for(const width of [1440,390]){
await p.setViewportSize({width,height:900});await p.goto('http://127.0.0.1:8796/');
await p.getByRole('button',{name:'开始体验 →',exact:true}).click();
for(let step=1;step<=8;step++){
assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`overflow ${width}/${step}`);
if(step===2)assert.match(await p.locator('#content').innerText(),/80.0/);
if(step===4)assert.match(await p.locator('#actual-energy').innerText(),/未计入/);
if(step===5)assert.match(await p.locator('#content').innerText(),/300–380/);
if(step===6){await p.getByRole('button',{name:'改前 / 改后 ↗'}).click();await p.locator('dialog').waitFor({state:'visible'});await p.getByRole('button',{name:'关闭 ×'}).click()}
if([1,4,6,8].includes(step))await p.screenshot({path:`tmp/journey-qa/${width}-${step}.png`,fullPage:true});
if(step<8)await p.locator('#journey-guide .primary').click();
}
await p.getByRole('button',{name:'自由查看完整原型',exact:true}).click();
await p.locator('#nav button').last().click();assert.match(await p.locator('#content').innerText(),/21:30/);
await p.locator('#journey-guide .primary').click();
await p.locator('.demo button').click();assert.equal(await p.locator('.welcome').isVisible(),true);
}
assert.deepEqual(errors,[]);console.log('PASS: desktop/mobile full guided journey, state assertions, version comparison, free navigation, reset; no overflow or JS errors.');
}finally{await browser.close()}
