/*
 * Copyright (C) 2026 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package android.os;

import android.annotation.Nullable;
import android.content.IContentProvider;
import android.util.Log;

import java.util.IdentityHashMap;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Process-local CDAC Binder endpoint registry.
 *
 * @hide
 */
public final class CdacEndpointRegistry {
    private static final String TAG = "CdacEndpointRegistry";

    private static final String ICONTENT_PROVIDER_DESCRIPTOR = "android.content.IContentProvider";
    private static final int SERVICE_CONTENT_PROVIDER_FILE_OPEN = 4;
    private static final int OP_CONTENT_PROVIDER_FILE_OPEN = 301;
    private static final int SERVICE_SETTINGS_PROVIDER_FILE_OPEN = 8;
    private static final int OP_SETTINGS_PROVIDER_FILE_OPEN = 701;
    private static final String SETTINGS_PROVIDER_CLASS =
            "com.android.providers.settings.SettingsProvider";
    private static final String SETTINGS_PROVIDER_AUTHORITY = "settings";

    private static final Object sLock = new Object();
    private static final IdentityHashMap<IBinder, Endpoint> sEndpoints = new IdentityHashMap<>();
    private static final AtomicLong sAuditSeq = new AtomicLong(1);

    private CdacEndpointRegistry() {}

    /** @hide */
    public static final class Endpoint {
        public final long endpointId;
        public final int serviceId;
        public final int defaultOpId;
        public final String endpointType;
        public final String symbolicName;
        public final String interfaceDescriptor;
        public final String binderClassName;
        public final int binderIdentityHash;
        public final int binderHashCode;
        public final String providerClassName;
        public final String providerAuthority;
        public final long metadataHash;
        public final long registrationSeq;
        public final String registrationSource;

        Endpoint(long endpointId, int serviceId, int defaultOpId, String endpointType,
                String symbolicName, String interfaceDescriptor, String binderClassName,
                int binderIdentityHash, int binderHashCode, String providerClassName,
                String providerAuthority, long metadataHash, long registrationSeq,
                String registrationSource) {
            this.endpointId = endpointId;
            this.serviceId = serviceId;
            this.defaultOpId = defaultOpId;
            this.endpointType = endpointType;
            this.symbolicName = symbolicName;
            this.interfaceDescriptor = interfaceDescriptor;
            this.binderClassName = binderClassName;
            this.binderIdentityHash = binderIdentityHash;
            this.binderHashCode = binderHashCode;
            this.providerClassName = providerClassName;
            this.providerAuthority = providerAuthority;
            this.metadataHash = metadataHash;
            this.registrationSeq = registrationSeq;
            this.registrationSource = registrationSource;
        }
    }

    /** @hide */
    public static final class ResolvedTransaction {
        public final Endpoint endpoint;
        public final int opId;
        public final String operationName;
        public final String interfaceDescriptor;

        ResolvedTransaction(Endpoint endpoint, int opId, String operationName,
                String interfaceDescriptor) {
            this.endpoint = endpoint;
            this.opId = opId;
            this.operationName = operationName;
            this.interfaceDescriptor = interfaceDescriptor;
        }
    }

    /** @hide */
    public static void registerContentProvider(IBinder binder) {
        registerContentProvider(binder, "", "");
    }

    /** @hide */
    public static void registerContentProvider(IBinder binder, String providerClassName,
            String providerAuthority) {
        registerContentProviderFromLifecycle(binder, providerClassName, providerAuthority,
                "ContentProvider.attachInfo");
    }

