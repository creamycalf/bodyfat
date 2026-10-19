import {createRequire} from 'node:module';
import {mkdir} from 'node:fs/promises';
const require=createRequire(import.meta.url);
const {chromium}=require('C:/Users/lxx/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
await mkdir('tmp/health-pages-release',{recursive:true});
const browser=await chromium.launch({headless:true});
const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto('http://127.0.0.1:8795/');
await page.waitForFunction(()=>document.querySelector('#connection')?.textContent==='数据已连接');
await page.locator('nav [data-view="plan"]').click();
await page.locator('.current-plan').getByText('番茄炒蛋配米饭',{exact:true}).waitFor();
await page.locator('.current-plan').getByText('查看做法',{exact:true}).click();
await page.locator('.current-plan').getByText('番茄切块，鸡蛋打散',{exact:false}).waitFor();
await page.locator('#plan-content .current-plan [data-feedback="done"]').first().click();
await page.waitForFunction(()=>document.querySelector('#plan-content .checkin-state')?.textContent==='已完成');
await page.locator('nav [data-view="dashboard"]').click();
if(await page.locator('.today-task .checkin-state').first().textContent()!=='已完成')throw Error('Checkin did not sync');
await page.locator('nav [data-view="plan"]').click();
await page.locator('.plan-history > summary').click();
await page.locator('.history-version > summary').first().click();
await page.locator('.history-version .feedback-history > summary').click();
await page.getByText('历史打卡',{exact:true}).waitFor();
const before=await (await page.request.get('http://127.0.0.1:8795/api/work/state')).json();
await page.locator('.current-plan [data-help-mode="cook"]').click();
await page.waitForFunction(()=>document.querySelector('#send')?.disabled===false&&document.querySelector('#messages')?.textContent.includes('把番茄切块'));
const after=await (await page.request.get('http://127.0.0.1:8795/api/work/state')).json();
for(const k of ['profile','records','plans','feedback'])if(JSON.stringify(before[k])!==JSON.stringify(after[k]))throw Error('Recipe changed '+k);
await page.locator('#message').fill('午休散步完成了');await page.locator('#send').click();
await page.waitForFunction(()=>document.querySelector('#send')?.disabled===false&&document.querySelector('#messages')?.textContent.includes('已收到散步反馈'));
const checked=await (await page.request.get('http://127.0.0.1:8795/api/work/state')).json();
if(checked.tasks.find(t=>t.title.includes('散步'))?.status!=='done')throw Error('Dialogue checkin not saved');
for(const [width,height] of [[1280,900],[390,844]]){
 await page.setViewportSize({width,height});
 for(const v of ['dashboard','plan','archive','chat']){
  await page.locator(`nav [data-view="${v}"]`).click();
  await page.evaluate(()=>scrollTo(0,0));
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Overflow '+v+' '+width);
  await page.screenshot({path:`tmp/health-pages-release/${v}-${width}.png`,fullPage:true});
 }
}
await page.reload();await page.waitForFunction(()=>document.querySelector('#connection')?.textContent==='数据已连接');
const restored=await (await page.request.get('http://127.0.0.1:8795/api/work/state')).json();
if(restored.tasks.filter(t=>t.status==='done').length!==2)throw Error('Reload lost checkins');
await browser.close();console.log(JSON.stringify({errors,checkins:2,recipeWrites:0,history:true,responsive:true}));
if(errors.length)process.exitCode=1;
