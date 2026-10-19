"""Exercise the APK's offline controller with real worker threads and model ZIP.

Only microphone/Vosk JNI/platform callbacks are replaced. The Java controller,
ZIP extraction, checksum, state machine, text assembly and cleanup are the
production source. No audio, remote service, key, or health record is accessed.
"""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
JAVA_SOURCE = ROOT / 'android/standalone/app/src/main/java/cn/zhiheng/mobile/OfflineVoiceInput.java'
MODEL_ASSET = ROOT / 'android/standalone/app/src/main/assets/voice/vosk-model-small-cn-0.22.zip'
MODEL_DOWNLOAD = ROOT / 'tmp/voice-offline-downloads/vosk-model-small-cn-0.22.zip'
MODEL_HASH = '3af8b0e7e0f835ae9d414ce5df580237a3cfb08d586c9fbbb0f7ff29ad5b14ba'

STUBS = {
    'android/Manifest.java': '''package android;
public final class Manifest {public static final class permission {public static final String RECORD_AUDIO="android.permission.RECORD_AUDIO";}}''',
    'android/content/pm/PackageManager.java': '''package android.content.pm;
public final class PackageManager {public static final int PERMISSION_GRANTED=0;}''',
    'android/content/Context.java': '''package android.content;
import android.content.res.AssetManager;import java.io.File;
public class Context {public static File files;public static int permission=0;
 public Context getApplicationContext(){return this;}public AssetManager getAssets(){return new AssetManager();}
 public File getFilesDir(){return files;}public int checkSelfPermission(String value){return permission;}}''',
    'android/content/res/AssetManager.java': '''package android.content.res;
import java.io.*;import java.util.concurrent.atomic.AtomicInteger;
public final class AssetManager {public static File source;public static boolean missing;
 public static final AtomicInteger opens=new AtomicInteger();
 public InputStream open(String name)throws IOException{opens.incrementAndGet();if(missing)throw new FileNotFoundException();
  if(!name.equals("voice/vosk-model-small-cn-0.22.zip"))throw new IOException("unexpected asset");return new FileInputStream(source);}}''',
    'android/os/Looper.java': '''package android.os;
public final class Looper {public static Looper getMainLooper(){return new Looper();}}''',
    'android/os/Handler.java': '''package android.os;
import java.util.*;import java.util.concurrent.*;
public final class Handler {
 public static final BlockingQueue<Runnable> tasks=new LinkedBlockingQueue<>();
 public static final Map<Runnable,Long> delayed=Collections.synchronizedMap(new LinkedHashMap<>());
 public Handler(Looper looper){}public boolean post(Runnable task){tasks.add(task);return true;}
 public boolean postDelayed(Runnable task,long delay){delayed.put(task,delay);return true;}
 public void removeCallbacks(Runnable task){delayed.remove(task);tasks.remove(task);}
 public static Runnable deadline(long delay){synchronized(delayed){for(Map.Entry<Runnable,Long> row:delayed.entrySet())if(row.getValue()==delay)return row.getKey();}return null;}
}''',
    'android/os/SystemClock.java': '''package android.os;
public final class SystemClock {public static long elapsedRealtime(){return System.nanoTime()/1000000L;}}''',
    'android/media/AudioFormat.java': '''package android.media;
public final class AudioFormat {public static final int CHANNEL_IN_MONO=16,ENCODING_PCM_16BIT=2;}''',
    'android/media/MediaRecorder.java': '''package android.media;
public final class MediaRecorder {public static final class AudioSource {public static final int VOICE_RECOGNITION=6;}}''',
    'android/media/AudioRecord.java': '''package android.media;
import java.util.*;import java.util.concurrent.*;
public final class AudioRecord {
 public static final int STATE_INITIALIZED=1,RECORDSTATE_RECORDING=3,READ_NON_BLOCKING=1;
 public static final List<AudioRecord> instances=new CopyOnWriteArrayList<>();
 public static int minimum=3200;public static boolean initialized=true,permissionFailure=false,stopFailure=false,releaseFailure=false;
 public final int source,rate,channels,encoding,bufferSize;
 public final BlockingQueue<Integer> frames=new LinkedBlockingQueue<>();public final CountDownLatch released=new CountDownLatch(1);
 public static CountDownLatch readEntered,readContinue,stopEntered,stopContinue;public volatile boolean recording;public volatile int stops,releases;
 public AudioRecord(int source,int rate,int channels,int encoding,int size){this.source=source;this.rate=rate;this.channels=channels;this.encoding=encoding;bufferSize=size;instances.add(this);}
 public static int getMinBufferSize(int rate,int channels,int encoding){return minimum;}
 public int getState(){return initialized?STATE_INITIALIZED:0;}public int getRecordingState(){return recording?RECORDSTATE_RECORDING:0;}
 public void startRecording(){if(permissionFailure)throw new SecurityException();recording=true;}
 public int read(short[] buffer,int offset,int length,int mode){if(mode!=READ_NON_BLOCKING)throw new AssertionError("capture must be nonblocking");try{Integer marker=frames.poll();if(marker==null)return 0;if(marker<0)return marker;
  if(readEntered!=null)readEntered.countDown();if(readContinue!=null&&!readContinue.await(5,TimeUnit.SECONDS))return -3;
  buffer[offset]=marker.shortValue();return 1;}catch(InterruptedException failure){Thread.currentThread().interrupt();return -3;}}
 public void feed(int marker){frames.add(marker);}public void stop(){stops++;recording=false;frames.add(-3);
  if(stopEntered!=null)stopEntered.countDown();if(stopContinue!=null)try{stopContinue.await(5,TimeUnit.SECONDS);}catch(InterruptedException e){Thread.currentThread().interrupt();}
  if(stopFailure)throw new IllegalStateException("stop failed");}
 public void release(){releases++;released.countDown();if(releaseFailure)throw new IllegalStateException("release failed");}
}''',
    'org/json/JSONException.java': '''package org.json;
public class JSONException extends Exception {public JSONException(String message){super(message);}}''',
    'org/json/JSONObject.java': '''package org.json;
public final class JSONObject {private final String text;
 public JSONObject(String value)throws JSONException{if(value==null||!value.trim().startsWith("{"))throw new JSONException("invalid JSON");text=value;}
 public String optString(String key,String fallback){String quote=String.valueOf((char)34);int keyStart=text.indexOf(quote+key+quote);if(keyStart<0)return fallback;
  int colon=text.indexOf(':',keyStart),start=text.indexOf(quote,colon+1),end=text.indexOf(quote,start+1);return start>=0&&end>start?text.substring(start+1,end):fallback;}}
''',
    'org/vosk/Model.java': '''package org.vosk;
import java.io.*;import java.util.*;import java.util.concurrent.*;
public final class Model implements AutoCloseable {
 public static final List<Model> instances=new CopyOnWriteArrayList<>();public static String failure="";
 public static CountDownLatch entered,gate;public final String path;public volatile int closes;public final CountDownLatch closed=new CountDownLatch(1);
 public Model(String path)throws IOException{this.path=path;if(entered!=null)entered.countDown();
  if(gate!=null)try{if(!gate.await(5,TimeUnit.SECONDS))throw new IOException("test model gate timed out");}catch(InterruptedException e){throw new IOException(e);}
  if(failure.equals("linkage"))throw new UnsatisfiedLinkError();if(failure.equals("io"))throw new IOException();if(failure.equals("runtime"))throw new IllegalStateException();instances.add(this);}
 public void close(){closes++;closed.countDown();}}
''',
    'org/vosk/Recognizer.java': '''package org.vosk;
import java.io.*;import java.util.*;import java.util.concurrent.*;
public final class Recognizer implements AutoCloseable {
 public static final List<Recognizer> instances=new CopyOnWriteArrayList<>();public static boolean readFailure,closeFailure;
 public static String finalText="{\\\"text\\\":\\\"\\\"}";
 public static final Map<Integer,String> json=new ConcurrentHashMap<>();public static final Set<Integer> finalized=ConcurrentHashMap.newKeySet();
 public static final BlockingQueue<Integer> processed=new LinkedBlockingQueue<>();
 public final float rate;public volatile int closes;private int marker;
 public Recognizer(Model model,float rate)throws IOException{this.rate=rate;instances.add(this);}
 public boolean acceptWaveForm(short[] buffer,int count){if(readFailure)throw new IllegalStateException();marker=buffer[0];processed.add(marker);return finalized.contains(marker);}
 public String getResult(){return json.get(marker);}public String getPartialResult(){return json.get(marker);}public String getFinalResult(){return finalText;}
 public void close(){closes++;if(closeFailure)throw new IllegalStateException("close failed");}}
''',
}