    private static void registerContentProviderFromLifecycle(IBinder binder,
            String providerClassName, String providerAuthority, String registrationSource) {
        if (binder == null) {
            return;
        }
        final String descriptor = getDescriptor(binder);
        if (!ICONTENT_PROVIDER_DESCRIPTOR.equals(descriptor)) {
            auditRegister(binder, descriptor, null, registrationSource,
                    "descriptor_not_icontentprovider");
            return;
        }

        final int identity = System.identityHashCode(binder);
        final long registrationSeq = sAuditSeq.get();
        final long metadataHash = stableHash("lifecycle|"
                + nullToEmpty(providerClassName) + "|"
                + nullToEmpty(providerAuthority) + "|"
                + descriptor + "|"
                + identity);
        final boolean settingsProvider = isSettingsProvider(providerClassName, providerAuthority);
        final int serviceId = settingsProvider
                ? SERVICE_SETTINGS_PROVIDER_FILE_OPEN : SERVICE_CONTENT_PROVIDER_FILE_OPEN;
        final int opId = settingsProvider
                ? OP_SETTINGS_PROVIDER_FILE_OPEN : OP_CONTENT_PROVIDER_FILE_OPEN;
        final String endpointType = settingsProvider ? "settings_provider" : "content_provider";
        final String symbolicName = settingsProvider
                ? "settings_provider_open_file" : "content_provider_file_open";
        final long endpointId = settingsProvider
                ? stableHash("provider|settings|" + descriptor + "|" + identity)
                : stableHash("provider|" + descriptor + "|" + identity);
        final Endpoint endpoint = new Endpoint(
                endpointId,
                serviceId,
                opId,
                endpointType,
                symbolicName,
                descriptor,
                binder.getClass().getName(),
                identity,
                binder.hashCode(),
                nullToEmpty(providerClassName),
                nullToEmpty(providerAuthority),
                metadataHash,
                registrationSeq,
                registrationSource);
        final Endpoint existing;
        final String result;
        synchronized (sLock) {
            existing = sEndpoints.get(binder);
            if (existing == null) {
                sEndpoints.put(binder, endpoint);
                result = "ok";
            } else if (sameEndpointMetadata(existing, endpoint)) {
                result = "already_registered_idempotent";
            } else {
                result = "conflicting_duplicate_rejected";
            }
        }
        auditRegister(binder, descriptor, existing == null ? endpoint : existing, registrationSource,
                result);
    }

    /** @hide */
    public static void unregisterContentProvider(IBinder binder, String reason) {
        if (binder == null) {
            return;
        }
        final Endpoint endpoint;
        synchronized (sLock) {
            endpoint = sEndpoints.remove(binder);
        }
        if (endpoint != null && !CdacRuntimeConfig.isPerAttemptTextLoggingEnabled()) {
            sAuditSeq.getAndIncrement();
        } else if (endpoint != null) {
            Log.i(TAG, "event=CDAC_ENDPOINT_UNREGISTER"
                    + " audit_seq=" + sAuditSeq.getAndIncrement()
                    + " ts_ns=" + SystemClock.elapsedRealtimeNanos()
                    + " server_pid=" + Process.myPid()
                    + " server_tid=" + Process.myTid()
                    + " object_identity=" + System.identityHashCode(binder)
                    + " service_id=" + endpoint.serviceId
                    + " reason=" + nullToEmpty(reason));
        }
    }

    /** @hide */
    public static @Nullable ResolvedTransaction resolve(Binder target, int transactionCode,
            int transactionFlags) {
        if (target == null) {
            return null;
        }

        final String descriptor = getDescriptor(target);
        final String transactionName = providerTransactionName(transactionCode,
                target.getTransactionName(transactionCode));
        final boolean descriptorMatch = ICONTENT_PROVIDER_DESCRIPTOR.equals(descriptor);
        final boolean codeMatch = isProviderFileOpenTransaction(transactionCode);

        Endpoint endpoint;
        int candidateCount;
        boolean objectIdentityMatch;
        synchronized (sLock) {
            endpoint = sEndpoints.get(target);
            objectIdentityMatch = endpoint != null;
            candidateCount = countCandidatesLocked(descriptor);
        }

        String missReason = "";
        boolean serviceMatch = false;
        boolean resolveHit = false;
        if (!descriptorMatch) {
            missReason = "DESCRIPTOR_MISMATCH";
        } else if (endpoint == null) {
            missReason = candidateCount == 0 ? "NO_REGISTRATION" : "OBJECT_IDENTITY_MISMATCH";
        } else if (!codeMatch) {
            missReason = "TRANSACTION_CODE_UNMAPPED";
        } else {
            serviceMatch = isSupportedProviderFileOpenService(endpoint.serviceId);
            resolveHit = serviceMatch;
            if (!serviceMatch) {
                missReason = "OTHER_WITH_DIRECT_EVIDENCE";
            }
        }

        if (descriptorMatch || endpoint != null) {
            auditResolve(target, descriptor, transactionCode, transactionName, transactionFlags,
                    candidateCount, objectIdentityMatch, descriptorMatch, codeMatch, serviceMatch,
                    resolveHit, missReason, endpoint);
        }

        if (!resolveHit) {
            return null;
        }
        return new ResolvedTransaction(endpoint, endpoint.defaultOpId, transactionName,
                endpoint.interfaceDescriptor);
    }

    private static int countCandidatesLocked(@Nullable String descriptor) {
        int count = 0;
        for (Endpoint candidate : sEndpoints.values()) {
            if (nullToEmpty(descriptor).equals(candidate.interfaceDescriptor)) {
                count++;
            }
        }
        return count;
    }

