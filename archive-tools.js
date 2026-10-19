import {enhanceMeals} from './meal-records.js';
const MEDIA_TYPES={food:'饮食照片',report:'检查报告',general:'一般图片'};
const VALUE_LABELS={kg:'体重（kg）',cm:'围度（cm）',hours:'时长（小时）',name:'项目名称',value:'数值',unit:'单位',reference_range:'参考范围',date:'日期',description:'内容',time:'时间',amount:'数量',calorie_range:'热量范围'};

function appendCandidate(review,candidate,index){
 const box=document.createElement('fieldset'),legend=document.createElement('legend'),check=document.createElement('input');
 box.className='candidate';box.dataset.candidateRow=String(index);check.type='checkbox';check.checked=true;check.dataset.candidate=String(index);
 legend.append(check,document.createTextNode(` ${candidate.label||candidate.type}`));box.append(legend);
 for(const [key,value] of Object.entries(candidate.value||{})){
  const label=document.createElement('label'),input=document.createElement('input'),kind=typeof value;
  label.className='candidate-field';label.textContent=VALUE_LABELS[key]||key;input.dataset.valueKey=key;
  if(kind==='number'){input.type='number';input.step='any';input.dataset.valueType='number';input.value=String(value);}
  else if(kind==='boolean'){input.dataset.valueType='boolean';input.value=value?'是':'否';}
  else if(value&&kind==='object'){input.dataset.valueType='json';input.value=JSON.stringify(value);}
  else{input.dataset.valueType='string';input.value=value==null?'':String(value);}
  input.setAttribute('aria-label',`${candidate.label||candidate.type}的${VALUE_LABELS[key]||key}`);label.append(input);box.append(label);
 }
 review.append(box);
}

function reviewedRecords(review,candidates){
 return [...review.querySelectorAll('[data-candidate]:checked')].map(check=>{
  const candidate=candidates[Number(check.dataset.candidate)],box=check.closest('[data-candidate-row]'),value={};
  for(const input of box.querySelectorAll('[data-value-key]')){
   let field=input.value;
   if(input.dataset.valueType==='number'){field=Number(field);if(!Number.isFinite(field))throw new Error(`${input.getAttribute('aria-label')}不是有效数字`);}
   else if(input.dataset.valueType==='boolean')field=/^(是|true|1)$/i.test(field.trim());
   else if(input.dataset.valueType==='json'){try{field=JSON.parse(field);}catch{throw new Error(`${input.getAttribute('aria-label')}格式不正确`);}}
   value[input.dataset.valueKey]=field;
  }
  return {type:candidate.type,value};
 });
}

