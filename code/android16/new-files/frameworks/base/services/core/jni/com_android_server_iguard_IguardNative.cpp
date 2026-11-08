#define LOG_TAG "IguardNative"

#include <jni.h>
#include <log/log.h>

#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include "iguard_msg.h"

namespace android {

static constexpr const char* kCtlPath = "/dev/iguard_ctl";

static constexpr uint32_t kServiceIdUnknown        = 0;
static constexpr uint32_t kServiceIdIguardDemo     = 1;
static constexpr uint32_t kServiceIdPackageManager = 2;
static constexpr uint32_t kServiceIdDropBoxManager = 3;

static constexpr uint32_t kOpIdUnknown               = 0;
static constexpr uint32_t kOpIdReadSecret            = 1;
static constexpr uint32_t kOpIdReportOnlyThenReturn  = 2;
static constexpr uint32_t kOpIdReadPublic            = 3;
static constexpr uint32_t kOpIdWritePublic           = 4;
static constexpr uint32_t kOpIdToctouWritePublicRace = 5;
static constexpr uint32_t kOpIdReadByPath            = 6;
static constexpr uint32_t kOpIdReportThenThrow       = 7;

static constexpr uint32_t kOpIdPmGetPackageInfo      = 101;

static constexpr uint32_t kOpIdDropBoxGetNextEntry   = 201;
static constexpr uint32_t kOpIdDropBoxDump           = 202;

static bool streq(const char* a, const char* b) {
    return (a != nullptr && b != nullptr && strcmp(a, b) == 0);
}

static uint32_t resolveServiceId(const char* serviceName) {
    if (streq(serviceName, "iguard_demo")) {
        return kServiceIdIguardDemo;
    }
    if (streq(serviceName, "package_manager")) {
        return kServiceIdPackageManager;
    }
    if (streq(serviceName, "dropbox_manager")) {
        return kServiceIdDropBoxManager;
    }
    return kServiceIdUnknown;
}

static uint32_t resolveOpId(const char* serviceName, const char* operationName) {
    if (streq(serviceName, "iguard_demo") && streq(operationName, "readSecret")) {
        return kOpIdReadSecret;
    }
    if (streq(serviceName, "iguard_demo")
            && streq(operationName, "reportOnlyThenReturn")) {
        return kOpIdReportOnlyThenReturn;
    }
    if (streq(serviceName, "iguard_demo")
            && streq(operationName, "readPublic")) {
        return kOpIdReadPublic;
    }
    if (streq(serviceName, "iguard_demo")
            && streq(operationName, "writePublic")) {
        return kOpIdWritePublic;
    }
    if (streq(serviceName, "iguard_demo")
            && streq(operationName, "toctouWritePublicRace")) {
        return kOpIdToctouWritePublicRace;
    }
    if (streq(serviceName, "iguard_demo")
            && streq(operationName, "readByPath")) {
        return kOpIdReadByPath;
    }
    if (streq(serviceName, "iguard_demo")
            && streq(operationName, "reportThenThrow")) {
        return kOpIdReportThenThrow;
    }
    if (streq(serviceName, "package_manager")
            && streq(operationName, "getPackageInfo")) {
        return kOpIdPmGetPackageInfo;
    }
    if (streq(serviceName, "dropbox_manager")
            && streq(operationName, "getNextEntry")) {
        return kOpIdDropBoxGetNextEntry;
    }
    if (streq(serviceName, "dropbox_manager")
            && streq(operationName, "dump")) {
        return kOpIdDropBoxDump;
    }
    return kOpIdUnknown;
}

static bool writeFullyToFd(int fd, const void* buf, size_t len) {
    const uint8_t* p = static_cast<const uint8_t*>(buf);
    size_t off = 0;
    while (off < len) {
        ssize_t n = TEMP_FAILURE_RETRY(write(fd, p + off, len - off));
        if (n < 0) {
            return false;
        }
        if (n == 0) {
            errno = EIO;
            return false;
        }
        off += static_cast<size_t>(n);
    }
    return true;
}

static jstring nativePing(JNIEnv* env, jclass /* clazz */) {
    ALOGI("nativePing(): ok");
    return env->NewStringUTF("native-ping-ok");
}

static jboolean nativeReportCaller(JNIEnv* env, jclass /* clazz */,
        jint callingUid, jint callingPid,
        jstring serviceNameObj, jstring operationNameObj) {
    if (serviceNameObj == nullptr || operationNameObj == nullptr) {
        ALOGE("nativeReportCaller(): null jstring argument");
        return JNI_FALSE;
    }

    const char* serviceName = env->GetStringUTFChars(serviceNameObj, nullptr);
    const char* operationName = env->GetStringUTFChars(operationNameObj, nullptr);

    if (serviceName == nullptr || operationName == nullptr) {
        ALOGE("nativeReportCaller(): GetStringUTFChars failed");
        if (serviceName != nullptr) {
            env->ReleaseStringUTFChars(serviceNameObj, serviceName);
        }
        if (operationName != nullptr) {
            env->ReleaseStringUTFChars(operationNameObj, operationName);
        }
        return JNI_FALSE;
    }

    struct iguard_msg msg = {};

    msg.magic = IGUARD_MAGIC;
    msg.version = IGUARD_VERSION;
    msg.msg_type = IGUARD_MSG_REPORT;
    msg.msg_len = sizeof(msg);

    msg.uid = static_cast<uint32_t>(callingUid);
    msg.pid = static_cast<uint32_t>(callingPid);

    msg.service_id = resolveServiceId(serviceName);
    msg.op_id = resolveOpId(serviceName, operationName);

    msg.object_id = 0;
    msg.flags = 0;

    strncpy(msg.service, serviceName, IGUARD_SERVICE_LEN - 1);
    strncpy(msg.operation, operationName, IGUARD_OP_LEN - 1);
    msg.service[IGUARD_SERVICE_LEN - 1] = '\0';
    msg.operation[IGUARD_OP_LEN - 1] = '\0';

    ALOGI("nativeReportCaller(): writing struct to %s "
          "magic=0x%x version=%u type=%u len=%u uid=%u pid=%u "
          "service_id=%u op_id=%u service=%s operation=%s",
          kCtlPath,
          msg.magic,
          msg.version,
          msg.msg_type,
          msg.msg_len,
          msg.uid,
          msg.pid,
          msg.service_id,
          msg.op_id,
          msg.service,
          msg.operation);

    int fd = TEMP_FAILURE_RETRY(open(kCtlPath, O_WRONLY | O_CLOEXEC));
    if (fd < 0) {
        ALOGE("nativeReportCaller(): open(%s) failed: errno=%d (%s)",
              kCtlPath, errno, strerror(errno));
        env->ReleaseStringUTFChars(serviceNameObj, serviceName);
        env->ReleaseStringUTFChars(operationNameObj, operationName);
        return JNI_FALSE;
    }

    bool ok = writeFullyToFd(fd, &msg, sizeof(msg));
    if (!ok) {
        ALOGE("nativeReportCaller(): write failed: errno=%d (%s) "
              "service_id=%u op_id=%u service=%s operation=%s",
              errno,
              strerror(errno),
              msg.service_id,
              msg.op_id,
              msg.service,
              msg.operation);
    } else {
        ALOGI("nativeReportCaller(): write success "
              "service_id=%u op_id=%u service=%s operation=%s",
              msg.service_id,
              msg.op_id,
              msg.service,
              msg.operation);
    }

    close(fd);
    env->ReleaseStringUTFChars(serviceNameObj, serviceName);
    env->ReleaseStringUTFChars(operationNameObj, operationName);

    return ok ? JNI_TRUE : JNI_FALSE;
}

static jboolean nativeInvalidateCaller(JNIEnv* env, jclass /* clazz */,
        jstring serviceNameObj, jstring operationNameObj) {
    if (serviceNameObj == nullptr || operationNameObj == nullptr) {
        ALOGE("nativeInvalidateCaller(): null jstring argument");
        return JNI_FALSE;
    }

    const char* serviceName = env->GetStringUTFChars(serviceNameObj, nullptr);
    const char* operationName = env->GetStringUTFChars(operationNameObj, nullptr);

    if (serviceName == nullptr || operationName == nullptr) {
        ALOGE("nativeInvalidateCaller(): GetStringUTFChars failed");
        if (serviceName != nullptr) {
            env->ReleaseStringUTFChars(serviceNameObj, serviceName);
        }
        if (operationName != nullptr) {
            env->ReleaseStringUTFChars(operationNameObj, operationName);
        }
        return JNI_FALSE;
    }

    struct iguard_msg msg = {};

    msg.magic = IGUARD_MAGIC;
    msg.version = IGUARD_VERSION;
    msg.msg_type = IGUARD_MSG_INVALIDATE;
    msg.msg_len = sizeof(msg);

    msg.uid = 0;
    msg.pid = 0;
    msg.service_id = resolveServiceId(serviceName);
    msg.op_id = resolveOpId(serviceName, operationName);
    msg.object_id = 0;
    msg.flags = 0;

    strncpy(msg.service, serviceName, IGUARD_SERVICE_LEN - 1);
    strncpy(msg.operation, operationName, IGUARD_OP_LEN - 1);
    msg.service[IGUARD_SERVICE_LEN - 1] = '\0';
    msg.operation[IGUARD_OP_LEN - 1] = '\0';

    ALOGI("nativeInvalidateCaller(): writing struct to %s "
          "magic=0x%x version=%u type=%u len=%u "
          "service_id=%u op_id=%u service=%s operation=%s",
          kCtlPath,
          msg.magic,
          msg.version,
          msg.msg_type,
          msg.msg_len,
          msg.service_id,
          msg.op_id,
          msg.service,
          msg.operation);

    int fd = TEMP_FAILURE_RETRY(open(kCtlPath, O_WRONLY | O_CLOEXEC));
    if (fd < 0) {
        ALOGE("nativeInvalidateCaller(): open(%s) failed: errno=%d (%s)",
              kCtlPath, errno, strerror(errno));
        env->ReleaseStringUTFChars(serviceNameObj, serviceName);
        env->ReleaseStringUTFChars(operationNameObj, operationName);
        return JNI_FALSE;
    }

    bool ok = writeFullyToFd(fd, &msg, sizeof(msg));
    if (!ok) {
        ALOGE("nativeInvalidateCaller(): write failed: errno=%d (%s) "
              "service_id=%u op_id=%u service=%s operation=%s",
              errno,
              strerror(errno),
              msg.service_id,
              msg.op_id,
              msg.service,
              msg.operation);
    } else {
        ALOGI("nativeInvalidateCaller(): write success "
              "service_id=%u op_id=%u service=%s operation=%s",
              msg.service_id,
              msg.op_id,
              msg.service,
              msg.operation);
    }

    close(fd);
    env->ReleaseStringUTFChars(serviceNameObj, serviceName);
    env->ReleaseStringUTFChars(operationNameObj, operationName);
    return ok ? JNI_TRUE : JNI_FALSE;
}

static const JNINativeMethod gMethods[] = {
    {"nativePing", "()Ljava/lang/String;", (void*)nativePing},
    {"nativeReportCaller", "(IILjava/lang/String;Ljava/lang/String;)Z",
     (void*)nativeReportCaller},
    {"nativeInvalidateCaller", "(Ljava/lang/String;Ljava/lang/String;)Z",
     (void*)nativeInvalidateCaller},
};

int register_com_android_server_iguard_IguardNative(JNIEnv* env) {
    jclass clazz = env->FindClass("com/android/server/iguard/IguardNative");
    if (clazz == nullptr) {
        ALOGE("register_com_android_server_iguard_IguardNative: class not found");
        return -1;
    }
    if (env->RegisterNatives(clazz,
            gMethods,
            sizeof(gMethods) / sizeof(gMethods[0])) < 0) {
        ALOGE("register_com_android_server_iguard_IguardNative: RegisterNatives failed");
        return -1;
    }
    return 0;
}

}  // namespace android
