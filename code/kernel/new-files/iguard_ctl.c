// SPDX-License-Identifier: GPL-2.0
/*
 * I-Guard minimal control channel
 *
 * Phase 6.2 Step 3:
 *   - print service_id / op_id
 *   - keep service / operation strings
 *   - lightweight audit for zero IDs
 *   - recognize known demo path (1,1)
 *
 * Phase 6.3 Step 2:
 *   - delegation context store moved to built-in kernel core
 *   - control channel only builds seed and publishes it
 *
 * Phase 6.6 Step 1B-1:
 *   - extend /dev/iguard_ctl to accept POLICY_CLEAR / POLICY_ADD
 *   - reuse unified runtime policy helpers from iguard_ctx.c
 *
 * Phase 6.6 Step 2:
 *   - extend POLICY_ADD payload to carry:
 *       f_mode_mask / f_mode_value / ino / s_dev / i_mode
 *   - keep backward compatibility with old v1 POLICY_ADD payload
 *
 * Current stage:
 *   - report / invalidate path kept stable
 *   - runtime policy update path added
 *   - v1 + v2 policy add both accepted
 */

#include <linux/module.h>
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/types.h>
#include <linux/fs.h>
#include <linux/miscdevice.h>
#include <linux/uaccess.h>
#include <linux/string.h>
#include <linux/errno.h>
#include <linux/sched/task.h>
#include <linux/kdev_t.h>
#include <linux/iguard_ctx.h>

