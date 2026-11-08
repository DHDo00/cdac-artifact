// SPDX-License-Identifier: GPL-2.0
/*
 * I-Guard delegation context core
 *
 * Built-in kernel context store for per-thread delegation context.
 * Current stage:
 *   - publish / lookup / invalidate
 *   - object-side consume
 *   - minimal decision / apply / enforce-plan skeleton
 *   - real deny already enabled at corrected object-side hook
 *   - Phase 6.5 Step 1: static policy table replaces single hardcoded rule
 *   - Phase 6.5 Step 2: object-side features are unified as iguard_object_key
 *   - Phase 6.5 Step 3: policy_rule supports optional object-field matching
 *   - Phase 6.6 Step 1A: runtime policy overlay via debugfs
 *   - Phase 6.6 Step 1B-1: exported narrow runtime policy helpers for ctl path
 *   - Phase 6.6 Step 2: narrow helpers / debugfs parser / dump extended to
 *     f_mode / ino / s_dev / i_mode while preserving existing semantics
 *   - Phase 6.7 Step 3: decision log now prints specificity + object metadata
 *   - Phase 7.1 Step 1: minimal performance timing for decision/apply path
 *     and runtime policy add/clear operations
 *   - Phase 7.2 A3: debugfs ablation knob to bypass runtime overlay lookup
 *     while preserving runtime rule loading / dump visibility
 *   - Phase 7.2 A2: debugfs ablation knob to bypass per-thread context
 *     publish while preserving report/invalidate traffic
 *   - Phase 7.2 A1: debugfs ablation knob to keep only path_tail and remove
 *     rich object-side metadata before policy matching
 */

#include <linux/module.h>
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/errno.h>
#include <linux/hashtable.h>
#include <linux/ktime.h>
#include <linux/slab.h>
#include <linux/spinlock.h>
#include <linux/string.h>
#include <linux/sched.h>
#include <linux/fs.h>
#include <linux/dcache.h>
#include <linux/kdev_t.h>
#include <linux/iguard_ctx.h>
#include <linux/fcntl.h>
#include <linux/debugfs.h>
#include <linux/seq_file.h>
#include <linux/uaccess.h>
#include <linux/mutex.h>
#include <linux/err.h>
#include <linux/hash.h>
#include <linux/percpu.h>
#include <linux/seqlock.h>

#define IGUARD_CTX_HASH_BITS 6
#define IGUARD_FILE_COOKIE_HASH_BITS 12
#define IGUARD_QUIET_COUNTER_SCHEMA_VERSION 2
#define IGUARD_FD_TARGET_OBJECT_MAX 64

struct iguard_ctx_entry {
	struct hlist_node node;
	pid_t reporter_tid;
	u32 depth;
	bool poisoned;
	struct iguard_deleg_ctx stack[IGUARD_CTX_MAX_DEPTH];
};

static DEFINE_HASHTABLE(iguard_ctx_table, IGUARD_CTX_HASH_BITS);
static DEFINE_SPINLOCK(iguard_ctx_lock);
static atomic64_t iguard_ctx_seq = ATOMIC64_INIT(0);

struct iguard_file_cookie_entry {
	struct hlist_node node;
	const struct file *file;
	u64 cookie;
};

static DEFINE_HASHTABLE(iguard_file_cookie_table,
			IGUARD_FILE_COOKIE_HASH_BITS);
static DEFINE_SPINLOCK(iguard_file_cookie_lock);
static atomic64_t iguard_file_cookie_seq = ATOMIC64_INIT(0);

/*
 * Ablation knobs are declared early because publish path uses
 * iguard_ablate_disable_ctx before the decision-helper section.
 */
static bool iguard_ablate_disable_ctx;
static bool iguard_ablate_disable_runtime;
static bool iguard_ablate_path_tail_only;

/*
 * Phase 7.2 overhead breakdown knob.
 *
 * When enabled, keep validation-oriented verbose audit logs.
 * When disabled, suppress high-frequency allow-path logs and keep
 * warnings, errors, control-plane policy logs, and real-enforce logs.
 */
static bool iguard_verbose_audit = true;
static atomic64_t iguard_audit_seq = ATOMIC64_INIT(0);

struct iguard_quiet_counters {
	u64 context_push_ok;
	u64 context_push_fail;
	u64 context_pop_ok;
	u64 context_pop_fail;
	u64 context_lookup_hit;
	u64 context_lookup_miss;
	u64 relation_decision;
	u64 relation_complete;
	u64 relation_incomplete;
	u64 relation_stale;
	u64 relation_rule_match;
	u64 relation_rule_nonmatch;
	u64 relation_deny;
	u64 relation_allow;
	u64 file_open_join;
	u64 file_open_no_context;
	u64 file_open_deny;
	u64 relation_publish_total;
	u64 relation_unpaired;
	u64 fd_receive_event_total;
	u64 fd_receiver_install_attempt_total;
	u64 fd_receiver_install_success_total;
	u64 fd_receiver_install_failure_total;
	u64 frdac_target_fd_transfer_attempt_total;
	u64 frdac_target_receiver_install_success_total;
	u64 frdac_target_receiver_install_failure_total;
	u64 frdac_denied_internal_fd_acquire_total;
	u64 frdac_denied_internal_fd_release_total;
	u64 frdac_denied_internal_fd_outstanding;
	u64 frdac_denied_app_fd_install_total;
};

static DEFINE_PER_CPU(struct iguard_quiet_counters, iguard_qc);

#define IGUARD_QC_INC(field)	this_cpu_inc(iguard_qc.field)
#define IGUARD_QC_SUM(field)						\
	({								\
		u64 __total = 0;					\
		int __cpu;						\
		for_each_possible_cpu(__cpu)				\
			__total += per_cpu(iguard_qc, __cpu).field;	\
		__total;						\
	})

bool iguard_ctx_verbose_audit_enabled(void)
{
	return READ_ONCE(iguard_verbose_audit);
}
EXPORT_SYMBOL_GPL(iguard_ctx_verbose_audit_enabled);

u64 iguard_audit_next_seq(void)
{
	return atomic64_inc_return(&iguard_audit_seq);
}
EXPORT_SYMBOL_GPL(iguard_audit_next_seq);

