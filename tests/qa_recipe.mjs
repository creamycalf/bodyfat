import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require('C:/Users/lxx/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const browser=await chromium.launch({headless:true});const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto('http://127.0.0.1:8795/');await page.evaluate(()=>localStorage.setItem('zhiheng-session-v2','recipe-conversation'));await page.reload();
 await page.locator('nav [data-view="plan"]').click();await page.getByRole('button',{name:'获取详细做法',exact:true}).click();
 await page.getByRole('button',{name:'保存到该事项',exact:true}).waitFor();await page.reload();
 await page.getByRole('button',{name:'保存到该事项',exact:true}).click();await page.getByText('已保存到计划事项。',{exact:true}).waitFor();
 await page.reload();await page.locator('nav [data-view="plan"]').click();await page.getByRole('heading',{name:'米饭配蒸蛋',exact:true}).waitFor();
 for(const width of [1280,390]){await page.setViewportSize({width,height:900});if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Overflow');await page.screenshot({path:`tmp/recipe-release-20260916/plan-${width}.png`,fullPage:true});}
 const state=await(await page.request.get('http://127.0.0.1:8795/api/work/state')).json();
 if(state.records.length||state.feedback.length||state.plans.length!==1||state.plans[0].items[0].recipe_history.length!==1)throw Error('Persistence mismatch');
 if(errors.length)throw Error(errors.join('\n'));console.log(JSON.stringify({errors,savedAfterRefresh:true,records:state.records.length,feedback:state.feedback.length}));
}finally{await browser.close();}
