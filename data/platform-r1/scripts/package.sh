#!/bin/bash
# package.sh — build audit_package/ + SHA256SUMS.txt + audit_package.tar.gz (this round)
set -euo pipefail
cd "$(dirname "$0")/.."
PKG=audit_package
mkdir -p "$PKG"
# top-level small deliverables
for f in README.md INPUT_AND_PROVENANCE.md INPUT_HASHES.csv PRE_LAUNCH_STATE.txt \
  EXISTING_BATCH_ELIGIBILITY.csv ALIGNMENT_PLAN.md ALIGNMENT_PLAN_AMENDMENT_1.md PROTOCOL_FROZEN.md \
  ARTIFACT_AND_RUNTIME_IDENTITY.csv PER_REQUEST_LEDGER.csv PER_BOOT_SUMMARY.csv THREE_VERSION_SUMMARY.csv \
  TABLE_XV_DATA.md SCOPE_ALIGNMENT.csv GRAPHICSSTATS_SCOPE_RECONCILIATION.csv \
  CLAIM_EVIDENCE_MAP.csv FAILURES_AND_EXCLUSIONS.md MISSING_AND_LIMITATIONS.md DATA_FEEDBACK.md \
  RAW_EVIDENCE_INDEX.csv FINAL_STATUS.txt; do
  [ -f "$f" ] && cp -p "$f" "$PKG/$f"
done
# directories
cp -rp scope "$PKG/"
cp -rp diagnostics "$PKG/"
cp -rp history_ledgers "$PKG/"
cp -rp evidence_slices "$PKG/"
cp -rp scripts "$PKG/"
# per-boot small evidence
for b in a15_boot2 a15_boot3 a16_boot2 a16_boot3 a17_boot3; do
  d="$PKG/runs/$b"; mkdir -p "$d/matrix" "$d/preflight"
  cp -p "runs/$b/PER_REQUEST_LEDGER.csv" "$d/" 2>/dev/null || cp -p "runs/$b/matrix/PER_REQUEST_LEDGER.csv" "$d/PER_REQUEST_LEDGER.csv"
  cp -p "runs/$b/boot_summary.json" "$d/" 2>/dev/null || true
  cp -p "runs/$b/protocol_frozen_"*.md "$d/" 2>/dev/null || true
  cp -p "runs/$b/attempts.log" "$d/" 2>/dev/null || true
  cp -p "runs/$b/input_img_hashes_pre.txt" "$d/" 2>/dev/null || true
  cp -p "runs/$b/preflight/uris.env" "$d/preflight/" 2>/dev/null || true
  for f in boot_id fingerprint release sdk selinux_mode kernel_rel dev_iguard_ctl_lsZ codename build_id security_patch proc_version; do
    cp -p "runs/$b/preflight/$f.txt" "$d/preflight/" 2>/dev/null || true
  done
  cp -p "runs/$b/matrix/"*_app.txt "$d/matrix/" 2>/dev/null || true
  cp -p "runs/$b/matrix/"*_am.txt "$d/matrix/" 2>/dev/null || true
  cp -p "runs/$b/matrix/"b1_rule_add.txt "runs/$b/matrix/"b2_rule_add.txt "runs/$b/matrix/"b1_rule_clear.txt "runs/$b/matrix/"b2_rule_clear.txt "$d/matrix/" 2>/dev/null || true
  cp -p "runs/$b/matrix/final_policy_dump.txt" "$d/matrix/" 2>/dev/null || true
  cp -p "runs/$b/matrix/final_policy_dump_recovered.txt" "$d/matrix/" 2>/dev/null || true
  cp -p "runs/$b/matrix/final_qc_recovered.txt" "$d/matrix/" 2>/dev/null || true
  cp -p "runs/$b/matrix/b3_post_qc.txt" "$d/matrix/" 2>/dev/null || true
  cp -p "runs/$b/matrix/"*_backingX.sha "$d/matrix/" 2>/dev/null || true
  cp -p "runs/$b/matrix/"*_backingY.sha "$d/matrix/" 2>/dev/null || true
done
# SHA256SUMS inside audit_package (paths ./..., excludes itself); top-level copy for convenience
(cd "$PKG" && find . -type f ! -name SHA256SUMS.txt -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS.txt)
cp "$PKG/SHA256SUMS.txt" ./SHA256SUMS.txt
echo "package file count: $(find "$PKG" -type f | wc -l)"
