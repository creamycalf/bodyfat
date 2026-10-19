"""Run the native speech controller against deterministic Android service events.

These stubs only replace Android's platform services. The session controller under
test is the actual Java source shipped in the APK, including its listener and
deadline callbacks. No device, microphone, health data, or model API is accessed.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
JAVA_SOURCE = ROOT / 'android/standalone/app/src/main/java/cn/zhiheng/mobile/NativeVoiceInput.java'
MANIFEST = ROOT / 'android/standalone/app/src/main/AndroidManifest.xml'

ANDROID_STUBS = {
    'android/content/Context.java': '''package android.content;
public class Context {}''',
    'android/content/Intent.java': '''package android.content;
import java.util.HashMap;
import java.util.Map;
public class Intent {
    private final String action;
    private final Map<String,Object> extras=new HashMap<>();
    public Intent(String action){this.action=action;}
    public Intent putExtra(String key,String value){extras.put(key,value);return this;}
    public Intent putExtra(String key,boolean value){extras.put(key,value);return this;}
    public Intent putExtra(String key,int value){extras.put(key,value);return this;}
    public String getAction(){return action;}
    public String getStringExtra(String key){return (String)extras.get(key);}
    public boolean getBooleanExtra(String key,boolean fallback){return extras.containsKey(key)?(Boolean)extras.get(key):fallback;}
    public int getIntExtra(String key,int fallback){return extras.containsKey(key)?(Integer)extras.get(key):fallback;}
}''',
    'android/os/Build.java': '''package android.os;
public final class Build {public static final class VERSION {public static int SDK_INT=31;}}''',
    'android/os/Bundle.java': '''package android.os;
import java.util.ArrayList;
import java.util.HashMap;
public class Bundle {
    private final HashMap<String,ArrayList<String>> words=new HashMap<>();
    public void putStringArrayList(String key,ArrayList<String> value){words.put(key,value);}
    public ArrayList<String> getStringArrayList(String key){return words.get(key);}
}''',
    'android/os/Looper.java': '''package android.os;
public final class Looper {public static Looper getMainLooper(){return new Looper();}}''',
    'android/os/Handler.java': '''package android.os;
import java.util.ArrayList;
public final class Handler {
    public static final ArrayList<Runnable> pending=new ArrayList<>();
    public static long lastDelay;
    public Handler(Looper looper){}
    public boolean postDelayed(Runnable task,long delay){pending.add(task);lastDelay=delay;return true;}
    public void removeCallbacks(Runnable task){pending.removeIf(item->item==task);}
    public static void reset(){pending.clear();lastDelay=0;}
}''',
    'android/speech/RecognitionListener.java': '''package android.speech;
import android.os.Bundle;
public interface RecognitionListener {
    void onReadyForSpeech(Bundle params); void onBeginningOfSpeech();
    void onRmsChanged(float rmsDb); void onBufferReceived(byte[] buffer);
    void onEndOfSpeech(); void onPartialResults(Bundle values);
    void onResults(Bundle values); void onError(int error); void onEvent(int type,Bundle params);
}''',
    'android/speech/RecognizerIntent.java': '''package android.speech;
public final class RecognizerIntent {
    public static final String ACTION_RECOGNIZE_SPEECH="android.speech.action.RECOGNIZE_SPEECH";
    public static final String EXTRA_LANGUAGE_MODEL="android.speech.extra.LANGUAGE_MODEL";
    public static final String LANGUAGE_MODEL_FREE_FORM="free_form";
    public static final String EXTRA_LANGUAGE="android.speech.extra.LANGUAGE";
    public static final String EXTRA_PARTIAL_RESULTS="android.speech.extra.PARTIAL_RESULTS";
    public static final String EXTRA_MAX_RESULTS="android.speech.extra.MAX_RESULTS";
}''',
    'android/speech/SpeechRecognizer.java': '''package android.speech;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.Handler;
import java.util.ArrayList;
public final class SpeechRecognizer {
    public static final int ERROR_NETWORK_TIMEOUT=1,ERROR_NETWORK=2,ERROR_AUDIO=3,
        ERROR_SERVER=4,ERROR_CLIENT=5,ERROR_SPEECH_TIMEOUT=6,ERROR_NO_MATCH=7,
        ERROR_RECOGNIZER_BUSY=8,ERROR_INSUFFICIENT_PERMISSIONS=9,
        ERROR_LANGUAGE_NOT_SUPPORTED=12,ERROR_LANGUAGE_UNAVAILABLE=13;
    public static final String RESULTS_RECOGNITION="results_recognition";
    public static boolean deviceAvailable,defaultAvailable,deviceCreateFails,defaultCreateFails,
        startSecurityFails,startRuntimeFails;
    public static int deviceChecks,defaultChecks;
    public static final ArrayList<SpeechRecognizer> instances=new ArrayList<>();
    public final boolean onDevice;
    public RecognitionListener callback;
    public Intent request;
    public int starts,stops,cancels,destroys;
    public boolean stopFails,cancelFails,destroyFails;
    private SpeechRecognizer(boolean local){onDevice=local;instances.add(this);}
    public static void reset(){
        deviceAvailable=false;defaultAvailable=true;deviceCreateFails=false;defaultCreateFails=false;
        startSecurityFails=false;startRuntimeFails=false;deviceChecks=0;defaultChecks=0;
        instances.clear();Handler.reset();Build.VERSION.SDK_INT=31;
    }
    public static boolean isOnDeviceRecognitionAvailable(Context context){deviceChecks++;return deviceAvailable;}
    public static boolean isRecognitionAvailable(Context context){defaultChecks++;return defaultAvailable;}
    public static SpeechRecognizer createOnDeviceSpeechRecognizer(Context context){
        if(deviceCreateFails)throw new IllegalStateException("missing on-device service");return new SpeechRecognizer(true);
    }
    public static SpeechRecognizer createSpeechRecognizer(Context context){
        if(defaultCreateFails)throw new IllegalStateException("missing system service");return new SpeechRecognizer(false);
    }
    public void setRecognitionListener(RecognitionListener listener){callback=listener;}
    public void startListening(Intent intent){
        request=intent;starts++;if(startSecurityFails)throw new SecurityException("microphone denied");
        if(startRuntimeFails)throw new IllegalStateException("speech service unavailable");
    }
    public void stopListening(){stops++;if(stopFails)throw new IllegalStateException("stop failed");}
    public void cancel(){cancels++;if(cancelFails)throw new IllegalStateException("cancel failed");}
    public void destroy(){destroys++;if(destroyFails)throw new IllegalStateException("destroy failed");}
}''',
}

JAVA_TEST = r'''
package cn.zhiheng.mobile;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import java.util.ArrayList;
import java.util.Arrays;

public final class NativeVoiceControllerTest {
    private static final class Events implements NativeVoiceInput.Listener {
        final ArrayList<String> states=new ArrayList<>();
        int results,unavailable;
        String text,error,code;
        public void state(String state,String text){states.add(state+":"+text);}
        public void result(String text,String error,String code){results++;this.text=text;this.error=error;this.code=code;}
        public void unavailable(){unavailable++;}
    }
    private static void check(boolean condition,String message){if(!condition)throw new AssertionError(message);}
    private static void equal(Object expected,Object actual,String message){
        if(expected==null?actual!=null:!expected.equals(actual))throw new AssertionError(message+": expected "+expected+", actual "+actual);
    }
    private static NativeVoiceInput controller(){return new NativeVoiceInput(new Context());}
    private static SpeechRecognizer engine(){return SpeechRecognizer.instances.get(SpeechRecognizer.instances.size()-1);}
    private static Bundle words(String... texts){
        Bundle bundle=new Bundle();bundle.putStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION,new ArrayList<>(Arrays.asList(texts)));return bundle;
    }
    private static void released(SpeechRecognizer recognizer){
        equal(1,recognizer.cancels,"recognizer cancelled once");equal(1,recognizer.destroys,"recognizer destroyed once");
        equal(0,Handler.pending.size(),"terminal session removes its deadline");
    }
    private static void chineseAndCallbacks(){
        NativeVoiceInput voice=controller();Events events=new Events();voice.start(events);SpeechRecognizer recognizer=engine();
        Intent intent=recognizer.request;
        equal(RecognizerIntent.ACTION_RECOGNIZE_SPEECH,intent.getAction(),"speech activity action");
        equal("zh-CN",intent.getStringExtra(RecognizerIntent.EXTRA_LANGUAGE),"recognition language");
        equal(RecognizerIntent.LANGUAGE_MODEL_FREE_FORM,intent.getStringExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL),"natural speech model");
        check(intent.getBooleanExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS,false),"partial transcription enabled");
        equal(1,intent.getIntExtra(RecognizerIntent.EXTRA_MAX_RESULTS,-1),"one hypothesis requested");
        equal(Arrays.asList("ready:"),events.states,"initial ready event");
        recognizer.callback.onReadyForSpeech(new Bundle());recognizer.callback.onBeginningOfSpeech();
        recognizer.callback.onPartialResults(words(null," ","  今天中午吃了鸡肉  "));
        recognizer.callback.onPartialResults(null);recognizer.callback.onPartialResults(words(""));
        recognizer.callback.onEndOfSpeech();voice.stop();
        check(events.states.contains("listening:今天中午吃了鸡肉"),"use first nonempty partial hypothesis");
        equal(1,recognizer.stops,"stop waits for recognizer's final text");equal(0,events.results,"stop does not finalize early");
        recognizer.callback.onResults(words("  今天中午吃了鸡肉和米饭  ","other hypothesis"));
        equal(1,events.results,"one final callback");equal("今天中午吃了鸡肉和米饭",events.text,"trimmed final text");
        equal("",events.error,"successful recognition has no error");equal("",events.code,"successful recognition has no error code");
        released(recognizer);voice.stop();voice.cancel();equal(1,events.results,"cleanup never republishes results");
    }
    private static void enginePreference(){
        SpeechRecognizer.deviceAvailable=true;NativeVoiceInput local=controller();check(local.available(),"on-device availability");
        Events events=new Events();local.start(events);check(engine().onDevice,"SDK 31 prefers on-device engine");local.cancel();
        SpeechRecognizer.reset();Build.VERSION.SDK_INT=30;SpeechRecognizer.deviceAvailable=true;
        NativeVoiceInput older=controller();check(older.available(),"pre-31 system engine availability");older.start(new Events());
        check(!engine().onDevice,"pre-31 uses system recognizer");equal(0,SpeechRecognizer.deviceChecks,"pre-31 never calls API 31 method");older.cancel();
    }
    private static void oneLanguageFallback(){
        for(int failure:new int[]{SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED,SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE,SpeechRecognizer.ERROR_CLIENT}){
            SpeechRecognizer.reset();SpeechRecognizer.deviceAvailable=true;NativeVoiceInput voice=controller();Events events=new Events();voice.start(events);
            SpeechRecognizer offline=engine();Runnable firstDeadline=Handler.pending.get(0);offline.callback.onError(failure);
            SpeechRecognizer fallback=engine();equal(2,SpeechRecognizer.instances.size(),"one engine replacement");check(!fallback.onDevice,"fallback uses system speech service");
            equal(1,offline.destroys,"offline engine released before fallback");equal(1,Handler.pending.size(),"fallback replaces deadline");
            offline.callback.onResults(words("obsolete offline result"));firstDeadline.run();equal(0,events.results,"obsolete offline callbacks ignored");
            fallback.callback.onError(failure);equal(1,events.unavailable,"unsupported system service offers fallback UI");
            equal(2,SpeechRecognizer.instances.size(),"language fallback never loops");equal(0,events.results,"unavailability is not a fake result");released(fallback);
        }
        SpeechRecognizer.reset();SpeechRecognizer.deviceAvailable=true;NativeVoiceInput voice=controller();Events events=new Events();voice.start(events);
        engine().callback.onPartialResults(words("已经听见了"));engine().callback.onError(SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE);
        equal(1,SpeechRecognizer.instances.size(),"do not replace recognizer after receiving speech");equal(1,events.results,"heard speech ends with error");
    }
    private static void unavailableAndCreationFallback(){
        SpeechRecognizer.defaultAvailable=false;SpeechRecognizer.defaultCreateFails=true;NativeVoiceInput absent=controller();
        check(!absent.available(),"no speech services reported unavailable");Events missing=new Events();absent.start(missing);
        equal(1,missing.unavailable,"missing system service has unavailable callback");equal(0,Handler.pending.size(),"creation failure leaves no timer");
        SpeechRecognizer.reset();SpeechRecognizer.deviceAvailable=true;SpeechRecognizer.deviceCreateFails=true;NativeVoiceInput voice=controller();Events events=new Events();voice.start(events);
        check(!engine().onDevice,"on-device creation failure falls back");engine().callback.onResults(words("系统语音可用"));equal("系统语音可用",events.text,"fallback transcribes");
        SpeechRecognizer.reset();SpeechRecognizer.startRuntimeFails=true;NativeVoiceInput broken=controller();Events crashed=new Events();broken.start(crashed);
        equal(1,crashed.unavailable,"service startup failure invokes unavailable");released(engine());
    }
    private static void cancelAndSessionIsolation(){
        NativeVoiceInput voice=controller();Events first=new Events();voice.start(first);SpeechRecognizer old=engine();Runnable oldDeadline=Handler.pending.get(0);
        voice.cancel();released(old);int before=first.states.size();
        old.callback.onReadyForSpeech(new Bundle());old.callback.onPartialResults(words("obsolete"));old.callback.onEndOfSpeech();
        old.callback.onResults(words("obsolete"));old.callback.onError(SpeechRecognizer.ERROR_NETWORK);oldDeadline.run();
        equal(before,first.states.size(),"cancelled listener receives no more states");equal(0,first.results,"cancelled listener receives no result");
        Events next=new Events();voice.start(next);SpeechRecognizer fresh=engine();old.callback.onResults(words("wrong session"));oldDeadline.run();
        equal(0,next.results,"old callback cannot finish next session");fresh.callback.onResults(words("新会话"));equal("新会话",next.text,"new session final result");
        voice.start(new Events());SpeechRecognizer replaced=engine();Events replacement=new Events();voice.start(replacement);
        equal(1,replaced.destroys,"starting next session releases active recognizer");replaced.callback.onResults(words("overwritten"));equal(0,replacement.results,"replacement ignores earlier recognizer");voice.cancel();
    }
    private static void errorMapping(){
        int[] failures={SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS,SpeechRecognizer.ERROR_NETWORK,SpeechRecognizer.ERROR_NETWORK_TIMEOUT,
            SpeechRecognizer.ERROR_AUDIO,SpeechRecognizer.ERROR_NO_MATCH,SpeechRecognizer.ERROR_SPEECH_TIMEOUT,SpeechRecognizer.ERROR_RECOGNIZER_BUSY,SpeechRecognizer.ERROR_SERVER};
        String[] codes={"VOICE_PERMISSION_DENIED","VOICE_NETWORK","VOICE_NETWORK","VOICE_AUDIO","VOICE_NO_SPEECH","VOICE_NO_SPEECH","VOICE_BUSY","VOICE_RECOGNIZER_ERROR"};
        for(int i=0;i<failures.length;i++){
            SpeechRecognizer.reset();NativeVoiceInput voice=controller();Events events=new Events();voice.start(events);SpeechRecognizer recognizer=engine();recognizer.callback.onError(failures[i]);
            equal(codes[i],events.code,"user actionable error "+failures[i]);equal("",events.text,"failure never creates text");check(!events.error.isEmpty(),"error has Chinese explanation");
            equal(1,events.results,"error ends once");released(recognizer);recognizer.callback.onResults(words("late result"));equal(1,events.results,"late result after error ignored");
        }
        SpeechRecognizer.reset();SpeechRecognizer.startSecurityFails=true;NativeVoiceInput denied=controller();Events events=new Events();denied.start(events);
        equal("VOICE_PERMISSION_DENIED",events.code,"security exception maps to microphone permission");released(engine());
    }
    private static void timeoutAndRetry(){
        NativeVoiceInput voice=controller();Events events=new Events();voice.start(events);SpeechRecognizer recognizer=engine();
        equal(50000L,Handler.lastDelay,"recognition has bounded 50 second deadline");Runnable deadline=Handler.pending.get(0);deadline.run();
        equal("VOICE_TIMEOUT",events.code,"deadline gives timeout code");equal(1,events.results,"deadline finishes once");released(recognizer);
        Events retry=new Events();voice.start(retry);SpeechRecognizer next=engine();deadline.run();recognizer.callback.onResults(words("too late"));
        equal(0,retry.results,"timed out session cannot affect retry");next.callback.onResults(words("重新说一遍"));equal("重新说一遍",retry.text,"retry succeeds");released(next);
    }
    private static void emptyFinalAndStopFailure(){
        for(Bundle answer:new Bundle[]{null,new Bundle(),words(null," ","")}){
            SpeechRecognizer.reset();NativeVoiceInput voice=controller();Events events=new Events();voice.start(events);SpeechRecognizer recognizer=engine();recognizer.callback.onResults(answer);
            equal("VOICE_NO_SPEECH",events.code,"empty final offers retry");equal("",events.text,"empty final has no text");released(recognizer);
        }
        SpeechRecognizer.reset();NativeVoiceInput voice=controller();Events events=new Events();voice.start(events);SpeechRecognizer recognizer=engine();recognizer.stopFails=true;voice.stop();
        equal("VOICE_STOP_FAILED",events.code,"stop failure ends clearly");released(recognizer);
    }
    private static void releaseExceptions(){
        NativeVoiceInput voice=controller();Events events=new Events();voice.start(events);SpeechRecognizer recognizer=engine();
        recognizer.cancelFails=true;recognizer.destroyFails=true;voice.cancel();released(recognizer);recognizer.callback.onResults(words("late"));
        equal(0,events.results,"broken cleanup still invalidates old listener");Events retry=new Events();voice.start(retry);engine().callback.onResults(words("后续可录入"));equal("后续可录入",retry.text,"cleanup exceptions do not poison retry");
    }
    public static void main(String[] args){
        SpeechRecognizer.reset();switch(args[0]){
            case "chinese":chineseAndCallbacks();break;case "preference":enginePreference();break;
            case "language":oneLanguageFallback();break;case "unavailable":unavailableAndCreationFallback();break;
            case "isolation":cancelAndSessionIsolation();break;case "errors":errorMapping();break;
            case "timeout":timeoutAndRetry();break;case "empty":emptyFinalAndStopFailure();break;
            case "cleanup":releaseExceptions();break;default:throw new AssertionError("unknown case");
        }
        System.out.println("PASS: "+args[0]);
    }
}
'''


class AndroidVoiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        candidates = []
        if os.environ.get('JAVA_HOME'):
            candidates.append(Path(os.environ['JAVA_HOME']) / 'bin')
        if shutil.which('javac'):
            candidates.append(Path(shutil.which('javac')).parent)
        candidates.append(ROOT.parent / 'moviedl/.tool-downloads/jdk17/jdk-17.0.20.1+1/bin')
        java_bin = next((folder for folder in candidates if (folder / 'javac.exe').is_file()
                         or (folder / 'javac').is_file()), None)
        if java_bin is None:
            raise unittest.SkipTest('Java compiler unavailable for native speech controller verification')
        suffix = '.exe' if (java_bin / 'javac.exe').is_file() else ''
        cls.java = str(java_bin / ('java' + suffix))
        cls.temp = tempfile.TemporaryDirectory(prefix='zhiheng-android-voice-')
        cls.addClassCleanup(cls.temp.cleanup)
        folder = Path(cls.temp.name)
        sources = [JAVA_SOURCE]
        for name, source in ANDROID_STUBS.items():
            target = folder / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source, encoding='utf-8')
            sources.append(target)
        harness = folder / 'cn/zhiheng/mobile/NativeVoiceControllerTest.java'
        harness.parent.mkdir(parents=True, exist_ok=True)
        harness.write_text(JAVA_TEST, encoding='utf-8')
        sources.append(harness)
        compiled = subprocess.run([str(java_bin / ('javac' + suffix)), '-encoding', 'UTF-8',
            '-d', str(folder), *map(str, sources)], capture_output=True, text=True, timeout=30)
        if compiled.returncode:
            raise AssertionError('Actual NativeVoiceInput compilation failed:\n' + compiled.stderr)

    def check_case(self, case):
        checked = subprocess.run([self.java, '-Dfile.encoding=UTF-8', '-cp', self.temp.name,
            'cn.zhiheng.mobile.NativeVoiceControllerTest', case], capture_output=True,
            text=True, encoding='utf-8', timeout=15)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertIn('PASS: ' + case, checked.stdout)

    def test_chinese_intent_partial_stop_and_final_result(self):
        self.check_case('chinese')

    def test_sdk_31_prefers_offline_and_older_android_uses_default_service(self):
        self.check_case('preference')

    def test_missing_chinese_language_pack_falls_back_only_once(self):
        self.check_case('language')

    def test_missing_or_broken_service_offers_unavailable_fallback(self):
        self.check_case('unavailable')

    def test_cancel_and_replacement_ignore_obsolete_service_callbacks(self):
        self.check_case('isolation')

    def test_permission_network_audio_no_speech_and_busy_errors(self):
        self.check_case('errors')

    def test_deadline_cleans_up_and_allows_safe_retry(self):
        self.check_case('timeout')

    def test_empty_final_text_and_failed_stop_allow_retry(self):
        self.check_case('empty')

    def test_cleanup_exceptions_do_not_leave_active_callbacks(self):
        self.check_case('cleanup')

    def test_android_package_can_discover_speech_services_and_request_microphone(self):
        manifest = ET.parse(MANIFEST).getroot()
        name = '{http://schemas.android.com/apk/res/android}name'
        permissions = {item.get(name) for item in manifest.findall('uses-permission')}
        queries = {item.get(name) for item in manifest.findall('queries/intent/action')}
        self.assertIn('android.permission.RECORD_AUDIO', permissions)
        self.assertIn('android.speech.RecognitionService', queries)
        self.assertIn('android.speech.action.RECOGNIZE_SPEECH', queries)


if __name__ == '__main__':
    unittest.main()
