const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function nutritionInfo(record){
 const value=record?.value||{},context=value.nutrition_context||{};
 const known=Object.values(value.nutrition||{}).some(v=>v!==null&&v!==undefined);
 const labels={conversation_estimate:'根据本次餐食描述估算',image_estimate:'根据图片及食用说明估算',scaled:'按原记录份量换算',unknown:'营养尚未估算'};
 const label=known?(labels[context.method]||'历史估算，详细依据未记录'):'营养尚未估算';
 return `<div class="nutrition-evidence"><p class="muted">${esc(label)} · ${known?'准确程度未校准':'未知不按零计入'}</p>${context.basis?`<p class="muted">依据：${esc(context.basis)}</p>`:''}<p class="muted">${esc(value.uncertainty|| (known?'份量、品牌和烹调用油可能影响结果。':'可补充食物重量、包装标签或实际食用量后核实。'))}</p></div>`;
}
export function nutritionCoverage(total,compact=false){
 if(!total)return '';
 if(compact)return `${total.estimated_count||0} 条已估算 / ${total.unknown_count||0} 条未知`;
 return `${total.estimated_count||0} 条已估算 · ${total.unknown_count||0} 条未知${total.unknown_count?'，合计仅含已估算部分':''}`;
}
export function recipePortion(option,mode='cook'){
 return `<p class="muted recipe-portion">份量：${esc(option?.servings||'份数未说明，请核对后使用')}${mode==='cook'?`<br>重量口径：${esc(option?.weight_basis||'生熟重量未说明，请核对')}`:''}<br>参考建议，不代表已确定的个人摄入目标。</p>`;
}
