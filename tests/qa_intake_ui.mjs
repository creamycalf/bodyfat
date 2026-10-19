import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
let playwright;try{playwright=require('playwright');}catch{playwright=require('../tmp/ui-tools/node_modules/playwright');}
const {chromium}=playwright;
const browser=await chromium.launch({headless:true,channel:'msedge'});const page=await browser.newPage();const errors=[];
page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto('http://127.0.0.1:8796/');await page.getByText('数据已连接',{exact:true}).waitFor();
 const input=page.locator('#message');await input.fill('测试换行');await input.press('Shift+Enter');
 if(!await input.inputValue().then(v=>v.includes('\n')))throw Error('Shift Enter did not insert newline');
 await input.dispatchEvent('keydown',{key:'Enter',isComposing:true});
 if(await page.locator('#send').isDisabled())throw Error('IME sent message');
 await input.fill('资料没齐，请先给初步计划');await input.press('Enter');
 await page.locator('[data-chat-plan]').waitFor();await page.locator('[data-chat-plan]').click();
 if(await page.locator('#plan').isHidden())throw Error('Plan link failed');
 await page.reload();await page.locator('[data-chat-plan]').waitFor();
 await page.locator('#camera').click();
 if(await page.locator('#camera-file').getAttribute('capture')!=='environment')throw Error('Camera capture missing');
 for(const width of [1280,390]){await page.setViewportSize({width,height:900});await page.locator('nav [data-view="plan"]').click();if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Overflow');await page.screenshot({path:`tmp/intake-plan-${width}.png`,fullPage:true});}
 if(errors.length)throw Error(errors.join('\n'));
 console.log('PASS: Enter, Shift+Enter, IME, plan link after reload, camera input, desktop/mobile layout');
}finally{await browser.close();}