HARNESS = r'''
package cn.zhiheng.mobile;
import android.content.Context;import android.content.res.AssetManager;import android.media.AudioRecord;import android.media.AudioFormat;import android.media.MediaRecorder;
import android.os.Handler;import org.vosk.Model;import org.vosk.Recognizer;
import java.io.*;import java.nio.charset.StandardCharsets;import java.nio.file.*;import java.util.*;import java.util.concurrent.*;import java.util.function.BooleanSupplier;

public final class OfflineVoiceControllerTest {
 private static final String HASH="3af8b0e7e0f835ae9d414ce5df580237a3cfb08d586c9fbbb0f7ff29ad5b14ba";
 private static final class Events implements OfflineVoiceInput.Listener {
  final ArrayList<String> states=new ArrayList<>();int results,missing;String text,error,code;
  public void state(String state,String text){states.add(state+":"+text);}
  public void result(String text,String error,String code){
   for(AudioRecord audio:AudioRecord.instances)equal(1,audio.releases,"microphone released before terminal callback");
   for(Recognizer rec:Recognizer.instances)equal(1,rec.closes,"native recognizer closed before terminal callback");
   results++;this.text=text;this.error=error;this.code=code;
  }
  public void unavailable(){missing++;}
  boolean listening(){return states.stream().anyMatch(value->value.startsWith("listening:"));}
 }
 private static void check(boolean condition,String label){if(!condition)throw new AssertionError(label);}
 private static void equal(Object expected,Object actual,String label){if(!Objects.equals(expected,actual))throw new AssertionError(label+": expected "+expected+", actual "+actual);}
 private static void pumpUntil(BooleanSupplier done)throws Exception{
  long end=System.nanoTime()+TimeUnit.SECONDS.toNanos(8);
  while(!done.getAsBoolean()){long remaining=end-System.nanoTime();if(remaining<=0)throw new AssertionError("callback wait timed out");
   Runnable callback=Handler.tasks.poll(remaining,TimeUnit.NANOSECONDS);if(callback==null)throw new AssertionError("callback wait timed out");callback.run();}
 }
 private static void flush(){Runnable callback;while((callback=Handler.tasks.poll())!=null)callback.run();}
 private static void await(CountDownLatch gate,String label)throws Exception{check(gate.await(5,TimeUnit.SECONDS),label);}
 private static AudioRecord audio(){return AudioRecord.instances.get(AudioRecord.instances.size()-1);}
 private static OfflineVoiceInput controller(){return new OfflineVoiceInput(new Context());}
 private static Events start(OfflineVoiceInput voice)throws Exception{Events event=new Events();voice.start(event);pumpUntil(event::listening);return event;}
 private static void segment(AudioRecord audio,int marker,String json,boolean finalSegment)throws Exception{
  Recognizer.json.put(marker,json);if(finalSegment)Recognizer.finalized.add(marker);audio.feed(marker);
  equal(marker,Recognizer.processed.poll(5,TimeUnit.SECONDS),"worker accepted supplied PCM frame");
 }
 private static void finish(OfflineVoiceInput voice,Events event)throws Exception{voice.stop();pumpUntil(()->event.results+event.missing>0);flush();}
 private static void destroy(OfflineVoiceInput voice)throws Exception{
  voice.destroy();for(AudioRecord item:AudioRecord.instances)await(item.released,"cancelled recording is released");
  for(Model model:Model.instances){await(model.closed,"destroy closes native model on worker");equal(1,model.closes,"destroy closes reusable native model once");}flush();
 }
 private static void installAndReuse()throws Exception{
  OfflineVoiceInput voice=controller();check(voice.available(),"bundled model available without system service");Events first=start(voice);
  File installed=new File(Context.files,"voice/vosk-model-small-cn-0.22");
  equal(HASH,Files.readString(new File(installed,"model-ready.sha256").toPath(),StandardCharsets.US_ASCII),"verified model checksum marker");
  check(new File(installed,"am/final.mdl").length()>0,"actual archive unpacked");check(!new File(Context.files,"voice/vosk-model-small-cn-0.22.preparing").exists(),"staging directory cleaned");
  equal(Arrays.asList("ready:","preparing:","listening:"),first.states,"first-use callback order");
  Recognizer.finalText="{\"text\":\"模型 可以 使用\"}";finish(voice,first);equal("模型可以使用",first.text,"installed model session works");
  int before=AssetManager.opens.get();Events second=start(voice);finish(voice,second);
  equal(before+1,AssetManager.opens.get(),"second session checks bundled asset but does not unzip again");equal(1,Model.instances.size(),"native model reused");
  destroy(voice);check(!voice.available(),"destroyed input reports unavailable");
 }
 private static void chineseAssembly()throws Exception{
  OfflineVoiceInput voice=controller();Events event=start(voice);AudioRecord rec=audio();
  equal(16000,rec.rate,"16 kHz audio");equal(AudioFormat.CHANNEL_IN_MONO,rec.channels,"mono audio");equal(AudioFormat.ENCODING_PCM_16BIT,rec.encoding,"PCM16 audio");equal(MediaRecorder.AudioSource.VOICE_RECOGNITION,rec.source,"speech microphone source");
  segment(rec,1,"{\"text\":\"我 今天 吃了\"}",true);pumpUntil(()->event.states.contains("listening:我今天吃了"));
  segment(rec,2,"{\"partial\":\"鸡肉 还有\"}",false);pumpUntil(()->event.states.contains("listening:我今天吃了鸡肉还有"));equal(0,event.results,"partials never finalize a session");
  segment(rec,3,"{\"text\":\"鸡肉\"}",true);pumpUntil(()->event.states.contains("listening:我今天吃了鸡肉"));
  Recognizer.finalText="{\"text\":\"和 米饭 100 克\"}";finish(voice,event);
  equal("我今天吃了鸡肉和米饭100克",event.text,"combine finalized segments plus final tail without partial duplication");equal("",event.code,"success has no error");equal(1,event.results,"one final result");
  voice.stop();voice.cancel();flush();equal(1,event.results,"terminal controls never resubmit text");destroy(voice);
 }
 private static void latinAndEmpty()throws Exception{
  OfflineVoiceInput voice=controller();Events first=start(voice);segment(audio(),1,"{\"text\":\"使用 Apple watch\"}",true);pumpUntil(()->first.states.contains("listening:使用Apple watch"));
  Recognizer.finalText="{\"text\":\"散步 30 分钟\"}";finish(voice,first);equal("使用Apple watch散步30分钟",first.text,"preserve Latin word spaces while compacting Chinese");
  Recognizer.finalText="{\"text\":\" \"}";Events empty=start(voice);finish(voice,empty);equal("VOICE_NO_SPEECH",empty.code,"empty audio gives useful retry error");equal("",empty.text,"silence never creates text");destroy(voice);
 }
 private static void finalFrameDuringStop()throws Exception{
  OfflineVoiceInput voice=controller();Events event=start(voice);AudioRecord.readEntered=new CountDownLatch(1);AudioRecord.readContinue=new CountDownLatch(1);
  Recognizer.json.put(1,"{\"text\":\"最后 说 的\"}");Recognizer.finalized.add(1);Recognizer.finalText="{\"text\":\"一句话\"}";
  audio().feed(1);await(AudioRecord.readEntered,"positive PCM frame already captured by recorder");voice.stop();AudioRecord.readContinue.countDown();pumpUntil(()->event.results>0);flush();
  equal("最后说的一句话",event.text,"Stop must preserve an already captured final positive PCM frame");
  check(!event.states.contains("listening:最后说的"),"delayed listening preview must not re-enable Stop after processing starts");destroy(voice);
 }
 private static void cancelAndGeneration()throws Exception{
  OfflineVoiceInput voice=controller();Events old=start(voice);AudioRecord earlier=audio();Recognizer.finalText="{\"text\":\"旧结果\"}";
  voice.stop();await(earlier.released,"old stop completes on worker");Events fresh=new Events();voice.start(fresh);
  pumpUntil(fresh::listening);equal(0,old.results,"queued old terminal result cannot commit after new session starts");
  voice.cancel();await(audio().released,"cancel releases recording");flush();equal(0,fresh.results,"cancelled session never submits transcription");
  Recognizer.finalText="{\"text\":\"新的 录入\"}";Events retry=start(voice);finish(voice,retry);equal("新的录入",retry.text,"safe retry works after cancel");destroy(voice);
 }
 private static void preparationCancel()throws Exception{
  Model.entered=new CountDownLatch(1);Model.gate=new CountDownLatch(1);OfflineVoiceInput voice=controller();Events old=new Events();voice.start(old);
  await(Model.entered,"model load reached worker");flush();check(old.states.contains("preparing:"),"preparing acknowledged promptly");voice.cancel();Model.gate.countDown();
  Events next=new Events();voice.start(next);pumpUntil(next::listening);equal(0,old.results,"cancel while native model loads does not submit stale result");
  finish(voice,next);equal(1,next.results,"new recording works after preparation cancellation");destroy(voice);
 }
 private static void deadline()throws Exception{
  OfflineVoiceInput voice=controller();Events event=start(voice);flush();Runnable timeout=Handler.deadline(50000);
  check(timeout!=null,"recording deadline exists");timeout.run();pumpUntil(()->event.results>0);equal("VOICE_TIMEOUT",event.code,"recording limit stops silence with actionable timeout");equal(0,Handler.delayed.size(),"terminal session removes all timers");
  Events retry=start(voice);timeout.run();flush();equal(0,retry.results,"stale timer cannot finish new recording");Recognizer.finalText="{\"text\":\"重新 说话\"}";finish(voice,retry);equal("重新说话",retry.text,"record after timeout");destroy(voice);
 }
 private static void permissionAndUnavailable()throws Exception{
  Context.permission=-1;OfflineVoiceInput voice=controller();Events denied=new Events();voice.start(denied);pumpUntil(()->denied.results>0);
  equal("VOICE_PERMISSION_DENIED",denied.code,"permission denied before model/audio creation");equal(0,AudioRecord.instances.size(),"permission denial never records audio");
  Context.permission=0;AssetManager.missing=true;check(!voice.available(),"missing bundled asset is unavailable");Events missing=new Events();voice.start(missing);pumpUntil(()->missing.missing>0);equal(0,missing.results,"resource absence is not fake transcription");equal(0,Handler.delayed.size(),"unavailable has no dangling timer");destroy(voice);
 }
 private static void audioFailure()throws Exception{
  OfflineVoiceInput voice=controller();Events event=start(voice);audio().feed(-2);pumpUntil(()->event.results>0);equal("VOICE_AUDIO",event.code,"microphone read failure maps to useful audio error");
  Recognizer.finalText="{\"text\":\"再次 录入\"}";Events retry=start(voice);finish(voice,retry);equal("再次录入",retry.text,"audio failure releases resources and permits retry");destroy(voice);
 }
 private static void nativeFailure()throws Exception{
  Model.failure="linkage";OfflineVoiceInput voice=controller();Events missing=new Events();voice.start(missing);pumpUntil(()->missing.missing>0);equal(0,missing.results,"JNI absence offers fallback rather than fabricated text");equal(0,AudioRecord.instances.size(),"JNI failure does not open microphone");
  Model.failure="";Events retry=start(voice);Recognizer.readFailure=true;audio().feed(1);pumpUntil(()->retry.results>0);equal("VOICE_OFFLINE_ERROR",retry.code,"recognizer runtime error is recoverable");destroy(voice);
 }
 private static void cleanupExceptions()throws Exception{
  OfflineVoiceInput voice=controller();Events event=start(voice);AudioRecord.stopFailure=true;AudioRecord.releaseFailure=true;Recognizer.closeFailure=true;
  Recognizer.finalText="{\"text\":\"正常 结果\"}";finish(voice,event);equal("正常结果",event.text,"cleanup exceptions do not discard finalized text");equal(1,event.results,"cleanup exceptions still finalize exactly once");destroy(voice);
 }
 private static void automaticFinish()throws Exception{
  OfflineVoiceInput voice=controller();Events event=start(voice);
  segment(audio(),1,"{\"text\":\"今天 吃了 鸡肉\"}",true);pumpUntil(()->event.states.contains("listening:今天吃了鸡肉"));flush();
  Runnable silence=Handler.deadline(1500);check(silence!=null,"recognized endpoint schedules hands-free completion");
  silence.run();pumpUntil(()->event.results>0);equal("今天吃了鸡肉",event.text,"pause completes a usable draft without manual Stop");equal(0,Handler.delayed.size(),"completion clears silence and recording deadlines");destroy(voice);
 }
 private static void continuingSpeech()throws Exception{
  OfflineVoiceInput voice=controller();Events event=start(voice);
  segment(audio(),1,"{\"text\":\"今天 吃了\"}",true);pumpUntil(()->event.states.contains("listening:今天吃了"));flush();check(Handler.deadline(1500)!=null,"pause pending");
  segment(audio(),2,"{\"partial\":\"鸡肉\"}",false);pumpUntil(()->event.states.contains("listening:今天吃了鸡肉"));flush();
  check(Handler.deadline(1500)==null,"new speech cancels automatic end before the next pause");
  Recognizer.finalText="{\"text\":\"鸡肉 和 米饭\"}";finish(voice,event);equal("今天吃了鸡肉和米饭",event.text,"continued phrase stays in the same recording");destroy(voice);
 }
 private static void stopOffUi()throws Exception{
  OfflineVoiceInput voice=controller();Events event=start(voice);AudioRecord.stopEntered=new CountDownLatch(1);AudioRecord.stopContinue=new CountDownLatch(1);
  long before=System.nanoTime();voice.stop();check(System.nanoTime()-before<TimeUnit.MILLISECONDS.toNanos(200),"Stop returns promptly on UI even when platform cleanup blocks");
  await(AudioRecord.stopEntered,"platform Stop occurs on worker");before=System.nanoTime();voice.cancel();check(System.nanoTime()-before<TimeUnit.MILLISECONDS.toNanos(200),"Cancel never calls blocked platform Stop on UI");
  AudioRecord.stopContinue.countDown();destroy(voice);equal(0,event.results,"cancelled blocked cleanup cannot submit stale text");
 }
 private static void unsafeArchive()throws Exception{
  OfflineVoiceInput voice=controller();Events event=new Events();voice.start(event);pumpUntil(()->event.results>0);
  equal("VOICE_MODEL_LOAD",event.code,"unsafe/tampered ZIP rejected as model load error");equal(0,Model.instances.size(),"unverified model never reaches native loader");
  check(!new File(Context.files,"escaped.txt").exists(),"path traversal cannot write outside staging");check(!new File(Context.files,"voice/vosk-model-small-cn-0.22.preparing").exists(),"failed extraction staging removed");
  check(!new File(Context.files,"voice/vosk-model-small-cn-0.22").exists(),"unverified model never installed");destroy(voice);
 }
 public static void main(String[] args)throws Exception{
  Context.files=new File(args[1]);Context.files.mkdirs();AssetManager.source=new File(args[2]);
  switch(args[0]){case "install":installAndReuse();break;case "chinese":chineseAssembly();break;case "latin":latinAndEmpty();break;case "stop_frame":finalFrameDuringStop();break;
   case "generation":cancelAndGeneration();break;case "prepare_cancel":preparationCancel();break;case "deadline":deadline();break;
   case "permission":permissionAndUnavailable();break;case "audio":audioFailure();break;case "native":nativeFailure();break;
   case "cleanup":cleanupExceptions();break;case "auto_finish":automaticFinish();break;case "continue":continuingSpeech();break;case "ui_stop":stopOffUi();break;case "unsafe":unsafeArchive();break;default:throw new AssertionError("unknown case");}
  System.out.println("PASS: "+args[0]);
 }
}
'''


class OfflineVoiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        candidates = []
        if os.environ.get('JAVA_HOME'):
            candidates.append(Path(os.environ['JAVA_HOME']) / 'bin')
        if shutil.which('javac'):
            candidates.append(Path(shutil.which('javac')).parent)
        candidates.append(ROOT.parent / 'moviedl/.tool-downloads/jdk17/jdk-17.0.20.1+1/bin')
        java_bin = next((path for path in candidates if (path / 'javac.exe').is_file()
                         or (path / 'javac').is_file()), None)
        if java_bin is None:
            raise unittest.SkipTest('Java compiler unavailable for actual offline controller checks')
        cls.asset = MODEL_ASSET if MODEL_ASSET.is_file() else MODEL_DOWNLOAD
        if not cls.asset.is_file():
            raise AssertionError('Bundled Chinese voice ZIP is required for offline model verification')
        if hashlib.sha256(cls.asset.read_bytes()).hexdigest() != MODEL_HASH:
            raise AssertionError('Chinese voice model checksum differs from pinned official archive')
        suffix = '.exe' if (java_bin / 'javac.exe').is_file() else ''
        cls.java = str(java_bin / ('java' + suffix))
        cls.temp = tempfile.TemporaryDirectory(prefix='zhiheng-offline-voice-')
        cls.addClassCleanup(cls.temp.cleanup)
        folder = Path(cls.temp.name)
        sources = [JAVA_SOURCE]
        for name, source in STUBS.items():
            target = folder / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source, encoding='utf-8')
            sources.append(target)
        harness = folder / 'cn/zhiheng/mobile/OfflineVoiceControllerTest.java'
        harness.parent.mkdir(parents=True, exist_ok=True)
        harness.write_text(HARNESS, encoding='utf-8')
        sources.append(harness)
        compiled = subprocess.run([str(java_bin / ('javac' + suffix)), '-encoding', 'UTF-8',
            '-d', str(folder), *map(str, sources)], capture_output=True, text=True, timeout=30)
        if compiled.returncode:
            raise AssertionError('Actual OfflineVoiceInput compilation failed:\n' + compiled.stderr)
        cls.installed = folder / 'installed'
        installed = cls.run_case('install', cls.installed)
        if installed.returncode:
            raise AssertionError('Production model extraction fixture failed:\n' + installed.stderr)
        cls.unsafe_zip = folder / 'unsafe.zip'
        with zipfile.ZipFile(cls.unsafe_zip, 'w') as archive:
            archive.writestr('vosk-model-small-cn-0.22/../../../escaped.txt', 'tampered')
        cls.tampered_zip = folder / 'tampered.zip'
        with zipfile.ZipFile(cls.tampered_zip, 'w') as archive:
            archive.writestr('vosk-model-small-cn-0.22/conf/model.conf', 'tampered model')

    @classmethod
    def run_case(cls, case, files=None, asset=None):
        return subprocess.run([cls.java, '-Dfile.encoding=UTF-8', '-cp', cls.temp.name,
            'cn.zhiheng.mobile.OfflineVoiceControllerTest', case,
            str(files or cls.installed), str(asset or cls.asset)], capture_output=True,
            text=True, encoding='utf-8', timeout=20)

    def check_case(self, case, files=None, asset=None):
        checked = self.run_case(case, files, asset)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertIn('PASS: ' + case, checked.stdout)

    def test_first_use_extracts_verified_archive_and_reuses_native_model(self):
        self.check_case('install', Path(self.temp.name) / 'fresh-install')

    def test_pcm16_chinese_segments_and_final_tail_exclude_partial_hypotheses(self):
        self.check_case('chinese')

    def test_pause_finishes_a_recognized_phrase_without_stop_button(self):
        self.check_case('auto_finish')

    def test_continued_speech_cancels_pending_automatic_end(self):
        self.check_case('continue')

    def test_blocked_platform_stop_does_not_block_ui_stop_or_cancel(self):
        self.check_case('ui_stop')

    def test_latin_word_spaces_and_silence_have_useful_results(self):
        self.check_case('latin')

    def test_stop_keeps_final_captured_pcm_frame_without_reenabling_listening(self):
        self.check_case('stop_frame')

    def test_cancel_and_replacement_reject_old_queued_results(self):
        self.check_case('generation')

    def test_cancel_while_native_model_loads_permits_new_recording(self):
        self.check_case('prepare_cancel')

    def test_deadline_stops_microphone_and_stale_timer_cannot_finish_retry(self):
        self.check_case('deadline')

    def test_permissions_and_missing_assets_never_record_or_fake_results(self):
        self.check_case('permission')

    def test_audio_failure_releases_resources_and_allows_retry(self):
        self.check_case('audio')

    def test_jni_and_recognizer_failure_offer_recoverable_outcome(self):
        self.check_case('native')

    def test_cleanup_exceptions_still_finalize_once(self):
        self.check_case('cleanup')

    def test_path_traversal_archive_never_writes_outside_staging(self):
        self.check_case('unsafe', Path(self.temp.name) / 'unsafe-files', self.unsafe_zip)

    def test_tampered_archive_never_reaches_native_loader(self):
        self.check_case('unsafe', Path(self.temp.name) / 'tampered-files', self.tampered_zip)


if __name__ == '__main__':
    unittest.main()
