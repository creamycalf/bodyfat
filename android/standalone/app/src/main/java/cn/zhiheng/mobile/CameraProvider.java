package cn.zhiheng.mobile;

import android.content.*;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import java.io.*;

/** Grants the camera access only to a randomly named image in our camera cache. */
public class CameraProvider extends ContentProvider {
    public boolean onCreate(){return true;}
    private File image(Uri uri) throws FileNotFoundException {
        String name=uri.getLastPathSegment();
        if(!uri.getPath().equals("/"+name)||name==null||!name.matches("[a-f0-9-]{36}\\.jpg"))throw new FileNotFoundException();
        return new File(new File(getContext().getCacheDir(),"camera"),name);
    }
    public ParcelFileDescriptor openFile(Uri uri,String mode) throws FileNotFoundException {
        return ParcelFileDescriptor.open(image(uri),ParcelFileDescriptor.parseMode(mode));
    }
    public String getType(Uri uri){return "image/jpeg";}
    public Cursor query(Uri uri,String[] projection,String selection,String[] args,String sort){
        try{File f=image(uri);String[] cols=projection==null?new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE}:projection;
            MatrixCursor c=new MatrixCursor(cols);Object[] row=new Object[cols.length];
            for(int i=0;i<cols.length;i++)row[i]=OpenableColumns.DISPLAY_NAME.equals(cols[i])?f.getName():OpenableColumns.SIZE.equals(cols[i])?f.length():null;
            c.addRow(row);return c;
        }catch(FileNotFoundException e){return null;}
    }
    public Uri insert(Uri u,ContentValues v){throw new UnsupportedOperationException();}
    public int update(Uri u,ContentValues v,String s,String[] a){throw new UnsupportedOperationException();}
    public int delete(Uri u,String s,String[] a){throw new UnsupportedOperationException();}
}
