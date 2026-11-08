/*
 * Copyright (C) 2026 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package android.os;

import android.util.Log;

import java.util.concurrent.atomic.AtomicLong;

/**
 * Process-local CDAC runtime configuration.
 *
 * @hide
 */
final class CdacRuntimeConfig {
    private static final String TAG = "CdacRuntimeConfig";
    static final String PROP_LOGGING_MODE = "persist.debug.cdac.logging_mode";
    private static final String PROP_COUNTER_CMD = "persist.debug.cdac.counter_cmd";
    private static final int MSG_PUSH = 5;
    private static final int MSG_POP = 6;
    static final String MODE_QUIET = "quiet";
    static final String MODE_AUDIT = "audit";
    static final String MODE_TRACE = "trace";

    private static final AtomicLong sEndpointResolveCount = new AtomicLong();
    private static final AtomicLong sContextEnterCount = new AtomicLong();
    private static final AtomicLong sContextExitCount = new AtomicLong();
    private static final AtomicLong sContextPublishPushCount = new AtomicLong();
    private static final AtomicLong sContextPublishPopCount = new AtomicLong();
    private static final AtomicLong sBinderEntryCount = new AtomicLong();

    private static volatile String sLoggingMode = readLoggingMode();
    private static volatile String sLastCounterCommand = SystemProperties.get(PROP_COUNTER_CMD, "");

    static {
        SystemProperties.addChangeCallback(CdacRuntimeConfig::onPropertiesChanged);
    }

    private CdacRuntimeConfig() {}

    static boolean isPerAttemptTextLoggingEnabled() {
        return !MODE_QUIET.equals(sLoggingMode);
    }

    static String loggingModeForDebug() {
        return sLoggingMode;
    }

    static void noteEndpointResolve() {
        sEndpointResolveCount.incrementAndGet();
    }

    static void noteContextEnter() {
        sContextEnterCount.incrementAndGet();
    }

    static void noteContextExit() {
        sContextExitCount.incrementAndGet();
    }

    static void noteContextPublish(int msgType) {
        if (msgType == MSG_PUSH) {
            sContextPublishPushCount.incrementAndGet();
        } else if (msgType == MSG_POP) {
            sContextPublishPopCount.incrementAndGet();
        }
    }

    static void noteBinderEntry() {
        sBinderEntryCount.incrementAndGet();
    }

    private static void onPropertiesChanged() {
        sLoggingMode = readLoggingMode();

        final String command = SystemProperties.get(PROP_COUNTER_CMD, "");
        if (command.equals(sLastCounterCommand)) {
            return;
        }
        sLastCounterCommand = command;
        if (command.startsWith("reset:")) {
            resetCounters();
            Log.i(TAG, "event=CDAC_FRAMEWORK_COUNTER_RESET"
                    + " command=" + command
                    + " pid=" + Process.myPid()
                    + " tid=" + Process.myTid());
        } else if (command.startsWith("dump:")) {
            Log.i(TAG, "event=CDAC_FRAMEWORK_COUNTER_DUMP"
                    + " command=" + command
                    + " pid=" + Process.myPid()
                    + " tid=" + Process.myTid()
                    + " endpoint_resolve=" + sEndpointResolveCount.get()
                    + " context_enter=" + sContextEnterCount.get()
                    + " context_exit=" + sContextExitCount.get()
                    + " context_publish_push=" + sContextPublishPushCount.get()
                    + " context_publish_pop=" + sContextPublishPopCount.get()
                    + " binder_entry=" + sBinderEntryCount.get());
        }
    }

    private static void resetCounters() {
        sEndpointResolveCount.set(0);
        sContextEnterCount.set(0);
        sContextExitCount.set(0);
        sContextPublishPushCount.set(0);
        sContextPublishPopCount.set(0);
        sBinderEntryCount.set(0);
    }

    private static String readLoggingMode() {
        final String value = SystemProperties.get(PROP_LOGGING_MODE, MODE_TRACE);
        if (MODE_QUIET.equals(value) || MODE_AUDIT.equals(value) || MODE_TRACE.equals(value)) {
            return value;
        }
        return MODE_TRACE;
    }
}
