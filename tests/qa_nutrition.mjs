import {createRequire} from 'node:module';
import {mkdir} from 'node:fs/promises';
const require=createRequire(import.meta.url);
const {chromium}=require('C:/Users/lxx/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
await mkdir('tmp/nutrition-ui-20260917',{recursive:true});
const browser=await chromium.launch({headless:true});
const page=await browser.newPage(),errors=[];
page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto('http://127.0.0.1:8796/');
 await page.waitForFunction(()=>document.querySelector('#connection')?.textContent==='数据已连接');
 for(const width of [1280,390]){
  await page.setViewportSize({width,height:900});
  await page.locator('nav [data-view="dashboard"]').click();
  await page.getByText('1 条已估算 · 1 条未知，合计仅含已估算部分',{exact:true}).first().waitFor();
  await page.getByText('查看已记录餐食',{exact:true}).click();
  await page.locator('#dashboard-content').getByText('根据本次餐食描述估算 · 准确程度未校准',{exact:true}).waitFor();
  await page.locator('#dashboard-content').getByText('营养尚未估算 · 未知不按零计入',{exact:true}).waitFor();
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('dashboard overflow');
  await page.screenshot({path:`tmp/nutrition-ui-20260917/dashboard-${width}.png`,fullPage:true});
  await page.locator('nav [data-view="plan"]').click();
  await page.getByText('份量：1人1餐参考量',{exact:false}).waitFor();
  await page.getByText('份数未说明，请核对后使用',{exact:false}).waitFor();
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('plan overflow');
  await page.screenshot({path:`tmp/nutrition-ui-20260917/plan-${width}.png`,fullPage:true});
  await page.reload();await page.waitForFunction(()=>document.querySelector('#connection')?.textContent==='数据已连接');
 }
 // Module output must escape model/user text and retain legacy uncertainty.
 const safe=await page.evaluate(async()=>{
  const {nutritionInfo,recipePortion}=await import('/nutrition-info.js');
  const html=nutritionInfo({value:{nutrition:{kcal:100},nutrition_context:{basis:'<img src=x onerror=alert(1)>'}}});
  return !html.includes('<img')&&html.includes('历史估算')&&recipePortion({}).includes('生熟重量未说明');
 });
 if(!safe)throw Error('Unsafe or misleading legacy rendering');
 if(errors.length)throw Error(errors.join('\n'));
 console.log(JSON.stringify({errors,responsive:true,unknownCoverage:true,provenance:true,portions:true,escaped:true}));
}finally{await browser.close();}