#define iguard_vinfo(fmt, ...)						\
	do {								\
		if (READ_ONCE(iguard_verbose_audit))			\
			pr_info(fmt, ##__VA_ARGS__);			\
	} while (0)

struct iguard_fd_target_object {
	unsigned long ino;
	dev_t s_dev;
};

struct iguard_fd_target_proxy {
	u64 file_cookie;
};

static DEFINE_SEQLOCK(iguard_fd_target_lock);
static struct iguard_fd_target_object
	iguard_fd_target_objects[IGUARD_FD_TARGET_OBJECT_MAX];
static struct iguard_fd_target_proxy
	iguard_fd_target_proxies[IGUARD_FD_TARGET_OBJECT_MAX];
static u32 iguard_fd_target_object_count;
static u32 iguard_fd_target_proxy_count;

static void iguard_fd_target_cache_rebuild_locked(void);

u64 iguard_file_cookie(const struct file *file)
{
	struct iguard_file_cookie_entry *entry;
	struct iguard_file_cookie_entry *new_entry = NULL;
	unsigned long flags;
	u64 cookie;

	if (!file)
		return 0;

	spin_lock_irqsave(&iguard_file_cookie_lock, flags);
	hash_for_each_possible(iguard_file_cookie_table, entry, node,
			       (unsigned long)file) {
		if (entry->file == file) {
			cookie = entry->cookie;
			spin_unlock_irqrestore(&iguard_file_cookie_lock, flags);
			return cookie;
		}
	}
	spin_unlock_irqrestore(&iguard_file_cookie_lock, flags);

	new_entry = kmalloc(sizeof(*new_entry), GFP_ATOMIC);
	if (!new_entry)
		return 0;

	new_entry->file = file;
	new_entry->cookie = atomic64_inc_return(&iguard_file_cookie_seq);

	spin_lock_irqsave(&iguard_file_cookie_lock, flags);
	hash_for_each_possible(iguard_file_cookie_table, entry, node,
			       (unsigned long)file) {
		if (entry->file == file) {
			cookie = entry->cookie;
			spin_unlock_irqrestore(&iguard_file_cookie_lock, flags);
			kfree(new_entry);
			return cookie;
		}
	}
	hash_add(iguard_file_cookie_table, &new_entry->node,
		 (unsigned long)file);
	cookie = new_entry->cookie;
	spin_unlock_irqrestore(&iguard_file_cookie_lock, flags);

	return cookie;
}
EXPORT_SYMBOL_GPL(iguard_file_cookie);

void iguard_file_cookie_release(const struct file *file)
{
	struct iguard_file_cookie_entry *entry;
	unsigned long flags;

	if (!file)
		return;

	spin_lock_irqsave(&iguard_file_cookie_lock, flags);
	hash_for_each_possible(iguard_file_cookie_table, entry, node,
			       (unsigned long)file) {
		if (entry->file == file) {
			hash_del(&entry->node);
			spin_unlock_irqrestore(&iguard_file_cookie_lock, flags);
			kfree(entry);
			return;
		}
	}
	spin_unlock_irqrestore(&iguard_file_cookie_lock, flags);
}
EXPORT_SYMBOL_GPL(iguard_file_cookie_release);

static void iguard_file_identity(const struct file *file,
				 unsigned long *ino,
				 dev_t *s_dev,
				 umode_t *i_mode,
				 int *f_flags,
				 fmode_t *f_mode)
{
	struct inode *inode;

	if (ino)
		*ino = 0;
	if (s_dev)
		*s_dev = 0;
	if (i_mode)
		*i_mode = 0;
	if (f_flags)
		*f_flags = 0;
	if (f_mode)
		*f_mode = 0;

	if (!file)
		return;

	inode = file_inode((struct file *)file);
	if (!inode)
		return;

	if (ino)
		*ino = (unsigned long)inode->i_ino;
	if (s_dev && inode->i_sb)
		*s_dev = inode->i_sb->s_dev;
	if (i_mode)
		*i_mode = inode->i_mode;
	if (f_flags)
		*f_flags = file->f_flags;
	if (f_mode)
		*f_mode = file->f_mode;
}

static bool iguard_target_object_match(unsigned long ino, dev_t s_dev)
{
	unsigned int seq;
	u32 count;
	u32 i;
	bool matched;

	if (!ino || !s_dev)
		return false;

	do {
		seq = read_seqbegin(&iguard_fd_target_lock);
		matched = false;
		count = READ_ONCE(iguard_fd_target_object_count);
		if (count > IGUARD_FD_TARGET_OBJECT_MAX)
			count = IGUARD_FD_TARGET_OBJECT_MAX;
		for (i = 0; i < count; i++) {
			if (iguard_fd_target_objects[i].ino == ino &&
			    iguard_fd_target_objects[i].s_dev == s_dev) {
				matched = true;
				break;
			}
		}
	} while (read_seqretry(&iguard_fd_target_lock, seq));

	return matched;
}

static bool iguard_target_proxy_cookie_match(u64 file_cookie)
{
	unsigned int seq;
	u32 count;
	u32 i;
	bool matched;

	if (!file_cookie)
		return false;

	do {
		seq = read_seqbegin(&iguard_fd_target_lock);
		matched = false;
		count = READ_ONCE(iguard_fd_target_proxy_count);
		if (count > IGUARD_FD_TARGET_OBJECT_MAX)
			count = IGUARD_FD_TARGET_OBJECT_MAX;
		for (i = 0; i < count; i++) {
			if (iguard_fd_target_proxies[i].file_cookie == file_cookie) {
				matched = true;
				break;
			}
		}
	} while (read_seqretry(&iguard_fd_target_lock, seq));

	return matched;
}

static void iguard_fd_target_proxy_track(u64 proxy_file_cookie)
{
	u32 count;
	u32 i;

	if (!proxy_file_cookie)
		return;

	write_seqlock(&iguard_fd_target_lock);
	count = READ_ONCE(iguard_fd_target_proxy_count);
	if (count > IGUARD_FD_TARGET_OBJECT_MAX)
		count = IGUARD_FD_TARGET_OBJECT_MAX;
	for (i = 0; i < count; i++) {
		if (iguard_fd_target_proxies[i].file_cookie == proxy_file_cookie)
			goto out;
	}
	if (count < IGUARD_FD_TARGET_OBJECT_MAX) {
		iguard_fd_target_proxies[count].file_cookie = proxy_file_cookie;
		count++;
		WRITE_ONCE(iguard_fd_target_proxy_count, count);
	}
out:
	write_sequnlock(&iguard_fd_target_lock);
}

static bool iguard_file_is_tracked_target(const struct file *file)
{
	unsigned long ino = 0;
	dev_t s_dev = 0;

	if (!file)
		return false;

	if (!READ_ONCE(iguard_fd_target_object_count) &&
	    !READ_ONCE(iguard_fd_target_proxy_count))
		return false;

	iguard_file_identity(file, &ino, &s_dev, NULL, NULL, NULL);
	if (iguard_target_object_match(ino, s_dev))
		return true;

	return iguard_target_proxy_cookie_match(iguard_file_cookie(file));
}

void iguard_audit_fd_install(unsigned int fd, struct file *file)
{
	unsigned long ino;
	dev_t s_dev;
	umode_t i_mode;
	int f_flags;
	fmode_t f_mode;
	bool is_target = iguard_file_is_tracked_target(file);

	IGUARD_QC_INC(fd_receiver_install_attempt_total);
	IGUARD_QC_INC(fd_receiver_install_success_total);
	if (is_target) {
		IGUARD_QC_INC(frdac_target_fd_transfer_attempt_total);
		IGUARD_QC_INC(frdac_target_receiver_install_success_total);
	}

	if (!iguard_ctx_verbose_audit_enabled())
		return;

	iguard_file_identity(file, &ino, &s_dev, &i_mode, &f_flags, &f_mode);

	iguard_vinfo("CDAC_FILE_LINEAGE event=fd_install ts_ns=%llu audit_seq=%llu pid=%d tid=%d local_fd=%u file_cookie=%llu ino=%lu s_dev=%u:%u i_mode=0%o f_flags=0x%x f_mode=0x%x\n",
		(unsigned long long)ktime_get_ns(),
		(unsigned long long)iguard_audit_next_seq(),
		task_tgid_nr(current),
		task_pid_nr(current),
		fd,
		(unsigned long long)iguard_file_cookie(file),
		ino,
		MAJOR(s_dev), MINOR(s_dev),
		i_mode,
		f_flags,
		(unsigned int)f_mode);
}
EXPORT_SYMBOL_GPL(iguard_audit_fd_install);

void iguard_audit_receive_fd_result(unsigned int fd, struct file *file,
				    unsigned int o_flags, int result)
{
	unsigned long ino;
	dev_t s_dev;
	bool is_target = iguard_file_is_tracked_target(file);

	IGUARD_QC_INC(fd_receive_event_total);
	if (result == 0) {
		if (is_target)
			IGUARD_QC_INC(frdac_target_fd_transfer_attempt_total);
	} else {
		IGUARD_QC_INC(fd_receiver_install_failure_total);
		if (is_target)
			IGUARD_QC_INC(frdac_target_receiver_install_failure_total);
	}

	if (!iguard_ctx_verbose_audit_enabled())
		return;

	iguard_file_identity(file, &ino, &s_dev, NULL, NULL, NULL);
	pr_info("CDAC_RECEIVE_FD_TRANSFER event=receive_fd receiver_pid=%d receiver_tid=%d receiver_fd=%u file_cookie=%llu ino=%lu s_dev=%u:%u o_flags=0x%x transfer_result=%s result=%d\n",
		task_tgid_nr(current), task_pid_nr(current), fd,
		(unsigned long long)iguard_file_cookie(file), ino,
		MAJOR(s_dev), MINOR(s_dev), o_flags,
		result == 0 ? "installed" : "failed", result);
}
EXPORT_SYMBOL_GPL(iguard_audit_receive_fd_result);

void iguard_audit_binder_fd_send(pid_t sender_pid, pid_t sender_tid,
				 pid_t receiver_pid, u32 source_fd,
				 int binder_transaction_id,
				 struct file *file)
{
	unsigned long ino;
	dev_t s_dev;
	umode_t i_mode;
	int f_flags;
	fmode_t f_mode;

	if (!iguard_ctx_verbose_audit_enabled())
		return;

	iguard_file_identity(file, &ino, &s_dev, &i_mode, &f_flags, &f_mode);

	iguard_vinfo("CDAC_BINDER_FD_TRANSFER event=send binder_transaction_id=%d sender_pid=%d sender_tid=%d receiver_pid=%d source_fd=%u sender_file_cookie=%llu receiver_file_cookie=%llu ino=%lu s_dev=%u:%u i_mode=0%o f_flags=0x%x f_mode=0x%x transfer_result=queued\n",
		binder_transaction_id,
		sender_pid,
		sender_tid,
		receiver_pid,
		source_fd,
		(unsigned long long)iguard_file_cookie(file),
		(unsigned long long)iguard_file_cookie(file),
		ino,
		MAJOR(s_dev), MINOR(s_dev),
		i_mode,
		f_flags,
		(unsigned int)f_mode);
}
EXPORT_SYMBOL_GPL(iguard_audit_binder_fd_send);

void iguard_audit_binder_fd_recv(pid_t receiver_pid, pid_t receiver_tid,
				 unsigned int receiver_fd,
				 int binder_transaction_id,
				 struct file *file)
{
	unsigned long ino;
	dev_t s_dev;
	umode_t i_mode;
	int f_flags;
	fmode_t f_mode;

	if (!iguard_ctx_verbose_audit_enabled())
		return;

	iguard_file_identity(file, &ino, &s_dev, &i_mode, &f_flags, &f_mode);

	iguard_vinfo("CDAC_BINDER_FD_TRANSFER event=recv binder_transaction_id=%d receiver_pid=%d receiver_tid=%d receiver_fd=%u sender_file_cookie=%llu receiver_file_cookie=%llu ino=%lu s_dev=%u:%u i_mode=0%o f_flags=0x%x f_mode=0x%x transfer_result=installed\n",
		binder_transaction_id,
		receiver_pid,
		receiver_tid,
		receiver_fd,
		(unsigned long long)iguard_file_cookie(file),
		(unsigned long long)iguard_file_cookie(file),
		ino,
		MAJOR(s_dev), MINOR(s_dev),
		i_mode,
		f_flags,
		(unsigned int)f_mode);
}
EXPORT_SYMBOL_GPL(iguard_audit_binder_fd_recv);

void iguard_audit_rust_binder_fd_transfer(u32 stage,
					   pid_t sender_pid,
					   pid_t sender_tid,
					   u32 sender_fd,
					   pid_t receiver_pid,
					   pid_t receiver_tid,
					   u32 receiver_fd,
					   int binder_transaction_id,
					   struct file *file,
					   int result)
{
	unsigned long ino;
	dev_t s_dev;
	umode_t i_mode;
	int f_flags;
	fmode_t f_mode;
	const char *stage_str = stage == 0 ? "translate" : "install";
	const char *result_str = result == 0 ?
		(stage == 0 ? "reserved" : "installed") : "error";
	u64 cookie;

	if (!iguard_ctx_verbose_audit_enabled())
		return;

	iguard_file_identity(file, &ino, &s_dev, &i_mode, &f_flags, &f_mode);
	cookie = iguard_file_cookie(file);

	iguard_vinfo("CDAC_RUST_BINDER_FD_TRANSFER stage=%s ts_ns=%llu binder_transaction_id=%d sender_pid=%d sender_tid=%d sender_fd=%u sender_file_cookie=%llu sender_inode=%lu sender_s_dev=%u:%u receiver_pid=%d receiver_tid=%d receiver_fd=%u receiver_file_cookie=%llu i_mode=0%o f_flags=0x%x f_mode=0x%x result=%s\n",
		stage_str,
		(unsigned long long)ktime_get_ns(),
		binder_transaction_id,
		sender_pid,
		sender_tid,
		sender_fd,
		(unsigned long long)cookie,
		ino,
		MAJOR(s_dev), MINOR(s_dev),
		receiver_pid,
		receiver_tid,
		receiver_fd,
		(unsigned long long)cookie,
		i_mode,
		f_flags,
		(unsigned int)f_mode,
		result_str);
}
EXPORT_SYMBOL_GPL(iguard_audit_rust_binder_fd_transfer);

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

static struct iguard_ctx_entry *iguard_ctx_find_entry_locked(pid_t tid)
{
	struct iguard_ctx_entry *entry;

	hash_for_each_possible(iguard_ctx_table, entry, node, (u32)tid) {
		if (entry->reporter_tid == tid)
			return entry;
	}

	return NULL;
}

static struct iguard_ctx_entry *iguard_ctx_get_entry_locked(pid_t tid)
{
	struct iguard_ctx_entry *entry;

	entry = iguard_ctx_find_entry_locked(tid);
	if (entry)
		return entry;

	entry = kzalloc(sizeof(*entry), GFP_ATOMIC);
	if (!entry)
		return NULL;

	entry->reporter_tid = tid;
	hash_add(iguard_ctx_table, &entry->node, (u32)tid);
	return entry;
}

int iguard_ctx_push_from_current(const struct iguard_ctx_seed *seed)
{
	struct iguard_ctx_entry *entry;
	struct iguard_deleg_ctx snap;
	unsigned long flags;
	pid_t tid = task_pid_nr(current);
	pid_t tgid = task_tgid_nr(current);
	u64 seq;

	if (!seed)
		return -EINVAL;

	if (iguard_ablate_disable_ctx) {
		iguard_vinfo("CDAC_BINDER_ASYNC_ABSTAIN event=push_skipped reason=ablation current_tgid=%d current_tid=%d caller_uid=%u caller_pid=%u service_id=%u op_id=%u service=%s op=%s\n",
			tgid,
			tid,
			seed->caller_uid,
			seed->caller_pid,
			seed->service_id,
			seed->op_id,
			seed->service,
			seed->operation);
		return 0;
	}

	spin_lock_irqsave(&iguard_ctx_lock, flags);

	entry = iguard_ctx_get_entry_locked(tid);
	if (!entry) {
		spin_unlock_irqrestore(&iguard_ctx_lock, flags);
		pr_warn("CDAC_BINDER_STACK_MISMATCH event=push_failed reason=no_memory tid=%d tgid=%d\n",
			tid, tgid);
		IGUARD_QC_INC(context_push_fail);
		return -ENOMEM;
	}

	if (entry->poisoned || entry->depth >= IGUARD_CTX_MAX_DEPTH) {
		entry->depth = 0;
		entry->poisoned = true;
		spin_unlock_irqrestore(&iguard_ctx_lock, flags);
		pr_warn("CDAC_BINDER_STACK_MISMATCH event=push_failed reason=stack_overflow tid=%d tgid=%d requested_depth=%u max_depth=%u\n",
			tid, tgid, entry->depth + 1, IGUARD_CTX_MAX_DEPTH);
		IGUARD_QC_INC(context_push_fail);
		return -EOVERFLOW;
	}

	seq = seed->sequence_id ? seed->sequence_id :
		(u64)atomic64_inc_return(&iguard_ctx_seq);
	memset(&snap, 0, sizeof(snap));
	snap.reporter_tgid = tgid;
	snap.reporter_tid = tid;
	snap.caller_uid = seed->caller_uid;
	snap.caller_pid = seed->caller_pid;
	snap.service_id = seed->service_id;
	snap.op_id = seed->op_id;
	snap.transaction_code = seed->transaction_code;
	snap.transaction_flags = seed->transaction_flags;
	snap.nesting_depth = entry->depth + 1;
	snap.endpoint_id = seed->endpoint_id;
	snap.interface_hash = seed->interface_hash;
	iguard_copy_fixed_field(snap.service, sizeof(snap.service),
				seed->service, sizeof(seed->service));
	iguard_copy_fixed_field(snap.operation, sizeof(snap.operation),
				seed->operation, sizeof(seed->operation));

	snap.seqno = seq;
	snap.ts_ns = ktime_get_mono_fast_ns();
	snap.active = true;

	entry->stack[entry->depth++] = snap;

	spin_unlock_irqrestore(&iguard_ctx_lock, flags);

	iguard_vinfo("CDAC_BINDER_PUSH source=UNIFIED_BINDER_HOOK seq=%llu reporter_tgid=%d reporter_tid=%d caller_uid=%u caller_pid=%u endpoint_id=%llu service_id=%u op_id=%u transaction_code=%u transaction_flags=0x%x nesting_depth=%u service=%s op=%s ts_ns=%llu stack_result=ok\n",
		(unsigned long long)snap.seqno,
		snap.reporter_tgid,
		snap.reporter_tid,
		snap.caller_uid,
		snap.caller_pid,
		(unsigned long long)snap.endpoint_id,
		snap.service_id,
		snap.op_id,
		snap.transaction_code,
		snap.transaction_flags,
		snap.nesting_depth,
		snap.service,
		snap.operation,
		(unsigned long long)snap.ts_ns);

	IGUARD_QC_INC(context_push_ok);
	return 0;
}
EXPORT_SYMBOL_GPL(iguard_ctx_push_from_current);

int iguard_ctx_publish_from_current(const struct iguard_ctx_seed *seed)
{
	return iguard_ctx_push_from_current(seed);
}
EXPORT_SYMBOL_GPL(iguard_ctx_publish_from_current);

int iguard_ctx_pop_current(u64 sequence_id, u32 nesting_depth)
{
	struct iguard_ctx_entry *entry;
	struct iguard_deleg_ctx snap;
	unsigned long flags;
	pid_t tid = task_pid_nr(current);
	pid_t tgid = task_tgid_nr(current);
	bool ok = false;
	const char *reason = "ok";

	memset(&snap, 0, sizeof(snap));

	spin_lock_irqsave(&iguard_ctx_lock, flags);
	entry = iguard_ctx_find_entry_locked(tid);
	if (!entry || entry->depth == 0) {
		reason = "stack_underflow";
	} else {
		snap = entry->stack[entry->depth - 1];
		if (snap.seqno != sequence_id) {
			reason = "sequence_mismatch";
			entry->depth = 0;
			entry->poisoned = true;
		} else if (nesting_depth != 0 && snap.nesting_depth != nesting_depth) {
			reason = "depth_mismatch";
			entry->depth = 0;
			entry->poisoned = true;
		} else {
			entry->depth--;
			entry->poisoned = false;
			ok = true;
		}
	}
	spin_unlock_irqrestore(&iguard_ctx_lock, flags);

	if (ok) {
		iguard_vinfo("CDAC_BINDER_POP source=UNIFIED_BINDER_HOOK seq=%llu reporter_tgid=%d reporter_tid=%d endpoint_id=%llu service_id=%u op_id=%u transaction_code=%u transaction_flags=0x%x nesting_depth=%u remaining_depth=%u stack_result=ok\n",
			(unsigned long long)snap.seqno,
			snap.reporter_tgid,
			snap.reporter_tid,
			(unsigned long long)snap.endpoint_id,
			snap.service_id,
			snap.op_id,
			snap.transaction_code,
			snap.transaction_flags,
			snap.nesting_depth,
			entry ? entry->depth : 0);
		IGUARD_QC_INC(context_pop_ok);
		return 0;
	}

	pr_warn("CDAC_BINDER_STACK_MISMATCH source=UNIFIED_BINDER_HOOK event=pop_failed reason=%s current_tgid=%d current_tid=%d sequence_id=%llu nesting_depth=%u top_seq=%llu top_depth=%u\n",
		reason, tgid, tid, (unsigned long long)sequence_id, nesting_depth,
		(unsigned long long)snap.seqno, snap.nesting_depth);
	IGUARD_QC_INC(context_pop_fail);
	return -EINVAL;
}
EXPORT_SYMBOL_GPL(iguard_ctx_pop_current);

bool iguard_ctx_lookup_current(struct iguard_deleg_ctx *out)
{
	struct iguard_ctx_entry *entry;
	unsigned long flags;
	pid_t tid = task_pid_nr(current);

	if (!out)
		return false;

	spin_lock_irqsave(&iguard_ctx_lock, flags);

	entry = iguard_ctx_find_entry_locked(tid);
	if (entry && !entry->poisoned && entry->depth > 0) {
		*out = entry->stack[entry->depth - 1];
		spin_unlock_irqrestore(&iguard_ctx_lock, flags);
		return true;
	}

	spin_unlock_irqrestore(&iguard_ctx_lock, flags);
	return false;
}
EXPORT_SYMBOL_GPL(iguard_ctx_lookup_current);

void iguard_ctx_invalidate_current(void)
{
	struct iguard_ctx_entry *entry;
	unsigned long flags;
	pid_t tid = task_pid_nr(current);

	spin_lock_irqsave(&iguard_ctx_lock, flags);

	entry = iguard_ctx_find_entry_locked(tid);
	if (entry)
		entry->depth = 0;

	spin_unlock_irqrestore(&iguard_ctx_lock, flags);
}
EXPORT_SYMBOL_GPL(iguard_ctx_invalidate_current);

/* I-GUARD decision / apply / enforcement helper begin */

enum iguard_decision_kind {
	IGUARD_DECISION_AUDIT = 1,
	IGUARD_DECISION_WOULD_DENY = 2,
};

enum iguard_apply_result {
	IGUARD_APPLY_ALLOW = 0,
	IGUARD_APPLY_WOULD_DENY = 1,
};

enum iguard_enforce_mode {
	IGUARD_ENFORCE_REPORT_ONLY = 0,
	IGUARD_ENFORCE_PREVIEW_ENFORCE = 1,
};

static enum iguard_enforce_mode iguard_file_open_default_enforce_mode =
	IGUARD_ENFORCE_REPORT_ONLY;

static bool iguard_real_enforce_enabled = true;

struct iguard_file_open_decision {
	enum iguard_decision_kind kind;
	u8 matched;
	const char *reason;
	const char *rule_src;
	int specificity;
};

struct iguard_file_open_enforce_plan {
	bool would_block;
	int future_errno;
	const char *verdict;
};

struct iguard_object_key {
	const char *path_tail;
	unsigned long ino;
	dev_t s_dev;
	umode_t i_mode;
	int f_flags;
	fmode_t f_mode;
};

/*
 * Internal policy rule shape used only inside iguard_ctx.c.
 *
 * Matching conventions:
 *   - service_id == 0 / op_id == 0 / caller_uid == 0 => wildcard
 *   - service == NULL / operation == NULL / path_tail == NULL => wildcard
 *   - ino == 0 / s_dev == 0 / i_mode == 0 => wildcard
 *   - f_flags_mask == 0 / f_mode_mask == 0 => wildcard
 */
struct iguard_policy_rule {
	u32 service_id;
	u32 op_id;
	u32 caller_uid;
	const char *service;
	const char *operation;

	const char *path_tail;
	unsigned long ino;
	dev_t s_dev;
	umode_t i_mode;

	int f_flags_mask;
	int f_flags_value;

	fmode_t f_mode_mask;
	fmode_t f_mode_value;

	u32 required_relation_type;
	u32 required_relation_stage;

	enum iguard_decision_kind decision_kind;
	const char *reason;
};

#define IGUARD_RUNTIME_POLICY_MAX 8192
#define IGUARD_RUNTIME_STR_MAX    96
#define IGUARD_POLICY_CTL_MAX     512

struct iguard_runtime_policy_rule {
	bool used;
	struct iguard_policy_rule rule;

	char service_buf[IGUARD_RUNTIME_STR_MAX];
	char operation_buf[IGUARD_RUNTIME_STR_MAX];
	char path_tail_buf[IGUARD_RUNTIME_STR_MAX];
	char reason_buf[IGUARD_RUNTIME_STR_MAX];
};

static DEFINE_MUTEX(iguard_runtime_policy_lock);
static struct iguard_runtime_policy_rule
	iguard_runtime_policy_table[IGUARD_RUNTIME_POLICY_MAX];
static size_t iguard_runtime_policy_count;

static void iguard_fd_target_cache_rebuild_locked(void)
{
	u32 count = 0;
	size_t i;

	write_seqlock(&iguard_fd_target_lock);
	memset(iguard_fd_target_objects, 0, sizeof(iguard_fd_target_objects));
	memset(iguard_fd_target_proxies, 0, sizeof(iguard_fd_target_proxies));
	WRITE_ONCE(iguard_fd_target_proxy_count, 0);

	for (i = 0; i < IGUARD_RUNTIME_POLICY_MAX &&
		    count < IGUARD_FD_TARGET_OBJECT_MAX; i++) {
		const struct iguard_policy_rule *rule;

		if (!iguard_runtime_policy_table[i].used)
			continue;

		rule = &iguard_runtime_policy_table[i].rule;
		if (!rule->ino || !rule->s_dev)
			continue;

		iguard_fd_target_objects[count].ino = rule->ino;
		iguard_fd_target_objects[count].s_dev = rule->s_dev;
		count++;
	}

	WRITE_ONCE(iguard_fd_target_object_count, count);
	write_sequnlock(&iguard_fd_target_lock);
}

static struct dentry *iguard_debugfs_dir;

static int iguard_policy_rule_specificity_score(
		const struct iguard_policy_rule *rule);

/*
 * Keep current static baseline:
 *   - broad public.txt any-access audit rule
 *   - readSecret write-only deny
 *   - readPublic read-only audit
 *   - writePublic write-only deny
 *
 * Matching semantics:
 *   - runtime overlay rules are checked first
 *   - static rules are fallback baseline
 *   - within each source, more-specific wins
 */
static const struct iguard_policy_rule iguard_policy_table[] = {
	{
		.service_id = 1,
		.op_id = 0,
		.service = "iguard_demo",
		.operation = NULL,

		.path_tail = "public.txt",
		.ino = 0,
		.s_dev = 0,
		.i_mode = 0,

		.f_flags_mask = 0,
		.f_flags_value = 0,

		.f_mode_mask = 0,
		.f_mode_value = 0,

		.decision_kind = IGUARD_DECISION_AUDIT,
		.reason = "demo_public_txt_any_access_audit",
	},
	{
		.service_id = 1,
		.op_id = 1,
		.service = "iguard_demo",
		.operation = "readSecret",

		.path_tail = "secret.txt",
		.ino = 0,
		.s_dev = 0,
		.i_mode = 0,

		.f_flags_mask = O_ACCMODE,
		.f_flags_value = O_WRONLY,

		.f_mode_mask = 0,
		.f_mode_value = 0,

		.decision_kind = IGUARD_DECISION_WOULD_DENY,
		.reason = "demo_read_secret_secret_txt_write_only",
	},
	{
		.service_id = 1,
		.op_id = 3,
		.service = "iguard_demo",
		.operation = "readPublic",

		.path_tail = "public.txt",
		.ino = 0,
		.s_dev = 0,
		.i_mode = 0,

		.f_flags_mask = O_ACCMODE,
		.f_flags_value = O_RDONLY,

		.f_mode_mask = 0,
		.f_mode_value = 0,

		.decision_kind = IGUARD_DECISION_AUDIT,
		.reason = "demo_read_public_public_txt_read_only",
	},
	{
		.service_id = 1,
		.op_id = 4,
		.service = "iguard_demo",
		.operation = "writePublic",

		.path_tail = "public.txt",
		.ino = 0,
		.s_dev = 0,
		.i_mode = 0,

		.f_flags_mask = O_ACCMODE,
		.f_flags_value = O_WRONLY,

		.f_mode_mask = 0,
		.f_mode_value = 0,

		.decision_kind = IGUARD_DECISION_WOULD_DENY,
		.reason = "demo_write_public_public_txt_write_only_deny",
	},
};

static const char *iguard_decision_kind_str(enum iguard_decision_kind kind)
{
	switch (kind) {
	case IGUARD_DECISION_WOULD_DENY:
		return "would-deny";
	case IGUARD_DECISION_AUDIT:
	default:
		return "audit";
	}
}

static const char *iguard_apply_result_str(enum iguard_apply_result result)
{
	switch (result) {
	case IGUARD_APPLY_WOULD_DENY:
		return "would-deny";
	case IGUARD_APPLY_ALLOW:
	default:
		return "allow";
	}
}

static const char *iguard_enforce_mode_str(enum iguard_enforce_mode mode)
{
	switch (mode) {
	case IGUARD_ENFORCE_PREVIEW_ENFORCE:
		return "preview-enforce";
	case IGUARD_ENFORCE_REPORT_ONLY:
	default:
		return "report-only";
	}
}

static bool iguard_direct_file_open_enforce_supported(u32 service_id, u32 op_id)
{
	/*
	 * S10 SettingsProvider.openFile() has same-thread caller provenance,
	 * VFS-resolved object identity, operation evidence, and a pre-exposure
	 * error-return point in do_dentry_open(). Keep unrelated direct routes
	 * in report-only mode until they receive the same validation.
	 */
	return (service_id == 8 && op_id == 701) ||
	       (service_id == 7 && op_id == 601) ||
	       (service_id == 9 && op_id == 801) ||
	       (service_id == 10 && op_id == 901) ||
	       (service_id == 11 && op_id == 1001) ||
	       (service_id == 12 && op_id == 1101);
}

static enum iguard_enforce_mode iguard_select_file_open_enforce_mode(u32 service_id,
								     u32 op_id)
{
	if (iguard_direct_file_open_enforce_supported(service_id, op_id))
		return IGUARD_ENFORCE_PREVIEW_ENFORCE;

	return iguard_file_open_default_enforce_mode;
}

static void iguard_emit_runtime_policy_perf(const char *policy_op,
					    u64 cost_ns,
					    size_t idx,
					    size_t runtime_count,
					    const struct iguard_policy_rule *rule)
{
	if (!policy_op)
		policy_op = "-";

	if (!rule) {
		pr_info("iguard_ctx: perf policy_op=%s cost_ns=%llu runtime_policy_count=%zu\n",
			policy_op,
			(unsigned long long)cost_ns,
			runtime_count);
		return;
	}

	pr_info("iguard_ctx: perf policy_op=%s cost_ns=%llu idx=%zu runtime_policy_count=%zu service_id=%u op_id=%u caller_uid=%u service=%s operation=%s path_tail=%s ino=%lu s_dev=%u:%u i_mode=0%o f_flags_mask=0x%x f_flags_value=0x%x f_mode_mask=0x%x f_mode_value=0x%x required_relation_type=%u required_relation_stage=%u decision=%s reason=%s specificity=%d\n",
		policy_op,
		(unsigned long long)cost_ns,
		idx,
		runtime_count,
		rule->service_id,
		rule->op_id,
		rule->caller_uid,
		rule->service ? rule->service : "-",
		rule->operation ? rule->operation : "-",
		rule->path_tail ? rule->path_tail : "-",
		rule->ino,
		MAJOR(rule->s_dev), MINOR(rule->s_dev),
		rule->i_mode,
		rule->f_flags_mask,
		rule->f_flags_value,
		(unsigned int)rule->f_mode_mask,
		(unsigned int)rule->f_mode_value,
		rule->required_relation_type,
		rule->required_relation_stage,
		iguard_decision_kind_str(rule->decision_kind),
		rule->reason ? rule->reason : "-",
		iguard_policy_rule_specificity_score(rule));
}

static void iguard_build_object_key(struct file *file,
				    struct inode *inode,
				    struct iguard_object_key *out)
{
	const struct dentry *dentry = NULL;

	if (!out)
		return;

	memset(out, 0, sizeof(*out));
	out->path_tail = "?";

	if (!file || !inode)
		return;

	dentry = file->f_path.dentry;

	if (dentry && dentry->d_name.name && dentry->d_name.len)
		out->path_tail = dentry->d_name.name;

	out->ino = (unsigned long)inode->i_ino;
	out->i_mode = inode->i_mode;
	out->f_flags = file->f_flags;
	out->f_mode = file->f_mode;

	if (inode->i_sb)
		out->s_dev = inode->i_sb->s_dev;
}

static void iguard_ablate_object_key_if_needed(struct iguard_object_key *obj)
{
	if (!obj)
		return;

	if (!iguard_ablate_path_tail_only)
		return;

	iguard_vinfo("iguard_ctx: ablation path-tail-only active path_tail=%s orig_ino=%lu orig_s_dev=%u:%u orig_i_mode=0%o orig_f_flags=0x%x orig_f_mode=0x%x\n",
		obj->path_tail ? obj->path_tail : "(null)",
		obj->ino,
		MAJOR(obj->s_dev),
		MINOR(obj->s_dev),
		obj->i_mode,
		obj->f_flags,
		(unsigned int)obj->f_mode);

	/*
	 * Keep only path_tail.
	 * This preserves path-level matching but removes rich object-side
	 * discrimination features.
	 */
	obj->ino = 0;
	obj->s_dev = 0;
	obj->i_mode = 0;
	obj->f_flags = 0;
	obj->f_mode = 0;
}

static bool iguard_match_u32(u32 want, u32 got)
{
	return want == 0 || want == got;
}

static bool iguard_match_ulong(unsigned long want, unsigned long got)
{
	return want == 0 || want == got;
}

static bool iguard_match_dev(dev_t want, dev_t got)
{
	return want == 0 || want == got;
}

static bool iguard_match_umode(umode_t want, umode_t got)
{
	return want == 0 || want == got;
}

static bool iguard_match_str(const char *want, const char *got)
{
	if (!want)
		return true;

	if (!got)
		return false;

	return strcmp(want, got) == 0;
}

static bool iguard_match_masked_int(int mask, int want_value, int got_value)
{
	if (mask == 0)
		return true;

	return (got_value & mask) == want_value;
}

static bool iguard_match_masked_fmode(fmode_t mask,
				      fmode_t want_value,
				      fmode_t got_value)
{
	if (mask == 0)
		return true;

	return (got_value & mask) == want_value;
}

static int iguard_policy_rule_specificity_score(
		const struct iguard_policy_rule *rule)
{
	int score = 0;

	if (!rule)
		return -1;

	if (rule->service_id != 0)
		score++;
	if (rule->op_id != 0)
		score++;
	if (rule->caller_uid != 0)
		score++;

	if (rule->operation != NULL)
		score++;

	if (rule->path_tail != NULL)
		score++;
	if (rule->ino != 0)
		score++;
	if (rule->s_dev != 0)
		score++;
	if (rule->i_mode != 0)
		score++;

	if (rule->f_flags_mask != 0)
		score++;
	if (rule->f_mode_mask != 0)
		score++;
	if (rule->required_relation_type != 0)
		score++;
	if (rule->required_relation_stage != 0)
		score++;

	return score;
}

static bool iguard_policy_rule_matches(const struct iguard_policy_rule *rule,
				       u32 service_id,
				       u32 op_id,
				       u32 caller_uid,
				       const char *service,
				       const char *operation,
				       const struct iguard_object_key *obj)
{
	const char *path_tail;
	unsigned long ino;
	dev_t s_dev;
	umode_t i_mode;
	int f_flags;
	fmode_t f_mode;

	if (!rule)
		return false;

	if (rule->required_relation_type != 0 ||
	    rule->required_relation_stage != 0)
		return false;

	path_tail = obj ? obj->path_tail : NULL;
	ino = obj ? obj->ino : 0;
	s_dev = obj ? obj->s_dev : 0;
	i_mode = obj ? obj->i_mode : 0;
	f_flags = obj ? obj->f_flags : 0;
	f_mode = obj ? obj->f_mode : 0;

	if (!iguard_match_u32(rule->service_id, service_id))
		return false;
	if (!iguard_match_u32(rule->op_id, op_id))
		return false;
	if (!iguard_match_u32(rule->caller_uid, caller_uid))
		return false;
	/*
	 * `service` is a diagnostic namespace label. Authoritative service
	 * identity is carried by service_id/op_id plus operation metadata, so
	 * free-text service labels must not participate in safety matching.
	 */
	if (!iguard_match_str(rule->operation, operation))
		return false;
	if (!iguard_match_str(rule->path_tail, path_tail))
		return false;
	if (!iguard_match_ulong(rule->ino, ino))
		return false;
	if (!iguard_match_dev(rule->s_dev, s_dev))
		return false;
	if (!iguard_match_umode(rule->i_mode, i_mode))
		return false;
	if (!iguard_match_masked_int(rule->f_flags_mask,
				     rule->f_flags_value,
				     f_flags))
		return false;
	if (!iguard_match_masked_fmode(rule->f_mode_mask,
				       rule->f_mode_value,
				       f_mode))
		return false;

	return true;
}

static bool iguard_relation_policy_rule_matches(
		const struct iguard_policy_rule *rule,
		u32 service_id,
		u32 op_id,
		u32 caller_uid,
		const char *service,
		const char *operation,
		const struct iguard_relation_decision_input *input)
{
	if (!rule || !input)
		return false;

	if (rule->required_relation_type == 0 ||
	    rule->required_relation_stage == 0)
		return false;
	if (!iguard_match_u32(rule->service_id, service_id))
		return false;
	if (!iguard_match_u32(rule->op_id, op_id))
		return false;
	if (!iguard_match_u32(rule->caller_uid, caller_uid))
		return false;
	/*
	 * `service` is intentionally not a relation-policy predicate. The
	 * lifecycle endpoint/operation contract is service_id + op_id +
	 * operation, while this string is rendered for diagnostics.
	 */
	if (!iguard_match_str(rule->operation, operation))
		return false;
	if (!iguard_match_ulong(rule->ino, (unsigned long)input->lower_inode))
		return false;
	if (!iguard_match_dev(rule->s_dev, (dev_t)input->lower_s_dev))
		return false;
	if (rule->required_relation_type != input->relation_type)
		return false;
	if (rule->required_relation_stage != input->relation_stage)
		return false;

	return true;
}

static void iguard_runtime_rule_reset(struct iguard_runtime_policy_rule *rr)
{
	if (!rr)
		return;

	memset(rr, 0, sizeof(*rr));
	rr->rule.service = NULL;
	rr->rule.operation = NULL;
	rr->rule.path_tail = NULL;
	rr->rule.reason = NULL;
}

static void iguard_runtime_rule_fixup_ptrs(struct iguard_runtime_policy_rule *rr)
{
	if (!rr)
		return;

	rr->rule.service = rr->service_buf[0] ? rr->service_buf : NULL;
	rr->rule.operation = rr->operation_buf[0] ? rr->operation_buf : NULL;
	rr->rule.path_tail = rr->path_tail_buf[0] ? rr->path_tail_buf : NULL;
	rr->rule.reason = rr->reason_buf[0] ? rr->reason_buf : NULL;
}

static int iguard_parse_decision_kind(const char *s,
				      enum iguard_decision_kind *out)
{
	if (!s || !out)
		return -EINVAL;

	if (strcmp(s, "audit") == 0) {
		*out = IGUARD_DECISION_AUDIT;
		return 0;
	}
	if (strcmp(s, "deny") == 0) {
		*out = IGUARD_DECISION_WOULD_DENY;
		return 0;
	}

	return -EINVAL;
}

static const struct iguard_policy_rule *
iguard_find_best_matching_static_rule(u32 service_id, u32 op_id,
				      u32 caller_uid,
				      const char *service,
				      const char *operation,
				      const struct iguard_object_key *obj)
{
	const struct iguard_policy_rule *best_rule = NULL;
	int best_score = -1;
	size_t i;

	for (i = 0; i < ARRAY_SIZE(iguard_policy_table); i++) {
		const struct iguard_policy_rule *rule = &iguard_policy_table[i];
		int score;

		if (!iguard_policy_rule_matches(rule, service_id, op_id,
						caller_uid, service, operation, obj))
			continue;

		score = iguard_policy_rule_specificity_score(rule);

		if (!best_rule || score > best_score) {
			best_rule = rule;
			best_score = score;
		}
	}

	return best_rule;
}

static const struct iguard_policy_rule *
iguard_find_best_matching_runtime_rule(u32 service_id, u32 op_id,
				       u32 caller_uid,
				       const char *service,
				       const char *operation,
				       const struct iguard_object_key *obj)
{
	const struct iguard_policy_rule *best_rule = NULL;
	int best_score = -1;
	size_t i;

	for (i = 0; i < IGUARD_RUNTIME_POLICY_MAX; i++) {
		const struct iguard_policy_rule *rule;
		int score;

		if (!iguard_runtime_policy_table[i].used)
			continue;

		rule = &iguard_runtime_policy_table[i].rule;

		if (!iguard_policy_rule_matches(rule, service_id, op_id,
						caller_uid, service, operation, obj))
			continue;

		score = iguard_policy_rule_specificity_score(rule);

		if (!best_rule || score > best_score) {
			best_rule = rule;
			best_score = score;
		}
	}

	return best_rule;
}

static const struct iguard_policy_rule *
iguard_find_best_matching_relation_runtime_rule(
		u32 service_id, u32 op_id, u32 caller_uid,
		const char *service, const char *operation,
		const struct iguard_relation_decision_input *input,
		size_t *idx_out)
{
	const struct iguard_policy_rule *best_rule = NULL;
	int best_score = -1;
	size_t best_idx = 0;
	size_t i;

	for (i = 0; i < IGUARD_RUNTIME_POLICY_MAX; i++) {
		const struct iguard_policy_rule *rule;
		int score;

		if (!iguard_runtime_policy_table[i].used)
			continue;

		rule = &iguard_runtime_policy_table[i].rule;
		if (!iguard_relation_policy_rule_matches(rule, service_id, op_id,
							 caller_uid, service,
							 operation, input))
			continue;

		score = iguard_policy_rule_specificity_score(rule);
		if (!best_rule || score > best_score) {
			best_rule = rule;
			best_score = score;
			best_idx = i;
		}
	}

	if (idx_out)
		*idx_out = best_idx;

	return best_rule;
}

int iguard_ctx_runtime_policy_clear_all(void)
{
	size_t i;
	u64 t0_ns, t1_ns, cost_ns;
	size_t count_after;

	t0_ns = ktime_get_mono_fast_ns();

	mutex_lock(&iguard_runtime_policy_lock);
	for (i = 0; i < IGUARD_RUNTIME_POLICY_MAX; i++)
		iguard_runtime_rule_reset(&iguard_runtime_policy_table[i]);
	iguard_runtime_policy_count = 0;
	iguard_fd_target_cache_rebuild_locked();
	count_after = iguard_runtime_policy_count;
	mutex_unlock(&iguard_runtime_policy_lock);

	t1_ns = ktime_get_mono_fast_ns();
	cost_ns = t1_ns - t0_ns;

	pr_info("iguard_ctx: runtime-policy clear\n");
	iguard_emit_runtime_policy_perf("clear", cost_ns, 0, count_after, NULL);
	return 0;
}
EXPORT_SYMBOL_GPL(iguard_ctx_runtime_policy_clear_all);

static int iguard_ctx_runtime_policy_add_rule_internal(
		const struct iguard_policy_rule *src,
		const char *service,
		const char *operation,
		const char *path_tail,
		const char *reason)
{
	struct iguard_runtime_policy_rule tmp;
	struct iguard_policy_rule added_rule = {};
	size_t i;
	size_t added_idx = 0;
	size_t count_after = 0;
	u64 t0_ns, t1_ns, cost_ns;

	if (!src)
		return -EINVAL;

	iguard_runtime_rule_reset(&tmp);
	tmp.used = true;
	tmp.rule = *src;

	if (service)
		strscpy(tmp.service_buf, service, sizeof(tmp.service_buf));
	if (operation)
		strscpy(tmp.operation_buf, operation, sizeof(tmp.operation_buf));
	if (path_tail)
		strscpy(tmp.path_tail_buf, path_tail, sizeof(tmp.path_tail_buf));
	if (reason)
		strscpy(tmp.reason_buf, reason, sizeof(tmp.reason_buf));

	iguard_runtime_rule_fixup_ptrs(&tmp);

	t0_ns = ktime_get_mono_fast_ns();

	mutex_lock(&iguard_runtime_policy_lock);
	for (i = 0; i < IGUARD_RUNTIME_POLICY_MAX; i++) {
		if (iguard_runtime_policy_table[i].used)
			continue;

		iguard_runtime_policy_table[i] = tmp;
		iguard_runtime_rule_fixup_ptrs(&iguard_runtime_policy_table[i]);
		iguard_runtime_policy_count++;
		iguard_fd_target_cache_rebuild_locked();

		added_idx = i;
		added_rule = iguard_runtime_policy_table[i].rule;
		count_after = iguard_runtime_policy_count;

		mutex_unlock(&iguard_runtime_policy_lock);

		t1_ns = ktime_get_mono_fast_ns();
		cost_ns = t1_ns - t0_ns;

			pr_info("iguard_ctx: runtime-policy add idx=%zu service_id=%u op_id=%u caller_uid=%u service=%s operation=%s path_tail=%s ino=%lu s_dev=%u:%u i_mode=0%o f_flags_mask=0x%x f_flags_value=0x%x f_mode_mask=0x%x f_mode_value=0x%x required_relation_type=%u required_relation_stage=%u decision=%s reason=%s specificity=%d\n",
				added_idx,
			added_rule.service_id,
			added_rule.op_id,
			added_rule.caller_uid,
			added_rule.service ? added_rule.service : "-",
			added_rule.operation ? added_rule.operation : "-",
			added_rule.path_tail ? added_rule.path_tail : "-",
			added_rule.ino,
			MAJOR(added_rule.s_dev),
			MINOR(added_rule.s_dev),
			added_rule.i_mode,
			added_rule.f_flags_mask,
				added_rule.f_flags_value,
				(unsigned int)added_rule.f_mode_mask,
				(unsigned int)added_rule.f_mode_value,
				added_rule.required_relation_type,
				added_rule.required_relation_stage,
				iguard_decision_kind_str(added_rule.decision_kind),
			added_rule.reason ? added_rule.reason : "-",
			iguard_policy_rule_specificity_score(&added_rule));

		iguard_emit_runtime_policy_perf("add", cost_ns, added_idx,
						count_after, &added_rule);
		return 0;
	}
	count_after = iguard_runtime_policy_count;
	mutex_unlock(&iguard_runtime_policy_lock);

	t1_ns = ktime_get_mono_fast_ns();
	cost_ns = t1_ns - t0_ns;
	iguard_emit_runtime_policy_perf("add-nospace", cost_ns, 0, count_after,
					NULL);

	return -ENOSPC;
}

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
					      const char *reason)
{
	struct iguard_policy_rule rule = {};

	rule.service_id = service_id;
	rule.op_id = op_id;
	rule.caller_uid = caller_uid;
	rule.f_flags_mask = f_flags_mask;
	rule.f_flags_value = f_flags_value;
	rule.f_mode_mask = (fmode_t)f_mode_mask;
	rule.f_mode_value = (fmode_t)f_mode_value;
	rule.ino = (unsigned long)ino;
	rule.s_dev = (dev_t)s_dev;
	rule.i_mode = (umode_t)i_mode;

	switch (decision_kind) {
	case IGUARD_DECISION_AUDIT:
	case IGUARD_DECISION_WOULD_DENY:
		rule.decision_kind = decision_kind;
		break;
	default:
		return -EINVAL;
	}

	return iguard_ctx_runtime_policy_add_rule_internal(&rule,
							   service,
							   operation,
							   path_tail,
							   reason);
}
EXPORT_SYMBOL_GPL(iguard_ctx_runtime_policy_add_rule_fields);

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
						      const char *reason)
{
	struct iguard_policy_rule rule = {};

	if (required_relation_type == 0 || required_relation_stage == 0)
		return -EINVAL;

	rule.service_id = service_id;
	rule.op_id = op_id;
	rule.caller_uid = caller_uid;
	rule.ino = (unsigned long)ino;
	rule.s_dev = (dev_t)s_dev;
	rule.required_relation_type = required_relation_type;
	rule.required_relation_stage = required_relation_stage;

	switch (decision_kind) {
	case IGUARD_DECISION_AUDIT:
	case IGUARD_DECISION_WOULD_DENY:
		rule.decision_kind = decision_kind;
		break;
	default:
		return -EINVAL;
	}

	return iguard_ctx_runtime_policy_add_rule_internal(&rule,
							   service,
							   operation,
							   NULL,
							   reason);
}
EXPORT_SYMBOL_GPL(iguard_ctx_runtime_policy_add_relation_rule_fields);

