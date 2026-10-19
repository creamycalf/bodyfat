/* A linear, explicitly simulated walkthrough. No network or production data. */
const walkthrough=[
 {stage:0,page:'chat',title:'先用一个样例，走完真实使用流程',hint:'扮演林先生：先聊身体情况，再拍午餐，最后反馈加班安排。',next:'开始体验 →'},
 {stage:0,page:'chat',title:'第一步：通过对话认识你',hint:'下面是一段压缩的首次访谈样例。点击发送，看资料如何落到页面。',next:'发送这段样例'},
 {stage:1,page:'profile',title:'聊天里的信息，已经整理成档案',hint:'身高、体重、健康自述和生活习惯都有了出处。你不需要再填一次表。',next:'看自动生成的计划 →'},
 {stage:1,page:'plan',title:'同一次访谈，也生成了初版计划',hint:'活动、饮食、作息分别展示。接下来试试照片：拍下来，并不代表吃了。',next:'发送午餐照片与问题 →'},
 {stage:2,page:'food',title:'照片已分析，但没有计入摄入',hint:'样例消息：“这份多少热量？我还没吃，先看看。”',next:'发送：“刚才那份，整盘吃了一半”'},
 {stage:3,page:'today',title:'确认吃了，今日才出现实际摄入',hint:'半份记为 300–380 千卡，档案同步保留一条餐次；计划没有因此改变。',next:'发送：“这周加班到九点半，午休有二十分钟”'},
 {stage:4,page:'plan',title:'新的生活情况，让计划页面发生变化',hint:'晚间散步换成午休步行，饮食模块新增晚归图文。可以点“改前 / 改后”对照。',next:'看同步变化的今日看板 →'},
 {stage:4,page:'today',title:'今天该做什么，也同步更新了',hint:'活动改到午休，刚才的午餐记录仍然保留。这就是“聊完，页面跟着变”。',next:'完成体验 →'},
 {stage:4,page:'today',title:'体验完成，你只需要聊天和看结果',hint:'对话是入口；今日看行动，计划看安排，档案看资料和历史。',next:'重新体验'}
];
let journeyStep=0,freeExplore=false;
const originalRender=render;
const guide=document.createElement('section');guide.id='journey-guide';guide.setAttribute('aria-label','原型体验引导');document.querySelector('.shell').before(guide);
render=function(){originalRender();paintJourney()};
function moveJourney(index){journeyStep=index;freeExplore=false;const step=walkthrough[index];stage=step.stage;page=step.page;portion=.5;done=false;$('#toast').style.display='none';render();window.scrollTo(0,0)}
function journeyNext(){moveJourney(journeyStep===8?0:journeyStep+1)}
function paintJourney(){
 document.body.classList.toggle('journey-welcome',journeyStep===0&&!freeExplore);
 document.body.classList.toggle('journey-interview',journeyStep===1&&!freeExplore);
 const current=walkthrough[journeyStep];
 guide.innerHTML=journeyStep===0&&!freeExplore?'':`<div class="guide-copy"><span class="guide-count">${freeExplore?'自由查看':journeyStep===8?'已完成':`体验 ${journeyStep} / 7`}</span><div><b>${freeExplore?'你现在可以自由查看各个页面':current.title}</b><p>${freeExplore?'这里仍然是预设样例，不连接真实 AI。随时可以从头再体验。':current.hint}</p></div></div><div class="guide-actions">${journeyStep>0?'<button class="link" onclick="moveJourney(journeyStep-1)">上一步</button>':''}<button class="primary" onclick="journeyNext()">${current.next}</button></div>`;
 const reset=document.querySelector('.demo button');reset.setAttribute('onclick','moveJourney(0)');
 if(journeyStep===0&&!freeExplore){$('#content').innerHTML=`<section class="welcome"><span class="welcome-mark">知</span><div class="label">知衡 · 交互体验</div><h1>说说你的生活，<br>看看计划如何跟着变。</h1><p>不用填一堆表，也不用自己整理聊天记录。<br>我们用林先生的一天，带你走一遍。</p><div class="welcome-route"><span>聊身体情况</span><i>→</i><span>拍午餐</span><i>→</i><span>聊生活变化</span></div><button class="primary" onclick="moveJourney(1)">开始体验 →</button><small>约 2 分钟 · 全部为预设样例 · 不修改真实资料</small></section>`;return}
 if(journeyStep===1&&!freeExplore){$('#content').innerHTML=`<section class="interview-demo"><div class="heading"><div><h1>先聊聊你的情况</h1><p class="intro">正式使用时，AI 会逐步追问；这里将多轮访谈压缩为一个样例。</p></div></div><div class="interview-question"><span class="ai-icon">✳</span><div><b>知衡</b><p>你希望改善什么？可以聊聊身体情况、饮食、作息，以及健康方面需要注意的事。</p></div></div><div class="sample-message"><span class="label">即将发送的样例 · 林先生</span><p>我 35 岁，男，175 厘米、80 公斤，近半年大概重了 3 公斤。想先改善习惯，再慢慢减重。</p><p>工作久坐，经常吃外卖，通常凌晨一点睡。我原来觉得晚上能抽空散步。</p><p>没有已知疾病、长期用药或食物过敏，运动没有不舒服。</p><div class="row"><small>预设访谈样例，不是你的真实信息</small><button class="primary" onclick="journeyNext()">发送这段样例 ↑</button></div></div><p class="interview-foot">发送后，直接带你看生成的档案和计划。</p></section>`;return}
 if(journeyStep===8&&!freeExplore){$('#content').insertAdjacentHTML('afterbegin',`<section class="finish-note"><h2>日常使用，不需要操作这些演示步骤。</h2><p>直接聊天或发照片；需要变动时，AI 更新页面并说明原因。不是每句话都要改计划。</p><button onclick="freeExplore=true;render()">自由查看完整原型</button><button onclick="moveJourney(1)">再看一遍</button></section>`)}
 // Design explanations remain available, but don't compete with the walkthrough.
 if(page==='food'){
  const cards=[...document.querySelectorAll('#content > .grid.two > section:last-child > .card')];
  if(cards[1]){const extra=document.createElement('details');extra.className='alternate-food';extra.innerHTML='<summary>想试其他情况？更正食用份量</summary>';cards[1].before(extra);extra.append(cards[1])}
 }
}
// Navigation remains usable; the guide explicitly offers a return to its current step.
go=function(p){page=p;freeExplore=true;render();guide.innerHTML=`<div class="guide-copy"><span class="guide-count">自由查看</span><div><b>${p==='food'?'餐食分析':pages[p][1]}</b><p>当前数据来自刚才的样例。你也可以回到引导继续体验。</p></div></div><button class="primary" onclick="moveJourney(journeyStep)">返回引导 →</button>`;window.scrollTo(0,0)};
setStage=function(n){moveJourney([0,2,4,5,6][n]??0)};
moveJourney(0);
