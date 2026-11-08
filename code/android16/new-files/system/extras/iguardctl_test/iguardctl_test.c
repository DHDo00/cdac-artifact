#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/sysmacros.h>
#include <unistd.h>

#define IGUARD_CTL_PATH "/dev/iguard_ctl"

#define IGUARD_MAGIC            0x49475544u
#define IGUARD_VERSION          1u

#define IGUARD_MSG_POLICY_CLEAR 3u
#define IGUARD_MSG_POLICY_ADD   4u

#define IGUARD_DECISION_AUDIT      1u
#define IGUARD_DECISION_WOULD_DENY 2u

#define IGUARD_POLICY_SERVICE_LEN  32
#define IGUARD_POLICY_OP_LEN       32
#define IGUARD_POLICY_PATH_LEN     64
#define IGUARD_POLICY_REASON_LEN   64

struct iguard_policy_ctl_msg {
    uint32_t magic;
    uint32_t version;
    uint32_t msg_type;
    uint32_t msg_len;
};

struct iguard_policy_add_msg_v3 {
    uint32_t magic;
    uint32_t version;
    uint32_t msg_type;
    uint32_t msg_len;

    uint32_t service_id;
    uint32_t op_id;
    uint32_t caller_uid;

    uint32_t decision_kind;
    uint32_t f_flags_mask;
    uint32_t f_flags_value;

    char service[IGUARD_POLICY_SERVICE_LEN];
    char operation[IGUARD_POLICY_OP_LEN];
    char path_tail[IGUARD_POLICY_PATH_LEN];
    char reason[IGUARD_POLICY_REASON_LEN];

    uint32_t f_mode_mask;
    uint32_t f_mode_value;

    uint64_t ino;
    uint64_t s_dev;
    uint32_t i_mode;

    uint32_t required_relation_type;
    uint32_t required_relation_stage;
};

struct iguard_policy_add_msg_v2 {
    uint32_t magic;
    uint32_t version;
    uint32_t msg_type;
    uint32_t msg_len;

    uint32_t service_id;
    uint32_t op_id;
    uint32_t caller_uid;

    uint32_t decision_kind;
    uint32_t f_flags_mask;
    uint32_t f_flags_value;

    char service[IGUARD_POLICY_SERVICE_LEN];
    char operation[IGUARD_POLICY_OP_LEN];
    char path_tail[IGUARD_POLICY_PATH_LEN];
    char reason[IGUARD_POLICY_REASON_LEN];

    uint32_t f_mode_mask;
    uint32_t f_mode_value;

    uint64_t ino;
    uint64_t s_dev;
    uint32_t i_mode;
};

_Static_assert(sizeof(struct iguard_policy_ctl_msg) == 16,
               "iguard_policy_ctl_msg size mismatch");

static void usage(const char *prog)
{
    fprintf(stderr,
            "Usage:\n"
            "  %s clear\n"
            "  %s add key=value [key=value ...]\n"
            "\n"
            "Supported add keys:\n"
            "  service_id=<u32>\n"
            "  op_id=<u32>\n"
            "  service=<str>  diagnostic label only; not a schema-v2 security predicate\n"
            "  operation=<str>\n"
            "  path_tail=<str>\n"
            "  reason=<str>\n"
            "  f_flags_mask=<u32>\n"
            "  f_flags_value=<u32>\n"
            "  f_mode_mask=<u32>\n"
            "  f_mode_value=<u32>\n"
            "  ino=<u64>\n"
            "  s_dev=<u64>\n"
            "  i_mode=<u32>\n"
            "  required_relation_type=direct_backing_file_reference|<u32>\n"
            "  required_relation_stage=open_time|<u32>\n"
            "  decision=audit|deny\n"
            "\n"
            "Examples:\n"
            "  %s add service_id=1 path_tail=public.txt decision=audit reason=runtime_public_any_audit_ctl\n"
            "  %s add service_id=1 op_id=4 path_tail=public.txt decision=deny \\\n"
            "       reason=rt_write_public_deny f_flags_mask=3 f_flags_value=1 \\\n"
            "       f_mode_mask=3 f_mode_value=2\n",
            prog, prog, prog, prog);
}

static int parse_u32(const char *s, uint32_t *out)
{
    char *end = NULL;
    unsigned long v;

    if (s == NULL || *s == '\0' || out == NULL)
        return -1;

    errno = 0;
    v = strtoul(s, &end, 0);
    if (errno != 0 || end == s || *end != '\0' || v > 0xffffffffUL)
        return -1;

    *out = (uint32_t)v;
    return 0;
}

