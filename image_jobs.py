"""Persistent image analysis queue. Originals are saved before returning to the UI."""
import copy
import hashlib
import json
import re
import threading
import time
import uuid
import storage

_guard=threading.Lock()
_workers={}
TRANSIENT={'AI_TIMEOUT','AI_CONNECTION_FAILED','AI_BUSY','AI_UPSTREAM_UNAVAILABLE','AI_RATE_LIMITED','AI_INVALID_RESPONSE'}
AUTOMATIC_RETRY_MAX_ELAPSED_MS=30000

def public(job):
    value={k:copy.deepcopy(v) for k,v in job.items() if k not in ('payload','fingerprint')}
    # Restore the user's caption in the timeline without exposing upload bytes.
    value['message_text']=str((job.get('payload') or {}).get('context') or '请帮我看看这张照片。')[:2000]
    value['client_message_id']='image-job-'+job['id'][:64]
    return value

def submit(s,p):
    key=str(p.get('client_job_id') or uuid.uuid4().hex)
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',key):raise s.product.ProductError('任务标识无效')
    fingerprint=hashlib.sha256(json.dumps(p,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    followup=p.get('followup')
    if followup is not None:
        if not isinstance(followup,dict) or not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',str(followup.get('conversation_id',''))):
            raise s.product.ProductError('关联会话无效')
        if not isinstance(followup.get('text'),str) or not 1<=len(followup['text'])<=8000:
            raise s.product.ProductError('关联消息无效')
    with s.DATA_LOCK,storage.transaction(s.DATA):
        w=s.product.workspace(s);jobs=w.setdefault('image_jobs',{})
        if key in jobs:
            if jobs[key]['fingerprint']!=fingerprint:raise s.product.ProductError('相同任务标识不能提交不同图片',409)
            return {'ok':True,'job':public(jobs[key])}
        if sum(j['status'] in ('pending','running') for j in jobs.values())>=12:
            raise s.product.ProductError('等待分析的图片较多，请稍后再上传',429)
        item=s.analyze_image(p,prepare_only=True)
        # prepare_image may save media, but never overwrites this workspace snapshot.
        job={'id':key,'fingerprint':fingerprint,'media_id':item['id'],'status':'pending',
             'stage':'image','attempts':0,'created_at':s.product.now(),'updated_at':s.product.now(),
             'next_at':0,'payload':{'context':str(p.get('context',''))[:2000],'followup':followup},
             'conversation_id':(followup or {}).get('conversation_id'),'error':None}
        jobs[key]=job;s.save_json(s.DATA/'workspace.json',w)
    ensure_worker(s)
    return {'ok':True,'job':public(job)}

def list_jobs(s):
    with s.DATA_LOCK:return [public(j) for j in s.product.workspace(s).get('image_jobs',{}).values()][-50:]

def retry_job(s,key):
    with s.DATA_LOCK,storage.transaction(s.DATA):
        w=s.product.workspace(s);job=w.get('image_jobs',{}).get(key)
        if not job or job['status']!='failed':raise s.product.ProductError('该任务无需重试',409)
        job.update(status='pending',attempts=0,next_at=0,error=None,updated_at=s.product.now())
        s.save_json(s.DATA/'workspace.json',w)
    ensure_worker(s)
    return {'ok':True,'job':public(job)}

def recover(s):
    with s.DATA_LOCK,storage.transaction(s.DATA):
        w=s.product.workspace(s);changed=False
        for job in w.get('image_jobs',{}).values():
            if job['status']=='running':
                job['status']='pending' if job['attempts']<(3 if job['stage']=='followup' else 2) else 'failed'
                job['error']='分析被中断，已恢复待处理状态' if job['status']=='pending' else '分析多次中断，请手动重试'
                changed=True
        if changed:s.save_json(s.DATA/'workspace.json',w)

def update(s,key,**fields):
    with s.DATA_LOCK,storage.transaction(s.DATA):
        w=s.product.workspace(s);job=w.get('image_jobs',{}).get(key)
        if job is None:return False
        job.update(fields,updated_at=s.product.now());s.save_json(s.DATA/'workspace.json',w)
        return True

def run_one(s):
    with s.DATA_LOCK,storage.transaction(s.DATA):
        w=s.product.workspace(s)
        job=next((j for j in w.get('image_jobs',{}).values() if j['status']=='pending' and j.get('next_at',0)<=time.time()
                  and not (j['stage']=='followup' and s.product.chat_active(s))),None)
        if not job:return False
        job['status']='running';job['attempts']+=1;job['updated_at']=s.product.now()
        saved=copy.deepcopy(job);s.save_json(s.DATA/'workspace.json',w)
    key=saved['id'];payload=saved['payload']
    try:
        if saved['stage']=='image':
            result=s.analyze_image({'retry_id':saved['media_id'],'context':payload['context'],
                                    'conversation_id':saved.get('conversation_id')})
            error=result.get('ai_error')
            if error:
                # The transport already performs its own bounded retry. Do
                # not silently start another pair after a slow/exhausted
                # request; keep the photo and expose the manual retry action.
                transport_attempts=result.get('attempts') or 0
                elapsed_ms=result.get('elapsed_ms') or 0
                retry=(error in TRANSIENT and saved['attempts']<2 and transport_attempts<2
                       and elapsed_ms<AUTOMATIC_RETRY_MAX_ELAPSED_MS)
                update(s,key,status='pending' if retry else 'failed',error=error,next_at=time.time()+15)
                return True
            if not update(s,key,stage='followup',attempts=0,error=None):return True
        followup=payload.get('followup')
        if followup:
            # Reusing this ID after restart replays the saved receipt, not its writes.
            # A foreground answer must commit before this local publication.
            # Deferral is waiting, not failure, and consumes no retry budget.
            with s.DATA_LOCK:
                if s.product.chat_active(s):
                    update(s,key,status='pending',error=None,next_at=time.time()+1,
                           attempts=0 if saved['stage']=='image' else saved['attempts']-1)
                    return True
                answer=s.product.chat(s,{**followup,'media_id':saved['media_id'],
                    'client_message_id':'image-job-'+key[:64]},image_review_only=True)
            errors=[answer.get(k) for k in ('ai_error','page_error','food_error','workflow_warning') if answer.get(k)]
            update(s,key,status='partial' if errors else 'succeeded',error=','.join(errors) or None,
                   result={'conversation_id':answer['conversation_id'],'client_message_id':answer['client_message_id']})
        else:update(s,key,status='succeeded',error=None)
    except Exception as error:
        transient=isinstance(error,s.product.ProductError) and error.status==409
        retry=transient and saved['attempts']<3
        update(s,key,status='pending' if retry else 'failed',error=type(error).__name__,next_at=time.time()+5)
        s.log_event('image_job_failed',job_id=key,exception=type(error).__name__)
    return True

def ensure_worker(s):
    path=str(s.DATA.resolve())
    with _guard:
        if path in _workers and _workers[path].is_alive():return
        recover(s)
        def loop():
            while True:
                try:run_one(s)
                except Exception as error:s.log_event('image_worker_error',exception=type(error).__name__)
                time.sleep(1)
        thread=threading.Thread(target=loop,daemon=True,name='image-jobs')
        _workers[path]=thread;thread.start()