static struct iguard_file_open_decision
iguard_build_file_open_decision(u32 service_id, u32 op_id,
				u32 caller_uid,
				const char *service,
				const char *operation,
				const struct iguard_object_key *obj)
{
	struct iguard_file_open_decision decision = {
		.kind = IGUARD_DECISION_AUDIT,
		.matched = 0,
		.reason = "default_audit",
		.rule_src = "default",
		.specificity = 0,
	};
	const struct iguard_policy_rule *rule;

	if (!iguard_ablate_disable_runtime) {
		mutex_lock(&iguard_runtime_policy_lock);
		rule = iguard_find_best_matching_runtime_rule(service_id, op_id,
							      caller_uid,
							      service, operation, obj);
		if (rule) {
			decision.kind = rule->decision_kind;
			decision.matched = 1;
			decision.reason = rule->reason ? rule->reason : "runtime_match";
			decision.rule_src = "runtime";
			decision.specificity =
				iguard_policy_rule_specificity_score(rule);
			mutex_unlock(&iguard_runtime_policy_lock);
			return decision;
		}
		mutex_unlock(&iguard_runtime_policy_lock);
	} else {
		iguard_vinfo("iguard_ctx: ablation disable-runtime active service_id=%u op_id=%u service=%s operation=%s path_tail=%s\n",
			service_id,
			op_id,
			service ? service : "-",
			operation ? operation : "-",
			(obj && obj->path_tail) ? obj->path_tail : "-");
	}

	rule = iguard_find_best_matching_static_rule(service_id, op_id,
						     caller_uid,
						     service, operation, obj);
	if (rule) {
		decision.kind = rule->decision_kind;
		decision.matched = 1;
		decision.reason = rule->reason ? rule->reason : "static_match";
		decision.rule_src = "static";
		decision.specificity =
			iguard_policy_rule_specificity_score(rule);
		return decision;
	}

	return decision;
}

