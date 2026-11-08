package com.demo.espafdtest;

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

import java.io.FileOutputStream;
import java.io.InputStream;
import java.security.MessageDigest;

public class MainActivity extends Activity {
    private static final String TAG = "CDAC27_PATH";
    private static final String X_MARKER = "CDAC25GPSMARK_AAAA";

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
            } else if ("write_mp".equals(cmd)) {
                writeMp(intent.getStringExtra("uri"), intent.getStringExtra("token"));
            } else if ("restore_mp".equals(cmd)) {
                restoreMp(intent.getStringExtra("uri"));
            } else if ("write_diag".equals(cmd)) {
                writeDiag(intent.getStringExtra("uri"), Integer.parseInt(intent.getStringExtra("n")));
            } else if ("restore_diag".equals(cmd)) {
                restoreDiag(intent.getStringExtra("uri"));
            } else if ("query_state".equals(cmd)) {
                queryState(intent.getStringExtra("uri"));
            }
        } catch (Throwable t) {
            Log.i(TAG, "RESULT fail cmd=" + cmd + " err=" + t.getClass().getSimpleName() + ":" + t.getMessage());
        }
        finish();
    }

    private byte[] readAssetBytes(String name) throws Exception {
        InputStream in = getAssets().open(name);
        byte[] buf = new byte[in.available()];
        int off = 0, n;
        while (off < buf.length && (n = in.read(buf, off, buf.length - off)) > 0) off += n;
        in.close();
        return buf;
    }

    private static int indexOf(byte[] hay, byte[] needle) {
        outer: for (int i = 0; i + needle.length <= hay.length; i++) {
            for (int j = 0; j < needle.length; j++) {
                if (hay[i + j] != needle[j]) continue outer;
            }
            return i;
        }
        return -1;
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

    private void readCr(String uriStr, String marker) throws Exception {
        Uri u = Uri.parse(uriStr);
        ParcelFileDescriptor pfd = getContentResolver().openFileDescriptor(u, "r");
        logRead("CR", u, pfd, marker);
    }

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

    private byte[] payloadWithToken(String asset, String token) throws Exception {
        byte[] orig = readAssetBytes(asset);
        byte[] payload = orig.clone();
        byte[] marker = X_MARKER.getBytes("ISO-8859-1");
        int idx = indexOf(payload, marker);
        if (idx < 0) throw new IllegalStateException("marker not found in asset " + asset);
        byte[] tok = token.getBytes("ISO-8859-1");
        for (int i = 0; i < tok.length && idx + 15 + i < payload.length; i++) {
            payload[idx + 15 + i] = tok[i];
        }
        return payload;
    }

    private void writeMp(String uriStr, String token) throws Exception {
        Uri u = Uri.parse(uriStr);
        byte[] payload = payloadWithToken("image1.jpg", token);
        ParcelFileDescriptor pfd = getContentResolver().openFileDescriptor(u, "w");
        if (pfd == null) { Log.i(TAG, "WRITE_MP fail null-pfd uri=" + u); return; }
        StructStat pre = Os.fstat(pfd.getFileDescriptor());
        FileOutputStream out = new FileOutputStream(pfd.getFileDescriptor());
        out.write(payload); out.flush();
        StructStat post = Os.fstat(pfd.getFileDescriptor());
        pfd.close();
        Log.i(TAG, "WRITE_MP ok uri=" + u + " token=" + token
                + " pfd=1 dev=" + (pre.st_dev >>> 8) + ":" + (pre.st_dev & 0xff)
                + " ino=" + pre.st_ino
                + " size_pre=" + pre.st_size + " size_post=" + post.st_size
                + " written=" + payload.length + " sha256=" + sha256Hex(payload));
    }

    private void restoreMp(String uriStr) throws Exception {
        Uri u = Uri.parse(uriStr);
        byte[] orig = readAssetBytes("image1.jpg");
        ParcelFileDescriptor pfd = getContentResolver().openFileDescriptor(u, "w");
        if (pfd == null) { Log.i(TAG, "RESTORE_MP fail null-pfd uri=" + u); return; }
        FileOutputStream out = new FileOutputStream(pfd.getFileDescriptor());
        out.write(orig); out.flush();
        StructStat post = Os.fstat(pfd.getFileDescriptor());
        pfd.close();
        Log.i(TAG, "RESTORE_MP ok uri=" + u + " size_post=" + post.st_size
                + " written=" + orig.length + " sha256=" + sha256Hex(orig));
    }

    private void writeDiag(String uriStr, int n) throws Exception {
        Uri u = Uri.parse(uriStr);
        byte[] payload = new byte[n];
        for (int i = 0; i < n; i++) payload[i] = (byte) 'D';
        ParcelFileDescriptor pfd = getContentResolver().openFileDescriptor(u, "w");
        if (pfd == null) { Log.i(TAG, "WRITE_DIAG fail null-pfd uri=" + u); return; }
        StructStat pre = Os.fstat(pfd.getFileDescriptor());
        FileOutputStream out = new FileOutputStream(pfd.getFileDescriptor());
        out.write(payload); out.flush();
        StructStat post = Os.fstat(pfd.getFileDescriptor());
        pfd.close();
        Log.i(TAG, "WRITE_DIAG ok uri=" + u + " n=" + n
                + " dev=" + (pre.st_dev >>> 8) + ":" + (pre.st_dev & 0xff)
                + " ino=" + pre.st_ino
                + " size_pre=" + pre.st_size + " size_post=" + post.st_size
                + " written=" + n);
    }

    private void restoreDiag(String uriStr) throws Exception {
        Uri u = Uri.parse(uriStr);
        byte[] orig = readAssetBytes("image2.jpg");
        ParcelFileDescriptor pfd = getContentResolver().openFileDescriptor(u, "w");
        if (pfd == null) { Log.i(TAG, "RESTORE_DIAG fail null-pfd uri=" + u); return; }
        FileOutputStream out = new FileOutputStream(pfd.getFileDescriptor());
        out.write(orig); out.flush();
        StructStat post = Os.fstat(pfd.getFileDescriptor());
        pfd.close();
        Log.i(TAG, "RESTORE_DIAG ok uri=" + u + " size_post=" + post.st_size
                + " written=" + orig.length + " sha256=" + sha256Hex(orig));
    }

    private void makeImage(String name) throws Exception {
        String asset = "image1".equals(name) ? "image1.jpg" : "image2.jpg";
        String marker = "image1".equals(name) ? "CDAC25GPSMARK_AAAA" : "CDAC25GPSMARK_BBBB";
        byte[] bytes = readAssetBytes(asset);
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
