package com.android.server.iguard;

public final class IguardNative {
    private IguardNative() {}

    public static native String nativePing();

    public static native boolean nativeReportCaller(
            int callingUid, int callingPid, String serviceName, String operationName);

    public static native boolean nativeInvalidateCaller(
            String serviceName, String operationName);
}
