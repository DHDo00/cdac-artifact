/*
 * Copyright (C) 2026 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package android.os;

import android.annotation.Nullable;
import android.util.Log;

import java.io.FileOutputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayDeque;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Framework-side CDAC Binder transaction context bridge.
 *
 * @hide
 */
public final class CdacBinderContext {
    private static final String TAG = "CdacBinderContext";
    private static final String CTL_PATH = "/dev/iguard_ctl";

    private static final int MAGIC = 0x49475544;
    private static final int VERSION = 1;
    private static final int MSG_PUSH = 5;
    private static final int MSG_POP = 6;
    private static final int MSG_LEN = 136;
    private static final int FIELD_LEN = 32;

    private static final AtomicLong sSequence = new AtomicLong(1);
    private static final ThreadLocal<ArrayDeque<Frame>> sFrames =
            ThreadLocal.withInitial(ArrayDeque::new);

    private CdacBinderContext() {}

    /** @hide */
    public static @Nullable Frame enter(Binder target, int transactionCode, int transactionFlags,
            int callerUid, int callerPid) {
        final CdacEndpointRegistry.ResolvedTransaction resolved =
                CdacEndpointRegistry.resolve(target, transactionCode, transactionFlags);
        if (resolved == null) {
            return null;
        }

        final ArrayDeque<Frame> stack = sFrames.get();
        final int depth = stack.size() + 1;
        final Frame frame = new Frame(sSequence.getAndIncrement(), resolved.endpoint.endpointId,
                resolved.endpoint.serviceId, resolved.opId, callerUid, callerPid, Process.myTid(),
                transactionCode, transactionFlags, depth, resolved.interfaceDescriptor,
                resolved.operationName, resolved.endpoint.symbolicName);
        stack.push(frame);

        if (CdacRuntimeConfig.isPerAttemptTextLoggingEnabled()) {
            Log.i(TAG, "event=CDAC_CONTEXT_ENTER"
                    + " context_id=" + frame.sequenceId
                    + " caller_uid=" + callerUid
                    + " caller_pid=" + callerPid
                    + " server_pid=" + Process.myPid()
                    + " server_tid=" + frame.serverTid
                    + " endpoint_id=" + frame.endpointId
                    + " service_id=" + frame.serviceId
                    + " op_id=" + frame.opId
                    + " operation=" + frame.operationName
                    + " transaction_code=" + transactionCode
                    + " transaction_flags=0x" + Integer.toHexString(transactionFlags)
                    + " nesting_depth=" + depth);
        }

        if (!writeFrame(MSG_PUSH, frame)) {
            stack.pop();
            return null;
        }
        CdacRuntimeConfig.noteContextEnter();

        if (CdacRuntimeConfig.isPerAttemptTextLoggingEnabled()) {
            Log.i(TAG, "CDAC_BINDER_ENTER source=UNIFIED_BINDER_HOOK"
                    + " seq=" + frame.sequenceId
                    + " caller_uid=" + callerUid
                    + " caller_pid=" + callerPid
                    + " server_pid=" + Process.myPid()
                    + " server_tid=" + frame.serverTid
                    + " endpoint_id=" + frame.endpointId
                    + " service_id=" + frame.serviceId
                    + " op_id=" + frame.opId
                    + " descriptor=" + frame.interfaceDescriptor
                    + " transaction_code=" + transactionCode
                    + " transaction_name=" + frame.operationName
                    + " transaction_flags=0x" + Integer.toHexString(transactionFlags)
                    + " nesting_depth=" + depth);
        }
        return frame;
    }

    /** @hide */
    public static void exit(@Nullable Frame frame, boolean exceptional) {
        if (frame == null) {
            return;
        }

        final ArrayDeque<Frame> stack = sFrames.get();
        final Frame top = stack.peek();
        if (top != frame) {
            Log.w(TAG, "event=CDAC_CONTEXT_STACK_MISMATCH"
                    + " context_id=" + frame.sequenceId
                    + " top_context_id=" + (top != null ? top.sequenceId : -1)
                    + " server_pid=" + Process.myPid()
                    + " server_tid=" + Process.myTid());
            stack.clear();
        } else {
            stack.pop();
        }

        writeFrame(MSG_POP, frame);
        CdacRuntimeConfig.noteContextExit();
        if (CdacRuntimeConfig.isPerAttemptTextLoggingEnabled()) {
            Log.i(TAG, "event=CDAC_CONTEXT_EXIT"
                    + " context_id=" + frame.sequenceId
                    + " exceptional=" + (exceptional ? "yes" : "no")
                    + " server_pid=" + Process.myPid()
                    + " server_tid=" + Process.myTid()
                    + " endpoint_id=" + frame.endpointId
                    + " service_id=" + frame.serviceId
                    + " op_id=" + frame.opId
                    + " operation=" + frame.operationName
                    + " nesting_depth=" + frame.nestingDepth
                    + " remaining_depth=" + stack.size());
            Log.i(TAG, (exceptional ? "CDAC_BINDER_EXCEPTION_EXIT" : "CDAC_BINDER_EXIT")
                    + " source=UNIFIED_BINDER_HOOK"
                    + " seq=" + frame.sequenceId
                    + " server_pid=" + Process.myPid()
                    + " server_tid=" + Process.myTid()
                    + " endpoint_id=" + frame.endpointId
                    + " service_id=" + frame.serviceId
                    + " op_id=" + frame.opId
                    + " nesting_depth=" + frame.nestingDepth
                    + " remaining_depth=" + stack.size());
        }
    }

