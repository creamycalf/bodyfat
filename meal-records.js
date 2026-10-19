import {nutritionInfo} from './nutrition-info.js';
import {recordDay,recordDateText} from './health-pages.js';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pair=v=>Array.isArray(v)?esc(v.join('–')):'待核实';
function summary(r){return r?`${esc(recordDateText(r))}<p>${esc(r.value?.description||'饮食记录')}</p><p>热量 ${pair(r.value?.nutrition?.kcal)} kcal · 蛋白质 ${pair(r.value?.nutrition?.protein_g)} g · 碳水 ${pair(r.value?.nutrition?.carbs_g)} g · 脂肪 ${pair(r.value?.nutrition?.fat_g)} g</p>${nutritionInfo(r)}`:'撤回这餐摄入；保留原图和修正历史。';}

export function enhanceMeals(data,api,refresh,toast){
 const root=document.querySelector('#archive-content');
 function open(record){
  document.querySelector('.meal-editor')?.remove();
  const dialog=document.createElement('dialog');dialog.className='meal-editor';
  dialog.innerHTML=`<form><h2>核对这餐</h2><p class="muted">请核对日期、餐食和原图，确认选中的是要修改的记录。</p>${record.media_id?`<img class="meal-photo" alt="所选餐食原图" src="/api/media/image?id=${encodeURIComponent(record.media_id)}">`:''}<div class="meal-before">${summary(record)}</div><label>处理方式<select name="operation"><option value="edit">修正日期、内容或份量</option><option value="remove">其实没吃，撤回这餐摄入</option></select></label><div class="meal-fields"><label>实际用餐日期<input name="date" type="date" required value="${esc(recordDay(record))}"></label><label>实际吃了什么、多少<textarea name="description" required maxlength="2000">${esc(record.value?.description||'')}</textarea></label><label>营养估算<select name="nutrition_mode"><option value="unknown">食物或份量有变化，标为待核实</option><option value="keep">只改日期或文字，保留原估算</option><option value="scale">同样食物，按原记录份量换算</option></select></label><label class="factor-field" hidden>相对于修正前记录的倍数<input name="factor" type="number" min="0.01" max="4" step="0.01" value="0.5"><small>0.5 表示原记录的一半；没有原估算的营养仍保持未知。</small></label></div><div class="actions"><button type="submit">预览修改</button><button type="button" data-close>取消</button></div><section class="meal-diff" hidden aria-live="polite"></section><p class="meal-error" role="alert"></p></form>`;
  document.body.append(dialog);dialog.showModal();
  const form=dialog.querySelector('form'),diff=dialog.querySelector('.meal-diff'),error=dialog.querySelector('.meal-error');let draft=null;
  const close=()=>{dialog.close();dialog.remove();};dialog.querySelector('[data-close]').onclick=close;dialog.addEventListener('cancel',()=>dialog.remove());
  form.addEventListener('input',()=>{draft=null;diff.hidden=true;});
  form.addEventListener('change',()=>{const removal=form.elements.operation.value==='remove';dialog.querySelector('.meal-fields').hidden=removal;form.elements.date.required=!removal;form.elements.description.required=!removal;dialog.querySelector('.factor-field').hidden=form.elements.nutrition_mode.value!=='scale';});
  form.onsubmit=async e=>{e.preventDefault();error.textContent='';const button=form.querySelector('[type=submit]');button.disabled=true;
   const payload={id:record.id,operation:form.elements.operation.value,date:form.elements.date.value,description:form.elements.description.value,nutrition_mode:form.elements.nutrition_mode.value,factor:Number(form.elements.factor.value)};
   try{const preview=await api('/api/work/action',{action:'meal_preview',...payload});draft={...payload,token:preview.token};diff.innerHTML=`<h3>修改前</h3>${summary(preview.before)}<h3>修改后</h3>${summary(preview.after)}<button type="button" class="primary" data-commit>确认保存这次修改</button>`;diff.hidden=false;
    diff.scrollIntoView({block:'nearest'});
    diff.querySelector('[data-commit]').onclick=async event=>{if(!draft)return;event.currentTarget.disabled=true;try{await api('/api/work/action',{action:'meal_commit',...draft});close();await refresh();toast('这餐已更新，可在档案的餐食修正历史中撤销');}catch(err){error.textContent=err.message;draft=null;diff.hidden=true;}};
   }catch(err){error.textContent=err.message;}finally{button.disabled=false;}
  };
 }
 for(const button of root.querySelectorAll('[data-delete-record]')){
  const r=data.records.find(x=>x.id===button.dataset.deleteRecord);if(!['meal','beverage'].includes(r?.type))continue;
  button.textContent='核对 / 修正这餐';button.onclick=()=>open(r);button.dataset.mealEdit=r.id;
 }
 const finder=document.createElement('details');finder.className='card meal-finder';finder.innerHTML='<summary>查找与修正餐食</summary><label>用餐日期<input type="date" data-meal-date></label><label>餐食关键词<input type="search" data-meal-search placeholder="例如：午餐、米饭、咖啡"></label><div data-meal-results></div>';
 const renderResults=()=>{const day=finder.querySelector('[data-meal-date]').value,query=finder.querySelector('[data-meal-search]').value.trim();const results=finder.querySelector('[data-meal-results]');results.replaceChildren();
  for(const r of [...data.records].reverse().filter(r=>['meal','beverage'].includes(r.type)&&(!day||recordDay(r)===day)&&(!query||String(r.value?.description||'').includes(query)))){
   const row=document.createElement('div');row.className='item';row.innerHTML=summary(r);const button=document.createElement('button');button.textContent='核对 / 修正这餐';button.dataset.mealEdit=r.id;button.onclick=()=>open(r);row.append(button);results.append(row);
  }if(!results.children.length)results.textContent='没有符合条件的餐食记录。';
 };finder.addEventListener('input',renderResults);renderResults();root.prepend(finder);
 document.querySelectorAll('#dashboard-content .meal-record').forEach((row,i)=>{const record=data.food_summary?.records?.[i];if(!record)return;const button=document.createElement('button');button.textContent='核对 / 修正这餐';button.dataset.mealEdit=record.id;button.onclick=()=>open(record);row.append(button);});
 const card=document.createElement('details');card.className='card meal-corrections';card.innerHTML='<summary>餐食修正历史</summary>';
 for(const entry of [...(data.meal_corrections||[])].reverse()){
  const row=document.createElement('div');row.className='item';row.innerHTML=`<p>${esc(entry.created_at)} · ${entry.undone?'已撤销':'已保存'}</p><details><summary>${esc(entry.before.value?.description||'饮食记录')}</summary><h4>修改前</h4>${summary(entry.before)}<h4>修改后</h4>${summary(entry.after)}</details>`;
  if(!entry.undone){const button=document.createElement('button');button.textContent='撤销这次餐食修正';button.onclick=async()=>{button.disabled=true;try{await api('/api/work/action',{action:'meal_undo',correction_id:entry.id});await refresh();toast('已恢复修正前的餐食记录');}catch(e){toast(e.message);button.disabled=false;}};row.append(button);}card.append(row);
 }
 if(!(data.meal_corrections||[]).length)card.insertAdjacentHTML('beforeend','<p class="muted">暂无修正。展开实际健康记录，找到具体餐次后点击“核对 / 修正这餐”。</p>');
 root.append(card);
}