#define iguard_ctl_vinfo(fmt, ...)					\
	do {								\
		if (iguard_ctx_verbose_audit_enabled())			\
			pr_info(fmt, ##__VA_ARGS__);			\
	} while (0)


#define IGUARD_DEVICE_NAME              "iguard_ctl"

#define IGUARD_MSG_MAGIC                0x49475544U  /* 'IGUD' */
#define IGUARD_MSG_VERSION              1U

#define IGUARD_MSG_TYPE_REPORT_CALLER   1U
#define IGUARD_MSG_TYPE_INVALIDATE      2U
#define IGUARD_MSG_TYPE_POLICY_CLEAR    3U
#define IGUARD_MSG_TYPE_POLICY_ADD      4U
#define IGUARD_MSG_TYPE_STACK_PUSH      5U
#define IGUARD_MSG_TYPE_STACK_POP       6U

#define IGUARD_SERVICE_LEN              32
#define IGUARD_OP_LEN                   32

#define IGUARD_POLICY_SERVICE_LEN       32
#define IGUARD_POLICY_OP_LEN            32
#define IGUARD_POLICY_PATH_LEN          64
#define IGUARD_POLICY_REASON_LEN        64

#define IGUARD_DECISION_AUDIT_LOCAL        1U
#define IGUARD_DECISION_WOULD_DENY_LOCAL   2U

struct iguard_msg_hdr {
	u32 magic;
	u32 version;
	u32 msg_type;
	u32 msg_len;
};

/*
 * Original report / invalidate protocol.
 *
 * sizeof(struct iguard_msg) is expected to remain 112 for
 * the current userspace sender.
 */
struct iguard_msg {
	u32 magic;
	u32 version;
	u32 msg_type;
	u32 msg_len;

	u32 uid;
	u32 pid;

	u32 service_id;
	u32 op_id;

	char service[IGUARD_SERVICE_LEN];
	char operation[IGUARD_OP_LEN];

	u64 object_id;
	u32 flags;
};

struct iguard_stack_msg {
	u32 magic;
	u32 version;
	u32 msg_type;
	u32 msg_len;

	u32 caller_uid;
	u32 caller_pid;
	u32 service_id;
	u32 op_id;
	u32 server_tid;
	u32 transaction_code;
	u32 transaction_flags;
	u32 nesting_depth;

	u64 sequence_id;
	u64 endpoint_id;
	u64 interface_hash;

	char service[IGUARD_SERVICE_LEN];
	char operation[IGUARD_OP_LEN];
};

/*
 * Minimal control message for clearing runtime overlay rules.
 */
struct iguard_policy_ctl_msg {
	u32 magic;
	u32 version;
	u32 msg_type;
	u32 msg_len;
};

/*
 * Runtime policy add message v1.
 * This is the Phase 6.6 Step 1B-1 shape.
 */
struct iguard_policy_add_msg_v1 {
	u32 magic;
	u32 version;
	u32 msg_type;
	u32 msg_len;

	u32 service_id;
	u32 op_id;
	u32 caller_uid;

	u32 decision_kind;
	u32 f_flags_mask;
	u32 f_flags_value;

	char service[IGUARD_POLICY_SERVICE_LEN];
	char operation[IGUARD_POLICY_OP_LEN];
	char path_tail[IGUARD_POLICY_PATH_LEN];
	char reason[IGUARD_POLICY_REASON_LEN];
};

/*
 * Runtime policy add message v2.
 * Step 2 extension, appended after v1 so old senders can still work.
 */
struct iguard_policy_add_msg_v2 {
	u32 magic;
	u32 version;
	u32 msg_type;
	u32 msg_len;

	u32 service_id;
	u32 op_id;
	u32 caller_uid;

	u32 decision_kind;
	u32 f_flags_mask;
	u32 f_flags_value;

	char service[IGUARD_POLICY_SERVICE_LEN];
	char operation[IGUARD_POLICY_OP_LEN];
	char path_tail[IGUARD_POLICY_PATH_LEN];
	char reason[IGUARD_POLICY_REASON_LEN];

	u32 f_mode_mask;
	u32 f_mode_value;

	u64 ino;
	u64 s_dev;
	u32 i_mode;
};

static void iguard_copy_fixed_field(char *dst, size_t dst_sz,
				    const char *src, size_t src_sz)
{
	size_t n;

	if (!dst || dst_sz == 0)
		return;

	memset(dst, 0, dst_sz);

	if (!src || src_sz == 0)
		return;

	n = min(dst_sz - 1, src_sz);
	memcpy(dst, src, n);
	dst[dst_sz - 1] = '\0';
}

static int iguard_handle_stack_push(struct iguard_stack_msg *msg)
{
	struct iguard_ctx_seed seed;
	pid_t tid = task_pid_nr(current);

	if (msg->msg_len != sizeof(*msg)) {
		pr_warn("iguard_ctl: stack-push bad msg_len=%u expected=%zu\n",
			msg->msg_len, sizeof(*msg));
		return -EINVAL;
	}

	msg->service[sizeof(msg->service) - 1] = '\0';
	msg->operation[sizeof(msg->operation) - 1] = '\0';

	if (msg->server_tid != 0 && msg->server_tid != (u32)tid) {
		pr_warn("CDAC_BINDER_STACK_MISMATCH event=push_tid_mismatch claimed_tid=%u actual_tid=%d seq=%llu\n",
			msg->server_tid, tid, (unsigned long long)msg->sequence_id);
	}

	memset(&seed, 0, sizeof(seed));
	seed.caller_uid = msg->caller_uid;
	seed.caller_pid = msg->caller_pid;
	seed.service_id = msg->service_id;
	seed.op_id = msg->op_id;
	seed.transaction_code = msg->transaction_code;
	seed.transaction_flags = msg->transaction_flags;
	seed.nesting_depth = msg->nesting_depth;
	seed.sequence_id = msg->sequence_id;
	seed.endpoint_id = msg->endpoint_id;
	seed.interface_hash = msg->interface_hash;
	iguard_copy_fixed_field(seed.service, sizeof(seed.service),
				msg->service, sizeof(msg->service));
	iguard_copy_fixed_field(seed.operation, sizeof(seed.operation),
				msg->operation, sizeof(msg->operation));

	pr_info("CDAC_BINDER_ENTER_CTL source=UNIFIED_BINDER_HOOK seq=%llu current_tgid=%d current_tid=%d caller_uid=%u caller_pid=%u endpoint_id=%llu service_id=%u op_id=%u transaction_code=%u transaction_flags=0x%x nesting_depth=%u service=%s op=%s\n",
		(unsigned long long)msg->sequence_id,
		task_tgid_nr(current),
		tid,
		msg->caller_uid,
		msg->caller_pid,
		(unsigned long long)msg->endpoint_id,
		msg->service_id,
		msg->op_id,
		msg->transaction_code,
		msg->transaction_flags,
		msg->nesting_depth,
		msg->service,
		msg->operation);

	return iguard_ctx_push_from_current(&seed);
}

static int iguard_handle_stack_pop(struct iguard_stack_msg *msg)
{
	pid_t tid = task_pid_nr(current);

	if (msg->msg_len != sizeof(*msg)) {
		pr_warn("iguard_ctl: stack-pop bad msg_len=%u expected=%zu\n",
			msg->msg_len, sizeof(*msg));
		return -EINVAL;
	}

	msg->service[sizeof(msg->service) - 1] = '\0';
	msg->operation[sizeof(msg->operation) - 1] = '\0';

	if (msg->server_tid != 0 && msg->server_tid != (u32)tid) {
		pr_warn("CDAC_BINDER_STACK_MISMATCH event=pop_tid_mismatch claimed_tid=%u actual_tid=%d seq=%llu\n",
			msg->server_tid, tid, (unsigned long long)msg->sequence_id);
	}

	pr_info("CDAC_BINDER_EXIT_CTL source=UNIFIED_BINDER_HOOK seq=%llu current_tgid=%d current_tid=%d endpoint_id=%llu service_id=%u op_id=%u transaction_code=%u transaction_flags=0x%x nesting_depth=%u service=%s op=%s\n",
		(unsigned long long)msg->sequence_id,
		task_tgid_nr(current),
		tid,
		(unsigned long long)msg->endpoint_id,
		msg->service_id,
		msg->op_id,
		msg->transaction_code,
		msg->transaction_flags,
		msg->nesting_depth,
		msg->service,
		msg->operation);

	return iguard_ctx_pop_current(msg->sequence_id, msg->nesting_depth);
}

static int iguard_handle_policy_clear(const struct iguard_policy_ctl_msg *msg)
{
	if (msg->msg_len != sizeof(*msg)) {
		pr_warn("iguard_ctl: policy-clear bad msg_len=%u expected=%zu\n",
			msg->msg_len, sizeof(*msg));
		return -EINVAL;
	}

	pr_info("iguard_ctl: policy-clear received version=%u len=%u\n",
		msg->version, msg->msg_len);

	return iguard_ctx_runtime_policy_clear_all();
}

static int iguard_validate_decision_kind(u32 decision_kind)
{
	switch (decision_kind) {
	case IGUARD_DECISION_AUDIT_LOCAL:
	case IGUARD_DECISION_WOULD_DENY_LOCAL:
		return 0;
	default:
		return -EINVAL;
	}
}

static int iguard_handle_policy_add_v1(struct iguard_policy_add_msg_v1 *msg)
{
	int ret;

	if (msg->msg_len != sizeof(*msg)) {
		pr_warn("iguard_ctl: policy-add-v1 bad msg_len=%u expected=%zu\n",
			msg->msg_len, sizeof(*msg));
		return -EINVAL;
	}

	msg->service[sizeof(msg->service) - 1] = '\0';
	msg->operation[sizeof(msg->operation) - 1] = '\0';
	msg->path_tail[sizeof(msg->path_tail) - 1] = '\0';
	msg->reason[sizeof(msg->reason) - 1] = '\0';

	ret = iguard_validate_decision_kind(msg->decision_kind);
	if (ret) {
		pr_warn("iguard_ctl: policy-add-v1 bad decision_kind=%u\n",
			msg->decision_kind);
		return ret;
	}

	pr_info("iguard_ctl: policy-add-v1 service_id=%u op_id=%u caller_uid=%u service=%s operation=%s path_tail=%s decision=%u f_flags_mask=0x%x f_flags_value=0x%x reason=%s\n",
		msg->service_id,
		msg->op_id,
		msg->caller_uid,
		msg->service[0] ? msg->service : "-",
		msg->operation[0] ? msg->operation : "-",
		msg->path_tail[0] ? msg->path_tail : "-",
		msg->decision_kind,
		msg->f_flags_mask,
		msg->f_flags_value,
		msg->reason[0] ? msg->reason : "-");

	return iguard_ctx_runtime_policy_add_rule_fields(
			msg->service_id,
			msg->op_id,
			msg->caller_uid,
			msg->decision_kind,
			(int)msg->f_flags_mask,
			(int)msg->f_flags_value,
			0,
			0,
			0,
			0,
			0,
			msg->service[0] ? msg->service : NULL,
			msg->operation[0] ? msg->operation : NULL,
			msg->path_tail[0] ? msg->path_tail : NULL,
			msg->reason[0] ? msg->reason : NULL);
}

static int iguard_handle_policy_add_v2(struct iguard_policy_add_msg_v2 *msg)
{
	int ret;

	if (msg->msg_len != sizeof(*msg)) {
		pr_warn("iguard_ctl: policy-add-v2 bad msg_len=%u expected=%zu\n",
			msg->msg_len, sizeof(*msg));
		return -EINVAL;
	}

	msg->service[sizeof(msg->service) - 1] = '\0';
	msg->operation[sizeof(msg->operation) - 1] = '\0';
	msg->path_tail[sizeof(msg->path_tail) - 1] = '\0';
	msg->reason[sizeof(msg->reason) - 1] = '\0';

	ret = iguard_validate_decision_kind(msg->decision_kind);
	if (ret) {
		pr_warn("iguard_ctl: policy-add-v2 bad decision_kind=%u\n",
			msg->decision_kind);
		return ret;
	}

	pr_info("iguard_ctl: policy-add-v2 service_id=%u op_id=%u caller_uid=%u service=%s operation=%s path_tail=%s decision=%u f_flags_mask=0x%x f_flags_value=0x%x f_mode_mask=0x%x f_mode_value=0x%x ino=%llu s_dev=%u:%u i_mode=0%o reason=%s\n",
		msg->service_id,
		msg->op_id,
		msg->caller_uid,
		msg->service[0] ? msg->service : "-",
		msg->operation[0] ? msg->operation : "-",
		msg->path_tail[0] ? msg->path_tail : "-",
		msg->decision_kind,
		msg->f_flags_mask,
		msg->f_flags_value,
		msg->f_mode_mask,
		msg->f_mode_value,
		(unsigned long long)msg->ino,
		MAJOR((dev_t)msg->s_dev), MINOR((dev_t)msg->s_dev),
		msg->i_mode,
		msg->reason[0] ? msg->reason : "-");

	return iguard_ctx_runtime_policy_add_rule_fields(
			msg->service_id,
			msg->op_id,
			msg->caller_uid,
			msg->decision_kind,
			(int)msg->f_flags_mask,
			(int)msg->f_flags_value,
			(int)msg->f_mode_mask,
			(int)msg->f_mode_value,
			(u64)msg->ino,
			(u64)msg->s_dev,
			(u32)msg->i_mode,
			msg->service[0] ? msg->service : NULL,
			msg->operation[0] ? msg->operation : NULL,
			msg->path_tail[0] ? msg->path_tail : NULL,
			msg->reason[0] ? msg->reason : NULL);
}

static ssize_t iguard_ctl_write(struct file *file, const char __user *buf,
				size_t len, loff_t *ppos)
{
	struct iguard_msg_hdr hdr;
	int ret;

	if (!buf)
		return -EINVAL;

	if (len < sizeof(hdr)) {
		pr_warn("CDAC_CTL_REJECT reason=INVALID_LENGTH len=%zu hdr=%zu\n",
			len, sizeof(hdr));
		return -EINVAL;
	}

	memset(&hdr, 0, sizeof(hdr));

	if (copy_from_user(&hdr, buf, sizeof(hdr))) {
		pr_warn("iguard_ctl: copy_from_user hdr failed\n");
		return -EFAULT;
	}

	if (hdr.magic != IGUARD_MSG_MAGIC) {
		pr_warn("CDAC_CTL_REJECT reason=BAD_MAGIC magic=0x%x expected=0x%x\n",
			hdr.magic, IGUARD_MSG_MAGIC);
		return -EINVAL;
	}

	if (hdr.version != IGUARD_MSG_VERSION) {
		pr_warn("CDAC_CTL_REJECT reason=UNKNOWN_VERSION version=%u expected=%u type=%u len=%zu\n",
			hdr.version, IGUARD_MSG_VERSION, hdr.msg_type, len);
		return -EINVAL;
	}

	switch (hdr.msg_type) {
	case IGUARD_MSG_TYPE_REPORT_CALLER: {
		pr_warn("CDAC_CTL_REJECT reason=LEGACY_MESSAGE type=%u len=%zu msg_len=%u\n",
			hdr.msg_type, len, hdr.msg_len);
		return -EPROTO;
	}

	case IGUARD_MSG_TYPE_INVALIDATE: {
		pr_warn("CDAC_CTL_REJECT reason=LEGACY_MESSAGE type=%u len=%zu msg_len=%u\n",
			hdr.msg_type, len, hdr.msg_len);
		return -EPROTO;
	}

		case IGUARD_MSG_TYPE_STACK_PUSH:
		case IGUARD_MSG_TYPE_STACK_POP: {
			struct iguard_stack_msg msg;

				if (len != sizeof(msg)) {
					pr_warn("CDAC_CTL_REJECT reason=INVALID_LENGTH len=%zu expected=%zu type=%u\n",
						len, sizeof(msg), hdr.msg_type);
					return -EINVAL;
				}
				if (hdr.msg_len != sizeof(msg)) {
					pr_warn("CDAC_CTL_REJECT reason=INVALID_LENGTH msg_len=%u expected=%zu type=%u len=%zu\n",
						hdr.msg_len, sizeof(msg), hdr.msg_type, len);
					return -EINVAL;
				}
			memset(&msg, 0, sizeof(msg));
			if (copy_from_user(&msg, buf, sizeof(msg))) {
				pr_warn("iguard_ctl: copy_from_user stack failed type=%u\n",
					hdr.msg_type);
				return -EFAULT;
			}

			ret = hdr.msg_type == IGUARD_MSG_TYPE_STACK_PUSH ?
				iguard_handle_stack_push(&msg) :
				iguard_handle_stack_pop(&msg);
			if (ret)
				return ret;
			return len;
		}

		case IGUARD_MSG_TYPE_POLICY_CLEAR: {
		struct iguard_policy_ctl_msg msg;

		if (len != sizeof(msg)) {
			pr_warn("iguard_ctl: invalid policy-clear len=%zu expected=%zu\n",
				len, sizeof(msg));
			return -EINVAL;
		}
		if (hdr.msg_len != sizeof(msg)) {
			pr_warn("iguard_ctl: bad policy-clear msg_len=%u expected=%zu\n",
				hdr.msg_len, sizeof(msg));
			return -EINVAL;
		}

		memset(&msg, 0, sizeof(msg));
		if (copy_from_user(&msg, buf, sizeof(msg))) {
			pr_warn("iguard_ctl: copy_from_user policy-clear failed\n");
			return -EFAULT;
		}

		ret = iguard_handle_policy_clear(&msg);
		if (ret)
			return ret;
		return len;
	}

	case IGUARD_MSG_TYPE_POLICY_ADD: {
		/*
		 * Backward-compatible dispatch:
		 * - old sender => v1
		 * - new sender => v2
		 */
		if (len == sizeof(struct iguard_policy_add_msg_v1)) {
			struct iguard_policy_add_msg_v1 msg;

			if (hdr.msg_len != sizeof(msg)) {
				pr_warn("iguard_ctl: bad policy-add-v1 msg_len=%u expected=%zu\n",
					hdr.msg_len, sizeof(msg));
				return -EINVAL;
			}

			memset(&msg, 0, sizeof(msg));
			if (copy_from_user(&msg, buf, sizeof(msg))) {
				pr_warn("iguard_ctl: copy_from_user policy-add-v1 failed\n");
				return -EFAULT;
			}

			ret = iguard_handle_policy_add_v1(&msg);
			if (ret)
				return ret;
			return len;
		}

		if (len == sizeof(struct iguard_policy_add_msg_v2)) {
			struct iguard_policy_add_msg_v2 msg;

			if (hdr.msg_len != sizeof(msg)) {
				pr_warn("iguard_ctl: bad policy-add-v2 msg_len=%u expected=%zu\n",
					hdr.msg_len, sizeof(msg));
				return -EINVAL;
			}

			memset(&msg, 0, sizeof(msg));
			if (copy_from_user(&msg, buf, sizeof(msg))) {
				pr_warn("iguard_ctl: copy_from_user policy-add-v2 failed\n");
				return -EFAULT;
			}

			ret = iguard_handle_policy_add_v2(&msg);
			if (ret)
				return ret;
			return len;
		}

		pr_warn("iguard_ctl: invalid policy-add len=%zu expected=%zu(v1) or %zu(v2)\n",
			len,
			sizeof(struct iguard_policy_add_msg_v1),
			sizeof(struct iguard_policy_add_msg_v2));
		return -EINVAL;
	}

		default:
			pr_warn("CDAC_CTL_REJECT reason=UNKNOWN_TYPE type=%u expected=%u|%u|%u|%u\n",
				hdr.msg_type,
				IGUARD_MSG_TYPE_POLICY_CLEAR,
				IGUARD_MSG_TYPE_POLICY_ADD,
				IGUARD_MSG_TYPE_STACK_PUSH,
				IGUARD_MSG_TYPE_STACK_POP);
			return -EINVAL;
		}
}

static const struct file_operations iguard_ctl_fops = {
	.owner = THIS_MODULE,
	.write = iguard_ctl_write,
	.llseek = noop_llseek,
};

static struct miscdevice iguard_ctl_miscdev = {
	.minor = MISC_DYNAMIC_MINOR,
	.name = IGUARD_DEVICE_NAME,
	.fops = &iguard_ctl_fops,
};

static int __init iguard_ctl_init(void)
{
	int ret;

	ret = misc_register(&iguard_ctl_miscdev);
	if (ret) {
		pr_err("iguard_ctl: misc_register failed ret=%d\n", ret);
		return ret;
	}

	pr_info("iguard_ctl: registered /dev/%s sizeof(iguard_msg)=%zu sizeof(policy_ctl)=%zu sizeof(policy_add_v1)=%zu sizeof(policy_add_v2)=%zu\n",
		IGUARD_DEVICE_NAME,
		sizeof(struct iguard_msg),
		sizeof(struct iguard_policy_ctl_msg),
		sizeof(struct iguard_policy_add_msg_v1),
		sizeof(struct iguard_policy_add_msg_v2));
	return 0;
}

static void __exit iguard_ctl_exit(void)
{
	misc_deregister(&iguard_ctl_miscdev);
	pr_info("iguard_ctl: unloaded\n");
}

module_init(iguard_ctl_init);
module_exit(iguard_ctl_exit);

MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("I-Guard control channel using built-in delegation context core and runtime policy overlay");
