package com.demo.espafdtestb;

import android.app.Activity;
import android.content.ContentProviderClient;
import android.content.ContentValues;
import android.content.Intent;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.os.ParcelFileDescriptor;
import android.provider.MediaStore;
import android.system.Os;
import android.system.StructStat;
import android.util.Log;

import java.io.InputStream;
import java.security.MessageDigest;

public class MainActivity extends Activity {
    private static final String TAG = "CDAC27_PATH";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Intent intent = getIntent();
        if (intent == null) { finish(); return; }
        String cmd = intent.getStringExtra("cmd");
        if (cmd == null) { finish(); return; }
        try {
            if ("make_image".equals(cmd)) {
                makeImage(intent.getStringExtra("name"));
            } else if ("read_cr".equals(cmd)) {
                readCr(intent.getStringExtra("uri"), intent.getStringExtra("marker"));
            } else if ("read_cpc".equals(cmd)) {
                readCpc(intent.getStringExtra("uri"), intent.getStringExtra("marker"));
            } else if ("query_state".equals(cmd)) {
                queryState(intent.getStringExtra("uri"));
            }
        } catch (Throwable t) {
            Log.i(TAG, "RESULT fail cmd=" + cmd + " err=" + t.getClass().getSimpleName() + ":" + t.getMessage());
        }
        finish();
    }

    private static String sha256Hex(byte[] b) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        byte[] d = md.digest(b);
        StringBuilder sb = new StringBuilder();
        for (byte x : d) sb.append(String.format("%02x", x));
        return sb.toString();
    }

    private static void logRead(String kind, Uri u, ParcelFileDescriptor pfd, String marker) throws Exception {
        StructStat st = Os.fstat(pfd.getFileDescriptor());
        java.io.ByteArrayOutputStream bos = new java.io.ByteArrayOutputStream();
        try (InputStream in = new ParcelFileDescriptor.AutoCloseInputStream(pfd)) {
            byte[] chunk = new byte[4096];
            int c;
            while ((c = in.read(chunk)) > 0) bos.write(chunk, 0, c);
        }
        byte[] all = bos.toByteArray();
        boolean markerPresent = new String(all, "ISO-8859-1").contains(marker);
        Log.i(TAG, "READ_" + kind + " ok uri=" + u + " bytes=" + all.length
                + " dev=" + (st.st_dev >>> 8) + ":" + (st.st_dev & 0xff)
                + " ino=" + st.st_ino
                + " marker=" + marker + " marker_present=" + markerPresent
                + " sha256=" + sha256Hex(all));
    }

    // Chain 1: ContentResolver.openFileDescriptor(uri,"r")
    private void readCr(String uriStr, String marker) throws Exception {
        Uri u = Uri.parse(uriStr);
        ParcelFileDescriptor pfd = getContentResolver().openFileDescriptor(u, "r");
        logRead("CR", u, pfd, marker);
    }

    // Chain 2: ContentProviderClient.openFile(uri,"r")
    private void readCpc(String uriStr, String marker) throws Exception {
        Uri u = Uri.parse(uriStr);
        ContentProviderClient cpc = getContentResolver().acquireContentProviderClient(u);
        if (cpc == null) throw new IllegalStateException("acquireContentProviderClient null");
        try {
            ParcelFileDescriptor pfd = cpc.openFile(u, "r");
            logRead("CPC", u, pfd, marker);
        } finally {
            cpc.close();
        }
    }

    private void makeImage(String name) throws Exception {
        String asset = "image1".equals(name) ? "image1.jpg" : "image2.jpg";
        String marker = "image1".equals(name) ? "CDAC25GPSMARK_AAAA" : "CDAC25GPSMARK_BBBB";
        byte[] bytes;
        try (InputStream in = getAssets().open(asset)) {
            bytes = new byte[in.available()];
            int off = 0, n;
            while (off < bytes.length && (n = in.read(bytes, off, bytes.length - off)) > 0) off += n;
        }
        ContentValues cv = new ContentValues();
        cv.put(MediaStore.MediaColumns.DISPLAY_NAME, name + ".jpg");
        cv.put(MediaStore.MediaColumns.MIME_TYPE, "image/jpeg");
        cv.put(MediaStore.MediaColumns.RELATIVE_PATH, "Pictures/");
        Uri u = getContentResolver().insert(
                MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY), cv);
        if (u == null) { Log.i(TAG, "MAKE_IMAGE fail insert-null name=" + name); return; }
        java.io.OutputStream os = getContentResolver().openOutputStream(u);
        os.write(bytes);
        os.close();
        Cursor c = getContentResolver().query(u, new String[]{
                MediaStore.MediaColumns._ID, MediaStore.MediaColumns.OWNER_PACKAGE_NAME,
                MediaStore.MediaColumns.DATA, MediaStore.MediaColumns.SIZE,
                MediaStore.MediaColumns.IS_PENDING}, null, null, null);
        StringBuilder sb = new StringBuilder("MAKE_IMAGE ok name=" + name + " uri=" + u + " marker=" + marker + " bytes=" + bytes.length);
        if (c != null && c.moveToFirst()) {
            sb.append(" id=").append(c.getLong(0))
              .append(" owner=").append(c.getString(1))
              .append(" data=").append(c.getString(2))
              .append(" size=").append(c.getLong(3))
              .append(" is_pending=").append(c.getInt(4));
            c.close();
        }
        Log.i(TAG, sb.toString());
    }

    private void queryState(String uriStr) throws Exception {
        Uri u = Uri.parse(uriStr);
        Cursor c = getContentResolver().query(u, new String[]{
                MediaStore.MediaColumns._ID, MediaStore.MediaColumns.OWNER_PACKAGE_NAME,
                MediaStore.MediaColumns.DATA, MediaStore.MediaColumns.SIZE,
                MediaStore.MediaColumns.IS_PENDING}, null, null, null);
        if (c != null && c.moveToFirst()) {
            Log.i(TAG, "STATE uri=" + u + " id=" + c.getLong(0) + " owner=" + c.getString(1)
                    + " data=" + c.getString(2) + " size=" + c.getLong(3) + " is_pending=" + c.getInt(4));
            c.close();
        } else {
            Log.i(TAG, "STATE fail uri=" + u);
        }
    }
}
