package cn.zhiheng.mobile;

import android.app.*;
import android.Manifest;
import android.content.*;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.view.inputmethod.InputMethodManager;
import android.webkit.*;
import android.widget.*;
import android.text.InputType;
import android.security.keystore.*;
import android.util.Base64;
import com.chaquo.python.*;
import com.chaquo.python.android.AndroidPlatform;
import org.json.JSONObject;
import java.io.*;
import java.net.URL;
import java.net.HttpURLConnection;
import java.security.KeyStore;
import java.util.concurrent.*;
import javax.crypto.*;
import javax.crypto.spec.GCMParameterSpec;

public class MainActivity extends Activity {
    static final int PICK=7, IMPORT=8, SAVE=9, CAPTURE=10, AUDIO_PERMISSION=11, VOICE=12;
    Uri cameraUri;
    static final String KEY_ALIAS="zhiheng_model_config";
    final ExecutorService worker=Executors.newSingleThreadExecutor();
    WebView web; TextView status; Button aiButton;
    String origin="",cookie="",config="{}";
    ValueCallback<Uri[]> chooser;
    PermissionRequest pendingWebPermission;
    String voiceId=null;
    boolean voicePermissionPending=false;
    OfflineVoiceInput nativeVoice;
    File pendingExport;
    boolean ready=false;
    int dp(int n){return (int)(getResources().getDisplayMetrics().density*n);}
    void toast(String text){runOnUiThread(()->Toast.makeText(this,text,Toast.LENGTH_LONG).show());}

