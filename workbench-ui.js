const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const imageUrl = id => `/api/media/image?id=${encodeURIComponent(id)}`;
const range = pair => Array.isArray(pair) ? `${pair[0]}–${pair[1]}` : '待估算';
export function readableText(value){
 if(Array.isArray(value))return value.map(readableText).join('\n');
 let text=String(value??'').replace(/\\r\\n|\\n/g,'\n');
 if(/^\s*\[/.test(text)){
  try{const parsed=JSON.parse(text);if(Array.isArray(parsed))return parsed.map(readableText).join('\n');}catch{}
  if(/^\s*\['[\s\S]*'\]\s*$/.test(text))text=text.trim().slice(2,-2).split(/',\s*'/).join('\n');
 }
 return text;
}
export function prose(text){
 const inline=s=>escape(s).replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>');
 return readableText(text).split(/\n/).filter(line=>line.trim()&&!/^\s*([-*_])\1{2,}\s*$/.test(line)).map(line=>{
  if(/^#{1,6}\s/.test(line))return `<h3>${inline(line.replace(/^#{1,6}\s+/,''))}</h3>`;
  if(/^\s*[-*]\s/.test(line))return `<p class="module-point">${inline(line.replace(/^\s*[-*]\s+/,''))}</p>`;
  return `<p>${inline(line)}</p>`;
 }).join('');
}

export function readablePlan(p,options={}){
 const status={suggested:'待开始',active:'进行中',paused:'已暂停',completed:'已完成',replaced:'历史版本'};
 const unknowns=readableText(p.unknowns).split('\n').filter(Boolean);
 return `<article class="plan-card plan-document" id="plan-${escape(p.id)}-${p.version}">
 <div class="plan-overview"><div class="plan-meta"><span>${escape(status[p.status]||p.status)}</span><span>${escape(p.start_date)} — ${escape(p.end_date)}</span></div><h2>${escape(p.title)}</h2><div class="plan-goal">${prose(p.goal)}</div><div class="actions">${!options.history&&!['replaced','completed'].includes(p.status)?`<button class="primary" data-plan="${escape(p.id)}" data-version="${p.version}" data-status="${p.status==='active'?'paused':'active'}">${p.status==='active'?'暂停计划':'开始执行'}</button><button data-adjust="${escape(p.title)}">聊聊怎么调整</button>`:''}</div></div>
 ${p.changes?.length?`<div class="recent-adjustment"><strong>最近调整</strong><p>${escape([...new Set(p.changes.map(x=>{const match=x.label.match(/^第(\d+)项/);return match?p.items[Number(match[1])-1]?.title.split('：')[0]||x.label:x.label;}))].slice(0,4).join('、'))}已更新</p><small>${escape(p.created_at?.slice(0,16).replace('T',' '))} · 第 ${p.version} 版</small><details><summary>查看触发这次调整的对话</summary><p>${escape(readableText(p.reason))}</p></details></div>`:''}
 ${p.start_guide?.kind==='adaptive'&&p.start_date===options.today&&!options.history?`<section class="plan-footnote"><h3>可选的下一步</h3><ol>${p.start_guide.steps.map(step=>`<li>${escape(step)}</li>`).join('')}</ol><button data-talk="我想根据当前安排反馈执行情况或调整下一步。">反馈或调整</button></section>`:''}
 ${p.first_day_note?`<p class="plan-footnote">${escape(p.first_day_note)}</p>`:''}
 ${p.routine_basis&&Object.values(p.routine_basis).some(Boolean)?`<details class="plan-footnote"><summary>你的作息依据</summary>${Object.values(p.routine_basis).filter(Boolean).map(value=>prose(value)).join('')}</details>`:''}
 <details class="plan-footnote"><summary>行动依据与边界</summary>${p.items.map(item=>`<p><strong>${escape(item.title)}</strong>：${item.basis_record_ids?.length?`关联 ${item.basis_record_ids.length} 条记录（引用存在不代表因果已证实）`:'未关联事实记录，属于待反馈验证的建议'}。${escape(item.unknowns||'执行感受和适配程度仍需确认')}。${!item.alternatives?'暂无明确替代，可反馈困难后再讨论。':''}</p>`).join('')}</details>
 <div class="plan-sections">${p.items.map((item,n)=>{
 const content=readableText(item.detail),lines=content.split('\n').filter(x=>x.trim());
 const title=readableText(item.title).replace(/\*\*/g,'');
 const colon=title.indexOf('：');const label=colon>0?title.slice(0,colon):title;
 const subtitle=colon>0?title.slice(colon+1):'';
 return `<section class="plan-step"><span class="plan-number">${String(n+1).padStart(2,'0')}</span><div class="plan-step-content"><div class="plan-step-heading"><h3>${escape(label)}</h3><span>${escape(item.when)}</span></div>${subtitle?`<p class="plan-subtitle">${escape(subtitle)}</p>`:''}${item.problem?`<p class="plan-subtitle">先处理：${escape(readableText(item.problem))}</p>`:''}<div class="plan-instructions">${prose(lines[0]||'')}</div>${lines.length>1?`<details class="plan-expand"><summary>查看详细安排</summary><div class="plan-instructions">${prose(lines.slice(1).join('\n'))}</div></details>`:''}${options.mealChoices?options.mealChoices(item,p):''}${!options.history&&options.taskControls?(options.tasks||[]).filter(t=>t.plan_id===p.id&&t.version===p.version&&t.id===item.id).map(options.taskControls).join(''):''}${item.minimum?`<p class="plan-minimum">从这一步开始 · ${escape(readableText(item.minimum).replace(/\*\*/g,''))}</p>`:''}${item.alternatives||item.feedback||item.review_at?`<details class="plan-expand"><summary>做不到时怎么办与如何反馈</summary>${item.alternatives?`<p><strong>替代：</strong>${escape(readableText(item.alternatives))}</p>`:''}${item.feedback?`<p><strong>反馈：</strong>${escape(readableText(item.feedback))}</p>`:''}${item.review_at?`<p class="muted"><strong>复盘：</strong>${escape(readableText(item.review_at))}</p>`:''}</details>`:''}</div></section>`;
 }).join('')}</div>
 <details class="plan-footnote"><summary>制定依据与待了解事项</summary>${prose(p.basis)}${unknowns.length?`<h3>还需要了解</h3><ul>${unknowns.map(x=>`<li>${escape(x)}</li>`).join('')}</ul>`:''}<p class="muted">如出现明显不适，请停止相关活动并及时就医。计划用于日常管理，不替代诊断或处方。</p></details>
 ${p.changes?.length?`<details class="plan-footnote"><summary>查看本次调整 · 第 ${p.version} 版</summary>${p.changes.map(x=>`<div class="plan-change"><strong>${escape(x.label)}</strong><div>${prose(x.before??'未设置')}</div><span class="muted">调整为</span><div>${prose(x.after??'已移除')}</div></div>`).join('')}</details>`:''}
 ${p.basis_unavailable?.length?'<p class="basis-warning">部分制定依据已删除或停止用于后续回答，请重新核对计划。</p>':''}</article>`;
}

export function setupWorkbench() {
 if(!document.querySelector('#plan')){
  const section=document.createElement('section');section.id='plan';section.className='view';section.hidden=true;
  section.innerHTML='<div class="heading"><div><small>当前安排与更新依据</small><h1>我的计划</h1></div></div><div id="plan-content"></div>';
  document.querySelector('main').append(section);
 }
}

function trend(data) {
 const points=(data.dashboard.weight_series||[]).filter(p=>Number.isFinite(p.kg));
 if(points.length<2)return '<p class="muted">至少两次实际测量后显示趋势。</p>';
 const times=points.map(p=>new Date(p.date).getTime()),start=Math.min(...times),duration=Math.max(1,Math.max(...times)-start);
 const min=Math.min(...points.map(p=>p.kg)),max=Math.max(...points.map(p=>p.kg)),span=Math.max(.5,max-min);
 return `<svg viewBox="0 0 600 140" role="img" aria-label="按实际测量日期绘制的体重趋势"><polyline fill="none" stroke="#1d7961" stroke-width="3" points="${points.map((p,i)=>`${20+(times[i]-start)/duration*560},${20+(max-p.kg)/span*100}`).join(' ')}"/></svg><p class="muted">${escape(points[0].date.slice(0,10))} 至 ${escape(points.at(-1).date.slice(0,10))} · ${min}–${max} kg</p>`;
}

function moduleCard(m,data) {
 return `<article class="card dynamic-module" id="module-${escape(m.id)}"><span class="tag">${escape(m.page==='plan'?'方案更新':'持续跟进')} · v${m.version}</span><h2>${escape(m.title)}</h2>${m.type==='image'?`<img class="meal-photo" loading="lazy" src="${imageUrl(m.media_id)}" alt="${escape(m.title)}">`:''}<div class="module-body">${prose(m.body)}</div>${m.items?.length?`<ul>${m.items.map(x=>`<li>${prose(x)}</li>`).join('')}</ul>`:''}${m.type==='trend'?trend(data):''}<details><summary>为什么更新</summary><p>${escape(m.reason)}</p><p class="muted">${escape(m.updated_at?.slice(0,16).replace('T',' '))} · 来源：${escape(m.source?.text)}</p></details></article>`;
}

export function renderWorkbench(data,view,send) {
 document.querySelectorAll('#messages .page-save-note,#messages .chat-page-link').forEach(node=>node.remove());
 const activeId=localStorage.getItem('zhiheng-session-v2');
 const failures=(data.evaluation_jobs||[]).filter(x=>x.status==='failed'&&x.error!=='MODEL_MISSING_WORKBENCH_DECISION'&&x.conversation_id===activeId);
 for(const job of failures){
  const message=data.conversations.find(c=>c.id===activeId)?.messages.find(m=>m.result?.client_message_id===job.trigger_message_id);
  const bubble=message&&document.querySelector(`[data-message-id="${CSS.escape(message.id)}"]`);
  if(!bubble)continue;
  const note=document.createElement('div');note.className='page-save-note';
  if(job.kind==='chat'){
   if(message.result?.retry_chat)continue;
   const label=document.createElement('span');label.textContent=job.request_date!==data.today?'这条请求来自此前日期，请根据今天的情况重新说明。':'这次模型处理未完成，已保存的数据仍保留。';
   if(job.request_date!==data.today){note.append(label);bubble.append(note);continue;}
   const button=document.createElement('button');button.textContent='继续这次请求';
   button.onclick=()=>send('请继续这次未完成的请求。',{retry_chat:job.id});
   note.append(label,button);bubble.append(note);continue;
  }
  const label=document.createElement('span');label.textContent='这次的页面说明未保存，原有内容保留。';
  const button=document.createElement('button');button.textContent='恢复已保存资料的说明';
  button.onclick=()=>send('请恢复这段对话已保存资料的页面说明。',{retry_evaluation:true});
  note.append(label,button);bubble.append(note);
 }
 for(const page of ['plan','dashboard','archive']){
  const modules=(data.modules||[]).filter(m=>m.page===page&&!['saved-plan-summary','saved-profile-summary'].includes(m.id));
  if(modules.length)document.querySelector('#'+page+'-content').insertAdjacentHTML('beforeend','<details class="card supplementary"><summary>补充说明 · '+modules.length+'</summary>'+modules.map(m=>moduleCard(m,data)).join('')+'</details>');
 }
 for(const c of data.conversations)for(const m of c.messages){
  if(!m.result?.page_updates?.length)continue;
  const bubble=document.querySelector(`[data-message-id="${CSS.escape(m.id)}"]`);if(!bubble)continue;
  for(const change of m.result.page_updates){const b=document.createElement('button');b.className='chat-page-link';b.textContent='查看更新：'+change.title;b.onclick=()=>{view(change.page);document.getElementById('module-'+change.id)?.scrollIntoView({block:'center'});};bubble.append(b);}
 }
}