    private static boolean isSettingsProvider(String providerClassName, String providerAuthority) {
        return SETTINGS_PROVIDER_CLASS.equals(nullToEmpty(providerClassName))
                && SETTINGS_PROVIDER_AUTHORITY.equals(nullToEmpty(providerAuthority));
    }

    private static boolean isSupportedProviderFileOpenService(int serviceId) {
        return serviceId == SERVICE_CONTENT_PROVIDER_FILE_OPEN
                || serviceId == SERVICE_SETTINGS_PROVIDER_FILE_OPEN;
    }

    private static void auditRegister(IBinder binder, @Nullable String descriptor,
            @Nullable Endpoint endpoint, String registrationSource, String result) {
        if (!CdacRuntimeConfig.isPerAttemptTextLoggingEnabled()) {
            sAuditSeq.getAndIncrement();
            return;
        }
        Log.i(TAG, "event=CDAC_ENDPOINT_REGISTER"
                + " audit_seq=" + sAuditSeq.getAndIncrement()
                + " ts_ns=" + SystemClock.elapsedRealtimeNanos()
                + " server_pid=" + Process.myPid()
                + " server_tid=" + Process.myTid()
                + " registered_object_identity=" + System.identityHashCode(binder)
                    + " registered_object_class=" + binder.getClass().getName()
                    + " interface_descriptor=" + nullToEmpty(descriptor)
                    + " service_id=" + (endpoint != null ? endpoint.serviceId : 0)
                    + " endpoint_id=" + (endpoint != null ? endpoint.endpointId : 0)
                    + " supported_transaction_code="
                    + IContentProvider.OPEN_FILE_TRANSACTION + ";"
                    + IContentProvider.OPEN_ASSET_FILE_TRANSACTION + ";"
                    + IContentProvider.OPEN_TYPED_ASSET_FILE_TRANSACTION
                    + " op_id=" + (endpoint != null ? endpoint.defaultOpId : 0)
                    + " operation=openFile;openAssetFile;openTypedAssetFile"
                    + " registration_source=" + nullToEmpty(registrationSource)
                    + " trust_source=authoritative_provider_lifecycle"
                    + " provider_class=" + (endpoint != null
                            ? nullToEmpty(endpoint.providerClassName) : "")
                    + " provider_authority_hash=" + (endpoint != null
                            ? stableHash(endpoint.providerAuthority) : 0)
                    + " metadata_hash=" + (endpoint != null ? endpoint.metadataHash : 0)
                    + " registration_seq=" + (endpoint != null ? endpoint.registrationSeq : 0)
                    + " registration_lifetime=process"
                    + " result=" + result);
    }

    private static void auditResolve(Binder target, @Nullable String descriptor,
            int transactionCode, @Nullable String transactionName, int transactionFlags,
            int candidateCount, boolean objectIdentityMatch, boolean descriptorMatch,
            boolean transactionCodeMatch, boolean serviceMatch, boolean resolveHit,
            String missReason, @Nullable Endpoint endpoint) {
        CdacRuntimeConfig.noteEndpointResolve();
        if (!CdacRuntimeConfig.isPerAttemptTextLoggingEnabled()) {
            sAuditSeq.getAndIncrement();
            return;
        }
        Log.i(TAG, "event=CDAC_ENDPOINT_RESOLVE"
                + " audit_seq=" + sAuditSeq.getAndIncrement()
                + " ts_ns=" + SystemClock.elapsedRealtimeNanos()
                + " server_pid=" + Process.myPid()
                + " server_tid=" + Process.myTid()
                + " receiver_object_identity=" + System.identityHashCode(target)
                + " receiver_object_class=" + target.getClass().getName()
                + " interface_descriptor=" + nullToEmpty(descriptor)
                + " transaction_code=" + transactionCode
                + " transaction_name=" + nullToEmpty(transactionName)
                + " transaction_flags=0x" + Integer.toHexString(transactionFlags)
                + " candidate_count=" + candidateCount
                + " object_identity_match=" + yesNo(objectIdentityMatch)
                + " descriptor_match=" + yesNo(descriptorMatch)
                + " transaction_code_match=" + yesNo(transactionCodeMatch)
                + " service_match=" + yesNo(serviceMatch)
                + " resolve_type=" + (resolveHit ? "exact_lifecycle_receiver" : "none")
                + " trusted_source=" + (resolveHit
                        ? nullToEmpty(endpoint.registrationSource) : "")
                + " metadata_hash=" + (endpoint != null ? endpoint.metadataHash : 0)
                + " registration_seq=" + (endpoint != null ? endpoint.registrationSeq : 0)
                + " resolve_result=" + (resolveHit ? "hit" : "miss")
                + " miss_reason=" + (resolveHit ? "" : missReason)
                + " endpoint_id=" + (endpoint != null ? endpoint.endpointId : 0)
                + " service_id=" + (endpoint != null ? endpoint.serviceId : 0)
                + " op_id=" + (endpoint != null ? endpoint.defaultOpId : 0));
    }

