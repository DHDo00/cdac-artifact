#ifndef IGUARD_MSG_H
#define IGUARD_MSG_H

#include <stdint.h>

#define IGUARD_MAGIC            0x49475544u
#define IGUARD_VERSION          1u

#define IGUARD_MSG_REPORT       1u
#define IGUARD_MSG_INVALIDATE   2u
#define IGUARD_MSG_POLICY_CLEAR 3u
#define IGUARD_MSG_POLICY_ADD   4u

#define IGUARD_SERVICE_LEN         32
#define IGUARD_OP_LEN              32

#define IGUARD_POLICY_SERVICE_LEN  32
#define IGUARD_POLICY_OP_LEN       32
#define IGUARD_POLICY_PATH_LEN     64
#define IGUARD_POLICY_REASON_LEN   64

/*
 * Stable numeric IDs for dual-track semantics.
 * 0 is reserved for UNKNOWN.
 */
enum iguard_service_id {
    IGUARD_SERVICE_UNKNOWN             = 0,
    IGUARD_SERVICE_IGUARD_DEMO         = 1,
    IGUARD_SERVICE_PACKAGE_MANAGER     = 2,
    IGUARD_SERVICE_DROPBOX_MANAGER     = 3,
};

enum iguard_op_id {
    IGUARD_OP_UNKNOWN                  = 0,

    /* IguardDemoService operations. */
    IGUARD_OP_READ_SECRET              = 1,
    IGUARD_OP_REPORT_ONLY_THEN_RETURN  = 2,
    IGUARD_OP_READ_PUBLIC              = 3,
    IGUARD_OP_WRITE_PUBLIC             = 4,
    IGUARD_OP_TOCTOU_WRITE_PUBLIC_RACE = 5,
    IGUARD_OP_READ_BY_PATH             = 6,

    /* Real Android service validation operations. */
    IGUARD_OP_PM_GET_PACKAGE_INFO      = 101,

    /*
     * DropBoxManagerService operations used for real-service
     * bindability validation.
     */
    IGUARD_OP_DROPBOX_GET_NEXT_ENTRY   = 201,
    IGUARD_OP_DROPBOX_DUMP             = 202,
};

/*
 * Keep decision values aligned with kernel-side enum
 * iguard_decision_kind.
 */
enum iguard_policy_decision_kind {
    IGUARD_POLICY_DECISION_AUDIT      = 1,
    IGUARD_POLICY_DECISION_WOULD_DENY = 2,
};

/*
 * Original report / invalidate message.
 * Keep this layout stable for existing JNI paths.
 */
struct iguard_msg {
    uint32_t magic;
    uint32_t version;
    uint32_t msg_type;
    uint32_t msg_len;

    uint32_t uid;
    uint32_t pid;

    uint32_t service_id;
    uint32_t op_id;

    char service[IGUARD_SERVICE_LEN];
    char operation[IGUARD_OP_LEN];

    uint64_t object_id;
    uint32_t flags;
};

/*
 * Minimal control message for policy clear.
 */
struct iguard_policy_ctl_msg {
    uint32_t magic;
    uint32_t version;
    uint32_t msg_type;
    uint32_t msg_len;
};

/*
 * Policy add message for runtime overlay rules.
 */
struct iguard_policy_add_msg {
    uint32_t magic;
    uint32_t version;
    uint32_t msg_type;
    uint32_t msg_len;

    uint32_t service_id;
    uint32_t op_id;

    uint32_t decision_kind;
    uint32_t f_flags_mask;
    uint32_t f_flags_value;

    char service[IGUARD_POLICY_SERVICE_LEN];
    char operation[IGUARD_POLICY_OP_LEN];
    char path_tail[IGUARD_POLICY_PATH_LEN];
    char reason[IGUARD_POLICY_REASON_LEN];
};

#endif
