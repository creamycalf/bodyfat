import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile,writeFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {resolve,relative,isAbsolute} from 'node:path';
const require=createRequire(import.meta.url),{chromium}=require('../tmp/ui-tools/node_modules/playwright');
const files=new Map([['/nutrition-report-ui.js','nutrition-report-ui.js'],['/nutrition-report.css','nutrition-report.css'],['/app.css','app.css']]);
const server=createServer(async(req,res)=>{
 try{
  if(req.url==='/'){res.setHeader('Content-Type','text/html; charset=utf-8');res.end('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/app.css"><link rel="stylesheet" href="/nutrition-report.css"><style>body{margin:0;padding:12px}main{max-width:760px;margin:auto}</style><main id="report"></main>');return;}
  if(req.url?.startsWith('/api/media/image')){res.setHeader('Content-Type','image/svg+xml');res.end('<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120"><rect width="120" height="120" fill="#c7d9c3"/><circle cx="60" cy="60" r="35" fill="#dca761"/></svg>');return;}
  const file=files.get(req.url);if(!file){res.statusCode=404;res.end();return;}
  res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript; charset=utf-8':'text/css; charset=utf-8');res.end(await readFile(file));
 }catch(error){res.statusCode=500;res.end('Fixture asset unavailable');}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const browser=await chromium.launch({headless:true,channel:'msedge'}),page=await browser.newPage({viewport:{width:390,height:900}}),errors=[];
page.on('pageerror',error=>errors.push(error.message));
const nutrients={kcal:[450,850],protein_g:null,carbs_g:null,fat_g:null};
const report={kind:'food',foods:[{name:'合成混合餐食 <script>window.unsafe=true</script>',grams:null,nutrition_basis:'portion_estimate',nutrition:nutrients,weight_basis:'熟制成品',portion_basis:'照片中一盘可见总量',source:'模型根据可见份量直接估计，未经称量',source_meta:{kind:'model_estimate',basis:'visible_portion'},uncertainty:'用油与实际食用份量待核对',energy_share_pct:null}],counted_count:1,coverage:{kcal:1,protein_g:0,carbs_g:0,fat_g:0},totals:nutrients,partial_totals:nutrients,questions:['这是你吃的整盘，还是几个人分着吃？'],notice:'照片不表示实际摄入'};
const media={id:'synthetic-direct-food',review:{summary:'合成餐食估算；<img src=x onerror="window.unsafe=true">',report}};
try{
 await page.goto(`http://127.0.0.1:${server.address().port}/`);
 await page.evaluate(async fixture=>{
  const module=await import('/nutrition-report-ui.js');window.testModule=module;window.fixture=fixture;window.previews=[];
  document.querySelector('#report').innerHTML=module.nutritionReport(fixture);
  module.setupNutritionReportEditing(()=>({media:[fixture],saved_foods:[]}),async(url,payload)=>{window.previews.push(payload);return {token:'synthetic-token',after:fixture.review.report,intake_nutrition:{kcal:null}};},async()=>{},()=>{});
 },media);
 assert.equal(await page.locator('.nr-metric strong').first().innerText(),'450–850');
 assert.equal(await page.locator('.nr-metric strong').nth(1).innerText(),'未知');
 assert.match(await page.locator('.nr-food').innerText(),/照片估算.*待核对/);
 assert.match(await page.locator('.nr-food-title').innerText(),/重量待核对/);
 assert.match(await page.locator('.nr-food').innerText(),/本项热量占已列食物比例未知/);
 assert.equal(await page.evaluate(()=>Boolean(window.unsafe||document.querySelector('.nr-summary img')||document.querySelector('.nr-food script'))),false);
 await page.locator('.nr-food details summary').click();
 const calculation=await page.locator('.nr-food details').innerText();
 assert.match(calculation,/可见整份直接粗估/);assert.doesNotMatch(calculation,/×/);
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await page.locator('.nutrition-report').screenshot({path:'tmp/photo-estimate-mobile-0.4.31.png'});
 await page.locator('[data-report-edit]').click();
 const editor=page.locator('.nr-editor'),food=editor.locator('.nr-edit-food').first();
 assert.equal(await food.locator('[name="density_basis"]').inputValue(),'visible_portion');
 assert.equal(await food.locator('[name="kcal_low"]').inputValue(),'450');
 assert.equal(await food.locator('[name="protein_g_low"]').inputValue(),'');
 assert.equal(await food.locator('[name="grams_low"]').inputValue(),'');
 assert.match(await editor.innerText(),/重量不用于自动缩放/);
 await editor.getByRole('button',{name:'预览重算'}).click();
 let payload=await page.evaluate(()=>window.previews.at(-1));
 assert.deepEqual(payload.foods[0].nutrition,nutrients);
 assert.deepEqual(payload.foods[0].per_100g,{kcal:null,protein_g:null,carbs_g:null,fat_g:null});
 assert.equal(payload.foods[0].grams,null);assert.equal(payload.confirm_consumption,false);assert.equal(payload.eaten_servings,'');
 await food.locator('[name="grams_low"]').fill('200');await food.locator('[name="grams_high"]').fill('400');
 await editor.getByRole('button',{name:'预览重算'}).click();
 payload=await page.evaluate(()=>window.previews.at(-1));
 assert.deepEqual(payload.foods[0].nutrition.kcal,[450,850]);
 await food.locator('[name="density_basis"]').selectOption('per_100g');
 assert.equal(await food.locator('[name="kcal_low"]').inputValue(),'');
 assert.match(await food.locator('[data-nutrition-basis-note]').innerText(),/避免把整份数值误当每100g/);
 await food.locator('[name="kcal_low"]').fill('120');await food.locator('[name="kcal_high"]').fill('180');
 await editor.getByRole('button',{name:'预览重算'}).click();
 payload=await page.evaluate(()=>window.previews.at(-1));
 assert.equal(payload.foods[0].density_basis,'per_100g');assert.equal('nutrition' in payload.foods[0],false);
 assert.deepEqual(payload.foods[0].per_100g.kcal,[120,180]);
 await food.locator('[name="density_basis"]').selectOption('visible_portion');assert.equal(await food.locator('[name="kcal_low"]').inputValue(),'');
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await editor.getByRole('button',{name:'取消'}).click();
 await page.evaluate(()=>{
  const fixture=structuredClone(window.fixture);fixture.review.report.foods=[{name:'未知食物',included:true,nutrition:{kcal:null},grams:null}];
  fixture.review.report.coverage={};fixture.review.report.totals={};fixture.review.report.partial_totals={};
  document.querySelector('#report').innerHTML=window.testModule.nutritionReport(fixture);
 });
 assert.deepEqual(await page.locator('.nr-metric strong').allTextContents(),['未知','未知','未知','未知']);
 assert.doesNotMatch(await page.locator('.nutrition-report').innerText(),/undefined|NaN/);
 await page.evaluate(()=>{const fixture=structuredClone(window.fixture);fixture.review.report.foods[0].nutrition.kcal=['0',null];fixture.review.report.partial_totals.kcal=['0',null];document.querySelector('#report').innerHTML=window.testModule.nutritionReport(fixture);});
 assert.equal(await page.locator('.nr-metric strong').first().innerText(),'未知');
 assert.deepEqual(errors,[]);
 let actualPhotoReport;
 const artifactArgument=process.argv.indexOf('--live-artifact');
 if(artifactArgument!==-1){
  const artifactPath=resolve(process.argv[artifactArgument+1]||''),insideTmp=relative(resolve('tmp'),artifactPath);
  assert(insideTmp&&!insideTmp.startsWith('..')&&!isAbsolute(insideTmp)&&!insideTmp.split(/[\\/]/).includes('.data'),'Use a model-test artifact under tmp');
  const artifact=JSON.parse(await readFile(artifactPath,'utf8'));
  assert.equal(artifact.run_status,'completed');assert.deepEqual(artifact.check_failures,[]);
  const actual={id:artifact.media_id,review:artifact.normalized_review};
  assert.equal(actual.review.report.kind,'food');
  await page.evaluate(fixture=>{document.querySelector('#report').innerHTML=window.testModule.nutritionReport(fixture);},actual);
  const visibleCalories=await page.locator('.nr-metric strong').first().innerText();
  const expected=artifact.displayed_kcal[0]===artifact.displayed_kcal[1]?String(artifact.displayed_kcal[0]):artifact.displayed_kcal.join('–');
  assert.equal(visibleCalories,expected);assert.match(await page.locator('.nr-badge').innerText(),/照片估算.*待核对/);
  assert.match(await page.locator('.nutrition-report').innerText(),/尚未按本人食用份量换算/);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.locator('.nutrition-report').screenshot({path:'tmp/meal-photo-report-mobile-0.4.31.png'});
  actualPhotoReport={verified:true,calories:artifact.displayed_kcal,foods:actual.review.report.foods.length};
 }
 assert.deepEqual(errors,[]);
 const result={passed:true,viewport:390,directCalories:true,unknownNotZero:true,noDensityInvention:true,editorRoundTrip:true,weightDoesNotScaleDirect:true,basisSwitchClearsValues:true,htmlEscaped:true,noPageErrors:true,...(actualPhotoReport?{actualPhotoReport}:{})};
 await writeFile('tmp/photo-estimate-ui-0.4.31.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
