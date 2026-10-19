package cn.zhiheng.mobile;

import android.app.Instrumentation;
import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

/** Runs against the signed release Activity. No debug server or test hooks in APK. */
public class SmokeInstrumentation extends Instrumentation {
    MainActivity activity;
    String stage;
    @Override public void onCreate(Bundle args){super.onCreate(args);stage=args.getString("stage","first");start();}
    String js(String script)throws Exception{
        CountDownLatch done=new CountDownLatch(1);AtomicReference<String> value=new AtomicReference<>();
        runOnMainSync(()->activity.web.evaluateJavascript(script,r->{value.set(r);done.countDown();}));
        if(!done.await(15,TimeUnit.SECONDS))throw new Exception("JS timed out");return value.get();
    }
    void until(String script)throws Exception{
        for(int i=0;i<600;i++){if("true".equals(js(script)))return;Thread.sleep(200);}throw new Exception("Check timed out: "+script);
    }
    void check(String script)throws Exception{String value=js(script);if(!"true".equals(value))throw new Exception("Check failed: "+script+" => "+value);}
    void checkpoint(String text){Bundle status=new Bundle();status.putString("stream",text+"\n");sendStatus(0,status);}
    void tap(String selector)throws Exception{
        org.json.JSONArray position=new org.json.JSONArray(js("(()=>{const r=document.querySelector("+org.json.JSONObject.quote(selector)+").getBoundingClientRect();return [r.left+r.width/2,r.top+r.height/2,innerWidth];})()"));
        int[] screen=new int[2];AtomicReference<Float> scale=new AtomicReference<>();
        runOnMainSync(()->{activity.web.getLocationOnScreen(screen);scale.set((float)activity.web.getWidth()/(float)position.optDouble(2));});
        float x=screen[0]+(float)position.getDouble(0)*scale.get(),y=screen[1]+(float)position.getDouble(1)*scale.get();
        long time=android.os.SystemClock.uptimeMillis();
        android.view.MotionEvent down=android.view.MotionEvent.obtain(time,time,android.view.MotionEvent.ACTION_DOWN,x,y,0);
        android.view.MotionEvent up=android.view.MotionEvent.obtain(time,time+50,android.view.MotionEvent.ACTION_UP,x,y,0);
        try{sendPointerSync(down);sendPointerSync(up);}finally{down.recycle();up.recycle();}
    }
    void cameraContract()throws Exception{
        check("document.querySelector('#camera-file').capture==='environment' && document.querySelector('#camera').textContent==='拍照'");
        for(boolean success:new boolean[]{true,false}){
            CountDownLatch done=new CountDownLatch(1);AtomicReference<android.net.Uri[]> received=new AtomicReference<>();
            ActivityMonitor monitor=new ActivityMonitor(){
                @Override public ActivityResult onStartActivity(Intent i){
                    if(!android.provider.MediaStore.ACTION_IMAGE_CAPTURE.equals(i.getAction()))return null;
                    android.net.Uri uri=i.getParcelableExtra(android.provider.MediaStore.EXTRA_OUTPUT);
                    if(success)try(java.io.OutputStream stream=getTargetContext().getContentResolver().openOutputStream(uri)){
                        android.graphics.Bitmap bitmap=android.graphics.Bitmap.createBitmap(16,16,android.graphics.Bitmap.Config.ARGB_8888);
                        bitmap.eraseColor(android.graphics.Color.GREEN);bitmap.compress(android.graphics.Bitmap.CompressFormat.JPEG,90,stream);bitmap.recycle();
                    }catch(Exception e){throw new RuntimeException(e);}
                    return new ActivityResult(success?Activity.RESULT_OK:Activity.RESULT_CANCELED,null);
                }
            };
            addMonitor(monitor);
            try{
                runOnMainSync(()->{activity.chooser=uris->{received.set(uris);done.countDown();};activity.capturePhoto();});
                if(!done.await(10,TimeUnit.SECONDS))throw new Exception("Camera callback timeout");
                if(success?(received.get()==null||received.get().length!=1):received.get()!=null)throw new Exception("Camera callback mismatch");
                if(success)try(java.io.InputStream in=getTargetContext().getContentResolver().openInputStream(received.get()[0])){if(in.read()!=255)throw new Exception("Full JPEG unavailable");}
            }finally{removeMonitor(monitor);}
        }
        try{getTargetContext().getContentResolver().openFileDescriptor(android.net.Uri.parse("content://cn.zhiheng.mobile.camera/../config.json"),"r");throw new Exception("Camera path traversal accepted");}
        catch(java.io.FileNotFoundException expected){}
    }
    void pickerContract()throws Exception{
        check("document.querySelector('#photo-file').accept.includes('image/jpeg')");
        java.io.File dir=new java.io.File(getTargetContext().getCacheDir(),"camera");dir.mkdirs();
        java.io.File fixture=new java.io.File(dir,java.util.UUID.randomUUID().toString()+".jpg");
        android.net.Uri uri=android.net.Uri.parse("content://"+getTargetContext().getPackageName()+".camera/"+fixture.getName());
        try{
            try(java.io.OutputStream stream=new java.io.FileOutputStream(fixture)){
                android.graphics.Bitmap bitmap=android.graphics.Bitmap.createBitmap(16,16,android.graphics.Bitmap.Config.ARGB_8888);
                bitmap.eraseColor(android.graphics.Color.BLUE);bitmap.compress(android.graphics.Bitmap.CompressFormat.JPEG,90,stream);bitmap.recycle();
            }
            for(boolean success:new boolean[]{true,false}){
                CountDownLatch opened=new CountDownLatch(1);
                ActivityMonitor monitor=new ActivityMonitor(){
                    @Override public ActivityResult onStartActivity(Intent i){
                        if(!Intent.ACTION_OPEN_DOCUMENT.equals(i.getAction()))return null;
                        if(!"image/*".equals(i.getType()))throw new IllegalStateException("Picker MIME changed");
                        opened.countDown();
                        return new ActivityResult(success?Activity.RESULT_OK:Activity.RESULT_CANCELED,
                            success?new Intent().setData(uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION):null);
                    }
                };
                addMonitor(monitor);
                try{
                    tap("#photo");
                    if(!opened.await(10,TimeUnit.SECONDS))throw new Exception("Image picker did not open");
                    if(success){
                        until("!document.querySelector('#pending-attachment').hidden");
                        check("document.querySelector('#message').value==='输入法测试草稿'");
                        js("document.querySelector('#pending-attachment [aria-label=\"移除附件\"]').click()");
                    }
                    check("document.querySelector('#pending-attachment').hidden && document.querySelector('#message').value==='输入法测试草稿'");
                }finally{removeMonitor(monitor);}
            }
        }finally{fixture.delete();}
    }
    String voiceSession()throws Exception{
        js("window.qaNativeVoiceSession=null;document.querySelector('#voice').click()");
        until("typeof window.qaNativeVoiceSession==='string'");
        String id=(String)new org.json.JSONTokener(js("window.qaNativeVoiceSession")).nextValue();
        runOnMainSync(()->activity.voiceId=id);return id;
    }
    void offlineModelContract()throws Exception{
        // Exercise the shipped Android JNI and the production model unpacker.
        // This isolated controller never starts AudioRecord or opens a microphone.
        OfflineVoiceInput controller=new OfflineVoiceInput(getTargetContext());
        try{
            Class<?> sessionClass=Class.forName("cn.zhiheng.mobile.OfflineVoiceInput$Session");
            java.lang.reflect.Constructor<?> constructor=sessionClass.getDeclaredConstructor(int.class,OfflineVoiceInput.Listener.class);constructor.setAccessible(true);
            OfflineVoiceInput.Listener listener=new OfflineVoiceInput.Listener(){public void state(String s,String t){}public void result(String t,String e,String c){}public void unavailable(){}};
            Object session=constructor.newInstance(0,listener);
            java.lang.reflect.Field active=OfflineVoiceInput.class.getDeclaredField("active");active.setAccessible(true);active.set(controller,session);
            java.lang.reflect.Method prepare=OfflineVoiceInput.class.getDeclaredMethod("prepareModel",sessionClass);prepare.setAccessible(true);
            java.io.File modelPath=(java.io.File)prepare.invoke(controller,session);
            StringBuilder transcript=new StringBuilder();
            try(org.vosk.Model model=new org.vosk.Model(modelPath.getAbsolutePath());
                org.vosk.Recognizer recognizer=new org.vosk.Recognizer(model,16000f);
                java.io.InputStream source=getContext().getAssets().open("synthetic-cn.pcm")){
                byte[] pcm=new byte[3200];int count;
                while((count=source.read(pcm))!=-1){
                    if(recognizer.acceptWaveForm(pcm,count))transcript.append(new org.json.JSONObject(recognizer.getResult()).optString("text"));
                }
                transcript.append(new org.json.JSONObject(recognizer.getFinalResult()).optString("text"));
            }
            String recognized=transcript.toString().replace(" ","");int matched=0;
            for(String keyword:new String[]{"苹果","牛奶","散步","三十分钟"})if(recognized.contains(keyword))matched++;
            if(matched<3)throw new Exception("Offline synthetic Chinese decode failed: "+recognized);
            checkpoint("PASS Android native offline Chinese model: "+recognized+"; synthetic PCM fixture, no microphone, no network, keyword checks="+matched+"/4");
        }finally{controller.destroy();}
    }
    void mobileInputContract()throws Exception{
        // This stage must run on a freshly created, disposable app data image.
        // Refuse even an accidental invocation against existing personal data.
        js("fetch('/api/work/state').then(r=>r.json()).then(s=>window.qaBefore=s)");
        until("Boolean(window.qaBefore)");
        check("window.qaBefore.records.length===0 && Object.keys(window.qaBefore.profile).length===0 && window.qaBefore.media.length===0 && window.qaBefore.conversations.every(c=>!c.messages.length)");
        if(!activity.nativeVoice.available())throw new Exception("Bundled offline voice model unavailable");
        until("Boolean(window.zhihengNativeVoice)");
        js("window.qaOriginalVoiceBridge=window.zhihengNativeVoice;window.zhihengNativeVoice={start:id=>window.qaNativeVoiceSession=id,stop:()=>window.qaStopped=true,cancel:()=>window.qaCancelled=true,keyboard:()=>window.qaOriginalVoiceBridge.keyboard()};document.querySelector('#message').value='语音测试草稿'");
        try{
            voiceSession();
            runOnMainSync(()->activity.voiceState("preparing","",false));
            until("document.querySelector('#voice-status').textContent.includes('离线中文语音')");
            runOnMainSync(()->activity.voiceState("listening","今天体重",true));
            until("document.querySelector('#message').value==='语音测试草稿\\n今天体重'");
            check("document.querySelector('#message').readOnly && !document.querySelector('#voice').disabled");
            js("document.querySelector('#voice').click()");
            check("window.qaStopped===true");
            runOnMainSync(()->activity.voiceResult("今天体重72公斤","",false,""));
            until("document.querySelector('#message').value==='语音测试草稿\\n今天体重72公斤' && !document.querySelector('#message').readOnly");
            js("document.querySelector('#message').value='取消测试草稿'");
            voiceSession();
            runOnMainSync(()->activity.voiceState("listening","不应保留的临时文字",true));
            until("document.querySelector('#message').value.includes('临时文字')");
            js("document.querySelector('#voice-cancel').click()");
            check("document.querySelector('#message').value==='取消测试草稿' && !document.querySelector('#message').readOnly");
            runOnMainSync(()->activity.cancelVoice());
            voiceSession();
            runOnMainSync(()->activity.voiceResult("","离线语音测试失败，草稿保留",false,"VOICE_OFFLINE_ERROR"));
            until("Boolean(document.querySelector('[data-voice-keyboard]'))");
            check("document.querySelector('#message').value==='取消测试草稿'");
            checkpoint("PASS mobile voice bridge: synthetic offline state/partial/final, stop, cancel and error preserve draft; no microphone audio was used");
            js("document.querySelector('#message').value='输入法测试草稿'");
            cameraContract();pickerContract();
            checkpoint("PASS mobile image: synthetic full JPEG capture/cancel/provider isolation and actual picker touch/select/cancel preserve draft; nothing uploaded");
            tap("[data-voice-keyboard]");
            until("document.activeElement===document.querySelector('#message')");
            boolean keyboard=false;AtomicReference<String> keyboardDetails=new AtomicReference<>("");
            for(int i=0;i<50&&!keyboard;i++){
                AtomicReference<Boolean> shown=new AtomicReference<>(false);
                runOnMainSync(()->{
                    android.view.View root=activity.getWindow().getDecorView();
                    android.graphics.Rect visible=new android.graphics.Rect();root.getWindowVisibleDisplayFrame(visible);
                    android.view.inputmethod.InputMethodManager input=(android.view.inputmethod.InputMethodManager)activity.getSystemService(android.content.Context.INPUT_METHOD_SERVICE);
                    keyboardDetails.set("decor="+root.getHeight()+",visible="+visible.bottom+",web="+activity.web.getHeight()+",focus="+activity.web.hasWindowFocus()+",imeActive="+(input!=null&&input.isActive(activity.web)));
                    if(android.os.Build.VERSION.SDK_INT>=30&&root.getRootWindowInsets()!=null)
                        shown.set(root.getRootWindowInsets().isVisible(android.view.WindowInsets.Type.ime()));
                    else{
                        shown.set(root.getHeight()-visible.bottom>activity.dp(100));
                    }
                });
                keyboard=shown.get();if(!keyboard)Thread.sleep(100);
            }
            if(!keyboard){
                // Distinguish a broken IME/host configuration from an app
                // fallback problem using a real native EditText, no user data.
                AtomicReference<android.app.AlertDialog> probe=new AtomicReference<>();
                runOnMainSync(()->{
                    android.widget.EditText input=new android.widget.EditText(activity);
                    input.setSingleLine(true);input.setText("键盘环境测试");
                    android.app.AlertDialog dialog=new android.app.AlertDialog.Builder(activity).setView(input).create();
                    probe.set(dialog);dialog.show();input.requestFocus();
                    dialog.getWindow().setSoftInputMode(android.view.WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_VISIBLE);
                    input.postDelayed(()->((android.view.inputmethod.InputMethodManager)activity.getSystemService(android.content.Context.INPUT_METHOD_SERVICE)).showSoftInput(input,android.view.inputmethod.InputMethodManager.SHOW_FORCED),200);
                });
                Thread.sleep(1500);
                AtomicReference<String> nativeDetails=new AtomicReference<>();
                runOnMainSync(()->{
                    android.view.View root=probe.get().getWindow().getDecorView();
                    android.graphics.Rect visible=new android.graphics.Rect();root.getWindowVisibleDisplayFrame(visible);
                    nativeDetails.set("decor="+root.getRootView().getHeight()+",visible="+visible.bottom+",screen="+activity.getResources().getDisplayMetrics().heightPixels);
                    probe.get().dismiss();
                });
                throw new Exception("Soft keyboard did not become visible: "+keyboardDetails.get()+"; native probe "+nativeDetails.get());
            }
            check("(()=>{const r=document.querySelector('#message').getBoundingClientRect();return r.top>=0 && r.bottom<=innerHeight+1 && document.querySelector('#message').value==='输入法测试草稿';})()");
            runOnMainSync(()->((android.view.inputmethod.InputMethodManager)activity.getSystemService(android.content.Context.INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(activity.web.getWindowToken(),0));
            js("fetch('/api/work/state').then(r=>r.json()).then(s=>window.qaAfter=s)");
            until("Boolean(window.qaAfter)");
            check("window.qaAfter.records.length===0 && window.qaAfter.conversations.every(c=>!c.messages.length)");
        }finally{
            runOnMainSync(()->activity.cancelVoice());
            js("window.zhihengNativeVoice=window.qaOriginalVoiceBridge;document.querySelector('#message').value=''");
        }
    }
    void welcomeContinuityContract(boolean sendMessage)throws Exception{
        js("window.qaBefore=null;fetch('/api/work/state').then(r=>r.json()).then(s=>window.qaBefore=s)");
        until("Boolean(window.qaBefore)");
        check("window.qaBefore.records.length===1 && window.qaBefore.records[0].type==='weight' && window.qaBefore.records[0].value.kg===72 && Object.keys(window.qaBefore.profile).length===0");
        js("window.qaOriginalRecords=JSON.stringify(window.qaBefore.records);document.querySelector('#new-chat').click()");
        until("Boolean(document.querySelector('[data-chat-welcome]'))");
        check("(()=>{const top=document.querySelector('.workspace>header').getBoundingClientRect().bottom,bottom=document.querySelector('#composer').getBoundingClientRect().top;const cards=[...document.querySelectorAll('.chat-starters button')];return cards.length===4&&cards.every(c=>{const r=c.getBoundingClientRect();return r.height>=44&&r.width>=44&&r.top>=top&&r.bottom<=bottom-8;});})()");
        checkpoint("PASS welcome: all four entry cards are visible above the composer with 44px targets, preserving the existing fictional 72kg record");
        if(!sendMessage)return;
        String unique="这是0.4.43界面验收。请用一句话说明食物照片如何帮助决定份量，不要保存任何健康资料。";
        js("document.querySelector('#message').value="+org.json.JSONObject.quote(unique)+";document.querySelector('#message').addEventListener('keydown',e=>window.qaEnterEvent={key:e.key,keyCode:e.keyCode,isComposing:e.isComposing},{once:true})");
        tap("#message");
        check("document.activeElement===document.querySelector('#message')");
        sendKeyDownUpSync(android.view.KeyEvent.KEYCODE_ENTER);
        Thread.sleep(500);
        checkpoint("Enter diagnostic: "+js("JSON.stringify({event:window.qaEnterEvent,value:document.querySelector('#message').value,sending:document.querySelector('#send').disabled,thinking:Boolean(document.querySelector('.thinking-status'))})"));
        until("document.querySelector('#message').value==='' || Boolean(document.querySelector('.thinking-status'))");
        until("!document.querySelector('#send').disabled && !document.querySelector('.thinking-status')");
        js("window.qaAfter=null;fetch('/api/work/state').then(r=>r.json()).then(s=>window.qaAfter=s)");
        until("Boolean(window.qaAfter)");
        check("JSON.stringify(window.qaAfter.records)===window.qaOriginalRecords");
        check("(()=>{const cid=localStorage.getItem('zhiheng-session-v2'),c=window.qaAfter.conversations.find(c=>c.id===cid),m=c?.messages||[],last=m[m.length-1];return m.some(x=>x.role==='user'&&x.text.includes('这是0.4.43界面验收'))&&last?.role==='assistant'&&last.result?.ai_status==='connected'&&!last.result?.ai_error;})()");
        checkpoint("PASS continuity: a real Android Enter key sent a unique fictional consultation, the remote model replied, and the prior 72kg record is unchanged with no duplicate");
    }
    @Override public void onStart(){
        Bundle result=new Bundle();
        try{
            Intent intent=new Intent(getTargetContext(),MainActivity.class);intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            activity=(MainActivity)startActivitySync(intent);
            until("document.querySelector('#connection')?.textContent==='数据已连接'");
            check("location.hostname==='127.0.0.1' && !document.body.textContent.includes('连接设置')");
            check("!document.cookie.includes('zhiheng_local') && typeof crypto.randomUUID==='function'");
            if("welcome".equals(stage)||"continuity".equals(stage)){
                welcomeContinuityContract("continuity".equals(stage));result.putString("stream","PASS "+stage+": upgraded release keeps old fictional data and a usable first screen\n");finish(Activity.RESULT_OK,result);return;
            }else if("offline-model".equals(stage)){
                offlineModelContract();result.putString("stream","PASS Android offline model JNI smoke (synthetic audio, not a microphone/accuracy test)\n");finish(Activity.RESULT_OK,result);return;
            }else if("mobile-input".equals(stage)){
                mobileInputContract();
                result.putString("stream","PASS mobile-input: real WebView/Java voice events with synthetic transcript (no microphone recognition), cancel/error draft recovery, soft keyboard visibility/layout, synthetic camera/gallery selection and cancellation; no model requests or records\n");finish(Activity.RESULT_OK,result);return;
            }else if("embedded".equals(stage)){
                cameraContract();
                String bundled=activity.assetText("engine/default_model.json");
                if(!new org.json.JSONObject(activity.config).getJSONObject("ai").getString("base_url").equals(new org.json.JSONObject(bundled).getJSONObject("ai").getString("base_url")))throw new Exception("Endpoint migration failed");
                com.chaquo.python.Python.getInstance().getModule("mobile_runtime").callAttr("configure",bundled);
                String connection=com.chaquo.python.Python.getInstance().getModule("mobile_runtime").callAttr("check_connection").toString();
                if(!new org.json.JSONObject(connection).optBoolean("ok"))throw new Exception("Connection probe: "+connection);
                if(!activity.config.contains("api_key"))throw new Exception("Embedded config missing");
                js("document.querySelector('#message').value='我今天体重72公斤，请只记录这条体重，不要制定计划';document.querySelector('#message').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));");
                until("!document.querySelector('#send').disabled");
                js("fetch('/api/work/state').then(r=>r.json()).then(s=>window.qaState=s)");
                until("window.qaState?.records.some(r=>r.type==='weight'&&r.value.kg===72)");
                check("(()=>{const cid=localStorage.getItem('zhiheng-session-v2');const messages=window.qaState.conversations.find(c=>c.id===cid).messages;const r=messages[messages.length-1].result;return r?.ai_status==='connected'&&!r?.ai_error;})()");
                result.putString("stream","PASS embedded: Enter send, camera JPEG/cancel/provider isolation, connected model response and local persistence\n");finish(Activity.RESULT_OK,result);return;
            }else if("first".equals(stage)){
                js("document.querySelector('#message').value='今天体重72公斤';document.querySelector('#composer').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));");
                until("!document.querySelector('#send').disabled && document.querySelector('#messages').textContent.includes('72')");
                js("fetch('/api/work/state').then(r=>r.json()).then(s=>window.qaState=s)");
                until("window.qaState?.records.some(r=>r.type==='weight'&&r.value.kg===72)");
                js("fetch('/api/backup').then(r=>r.arrayBuffer()).then(b=>window.qaBackup=Array.from(new Uint8Array(b).slice(0,2)))");
                until("window.qaBackup?.[0]===80 && window.qaBackup?.[1]===75");
                for(String page:new String[]{"plan","dashboard","archive"}){
                    js("document.querySelector('nav [data-view=\""+page+"\"]').click()");
                    check("!document.querySelector('#"+page+"').hidden");
                }
                // Exercise native configuration encryption without sending any model request.
                runOnMainSync(()->activity.applyConfig("{\"base_url\":\"https://example.com/v1\",\"model\":\"qa-only\",\"api_key\":\"synthetic-test-key\"}"));
                for(int i=0;i<100&&!activity.config.contains("qa-only");i++)Thread.sleep(100);
                if(!activity.readConfig().contains("synthetic-test-key"))throw new Exception("Encrypted config readback failed");
                String ciphertext=getTargetContext().getSharedPreferences("standalone",0).getString("model","");
                if(ciphertext.contains("synthetic-test-key")||ciphertext.contains("example.com"))throw new Exception("Config stored as plaintext");
            }else{
                if(!activity.config.contains("synthetic-test-key"))throw new Exception("Model configuration did not survive restart");
                js("fetch('/api/work/state').then(r=>r.json()).then(s=>window.qaState=s)");
                until("window.qaState?.records.filter(r=>r.type==='weight'&&r.value.kg===72).length===1");
                runOnMainSync(()->activity.applyConfig("{}"));
                for(int i=0;i<100&&activity.config.contains("synthetic-test-key");i++)Thread.sleep(100);
            }
            result.putString("stream","PASS standalone "+stage+": local engine, authenticated page, offline record, persistence, encrypted settings\n");finish(Activity.RESULT_OK,result);
        }catch(Throwable e){result.putString("stream","FAIL: "+e.toString()+"\n");finish(Activity.RESULT_CANCELED,result);}
    }
}
