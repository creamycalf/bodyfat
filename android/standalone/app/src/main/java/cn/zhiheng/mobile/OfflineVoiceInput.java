package cn.zhiheng.mobile;

import android.Manifest;
import android.content.Context;
import android.content.pm.PackageManager;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import org.json.JSONException;
import org.json.JSONObject;
import org.vosk.Model;
import org.vosk.Recognizer;
import java.io.BufferedInputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.DigestInputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.RejectedExecutionException;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/** Local Chinese dictation. Audio is processed in memory and never saved or uploaded. */
final class OfflineVoiceInput {
    interface Listener {
        void state(String state, String text);
        void result(String text, String error, String code);
        void unavailable();
    }

    private static final String MODEL_NAME="vosk-model-small-cn-0.22";
    private static final String MODEL_ASSET="voice/"+MODEL_NAME+".zip";
    private static final String MODEL_SHA256="3af8b0e7e0f835ae9d414ce5df580237a3cfb08d586c9fbbb0f7ff29ad5b14ba";
    private static final String READY_FILE="model-ready.sha256";
    private static final int SAMPLE_RATE=16000;
    private static final long MAX_FILE_BYTES=64L*1024*1024;
    private static final long MAX_MODEL_BYTES=128L*1024*1024;
    private static final long RECORD_LIMIT_MS=50000;
    private final Context context;
    private final Handler handler=new Handler(Looper.getMainLooper());
    // Only this worker creates, calls, and closes the native model and recognizers.
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private volatile Session active;
    private volatile boolean destroyed;
    private volatile int generation;
    private Model model;

    private static final class Session {
        final int generation;
        final Listener callback;
        volatile boolean cancelled,stopRequested,listening,timedOut;
        volatile AudioRecord audio;
        Runnable deadline,silence;
        Session(int generation,Listener callback){this.generation=generation;this.callback=callback;}
    }

    OfflineVoiceInput(Context context){this.context=context.getApplicationContext();}

    boolean available(){
        if(destroyed)return false;
        try(InputStream ignored=context.getAssets().open(MODEL_ASSET)){return true;}
        catch(IOException|RuntimeException error){return false;}
    }

    void start(Listener callback){
        cancel();
        if(callback==null)return;
        if(destroyed){handler.post(callback::unavailable);return;}
        Session session=new Session(++generation,callback);active=session;
        if(!available()){unavailable(session);return;}
        if(context.checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){
            finish(session,"","麦克风未授权，请在系统设置允许知衡使用麦克风。","VOICE_PERMISSION_DENIED");return;
        }
        // Acknowledge immediately: first use needs to unpack and load the bundled model.
        state(session,"ready","");
        state(session,"preparing","");
        session.deadline=()->{
            if(!current(session))return;
            session.cancelled=true;
            finish(session,"","离线语音准备超时，可以重试；已有草稿已保留。","VOICE_TIMEOUT");
        };
        handler.postDelayed(session.deadline,90000);
        try{worker.execute(()->recognize(session));}
        catch(RejectedExecutionException error){unavailable(session);}
    }

    void stop(){
        Session session=active;
        if(session==null||!session.listening||session.stopRequested)return;
        session.stopRequested=true;
        state(session,"processing","");
        // AudioRecord.stop can block on some phones. Nonblocking capture lets
        // the worker finish and release the microphone without blocking UI.
    }

    void cancel(){
        Session session=active;active=null;generation++;
        if(session!=null){
            session.cancelled=true;
            if(session.deadline!=null)handler.removeCallbacks(session.deadline);
            if(session.silence!=null)handler.removeCallbacks(session.silence);
        }
    }

    void destroy(){
        if(destroyed)return;
        destroyed=true;cancel();
        // Enqueue after the cancelled recording; never wait for a native call on the UI thread.
        try{worker.execute(()->{if(model!=null){try{model.close();}catch(RuntimeException ignored){}model=null;}});}
        catch(RejectedExecutionException ignored){}
        worker.shutdown();
    }

