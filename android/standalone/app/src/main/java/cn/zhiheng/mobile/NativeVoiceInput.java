package cn.zhiheng.mobile;

import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import java.util.ArrayList;

/** Owns one recognizer session. All methods and callbacks run on the main thread. */
final class NativeVoiceInput {
    interface Listener {
        void state(String state, String text);
        void result(String text, String error, String code);
        void unavailable();
    }
    private final Context context;
    private final Handler handler=new Handler(Looper.getMainLooper());
    private SpeechRecognizer recognizer;
    private Listener listener;
    private Runnable deadline;
    private int generation;
    private boolean onDevice,heard;

    NativeVoiceInput(Context context){this.context=context;}
    boolean available(){
        try{return Build.VERSION.SDK_INT>=31&&SpeechRecognizer.isOnDeviceRecognitionAvailable(context)
            ||SpeechRecognizer.isRecognitionAvailable(context);}catch(RuntimeException error){return false;}
    }
    void start(Listener callback){
        cancel();listener=callback;
        boolean local=false;
        try{local=Build.VERSION.SDK_INT>=31&&SpeechRecognizer.isOnDeviceRecognitionAvailable(context);}catch(RuntimeException ignored){}
        startEngine(local);
    }
    private void startEngine(boolean local){
        final int session=++generation;release();onDevice=local;heard=false;
        try{
            recognizer=local?SpeechRecognizer.createOnDeviceSpeechRecognizer(context):SpeechRecognizer.createSpeechRecognizer(context);
            recognizer.setRecognitionListener(new RecognitionListener(){
                private boolean current(){return session==generation&&listener!=null;}
                @Override public void onReadyForSpeech(Bundle params){if(current())listener.state("listening","");}
                @Override public void onBeginningOfSpeech(){if(current())heard=true;}
                @Override public void onRmsChanged(float rmsDb){}
                @Override public void onBufferReceived(byte[] buffer){}
                @Override public void onEndOfSpeech(){if(current())listener.state("processing","");}
                @Override public void onPartialResults(Bundle values){
                    if(!current())return;String text=first(values);if(!text.isEmpty()){heard=true;listener.state("listening",text);}
                }
                @Override public void onResults(Bundle values){
                    if(!current())return;String text=first(values);
                    finish(text,text.isEmpty()?"没有识别到文字，请再说一次。":"",text.isEmpty()?"VOICE_NO_SPEECH":"");
                }
                @Override public void onError(int error){
                    if(!current())return;
                    // An offline engine may exist but have no Chinese language pack.
                    if(onDevice&&!heard&&(error==SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED
                        ||error==SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE||error==SpeechRecognizer.ERROR_CLIENT)){
                        try{if(SpeechRecognizer.isRecognitionAvailable(context)){startEngine(false);return;}}catch(RuntimeException ignored){}
                    }
                    if(!heard&&(error==SpeechRecognizer.ERROR_CLIENT||error==SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED
                        ||error==SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE)){unavailable();return;}
                    String code="VOICE_RECOGNIZER_ERROR",message="手机语音服务识别失败，可以重试或使用输入法语音。";
                    switch(error){
                        case SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS:code="VOICE_PERMISSION_DENIED";message="麦克风未授权，请在系统设置允许知衡使用麦克风。";break;
                        case SpeechRecognizer.ERROR_NETWORK:case SpeechRecognizer.ERROR_NETWORK_TIMEOUT:code="VOICE_NETWORK";message="手机语音服务连接失败，请检查网络后重试。";break;
                        case SpeechRecognizer.ERROR_AUDIO:code="VOICE_AUDIO";message="麦克风暂时不可用，请关闭其他录音应用后重试。";break;
                        case SpeechRecognizer.ERROR_NO_MATCH:case SpeechRecognizer.ERROR_SPEECH_TIMEOUT:code="VOICE_NO_SPEECH";message="没有听清，请靠近手机再说一次。";break;
                        case SpeechRecognizer.ERROR_RECOGNIZER_BUSY:code="VOICE_BUSY";message="手机语音服务正忙，请稍后重试。";break;
                    }
                    finish("",message,code);
                }
                @Override public void onEvent(int type,Bundle params){}
            });
            deadline=()->{if(session==generation&&listener!=null)finish("","语音识别等待超时，草稿已保留，可以重试。","VOICE_TIMEOUT");};
            handler.postDelayed(deadline,50000);
            listener.state("ready","");recognizer.startListening(intent());
        }catch(SecurityException error){finish("","麦克风未授权，请在系统设置允许知衡使用麦克风。","VOICE_PERMISSION_DENIED");}
        catch(RuntimeException error){if(local){startEngine(false);}else unavailable();}
    }
    static Intent intent(){
        return new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE,"zh-CN")
            .putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS,true)
            .putExtra(RecognizerIntent.EXTRA_MAX_RESULTS,1);
    }
    private static String first(Bundle values){
        ArrayList<String> words=values==null?null:values.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
        if(words!=null)for(String word:words)if(word!=null&&!word.trim().isEmpty())return word.trim();
        return "";
    }
    void stop(){
        if(recognizer==null||listener==null)return;
        try{listener.state("processing","");recognizer.stopListening();}
        catch(RuntimeException error){finish("","语音服务未能结束识别，请重试。","VOICE_STOP_FAILED");}
    }
    void cancel(){generation++;listener=null;release();}
    private void finish(String text,String error,String code){Listener callback=listener;listener=null;generation++;release();if(callback!=null)callback.result(text,error,code);}
    private void unavailable(){Listener callback=listener;listener=null;generation++;release();if(callback!=null)callback.unavailable();}
    private void release(){
        if(deadline!=null){handler.removeCallbacks(deadline);deadline=null;}
        SpeechRecognizer previous=recognizer;recognizer=null;
        if(previous!=null){try{previous.cancel();}catch(RuntimeException ignored){}try{previous.destroy();}catch(RuntimeException ignored){}}
    }
}