static void iguard_emit_file_open_decision(u64 seqno,
					   int reporter_tgid,
					   int reporter_tid,
					   u32 caller_uid,
					   int caller_pid,
					   u32 service_id,
					   u32 op_id,
					   const char *service,
					   const char *operation,
					   const struct iguard_object_key *obj,
					   const struct iguard_file_open_decision *decision)
{
	const char *path_tail = obj ? obj->path_tail : "(null)";
	unsigned long ino = obj ? obj->ino : 0;
	dev_t s_dev = obj ? obj->s_dev : 0;
	umode_t i_mode = obj ? obj->i_mode : 0;
	int f_flags = obj ? obj->f_flags : 0;
	fmode_t f_mode = obj ? obj->f_mode : 0;

	if (!decision)
		return;

	iguard_vinfo("iguard_ctx: decision seq=%llu action=%s matched=%u reason=%s rule_src=%s specificity=%d reporter_tgid=%d reporter_tid=%d caller_uid=%u caller_pid=%d service_id=%u op_id=%u service=%s operation=%s path_tail=%s obj_ino=%lu obj_s_dev=%u:%u obj_i_mode=0%o obj_f_flags=0x%x obj_f_mode=0x%x\n",
		(unsigned long long)seqno,
		iguard_decision_kind_str(decision->kind),
		decision->matched ? 1 : 0,
		decision->reason ? decision->reason : "-",
		decision->rule_src ? decision->rule_src : "-",
		decision->specificity,
		reporter_tgid,
		reporter_tid,
		caller_uid,
		caller_pid,
		service_id,
		op_id,
		service ? service : "-",
		operation ? operation : "-",
		path_tail ? path_tail : "(null)",
		ino,
		MAJOR(s_dev), MINOR(s_dev),
		i_mode,
		f_flags,
		(unsigned int)f_mode);
}