    private boolean current(Session session){return active==session&&session.generation==generation&&!destroyed;}
    private boolean recording(Session session){return current(session)&&!session.cancelled&&!session.stopRequested;}

    private void state(Session session,String status,String text){
        handler.post(()->{
            if(current(session)&&!session.cancelled&&!(session.stopRequested&&"listening".equals(status)))
                session.callback.state(status,text);
        });
    }

    private void finish(Session session,String text,String error,String code){
        handler.post(()->{
            if(!current(session))return;
            active=null;generation++;
            if(session.deadline!=null)handler.removeCallbacks(session.deadline);
            if(session.silence!=null)handler.removeCallbacks(session.silence);
            session.callback.result(text,error,code);
        });
    }

    private void unavailable(Session session){
        handler.post(()->{
            if(!current(session))return;
            active=null;generation++;
            if(session.deadline!=null)handler.removeCallbacks(session.deadline);
            if(session.silence!=null)handler.removeCallbacks(session.silence);
            session.callback.unavailable();
        });
    }

    private void silence(Session session,boolean ended){
        handler.post(()->{
            if(!recording(session))return;
            if(session.silence!=null)handler.removeCallbacks(session.silence);
            session.silence=null;
            if(ended){session.silence=()->{if(recording(session))stop();};handler.postDelayed(session.silence,1500);}
        });
    }

