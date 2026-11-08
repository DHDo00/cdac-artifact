package com.android.server.iguard;

import android.content.Context;
import android.os.Binder;
import android.os.Environment;
import android.os.Parcel;
import android.os.RemoteException;
import android.util.Slog;

import com.android.server.SystemService;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;

public final class IguardDemoService extends SystemService {
    private static final String TAG = "IguardDemoService";
    public static final String SERVICE_NAME = "iguard_demo";

    private static final String SECRET_DIR_NAME = "iguard_demo";
    private static final String SECRET_FILE_NAME = "secret.txt";
    private static final String DEFAULT_SECRET_CONTENT = "I-GUARD DEMO SECRET\n";

    private static final String PUBLIC_FILE_NAME = "public.txt";
    private static final String DEFAULT_PUBLIC_CONTENT = "I-GUARD PUBLIC DATA\n";
    private static final String UPDATED_PUBLIC_CONTENT = "I-GUARD PUBLIC UPDATED\n";

    private final Object mLock = new Object();

    private static boolean legacyReportDisabled(int uid, int pid, String service, String operation) {
        return false;
    }

    private static boolean legacyInvalidateDisabled(String service, String operation) {
        return false;
    }

    private final IIguardDemoService.Stub mBinder = new IIguardDemoService.Stub() {
        @Override
        public boolean onTransact(int code, Parcel data, Parcel reply, int flags)
                throws RemoteException {
            Slog.i(TAG, "onTransact() code=" + code
                    + " flags=" + flags
                    + " callingUid=" + Binder.getCallingUid()
                    + " callingPid=" + Binder.getCallingPid());
            return super.onTransact(code, data, reply, flags);
        }

        @Override
        public String ping() throws RemoteException {
            Slog.i(TAG, "ping()");
            return "IguardDemoService alive";
        }

        @Override
        public String readSecret() throws RemoteException {
            final int callingUid = Binder.getCallingUid();
            final int callingPid = Binder.getCallingPid();
            final String opName = "readSecret";

            synchronized (mLock) {
                final boolean nativeOk = legacyReportDisabled(
                        callingUid, callingPid, SERVICE_NAME, opName);

                Slog.i(TAG, "nativeReportCaller() => " + nativeOk
                        + " callerUid=" + callingUid
                        + " callerPid=" + callingPid);

                try {
                    final File secretFile = getOrCreateSecretFileLocked();
                    final String content = readFileAsString(secretFile);

                    Slog.i(TAG, "readSecret() callerUid=" + callingUid
                            + " callerPid=" + callingPid
                            + " path=" + secretFile.getAbsolutePath()
                            + " bytes=" + content.length());

                    return content;
                } catch (IOException e) {
                    Slog.e(TAG, "readSecret() failed for callerUid=" + callingUid
                            + " callerPid=" + callingPid, e);
                    return "ERROR: " + e.getMessage();
                } finally {
                    final boolean invalidateOk = legacyInvalidateDisabled(
                            SERVICE_NAME, opName);
                    Slog.i(TAG, "nativeInvalidateCaller() => " + invalidateOk
                            + " service=" + SERVICE_NAME
                            + " operation=" + opName);
                }
            }
        }

        @Override
        public String readPublic() throws RemoteException {
            final int callingUid = Binder.getCallingUid();
            final int callingPid = Binder.getCallingPid();
            final String opName = "readPublic";

            synchronized (mLock) {
                final boolean nativeOk = legacyReportDisabled(
                        callingUid, callingPid, SERVICE_NAME, opName);

                Slog.i(TAG, "nativeReportCaller() => " + nativeOk
                        + " callerUid=" + callingUid
                        + " callerPid=" + callingPid
                        + " service=" + SERVICE_NAME
                        + " operation=" + opName);

                try {
                    final File publicFile = getOrCreatePublicFileLocked();
                    final String content = readFileAsString(publicFile);

                    Slog.i(TAG, "readPublic() callerUid=" + callingUid
                            + " callerPid=" + callingPid
                            + " path=" + publicFile.getAbsolutePath()
                            + " bytes=" + content.length());

                    return content;
                } catch (IOException e) {
                    Slog.e(TAG, "readPublic() failed for callerUid=" + callingUid
                            + " callerPid=" + callingPid, e);
                    return "ERROR: " + e.getMessage();
                } finally {
                    final boolean invalidateOk = legacyInvalidateDisabled(
                            SERVICE_NAME, opName);
                    Slog.i(TAG, "nativeInvalidateCaller() => " + invalidateOk
                            + " service=" + SERVICE_NAME
                            + " operation=" + opName);
                }
            }
        }

        /*
         * Plain service baseline for performance evaluation.
         *
         * This method intentionally does NOT call:
         *   - IguardNative.nativeReportCaller()
         *   - IguardNative.nativeInvalidateCaller()
         *
         * It reuses the same public.txt object and the same file-read helper as
         * readPublic(), but removes I-Guard context publication/invalidation
         * from the service path. This is used to measure the service-only file
         * read cost and to separate plain service overhead from I-Guard overhead.
         */
        @Override
        public String readPublicPlain() throws RemoteException {
            final int callingUid = Binder.getCallingUid();
            final int callingPid = Binder.getCallingPid();

            synchronized (mLock) {
                try {
                    final File publicFile = getOrCreatePublicFileLocked();
                    final String content = readFileAsString(publicFile);

                    Slog.i(TAG, "readPublicPlain() callerUid=" + callingUid
                            + " callerPid=" + callingPid
                            + " path=" + publicFile.getAbsolutePath()
                            + " bytes=" + content.length()
                            + " plainBaseline=true"
                            + " reportCaller=false"
                            + " invalidateCaller=false");

                    return content;
                } catch (IOException e) {
                    Slog.e(TAG, "readPublicPlain() failed for callerUid=" + callingUid
                            + " callerPid=" + callingPid, e);
                    return "ERROR: " + e.getMessage();
                }
            }
        }

        @Override
        public String readByPath(String path) throws RemoteException {
            final int callingUid = Binder.getCallingUid();
            final int callingPid = Binder.getCallingPid();
            final String opName = "readByPath";
            final String requestedPath = path;

            synchronized (mLock) {
                final boolean nativeOk = legacyReportDisabled(
                        callingUid, callingPid, SERVICE_NAME, opName);

                Slog.i(TAG, "nativeReportCaller() => " + nativeOk
                        + " callerUid=" + callingUid
                        + " callerPid=" + callingPid
                        + " service=" + SERVICE_NAME
                        + " operation=" + opName
                        + " requestedPath=" + requestedPath);

                try {
                    if (requestedPath == null || requestedPath.isEmpty()) {
                        return "ERROR: empty path";
                    }

                    final File targetFile = new File(requestedPath);
                    final String content = readFileAsString(targetFile);

                    Slog.i(TAG, "readByPath() callerUid=" + callingUid
                            + " callerPid=" + callingPid
                            + " requestedPath=" + requestedPath
                            + " canonicalPath=" + targetFile.getAbsolutePath()
                            + " bytes=" + content.length());

                    return content;
                } catch (IOException e) {
                    Slog.e(TAG, "readByPath() failed for callerUid=" + callingUid
                            + " callerPid=" + callingPid
                            + " requestedPath=" + requestedPath, e);
                    return "ERROR: " + e.getMessage();
                } finally {
                    final boolean invalidateOk = legacyInvalidateDisabled(
                            SERVICE_NAME, opName);
                    Slog.i(TAG, "nativeInvalidateCaller() => " + invalidateOk
                            + " service=" + SERVICE_NAME
                            + " operation=" + opName);
                }
            }
        }

        @Override
        public String writePublic() throws RemoteException {
            final int callingUid = Binder.getCallingUid();
            final int callingPid = Binder.getCallingPid();
            final String opName = "writePublic";

            synchronized (mLock) {
                final boolean nativeOk = legacyReportDisabled(
                        callingUid, callingPid, SERVICE_NAME, opName);

                Slog.i(TAG, "nativeReportCaller() => " + nativeOk
                        + " callerUid=" + callingUid
                        + " callerPid=" + callingPid
                        + " service=" + SERVICE_NAME
                        + " operation=" + opName);

                try {
                    final File publicFile = getOrCreatePublicFileLocked();
                    writeStringToFile(publicFile, UPDATED_PUBLIC_CONTENT);

                    Slog.i(TAG, "writePublic() callerUid=" + callingUid
                            + " callerPid=" + callingPid
                            + " path=" + publicFile.getAbsolutePath()
                            + " bytes=" + UPDATED_PUBLIC_CONTENT.length());

                    return "WRITE_PUBLIC_OK";
                } catch (IOException e) {
                    Slog.e(TAG, "writePublic() failed for callerUid=" + callingUid
                            + " callerPid=" + callingPid, e);
                    return "ERROR: " + e.getMessage();
                } finally {
                    final boolean invalidateOk = legacyInvalidateDisabled(
                            SERVICE_NAME, opName);
                    Slog.i(TAG, "nativeInvalidateCaller() => " + invalidateOk
                            + " service=" + SERVICE_NAME
                            + " operation=" + opName);
                }
            }
        }

        @Override
        public String toctouWritePublicRace(int rounds) throws RemoteException {
            final int callingUid = Binder.getCallingUid();
            final int callingPid = Binder.getCallingPid();
            final String opName = "toctouWritePublicRace";
            final int safeRounds = Math.max(1, Math.min(rounds, 10000));

            final File baseDir = new File(Environment.getDataSystemDirectory(), SECRET_DIR_NAME);
            final File publicFile = new File(baseDir, PUBLIC_FILE_NAME);
            final File swapFile = new File(baseDir, "public.swap");
            final File tmpFile = new File(baseDir, "public.tmp");

            synchronized (mLock) {
                try {
                    if (!baseDir.exists() && !baseDir.mkdirs()) {
                        throw new IOException("Failed to create dir: "
                                + baseDir.getAbsolutePath());
                    }

                    if (tmpFile.exists() && !tmpFile.delete()) {
                        Slog.w(TAG, "T5 failed to delete stale tmp: "
                                + tmpFile.getAbsolutePath());
                    }

                    if (!publicFile.exists()) {
                        writeStringToFile(publicFile, DEFAULT_PUBLIC_CONTENT);
                    }

                    if (!swapFile.exists()) {
                        writeStringToFile(swapFile, "I-GUARD PUBLIC SWAP DATA\n");
                    }

                    Slog.i(TAG, "T5 prepared files"
                            + " public=" + publicFile.getAbsolutePath()
                            + " swap=" + swapFile.getAbsolutePath()
                            + " rounds=" + safeRounds
                            + " callerUid=" + callingUid
                            + " callerPid=" + callingPid);
                } catch (IOException e) {
                    Slog.e(TAG, "T5 prepare failed", e);
                    return "T5_PREPARE_ERROR: " + e.getMessage();
                }
            }

            final java.util.concurrent.atomic.AtomicBoolean running =
                    new java.util.concurrent.atomic.AtomicBoolean(true);
            final java.util.concurrent.atomic.AtomicInteger renameOk =
                    new java.util.concurrent.atomic.AtomicInteger(0);
            final java.util.concurrent.atomic.AtomicInteger renameFail =
                    new java.util.concurrent.atomic.AtomicInteger(0);
            final java.util.concurrent.atomic.AtomicInteger openOk =
                    new java.util.concurrent.atomic.AtomicInteger(0);
            final java.util.concurrent.atomic.AtomicInteger openDenied =
                    new java.util.concurrent.atomic.AtomicInteger(0);
            final java.util.concurrent.atomic.AtomicInteger openMiss =
                    new java.util.concurrent.atomic.AtomicInteger(0);
            final java.util.concurrent.atomic.AtomicInteger openOther =
                    new java.util.concurrent.atomic.AtomicInteger(0);

            final Thread renamer = new Thread(() -> {
                while (running.get()) {
                    try {
                        boolean ok = false;

                        if (publicFile.exists() && swapFile.exists() && !tmpFile.exists()) {
                            final boolean a = publicFile.renameTo(tmpFile);
                            final boolean b = a && swapFile.renameTo(publicFile);
                            final boolean c = b && tmpFile.renameTo(swapFile);
                            ok = a && b && c;

                            if (!ok) {
                                if (tmpFile.exists() && !publicFile.exists()) {
                                    // Best-effort recovery so the next round has a public.txt again.
                                    tmpFile.renameTo(publicFile);
                                }
                            }
                        }

                        if (ok) {
                            renameOk.incrementAndGet();
                        } else {
                            renameFail.incrementAndGet();
                        }

                        Thread.yield();
                    } catch (Throwable t) {
                        renameFail.incrementAndGet();
                        Slog.w(TAG, "T5 renamer exception", t);
                    }
                }
            }, "IguardT5Renamer");

            final Thread opener = new Thread(() -> {
                for (int i = 0; i < safeRounds; i++) {
                    final boolean nativeOk = legacyReportDisabled(
                            callingUid, callingPid, SERVICE_NAME, opName);

                    if (!nativeOk) {
                        Slog.w(TAG, "T5 nativeReportCaller failed"
                                + " i=" + i
                                + " callerUid=" + callingUid
                                + " callerPid=" + callingPid);
                    }

                    try {
                        final java.io.FileDescriptor fd = android.system.Os.open(
                                publicFile.getAbsolutePath(),
                                android.system.OsConstants.O_WRONLY,
                                0);
                        android.system.Os.close(fd);
                        openOk.incrementAndGet();
                    } catch (android.system.ErrnoException e) {
                        if (e.errno == android.system.OsConstants.EACCES) {
                            openDenied.incrementAndGet();
                        } else if (e.errno == android.system.OsConstants.ENOENT) {
                            openMiss.incrementAndGet();
                        } else {
                            openOther.incrementAndGet();
                            Slog.w(TAG, "T5 open errno=" + e.errno + " at i=" + i, e);
                        }
                    } catch (Throwable t) {
                        openOther.incrementAndGet();
                        Slog.w(TAG, "T5 open exception at i=" + i, t);
                    } finally {
                        final boolean invalidateOk = legacyInvalidateDisabled(
                                SERVICE_NAME, opName);
                        if (!invalidateOk) {
                            Slog.w(TAG, "T5 nativeInvalidateCaller failed"
                                    + " callerUid=" + callingUid
                                    + " callerPid=" + callingPid);
                        }
                    }
                }

                running.set(false);
            }, "IguardT5Opener");

            final long startNs = System.nanoTime();

            renamer.start();
            opener.start();

            try {
                opener.join();
                running.set(false);
                renamer.join(1000);
            } catch (InterruptedException e) {
                running.set(false);
                Thread.currentThread().interrupt();
                Slog.e(TAG, "T5 interrupted", e);
                return "T5_INTERRUPTED";
            }

            final long elapsedNs = System.nanoTime() - startNs;

            final String result = "T5_TOCTOU_DONE"
                    + " rounds=" + safeRounds
                    + " openOk=" + openOk.get()
                    + " openDenied=" + openDenied.get()
                    + " openMiss=" + openMiss.get()
                    + " openOther=" + openOther.get()
                    + " renameOk=" + renameOk.get()
                    + " renameFail=" + renameFail.get()
                    + " elapsedNs=" + elapsedNs
                    + " callerUid=" + callingUid
                    + " callerPid=" + callingPid;

            Slog.i(TAG, result);
            return result;
        }

        @Override
        public String reportOnlyThenReturn() throws RemoteException {
            final int callingUid = Binder.getCallingUid();
            final int callingPid = Binder.getCallingPid();
            final String opName = "reportOnlyThenReturn";

            synchronized (mLock) {
                final boolean nativeOk = legacyReportDisabled(
                        callingUid, callingPid, SERVICE_NAME, opName);

                Slog.i(TAG, "nativeReportCaller() => " + nativeOk
                        + " callerUid=" + callingUid
                        + " callerPid=" + callingPid
                        + " service=" + SERVICE_NAME
                        + " operation=" + opName);

                try {
                    Slog.i(TAG, "reportOnlyThenReturn() callerUid=" + callingUid
                            + " callerPid=" + callingPid
                            + " no file open will be performed");
                    return "REPORT_ONLY_OK";
                } finally {
                    final boolean invalidateOk = legacyInvalidateDisabled(
                            SERVICE_NAME, opName);
                    Slog.i(TAG, "nativeInvalidateCaller() => " + invalidateOk
                            + " service=" + SERVICE_NAME
                            + " operation=" + opName);
                }
            }
        }

        @Override
        public String reportThenThrow() throws RemoteException {
            final int callingUid = Binder.getCallingUid();
            final int callingPid = Binder.getCallingPid();
            final String opName = "reportThenThrow";

            synchronized (mLock) {
                final boolean nativeOk = legacyReportDisabled(
                        callingUid, callingPid, SERVICE_NAME, opName);

                Slog.i(TAG, "nativeReportCaller() => " + nativeOk
                        + " callerUid=" + callingUid
                        + " callerPid=" + callingPid
                        + " service=" + SERVICE_NAME
                        + " operation=" + opName);

                try {
                    Slog.i(TAG, "reportThenThrow() callerUid=" + callingUid
                            + " callerPid=" + callingPid
                            + " throwing expected test exception");
                    throw new SecurityException("expected reportThenThrow test exception");
                } finally {
                    final boolean invalidateOk = legacyInvalidateDisabled(
                            SERVICE_NAME, opName);
                    Slog.i(TAG, "nativeInvalidateCaller() => " + invalidateOk
                            + " service=" + SERVICE_NAME
                            + " operation=" + opName);
                }
            }
        }
    };

