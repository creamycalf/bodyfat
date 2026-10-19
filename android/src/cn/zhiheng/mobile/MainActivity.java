package cn.zhiheng.mobile;

import android.app.*;
import android.content.*;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.*;
import android.widget.*;
import android.view.*;

public class MainActivity extends Activity {
    WebView web;
    LinearLayout root;
    TextView status;
    String origin="";
    ValueCallback<Uri[]> chooser;
    static final int PICK=7;
    int dp(int n){return (int)(getResources().getDisplayMetrics().density*n);}

    @Override public void onCreate(Bundle state){
        super.onCreate(state);
        getWindow().setStatusBarColor(0xff177c6e);
        root=new LinearLayout(this);root.setOrientation(1);setContentView(root);
        LinearLayout bar=new LinearLayout(this);
        Button settings=new Button(this);settings.setText("连接设置");settings.setOnClickListener(v->connectDialog());bar.addView(settings);
        Button reload=new Button(this);reload.setText("重试 / 刷新");reload.setOnClickListener(v->web.reload());bar.addView(reload);
        root.addView(bar);
        status=new TextView(this);status.setPadding(dp(12),dp(4),dp(12),dp(4));root.addView(status);
        web=new WebView(this);root.addView(web,new LinearLayout.LayoutParams(-1,0,1));
        WebSettings s=web.getSettings();s.setJavaScriptEnabled(true);s.setDomStorageEnabled(true);s.setAllowFileAccess(false);s.setAllowContentAccess(true);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        CookieManager.getInstance().setAcceptCookie(true);CookieManager.getInstance().setAcceptThirdPartyCookies(web,false);
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest req){return !sameOrigin(req.getUrl());}
            @Override public void onPageFinished(WebView view,String url){CookieManager.getInstance().flush();}
            @Override public void onReceivedError(WebView view,WebResourceRequest req,WebResourceError err){if(req.isForMainFrame())status.setText("未连上电脑。确认同一 Wi-Fi、电脑服务已启动，再点重试。");}
            @Override public void onReceivedHttpError(WebView view,WebResourceRequest req,WebResourceResponse res){if(req.isForMainFrame())status.setText(res.getStatusCode()==401||res.getStatusCode()==403?"连接码失效，请重新填写电脑提供的完整连接地址。":"电脑服务返回错误，请稍后重试。");}
        });
        web.setWebChromeClient(new WebChromeClient(){
            @Override public boolean onShowFileChooser(WebView v,ValueCallback<Uri[]> callback,FileChooserParams params){
                if(!sameOrigin(Uri.parse(v.getUrl())))return false;
                if(chooser!=null)chooser.onReceiveValue(null);chooser=callback;
                Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT);intent.addCategory(Intent.CATEGORY_OPENABLE);
                String[] accept=params.getAcceptTypes();intent.setType(accept.length>0&&accept[0].startsWith("image")?"image/*":"*/*");
                try{startActivityForResult(intent,PICK);}catch(ActivityNotFoundException e){chooser.onReceiveValue(null);chooser=null;Toast.makeText(MainActivity.this,"未找到文件选择器",Toast.LENGTH_LONG).show();}return true;
            }
            @Override public boolean onJsAlert(WebView v,String url,String text,JsResult result){new AlertDialog.Builder(MainActivity.this).setMessage(text).setPositiveButton("确定",(d,w)->result.confirm()).setOnCancelListener(d->result.cancel()).show();return true;}
            @Override public boolean onJsConfirm(WebView v,String url,String text,JsResult result){new AlertDialog.Builder(MainActivity.this).setMessage(text).setPositiveButton("确定",(d,w)->result.confirm()).setNegativeButton("取消",(d,w)->result.cancel()).setOnCancelListener(d->result.cancel()).show();return true;}
            @Override public boolean onJsPrompt(WebView v,String url,String text,String value,JsPromptResult result){EditText input=new EditText(MainActivity.this);input.setText(value);new AlertDialog.Builder(MainActivity.this).setMessage(text).setView(input).setPositiveButton("确定",(d,w)->result.confirm(input.getText().toString())).setNegativeButton("取消",(d,w)->result.cancel()).setOnCancelListener(d->result.cancel()).show();return true;}
        });
        web.setDownloadListener((url,ua,cd,mime,size)->Toast.makeText(this,"本测试版请在电脑端导出数据或完整备份。",Toast.LENGTH_LONG).show());
        String saved=getPreferences(0).getString("connection","");
        if(saved.isEmpty())connectDialog();else load(saved);
    }
    boolean sameOrigin(Uri u){return u!=null&&(u.getScheme()+"://"+u.getAuthority()).equals(origin);}
    boolean valid(Uri u){
        if(!"http".equals(u.getScheme())||u.getUserInfo()!=null||!"/connect".equals(u.getPath())||u.getPort()<1||u.getQueryParameter("token")==null)return false;
        String h=u.getHost();if(h==null)return false;
        String[] p=h.split("\\.");if(p.length!=4)return false;
        try{int[] n=new int[4];for(int i=0;i<4;i++){n[i]=Integer.parseInt(p[i]);if(n[i]<0||n[i]>255)return false;}
            return n[0]==10||(n[0]==192&&n[1]==168)||(n[0]==172&&n[1]>=16&&n[1]<=31);
        }catch(NumberFormatException e){return false;}
    }
    void load(String url){Uri u=Uri.parse(url);if(!valid(u)){status.setText("请输入电脑生成的局域网连接地址。");return;}
        origin=u.getScheme()+"://"+u.getAuthority();getPreferences(0).edit().putString("connection",url).apply();
        status.setText("电脑连接："+u.getAuthority()+" · 数据保存在电脑");web.loadUrl(url);
    }
    void connectDialog(){
        EditText input=new EditText(this);input.setSingleLine(true);input.setHint("粘贴电脑生成的完整连接地址");input.setText(getPreferences(0).getString("connection",""));
        input.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_VARIATION_URI);
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle("连接知衡电脑服务").setMessage("手机和电脑连接同一 Wi-Fi。启动电脑端“启动手机测试.cmd”，复制生成的连接地址。语音可使用手机键盘输入。").setView(input).setPositiveButton("连接",null).setNegativeButton("取消",null).create();
        dialog.setOnShowListener(d->dialog.getButton(-1).setOnClickListener(v->{String url=input.getText().toString().trim();if(!valid(Uri.parse(url))){input.setError("需要完整的局域网连接地址（含连接码）");return;}load(url);dialog.dismiss();}));dialog.show();
    }
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==PICK&&chooser!=null){chooser.onReceiveValue(result==RESULT_OK&&data!=null&&data.getData()!=null?new Uri[]{data.getData()}:null);chooser=null;}}
    @Override public void onBackPressed(){if(web.canGoBack())web.goBack();else super.onBackPressed();}
    @Override protected void onDestroy(){if(chooser!=null)chooser.onReceiveValue(null);web.destroy();super.onDestroy();}
}
