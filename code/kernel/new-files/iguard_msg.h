#ifndef IGUARD_MSG_H
#define IGUARD_MSG_H

#include <linux/types.h>

#define IGUARD_MAGIC       0x49475544u
#define IGUARD_VERSION     1u
#define IGUARD_MSG_REPORT  1u

#define IGUARD_SERVICE_LEN 32
#define IGUARD_OP_LEN      32

/*
 * Stable numeric IDs for dual-track semantics.
 * 0 is reserved for UNKNOWN.
 */
enum iguard_service_id {
    IGUARD_SERVICE_UNKNOWN     = 0,
    IGUARD_SERVICE_IGUARD_DEMO = 1,
};

enum iguard_op_id {
    IGUARD_OP_UNKNOWN     = 0,
    IGUARD_OP_READ_SECRET = 1,
};

struct iguard_msg {
    __u32 magic;
    __u32 version;
    __u32 msg_type;
    __u32 msg_len;

    __u32 uid;
    __u32 pid;

    __u32 service_id;
    __u32 op_id;

    char service[IGUARD_SERVICE_LEN];
    char operation[IGUARD_OP_LEN];

    __u64 object_id;
    __u32 flags;
};

#endif
