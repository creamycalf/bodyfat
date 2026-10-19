import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require('C:/Users/lxx/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const browser=await chromium.launch({headless:true});
const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto('http://127.0.0.1:8787/');
await page.waitForFunction(()=>document.querySelector('#connection')?.textContent==='数据已连接');
for(const [width,height] of [[1280,900],[390,844]]){
 await page.setViewportSize({width,height});
 for(const v of ['dashboard','plan','archive']){
  await page.locator(`nav [data-view="${v}"]`).click();await page.evaluate(()=>scrollTo(0,0));
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Overflow '+v+' '+width);
  await page.screenshot({path:`tmp/health-pages-release/formal-${v}-${width}.png`,fullPage:true});
 }
}
if(await page.locator('.current-plan').count()&&!(await page.locator('.meal-choices').count()))throw Error('Existing diet plan has no help entry');
await browser.close();console.log(JSON.stringify({errors,formalReadOnly:true,responsive:true}));
if(errors.length)process.exitCode=1;