static void iguard_emit_file_open_apply_result(u64 seqno,
					       int reporter_tgid,
					       int reporter_tid,
					       u32 caller_uid,
					       int caller_pid,
					       u32 service_id,
					       u32 op_id,
					       const char *service,
					       const char *operation,
					       const struct iguard_object_key *obj,
					       const struct iguard_file_open_decision *decision,
					       enum iguard_apply_result result)
{
	const char *path_tail = obj ? obj->path_tail : "(null)";

	iguard_vinfo("iguard_ctx: decision-apply seq=%llu result=%s action=%s matched=%u reason=%s rule_src=%s reporter_tgid=%d reporter_tid=%d caller_uid=%u caller_pid=%d service_id=%u op_id=%u service=%s operation=%s path_tail=%s\n",
		(unsigned long long)seqno,
		iguard_apply_result_str(result),
		decision ? iguard_decision_kind_str(decision->kind) : "-",
		decision && decision->matched ? 1 : 0,
		(decision && decision->reason) ? decision->reason : "-",
		(decision && decision->rule_src) ? decision->rule_src : "-",
		reporter_tgid,
		reporter_tid,
		caller_uid,
		caller_pid,
		service_id,
		op_id,
		service ? service : "-",
		operation ? operation : "-",
		path_tail ? path_tail : "(null)");
}

