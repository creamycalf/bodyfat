import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require('C:/Users/lxx/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const browser=await chromium.launch({headless:true});const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto('http://127.0.0.1:8795/');await page.evaluate(()=>localStorage.setItem('zhiheng-session-v2','recovery-conversation'));await page.reload();
 await page.locator('[data-retry-chat]').waitFor();
 if(await page.getByRole('button',{name:'继续这次请求',exact:true}).count()!==1)throw Error('Duplicate retry controls');
 await page.reload();await page.locator('[data-retry-chat]').click();
 await page.waitForFunction(()=>!document.querySelector('#send').disabled&&!document.querySelector('[data-retry-chat]'));
 const state=await(await page.request.get('http://127.0.0.1:8795/api/work/state')).json();
 if(state.records.length!==1||state.plans.length!==0||state.evaluation_jobs.some(j=>j.kind==='chat'&&j.status==='failed'))throw Error('Recovery persistence mismatch');
 if(await page.getByRole('button',{name:'继续这次请求',exact:true}).count())throw Error('Resolved retry still visible');
 await page.setViewportSize({width:390,height:844});await page.locator('nav [data-view="plan"]').click();
 if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Overflow');
 if(errors.length)throw Error(errors.join('\n'));console.log(JSON.stringify({errors,retryAfterRefresh:true,weightRecords:state.records.length,plans:state.plans.length,retryResolved:true}));
}finally{await browser.close();}