    private void recognize(Session session){
        Recognizer recognizer=null;AudioRecord audio=null;
        String text="",error="",code="";boolean unsupported=false;
        StringBuilder segments=new StringBuilder();
        try{
            if(!recording(session))return;
            if(model==null)model=new Model(prepareModel(session).getAbsolutePath());
            if(!recording(session))return;
            recognizer=new Recognizer(model,(float)SAMPLE_RATE);
            int min=AudioRecord.getMinBufferSize(SAMPLE_RATE,AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT);
            if(min<=0||min>1024*1024)throw new AudioFailure();
            try{audio=new AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION,SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT,Math.max(6400,min*2));}
            catch(IllegalArgumentException failure){throw new AudioFailure();}
            session.audio=audio;
            if(audio.getState()!=AudioRecord.STATE_INITIALIZED)throw new AudioFailure();
            if(!recording(session))return;
            try{audio.startRecording();}catch(IllegalStateException failure){throw new AudioFailure();}
            if(audio.getRecordingState()!=AudioRecord.RECORDSTATE_RECORDING)throw new AudioFailure();
            session.listening=true;
            final long started=SystemClock.elapsedRealtime();
            handler.post(()->{
                if(!recording(session))return;
                if(session.deadline!=null)handler.removeCallbacks(session.deadline);
                session.deadline=()->{
                    if(!current(session)||session.cancelled)return;
                    session.timedOut=true;session.stopRequested=true;
                    state(session,"processing","");
                };
                handler.postDelayed(session.deadline,RECORD_LIMIT_MS);
            });
            state(session,"listening","");
            short[] buffer=new short[1600];String previous="";
            while(recording(session)){
                if(SystemClock.elapsedRealtime()-started>=RECORD_LIMIT_MS){session.timedOut=true;break;}
                int count=audio.read(buffer,0,buffer.length,AudioRecord.READ_NON_BLOCKING);
                if(count<0){if(!recording(session))break;throw new AudioFailure();}
                if(count==0){try{Thread.sleep(10);}catch(InterruptedException interrupted){Thread.currentThread().interrupt();break;}continue;}
                if(!current(session)||session.cancelled)break;
                String preview;
                if(recognizer.acceptWaveForm(buffer,count)){
                    String segment=jsonText(recognizer.getResult(),"text");
                    append(segments,segment);preview=segments.toString();
                    if(!segment.isEmpty())silence(session,true);
                }else{
                    StringBuilder draft=new StringBuilder(segments);
                    String partial=jsonText(recognizer.getPartialResult(),"partial");
                    append(draft,partial);preview=draft.toString();
                    if(!partial.isEmpty())silence(session,false);
                }
                if(!preview.equals(previous)){previous=preview;state(session,"listening",preview);}
            }
            if(current(session)&&!session.cancelled){
                state(session,"processing","");
                append(segments,jsonText(recognizer.getFinalResult(),"text"));text=segments.toString().trim();
                if(text.isEmpty()){
                    code=session.timedOut?"VOICE_TIMEOUT":"VOICE_NO_SPEECH";
                    error=session.timedOut?"没有听清，录音已结束，可以靠近手机再试一次。":"没有听清，请靠近手机再说一次。";
                }
            }
        }catch(SecurityException failure){code="VOICE_PERMISSION_DENIED";error="麦克风未授权，请在系统设置允许知衡使用麦克风。";}
        catch(AudioFailure failure){code="VOICE_AUDIO";error="麦克风暂时不可用，请关闭其他录音应用后重试。";}
        catch(IOException failure){code="VOICE_MODEL_LOAD";error="离线语音模型未能准备好，请检查手机剩余空间后重试。";}
        catch(LinkageError failure){unsupported=true;}
        catch(RuntimeException failure){code="VOICE_OFFLINE_ERROR";error="离线语音识别未完成，可以重试；已有草稿已保留。";}
        finally{
            session.listening=false;session.audio=null;
            if(audio!=null){try{audio.stop();}catch(RuntimeException ignored){}try{audio.release();}catch(RuntimeException ignored){}}
            if(recognizer!=null){try{recognizer.close();}catch(RuntimeException ignored){}}
        }
        if(current(session)&&!session.cancelled){if(unsupported)unavailable(session);else finish(session,text,error,code);}
    }

    private static final class AudioFailure extends Exception {}

    private static String jsonText(String value,String key){
        try{return new JSONObject(value).optString(key,"").trim();}
        catch(JSONException|RuntimeException error){return "";}
    }

    // Vosk separates Chinese tokens with spaces. Keep spaces between Latin words only.
    private static String compact(String value){
        String[] words=value.trim().split("\\s+");StringBuilder result=new StringBuilder();
        for(String word:words){
            if(word.isEmpty())continue;
            if(result.length()>0&&!chinese(result.charAt(result.length()-1))&&!chinese(word.charAt(0)))result.append(' ');
            result.append(word);
        }
        return result.toString();
    }

    private static boolean chinese(char value){return value>='\u3400'&&value<='\u9fff'||value>='\uf900'&&value<='\ufaff';}
    private static void append(StringBuilder target,String value){
        String part=compact(value);if(part.isEmpty())return;
        if(target.length()>0&&!chinese(target.charAt(target.length()-1))&&!chinese(part.charAt(0)))target.append(' ');
        target.append(part);
    }

    private File prepareModel(Session session) throws IOException {
        File files=context.getFilesDir().getCanonicalFile();
        File base=new File(files,"voice");
        if(!base.getCanonicalFile().equals(base.getAbsoluteFile()))throw new IOException("Unsafe voice directory");
        mkdir(base);
        File destination=new File(base,MODEL_NAME);
        inside(destination,base);
        if(ready(destination))return destination;
        File staging=new File(base,MODEL_NAME+".preparing");
        deleteOwned(staging,base);mkdir(staging);
        boolean installed=false;
        try{
            MessageDigest digest;
            try{digest=MessageDigest.getInstance("SHA-256");}catch(NoSuchAlgorithmException failure){throw new IOException(failure);}
            long total=0;int entries=0;byte[] buffer=new byte[32768];
            try(InputStream asset=context.getAssets().open(MODEL_ASSET);
                DigestInputStream source=new DigestInputStream(new BufferedInputStream(asset),digest);
                ZipInputStream zip=new ZipInputStream(source)){
                ZipEntry entry;
                while((entry=zip.getNextEntry())!=null){
                    if(!recording(session))throw new IOException("Cancelled model preparation");
                    if(++entries>128)throw new IOException("Too many model entries");
                    String name=entry.getName();
                    if(!name.startsWith(MODEL_NAME+"/")||name.indexOf('\\')>=0||name.startsWith("/")
                        ||name.contains("/../")||name.endsWith("/..")||entry.getSize()>MAX_FILE_BYTES)
                        throw new IOException("Unsafe model entry");
                    File out=new File(staging,name);inside(out,staging);
                    if(entry.isDirectory())mkdir(out);
                    else{
                        if(out.exists())throw new IOException("Duplicate model entry");
                        mkdir(out.getParentFile());long length=0;
                        try(FileOutputStream output=new FileOutputStream(out)){
                            int read;
                            while((read=zip.read(buffer))!=-1){
                                if(!recording(session))throw new IOException("Cancelled model preparation");
                                length+=read;total+=read;
                                if(length>MAX_FILE_BYTES||total>MAX_MODEL_BYTES)throw new IOException("Model exceeds size limit");
                                output.write(buffer,0,read);
                            }
                        }
                    }
                    zip.closeEntry();
                }
                // ZipInputStream may leave the central directory unread. Hash the whole asset.
                while(source.read(buffer)!=-1){if(!recording(session))throw new IOException("Cancelled model preparation");}
            }
            if(!MODEL_SHA256.equals(hex(digest.digest())))throw new IOException("Model checksum mismatch");
            File unpacked=new File(staging,MODEL_NAME);
            if(!requiredFiles(unpacked))throw new IOException("Incomplete model");
            try(FileOutputStream marker=new FileOutputStream(new File(unpacked,READY_FILE))){
                marker.write(MODEL_SHA256.getBytes(StandardCharsets.US_ASCII));marker.getFD().sync();
            }
            if(!recording(session))throw new IOException("Cancelled model preparation");
            deleteOwned(destination,base);
            if(!unpacked.renameTo(destination))throw new IOException("Unable to install local model");
            installed=true;return destination;
        }finally{
            deleteOwned(staging,base);
            if(!installed&&!ready(destination))deleteOwned(destination,base);
        }
    }

    private static boolean ready(File directory) throws IOException {
        if(!requiredFiles(directory))return false;
        File marker=new File(directory,READY_FILE);if(!marker.isFile()||marker.length()!=64)return false;
        inside(marker,directory);
        byte[] bytes=new byte[64];int offset=0;
        try(FileInputStream input=new FileInputStream(marker)){
            while(offset<bytes.length){int count=input.read(bytes,offset,bytes.length-offset);if(count<0)return false;offset+=count;}
        }
        return MODEL_SHA256.equals(new String(bytes,StandardCharsets.US_ASCII));
    }

    private static boolean requiredFiles(File directory) throws IOException {
        for(String name:new String[]{"am/final.mdl","conf/model.conf","conf/mfcc.conf","graph/HCLr.fst","graph/Gr.fst"}){
            File file=new File(directory,name);inside(file,directory);if(!file.isFile()||file.length()==0)return false;
        }
        return true;
    }

    private static void mkdir(File directory) throws IOException {
        if(!directory.isDirectory()&&!directory.mkdirs())throw new IOException("Unable to create voice directory");
    }
    private static void inside(File file,File root) throws IOException {
        String parent=root.getCanonicalPath()+File.separator;
        if(!file.getCanonicalPath().startsWith(parent))throw new IOException("Unsafe voice path");
    }
    private static void deleteOwned(File file,File root) throws IOException {
        inside(file,root);if(!file.exists())return;
        if(file.isDirectory()){
            File[] children=file.listFiles();if(children==null)throw new IOException("Unable to list voice directory");
            for(File child:children)deleteOwned(child,root);
        }
        if(!file.delete())throw new IOException("Unable to clean voice directory");
    }
    private static String hex(byte[] bytes){
        char[] digits="0123456789abcdef".toCharArray();StringBuilder result=new StringBuilder(bytes.length*2);
        for(byte value:bytes){result.append(digits[(value&255)>>>4]);result.append(digits[value&15]);}
        return result.toString();
    }
}
