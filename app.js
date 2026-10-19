import {setupVoice} from './voice.js';
import {enhanceArchive} from './archive-tools.js';
import {setupWorkbench,renderWorkbench,prose} from './workbench-ui.js';
import './mobile-compat.js';
import {renderHealthPages,bindHealthPages,recipeDraft} from './health-pages.js';
import {watchImageJobs,conversationTurns} from './image-jobs-ui.js';
import {prepareUpload,imageError} from './image-upload.js';
import {setupNutritionReportEditing,nutritionReport} from './nutrition-report-ui.js';
setupWorkbench();
const $=s=>document.querySelector(s), esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let data=null,busy=false,voiceBusy=false,source='text',retry=null,cid=localStorage.getItem('zhiheng-session-v2')||crypto.randomUUID();
let attachedMedia=null;
let attachedConversation=null,imageJobs=[],imageSyncError='',imageWatcher=null;
const dismissedPhotoReplies=new Set();
let pendingAttachment=null,attachmentUploading=false;
window.addEventListener('beforeunload',e=>{if(pendingAttachment){e.preventDefault();e.returnValue='';}});
let pendingChat=null;
const chatDetailExpansion=new Map();
let followChatEnd=true,chatScrollFrame=0,scrollConversation=cid,programmaticScrollUntil=0,lastWindowScroll=scrollY;
$('#intake').insertAdjacentHTML('afterend','<div id="chat-end" aria-hidden="true"></div>');
$('#composer').insertAdjacentHTML('afterbegin','<button id="chat-latest" type="button" hidden>回到最新 ↓</button>');
$('#chat-latest').onclick=()=>scrollChatEnd();
$('#open-history').onclick=()=>$('#history-dialog').showModal();
$('#close-history').onclick=()=>$('#history-dialog').close();
const stages={reading:'正在读取本次消息与已有资料',thinking:'AI 正在思考，等待回复…',validating:'回复已收到，正在核对档案与计划变更',saving:'正在保存本次结果'};
function paintPending(){
 if(!pendingChat||pendingChat.cid!==cid){document.querySelectorAll('[data-pending-chat]').forEach(x=>x.remove());return;}
 const existing=document.querySelector('.thinking-status');
 if(existing){
  existing.querySelector('strong').textContent=stages[pendingChat.stage];
  existing.querySelector('small').textContent=`已等待 ${Math.floor((Date.now()-pendingChat.started)/1000)} 秒`;
  existing.querySelector('details p').textContent=pendingChat.history.map(s=>stages[s]).join('\n');
  scheduleChatEnd();
  return;
 }
 $('#messages').insertAdjacentHTML('beforeend',`<div data-pending-chat class="bubble user">${esc(pendingChat.text)}</div><div data-pending-chat class="bubble assistant thinking-status" role="status"><span class="thinking-dot"></span><strong>${esc(stages[pendingChat.stage])}</strong><small>已等待 ${Math.floor((Date.now()-pendingChat.started)/1000)} 秒</small><details><summary>查看处理进度</summary><p>${pendingChat.history.map(s=>esc(stages[s])).join('\n')}</p><p class="muted">这里显示实际处理阶段。当前连接一次返回完整回复，不提供逐字输出或内部推理。</p></details></div>`);
 scheduleChatEnd();
}
async function chatStream(payload){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),110000);
 try{
  const response=await fetch('/api/work/chat-stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:controller.signal});
  if(!response.ok)throw Error('连接失败，请重试');
  const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='',result;
  while(true){const {value,done}=await reader.read();buffer+=decoder.decode(value||new Uint8Array(),{stream:!done});let split;
   while((split=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,split);buffer=buffer.slice(split+1);if(!line.trim())continue;const event=JSON.parse(line);
    if(event.type==='error')throw Error(event.error);
    if(event.type==='result')result=event.result;
    if(event.type==='progress'&&pendingChat&&stages[event.stage]){pendingChat.stage=event.stage;if(!pendingChat.history.includes(event.stage))pendingChat.history.push(event.stage);paintPending();}
   }if(done)break;
  }if(!result)throw Error('连接中断，原文已保留。可重试获取保存结果');return result;
 }finally{clearTimeout(timer);}
}
window.addEventListener('discuss-media',e=>{closeImageReport();attachedMedia=e.detail.id;attachedConversation=cid;view('chat');paintReplyPhoto();$('#message').focus();});
const labels={suggested:'建议中',active:'执行中',paused:'已暂停',completed:'已完成',replaced:'已替换',done:'完成',partial:'部分完成',skipped:'跳过',deferred:'已延期',unreported:'未反馈'};
function sourceHtml(source,fallback='既有资料'){
 if(source?.conversation_id){const at=source.at?new Date(source.at).toLocaleString():'时间未知';return `来自对话 · ${esc(at)} <button type="button" class="link-button" data-source-conversation="${esc(source.conversation_id)}" data-source-message="${esc(source.message_id||'')}">查看原话</button>`;}
 if(source?.text==='手动编辑')return `手动编辑 · ${esc(source.at?new Date(source.at).toLocaleString():'')}`;
 const names={voice:'语音对话',conversation:'对话',intake_form:'资料表单',image:'图片核对'};return esc(names[source]||fallback);
}
function toast(text){$('#toast').textContent=text;$('#toast').hidden=false;setTimeout(()=>$('#toast').hidden=true,4500);}
function recordText(record){const v=record.value||{};if(v.description)return v.description;const names={kg:'公斤',hours:'小时',cm:'厘米',name:'项目',value:'数值',unit:'单位',date:'日期'};return Object.entries(v).filter(([k,x])=>x!==null&&typeof x!=='object').map(([k,x])=>`${names[k]||k}：${x}`).join('，')||'详细记录';}
async function api(path,p){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),100000);try{const r=await fetch(path,{method:p?'POST':'GET',headers:p?{'Content-Type':'application/json'}:{},body:p?JSON.stringify(p):undefined,signal:controller.signal});const result=await r.json();if(!r.ok)throw Error(result.error||'请求失败');return result;}finally{clearTimeout(timer);}}
setupNutritionReportEditing(()=>data,api,refresh,toast);
function view(name){document.querySelectorAll('.view').forEach(x=>x.hidden=x.id!==name);document.querySelectorAll('[data-view]').forEach(x=>x.classList.toggle('active',x.dataset.view===name));const names={chat:'对话',dashboard:'看板',plan:'计划',archive:'档案',mine:'设置'};if($('#breadcrumb'))$('#breadcrumb').textContent=names[name]||name;scheduleComposerLayout();}
document.querySelectorAll('[data-view]').forEach(x=>x.onclick=()=>view(x.dataset.view));
// Shared page renderers keep current plans and history consistent.
function receiptText(result){
 return (result.receipts||[]).filter(x=>x!=='已保留本次更新失败状态，可从对话重试').map(x=>x==='模型未返回完整页面更新判断，本轮页面评估不完整'?'本次未完成计划评估；实际保存结果以其他条目为准':x).map(esc).join(' · ');
}
function retryAvailable(id){return Boolean(id&&data?.evaluation_jobs?.some(job=>job.id===id&&job.kind==='chat'&&job.status==='failed'&&job.request_date===data.today));}
function chatReceipt(result,messageId){
 const text=receiptText(result),canRetry=retryAvailable(result.retry_chat);
 const undo=result.receipts?.length&&result.client_message_id?`<button data-undo="${esc(result.client_message_id)}">撤销本次整理</button>`:'';
 const attention=canRetry||result.ai_error||result.page_error||result.food_error||['failed','partial'].includes(result.background?.status)||/未完成|未保存|未返回|待核实/.test(text);
 if(!text&&!canRetry)return '';
 if(attention)return `<div class="receipt receipt-attention"><p>${text||'本次处理尚未完成'}${result.ai_error?` <span class="receipt-error-code">(${esc(result.ai_error)})</span>`:''}</p><div class="actions">${canRetry?`<button class="primary" data-retry-chat="${esc(result.retry_chat)}" data-retry-conversation="${esc(result.conversation_id||cid)}">继续这次请求</button>`:''}${undo}</div></div>`;
 return `<details class="receipt receipt-details" data-chat-detail="${esc(cid+':receipt:'+messageId)}"><summary>查看本次整理</summary><p>${text}</p>${undo}</details>`;
}
const photoUrl=id=>'/api/media/image?id='+encodeURIComponent(id);
function replyPhoto(){
 if(pendingAttachment)return null;
 if(attachedMedia&&attachedConversation===cid)return {id:attachedMedia,key:cid+':manual:'+attachedMedia};
 const messages=data?.conversations.find(c=>c.id===cid)?.messages||[],last=conversationTurns(messages,imageJobs,cid).at(-1)?.assistant;
 if(last?.result?.reply_source!=='saved_image_report')return null;
 const user=messages.find(m=>m.id===last.result.client_message_id),key=cid+':'+last.id;
 if(!user?.media_id||dismissedPhotoReplies.has(key))return null;
 return {id:user.media_id,key};
}
function paintReplyPhoto(){
 const root=$('#reply-photo');if(!root)return;
 const photo=replyPhoto(),media=data?.media.find(m=>m.id===photo?.id);
 root.hidden=!media;
 const markup=media?`<img src="${photoUrl(media.id)}" alt="正在回复的照片"><div><strong>接着聊这张照片</strong><small>补充食材、份量，或直接回答上面的问题</small></div><button type="button" data-clear-photo aria-label="取消关联照片">×</button>`:'';
 if(root._markup!==markup){root.innerHTML=markup;root._markup=markup;}
 const clear=root.querySelector('[data-clear-photo]');if(clear)clear.onclick=()=>{dismissedPhotoReplies.add(photo.key);const last=data.conversations.find(c=>c.id===cid)?.messages.at(-1);if(last)dismissedPhotoReplies.add(cid+':'+last.id);attachedMedia=null;attachedConversation=null;paintReplyPhoto();};
 $('#message').placeholder=media?'继续问这张照片，比如怎么搭配、吃多少合适…':pendingAttachment?'想了解营养、份量或报告指标？也可以直接发送…':'问饮食、运动，或发食物 / 报告照片…';
}
function photoMarkup(id){return `<button class="chat-photo-open" type="button" data-open-photo="${esc(id)}" aria-label="查看照片大图"><img class="chat-photo" src="${photoUrl(id)}" alt="发送的照片" width="240" height="180"></button>`;}
function imageSummary(media){
 const report=media.review?.report;if(!report)return '';
 const kcal=report.totals?.kcal||report.partial_totals?.kcal;
 const shown=Array.isArray(kcal)&&kcal.length===2?kcal[0]===kcal[1]?String(kcal[0]):kcal.join('–'):null;
 const partial=!report.totals?.kcal&&shown;
 const label=report.kind==='food'?(shown?`${partial?'已估算部分':'照片中食物'} · ${shown} kcal`:'食物已识别 · 热量待补充'):report.kind==='report'?'报告中的可读信息':'图片内容';
 return `<section class="chat-image-summary" data-chat-image-summary="${esc(media.id)}"><div class="chat-image-summary-head"><strong>${esc(label)}</strong><span>${report.kind==='food'?'照片估算':'图片解读'}</span></div>${report.kind==='food'?`<p>${partial?'还有项目未知，不代表整盘总量。':'份量和食材待核对。'}${media.food_decision?.status==='consumed'?'实际食用情况见保存回执。':'尚未计入实际摄入。'}</p>`:''}<div class="chat-image-actions"><button type="button" class="chat-report-open" data-open-report="${esc(media.id)}" aria-haspopup="dialog">查看分析结果 <span aria-hidden="true">↗</span></button><button type="button" class="chat-photo-reply" data-discuss-photo="${esc(media.id)}">接着聊这张照片</button></div></section>`;
}
function closeImageReport(){
 const dialog=$('.chat-report-dialog');if(!dialog)return;
 dialog.close();dialog.remove();document.documentElement.classList.remove('image-report-open');
}
function syncImageReport(){
 const dialog=$('.chat-report-dialog');if(!dialog)return;
 const media=data?.media.find(m=>m.id===dialog.dataset.mediaId);if(!media?.review?.report){closeImageReport();return;}
 const body=dialog.querySelector('.chat-report-body'),markup=nutritionReport(media);
 if(body._markup!==markup){const top=body.scrollTop;body.innerHTML=markup;body._markup=markup;body.scrollTop=top;}
}
function openImageReport(id){
 const media=data?.media.find(m=>m.id===id);if(!media?.review?.report){toast('这张图片的分析结果尚未准备好');return;}
 closeImageReport();
 const dialog=document.createElement('dialog');dialog.className='chat-report-dialog';dialog.dataset.mediaId=id;
 dialog.setAttribute('aria-labelledby','chat-report-title');
 dialog.innerHTML=`<header class="chat-report-heading"><div><small>知衡 · 图片解读</small><h2 id="chat-report-title">分析结果</h2></div><button type="button" data-close-report aria-label="关闭分析结果" autofocus>关闭 ×</button></header><div class="chat-report-body"></div><footer class="chat-report-footer"><span>看完可以回到原来的对话继续聊</span><button type="button" class="primary" data-report-discuss="${esc(id)}">接着聊这张照片</button></footer>`;
 document.body.append(dialog);syncImageReport();
 dialog.querySelector('[data-close-report]').onclick=closeImageReport;
 dialog.addEventListener('close',()=>{dialog.remove();if(!$('.chat-report-dialog'))document.documentElement.classList.remove('image-report-open');scheduleComposerLayout();});
 dialog.addEventListener('click',e=>{if(e.target!==dialog)return;const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)closeImageReport();});
 document.documentElement.classList.add('image-report-open');dialog.showModal();
}
function imageProgress(job){
 const failed=job.status==='failed',partial=job.status==='partial';
 const status=failed?'这张照片还没分析成功':partial?'图片已分析，还有内容待处理':job.status==='succeeded'?'正在读取图片回复…':job.stage==='followup'?'看完了，正在整理回复…':job.status==='pending'?'照片已收到，稍等一下…':'正在看这张照片…';
 return `<div class="bubble assistant image-inline-progress" data-image-job-id="${esc(job.id)}" role="status">${failed?'':'<span class="thinking-dot" aria-hidden="true"></span>'}<strong>${status}</strong><p>${failed?esc(imageError(job.error||'稍后可以重试')):job.attempts>1?'正在重试，你也可以继续打字补充。':'你可以继续说，图片结果会出现在这里。'}</p>${partial&&job.error?`<p role="alert">${esc(imageError(job.error))}</p>`:''}${failed&&!['AI_HTTP_413','AI_IMAGE_TOO_LARGE'].includes(job.error)?`<button type="button" data-retry-image="${esc(job.id)}">重试这张照片</button>`:''}${failed&&['AI_HTTP_413','AI_IMAGE_TOO_LARGE'].includes(job.error)?'<p>请重新选择原图上传。</p>':''}</div>`;
}
function renderMessages(conv){
 const root=$('#messages'),turns=conversationTurns(conv?.messages||[],imageJobs,cid);
 const visible=new Set(),seenPhotos=new Set();
 root.querySelector('[data-chat-welcome]')?.remove();
 for(const turn of turns){
  visible.add(turn.key);
  let node=[...root.children].find(n=>n.dataset.turnId===turn.key);
  if(!node){node=document.createElement('section');node.className='chat-turn';node.dataset.turnId=turn.key;}
  const mediaId=turn.job?.media_id||turn.user?.media_id,media=data.media.find(m=>m.id===mediaId);
  const firstPhoto=mediaId&&!seenPhotos.has(mediaId);if(mediaId)seenPhotos.add(mediaId);
  const caption=turn.job?.message_text||turn.user?.text||'';
  const user=turn.user||turn.job?`<div class="bubble user${firstPhoto?' photo-message':''}" data-message-id="${esc(turn.user?.id||turn.key)}">${firstPhoto?photoMarkup(mediaId):mediaId?`<button class="chat-photo-reference" type="button" data-open-photo="${esc(mediaId)}">↳ 关于这张照片</button>`:''}${caption?`<div class="chat-user-text">${esc(caption)}</div>`:''}</div>`:'';
  const m=turn.assistant;
  const plan=m?.result?.plan;
  const extras=m?.result?.recipe_draft?recipeDraft(m.result):plan?`<section class="card"><strong>${esc(plan.title)}</strong><p>${esc(plan.start_date)} 至 ${esc(plan.end_date)} · ${plan.items.length} 项安排</p><button data-chat-plan="${esc(plan.id)}" data-chat-version="${plan.version}">查看完整计划与做法</button></section>`:'';
  const assistant=m?`<div class="bubble assistant" data-message-id="${esc(m.id)}"><div class="assistant-label">知衡</div>${prose(m.text)}</div>${media&&firstPhoto?imageSummary(media):''}${extras}${m.result?chatReceipt(m.result,m.id):''}`:turn.job?imageProgress(turn.job):'';
  for(const [kind,markup] of [['user',user],['answer',assistant]]){
   let part=node.querySelector(':scope > [data-turn-part="'+kind+'"]');
   if(!part){part=document.createElement('div');part.dataset.turnPart=kind;node.append(part);}
   if(part._markup!==markup){part.innerHTML=markup;part._markup=markup;}
  }
  // Do not reinsert unchanged nodes: focus, expanded details and images survive polls.
  const position=turns.indexOf(turn),current=root.children[position];
  if(current!==node)root.insertBefore(node,current||null);
 }
 for(const child of [...root.children])if(child.dataset.turnId&&!visible.has(child.dataset.turnId)||child.dataset.chatError!==undefined)child.remove();
 if(!turns.length&&!pendingChat){
  root.innerHTML=`<section class="chat-welcome" data-chat-welcome aria-labelledby="welcome-title"><h2 id="welcome-title">今天想聊什么？</h2><p>直接说说你的情况，或从下面开始。</p><div class="chat-starters"><button type="button" data-starter="我想减肥，请先一起了解我的基础情况和目标。"><strong>开始减脂</strong><span>一起了解情况和目标</span></button><button type="button" data-start-photo><strong>这餐怎么吃</strong><span>看份量与搭配</span></button><button type="button" data-starter="我想找适合自己的运动方式，请结合我的身体情况、时间和场地帮我安排。"><strong>安排运动</strong><span>结合身体、时间和场地</span></button><button type="button" data-start-report><strong>看懂报告</strong><span>看指标与合理下一步</span></button></div></section>`;
  root.querySelectorAll('[data-starter]').forEach(b=>b.onclick=()=>{if(voiceBusy)return;if(!$('#message').value.trim())$('#message').value=b.dataset.starter;$('#message').focus();$('#message').dispatchEvent(new Event('input',{bubbles:true}));});
  root.querySelector('[data-start-photo]').onclick=()=>$('#photo').click();
  root.querySelector('[data-start-report]').onclick=()=>{if(voiceBusy)return;if(!$('#message').value.trim())$('#message').value='请帮我解读这份检查报告，说明值得关注的指标和合理的下一步。';$('#photo').click();};
 }
 $('#chat').classList.toggle('has-messages',Boolean(turns.length||pendingChat));
 $('#chat').classList.toggle('chat-empty',!turns.length&&!pendingChat);
 let notice=root.querySelector('.image-sync-notice');
 if(imageSyncError&&turns.some(t=>t.job)){if(!notice){notice=document.createElement('p');notice.className='image-sync-notice muted';notice.setAttribute('role','status');root.append(notice);}notice.textContent=imageSyncError;}else notice?.remove();
 paintReplyPhoto();
}
function render(){
 if(scrollConversation!==cid){scrollConversation=cid;followChatEnd=true;}
 document.querySelectorAll('[data-chat-detail]').forEach(detail=>chatDetailExpansion.set(detail.dataset.chatDetail,detail.open));
 document.querySelectorAll('.evaluation-failure').forEach(x=>x.remove());
 $('#connection').textContent='数据已连接';$('#today').textContent=new Date().toLocaleDateString();$('#confirm-each').checked=data.settings.confirm_each;
 const conv=data.conversations.find(x=>x.id===cid);
 const assessment=data.assessment||{},topics=assessment.topics||[],open=topics.find(t=>t.status==='open');
 const saved=Object.entries(data.profile).filter(([k])=>data.fields[k]);
 const upcoming=[...data.plans].reverse().find(p=>p.start_guide?.kind==='adaptive'&&['active','suggested'].includes(p.status)&&p.start_date===data.today);
 $('#assessment').innerHTML=`<details class="assessment-strip" id="chat-assessment-progress" data-chat-detail="${esc(cid+':progress')}"><summary>记住的情况 · ${saved.length} 项${data.pending.length?' · '+data.pending.length+' 项待核实':''}</summary><div class="assessment-body"><div class="assessment-topics">${topics.map(t=>`<span class="${esc(t.status)}">${esc(t.title)} · ${t.status==='known'?'已了解':t.status==='skipped'?'已跳过':'待了解'}</span>`).join('')}</div>${open&&assessment.stage!=='持续跟进'?`<div class="actions"><button data-start-assessment>继续对话</button><button data-skip-topic="${esc(open.title)}">暂时跳过${esc(open.title)}</button><button data-preliminary>先生成初版计划</button></div>`:''}<details id="saved-profile-summary" data-chat-detail="${esc(cid+':profile')}"><summary>实际已保存的档案 · ${saved.length} 项</summary>${saved.map(([k,v])=>`<p><strong>${esc(data.fields[k])}：</strong>${esc(Array.isArray(v)?v.join('、')||'自述无':v)}</p>`).join('')||'<p>还没有已保存的档案。对话建议不等于入档；回答后可在这里核对。</p>'}<button data-open-page="archive">核对档案与原话</button></details>${upcoming?`<section class="assessment-next"><h3>可选的下一步</h3>${upcoming.start_guide.steps.map(step=>`<p>${esc(step)}</p>`).join('')}<button data-talk="我想根据当前安排反馈执行情况或调整下一步。">反馈或调整</button></section>`:''}</div></details>`;
 renderMessages(conv);
 document.querySelectorAll('[data-chat-plan]').forEach(b=>b.onclick=()=>{view('plan');$('#plan-content').scrollIntoView({block:'start'});});
 document.querySelectorAll('[data-save-recipe]').forEach(b=>b.onclick=()=>action({action:'recipe_save',id:b.dataset.saveRecipe}));
 const session=data.sessions[cid], last=[...(conv?.messages||[])].reverse().find(x=>x.result?.form);
 renderForm(session?.waiting&&!session.intake_done?last?.result.form:null);
 const live=data.plans.filter(p=>['active','suggested','paused'].includes(p.status));
 renderHealthPages(data,{sourceHtml,field,recordText});
 renderWorkbench(data,view,send);
 for(const review of data.review_cards||[]){
  const card=document.createElement('section');card.className='card';
  const title=document.createElement('h3');title.textContent=review.due?'到了约定复盘时间':'最近执行反馈';card.append(title);
  const text=document.createElement('p');text.textContent=`过去最多七天：已反馈 ${review.observed}/${review.expected} 项。${review.reason}`;card.append(text);
  const observations=review.observations||{},evidence=document.createElement('p');evidence.className='muted';
  evidence.textContent=`同期记录：饥饿感 ${observations.hunger?.count||0} 条、睡眠 ${observations.sleep?.count||0} 条、活动 ${observations.activity?.count||0} 条、体重 ${observations.weight?.count||0} 条。${review.unknowns?.length?'尚未了解：'+review.unknowns.join('、')+'。':''}${review.observation_condition||''}`;card.append(evidence);
  const hunger=document.createElement('select');hunger.setAttribute('aria-label','本周饥饿感');hunger.innerHTML='<option value="unknown">饥饿感：暂未说明</option><option value="comfortable">饥饿感：总体舒适</option><option value="hungry">饥饿感：常觉得饿</option><option value="very_hungry">饥饿感：明显难受</option>';card.append(hunger);
  const difficulty=document.createElement('textarea');difficulty.maxLength=500;difficulty.placeholder='最难执行的一点（可选）';difficulty.setAttribute('aria-label','执行困难');card.append(difficulty);
  const note=document.createElement('textarea');note.maxLength=500;note.placeholder='这次执行的感受或困难（可选）';note.setAttribute('aria-label','复盘感受或困难');card.append(note);
  const choices=review.decision==='simplify'?[['simplify','明天起试最低行动'],['maintain','保持当前行动']]:review.observed?[['maintain','保持当前行动']]:[['assess','保存感受，稍后补充评估']];
  for(const [choice,label] of choices){const button=document.createElement('button');button.textContent=label;button.onclick=()=>action({action:'review_plan',id:review.plan_id,version:review.version,choice,note:note.value,hunger:hunger.value,difficulty:difficulty.value});card.append(button);}
  const reviewedPlan=data.plans.find(p=>p.id===review.plan_id&&p.version===review.version);
  for(const item of reviewedPlan?.items||[]){
   if(!item.alternatives||item.alternatives===item.detail)continue;
   const alternative=document.createElement('p');alternative.textContent=`${item.title} · 已保存替代：${item.alternatives}`;card.append(alternative);
   const replace=document.createElement('button');replace.textContent=`明天起替换「${item.title}」`;replace.onclick=()=>action({action:'review_plan',id:review.plan_id,version:review.version,choice:'replace',item_id:item.id,note:note.value,hunger:hunger.value,difficulty:difficulty.value});card.append(replace);
  }
  const discuss=document.createElement('button');discuss.textContent='补充感受与困难';discuss.onclick=()=>{view('chat');$('#message').value='我想复盘执行情况，最近的感受和困难是：';$('#message').focus();};card.append(discuss);
  $('#plan-content').append(card);
 }
 for(const review of (data.reviews||[]).slice(-3).reverse()){
  const history=document.createElement('section');history.className='card';
  const text=document.createElement('p');text.textContent=`${review.as_of} 复盘 · ${{assess:'补充评估',maintain:'保持行动',simplify:'最低行动',replace:'替代行动'}[review.choice]||review.choice} · 版本 ${review.version} → ${review.result_version}。${review.change_explanation||review.reason} ${review.difficulty?'困难：'+review.difficulty:''}`;history.append(text);$('#plan-content').append(history);
 }
 for(const turn of data.interrupted_turns||[]){
  const card=document.createElement('section');card.className='card evaluation-failure';
  const title=document.createElement('h3');title.textContent='有一条请求尚未完成';card.append(title);
  const detail=document.createElement('p');detail.textContent=turn.text;card.append(detail);
  const note=document.createElement('p');note.textContent=turn.resumable?'已保存的资料仍在，可继续处理剩余内容。':'此后资料或日期已变化，请根据当前情况重新说明；已保存的资料仍在。';card.append(note);
  const button=document.createElement('button');button.textContent=turn.resumable?'恢复未完成请求':'继续说明当前情况';
  button.onclick=()=>{cid=turn.conversation_id;localStorage.setItem('zhiheng-session-v2',cid);view('chat');if(turn.resumable)send('恢复未完成请求',{resume_turn:turn.id});else{$('#message').value='请根据当前已保存资料继续：';$('#message').focus();}};
  card.append(button);$('#assessment').append(card);
 }
 bindHealthPages(data,{view,send,toast});
 document.querySelector('[data-start-assessment]')?.addEventListener('click',()=>{$('#message').value='继续了解我的情况，请结合刚才讨论的困难，帮我判断下一步。';$('#message').focus();});
 document.querySelector('[data-skip-topic]')?.addEventListener('click',e=>action({action:'assessment_skip',topic:e.currentTarget.dataset.skipTopic}));
 document.querySelector('[data-preliminary]')?.addEventListener('click',()=>send('资料还不完整，请先根据已知情况生成一份初版计划，明确标出未知项。'));
 const history=[...data.conversations];
 for(const job of imageJobs)if(job.conversation_id&&!history.some(c=>c.id===job.conversation_id))history.push({id:job.conversation_id,created_at:job.created_at,messages:[{text:job.message_text||'照片对话'}]});
 $('#history').innerHTML=history.reverse().filter(c=>JSON.stringify(c.messages).includes($('#history-search').value)).map(c=>`<div class="item"><button data-conversation="${esc(c.id)}">${esc(c.messages[0]?.text||'对话')}</button><p class="muted">${esc(c.updated_at||c.created_at)}</p></div>`).join('');
 document.querySelectorAll('[data-plan]').forEach(b=>b.onclick=()=>action({action:'plan_status',id:b.dataset.plan,version:Number(b.dataset.version),status:b.dataset.status}));
 document.querySelectorAll('[data-adjust]').forEach(b=>b.onclick=()=>{view('chat');$('#message').value='请调整当前计划：';$('#message').focus();});
 document.querySelectorAll('[data-task]').forEach(b=>b.onclick=()=>{const payload={action:'feedback',task_id:b.dataset.task,status:b.dataset.feedback};if(payload.status==='deferred'){const next=new Date();next.setDate(next.getDate()+1);const suggested=`${next.getFullYear()}-${String(next.getMonth()+1).padStart(2,'0')}-${String(next.getDate()).padStart(2,'0')}`,target=prompt('延期到哪一天？请输入 YYYY-MM-DD',suggested);if(!target)return;payload.deferred_to=target;}action(payload);});
 document.querySelectorAll('[data-pending]').forEach(b=>b.onclick=()=>action({action:'pending',id:b.dataset.pending,accept:b.dataset.accept==='true'}));
 document.querySelectorAll('[data-undo]').forEach(b=>b.onclick=()=>action({action:'undo',id:b.dataset.undo}));
 document.querySelectorAll('[data-retry-chat]').forEach(b=>b.onclick=()=>{if(busy)return;cid=b.dataset.retryConversation;localStorage.setItem('zhiheng-session-v2',cid);send('恢复未完成请求',{retry_chat:b.dataset.retryChat});});
 document.querySelectorAll('[data-conversation]').forEach(b=>b.onclick=()=>{if(voiceBusy){toast('请先完成或取消语音录入');return;}$('#history-dialog').close();cid=b.dataset.conversation;localStorage.setItem('zhiheng-session-v2',cid);render();view('chat');});
 document.querySelectorAll('[data-source-conversation]').forEach(b=>b.onclick=()=>{cid=b.dataset.sourceConversation;localStorage.setItem('zhiheng-session-v2',cid);render();view('chat');const target=document.querySelector(`[data-message-id="${CSS.escape(b.dataset.sourceMessage)}"]`);if(target){followChatEnd=false;target.classList.add('source-highlight');target.scrollIntoView({block:'center'});paintLatestButton();}});
 document.querySelectorAll('[data-delete-record]').forEach(b=>b.onclick=async()=>{if(confirm('删除这条实际记录？'))try{await api('/api/records/delete',{id:b.dataset.deleteRecord,confirm:true});await refresh();}catch(e){toast(e.message);}});
 $('#profile-form').onsubmit=e=>{e.preventDefault();const fields=values(e.target),clear_fields=Object.keys(data.profile).filter(k=>k!=='weight_kg'&&k in data.fields&&!(k in fields));action({action:'profile',fields,clear_fields});};
 enhanceArchive(data,api,refresh,toast);
 $('#profile-form').insertAdjacentHTML('beforebegin','<button id="recover-profile" type="button">从历史回答查漏</button><p class="muted">只查找有明确原话依据、尚未入档的年龄、性别和身高，结果放到待核实区，由你确认。</p>');
 $('#recover-profile').onclick=async()=>{if(busy)return;try{await api('/api/work/action',{action:'recover_profile'});await refresh();view('archive');toast('查漏完成，请查看待核实区；没有明确依据的项目不会猜测补齐。');}catch(e){toast(e.message);}};
 document.querySelectorAll('[data-chat-detail]').forEach(detail=>{detail.open=chatDetailExpansion.get(detail.dataset.chatDetail)===true;});
 paintPending();
 syncImageReport();
 scheduleChatEnd();

}
function field(k,label,v=''){return `<label class="field">${esc(label)}<input name="${esc(k)}" value="${esc(Array.isArray(v)?v.join('，'):v??'')}" ${['age','height_cm','weight_kg'].includes(k)?'type="number" step="any"':''}></label>`;}
function values(form){return Object.fromEntries([...new FormData(form)].filter(([,v])=>v.trim()!==''));}
function renderForm(form){$('#intake').innerHTML=form?`<form class="card" id="intake-form"><h2>${esc(form.title)}</h2><p class="muted">全部选填。可以填表，也可以在下方用文字或语音回答。</p>${form.fields.map(f=>field(f.key,f.label,f.value)).join('')}<div class="actions"><button class="primary">保存并继续生成计划</button><button type="button" id="skip-intake">跳过，先给初步计划</button></div></form>`:'';if(form){$('#intake-form').onsubmit=e=>{e.preventDefault();send('已填写资料，请继续原来的计划请求。',{intake_values:values(e.target)});};$('#skip-intake').onclick=()=>send('暂时跳过资料，请给出初步计划。',{skip_intake:true});}}
async function refresh(){data=await api('/api/work/state');render();}
// Keep the composer in the visible viewport and reserve its real height in chat.
let composerLayoutFrame=0,viewportBaseline=innerHeight,viewportWidth=innerWidth,welcomeScrollConversation=null;
function scheduleComposerLayout(){if(!composerLayoutFrame)composerLayoutFrame=requestAnimationFrame(updateComposerLayout);}
function updateComposerLayout(){
 composerLayoutFrame=0;
 const composer=$('#composer'),chat=$('#chat'),root=document.documentElement;
 if(chat.hidden){document.body.classList.remove('chat-keyboard-open');return;}
 const viewport=window.visualViewport,visibleHeight=viewport?.height||innerHeight;
 if(Math.abs(innerWidth-viewportWidth)>80){viewportBaseline=innerHeight;viewportWidth=innerWidth;}
 viewportBaseline=Math.max(viewportBaseline,innerHeight);
 const keyboard=innerWidth<=760&&composer.contains(document.activeElement)&&viewportBaseline-visibleHeight>140;
 document.body.classList.toggle('chat-keyboard-open',keyboard);
 const bounds=chat.getBoundingClientRect(),nav=$('.sidebar nav');
 const navHeight=innerWidth<=760&&!keyboard?nav.getBoundingClientRect().height:0;
 const occluded=Math.max(0,innerHeight-visibleHeight-(viewport?.offsetTop||0));
 const bottom=occluded+navHeight+(innerWidth<=760?8:16);
 root.style.setProperty('--composer-left',bounds.left+'px');root.style.setProperty('--composer-width',bounds.width+'px');
 root.style.setProperty('--composer-bottom',bottom+'px');root.style.setProperty('--composer-max-height',Math.max(120,visibleHeight-navHeight-24)+'px');
 root.style.setProperty('--composer-height',composer.getBoundingClientRect().height+'px');
 scheduleChatEnd();
}
function paintLatestButton(){
 $('#chat-latest').hidden=followChatEnd||$('#chat').hidden||Boolean($('#messages [data-chat-welcome]')&&!pendingChat&&!$('#messages [data-chat-error]'));
}
function scheduleChatEnd(){
 paintLatestButton();
 if(!followChatEnd||$('#chat').hidden||chatScrollFrame)return;
 chatScrollFrame=requestAnimationFrame(()=>{
  chatScrollFrame=0;
  if(!followChatEnd||$('#chat').hidden||document.querySelector('dialog[open]'))return;
  // An empty chat has no latest message. Following its end anchor hides the
  // welcome title and new-chat controls behind the sticky header on phones.
  // Reset only when entering that empty conversation; polling must not undo
  // the user's own scroll through the starter cards.
  if($('#messages [data-chat-welcome]')&&!pendingChat&&!$('#messages [data-chat-error]')){
   if(welcomeScrollConversation!==cid){welcomeScrollConversation=cid;programmaticScrollUntil=performance.now()+120;window.scrollTo({top:0,behavior:'instant'});lastWindowScroll=scrollY;}
   return;
  }
  welcomeScrollConversation=null;
  // Measure after layout, using the actual input top, including viewport/keyboard changes.
  const end=$('#chat-end'),composer=$('#composer');
  const target=Math.max(0,scrollY+end.getBoundingClientRect().bottom-composer.getBoundingClientRect().top+16);
  if(Math.abs(target-scrollY)>1){programmaticScrollUntil=performance.now()+120;window.scrollTo({top:target,behavior:'instant'});}
  lastWindowScroll=scrollY;
 });
}
function scrollChatEnd(){
 followChatEnd=true;scheduleComposerLayout();scheduleChatEnd();
}
async function action(p){if(busy){toast('请等本次回复完成后再打卡或修改');return;}try{await api('/api/work/action',p);await refresh();toast('已保存');}catch(e){toast(e.message);}}
async function send(text,extra={}){
 if(busy||voiceBusy||!text.trim())return;busy=true;$('#send').disabled=true;$('#send').textContent='等待回复';$('#message').disabled=true;
 localStorage.setItem('zhiheng-session-v2',cid);const payload=retry&&retry.text===text&&retry.conversation_id===cid&&JSON.stringify(retry.plan_help||null)===JSON.stringify(extra.plan_help||null)?retry:{text,conversation_id:cid,client_message_id:crypto.randomUUID(),input_source:source,...extra};retry=payload;
 pendingChat={cid,text,stage:'reading',started:Date.now(),history:['reading']};$('#message').value='';scrollChatEnd();paintPending();
 const clock=setInterval(paintPending,1000);
 try{await chatStream(payload);retry=null;source='text';pendingChat=null;if(attachedConversation===payload.conversation_id){attachedMedia=null;attachedConversation=null;}await refresh();scheduleChatEnd();}
 catch(e){pendingChat=null;paintPending();$('#message').value=text;const message=e.name==='AbortError'?'等待超时，原文已保留，可以重试。':e.message;$('#messages').insertAdjacentHTML('beforeend',`<div class="bubble assistant" data-chat-error role="alert">${esc(message)}</div>`);toast(message);scheduleChatEnd();}
 finally{clearInterval(clock);busy=false;$('#send').disabled=false;$('#message').disabled=false;$('#send').textContent='发送';scheduleComposerLayout();}
}
$('#composer').onsubmit=e=>{e.preventDefault();if(voiceBusy){voiceInput.finish();return;}if(pendingAttachment){sendAttachment();return;}const photo=replyPhoto();send($('#message').value,photo?{media_id:photo.id}:{});};$('#new-chat').onclick=()=>{if(busy||voiceBusy){toast(voiceBusy?'请先完成或取消语音录入':'请等待本次回复完成');return;}if(pendingAttachment&&!confirm('当前有未发送图片，切换新对话会移除附件，继续吗？'))return;pendingAttachment=null;paintAttachment();cid=crypto.randomUUID();retry=null;attachedMedia=null;attachedConversation=null;localStorage.setItem('zhiheng-session-v2',cid);render();};
$('#export-chat').onclick=async()=>{
 if(!data?.conversations?.some(item=>item.id===cid&&item.messages?.length)){toast('当前对话还没有可导出的消息');return;}
 const exportId=cid;
 try{
  if(window.zhihengNativeExport?.conversation){window.zhihengNativeExport.conversation(exportId);return;}
  const exported=await api('/api/conversation-export?id='+encodeURIComponent(exportId));
  const day=(exported.created_at||new Date().toISOString()).slice(0,10);
  download(new Blob([JSON.stringify(exported,null,2)],{type:'application/json;charset=utf-8'}),`知衡-对话-${day}-${exportId.slice(0,8)}.json`);
  toast('本对话已导出。分享前请检查原话中的隐私信息。');
 }catch(error){toast('导出失败：'+error.message);}
};
document.querySelectorAll('[data-prompt]').forEach(b=>b.onclick=()=>send(b.dataset.prompt));$('#history-search').oninput=()=>render();
const voiceInput=setupVoice($('#message'),$('#voice'),$('#voice-cancel'),$('#voice-status'),v=>source=v);
window.addEventListener('zhiheng-voice-busy',event=>{
 voiceBusy=Boolean(event.detail?.busy);
 for(const id of ['photo','camera']){const button=$('#'+id);if(button)button.disabled=busy||voiceBusy;}
 $('#send').disabled=busy||(voiceBusy&&!event.detail?.canStop);
 $('#send').textContent=busy?'等待回复':voiceBusy?(event.detail?.canStop?'完成录入':'识别中…'):'发送';
 scheduleComposerLayout();
});
$('#message').addEventListener('input',scheduleComposerLayout);
let composing=false;
$('#message').addEventListener('compositionstart',()=>composing=true);
$('#message').addEventListener('compositionend',()=>composing=false);
$('#message').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing&&!composing&&e.keyCode!==229){e.preventDefault();if(!busy)$('#composer').requestSubmit();}});
$('#message').setAttribute('enterkeyhint','send');
$('#message').insertAdjacentHTML('afterend','<small class="muted composer-key-hint">回车发送 · Shift + 回车换行</small>');
$('#confirm-each').onchange=e=>action({action:'settings',confirm_each:e.target.checked});
function download(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('#export').onclick=async()=>{try{download(new Blob([JSON.stringify(await api('/api/export'),null,2)],{type:'application/json'}),'zhiheng-export.json');}catch(e){toast(e.message);}};
$('#backup').onclick=async()=>{try{const r=await fetch('/api/backup');if(!r.ok)throw Error('备份生成失败');download(await r.blob(),'zhiheng-backup.zip');}catch(e){toast(e.message);}};
$('#restore').onclick=()=>$('#restore-file').click();$('#restore-file').onchange=async e=>{const file=e.target.files[0];if(!file||!confirm('恢复将替换当前资料、计划和记录，确定继续？'))return;try{const r=await fetch('/api/restore',{method:'POST',headers:{'Content-Type':'application/zip','X-Zhiheng-Confirm':'restore'},body:file});if(!r.ok)throw Error('恢复失败');await refresh();toast('恢复完成');}catch(e){toast(e.message);}};
$('#reset').onclick=async()=>{if(confirm('清空应用数据？本机自动备份仍保留。')){await api('/api/reset',{confirm:true});await refresh();}};
$('#photo').onclick=()=>{if(busy){toast('请等待当前对话完成');return;}$('#photo-file').click();};
$('#photo').insertAdjacentHTML('afterend','<button id="camera" type="button">拍照</button><input id="camera-file" type="file" accept="image/jpeg" capture="environment" hidden>');
$('#camera').onclick=()=>{if(busy){toast('请等待当前对话完成');return;}$('#camera-file').click();};
$('#photo-category').insertAdjacentHTML('afterbegin','<option value="auto">自动识别类型</option>');$('#photo-category').value='auto';
$('#message').insertAdjacentHTML('beforebegin','<div id="pending-attachment" class="pending-attachment" hidden></div>');
function paintAttachment(){
 const root=$('#pending-attachment');root.hidden=!pendingAttachment;root.replaceChildren();$('#photo-options').hidden=!pendingAttachment;paintReplyPhoto();if(!pendingAttachment)return;
 const img=document.createElement('img');img.src=pendingAttachment.photo.data;img.alt='待发送附件';root.append(img);
 const detail=document.createElement('div');const title=document.createElement('strong');title.textContent=attachmentUploading?'正在发送照片…':'照片准备好了';detail.append(title);
 const note=document.createElement('p');note.textContent='图片将发送给已配置的 AI 服务。可以加一句问题再发送。';detail.append(note);root.append(detail);
 const remove=document.createElement('button');remove.type='button';remove.textContent='×';remove.setAttribute('aria-label','移除附件');remove.disabled=attachmentUploading;remove.onclick=()=>{pendingAttachment=null;paintAttachment();};root.append(remove);
}
async function sendAttachment(){
 if(busy||voiceBusy||!pendingAttachment)return;
 const attachment=pendingAttachment,context=$('#message').value.trim(),conversation=cid;
 const payload={...attachment.photo,category:$('#photo-category').value,context,background:true,client_job_id:attachment.id,
  followup:{conversation_id:conversation,text:context||'请帮我看看这张照片。'}};
 // A retry after an uncertain network result must use the identical payload.
 if(attachment.payload&&JSON.stringify({...payload,client_job_id:''})!==JSON.stringify({...attachment.payload,client_job_id:''})){
  toast('上次发送结果未确认，请保持原说明重试，避免重复上传。');return;
 }
 attachment.payload=payload;busy=true;attachmentUploading=true;$('#send').disabled=true;$('#photo').disabled=true;$('#camera').disabled=true;$('#message').disabled=true;paintAttachment();
 scrollChatEnd();
 try{
  const result=await api('/api/analyze-image',payload);
  pendingAttachment=null;paintAttachment();$('#message').value='';attachedMedia=null;attachedConversation=null;
  imageWatcher?.accept(result.job);await refresh().catch(()=>toast('照片已发送，正在恢复对话连接…'));scheduleChatEnd();
 }catch(error){toast('发送未完成，附件和说明已保留：'+imageError(error));}
 finally{busy=false;attachmentUploading=false;$('#send').disabled=false;$('#photo').disabled=false;$('#camera').disabled=false;$('#message').disabled=false;paintAttachment();}
}
$('#photo-file').onchange=async e=>{
 const file=e.target.files[0];if(!file)return;
 if(pendingAttachment&&!confirm('替换当前未发送附件？')){e.target.value='';return;}
 const category=$('#photo-category').value;
 busy=true;$('#send').disabled=true;$('#camera').disabled=true;$('#photo').disabled=true;
 let errorBox=$('#photo-upload-error');if(!errorBox){$('#composer').insertAdjacentHTML('beforebegin','<div id="photo-upload-error" class="card" role="alert" hidden></div>');errorBox=$('#photo-upload-error');}errorBox.hidden=true;
 try{
  toast('正在处理照片…');const photo=await prepareUpload(file,category);
  pendingAttachment={photo,name:file.name||'照片附件',id:crypto.randomUUID()};paintAttachment();if($('#toast').textContent==='正在处理照片…')$('#toast').hidden=true;$('#message').focus();
 }catch(error){errorBox.textContent='照片上传未完成：'+imageError(error);errorBox.hidden=false;toast(imageError(error));}
 finally{busy=false;$('#send').disabled=false;$('#camera').disabled=false;$('#photo').disabled=false;e.target.value='';}
};
$('#camera-file').onchange=$('#photo-file').onchange;
$('#messages').addEventListener('click',async e=>{
 const report=e.target.closest('[data-open-report]');if(report){openImageReport(report.dataset.openReport);return;}
 const retryImage=e.target.closest('[data-retry-image]');if(retryImage){retryImage.disabled=true;try{await imageWatcher.retry(retryImage.dataset.retryImage);}finally{retryImage.disabled=false;}return;}
 const discuss=e.target.closest('[data-discuss-photo]');if(discuss){window.dispatchEvent(new CustomEvent('discuss-media',{detail:{id:discuss.dataset.discussPhoto}}));return;}
 const photo=e.target.closest('[data-open-photo]');if(!photo)return;
 const dialog=document.createElement('dialog');dialog.className='chat-photo-viewer';
 dialog.innerHTML=`<button type="button" aria-label="关闭照片">关闭</button><img src="${photoUrl(photo.dataset.openPhoto)}" alt="照片大图">`;
 document.body.append(dialog);dialog.addEventListener('close',()=>dialog.remove());dialog.querySelector('button').onclick=()=>dialog.close();dialog.showModal();
});
new ResizeObserver(scheduleComposerLayout).observe($('#composer'));
new ResizeObserver(scheduleComposerLayout).observe($('.workspace main'));
new ResizeObserver(scheduleChatEnd).observe($('#messages'));
new ResizeObserver(scheduleChatEnd).observe($('#intake'));
window.addEventListener('scroll',()=>{
 const movingUp=scrollY<lastWindowScroll-2;lastWindowScroll=scrollY;
 if($('#chat').hidden||document.querySelector('dialog[open]')||performance.now()<programmaticScrollUntil)return;
 const gap=$('#chat-end').getBoundingClientRect().bottom-$('#composer').getBoundingClientRect().top;
 if(movingUp&&gap>80){followChatEnd=false;paintLatestButton();}
 else if(!followChatEnd&&gap<=32){followChatEnd=true;paintLatestButton();}
},{passive:true});
window.addEventListener('wheel',e=>{if(e.deltaY<0&&!$('#chat').hidden&&!document.querySelector('dialog[open]')){followChatEnd=false;paintLatestButton();}},{passive:true});
let chatTouchY=null;
window.addEventListener('touchstart',e=>{chatTouchY=e.touches[0]?.clientY??null;},{passive:true});
window.addEventListener('touchmove',e=>{const y=e.touches[0]?.clientY;if(chatTouchY!==null&&y-chatTouchY>4&&!$('#chat').hidden&&!document.querySelector('dialog[open]')){followChatEnd=false;paintLatestButton();}chatTouchY=y??null;},{passive:true});
$('#messages').addEventListener('load',scheduleChatEnd,true);
window.addEventListener('resize',scheduleComposerLayout);
window.visualViewport?.addEventListener('resize',scheduleComposerLayout);
window.visualViewport?.addEventListener('scroll',scheduleComposerLayout);
document.addEventListener('focusin',scheduleComposerLayout);document.addEventListener('focusout',scheduleComposerLayout);
scheduleComposerLayout();
imageWatcher=watchImageJobs(api,refresh,toast,state=>{imageJobs=state.jobs;imageSyncError=state.error;if(data)render();});
refresh().catch(e=>{$('#connection').textContent='数据连接失败';toast(e.message);});api('/api/config-status').then(c=>$('#model-status').textContent=c.enabled&&c.key_present?'模型已配置 · 当前资料与计划保存在本机':'模型未配置，暂时无法生成计划').catch(()=>{});