    public IguardDemoService(Context context) {
        super(context);
    }

    @Override
    public void onStart() {
        Slog.i(TAG, "Starting IguardDemoService");
        publishBinderService(SERVICE_NAME, mBinder);
        Slog.i(TAG, "IguardDemoService published as: " + SERVICE_NAME);
    }

    private File getOrCreateSecretFileLocked() throws IOException {
        final File baseDir = new File(Environment.getDataSystemDirectory(), SECRET_DIR_NAME);
        if (!baseDir.exists() && !baseDir.mkdirs()) {
            throw new IOException("Failed to create dir: " + baseDir.getAbsolutePath());
        }

        final File secretFile = new File(baseDir, SECRET_FILE_NAME);
        if (!secretFile.exists()) {
            writeStringToFile(secretFile, DEFAULT_SECRET_CONTENT);
            Slog.i(TAG, "Created demo secret file: " + secretFile.getAbsolutePath());
        }

        return secretFile;
    }

    private File getOrCreatePublicFileLocked() throws IOException {
        final File baseDir = new File(Environment.getDataSystemDirectory(), SECRET_DIR_NAME);
        if (!baseDir.exists() && !baseDir.mkdirs()) {
            throw new IOException("Failed to create dir: " + baseDir.getAbsolutePath());
        }

        final File publicFile = new File(baseDir, PUBLIC_FILE_NAME);
        if (!publicFile.exists()) {
            writeStringToFile(publicFile, DEFAULT_PUBLIC_CONTENT);
            Slog.i(TAG, "Created demo public file: " + publicFile.getAbsolutePath());
        }

        return publicFile;
    }

    private static void writeStringToFile(File file, String value) throws IOException {
        try (FileOutputStream fos = new FileOutputStream(file)) {
            fos.write(value.getBytes(StandardCharsets.UTF_8));
            fos.flush();
            fos.getFD().sync();
        }
    }

    private static String readFileAsString(File file) throws IOException {
        try (FileInputStream fis = new FileInputStream(file);
             ByteArrayOutputStream bos = new ByteArrayOutputStream()) {

            final byte[] buf = new byte[4096];
            int n;
            while ((n = fis.read(buf)) != -1) {
                bos.write(buf, 0, n);
            }
            return bos.toString(StandardCharsets.UTF_8.name());
        }
    }
}