static struct iguard_file_open_enforce_plan
iguard_build_file_open_enforce_plan(const struct iguard_file_open_decision *decision,
				    enum iguard_apply_result result,
				    enum iguard_enforce_mode mode)
{
	struct iguard_file_open_enforce_plan plan = {
		.would_block = false,
		.future_errno = 0,
		.verdict = "allow",
	};

	if (!decision)
		return plan;

	if (result != IGUARD_APPLY_WOULD_DENY)
		return plan;

	switch (mode) {
	case IGUARD_ENFORCE_PREVIEW_ENFORCE:
		plan.would_block = true;
		plan.future_errno = -EACCES;
		plan.verdict = "would-deny-here";
		break;
	case IGUARD_ENFORCE_REPORT_ONLY:
	default:
		plan.would_block = false;
		plan.future_errno = 0;
		plan.verdict = "allow-for-now";
		break;
	}

	return plan;
}

static void iguard_emit_file_open_enforce_plan(u64 seqno,
					       int reporter_tgid,
					       int reporter_tid,
					       u32 caller_uid,
					       int caller_pid,
					       u32 service_id,
					       u32 op_id,
					       const char *service,
					       const char *operation,
					       const struct iguard_object_key *obj,
					       const struct iguard_file_open_decision *decision,
					       enum iguard_apply_result result,
					       enum iguard_enforce_mode mode,
					       const struct iguard_file_open_enforce_plan *plan)
{
	const char *path_tail = obj ? obj->path_tail : "(null)";

	if (!decision || !plan)
		return;

	if (result != IGUARD_APPLY_WOULD_DENY)
		return;

	iguard_vinfo("iguard_ctx: enforce-plan seq=%llu mode=%s result=%s action=%s matched=%u reason=%s rule_src=%s reporter_tgid=%d reporter_tid=%d caller_uid=%u caller_pid=%d service_id=%u op_id=%u service=%s operation=%s path_tail=%s would_block=%u future_errno=%d verdict=%s\n",
		(unsigned long long)seqno,
		iguard_enforce_mode_str(mode),
		iguard_apply_result_str(result),
		iguard_decision_kind_str(decision->kind),
		decision->matched ? 1 : 0,
		decision->reason ? decision->reason : "-",
		decision->rule_src ? decision->rule_src : "-",
		reporter_tgid,
		reporter_tid,
		caller_uid,
		caller_pid,
		service_id,
		op_id,
		service ? service : "-",
		operation ? operation : "-",
		path_tail ? path_tail : "(null)",
		plan->would_block ? 1 : 0,
		plan->future_errno,
		plan->verdict ? plan->verdict : "-");
}

static bool iguard_should_really_enforce(
		const struct iguard_file_open_enforce_plan *plan,
		enum iguard_enforce_mode mode)
{
	if (!plan)
		return false;

	if (!iguard_real_enforce_enabled)
		return false;

	if (mode != IGUARD_ENFORCE_PREVIEW_ENFORCE)
		return false;

	if (!plan->would_block)
		return false;

	if (plan->future_errno >= 0)
		return false;

	return true;
}

static void iguard_emit_file_open_perf(u64 seqno,
				       int reporter_tgid,
				       int reporter_tid,
				       u32 caller_uid,
				       int caller_pid,
				       u32 service_id,
				       u32 op_id,
				       const char *service,
				       const char *operation,
				       const struct iguard_object_key *obj,
				       const struct iguard_file_open_decision *decision,
				       enum iguard_apply_result result,
				       int future_errno,
				       u64 decision_ns)
{
	const char *path_tail = obj ? obj->path_tail : "(null)";
	unsigned long ino = obj ? obj->ino : 0;
	dev_t s_dev = obj ? obj->s_dev : 0;
	umode_t i_mode = obj ? obj->i_mode : 0;
	int f_flags = obj ? obj->f_flags : 0;
	fmode_t f_mode = obj ? obj->f_mode : 0;

	iguard_vinfo("iguard_ctx: perf seq=%llu decision_ns=%llu result=%s action=%s matched=%u reason=%s rule_src=%s specificity=%d future_errno=%d reporter_tgid=%d reporter_tid=%d caller_uid=%u caller_pid=%d service_id=%u op_id=%u service=%s operation=%s path_tail=%s obj_ino=%lu obj_s_dev=%u:%u obj_i_mode=0%o obj_f_flags=0x%x obj_f_mode=0x%x\n",
		(unsigned long long)seqno,
		(unsigned long long)decision_ns,
		iguard_apply_result_str(result),
		decision ? iguard_decision_kind_str(decision->kind) : "-",
		decision && decision->matched ? 1 : 0,
		(decision && decision->reason) ? decision->reason : "-",
		(decision && decision->rule_src) ? decision->rule_src : "-",
		decision ? decision->specificity : 0,
		future_errno,
		reporter_tgid,
		reporter_tid,
		caller_uid,
		caller_pid,
		service_id,
		op_id,
		service ? service : "-",
		operation ? operation : "-",
		path_tail ? path_tail : "(null)",
		ino,
		MAJOR(s_dev), MINOR(s_dev),
		i_mode,
		f_flags,
		(unsigned int)f_mode);
}

static enum iguard_apply_result
iguard_apply_file_open_decision(u64 seqno,
				int reporter_tgid,
				int reporter_tid,
				u32 caller_uid,
				int caller_pid,
				u32 service_id,
				u32 op_id,
				const char *service,
				const char *operation,
				const struct iguard_object_key *obj,
				struct iguard_file_open_decision *decision_out,
				int *future_errno_out)
{
	struct iguard_file_open_decision decision;
	struct iguard_file_open_enforce_plan plan;
	enum iguard_apply_result result;
	enum iguard_enforce_mode mode =
		iguard_select_file_open_enforce_mode(service_id, op_id);
	int future_errno = 0;
	u64 t0_ns, t1_ns, decision_ns;

	t0_ns = ktime_get_mono_fast_ns();

	decision = iguard_build_file_open_decision(service_id, op_id,
						   caller_uid,
						   service, operation, obj);

	iguard_emit_file_open_decision(seqno,
				       reporter_tgid,
				       reporter_tid,
				       caller_uid,
				       caller_pid,
				       service_id,
				       op_id,
				       service,
				       operation,
				       obj,
				       &decision);

	result = (decision.kind == IGUARD_DECISION_WOULD_DENY) ?
		 IGUARD_APPLY_WOULD_DENY :
		 IGUARD_APPLY_ALLOW;

	iguard_emit_file_open_apply_result(seqno,
					   reporter_tgid,
					   reporter_tid,
					   caller_uid,
					   caller_pid,
					   service_id,
					   op_id,
					   service,
					   operation,
					   obj,
					   &decision,
					   result);

	plan = iguard_build_file_open_enforce_plan(&decision, result, mode);

	iguard_emit_file_open_enforce_plan(seqno,
					   reporter_tgid,
					   reporter_tid,
					   caller_uid,
					   caller_pid,
					   service_id,
					   op_id,
					   service,
					   operation,
					   obj,
					   &decision,
					   result,
					   mode,
					   &plan);

	if (iguard_should_really_enforce(&plan, mode))
		future_errno = plan.future_errno;

	if (decision_out)
		*decision_out = decision;

	if (future_errno_out)
		*future_errno_out = future_errno;

	t1_ns = ktime_get_mono_fast_ns();
	decision_ns = t1_ns - t0_ns;

	iguard_emit_file_open_perf(seqno,
				   reporter_tgid,
				   reporter_tid,
				   caller_uid,
				   caller_pid,
				   service_id,
				   op_id,
				   service,
				   operation,
				   obj,
				   &decision,
				   result,
				   future_errno,
				   decision_ns);

	return result;
}
/* I-GUARD decision / apply / enforcement helper end */