    @Override public void onCreate(Bundle state){
        super.onCreate(state);getWindow().setStatusBarColor(0xff177c6e);
        LinearLayout root=new LinearLayout(this);root.setOrientation(1);setContentView(root);
        LinearLayout bar=new LinearLayout(this);
        status=new TextView(this);status.setText("正在打开手机本地资料…");status.setPadding(dp(12),dp(4),dp(4),dp(4));bar.addView(status,new LinearLayout.LayoutParams(0,-2,1));
        aiButton=new Button(this);aiButton.setText("AI 设置");aiButton.setEnabled(false);aiButton.setOnClickListener(v->settings());bar.addView(aiButton);root.addView(bar);
        nativeVoice=new OfflineVoiceInput(this);
        web=new WebView(this);root.addView(web,new LinearLayout.LayoutParams(-1,0,1));
        WebSettings s=web.getSettings();s.setUserAgentString(s.getUserAgentString()+" ZhihengAndroid");s.setJavaScriptEnabled(true);s.setDomStorageEnabled(true);s.setAllowFileAccess(false);s.setAllowContentAccess(true);s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        CookieManager.getInstance().setAcceptCookie(true);CookieManager.getInstance().setAcceptThirdPartyCookies(web,false);
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView v,WebResourceRequest r){
                Uri u=r.getUrl();
                if("zhiheng-export".equals(u.getScheme())&&r.isForMainFrame()&&sameOrigin(v.getUrl())){export(u.getHost(),u.getQueryParameter("id"));return true;}
                if("zhiheng-voice".equals(u.getScheme())&&r.isForMainFrame()&&sameOrigin(v.getUrl())){
                    if("start".equals(u.getHost()))startVoice(u.getQueryParameter("id"));
                    if("cancel".equals(u.getHost()))cancelVoice();
                    if("stop".equals(u.getHost()))nativeVoice.stop();
                    if("keyboard".equals(u.getHost()))showVoiceKeyboard();
                    return true;
                }
                return !sameOrigin(u.toString());
            }
            @Override public WebResourceResponse shouldInterceptRequest(WebView v,WebResourceRequest r){
                String scheme=r.getUrl().getScheme();
                if(("http".equals(scheme)||"https".equals(scheme))&&!sameOrigin(r.getUrl().toString()))return new WebResourceResponse("text/plain","UTF-8",403,"Blocked",null,new ByteArrayInputStream(new byte[0]));
                return null;
            }
            @Override public void onPageFinished(WebView v,String url){
                if(!sameOrigin(url))return;CookieManager.getInstance().flush();
                v.evaluateJavascript("window.zhihengNativeVoice={start:id=>{location.href='zhiheng-voice://start?id='+encodeURIComponent(id)},stop:()=>{location.href='zhiheng-voice://stop'},cancel:()=>{location.href='zhiheng-voice://cancel'},keyboard:()=>{location.href='zhiheng-voice://keyboard'}};window.dispatchEvent(new Event('zhiheng-voice-ready'));",null);
                v.evaluateJavascript("window.zhihengNativeExport={conversation:id=>{location.href='zhiheng-export://conversation?id='+encodeURIComponent(id)}};",null);
                v.evaluateJavascript("(()=>{for(const [id,kind] of [['export','json'],['backup','backup']]){const b=document.getElementById(id);if(b)b.onclick=()=>{location.href='zhiheng-export://'+kind;};}})()",null);
            }
            @Override public void onReceivedError(WebView v,WebResourceRequest r,WebResourceError e){if(r.isForMainFrame())status.setText("本地页面未打开，请退出后重新打开应用");}
        });
        web.setWebChromeClient(new WebChromeClient(){
            @Override public void onPermissionRequest(PermissionRequest request){runOnUiThread(()->{
                if(!sameOrigin(request.getOrigin().toString())||!sameOrigin(web.getUrl())){request.deny();return;}
                boolean audio=false;for(String resource:request.getResources())if(PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(resource))audio=true;
                if(!audio){request.deny();return;}
                if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)==PackageManager.PERMISSION_GRANTED)request.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
                else if(pendingWebPermission!=null||voiceId!=null)request.deny();
                else{pendingWebPermission=request;requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO},AUDIO_PERMISSION);}
            });}
            @Override public void onPermissionRequestCanceled(PermissionRequest request){if(pendingWebPermission==request)pendingWebPermission=null;}
            @Override public boolean onShowFileChooser(WebView v,ValueCallback<Uri[]> callback,FileChooserParams p){
                if(!sameOrigin(v.getUrl()))return false;if(chooser!=null)chooser.onReceiveValue(null);chooser=callback;
                if(p.isCaptureEnabled()){capturePhoto();return true;}
                Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT);i.addCategory(Intent.CATEGORY_OPENABLE);String[] types=p.getAcceptTypes();i.setType(types.length>0&&types[0].startsWith("image")?"image/*":"*/*");
                try{startActivityForResult(i,PICK);}catch(ActivityNotFoundException e){chooser.onReceiveValue(null);chooser=null;toast("未找到系统文件选择器");}return true;
            }
            @Override public boolean onJsAlert(WebView v,String u,String t,JsResult r){new AlertDialog.Builder(MainActivity.this).setMessage(t).setPositiveButton("确定",(d,w)->r.confirm()).setOnCancelListener(d->r.cancel()).show();return true;}
            @Override public boolean onJsConfirm(WebView v,String u,String t,JsResult r){new AlertDialog.Builder(MainActivity.this).setMessage(t).setPositiveButton("确定",(d,w)->r.confirm()).setNegativeButton("取消",(d,w)->r.cancel()).setOnCancelListener(d->r.cancel()).show();return true;}
            @Override public boolean onJsPrompt(WebView v,String u,String t,String val,JsPromptResult r){EditText input=new EditText(MainActivity.this);input.setText(val);new AlertDialog.Builder(MainActivity.this).setMessage(t).setView(input).setPositiveButton("确定",(d,w)->r.confirm(input.getText().toString())).setNegativeButton("取消",(d,w)->r.cancel()).setOnCancelListener(d->r.cancel()).show();return true;}
        });
        worker.execute(()->{
            try{
                File engine=new File(getFilesDir(),"engine");if(!engine.isDirectory()&&!engine.mkdirs())throw new IOException();
                for(String name:getAssets().list("engine")){if(name.equals("default_model.json"))continue;try(InputStream in=getAssets().open("engine/"+name);OutputStream out=new FileOutputStream(new File(engine,name))){copy(in,out);}}
                File oldBundledConfig=new File(engine,"default_model.json");if(oldBundledConfig.exists())oldBundledConfig.delete();
                boolean configError=false;try{
                    String bundled=null;try{bundled=assetText("engine/default_model.json");}catch(FileNotFoundException absent){}
                    // A package upgrade can leave an unreadable Android Keystore
                    // value behind. Do not start with an empty AI config in that
                    // case; fall back to this package's embedded test config.
                    try{config=readConfig();}catch(Exception unreadable){
                        config="{}";
                        getSharedPreferences("standalone",0).edit().remove("model").commit();
                    }
                    JSONObject savedAi=new JSONObject(config).optJSONObject("ai");
                    if(!getSharedPreferences("standalone",0).getBoolean("endpoint_migration_v6",false)){
                        if(bundled!=null){JSONObject next=new JSONObject(bundled);String endpoint=next.getJSONObject("ai").optString("base_url");
                            String previous=savedAi==null?"":savedAi.optString("base_url");
                            if(endpoint.startsWith("http://47.110.38.211:8080/")&&(previous.isEmpty()||previous.equals("https://www.vibecd.cc/v1"))){
                                storeConfig(bundled);config=bundled;savedAi=next.getJSONObject("ai");
                            }
                            getSharedPreferences("standalone",0).edit().putBoolean("endpoint_migration_v6",true).commit();
                        }
                    }
                    // Apply this release's user-requested service change only
                    // to the previous default endpoint/model combination.
                    if(!getSharedPreferences("standalone",0).getBoolean("model_migration_v7",false)){
                        if(bundled!=null){
                            JSONObject next=new JSONObject(bundled);JSONObject nextAi=next.getJSONObject("ai");
                            String previous=savedAi==null?"":savedAi.optString("base_url").replaceAll("/+$","");
                            boolean oldDefault=savedAi!=null&&(previous.equals("http://47.110.38.211:8080/v1")||previous.equals("https://www.vibecd.cc/v1"))
                                &&savedAi.optString("model").equals("claude-opus-4-8")
                                &&savedAi.optString("vision_model","claude-opus-4-8").equals("claude-opus-4-8");
                            if(oldDefault&&nextAi.optString("base_url").equals("https://server.max-tabs.com/v1")&&nextAi.optString("model").equals("gpt-5.5")){
                                storeConfig(bundled);config=bundled;savedAi=nextAi;
                            }
                            getSharedPreferences("standalone",0).edit().putBoolean("model_migration_v7",true).commit();
                        }
                    }
                    if(!getSharedPreferences("standalone",0).getBoolean("model_migration_v8",false)&&bundled!=null){
                        JSONObject nextAi=new JSONObject(bundled).getJSONObject("ai");
                        String previous=savedAi==null?"":savedAi.optString("base_url").trim().replaceAll("/+$","");
                        String previousModel=savedAi==null?"":savedAi.optString("model");
                        boolean oldDefault=savedAi!=null&&savedAi.optString("vision_model",previousModel).equals(previousModel)&&(
                            (previous.equals("https://server.max-tabs.com/v1")&&previousModel.equals("gpt-5.5"))||
                            ((previous.equals("http://47.110.38.211:8080/v1")||previous.equals("https://www.vibecd.cc/v1"))&&previousModel.equals("claude-opus-4-8")));
                        if(oldDefault&&nextAi.optString("base_url").equals("https://cc-vibe.com/v1")){
                            storeConfig(bundled);config=bundled;savedAi=nextAi;
                        }
                        getSharedPreferences("standalone",0).edit().putBoolean("model_migration_v8",true).commit();
                    }
                    if(!getSharedPreferences("standalone",0).getBoolean(ModelConfigMigration.LEESSMIN_MIGRATION,false)&&bundled!=null){
                        JSONObject nextAi=new JSONObject(bundled).getJSONObject("ai");
                        ModelConfigMigration.Config previous=savedAi==null?null:new ModelConfigMigration.Config(config,
                            savedAi.optString("base_url"),savedAi.optString("model"),savedAi.optString("vision_model"),savedAi.optString("protocol"));
                        ModelConfigMigration.Config next=new ModelConfigMigration.Config(bundled,
                            nextAi.optString("base_url"),nextAi.optString("model"),nextAi.optString("vision_model"),nextAi.optString("protocol"));
                        String migrated=ModelConfigMigration.selectForLeessminRelease(previous,next,false);
                        if(migrated!=null&&!migrated.equals(config)){
                            storeConfig(migrated);config=migrated;savedAi=nextAi;
                        }
                        getSharedPreferences("standalone",0).edit().putBoolean(ModelConfigMigration.LEESSMIN_MIGRATION,true).commit();
                    }
                    if(!getSharedPreferences("standalone",0).getBoolean(ModelConfigMigration.SOL_MIGRATION,false)&&bundled!=null){
                        JSONObject nextAi=new JSONObject(bundled).getJSONObject("ai");
                        ModelConfigMigration.Config previous=savedAi==null?null:new ModelConfigMigration.Config(config,
                            savedAi.optString("base_url"),savedAi.optString("model"),savedAi.optString("vision_model"),savedAi.optString("protocol"));
                        ModelConfigMigration.Config next=new ModelConfigMigration.Config(bundled,
                            nextAi.optString("base_url"),nextAi.optString("model"),nextAi.optString("vision_model"),nextAi.optString("protocol"));
                        String migrated=ModelConfigMigration.selectForSolRelease(previous,next,false);
                        if(migrated!=null&&!migrated.equals(config)){storeConfig(migrated);config=migrated;savedAi=nextAi;}
                        getSharedPreferences("standalone",0).edit().putBoolean(ModelConfigMigration.SOL_MIGRATION,true).commit();
                    }
                    boolean configured=savedAi!=null&&!savedAi.optString("api_key").isEmpty();
                    if(!configured&&bundled!=null){
                        storeConfig(bundled);config=bundled;
                        getSharedPreferences("standalone",0).edit().putBoolean("embedded_model_v3",true).commit();
                    }
                }catch(Exception e){config="{}";configError=true;}
                if(!Python.isStarted())Python.start(new AndroidPlatform(getApplicationContext()));
                JSONObject session=new JSONObject(Python.getInstance().getModule("mobile_runtime").callAttr("start",engine.getAbsolutePath(),new File(getFilesDir(),"health-data").getAbsolutePath(),config).toString());
                String url=session.getString("url");origin=url.substring(0,url.length()-1);cookie=session.getString("cookie");
                final boolean warn=configError;
                runOnUiThread(()->{if(isDestroyed())return;CookieManager.getInstance().setCookie(url,cookie+"; HttpOnly; SameSite=Strict; Path=/",ok->{ready=true;aiButton.setEnabled(true);updateStatus();web.loadUrl(url);if(warn)toast("AI 设置无法读取，请重新填写；本地健康数据仍保留。");});});
            }catch(Exception e){runOnUiThread(()->{status.setText("本地启动失败，资料未清除");new AlertDialog.Builder(this).setTitle("暂时无法启动").setMessage("请重新打开应用。若仍失败，请反馈设备型号和安卓版本。不要卸载，以免丢失本地资料。").setPositiveButton("关闭",(d,w)->finish()).show();});}
        });
    }
    void startVoice(String id){
        if(id==null||id.isEmpty()||id.length()>80)return;
        if(voiceId!=null||pendingWebPermission!=null||voicePermissionPending){emitVoiceResult(id,"","麦克风正在被使用，请稍后重试。",false,"VOICE_BUSY");return;}
        voiceId=id;
        voiceState("ready","",false);
        if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){voicePermissionPending=true;requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO},AUDIO_PERMISSION);return;}
        launchVoice();
    }
    void launchVoice(){
        if(voiceId==null||!sameOrigin(web.getUrl()))return;
        if(nativeVoice.available()){
            final String session=voiceId;
            nativeVoice.start(new OfflineVoiceInput.Listener(){
                private boolean current(){return session.equals(voiceId);}
                public void state(String state,String text){if(current())voiceState(state,text,true);}
                public void result(String text,String error,String code){if(current())voiceResult(text,error,false,code);}
                public void unavailable(){if(current())voiceResult("","本机离线语音暂未准备好，可以重试或使用输入法语音。",false,"VOICE_OFFLINE_UNAVAILABLE");}
            });return;
        }
        voiceResult("","此安装包的中文离线语音资源不可用，请使用输入法语音。",false,"VOICE_OFFLINE_UNAVAILABLE");
    }
    void voiceState(String state,String text,boolean canStop){
        if(voiceId==null||isDestroyed()||!sameOrigin(web.getUrl()))return;
        try{JSONObject event=new JSONObject();event.put("id",voiceId);event.put("state",state);event.put("text",text);event.put("canStop",canStop);event.put("engine","offline");
            web.evaluateJavascript("window.dispatchEvent(new CustomEvent('zhiheng-voice-state',{detail:"+event+"}));",null);
        }catch(Exception ignored){}
    }
    void voiceResult(String text,String error,boolean cancelled){
        voiceResult(text,error,cancelled,"");
    }
    void voiceResult(String text,String error,boolean cancelled,String code){
        String id=voiceId;voiceId=null;nativeVoice.cancel();emitVoiceResult(id,text,error,cancelled,code);
    }
    void emitVoiceResult(String id,String text,String error,boolean cancelled,String code){
        if(id==null||isDestroyed()||!sameOrigin(web.getUrl()))return;
        try{JSONObject event=new JSONObject();event.put("id",id);event.put("text",text);event.put("error",error);event.put("cancelled",cancelled);event.put("code",code);event.put("fallback",!error.isEmpty());event.put("engine","offline");
            web.evaluateJavascript("window.dispatchEvent(new CustomEvent('zhiheng-voice-result',{detail:"+event.toString()+"}));",null);
        }catch(Exception ignored){}
    }
    void cancelVoice(){voiceId=null;nativeVoice.cancel();}
    void showVoiceKeyboard(){
        cancelVoice();web.requestFocus();
        web.evaluateJavascript("(()=>{const input=document.querySelector('#message');if(input&&!input.disabled)input.focus();})()",ignored->{
            InputMethodManager keyboard=(InputMethodManager)getSystemService(INPUT_METHOD_SERVICE);if(keyboard!=null)keyboard.showSoftInput(web,InputMethodManager.SHOW_IMPLICIT);
        });
    }
    @Override public void onRequestPermissionsResult(int code,String[] permissions,int[] results){
        super.onRequestPermissionsResult(code,permissions,results);if(code!=AUDIO_PERMISSION)return;
        voicePermissionPending=false;
        boolean granted=results.length>0&&results[0]==PackageManager.PERMISSION_GRANTED;
        PermissionRequest request=pendingWebPermission;pendingWebPermission=null;
        if(request!=null){if(granted&&sameOrigin(web.getUrl())&&sameOrigin(request.getOrigin().toString()))request.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});else request.deny();}
        if(voiceId!=null){if(granted)launchVoice();else voiceResult("","麦克风未授权。请到系统设置 → 应用 → 知衡 → 权限允许麦克风，再点语音。",false);}
    }
    boolean sameOrigin(String url){if(url==null||origin.isEmpty())return false;Uri u=Uri.parse(url);return origin.equals(u.getScheme()+"://"+u.getAuthority());}
    void updateStatus(){try{JSONObject ai=new JSONObject(config).optJSONObject("ai");status.setText(ai!=null&&ai.optBoolean("enabled")?"手机本地 · AI 已配置":"手机本地 · AI 未配置");}catch(Exception e){status.setText("手机本地");}}
    static void copy(InputStream in,OutputStream out)throws IOException{byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1)out.write(b,0,n);}
    String assetText(String name)throws Exception{try(InputStream in=getAssets().open(name);ByteArrayOutputStream out=new ByteArrayOutputStream()){copy(in,out);return out.toString("UTF-8");}}
    SecretKey key()throws Exception{
        KeyStore ks=KeyStore.getInstance("AndroidKeyStore");ks.load(null);
        if(!ks.containsAlias(KEY_ALIAS)){KeyGenerator g=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");g.init(new KeyGenParameterSpec.Builder(KEY_ALIAS,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());g.generateKey();}
        return (SecretKey)ks.getKey(KEY_ALIAS,null);
    }
    String readConfig()throws Exception{
        String raw=getSharedPreferences("standalone",0).getString("model","");if(raw.isEmpty())return "{}";
        String[] parts=raw.split(":");Cipher c=Cipher.getInstance("AES/GCM/NoPadding");c.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,Base64.decode(parts[0],Base64.NO_WRAP)));
        return new String(c.doFinal(Base64.decode(parts[1],Base64.NO_WRAP)),"UTF-8");
    }
    void storeConfig(String value)throws Exception{
        Cipher c=Cipher.getInstance("AES/GCM/NoPadding");c.init(Cipher.ENCRYPT_MODE,key());byte[] encrypted=c.doFinal(value.getBytes("UTF-8"));
        if(!getSharedPreferences("standalone",0).edit().putString("model",Base64.encodeToString(c.getIV(),Base64.NO_WRAP)+":"+Base64.encodeToString(encrypted,Base64.NO_WRAP)).commit())throw new IOException();
    }
    EditText field(LinearLayout layout,String hint,String value,boolean secret){EditText e=new EditText(this);e.setSingleLine(true);e.setHint(hint);e.setText(value);if(secret)e.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);layout.addView(e);return e;}
    void settings(){
        if(!ready)return;
        LinearLayout layout=new LinearLayout(this);layout.setOrientation(1);layout.setPadding(dp(18),0,dp(18),0);
        JSONObject current;try{current=new JSONObject(config).optJSONObject("ai");}catch(Exception e){current=null;}if(current==null)current=new JSONObject();final JSONObject old=current;
        EditText base=field(layout,"模型接口地址",old.optString("base_url"),false);
        EditText model=field(layout,"模型名称",old.optString("model"),false);
        EditText vision=field(layout,"图片模型（留空使用相同模型）",old.optString("vision_model"),false);
        EditText token=field(layout,old.optString("api_key").isEmpty()?"API 密钥":"密钥已保存，留空保持", "",true);
        Spinner protocol=new Spinner(this);String[] choices={"chat_completions","responses","auto"};protocol.setAdapter(new ArrayAdapter<String>(this,android.R.layout.simple_spinner_dropdown_item,choices));for(int i=0;i<choices.length;i++)if(choices[i].equals(old.optString("protocol")))protocol.setSelection(i);layout.addView(protocol);
        Button test=new Button(this);test.setText("测试已保存的模型连接");layout.addView(test);
        test.setOnClickListener(v->{test.setEnabled(false);test.setText("正在连接，请稍候…");worker.execute(()->{
            String message;
            try{JSONObject result=new JSONObject(Python.getInstance().getModule("mobile_runtime").callAttr("check_connection").toString());
                String error=result.optString("error","AI_CONNECTION_FAILED");
                String detail="AI_DNS_FAILED".equals(error)?"无法解析模型域名，请检查手机网络或DNS。":
                    "AI_TLS_FAILED".equals(error)?"HTTPS证书校验失败，请检查手机日期时间及网络代理。":
                    "AI_AUTH_FAILED".equals(error)?"接口拒绝鉴权，请核对密钥或模型服务访问权限。":
                    "AI_TIMEOUT".equals(error)?"连接或模型响应超时，可切换手机网络后再试。":
                    "AI_KEY_MISSING".equals(error)||"AI_DISABLED".equals(error)?"模型凭据未生效，请保存模型地址、名称和密钥。":"模型请求未成功，请保留错误码反馈。";
                message=result.optBoolean("ok")?"模型连接成功（"+result.optLong("elapsed_ms")+" ms）":detail+"\n错误码："+error;
            }catch(Exception e){message="连接检查未完成："+e.getClass().getSimpleName();}
            final String shown=message;runOnUiThread(()->{if(isDestroyed())return;test.setEnabled(true);test.setText("测试已保存的模型连接");new AlertDialog.Builder(this).setTitle("连接检查结果").setMessage(shown).setPositiveButton("确定",null).show();});
        });});
        final AlertDialog[] settingsDialog=new AlertDialog[1];
        try{for(String asset:getAssets().list("engine"))if(asset.equals("default_model.json")){
            Button restore=new Button(this);restore.setText("恢复内置测试模型");layout.addView(restore);
            restore.setOnClickListener(v->new AlertDialog.Builder(this).setMessage("用此安装包的内置模型替换当前AI设置？健康记录不会改变。").setPositiveButton("恢复",(d,w)->{try{applyConfig(assetText("engine/default_model.json"));if(settingsDialog[0]!=null)settingsDialog[0].dismiss();}catch(Exception e){toast("此安装包未包含模型配置");}}).setNegativeButton("取消",null).show());
            break;
        }}catch(IOException ignored){}
        ScrollView scroll=new ScrollView(this);scroll.addView(layout);
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle("AI 设置（可选）").setMessage("本地记录不需要联网。AI 对话和图片分析会将相关内容发送到你配置的模型服务。密钥仅加密保存在手机。").setView(scroll).setPositiveButton("保存",null).setNeutralButton("导入配置",(d,w)->{Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT);i.addCategory(Intent.CATEGORY_OPENABLE);i.setType("*/*");startActivityForResult(i,IMPORT);}).setNegativeButton("暂不设置",null).create();
        settingsDialog[0]=dialog;
        dialog.setOnShowListener(d->dialog.getButton(-1).setOnClickListener(v->{try{JSONObject ai=new JSONObject(old.toString());ai.put("base_url",base.getText().toString());ai.put("model",model.getText().toString());ai.put("vision_model",vision.getText().toString());ai.put("api_key",token.getText().toString().trim().isEmpty()?old.optString("api_key"):token.getText().toString());ai.put("protocol",protocol.getSelectedItem().toString());applyConfig(ai.toString());dialog.dismiss();}catch(Exception e){toast("设置格式有误");}}));dialog.show();
    }
    void applyConfig(String raw){worker.execute(()->{try{
        PyObject runtime=Python.getInstance().getModule("mobile_runtime");
        // configure returns normalized JSON; raw input is never written to logs.
        String normalized=runtime.callAttr("configure",raw).toString();
        try{storeConfig(normalized);}catch(Exception e){runtime.callAttr("configure",config);throw e;}
        config=normalized;runOnUiThread(()->{updateStatus();web.reload();toast("AI 设置已保存");});
    }catch(Exception e){toast("未保存：请核对模型地址、名称和密钥，或配置文件格式。");}});}
    void export(String kind,String conversationId){
        if(!"backup".equals(kind)&&!"json".equals(kind)&&!"conversation".equals(kind))return;
        boolean conversation="conversation".equals(kind);
        if(conversation&&(conversationId==null||conversationId.trim().isEmpty()||conversationId.length()>200)){toast("请选择要导出的对话");return;}
        if(pendingExport!=null){toast("请先完成当前导出");return;}
        String path=conversation?"/api/conversation-export?id="+Uri.encode(conversationId):"backup".equals(kind)?"/api/backup":"/api/export";
        String filename=conversation?"知衡-对话-"+conversationId.substring(0,Math.min(8,conversationId.length())).replaceAll("[^a-zA-Z0-9_-]","_")+".json":"backup".equals(kind)?"zhiheng-backup.zip":"zhiheng-export.json";
        File target=new File(getCacheDir(),"export-"+System.currentTimeMillis()+("backup".equals(kind)?".zip":".json"));pendingExport=target;
        worker.execute(()->{HttpURLConnection c=null;try{
            c=(HttpURLConnection)new URL(origin+path).openConnection();c.setInstanceFollowRedirects(false);c.setRequestProperty("Cookie",cookie);c.setConnectTimeout(10000);c.setReadTimeout(120000);
            if(c.getResponseCode()!=200)throw new IOException();try(InputStream in=c.getInputStream();OutputStream out=new FileOutputStream(target)){copy(in,out);}
            runOnUiThread(()->{
                if(isDestroyed()){target.delete();pendingExport=null;return;}
                try{Intent i=new Intent(Intent.ACTION_CREATE_DOCUMENT);i.addCategory(Intent.CATEGORY_OPENABLE);i.setType("backup".equals(kind)?"application/zip":"application/json");i.putExtra(Intent.EXTRA_TITLE,filename);startActivityForResult(i,SAVE);}
                catch(ActivityNotFoundException|SecurityException e){target.delete();pendingExport=null;toast("无法打开系统文件保存器，请检查系统文件应用后重试");}
            });
        }catch(Exception e){target.delete();runOnUiThread(()->{pendingExport=null;toast("导出失败，请重试");});}finally{if(c!=null)c.disconnect();}});
    }
    void capturePhoto(){
        try{
            File dir=new File(getCacheDir(),"camera");dir.mkdirs();
            File[] old=dir.listFiles();if(old!=null)for(File f:old)if(System.currentTimeMillis()-f.lastModified()>86400000)f.delete();
            File file=new File(dir,java.util.UUID.randomUUID().toString()+".jpg");file.createNewFile();
            cameraUri=Uri.parse("content://"+getPackageName()+".camera/"+file.getName());
            Intent i=new Intent(android.provider.MediaStore.ACTION_IMAGE_CAPTURE);
            i.putExtra(android.provider.MediaStore.EXTRA_OUTPUT,cameraUri);
            i.setClipData(ClipData.newRawUri("拍照",cameraUri));
            i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            startActivityForResult(i,CAPTURE);
        }catch(Exception e){cameraUri=null;if(chooser!=null){chooser.onReceiveValue(null);chooser=null;}toast("无法打开相机，请使用照片按钮从相册上传");}
    }
    @Override protected void onActivityResult(int request,int result,Intent data){
        super.onActivityResult(request,result,data);
        Uri uri=result==RESULT_OK&&data!=null?data.getData():null;
        if(request==CAPTURE){
            Uri captured=cameraUri;cameraUri=null;
            boolean valid=result==RESULT_OK&&captured!=null;
            if(valid){File f=new File(new File(getCacheDir(),"camera"),captured.getLastPathSegment());valid=f.length()>0;}
            if(captured!=null)revokeUriPermission(captured,Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            if(chooser!=null){chooser.onReceiveValue(valid?new Uri[]{captured}:null);chooser=null;}
        }
        if(request==PICK&&chooser!=null){chooser.onReceiveValue(uri==null?null:new Uri[]{uri});chooser=null;}
        if(request==IMPORT&&uri!=null)worker.execute(()->{try(InputStream in=getContentResolver().openInputStream(uri);ByteArrayOutputStream out=new ByteArrayOutputStream()){
            byte[] b=new byte[4096];int n;while((n=in.read(b))!=-1){if(out.size()+n>65536)throw new IOException();out.write(b,0,n);}String raw=out.toString("UTF-8");JSONObject ai=new JSONObject(raw).optJSONObject("ai");if(ai==null)ai=new JSONObject(raw);final String endpoint=ai.optString("base_url");
            runOnUiThread(()->new AlertDialog.Builder(this).setTitle("导入 AI 设置").setMessage("将使用模型服务：\n"+endpoint+"\n确认导入后，AI 请求会发送到此服务。").setPositiveButton("导入",(d,w)->applyConfig(raw)).setNegativeButton("取消",null).show());
        }catch(Exception e){toast("无法读取配置文件");}});
        if(request==SAVE&&pendingExport!=null){File file=pendingExport;pendingExport=null;if(uri==null){file.delete();return;}worker.execute(()->{try{try(InputStream in=new FileInputStream(file);OutputStream out=getContentResolver().openOutputStream(uri)){if(out==null)throw new IOException();copy(in,out);}toast("文件已保存");}catch(Exception e){toast("保存失败，请重新导出");}finally{file.delete();}});}
    }
    @Override public void onBackPressed(){
        if(!sameOrigin(web.getUrl())){finishBackNavigation();return;}
        web.evaluateJavascript("(()=>{const dialogs=Array.from(document.querySelectorAll('dialog[open]'));const top=dialogs[dialogs.length-1];if(!top)return false;top.close();return true;})()",
            handled->{if(!"true".equals(handled)&&!isFinishing()&&!isDestroyed())finishBackNavigation();});
    }
    private void finishBackNavigation(){if(web.canGoBack())web.goBack();else super.onBackPressed();}
    @Override protected void onStop(){
        if(voiceId!=null&&!voicePermissionPending)voiceResult("","语音录入已暂停，草稿已保留，请重新开始。",false,"VOICE_INTERRUPTED");
        super.onStop();
    }
    @Override protected void onDestroy(){cancelVoice();nativeVoice.destroy();if(chooser!=null)chooser.onReceiveValue(null);if(pendingWebPermission!=null){pendingWebPermission.deny();pendingWebPermission=null;}web.destroy();worker.shutdown();super.onDestroy();}
}