static int parse_u64(const char *s, uint64_t *out)
{
    char *end = NULL;
    unsigned long long v;

    if (s == NULL || *s == '\0' || out == NULL)
        return -1;

    errno = 0;
    v = strtoull(s, &end, 0);
    if (errno != 0 || end == s || *end != '\0')
        return -1;

    *out = (uint64_t)v;
    return 0;
}

static int parse_dev_u64(const char *s, uint64_t *out)
{
    char *colon;
    char major_buf[64];
    char minor_buf[64];
    size_t major_len;
    uint64_t major_v;
    uint64_t minor_v;

    if (s == NULL || out == NULL)
        return -1;

    colon = strchr(s, ':');
    if (colon == NULL)
        return parse_u64(s, out);

    major_len = (size_t)(colon - s);
    if (major_len >= sizeof(major_buf) ||
        strlen(colon + 1) >= sizeof(minor_buf))
        return -1;

    memcpy(major_buf, s, major_len);
    major_buf[major_len] = '\0';
    strcpy(minor_buf, colon + 1);

    if (parse_u64(major_buf, &major_v) != 0 ||
        parse_u64(minor_buf, &minor_v) != 0)
        return -1;

    *out = (uint64_t)makedev((unsigned int)major_v, (unsigned int)minor_v);
    return 0;
}

static int parse_relation_type(const char *s, uint32_t *out)
{
    if (s == NULL || out == NULL)
        return -1;
    if (strcmp(s, "direct_backing_file_reference") == 0 ||
        strcmp(s, "DIRECT_BACKING_FILE_REFERENCE") == 0) {
        *out = 1u;
        return 0;
    }
    return parse_u32(s, out);
}

static int parse_relation_stage(const char *s, uint32_t *out)
{
    if (s == NULL || out == NULL)
        return -1;
    if (strcmp(s, "open_time") == 0 || strcmp(s, "OPEN_TIME") == 0) {
        *out = 1u;
        return 0;
    }
    return parse_u32(s, out);
}

static int parse_decision(const char *s, uint32_t *out)
{
    if (s == NULL || out == NULL)
        return -1;

    if (strcmp(s, "audit") == 0) {
        *out = IGUARD_DECISION_AUDIT;
        return 0;
    }
    if (strcmp(s, "deny") == 0) {
        *out = IGUARD_DECISION_WOULD_DENY;
        return 0;
    }
    return -1;
}

static int safe_copy(char *dst, size_t dst_sz, const char *src)
{
    size_t len;

    if (dst == NULL || dst_sz == 0 || src == NULL)
        return -1;

    len = strlen(src);
    if (len >= dst_sz)
        return -1;

    memcpy(dst, src, len + 1);
    return 0;
}

static int write_fully(int fd, const void *buf, size_t len)
{
    const uint8_t *p = (const uint8_t *)buf;
    size_t off = 0;

    while (off < len) {
        ssize_t n = write(fd, p + off, len - off);
        if (n < 0) {
            if (errno == EINTR)
                continue;
            return -1;
        }
        if (n == 0) {
            errno = EIO;
            return -1;
        }
        off += (size_t)n;
    }
    return 0;
}

static int send_policy_clear(void)
{
    int fd;
    struct iguard_policy_ctl_msg msg;

    memset(&msg, 0, sizeof(msg));
    msg.magic = IGUARD_MAGIC;
    msg.version = IGUARD_VERSION;
    msg.msg_type = IGUARD_MSG_POLICY_CLEAR;
    msg.msg_len = (uint32_t)sizeof(msg);

    fd = open(IGUARD_CTL_PATH, O_WRONLY | O_CLOEXEC);
    if (fd < 0) {
        perror("open(/dev/iguard_ctl)");
        return 1;
    }

    if (write_fully(fd, &msg, sizeof(msg)) != 0) {
        perror("write(policy_clear)");
        close(fd);
        return 1;
    }

    close(fd);
    printf("policy_clear ok\n");
    return 0;
}

