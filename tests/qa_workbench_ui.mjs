import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require('C:/Users/lxx/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const browser=await chromium.launch({headless:true});
const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.setContent('<body style="font:24px sans-serif;padding:35px;background:white"><h1>SYNTHETIC TEST MENU</h1><p>Not a real meal. Test fixture only.</p><h2>Rice and vegetables, one portion</h2><p>Energy: 600 kcal per portion</p><p>Protein: 20 g / Carbohydrates: 100 g / Fat: 13 g</p><p>Actual amount eaten: unknown</p></body>');
await page.screenshot({path:'tmp/workbench-v3-qa/synthetic-menu.png'});
await page.goto('http://127.0.0.1:8795/');
await page.waitForFunction(()=>document.querySelector('#connection')?.textContent==='数据已连接');
await page.waitForFunction(()=>document.querySelector('#image-job-status')!==null);
for(const [width,height] of [[1280,900],[390,844]]){
 await page.setViewportSize({width,height});
 for(const view of ['dashboard','plan','archive','chat']){
  await page.locator(`nav [data-view="${view}"]`).click();
  await page.locator(`#${view}`).waitFor({state:'visible'});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth);
  if(overflow)throw Error(`Horizontal overflow at ${width} / ${view}`);
  await page.screenshot({path:`tmp/workbench-v3-qa/${view}-${width}.png`,fullPage:true});
 }
}
await page.reload();
await page.waitForFunction(()=>document.querySelector('#connection')?.textContent==='数据已连接');
const jobs=await page.request.get('http://127.0.0.1:8795/api/work/image-jobs');
if((await jobs.json()).jobs.length){
 await page.waitForFunction(()=>document.querySelectorAll('#image-job-status article').length>0);
 await page.screenshot({path:'tmp/workbench-v3-qa/jobs-after-refresh-390.png',fullPage:true});
}
console.log(JSON.stringify({errors,modules:await page.locator('.dynamic-module').count(),planCards:await page.locator('#plan-content .plan-card').count()}));
await browser.close();
if(errors.length)process.exitCode=1;
