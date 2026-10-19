import {createRequire} from 'node:module';
import {mkdir,writeFile} from 'node:fs/promises';
const require=createRequire(import.meta.url);
const {chromium}=require('C:/Users/lxx/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const out='tmp/'+(process.env.TWO_DAY_RUN||'two-day-live-20260916');await mkdir(out,{recursive:true});
const base='http://127.0.0.1:'+(process.env.TWO_DAY_PORT||'8797');
const browser=await chromium.launch({headless:true});const page=await browser.newPage();const errors=[],checks=[];
page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto(base+'/');
 await page.evaluate(()=>localStorage.setItem('zhiheng-session-v2','two-day-synthetic-user'));
 await page.reload();await page.waitForFunction(()=>document.querySelector('#connection')?.textContent==='数据已连接');
 for(const width of [1280,390]){
  await page.setViewportSize({width,height:900});
  for(const view of ['dashboard','plan','archive','chat']){
   await page.locator(`nav [data-view="${view}"]`).click();await page.evaluate(()=>scrollTo(0,0));
   const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
   checks.push({view,width,overflow});await page.screenshot({path:`${out}/${view}-${width}.png`,fullPage:true});
  }
 }
 const before=await(await page.request.get(base+'/api/work/state')).json();
 await page.reload();await page.waitForFunction(()=>document.querySelector('#connection')?.textContent==='数据已连接');
 const after=await(await page.request.get(base+'/api/work/state')).json();
 const persisted=['records','plans','feedback','meal_corrections'].every(k=>JSON.stringify(before[k])===JSON.stringify(after[k]));
 const result={errors,checks,persisted};await writeFile(`${out}/browser-checks.json`,JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{await browser.close();}
