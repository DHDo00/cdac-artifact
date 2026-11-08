/* SPDX-License-Identifier: GPL-2.0 */
#ifndef _LINUX_IGUARD_CTX_H
#define _LINUX_IGUARD_CTX_H

#include <linux/types.h>

struct file;

#define IGUARD_CTX_SERVICE_LEN 32
#define IGUARD_CTX_OP_LEN      32
#define IGUARD_CTX_MAX_DEPTH   16

#define IGUARD_RELATION_TYPE_DIRECT_BACKING_FILE_REFERENCE 1U
#define IGUARD_RELATION_STAGE_OPEN_TIME                    1U

struct iguard_ctx_seed {
	u32 caller_uid;
	u32 caller_pid;

	u32 service_id;
	u32 op_id;
	u32 transaction_code;
	u32 transaction_flags;
	u32 nesting_depth;

	u64 sequence_id;
	u64 endpoint_id;
	u64 interface_hash;
	char service[IGUARD_CTX_SERVICE_LEN];
	char operation[IGUARD_CTX_OP_LEN];
};

struct iguard_deleg_ctx {
	pid_t reporter_tgid;
	pid_t reporter_tid;

	u32 caller_uid;
	u32 caller_pid;

	u32 service_id;
	u32 op_id;
	u32 transaction_code;
	u32 transaction_flags;
	u32 nesting_depth;

	u64 endpoint_id;
	u64 interface_hash;
	char service[IGUARD_CTX_SERVICE_LEN];
	char operation[IGUARD_CTX_OP_LEN];

	u64 seqno;
	u64 ts_ns;
	bool active;
};

struct iguard_relation_decision_input {
	u32 relation_type;
	u32 relation_stage;
	u64 connection_major;
	u64 connection_minor;
	u64 nodeid;
	u64 mapping_generation;
	u64 relation_id_for_logging;
	u64 lower_file_cookie;
	u64 proxy_file_cookie;
	u64 lower_inode;
	u64 lower_s_dev;
	int lower_f_flags;
	u32 lower_f_mode;
	u64 proxy_inode;
	u64 proxy_s_dev;
	int proxy_f_flags;
	u32 proxy_f_mode;
	bool relation_complete;
	bool relation_ambiguous;
	bool relation_stale;
	bool native_allowed;
	const char *source;
};

/* Core ctx lifecycle */
int iguard_ctx_publish_from_current(const struct iguard_ctx_seed *seed);
int iguard_ctx_push_from_current(const struct iguard_ctx_seed *seed);
int iguard_ctx_pop_current(u64 sequence_id, u32 nesting_depth);
bool iguard_ctx_lookup_current(struct iguard_deleg_ctx *out);
void iguard_ctx_invalidate_current(void);
bool iguard_ctx_verbose_audit_enabled(void);
u64 iguard_audit_next_seq(void);

/* Object-side hook entry */
int iguard_ctx_audit_file_open(struct file *file);
int iguard_ctx_apply_relation_decision(
		const struct iguard_relation_decision_input *input);

/* Generic descriptor-lineage audit helpers. */
u64 iguard_file_cookie(const struct file *file);
void iguard_file_cookie_release(const struct file *file);
void iguard_audit_fd_install(unsigned int fd, struct file *file);
void iguard_audit_receive_fd_result(unsigned int fd, struct file *file,
				    unsigned int o_flags, int result);
void iguard_audit_binder_fd_send(pid_t sender_pid, pid_t sender_tid,
				 pid_t receiver_pid, u32 source_fd,
				 int binder_transaction_id,
				 struct file *file);
void iguard_audit_binder_fd_recv(pid_t receiver_pid, pid_t receiver_tid,
				 unsigned int receiver_fd,
				 int binder_transaction_id,
				 struct file *file);
void iguard_audit_rust_binder_fd_transfer(u32 stage,
					   pid_t sender_pid,
					   pid_t sender_tid,
					   u32 sender_fd,
					   pid_t receiver_pid,
					   pid_t receiver_tid,
					   u32 receiver_fd,
					   int binder_transaction_id,
					   struct file *file,
					   int result);

/*
 * Runtime policy overlay helpers.
 *
 * Keep the public header narrow: callers pass rule fields directly, without
 * depending on the internal policy-rule layout used inside iguard_ctx.c.
 *
 * Field semantics:
 * - numeric 0 means "unset" for service_id/op_id/caller_uid/ino/s_dev/i_mode
 * - *_mask == 0 means "unset" for f_flags / f_mode matching
 * - NULL or empty string means "unset" for service / operation / path_tail /
 *   reason
 *
 * decision_kind:
 * - 0 => audit / allow-for-now
 * - 1 => deny
 */
int iguard_ctx_runtime_policy_clear_all(void);

int iguard_ctx_runtime_policy_add_rule_fields(u32 service_id,
					      u32 op_id,
					      u32 caller_uid,
					      u32 decision_kind,
					      int f_flags_mask,
					      int f_flags_value,
					      int f_mode_mask,
					      int f_mode_value,
					      u64 ino,
					      u64 s_dev,
					      u32 i_mode,
					      const char *service,
					      const char *operation,
						      const char *path_tail,
						      const char *reason);

int iguard_ctx_runtime_policy_add_relation_rule_fields(
						      u32 service_id,
						      u32 op_id,
						      u32 caller_uid,
						      u32 decision_kind,
						      u64 ino,
						      u64 s_dev,
						      u32 required_relation_type,
						      u32 required_relation_stage,
						      const char *service,
						      const char *operation,
						      const char *reason);

#endif /* _LINUX_IGUARD_CTX_H */
