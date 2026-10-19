import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),{chromium}=require('../tmp/ui-tools/node_modules/playwright');
const browser=await chromium.launch({headless:true,channel:'msedge'});
const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];
page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto('http://127.0.0.1:8798');
 await page.getByText('数据已连接',{exact:true}).waitFor();
 await page.locator('#new-chat').click();
 await page.locator('.chat-welcome').waitFor();
 for(const width of [320,390,1280]){
  await page.setViewportSize({width,height:844});
  await page.waitForTimeout(150);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  assert.equal(await page.locator('.chat-starters button').count(),4);
  await page.screenshot({path:`tmp/agent-welcome-${width}-0.4.39.png`,fullPage:true});
 }
 await page.setViewportSize({width:390,height:844});
 await page.locator('[data-starter]').first().click();
 assert.match(await page.locator('#message').inputValue(),/基础情况/);
 assert.equal(await page.locator('.chat-turn').count(),0,'Starter edits the draft without sending');
 await page.locator('#open-history').click();
 assert.equal(await page.locator('#history-dialog').evaluate(e=>e.open),true);
 await page.locator('#history-search').fill('不存在的对话');
 await page.locator('#close-history').click();
 assert.match(await page.locator('#message').inputValue(),/基础情况/);
 await page.locator('#message').fill('这是一段界面验收消息，请直接解释搭配。');
 await page.locator('#send').click();
 await page.waitForFunction(()=>!document.querySelector('#send').disabled);
 await page.locator('.assistant-label').waitFor();
 await page.screenshot({path:'tmp/agent-conversation-390-0.4.39.png',fullPage:true});
 assert.deepEqual(errors,[]);
 console.log('PASS: welcome, draft starters, modal history, draft retention, conversation and 320/390/1280 widths');
}finally{await browser.close();}
