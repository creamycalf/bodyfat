export function setupVoice(input,button,cancel,status,onSource,options={}){
  const limits={nativeAckTimeoutMs:10000,nativeResultTimeoutMs:180000,processingTimeoutMs:15000,browserTimeoutMs:60000,bridgeTimeoutMs:10000,...options};
  let active=null,sequence=0,destroyed=false;
  const events=[];
  const listen=(name,fn)=>{window.addEventListener?.(name,fn);events.push([name,fn]);};
  const inputChanged=()=>input.dispatchEvent?.(new Event('input',{bubbles:true}));
  const busy=value=>window.dispatchEvent?.(new CustomEvent('zhiheng-voice-busy',{detail:{busy:value,canStop:value&&Boolean(active?.canStop)}}));
  const current=session=>active===session&&!destroyed;
  function begin(kind){
    const session={kind,id:Date.now()+'-'+(++sequence),original:input.value,readOnly:input.readOnly,timers:new Set(),canStop:false};
    active=session;input.readOnly=true;cancel.hidden=false;button.disabled=true;busy(true);return session;
  }
  function timer(session,ms,fn){const id=setTimeout(()=>{session.timers.delete(id);if(current(session))fn();},ms);session.timers.add(id);return id;}
  function clearTimer(session,id){if(id!==undefined){clearTimeout(id);session.timers.delete(id);}}
  function reset(session){
    if(!current(session))return false;
    active=null;session.timers.forEach(clearTimeout);session.timers.clear();
    input.readOnly=session.readOnly;cancel.hidden=true;button.disabled=false;button.textContent='🎙 语音';busy(false);return true;
  }
  function cancelTransport(session){
    try{if(session.kind==='native')window.zhihengNativeVoice?.cancel();else session.rec?.abort();}catch{}
  }
  function fallback(message){
    status.textContent=message;
    const doc=status.ownerDocument;if(!doc)return;
    const entry=doc.createElement('button');entry.type='button';entry.textContent='使用输入法语音';entry.dataset.voiceKeyboard='';
    entry.onclick=()=>{if(input.disabled)return;input.focus?.();try{window.zhihengNativeVoice?.keyboard?.();}catch{}
      status.textContent='请点键盘上的麦克风说话。识别文字会留在输入框，核对后再发送。';};
    status.append(entry);
  }
  function fail(session,message,offerFallback=true){
    if(!current(session))return;input.value=session.original;inputChanged();reset(session);cancelTransport(session);
    if(offerFallback)fallback(message);else status.textContent=message;
  }
  function preview(session,text){
    session.text=String(text||'').trim();
    input.value=session.original+(session.original&&session.text?'\n':'')+session.text;inputChanged();
  }
  function recover(session,message){
    if(!current(session))return;
    if(!session.text){fail(session,message);return;}
    preview(session,session.text);reset(session);cancelTransport(session);onSource('voice');
    status.textContent=message+' 已保留已识别文字，请核对、修改后发送。';
  }
  function processing(session){
    session.stopping=true;session.canStop=false;button.disabled=true;button.textContent='正在完成录入…';
    status.textContent='正在完成识别，文字会留在输入框，核对后点发送。';busy(true);
    if(!session.processingTimer)session.processingTimer=timer(session,limits.processingTimeoutMs,()=>recover(session,'语音结束处理超时。'));
  }
  function finish(){
    const session=active;if(!session?.canStop)return;
    processing(session);
    try{if(session.kind==='native'){if(!window.zhihengNativeVoice?.stop)throw Error('stop unavailable');window.zhihengNativeVoice.stop();}else session.rec.stop();}
    catch{recover(session,'语音服务未能结束识别。');}
  }
  function nativeStart(session){
    if(!current(session))return;
    session.kind='native';clearTimer(session,session.bridgeTimer);
    button.textContent='正在打开语音…';status.textContent='正在准备中文语音。识别结果只填入草稿，核对后再发送。';
    session.ackTimer=timer(session,limits.nativeAckTimeoutMs,()=>fail(session,'手机语音服务没有响应，草稿已保留，可以重试。'));
    session.resultTimer=timer(session,limits.nativeResultTimeoutMs,()=>recover(session,'语音识别等待超时。'));
    try{window.zhihengNativeVoice.start(session.id);}catch{fail(session,'系统语音未能启动，可以重试或使用输入法语音。');}
  }
  listen('zhiheng-voice-ready',()=>{if(active?.kind==='bridge'&&window.zhihengNativeVoice)nativeStart(active);});
  listen('zhiheng-voice-state',event=>{
    const result=event.detail||{},session=active;
    if(!session||session.kind!=='native'||result.id!==session.id)return;
    clearTimer(session,session.ackTimer);
    if(session.stopping&&result.state!=='processing')return;
    session.canStop=result.canStop!==false&&result.state==='listening';button.disabled=!session.canStop;
    if(result.state==='listening'){
      if(result.text!==undefined)preview(session,result.text);
      button.textContent=session.canStop?'■ 完成录入':'系统语音识别中…';
      status.textContent=result.text?'文字已显示在输入框，停顿后会自动结束，也可以点“完成录入”。':result.engine==='offline'?'离线识别中，请说话。说完点“完成录入”，再核对发送。':'正在听… 说完可以点“完成录入”。';
      if(!session.canStop)status.textContent='请在手机系统语音窗口完成识别，文字会回到这里。';
    }else if(result.state==='processing'){processing(session);}
    else{button.textContent='正在打开语音…';status.textContent=result.engine==='offline'?'正在准备离线中文语音，首次使用需要解压模型，请稍等。':'正在准备麦克风，如出现权限提示请允许。';}
    busy(true);
  });
  listen('zhiheng-voice-result',event=>{
    const result=event.detail||{},session=active;
    if(!session||session.kind!=='native'||result.id!==session.id)return;
    if(result.cancelled){fail(session,'已取消，原有草稿已保留。',false);return;}
    if(result.error){recover(session,result.error);return;}
    const text=String(result.text||'').trim();
    if(!text&&session.text){recover(session,'未得到完整识别结果。');return;}
    preview(session,text);reset(session);
    if(text){onSource('voice');status.textContent='识别完成，请核对数字、单位和时间后发送。';}
    else status.textContent='没有识别到文字，请重试。';
  });
  button.onclick=()=>{
    if(destroyed||input.disabled)return;
    if(active){
      finish();return;
    }
    if(window.zhihengNativeVoice){nativeStart(begin('native'));return;}
    const androidWebView=window.zhihengNativeExpected||/ZhihengAndroid|Android.*;\s*wv\)/i.test(window.navigator?.userAgent||'');
    if(androidWebView){const session=begin('bridge');button.textContent='正在连接手机语音…';status.textContent='正在准备手机语音入口…';
      session.bridgeTimer=timer(session,limits.bridgeTimeoutMs,()=>fail(session,'手机语音入口暂未连接，请重开应用或使用输入法语音。'));return;}
    const Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;
    if(!Recognition){fallback('当前浏览器没有语音识别接口，可以使用键盘上的麦克风。');return;}
    if(window.isSecureContext===false){fallback('当前 HTTP 页面不能使用浏览器麦克风。请通过 HTTPS 或 localhost 打开，或使用输入法语音。');return;}
    const session=begin('browser');button.textContent='正在打开麦克风…';status.textContent='正在打开麦克风，请允许浏览器使用。';
    try{
      const rec=new Recognition();session.rec=rec;rec.lang='zh-CN';rec.interimResults=true;rec.continuous=false;
      rec.onstart=()=>{if(!current(session))return;session.canStop=true;button.disabled=false;button.textContent='■ 完成录入';status.textContent='正在听… 说完点完成录入，核对后再发送。';busy(true);};
      rec.onresult=event=>{if(!current(session))return;let text='';for(const row of event.results)text+=row[0].transcript;
        input.value=session.original+(session.original&&text?'\n':'')+text;inputChanged();session.text=text;};
      rec.onerror=event=>{if(!current(session))return;const messages={'not-allowed':'浏览器未允许麦克风。请在网站权限及系统隐私设置中允许后重试。','no-speech':'没有听到说话，请重试。','audio-capture':'未找到可用麦克风，请检查设备。','network':'语音服务连接失败，请检查网络后重试。','service-not-allowed':'当前浏览器不允许使用语音服务，可用输入法语音。','aborted':'语音识别已取消。'};
        fail(session,messages[event.error]||'语音识别失败，已有草稿已保留。');};
      rec.onend=()=>{if(!current(session))return;reset(session);if(session.text){onSource('voice');status.textContent='识别完成，请核对文字后发送。';}else status.textContent='没有识别到文字，请重试。';};
      timer(session,limits.browserTimeoutMs,()=>fail(session,'语音识别等待超时，草稿已保留，可以重试。'));rec.start();
    }catch{fail(session,'无法启动录音，请检查麦克风权限后重试。');}
  };
  cancel.onclick=()=>{if(active)fail(active,'已取消，原有草稿已保留。',false);};
  return {finish,destroy(){if(active){const session=active;reset(session);cancelTransport(session);}destroyed=true;
    events.forEach(([name,fn])=>window.removeEventListener?.(name,fn));button.onclick=null;cancel.onclick=null;}};
}
