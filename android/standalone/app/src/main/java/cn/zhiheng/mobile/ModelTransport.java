package cn.zhiheng.mobile;
import org.json.JSONObject;
import java.net.URL;
import java.net.HttpURLConnection;
import java.io.*;
import java.util.Iterator;
import javax.net.ssl.HttpsURLConnection;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;

/** Android system trust store; no certificate or hostname bypass. */
public final class ModelTransport {
    private static final ScheduledExecutorService deadlines=Executors.newSingleThreadScheduledExecutor(r->{
        Thread t=new Thread(r,"model-deadline");t.setDaemon(true);return t;
    });
    public static String request(String url,String headersJson,String body,int timeoutMs) throws Exception {
        JSONObject result=new JSONObject();HttpURLConnection connection=null;
        ScheduledFuture<?> deadline=null;AtomicBoolean expired=new AtomicBoolean(false);
        try {
            URL endpoint=new URL(url);
            boolean approvedTest="http".equals(endpoint.getProtocol())&&"47.110.38.211".equals(endpoint.getHost())&&endpoint.getPort()==8080;
            if(!"https".equals(endpoint.getProtocol())&&!approvedTest)throw new IOException("HTTPS required");
            connection=(HttpURLConnection)endpoint.openConnection();
            final HttpURLConnection active=connection;
            deadline=deadlines.schedule(()->{expired.set(true);active.disconnect();},Math.max(1,timeoutMs),TimeUnit.MILLISECONDS);
            connection.setInstanceFollowRedirects(false);
            connection.setConnectTimeout(Math.min(timeoutMs,20000));connection.setReadTimeout(timeoutMs);
            connection.setRequestMethod("POST");connection.setDoOutput(true);
            JSONObject headers=new JSONObject(headersJson);
            for(Iterator<String> it=headers.keys();it.hasNext();){String key=it.next();connection.setRequestProperty(key,headers.getString(key));}
            byte[] bytes=body.getBytes("UTF-8");connection.setFixedLengthStreamingMode(bytes.length);
            try(OutputStream out=connection.getOutputStream()){out.write(bytes);}
            int status=connection.getResponseCode();result.put("status",status);
            InputStream stream=status>=400?connection.getErrorStream():connection.getInputStream();
            ByteArrayOutputStream out=new ByteArrayOutputStream();
            if(stream!=null)try(InputStream in=stream){byte[] buffer=new byte[8192];int n;while((n=in.read(buffer))!=-1){if(out.size()+n>8*1024*1024)throw new IOException("response_too_large");out.write(buffer,0,n);}}
            result.put("body",out.toString("UTF-8"));
            if(expired.get())throw new java.net.SocketTimeoutException();
        }catch(Exception e){
            String code=expired.get()?"AI_TIMEOUT":e instanceof java.net.UnknownHostException?"AI_DNS_FAILED":e instanceof javax.net.ssl.SSLException?"AI_TLS_FAILED":e instanceof java.net.SocketTimeoutException?"AI_TIMEOUT":"AI_CONNECTION_FAILED";
            result=new JSONObject();result.put("error",code);
        }finally{if(deadline!=null)deadline.cancel(false);if(connection!=null)connection.disconnect();}
        return result.toString();
    }
}