int iguard_ctx_apply_relation_decision(
		const struct iguard_relation_decision_input *input)
{
	struct iguard_deleg_ctx snap;
	const struct iguard_policy_rule *rule = NULL;
	const char *verdict = "abstain";
	const char *reason = "no_context";
	bool context_available = false;
	bool stable_rule_match = false;
	bool relation_requirements_match = false;
	bool relation_complete = false;
	bool native_allowed = false;
	size_t rule_id = 0;
	enum iguard_decision_kind rule_decision_kind = IGUARD_DECISION_AUDIT;
	u32 rule_required_relation_type = 0;
	u32 rule_required_relation_stage = 0;
	char rule_reason[IGUARD_RUNTIME_STR_MAX];
	pid_t decision_tgid;
	pid_t decision_tid;
	int ret = 0;

	if (!input)
		return 0;

	IGUARD_QC_INC(relation_decision);
	IGUARD_QC_INC(relation_publish_total);

	memset(rule_reason, 0, sizeof(rule_reason));
	decision_tgid = task_tgid_nr(current);
	decision_tid = task_pid_nr(current);
	native_allowed = input->native_allowed;
	relation_complete = input->relation_complete &&
		input->relation_type == IGUARD_RELATION_TYPE_DIRECT_BACKING_FILE_REFERENCE &&
		input->relation_stage == IGUARD_RELATION_STAGE_OPEN_TIME &&
		input->mapping_generation != 0 &&
		input->lower_file_cookie != 0 &&
		input->proxy_file_cookie != 0 &&
		input->lower_inode != 0 &&
		input->lower_s_dev != 0 &&
		!input->relation_ambiguous &&
		!input->relation_stale;

	memset(&snap, 0, sizeof(snap));
	context_available = iguard_ctx_lookup_current(&snap);
	if (!context_available)
		goto emit;

	reason = "no_stable_rule_match";
	if (!native_allowed) {
		reason = "native_not_allowed";
		goto emit;
	}

	mutex_lock(&iguard_runtime_policy_lock);
	rule = iguard_find_best_matching_relation_runtime_rule(
			snap.service_id, snap.op_id, snap.caller_uid,
			snap.service, snap.operation, input, &rule_id);
	if (rule)
		stable_rule_match = true;
	if (rule) {
		rule_decision_kind = rule->decision_kind;
		rule_required_relation_type = rule->required_relation_type;
		rule_required_relation_stage = rule->required_relation_stage;
		if (rule->reason)
			strscpy(rule_reason, rule->reason, sizeof(rule_reason));
	}
	mutex_unlock(&iguard_runtime_policy_lock);

	if (!stable_rule_match)
		goto emit;

	if (!relation_complete) {
		reason = input->relation_stale ? "relation_stale" :
			input->relation_ambiguous ? "relation_ambiguous" :
			"relation_incomplete";
		goto emit;
	}

	relation_requirements_match =
		rule_required_relation_type == input->relation_type &&
		rule_required_relation_stage == input->relation_stage;
	if (!relation_requirements_match) {
		reason = "relation_requirements_mismatch";
		goto emit;
	}

	if (rule_decision_kind == IGUARD_DECISION_WOULD_DENY) {
		verdict = "deny";
		reason = rule_reason[0] ? rule_reason : "relation_rule_deny";
		ret = -EACCES;
	} else {
		verdict = "abstain";
		reason = rule_reason[0] ? rule_reason : "relation_rule_audit";
	}

emit:
	if (relation_complete)
		IGUARD_QC_INC(relation_complete);
	else {
		IGUARD_QC_INC(relation_incomplete);
		if (!input->relation_stale && !input->relation_ambiguous)
			IGUARD_QC_INC(relation_unpaired);
	}
	if (relation_complete &&
	    iguard_target_object_match((unsigned long)input->lower_inode,
				       (dev_t)input->lower_s_dev))
		iguard_fd_target_proxy_track(input->proxy_file_cookie);
	if (input->relation_stale)
		IGUARD_QC_INC(relation_stale);
	if (stable_rule_match)
		IGUARD_QC_INC(relation_rule_match);
	else
		IGUARD_QC_INC(relation_rule_nonmatch);
	if (ret == -EACCES) {
		IGUARD_QC_INC(relation_deny);
		IGUARD_QC_INC(frdac_denied_internal_fd_acquire_total);
		IGUARD_QC_INC(frdac_denied_internal_fd_outstanding);
		IGUARD_QC_INC(frdac_denied_internal_fd_release_total);
		this_cpu_dec(iguard_qc.frdac_denied_internal_fd_outstanding);
	} else {
		IGUARD_QC_INC(relation_allow);
	}

	iguard_vinfo("CDAC_RELATION_AWARE_DECISION event=CDAC_RELATION_AWARE_DECISION audit_seq=%llu ts_ns=%llu context_id=%llu source=%s caller_context_available=%u caller_uid=%u caller_pid=%u reporter_tgid=%d reporter_tid=%d decision_pid=%d decision_tid=%d service_id=%u op_id=%u service=%s operation=%s target_inode=%llu target_s_dev=%u:%u relation_type=%u relation_stage=%u connection_identity=%llu:%llu nodeid=%llu mapping_generation=%llu relation_id_for_logging=%llu lower_file_cookie=%llu proxy_file_cookie=%llu lower_f_flags=0x%x lower_f_mode=0x%x proxy_f_flags=0x%x proxy_f_mode=0x%x native_allowed=%u relation_complete=%u relation_ambiguous=%u relation_stale=%u rule_id=%zu stable_rule_match=%u relation_requirements_match=%u verdict=%s reason=%s\n",
		(unsigned long long)iguard_audit_next_seq(),
		(unsigned long long)ktime_get_ns(),
		context_available ? (unsigned long long)snap.seqno : 0ULL,
		input->source ? input->source : "-",
		context_available ? 1 : 0,
		context_available ? snap.caller_uid : 0,
		context_available ? snap.caller_pid : 0,
		context_available ? snap.reporter_tgid : 0,
		context_available ? snap.reporter_tid : 0,
		decision_tgid,
		decision_tid,
		context_available ? snap.service_id : 0,
		context_available ? snap.op_id : 0,
		context_available ? snap.service : "-",
		context_available ? snap.operation : "-",
		(unsigned long long)input->lower_inode,
		MAJOR((dev_t)input->lower_s_dev),
		MINOR((dev_t)input->lower_s_dev),
		input->relation_type,
		input->relation_stage,
		(unsigned long long)input->connection_major,
		(unsigned long long)input->connection_minor,
		(unsigned long long)input->nodeid,
		(unsigned long long)input->mapping_generation,
		(unsigned long long)input->relation_id_for_logging,
		(unsigned long long)input->lower_file_cookie,
		(unsigned long long)input->proxy_file_cookie,
		input->lower_f_flags,
		input->lower_f_mode,
		input->proxy_f_flags,
		input->proxy_f_mode,
		native_allowed ? 1 : 0,
		relation_complete ? 1 : 0,
		input->relation_ambiguous ? 1 : 0,
		input->relation_stale ? 1 : 0,
		rule_id,
		stable_rule_match ? 1 : 0,
		relation_requirements_match ? 1 : 0,
		verdict,
		reason ? reason : "-");

	return ret;
}
EXPORT_SYMBOL_GPL(iguard_ctx_apply_relation_decision);

static ssize_t iguard_policy_ctl_write(struct file *file,
				       const char __user *ubuf,
				       size_t len,
				       loff_t *ppos)
{
	char buf[IGUARD_POLICY_CTL_MAX];
	char *cursor, *tok;
	struct iguard_runtime_policy_rule tmp;
	bool has_decision = false;

	if (len == 0 || len >= sizeof(buf))
		return -EINVAL;

	if (copy_from_user(buf, ubuf, len))
		return -EFAULT;

	buf[len] = '\0';
	strim(buf);

	if (strcmp(buf, "clear") == 0) {
		int ret = iguard_ctx_runtime_policy_clear_all();

		if (ret)
			return ret;
		return len;
	}

	if (strncmp(buf, "add ", 4) != 0)
		return -EINVAL;

	iguard_runtime_rule_reset(&tmp);
	tmp.used = true;

	cursor = buf + 4;

	while ((tok = strsep(&cursor, " ")) != NULL) {
		char *eq;
		u32 u32v;
		u64 u64v;

		if (*tok == '\0')
			continue;

		eq = strchr(tok, '=');
		if (!eq)
			return -EINVAL;

		*eq = '\0';
		eq++;

		if (strcmp(tok, "service_id") == 0) {
			if (kstrtou32(eq, 0, &u32v))
				return -EINVAL;
			tmp.rule.service_id = u32v;
		} else if (strcmp(tok, "op_id") == 0) {
			if (kstrtou32(eq, 0, &u32v))
				return -EINVAL;
			tmp.rule.op_id = u32v;
		} else if (strcmp(tok, "service") == 0) {
			strscpy(tmp.service_buf, eq, sizeof(tmp.service_buf));
		} else if (strcmp(tok, "operation") == 0) {
			strscpy(tmp.operation_buf, eq, sizeof(tmp.operation_buf));
		} else if (strcmp(tok, "path_tail") == 0) {
			strscpy(tmp.path_tail_buf, eq, sizeof(tmp.path_tail_buf));
		} else if (strcmp(tok, "reason") == 0) {
			strscpy(tmp.reason_buf, eq, sizeof(tmp.reason_buf));
		} else if (strcmp(tok, "f_flags_mask") == 0) {
			if (kstrtou32(eq, 0, &u32v))
				return -EINVAL;
			tmp.rule.f_flags_mask = (int)u32v;
		} else if (strcmp(tok, "f_flags_value") == 0) {
			if (kstrtou32(eq, 0, &u32v))
				return -EINVAL;
			tmp.rule.f_flags_value = (int)u32v;
		} else if (strcmp(tok, "f_mode_mask") == 0) {
			if (kstrtou32(eq, 0, &u32v))
				return -EINVAL;
			tmp.rule.f_mode_mask = (fmode_t)u32v;
		} else if (strcmp(tok, "f_mode_value") == 0) {
			if (kstrtou32(eq, 0, &u32v))
				return -EINVAL;
			tmp.rule.f_mode_value = (fmode_t)u32v;
		} else if (strcmp(tok, "ino") == 0) {
			if (kstrtou64(eq, 0, &u64v))
				return -EINVAL;
			tmp.rule.ino = (unsigned long)u64v;
		} else if (strcmp(tok, "s_dev") == 0) {
			if (kstrtou64(eq, 0, &u64v))
				return -EINVAL;
			tmp.rule.s_dev = (dev_t)u64v;
			} else if (strcmp(tok, "i_mode") == 0) {
				if (kstrtou32(eq, 0, &u32v))
					return -EINVAL;
				tmp.rule.i_mode = (umode_t)u32v;
			} else if (strcmp(tok, "required_relation_type") == 0) {
				if (kstrtou32(eq, 0, &u32v))
					return -EINVAL;
				tmp.rule.required_relation_type = u32v;
			} else if (strcmp(tok, "required_relation_stage") == 0) {
				if (kstrtou32(eq, 0, &u32v))
					return -EINVAL;
				tmp.rule.required_relation_stage = u32v;
			} else if (strcmp(tok, "decision") == 0) {
				if (iguard_parse_decision_kind(eq, &tmp.rule.decision_kind))
					return -EINVAL;
			has_decision = true;
		} else {
			return -EINVAL;
		}
	}

	if (!has_decision)
		return -EINVAL;

	iguard_runtime_rule_fixup_ptrs(&tmp);

	{
		int ret;

			if (tmp.rule.required_relation_type != 0 ||
			    tmp.rule.required_relation_stage != 0) {
				ret = iguard_ctx_runtime_policy_add_relation_rule_fields(
					tmp.rule.service_id,
					tmp.rule.op_id,
					tmp.rule.caller_uid,
					tmp.rule.decision_kind,
					(u64)tmp.rule.ino,
					(u64)tmp.rule.s_dev,
					tmp.rule.required_relation_type,
					tmp.rule.required_relation_stage,
					tmp.rule.service,
					tmp.rule.operation,
					tmp.rule.reason);
			} else {
				ret = iguard_ctx_runtime_policy_add_rule_fields(
					tmp.rule.service_id,
					tmp.rule.op_id,
					tmp.rule.caller_uid,
				tmp.rule.decision_kind,
				tmp.rule.f_flags_mask,
				tmp.rule.f_flags_value,
				(int)tmp.rule.f_mode_mask,
				(int)tmp.rule.f_mode_value,
				(u64)tmp.rule.ino,
				(u64)tmp.rule.s_dev,
				(u32)tmp.rule.i_mode,
				tmp.rule.service,
					tmp.rule.operation,
					tmp.rule.path_tail,
					tmp.rule.reason);
			}
			if (ret)
				return ret;

		return len;
	}
}