static int send_policy_add(int argc, char **argv)
{
    int fd;
    int i;
    int have_decision = 0;
    int have_relation_type = 0;
    int have_relation_stage = 0;
    struct iguard_policy_add_msg_v3 msg;

    memset(&msg, 0, sizeof(msg));
    msg.magic = IGUARD_MAGIC;
    msg.version = IGUARD_VERSION;
    msg.msg_type = IGUARD_MSG_POLICY_ADD;
    msg.msg_len = (uint32_t)sizeof(msg);

    for (i = 2; i < argc; ++i) {
        char *eq;
        char key[64];
        char value[256];
        size_t key_len;
        const char *arg = argv[i];
        uint32_t u32v = 0;
        uint64_t u64v = 0;

        eq = strchr(arg, '=');
        if (eq == NULL) {
            fprintf(stderr, "bad arg (missing '='): %s\n", arg);
            return 1;
        }

        key_len = (size_t)(eq - arg);
        if (key_len == 0 || key_len >= sizeof(key)) {
            fprintf(stderr, "bad key in arg: %s\n", arg);
            return 1;
        }

        memcpy(key, arg, key_len);
        key[key_len] = '\0';

        if (strlen(eq + 1) >= sizeof(value)) {
            fprintf(stderr, "value too long in arg: %s\n", arg);
            return 1;
        }
        strcpy(value, eq + 1);

        if (strcmp(key, "service_id") == 0) {
            if (parse_u32(value, &u32v) != 0) {
                fprintf(stderr, "invalid service_id: %s\n", value);
                return 1;
            }
            msg.service_id = u32v;
        } else if (strcmp(key, "op_id") == 0) {
            if (parse_u32(value, &u32v) != 0) {
                fprintf(stderr, "invalid op_id: %s\n", value);
                return 1;
            }
            msg.op_id = u32v;
        } else if (strcmp(key, "caller_uid") == 0) {
            if (parse_u32(value, &u32v) != 0) {
                fprintf(stderr, "invalid caller_uid: %s\n", value);
                return 1;
            }
            msg.caller_uid = u32v;
        } else if (strcmp(key, "f_flags_mask") == 0) {
            if (parse_u32(value, &u32v) != 0) {
                fprintf(stderr, "invalid f_flags_mask: %s\n", value);
                return 1;
            }
            msg.f_flags_mask = u32v;
        } else if (strcmp(key, "f_flags_value") == 0) {
            if (parse_u32(value, &u32v) != 0) {
                fprintf(stderr, "invalid f_flags_value: %s\n", value);
                return 1;
            }
            msg.f_flags_value = u32v;
        } else if (strcmp(key, "f_mode_mask") == 0) {
            if (parse_u32(value, &u32v) != 0) {
                fprintf(stderr, "invalid f_mode_mask: %s\n", value);
                return 1;
            }
            msg.f_mode_mask = u32v;
        } else if (strcmp(key, "f_mode_value") == 0) {
            if (parse_u32(value, &u32v) != 0) {
                fprintf(stderr, "invalid f_mode_value: %s\n", value);
                return 1;
            }
            msg.f_mode_value = u32v;
        } else if (strcmp(key, "ino") == 0) {
            if (parse_u64(value, &u64v) != 0) {
                fprintf(stderr, "invalid ino: %s\n", value);
                return 1;
            }
            msg.ino = u64v;
        } else if (strcmp(key, "s_dev") == 0) {
            if (parse_dev_u64(value, &u64v) != 0) {
                fprintf(stderr, "invalid s_dev: %s\n", value);
                return 1;
            }
            msg.s_dev = u64v;
        } else if (strcmp(key, "i_mode") == 0) {
            if (parse_u32(value, &u32v) != 0) {
                fprintf(stderr, "invalid i_mode: %s\n", value);
                return 1;
            }
            msg.i_mode = u32v;
        } else if (strcmp(key, "required_relation_type") == 0) {
            if (parse_relation_type(value, &u32v) != 0) {
                fprintf(stderr, "invalid required_relation_type: %s\n", value);
                return 1;
            }
            msg.required_relation_type = u32v;
            have_relation_type = 1;
        } else if (strcmp(key, "required_relation_stage") == 0) {
            if (parse_relation_stage(value, &u32v) != 0) {
                fprintf(stderr, "invalid required_relation_stage: %s\n", value);
                return 1;
            }
            msg.required_relation_stage = u32v;
            have_relation_stage = 1;
        } else if (strcmp(key, "decision") == 0) {
            if (parse_decision(value, &u32v) != 0) {
                fprintf(stderr, "invalid decision: %s\n", value);
                return 1;
            }
            msg.decision_kind = u32v;
            have_decision = 1;
        } else if (strcmp(key, "service") == 0) {
            if (safe_copy(msg.service, sizeof(msg.service), value) != 0) {
                fprintf(stderr, "service too long\n");
                return 1;
            }
        } else if (strcmp(key, "operation") == 0) {
            if (safe_copy(msg.operation, sizeof(msg.operation), value) != 0) {
                fprintf(stderr, "operation too long\n");
                return 1;
            }
        } else if (strcmp(key, "path_tail") == 0) {
            if (safe_copy(msg.path_tail, sizeof(msg.path_tail), value) != 0) {
                fprintf(stderr, "path_tail too long\n");
                return 1;
            }
        } else if (strcmp(key, "reason") == 0) {
            if (safe_copy(msg.reason, sizeof(msg.reason), value) != 0) {
                fprintf(stderr, "reason too long\n");
                return 1;
            }
        } else {
            fprintf(stderr, "unknown key: %s\n", key);
            return 1;
        }
    }

    if (!have_decision) {
        fprintf(stderr, "missing required key: decision=audit|deny\n");
        return 1;
    }
    if (have_relation_type != have_relation_stage) {
        fprintf(stderr, "required_relation_type and required_relation_stage must be supplied together\n");
        return 1;
    }

    if (!have_relation_type && !have_relation_stage) {
        struct iguard_policy_add_msg_v2 msg_v2;

        memset(&msg_v2, 0, sizeof(msg_v2));
        msg_v2.magic = msg.magic;
        msg_v2.version = msg.version;
        msg_v2.msg_type = msg.msg_type;
        msg_v2.msg_len = (uint32_t)sizeof(msg_v2);
        msg_v2.service_id = msg.service_id;
        msg_v2.op_id = msg.op_id;
        msg_v2.caller_uid = msg.caller_uid;
        msg_v2.decision_kind = msg.decision_kind;
        msg_v2.f_flags_mask = msg.f_flags_mask;
        msg_v2.f_flags_value = msg.f_flags_value;
        msg_v2.f_mode_mask = msg.f_mode_mask;
        msg_v2.f_mode_value = msg.f_mode_value;
        msg_v2.ino = msg.ino;
        msg_v2.s_dev = msg.s_dev;
        msg_v2.i_mode = msg.i_mode;
        memcpy(msg_v2.service, msg.service, sizeof(msg_v2.service));
        memcpy(msg_v2.operation, msg.operation, sizeof(msg_v2.operation));
        memcpy(msg_v2.path_tail, msg.path_tail, sizeof(msg_v2.path_tail));
        memcpy(msg_v2.reason, msg.reason, sizeof(msg_v2.reason));

        fd = open(IGUARD_CTL_PATH, O_WRONLY | O_CLOEXEC);
        if (fd < 0) {
            perror("open(/dev/iguard_ctl)");
            return 1;
        }

        if (write_fully(fd, &msg_v2, sizeof(msg_v2)) != 0) {
            perror("write(policy_add)");
            close(fd);
            return 1;
        }

        close(fd);

        printf("policy_add ok: service_id=%u op_id=%u caller_uid=%u decision=%u path_tail=%s reason=%s f_flags_mask=0x%x f_flags_value=0x%x f_mode_mask=0x%x f_mode_value=0x%x ino=%" PRIu64 " s_dev=%" PRIu64 " i_mode=0%o schema=v2\n",
               msg_v2.service_id,
               msg_v2.op_id,
               msg_v2.caller_uid,
               msg_v2.decision_kind,
               msg_v2.path_tail[0] ? msg_v2.path_tail : "-",
               msg_v2.reason[0] ? msg_v2.reason : "-",
               msg_v2.f_flags_mask,
               msg_v2.f_flags_value,
               msg_v2.f_mode_mask,
               msg_v2.f_mode_value,
               msg_v2.ino,
               msg_v2.s_dev,
               msg_v2.i_mode);
        return 0;
    }

    fd = open(IGUARD_CTL_PATH, O_WRONLY | O_CLOEXEC);
    if (fd < 0) {
        perror("open(/dev/iguard_ctl)");
        return 1;
    }

    if (write_fully(fd, &msg, sizeof(msg)) != 0) {
        perror("write(policy_add)");
        close(fd);
        return 1;
    }

    close(fd);

    printf("policy_add ok: service_id=%u op_id=%u caller_uid=%u decision=%u path_tail=%s reason=%s f_flags_mask=0x%x f_flags_value=0x%x f_mode_mask=0x%x f_mode_value=0x%x ino=%" PRIu64 " s_dev=%" PRIu64 " i_mode=0%o required_relation_type=%u required_relation_stage=%u\n",
           msg.service_id,
           msg.op_id,
           msg.caller_uid,
           msg.decision_kind,
           msg.path_tail[0] ? msg.path_tail : "-",
           msg.reason[0] ? msg.reason : "-",
           msg.f_flags_mask,
           msg.f_flags_value,
           msg.f_mode_mask,
           msg.f_mode_value,
           msg.ino,
           msg.s_dev,
           msg.i_mode,
           msg.required_relation_type,
           msg.required_relation_stage);
    return 0;
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        usage(argv[0]);
        return 1;
    }

    if (strcmp(argv[1], "clear") == 0) {
        if (argc != 2) {
            usage(argv[0]);
            return 1;
        }
        return send_policy_clear();
    }

    if (strcmp(argv[1], "add") == 0) {
        if (argc < 3) {
            usage(argv[0]);
            return 1;
        }
        return send_policy_add(argc, argv);
    }

    usage(argv[0]);
    return 1;
}
