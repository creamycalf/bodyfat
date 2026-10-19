import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require('../tmp/ui-tools/node_modules/playwright');
const browser=await chromium.launch({headless:true,channel:'msedge'});
const page=await browser.newPage({viewport:{width:390,height:844}});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto('http://127.0.0.1:8812/');
 await page.getByText('数据已连接',{exact:true}).waitFor();
 const progress=page.locator('#chat-assessment-progress');
 if(await progress.evaluate(el=>el.open))throw Error('Progress should start collapsed');
 if((await page.locator('#messages').boundingBox()).y>550)throw Error('Chat is pushed below the initial mobile viewport');
 await page.screenshot({path:'tmp/guided-weight-chat-first-390.png'});
 await progress.locator(':scope > summary').focus();
 await page.keyboard.press('Enter');
 if(!await progress.evaluate(el=>el.open))throw Error('Progress is not keyboard expandable');
 await page.locator('[data-start-assessment]').waitFor({state:'visible'});
 await page.locator('[data-skip-topic]').waitFor({state:'visible'});
 await page.locator('[data-start-assessment]').click();
 if(await page.locator('#message').inputValue()!=='继续了解我的情况，请结合刚才讨论的困难，帮我判断下一步。')throw Error('Continue button reverted to profile form mode');
 await page.locator('#message').fill('');
 await page.locator('#saved-profile-summary > summary').click();
 await page.locator('#saved-profile-summary [data-open-page="archive"]').waitFor({state:'visible'});
 await progress.locator(':scope > summary').click();
 const replies=[];
 async function send(text){
  const expected=replies.length+1;
  await page.locator('#message').fill(text);await page.locator('#send').click();
  await page.waitForFunction(n=>!document.querySelector('#send').disabled&&document.querySelectorAll('#messages .bubble.assistant:not([data-pending-chat])').length>=n,expected,{timeout:20000});
  const reply=await page.locator('#messages .bubble.assistant').last().innerText();
  console.log(JSON.stringify({user:text,reply}));
  if(await page.locator('#messages [role="alert"]').count())throw Error(reply);
  if(await progress.evaluate(el=>el.open))throw Error('Collapsed progress reopened after a reply');
  for(const detail of await page.locator('#messages .receipt-details').all()){
   if(await detail.evaluate(el=>el.open))throw Error('Routine save receipt should stay compact');
  }
  replies.push(reply);return reply;
 }
 const turns=[
  '我想减肥，你带着我一步步来。',
  '我38岁，男，身高175厘米，体重85公斤，想先减到78公斤，最难是加班后吃多，常吃外卖。',
  '没有确诊疾病，没有用药，没有手术史，没有食物过敏，平时运动也没有不舒服。',
  '早餐两个鸡蛋一杯牛奶；午餐一碗米饭、鸡肉和蔬菜；晚餐经常一份外卖炒面，份量一大盒；下午喝一杯奶茶，晚上偶尔吃薯片。',
  '平时凌晨一点睡，早上七点起。办公室久坐，一天走路约20分钟，晚上八点下班，每天可以抽20分钟活动。去年80公斤，现在85公斤，以前节食坚持不住，晚上饿得厉害。'
 ];
 for(const text of turns){
  const reply=await send(text);
  if(!/[？?]|请核对/.test(reply))throw Error('Guidance stopped: '+reply);
  if(await page.locator('[data-chat-plan]').count())throw Error('Plan before confirmation');
 }
 if(!replies.at(-1).includes('请核对我理解的情况')){
  console.log(JSON.stringify(await page.evaluate(async()=>{const r=await fetch('/api/work/state');return r.json();})));
  throw Error('No summary');
 }
 if(replies.at(-1).includes('饮食条件：没有确诊疾病'))throw Error('Health paragraph was incorrectly saved as food conditions');
 const checkedProfile=await page.evaluate(async()=>{const r=await fetch('/api/work/state');return (await r.json()).profile;});
 if(String(checkedProfile.food_habits||'').includes('没有确诊疾病'))throw Error('Health paragraph leaked into saved food habits');
 const savedReceipt=page.locator('#messages .receipt-details').last();
 if(!await savedReceipt.count())throw Error('No expandable save evidence');
 await savedReceipt.locator('summary').focus();await page.keyboard.press('Enter');
 await savedReceipt.locator('[data-undo]').waitFor({state:'visible'});
 if(!(await savedReceipt.innerText()).includes('已'))throw Error('Saved evidence was lost');
 await savedReceipt.locator('summary').click();
 const nextQuestion=await page.evaluate(async()=>{const r=await fetch('/api/work/state');return (await r.json()).assessment?.next_question;});
 if(nextQuestion&&await progress.innerText().then(text=>text.includes(nextQuestion)))throw Error('Last chat question is duplicated in the progress panel');
 await page.screenshot({path:'tmp/guided-weight-summary-390.png',fullPage:true});
 let reply=await send('确认');
 if(reply.includes('用新记录'))reply=await send('用新记录');
 if(reply.includes('请核对我理解的情况'))reply=await send('确认');
 if(reply.includes('今天已经吃过哪些餐'))reply=await send('今天早餐午餐晚餐都吃过了，今天没有安排机会，请明天开始。');
 await page.locator('[data-chat-plan]').last().waitFor();
 await page.reload();await page.locator('[data-chat-plan]').last().waitFor();
 await page.locator('[data-chat-plan]').last().click();
 if(await page.locator('#plan').isHidden())throw Error('Saved plan did not open');
 for(const width of [320,390,1280]){
  await page.setViewportSize({width,height:900});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Layout overflow');
  await page.screenshot({path:`tmp/guided-weight-plan-${width}.png`,fullPage:true});
 }
 await page.locator('[data-view="chat"]').first().click();
 const savedPlanId=await page.locator('[data-chat-plan]').last().getAttribute('data-chat-plan');
 const latestReceipt=page.locator('#messages .receipt-details').last();
 await latestReceipt.locator('summary').click();
 const undoResponse=page.waitForResponse(response=>response.url().endsWith('/api/work/action')&&response.request().postDataJSON()?.action==='undo');
 await latestReceipt.locator('[data-undo]').click();
 if(!(await undoResponse).ok())throw Error('Expanded receipt undo failed');
 const plansAfterUndo=await page.evaluate(async()=>{const r=await fetch('/api/work/state');return (await r.json()).plans;});
 if(plansAfterUndo.some(plan=>plan.id===savedPlanId))throw Error('Undo did not remove the just-saved fictional plan');
 const fixture=await page.evaluate(async()=>{const r=await fetch('/api/work/state');return r.json();});
 const fixtureCid=await page.evaluate(()=>localStorage.getItem('zhiheng-session-v2'));
 const fixtureConversation=fixture.conversations.find(c=>c.id===fixtureCid);
 fixtureConversation.messages.push({id:'ui-failure-message',role:'assistant',text:'这次模型处理超时，已保存的资料仍保留。',result:{client_message_id:'ui-failure-turn',conversation_id:fixtureCid,receipts:['已保留本次更新失败状态，可从对话重试','本次未完成计划评估，现有计划未改动'],ai_error:'AI_TIMEOUT',background:{status:'failed'},retry_chat:'ui-failure-retry'}});
 fixture.evaluation_jobs.push({id:'ui-failure-retry',kind:'chat',status:'failed',conversation_id:fixtureCid,request_date:fixture.today});
 await page.route('**/api/work/state',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(fixture)}));
 await page.reload();await page.locator('[data-retry-chat="ui-failure-retry"]').waitFor({state:'visible'});
 if(!await page.locator('#messages .receipt-attention').last().innerText().then(text=>text.includes('AI_TIMEOUT')))throw Error('Failure code is hidden');
 for(const width of [320,390,1280]){
  await page.setViewportSize({width,height:900});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Chat layout overflow');
  await page.locator('#chat-assessment-progress > summary').click();
  await page.locator('#saved-profile-summary > summary').click();
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Expanded details overflow');
  await page.screenshot({path:`tmp/guided-weight-chat-details-${width}.png`,fullPage:true});
  await page.locator('#saved-profile-summary > summary').click();
  await page.locator('#chat-assessment-progress > summary').click();
 }
 if(errors.length)throw Error(errors.join('\n'));
 console.log('PASS: guided consultation and saved plan; compact keyboard-expandable progress and receipts; successful undo and visible timeout retry; 320/390/1280px layouts');
}finally{await browser.close();}