static int iguard_policy_dump_show(struct seq_file *m, void *v)
{
	size_t i;

	mutex_lock(&iguard_runtime_policy_lock);

	seq_printf(m, "runtime_policy_count=%zu\n", iguard_runtime_policy_count);

	for (i = 0; i < IGUARD_RUNTIME_POLICY_MAX; i++) {
		const struct iguard_runtime_policy_rule *rr =
			&iguard_runtime_policy_table[i];
		const struct iguard_policy_rule *r;

		if (!rr->used)
			continue;

		r = &rr->rule;

		seq_printf(m,
			   "[%zu] service_id=%u op_id=%u caller_uid=%u service=%s operation=%s path_tail=%s ino=%lu s_dev=%u:%u i_mode=0%o f_flags_mask=0x%x f_flags_value=0x%x f_mode_mask=0x%x f_mode_value=0x%x required_relation_type=%u required_relation_stage=%u decision=%s reason=%s specificity=%d\n",
			   i,
			   r->service_id,
			   r->op_id,
			   r->caller_uid,
			   r->service ? r->service : "-",
			   r->operation ? r->operation : "-",
			   r->path_tail ? r->path_tail : "-",
			   r->ino,
			   MAJOR(r->s_dev), MINOR(r->s_dev),
			   r->i_mode,
			   r->f_flags_mask,
			   r->f_flags_value,
			   (unsigned int)r->f_mode_mask,
			   (unsigned int)r->f_mode_value,
			   r->required_relation_type,
			   r->required_relation_stage,
			   iguard_decision_kind_str(r->decision_kind),
			   r->reason ? r->reason : "-",
			   iguard_policy_rule_specificity_score(r));
	}

	mutex_unlock(&iguard_runtime_policy_lock);
	return 0;
}

static int iguard_policy_dump_open(struct inode *inode, struct file *file)
{
	return single_open(file, iguard_policy_dump_show, inode->i_private);
}

static int iguard_quiet_counters_show(struct seq_file *m, void *v)
{
	seq_printf(m, "counter_schema_version=%u\n",
		   IGUARD_QUIET_COUNTER_SCHEMA_VERSION);
	seq_printf(m, "context_push_ok=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(context_push_ok));
	seq_printf(m, "context_push_fail=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(context_push_fail));
	seq_printf(m, "context_pop_ok=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(context_pop_ok));
	seq_printf(m, "context_pop_fail=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(context_pop_fail));
	seq_printf(m, "context_lookup_hit=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(context_lookup_hit));
	seq_printf(m, "context_lookup_miss=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(context_lookup_miss));
	seq_printf(m, "relation_decision=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(relation_decision));
	seq_printf(m, "relation_complete=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(relation_complete));
	seq_printf(m, "relation_incomplete=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(relation_incomplete));
	seq_printf(m, "relation_stale=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(relation_stale));
	seq_printf(m, "relation_rule_match=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(relation_rule_match));
	seq_printf(m, "relation_rule_nonmatch=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(relation_rule_nonmatch));
	seq_printf(m, "relation_deny=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(relation_deny));
	seq_printf(m, "relation_allow=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(relation_allow));
	seq_printf(m, "file_open_join=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(file_open_join));
	seq_printf(m, "file_open_no_context=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(file_open_no_context));
	seq_printf(m, "file_open_deny=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(file_open_deny));
	seq_printf(m, "relation_publish_total=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(relation_publish_total));
	seq_printf(m, "relation_unpaired=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(relation_unpaired));
	seq_printf(m, "context_enter_total=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(context_push_ok));
	seq_printf(m, "context_exit_total=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(context_pop_ok));
	seq_printf(m, "context_nested_mismatch_total=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(context_push_fail));
	seq_printf(m, "context_stale_total=%llu\n", 0ULL);
	seq_printf(m, "context_borrowed_total=%llu\n", 0ULL);
	seq_printf(m, "rule_match_total=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(relation_rule_match));
	seq_printf(m, "frdac_deny_total=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(relation_deny));
	seq_printf(m, "fd_receive_event_total=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(fd_receive_event_total));
	seq_printf(m, "fd_receiver_install_attempt_total=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(fd_receiver_install_attempt_total));
	seq_printf(m, "fd_receiver_install_success_total=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(fd_receiver_install_success_total));
	seq_printf(m, "fd_receiver_install_failure_total=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(fd_receiver_install_failure_total));
	seq_printf(m, "frdac_target_fd_transfer_attempt_total=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(frdac_target_fd_transfer_attempt_total));
	seq_printf(m, "frdac_target_receiver_install_success_total=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(frdac_target_receiver_install_success_total));
	seq_printf(m, "frdac_target_receiver_install_failure_total=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(frdac_target_receiver_install_failure_total));
	seq_printf(m, "frdac_denied_internal_fd_acquire_total=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(frdac_denied_internal_fd_acquire_total));
	seq_printf(m, "frdac_denied_internal_fd_release_total=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(frdac_denied_internal_fd_release_total));
	seq_printf(m, "frdac_denied_internal_fd_outstanding=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(frdac_denied_internal_fd_outstanding));
	seq_printf(m, "frdac_denied_app_fd_install_total=%llu\n",
		   (unsigned long long)IGUARD_QC_SUM(frdac_denied_app_fd_install_total));
	return 0;
}

static int iguard_quiet_counters_open(struct inode *inode, struct file *file)
{
	return single_open(file, iguard_quiet_counters_show, inode->i_private);
}

static void iguard_quiet_counters_reset(void)
{
	int cpu;

	for_each_possible_cpu(cpu)
		memset(&per_cpu(iguard_qc, cpu), 0,
		       sizeof(struct iguard_quiet_counters));
}

static ssize_t iguard_quiet_counters_write(struct file *file,
					   const char __user *ubuf,
					   size_t len, loff_t *ppos)
{
	char buf[16];
	size_t n;

	n = min(len, sizeof(buf) - 1);
	if (copy_from_user(buf, ubuf, n))
		return -EFAULT;
	buf[n] = '\0';
	strim(buf);
	if (strcmp(buf, "reset") != 0)
		return -EINVAL;

	iguard_quiet_counters_reset();
	return len;
}

static const struct file_operations iguard_policy_ctl_fops = {
	.write = iguard_policy_ctl_write,
	.llseek = noop_llseek,
};

static const struct file_operations iguard_policy_dump_fops = {
	.open = iguard_policy_dump_open,
	.read = seq_read,
	.llseek = seq_lseek,
	.release = single_release,
};

static const struct file_operations iguard_quiet_counters_fops = {
	.open = iguard_quiet_counters_open,
	.read = seq_read,
	.write = iguard_quiet_counters_write,
	.llseek = seq_lseek,
	.release = single_release,
};

int iguard_ctx_audit_file_open(struct file *file)
{
	struct iguard_file_open_decision decision;
	struct iguard_object_key obj;
	enum iguard_apply_result apply_result;
	int future_errno = 0;
	struct iguard_deleg_ctx snap;
	struct inode *inode;
	pid_t tid = task_pid_nr(current);

	if (!file)
		return 0;

	inode = file_inode(file);
	if (!inode)
		return 0;

	iguard_build_object_key(file, inode, &obj);

	if (obj.path_tail && strcmp(obj.path_tail, "iguard_ctl") == 0) {
		iguard_vinfo("iguard_ctx: skip-control-open current_tgid=%d current_tid=%d path_tail=%s ino=%lu s_dev=%u:%u i_mode=0%o f_flags=0x%x f_mode=0x%x\n",
			task_tgid_nr(current),
			task_pid_nr(current),
			obj.path_tail,
			obj.ino,
			MAJOR(obj.s_dev), MINOR(obj.s_dev),
			obj.i_mode,
			obj.f_flags,
			(unsigned int)obj.f_mode);
		return 0;
	}

	iguard_ablate_object_key_if_needed(&obj);

	if (!iguard_ctx_lookup_current(&snap)) {
		IGUARD_QC_INC(file_open_no_context);
		iguard_vinfo("CDAC_BINDER_NO_CONTEXT source=VFS_OPEN current_tgid=%d current_tid=%d ino=%lu s_dev=%u:%u i_mode=0%o f_flags=0x%x f_mode=0x%x path_tail=%s join_result=abstain\n",
			task_tgid_nr(current),
			tid,
			obj.ino,
			MAJOR(obj.s_dev), MINOR(obj.s_dev),
			obj.i_mode,
			obj.f_flags,
			(unsigned int)obj.f_mode,
			obj.path_tail ? obj.path_tail : "(null)");
		return 0;
	}

	apply_result = iguard_apply_file_open_decision(snap.seqno,
						       snap.reporter_tgid,
						       snap.reporter_tid,
						       snap.caller_uid,
						       snap.caller_pid,
						       snap.service_id,
						       snap.op_id,
						       snap.service,
						       snap.operation,
						       &obj,
						       &decision,
						       &future_errno);

	if (apply_result == IGUARD_APPLY_WOULD_DENY && future_errno < 0) {
		IGUARD_QC_INC(file_open_deny);
		iguard_vinfo("iguard_ctx: real-enforce seq=%llu reporter_tgid=%d reporter_tid=%d caller_uid=%u caller_pid=%u service_id=%u op_id=%u service=%s op=%s path_tail=%s errno=%d verdict=deny-now\n",
			(unsigned long long)snap.seqno,
			snap.reporter_tgid,
			snap.reporter_tid,
			snap.caller_uid,
			snap.caller_pid,
			snap.service_id,
			snap.op_id,
			snap.service,
			snap.operation,
			obj.path_tail ? obj.path_tail : "(null)",
			future_errno);

		return future_errno;
	}

	IGUARD_QC_INC(file_open_join);
	iguard_vinfo("CDAC_BINDER_VFS_JOIN source=UNIFIED_BINDER_HOOK seq=%llu reporter_tgid=%d reporter_tid=%d caller_uid=%u caller_pid=%u vfs_tid=%d endpoint_id=%llu service_id=%u op_id=%u transaction_code=%u transaction_flags=0x%x nesting_depth=%u service=%s op=%s file_cookie=%llu ino=%lu s_dev=%u:%u i_mode=0%o f_flags=0x%x f_mode=0x%x path_tail=%s join_result=joined stack_result=top\n",
		(unsigned long long)snap.seqno,
		snap.reporter_tgid,
		snap.reporter_tid,
		snap.caller_uid,
		snap.caller_pid,
		tid,
		(unsigned long long)snap.endpoint_id,
		snap.service_id,
		snap.op_id,
		snap.transaction_code,
		snap.transaction_flags,
		snap.nesting_depth,
		snap.service,
		snap.operation,
		(unsigned long long)iguard_file_cookie(file),
		obj.ino,
		MAJOR(obj.s_dev), MINOR(obj.s_dev),
		obj.i_mode,
		obj.f_flags,
		(unsigned int)obj.f_mode,
		obj.path_tail ? obj.path_tail : "(null)");

	return 0;
}
EXPORT_SYMBOL_GPL(iguard_ctx_audit_file_open);

static int __init iguard_ctx_init(void)
{
	hash_init(iguard_ctx_table);
	hash_init(iguard_file_cookie_table);

	iguard_debugfs_dir = debugfs_create_dir("iguard", NULL);
	if (!IS_ERR_OR_NULL(iguard_debugfs_dir)) {
		debugfs_create_file("policy_ctl", 0200,
				    iguard_debugfs_dir, NULL,
				    &iguard_policy_ctl_fops);
		debugfs_create_file("policy_dump", 0400,
				    iguard_debugfs_dir, NULL,
				    &iguard_policy_dump_fops);
		debugfs_create_file("quiet_counters", 0600,
				    iguard_debugfs_dir, NULL,
				    &iguard_quiet_counters_fops);
		debugfs_create_bool("ablate_disable_runtime", 0600,
				    iguard_debugfs_dir,
				    &iguard_ablate_disable_runtime);
		debugfs_create_bool("ablate_disable_ctx", 0600,
				    iguard_debugfs_dir,
				    &iguard_ablate_disable_ctx);
		debugfs_create_bool("ablate_path_tail_only", 0600,
				    iguard_debugfs_dir,
				    &iguard_ablate_path_tail_only);
		debugfs_create_bool("verbose_audit", 0600,
				    iguard_debugfs_dir,
				    &iguard_verbose_audit);
	} else {
		pr_warn("iguard_ctx: debugfs create_dir failed\n");
	}

	pr_info("iguard_ctx: core initialized\n");
	return 0;
}
core_initcall(iguard_ctx_init);