    private static boolean sameEndpointMetadata(Endpoint left, Endpoint right) {
        return left.endpointId == right.endpointId
                && left.serviceId == right.serviceId
                && left.defaultOpId == right.defaultOpId
                && left.binderIdentityHash == right.binderIdentityHash
                && left.binderHashCode == right.binderHashCode
                && nullToEmpty(left.interfaceDescriptor).equals(nullToEmpty(right.interfaceDescriptor))
                && nullToEmpty(left.binderClassName).equals(nullToEmpty(right.binderClassName))
                && nullToEmpty(left.providerClassName).equals(nullToEmpty(right.providerClassName))
                && nullToEmpty(left.providerAuthority).equals(nullToEmpty(right.providerAuthority));
    }

    /** @hide */
    public static int trustedRecordCountForTest() {
        synchronized (sLock) {
            return sEndpoints.size();
        }
    }

    /** @hide */
    public static String runUnregisteredIContentProviderNegativeSelfTestForDebug() {
        final int before = trustedRecordCountForTest();
        final Binder fake = new Binder();
        fake.attachInterface(null, ICONTENT_PROVIDER_DESCRIPTOR);
        final ResolvedTransaction resolved = resolve(fake,
                IContentProvider.OPEN_ASSET_FILE_TRANSACTION, 0);
        final int after = trustedRecordCountForTest();
        final int hit = resolved != null ? 1 : 0;
        final int growth = after - before;
        final String result = "ARBITRARY_ICONTENTPROVIDER_RESOLVE_HIT_COUNT=" + hit
                + " ARBITRARY_ICONTENTPROVIDER_TRUSTED_RECORD_CREATED_COUNT=" + growth
                + " ARBITRARY_ICONTENTPROVIDER_ALIAS_CREATED_COUNT=0"
                + " ARBITRARY_ICONTENTPROVIDER_CONTEXT_ENTER_COUNT=0"
                + " REGISTRY_RECORD_COUNT_GROWTH_FROM_NEGATIVE_TEST=" + growth;
        if (CdacRuntimeConfig.isPerAttemptTextLoggingEnabled()) {
            Log.i(TAG, "event=CDAC_ENDPOINT_NEGATIVE_SELFTEST"
                    + " audit_seq=" + sAuditSeq.getAndIncrement()
                    + " ts_ns=" + SystemClock.elapsedRealtimeNanos()
                    + " before_count=" + before
                    + " after_count=" + after
                    + " " + result);
        } else {
            sAuditSeq.getAndIncrement();
        }
        return result;
    }

    private static boolean isProviderFileOpenTransaction(int transactionCode) {
        return transactionCode == IContentProvider.OPEN_FILE_TRANSACTION
                || transactionCode == IContentProvider.OPEN_ASSET_FILE_TRANSACTION
                || transactionCode == IContentProvider.OPEN_TYPED_ASSET_FILE_TRANSACTION;
    }

    private static @Nullable String providerTransactionName(int transactionCode,
            @Nullable String transactionName) {
        if (transactionName != null && !transactionName.isEmpty()) {
            return transactionName;
        }
        if (transactionCode == IContentProvider.OPEN_FILE_TRANSACTION) {
            return "openFile";
        }
        if (transactionCode == IContentProvider.OPEN_ASSET_FILE_TRANSACTION) {
            return "openAssetFile";
        }
        if (transactionCode == IContentProvider.OPEN_TYPED_ASSET_FILE_TRANSACTION) {
            return "openTypedAssetFile";
        }
        return transactionName;
    }

    private static @Nullable String getDescriptor(IBinder binder) {
        try {
            return binder.getInterfaceDescriptor();
        } catch (RemoteException | RuntimeException e) {
            return null;
        }
    }

    static long stableHash(String value) {
        long hash = 0xcbf29ce484222325L;
        for (int i = 0; i < value.length(); i++) {
            hash ^= value.charAt(i);
            hash *= 0x100000001b3L;
        }
        return hash & Long.MAX_VALUE;
    }

    private static String nullToEmpty(@Nullable String value) {
        return value != null ? value : "";
    }

    private static String yesNo(boolean value) {
        return value ? "yes" : "no";
    }
}