    private static boolean writeFrame(int msgType, Frame frame) {
        final ByteBuffer buf = ByteBuffer.allocate(MSG_LEN);
        buf.order(ByteOrder.nativeOrder());
        buf.putInt(MAGIC);
        buf.putInt(VERSION);
        buf.putInt(msgType);
        buf.putInt(MSG_LEN);
        buf.putInt(frame.callerUid);
        buf.putInt(frame.callerPid);
        buf.putInt(frame.serviceId);
        buf.putInt(frame.opId);
        buf.putInt(frame.serverTid);
        buf.putInt(frame.transactionCode);
        buf.putInt(frame.transactionFlags);
        buf.putInt(frame.nestingDepth);
        buf.putLong(frame.sequenceId);
        buf.putLong(frame.endpointId);
        buf.putLong(CdacEndpointRegistry.stableHash(frame.interfaceDescriptor));
        putFixedString(buf, frame.symbolicService, FIELD_LEN);
        putFixedString(buf, frame.operationName, FIELD_LEN);

        try (FileOutputStream out = new FileOutputStream(CTL_PATH)) {
            out.write(buf.array());
            out.flush();
            CdacRuntimeConfig.noteContextPublish(msgType);
            if (CdacRuntimeConfig.isPerAttemptTextLoggingEnabled()) {
                Log.i(TAG, "event=CDAC_FRAMEWORK_CONTEXT_PUBLISH"
                        + " context_id=" + frame.sequenceId
                        + " msg_type=" + msgType
                        + " server_pid=" + Process.myPid()
                        + " server_tid=" + Process.myTid()
                        + " service_id=" + frame.serviceId
                        + " op_id=" + frame.opId
                        + " operation=" + frame.operationName
                        + " result=ok");
            }
            return true;
        } catch (Throwable t) {
            Log.w(TAG, "event=CDAC_FRAMEWORK_CONTEXT_PUBLISH"
                    + " context_id=" + frame.sequenceId
                    + " msg_type=" + msgType
                    + " server_pid=" + Process.myPid()
                    + " server_tid=" + Process.myTid()
                    + " service_id=" + frame.serviceId
                    + " op_id=" + frame.opId
                    + " operation=" + frame.operationName
                    + " result=write_failed", t);
            return false;
        }
    }

    private static void putFixedString(ByteBuffer buf, String value, int len) {
        final byte[] raw = value != null ? value.getBytes(StandardCharsets.UTF_8) : new byte[0];
        final int n = Math.min(raw.length, len - 1);
        buf.put(raw, 0, n);
        for (int i = n; i < len; i++) {
            buf.put((byte) 0);
        }
    }

    /** @hide */
    public static final class Frame {
        final long sequenceId;
        final long endpointId;
        final int serviceId;
        final int opId;
        final int callerUid;
        final int callerPid;
        final int serverTid;
        final int transactionCode;
        final int transactionFlags;
        final int nestingDepth;
        final String interfaceDescriptor;
        final String operationName;
        final String symbolicService;

        Frame(long sequenceId, long endpointId, int serviceId, int opId, int callerUid,
                int callerPid, int serverTid, int transactionCode, int transactionFlags,
                int nestingDepth, String interfaceDescriptor, String operationName,
                String symbolicService) {
            this.sequenceId = sequenceId;
            this.endpointId = endpointId;
            this.serviceId = serviceId;
            this.opId = opId;
            this.callerUid = callerUid;
            this.callerPid = callerPid;
            this.serverTid = serverTid;
            this.transactionCode = transactionCode;
            this.transactionFlags = transactionFlags;
            this.nestingDepth = nestingDepth;
            this.interfaceDescriptor = interfaceDescriptor != null ? interfaceDescriptor : "";
            this.operationName = operationName != null ? operationName : "";
            this.symbolicService = symbolicService != null ? symbolicService : "";
        }
    }
}
