package com.demo.esptiming;

import android.app.Activity;
import android.content.ContentResolver;
import android.content.UriPermission;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.ParcelFileDescriptor;
import android.os.SystemClock;
import android.system.Os;
import android.system.StructStat;
import android.util.Log;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/**
 * App-side end-to-end timing for the ESP write path.
 * Main metric: monotonic (SystemClock.elapsedRealtimeNanos) duration from
 * immediately before ContentResolver.openFileDescriptor(uri, mode) to the
 * ParcelFileDescriptor return OR the exception, per attempt.
 * Capability verification (write + fstat via the returned PFD), close, CSV
 * serialization and any fixture writes happen OUTSIDE the timed interval.
 */
public class MainActivity extends Activity {
    private static final String TAG = "EspTiming";

    private static final int REQ_OPEN_TREE = 7001;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        if (getIntent().getBooleanExtra("saf_tree", false)) {
            Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
            i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                    | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION | Intent.FLAG_GRANT_PREFIX_URI_PERMISSION);
            startActivityForResult(i, REQ_OPEN_TREE);
            return;
        }
        new Thread(new Runnable() {
            @Override public void run() {
                try {
                    runFromIntent(getIntent());
                } catch (Throwable t) {
                    Log.e(TAG, "FATAL " + t.getClass().getName() + " " + String.valueOf(t.getMessage()), t);
                } finally {
                    finish();
                }
            }
        }, "EspTimingWorker").start();
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQ_OPEN_TREE) {
            new Thread(new Runnable() { @Override public void run() {
                if (resultCode == RESULT_OK && data != null && data.getData() != null) {
                    Uri tree = data.getData();
                    int flags = data.getFlags() & (Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
                    try {
                        getContentResolver().takePersistableUriPermission(tree, flags);
                        Log.i(TAG, "TREE_PERSIST_OK uri=" + tree + " flags=" + flags);
                    } catch (Throwable t) {
                        Log.e(TAG, "TREE_PERSIST_FAIL uri=" + tree, t);
                    }
                    try {
                        List<UriPermission> up = getContentResolver().getPersistedUriPermissions();
                        StringBuilder sb = new StringBuilder();
                        for (UriPermission p : up) sb.append("grant uri=").append(p.getUri())
                                .append(" read=").append(p.isReadPermission())
                                .append(" write=").append(p.isWritePermission()).append("\n");
                        File dir = getExternalFilesDir(null);
                        File f = new File(dir, "grants.txt");
                        FileOutputStream fos = new FileOutputStream(f, false);
                        fos.write(sb.toString().getBytes(StandardCharsets.UTF_8));
                        fos.close();
                        Log.i(TAG, "GRANTS_DUMP n=" + up.size());
                    } catch (Throwable t) {
                        Log.e(TAG, "GRANTS_DUMP_FAIL", t);
                    }
                }
            }}, "esp-timing-tree").start();
        }
    }

    private void runFromIntent(Intent intent) throws Exception {
        String action = intent.getStringExtra("action");
        if ("restore".equals(action)) {
            Uri uri = intent.getData();
            String content = intent.getStringExtra("content");
            String mode = intent.getStringExtra("mode") != null ? intent.getStringExtra("mode") : "w";
            String label = intent.getStringExtra("label") != null ? intent.getStringExtra("label") : "restore";
            openWriteClose(uri, mode, content);
            Log.i(TAG, "RESTORE_DONE label=" + label + " uid=" + android.os.Process.myUid());
            return;
        }
        if (!"timed".equals(action)) {
            throw new IllegalArgumentException("unknown action " + action);
        }
        Uri uri = intent.getData();
        String mode = intent.getStringExtra("mode") != null ? intent.getStringExtra("mode") : "w";
        String label = intent.getStringExtra("label") != null ? intent.getStringExtra("label") : "timed";
        String state = intent.getStringExtra("state") != null ? intent.getStringExtra("state") : "unknown";
        String content = intent.getStringExtra("content") != null ? intent.getStringExtra("content") : "0123456789ABCD";
        int warmup = intent.getIntExtra("warmup", 5);
        int record = intent.getIntExtra("record", 20);
        String outName = intent.getStringExtra("out") != null ? intent.getStringExtra("out") : "timing.csv";
        long uid = android.os.Process.myUid();

        List<String> rows = new ArrayList<>();
        int total = warmup + record;
        for (int i = 1; i <= total; i++) {
            boolean recorded = i > warmup;
            long t0 = SystemClock.elapsedRealtimeNanos();
            ParcelFileDescriptor pfd = null;
            String exception = "";
            long t1;
            try {
                pfd = getContentResolver().openFileDescriptor(uri, mode);
                t1 = SystemClock.elapsedRealtimeNanos();
            } catch (Throwable t) {
                t1 = SystemClock.elapsedRealtimeNanos();
                exception = t.getClass().getName();
            }
            long openNs = t1 - t0;
            // Capability verification AFTER the timed interval:
            String result = "PFD_NULL";
            long dev = 0, ino = 0, sizePre = 0, sizePost = 0;
            long written = 0;
            long tClose0 = 0, tClose1 = 0;
            if (pfd != null) {
                try {
                    StructStat pre = Os.fstat(pfd.getFileDescriptor());
                    dev = pre.st_dev; ino = pre.st_ino; sizePre = pre.st_size;
                    byte[] bytes = content.getBytes(StandardCharsets.UTF_8);
                    FileOutputStream out = new FileOutputStream(pfd.getFileDescriptor());
                    out.write(bytes); out.flush(); out.close();
                    StructStat post = Os.fstat(pfd.getFileDescriptor());
                    sizePost = post.st_size;
                    written = bytes.length;
                    result = "WRITE_OK";
                } catch (Throwable t) {
                    result = "VERIFY_FAIL:" + t.getClass().getName();
                } finally {
                    tClose0 = SystemClock.elapsedRealtimeNanos();
                    closeQuietly(pfd);
                    tClose1 = SystemClock.elapsedRealtimeNanos();
                }
            } else {
                result = "OPEN_FAIL";
            }
            if (recorded) {
                rows.add(String.join(",",
                        String.valueOf(i - warmup),
                        state,
                        label,
                        String.valueOf(t0),
                        String.valueOf(t1),
                        String.valueOf(openNs),
                        result,
                        exception,
                        String.valueOf(dev),
                        String.valueOf(ino),
                        String.valueOf(sizePre),
                        String.valueOf(sizePost),
                        String.valueOf(written),
                        String.valueOf(tClose0),
                        String.valueOf(tClose1),
                        String.valueOf(tClose0 > 0 ? tClose1 - tClose0 : 0),
                        String.valueOf(uid)));
            }
        }
        // CSV serialization once, fully outside any timed interval:
        File dir = new File(getExternalFilesDir(null), "timing");
        if (!dir.exists() && !dir.mkdirs()) {
            throw new IllegalStateException("mkdir failed " + dir);
        }
        StringBuilder sb = new StringBuilder();
        sb.append("trial,state,label,t0_ns,t1_ns,open_ns,result,exception,dev,ino,size_pre,size_post,bytes_written,t_close0_ns,t_close1_ns,close_ns,uid\n");
        for (String r : rows) sb.append(r).append('\n');
        File out = new File(dir, outName);
        try (FileOutputStream fos = new FileOutputStream(out, false)) {
            fos.write(sb.toString().getBytes(StandardCharsets.UTF_8));
            fos.flush();
        }
        Log.i(TAG, "TIMED_DONE state=" + state + " label=" + label
                + " warmup=" + warmup + " recorded=" + rows.size()
                + " uid=" + uid + " out=" + out.getAbsolutePath());
    }

    private void openWriteClose(Uri uri, String mode, String content) throws Exception {
        ParcelFileDescriptor pfd = getContentResolver().openFileDescriptor(uri, mode);
        if (pfd == null) throw new IllegalStateException("null pfd");
        try {
            FileOutputStream out = new FileOutputStream(pfd.getFileDescriptor());
            out.write(content.getBytes(StandardCharsets.UTF_8));
            out.flush();
            out.close();
        } finally {
            closeQuietly(pfd);
        }
    }

    private static void closeQuietly(ParcelFileDescriptor pfd) {
        try { if (pfd != null) pfd.close(); } catch (Throwable ignored) {}
    }
}