export function enhanceArchive(data,api,refresh,toast){
 enhanceMeals(data,api,refresh,toast);
 const root=document.querySelector('#archive-content'),card=document.createElement('details'),heading=document.createElement('summary');
 card.className='card';heading.textContent='原始图片与执行记录';card.append(heading);
 for(const media of data.media||[]){
  const row=document.createElement('div'),title=document.createElement('p');row.className='item';
  title.textContent=`${MEDIA_TYPES[media.type]||'图片'} · ${media.confirmed?'已保留':'待确认保留'} · ${Math.round((media.bytes||0)/1024)} KB`;row.append(title);
  const preview=document.createElement('img');preview.className='meal-photo';preview.src='/api/media/image?id='+encodeURIComponent(media.id);preview.alt=MEDIA_TYPES[media.type]||'原图';preview.loading='lazy';row.append(preview);
  if(media.analysis_error||!(media.review?.record_candidates?.length)){const retry=document.createElement('button');retry.textContent='重新分析原图';retry.onclick=async()=>{retry.disabled=true;retry.textContent='正在提交…';try{await api('/api/analyze-image',{retry_id:media.id,background:true,client_job_id:crypto.randomUUID()});toast('已安排后台重试，可在对话页查看进度');}catch(error){toast(error.message);}finally{retry.disabled=false;retry.textContent='重新分析原图';}};row.append(retry);}
  if(media.food_pending){const approve=document.createElement('button');approve.textContent='确认这份实际食用记录';approve.onclick=async()=>{try{await api('/api/work/action',{action:'food_confirm',id:media.id});await refresh();}catch(error){toast(error.message);}};row.append(approve);}
  if(media.type==='food'){const p=document.createElement('p');p.className='muted';p.textContent=media.review?.summary||'可回到对话补充这张照片的情况。';row.append(p);const discuss=document.createElement('button');discuss.textContent='在对话中说明这张照片';discuss.onclick=()=>window.dispatchEvent(new CustomEvent('discuss-media',{detail:{id:media.id}}));row.append(discuss);}
  if(media.type!=='food'&&media.review_status==='pending'&&media.review){
   const review=document.createElement('form'),summary=document.createElement('p'),candidates=media.review.record_candidates||[];
   review.className='image-review';summary.textContent=media.review.summary||'请核对识别结果';review.append(summary);
   if(media.review.question){const q=document.createElement('p');q.className='muted';q.textContent=media.review.question;review.append(q);}
   candidates.forEach((candidate,index)=>appendCandidate(review,candidate,index));
   const save=document.createElement('button');save.className='primary';save.textContent=candidates.length?'确认所选记录并保留原图':'确认已核对并保留原图';review.append(save);
   review.onsubmit=async event=>{event.preventDefault();try{await api('/api/media/review',{id:media.id,records:reviewedRecords(review,candidates),confirm:true});await refresh();toast('图片核对结果已保存');}catch(error){toast(error.message);}};
   row.append(review);
  }
  for(const [label,path] of [['仅保留原图','confirm'],['删除原图','delete']]){
   const button=document.createElement('button');button.textContent=label;
   button.onclick=async()=>{if(path==='delete'&&!confirm('删除这张原图？'))return;try{await api('/api/media/'+path,{id:media.id,confirm:true});await refresh();}catch(error){toast(error.message);}};row.append(button);
  }
  card.append(row);
 }
 const statuses={done:'完成',partial:'部分完成',skipped:'跳过',deferred:'延期',unreported:'撤回反馈'};
 for(const f of [...data.feedback].reverse().slice(0,30)){
  const p=document.createElement('p'),[id,version,itemId,date]=f.task_id.split(':'),plan=data.plans.find(x=>x.id===id&&String(x.version)===version),item=plan?.items.find(x=>x.id===itemId);
  p.className='muted';p.textContent=`${date} · ${item?.title||'计划事项'} · ${statuses[f.status]||f.status}${f.deferred_to?' → '+f.deferred_to:''}${f.note?' · '+f.note:''}`;card.append(p);
 }
 if(!data.media.length&&!data.feedback.length){const p=document.createElement('p');p.className='muted';p.textContent='暂无原图和执行反馈';card.append(p);}root.append(card);
 for(const button of root.querySelectorAll('[data-delete-record]')){
  const record=data.records.find(r=>r.id===button.dataset.deleteRecord),memory=document.createElement('button');memory.textContent=record.memory_enabled===false?'允许用于后续回答':'不用于后续回答';
  memory.onclick=async()=>{try{await api('/api/records/memory',{id:record.id,enabled:record.memory_enabled===false});await refresh();}catch(error){toast(error.message);}};button.after(memory);
  if(['weight','sleep'].includes(record.type)){
   const edit=document.createElement('button');edit.textContent='修正数值';edit.onclick=()=>{
    const key=record.type==='weight'?'kg':'hours',form=document.createElement('form'),input=document.createElement('input'),save=document.createElement('button');input.type='number';input.step='0.1';input.value=record.value[key];input.setAttribute('aria-label',record.type==='weight'?'体重公斤':'睡眠小时');save.textContent='保存修正';form.append(input,save);edit.replaceWith(form);
    form.onsubmit=async event=>{event.preventDefault();try{await api('/api/records/update',{id:record.id,record:{value:{...record.value,[key]:Number(input.value)}}});await refresh();}catch(error){toast(error.message);}};
   };memory.after(edit);
  }
 }

}
