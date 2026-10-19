import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {writeFile} from 'node:fs/promises';
const require=createRequire(import.meta.url),{chromium}=require('../tmp/ui-tools/node_modules/playwright');
const url=process.argv[2]||'http://127.0.0.1:8806';
const browser=await chromium.launch({headless:true,channel:'msedge'}),rows=[];
try{
 for(const viewport of [{width:360,height:568},{width:320,height:640},{width:390,height:844}]){
  const page=await browser.newPage({viewport});
  await page.goto(url);await page.getByText('数据已连接',{exact:true}).waitFor();
  await page.waitForTimeout(250);
  const first=await page.evaluate(()=>{
   const h=document.querySelector('.workspace>header').getBoundingClientRect(),welcome=document.querySelector('#welcome-title').getBoundingClientRect(),controls=document.querySelector('#new-chat').getBoundingClientRect();
   return {scrollY,headerBottom:h.bottom,welcomeTop:welcome.top,controlsTop:controls.top};
  });
  assert(first.scrollY<=1&&first.welcomeTop>=first.headerBottom&&first.controlsTop>=first.headerBottom,JSON.stringify(first));
  await page.evaluate(()=>window.scrollTo(0,100));await page.waitForTimeout(180);
  const deliberateScroll=await page.evaluate(()=>scrollY);
  await page.waitForTimeout(1000);
  const retainedScroll=await page.evaluate(()=>scrollY);
  assert(Math.abs(retainedScroll-deliberateScroll)<3,'empty welcome poll must preserve deliberate scroll');
  await page.evaluate(()=>document.querySelector('#new-chat').click());await page.waitForTimeout(180);
  const newChatTop=await page.evaluate(()=>scrollY);
  assert(newChatTop<=1,'new empty chat must show its header');
  await page.locator('#message').fill('滚动验收慢回复');await page.locator('#send').click();
  await page.locator('.thinking-status').waitFor();await page.waitForTimeout(180);
  const thinkingGap=await page.evaluate(()=>document.querySelector('.thinking-status').getBoundingClientRect().bottom-document.querySelector('#composer').getBoundingClientRect().top);
  assert(thinkingGap<=2,'first send must still reveal its processing status');
  await page.locator('#send').filter({hasText:'发送'}).waitFor();
  await page.locator('#message').fill('滚动验收长回复');await page.locator('#send').click();
  await page.locator('#send').filter({hasText:'发送'}).waitFor();await page.waitForTimeout(300);
  const gap=await page.evaluate(()=>document.querySelector('#chat-end').getBoundingClientRect().bottom-document.querySelector('#composer').getBoundingClientRect().top);
  assert(gap<=2,'actual messages must still follow latest');
  await page.evaluate(()=>window.scrollBy(0,-220));await page.waitForTimeout(180);
  const readingScroll=await page.evaluate(()=>scrollY);await page.waitForTimeout(3200);
  const readingAfterPoll=await page.evaluate(()=>scrollY);
  assert(Math.abs(readingAfterPoll-readingScroll)<3,'polling must not pull a reader away from earlier messages');
  await page.locator('#chat-latest').click();await page.waitForTimeout(200);
  const returnedGap=await page.evaluate(()=>document.querySelector('#chat-end').getBoundingClientRect().bottom-document.querySelector('#composer').getBoundingClientRect().top);
  assert(returnedGap<=2,'return-to-latest must restore follow');
  rows.push({viewport,passed:true,initial:first,deliberateScroll,retainedScroll,newChatTop,thinkingGap,latestGap:gap,readingScroll,readingAfterPoll,returnedGap});
  await page.close();
 }
 await writeFile('tmp/mobile-welcome-scroll-0.4.43.json',JSON.stringify(rows,null,2));console.log(JSON.stringify(rows));
}finally{await browser.close();}
