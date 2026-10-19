import {createRequire} from 'node:module';
import {mkdir} from 'node:fs/promises';
const require=createRequire(import.meta.url);
const {chromium}=require('C:/Users/lxx/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
await mkdir('tmp/meal-correction-qa',{recursive:true});
const browser=await chromium.launch({headless:true});const page=await browser.newPage();const errors=[];
page.on('pageerror',e=>errors.push(e.message));
const state=async()=>await(await page.request.get('http://127.0.0.1:8795/api/work/state')).json();
try{
 await page.goto('http://127.0.0.1:8795/');await page.waitForFunction(()=>document.querySelector('#connection')?.textContent==='数据已连接');
 const original=await state();
 for(const width of [1280,390]){
  await page.setViewportSize({width,height:900});
  await page.locator('nav [data-view="archive"]').click();
  await page.locator('.meal-finder > summary').click();
  await page.locator('[data-meal-search]').fill('测试午餐');
  await page.locator('.meal-finder [data-meal-edit]').click();
  await page.locator('.meal-editor [name=description]').fill('测试午餐实际吃了一半');
  await page.locator('.meal-editor [name=nutrition_mode]').selectOption('scale');
  await page.locator('.meal-editor button[type=submit]').click();
  await page.locator('[data-commit]').waitFor();
  if(JSON.stringify((await state()).records)!==JSON.stringify(original.records))throw Error('Preview wrote data');
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth||document.querySelector('.meal-editor').scrollWidth>document.querySelector('.meal-editor').clientWidth))throw Error('Overflow');
  await page.screenshot({path:`tmp/meal-correction-qa/preview-${width}.png`,fullPage:true});
  await page.locator('[data-commit]').click();await page.waitForSelector('.meal-editor',{state:'detached'});
  await page.waitForFunction(()=>document.querySelector('.meal-corrections button'));
  let after=await state();if(after.records.length!==1||after.records[0].id!==original.records[0].id||after.records[0].value.nutrition.kcal[0]!==200)throw Error('Correction mismatch');
  await page.reload();await page.waitForFunction(()=>document.querySelector('#connection')?.textContent==='数据已连接');
  await page.locator('nav [data-view="archive"]').click();await page.locator('.meal-corrections > summary').click();
  await page.getByRole('button',{name:'撤销这次餐食修正',exact:true}).click();
  await page.waitForFunction(()=>!document.querySelector('.meal-corrections button'));
  if(JSON.stringify((await state()).records)!==JSON.stringify(original.records))throw Error('Undo mismatch');
 }
 await page.locator('nav [data-view="dashboard"]').click();
 await page.getByText('查看已记录餐食',{exact:true}).click();
 await page.locator('#dashboard-content [data-meal-edit]').click();
 await page.locator('.meal-editor [name=operation]').selectOption('remove');await page.locator('.meal-editor button[type=submit]').click();
 await page.locator('[data-commit]').click();await page.waitForSelector('.meal-editor',{state:'detached'});
 if((await state()).records.length!==0)throw Error('Retraction failed');
 if(errors.length)throw Error(errors.join('\n'));
 console.log(JSON.stringify({errors,previewReadOnly:true,identityPreserved:true,undoAfterReload:true,retraction:true,widths:[1280,390]}));
}finally{await browser.close();}
