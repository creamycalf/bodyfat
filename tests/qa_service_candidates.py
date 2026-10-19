"""Compare service aliases using identical synthetic conversations, no user data."""
import concurrent.futures
import json
import os
from pathlib import Path
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
MODELS=('claude-opus-4-8','claude-opus-5','claude-sonnet-5','claude-fable-5')
SYSTEM='你是一个自然交流的营养管理助手。先接住本轮需求，不急着建档或制定计划。只依据明确事实，不推断诊断、血糖或代谢状态。不复问拒答内容。用2至4个短句回应，必要时最多问一个问题。不要说已经保存资料。'
CASES=[
 ('first',[{'role':'user','content':'我现在88公斤，想瘦一点，但以前一做计划就坚持不下来，先聊聊行吗？'}]),
 ('correction',[
  {'role':'user','content':'我38岁，172厘米，性别暂时不想说。晚上九点下班，到家很饿，只能叫外卖。'},
  {'role':'assistant','content':'可以先不说性别。你九点到家之前，上一餐通常几点吃？'},
  {'role':'user','content':'不是，九点是下班，十点才到家。午餐十二点吃，下午没吃东西。别急着安排，我只想知道为什么饿。'}]),
 ('ownership',[
  {'role':'user','content':'性别不想说，先聊晚餐。'},
  {'role':'assistant','content':'好。你刚才提到的午餐米饭是你自己吃的吗？'},
  {'role':'user','content':'那个饭是同事吃的，我自己吃的面。先别给方案，也别再问性别。只回应这次更正。'}]),
]

def main():
 ai=json.loads((ROOT/'config.json').read_text('utf-8'))['ai']
 key=os.environ.get(ai.get('api_key_env','ZHIHENG_AI_API_KEY'),'')
 if not key:raise SystemExit('Configured environment key missing')
 output=ROOT/'tmp/service-candidates.json'
 results=[]
 def call(model,case,messages,structured):
  system=SYSTEM
  if structured:system+=' 只返回合法JSON：{"reply":"回复","profile_changes":[],"plan":null}。profile_changes仅包含本轮本人明确事实，使用field、value、evidence；evidence必须是本轮原文。'
  body={'model':model,'messages':[{'role':'system','content':system},*messages],'max_tokens':1200}
  req=urllib.request.Request('http://47.110.38.211:8080/v1/chat/completions',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
  start=time.monotonic()
  row={'model':model,'case':case,'structured':structured}
  try:
   with urllib.request.urlopen(req,timeout=65) as response:data=json.load(response)
   choice=data['choices'][0];raw=choice['message']['content']
   row.update(raw=raw,reported_model=data.get('model'),finish_reason=choice.get('finish_reason'))
   if structured:
    cleaned=raw.strip()
    if cleaned.startswith('```'):cleaned=cleaned.split('\n',1)[1].rsplit('```',1)[0].strip()
    try:row['parsed']=json.loads(cleaned);row['json_valid']=True
    except (ValueError,TypeError):row['json_valid']=False
  except Exception as error:row['error']=type(error).__name__
  row['elapsed_seconds']=round(time.monotonic()-start,2)
  return row
 # Three in-flight calls, bounded synthetic input; no automatic retries.
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  futures=[pool.submit(call,model,case,messages,structured) for model in MODELS for case,messages in CASES for structured in (False,True)]
  for future in concurrent.futures.as_completed(futures):
   row=future.result();results.append(row)
   output.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
   print(json.dumps({k:v for k,v in row.items() if k not in ('raw','parsed')},ensure_ascii=False),flush=True)
 print('Saved '+str(output),flush=True)

if __name__=='__main__':main()
