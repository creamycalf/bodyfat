// Job updates feed the conversation timeline. No separate task dashboard.
export function watchImageJobs(api,refresh,toast,onChange){
 const known=new Map(),accepted=new Map();let jobs=[],polling=false,refreshPending=false,lastPublished='',revision=0;
 function publish(error=''){
  const state={jobs,error},signature=JSON.stringify(state);
  if(signature!==lastPublished){lastPublished=signature;onChange(state);}
 }
 async function poll(){
  if(polling)return;polling=true;const started=revision;
  try{
   const result=await api('/api/work/image-jobs');jobs=result.jobs||[];
   // A poll started before an upload/retry response must not erase that response.
   for(const [id,item] of accepted){if(item.revision>started)jobs=[...jobs.filter(job=>job.id!==id),item.job];else accepted.delete(id);}
   for(const job of jobs){
    const signature=JSON.stringify([job.status,job.stage,job.error,job.result]);
    if(known.get(job.id)!==signature&&['succeeded','partial'].includes(job.status))refreshPending=true;
    known.set(job.id,signature);
   }
   for(const id of known.keys())if(!jobs.some(job=>job.id===id))known.delete(id);
   publish();
   if(refreshPending){await refresh();refreshPending=false;}
  }catch(error){publish(refreshPending?'图片已处理，正在重新读取回复…':'图片状态暂时无法更新，正在重连…');}
  finally{polling=false;}
 }
 const timer=setInterval(poll,3000);poll();
 return {poll,stop:()=>clearInterval(timer),
  accept(job){if(!job)return;accepted.set(job.id,{job,revision:++revision});jobs=[...jobs.filter(item=>item.id!==job.id),job];publish();},
  async retry(id){try{const result=await api('/api/work/image-jobs/retry',{id});this.accept(result.job);await poll();}catch(error){toast(error.message);}}
 };
}

// Completed jobs and saved messages share a key, keeping each image in the
// original sending position even if a newer text turn finished first.
export function conversationTurns(messages,jobs,cid){
 const related=jobs.filter(job=>job.conversation_id===cid);
 const jobMessage=job=>job.result?.client_message_id||job.client_message_id||'image-job-'+job.id.slice(0,64);
 const matched=new Set(),turns=[];
 for(let i=0;i<messages.length;i++){
  const user=messages[i];
  if(user.role!=='user'){turns.push({key:user.id,user:null,assistant:user,at:user.created_at,index:i});continue;}
  const assistant=messages[i+1]?.role==='assistant'?messages[++i]:null;
  const job=related.find(item=>jobMessage(item)===user.id);if(job)matched.add(job.id);
  turns.push({key:user.id,user,assistant,job,at:job?.created_at||user.created_at,index:i});
 }
 for(const job of related)if(!matched.has(job.id))turns.push({key:jobMessage(job),job,user:null,assistant:null,at:job.created_at,index:messages.length+turns.length});
 return turns.sort((a,b)=>{
  const first=Date.parse(a.at),second=Date.parse(b.at);
  return Number.isFinite(first)&&Number.isFinite(second)&&first!==second?first-second:a.index-b.index;
 });
}
