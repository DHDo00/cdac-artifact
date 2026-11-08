# Applying the patches

## AOSP 16 (primary build)

Base: manifest revision `android16-qpr2-release`, product
`aosp_cf_x86_64_only_phone`, release trunk_staging, variant eng.

    repo init -u https://android.googlesource.com/platform/manifest -b android16-qpr2-release
    repo sync -c

Base commit per modified project:

| Project | Base commit |
|---|---|
| device/generic/goldfish | f3487b53aafe47000f08501243f5924526f1809a |
| device/google/cuttlefish | 4d368849922b04124e66b1aad48f93b3209f3c8d |
| external/libfuse | cb0f94cf4cd8769e3d18f2bb0dd8ace65e6bcb31 |
| frameworks/base | 45034f0663f960d9ee5fb0a101a4732b71f6e2f4 |
| packages/providers/ContactsProvider | 5821e66694f1075d15e48f9a7d073bddd7b34aa8 |
| packages/providers/DownloadProvider | a1f6f64f40b78cfe4db4ac2763609c470f487cd4 |
| packages/providers/MediaProvider | 217515852d78543d1d7da39bd69d4e03957ee118 |
| packages/providers/TelephonyProvider | 6b585cd335401601ce730104242159b18c9c6ae9 |
| system/extras | 3f52a5ab49ba53bc463de658db1d112e001c0280 |
| system/sepolicy | 43e4494a5a78317819dcc2766a11927c12ef3dfd |

Apply in the matching project directory:

    git apply -p1 /path/to/code/android16/000N-<project>.patch

`0001` through `0009` map to the table rows in order. system/extras has no
tracked-file patch; only new files.

Copy the new files from `code/android16/new-files/<project-path>/` into the
same path inside each project. New files for system/extras build the
`iguardctl_test` binary.

Build:

    . build/envsetup.sh
    lunch aosp_cf_x86_64_only_phone-trunk_staging-eng
    m -j

## Kernel

Base: `kernel/common` at commit `ff78c78d65d3b2e46c6cd4c1b59e8e0e6150cdae`
(common-android16-6.12 lineage, 6.12.74).

Check out that commit in `common/`, then:

    git apply -p1 /path/to/code/kernel/android16-6.12.patch

and copy the files in `code/kernel/new-files/` to the same paths in the
kernel tree (`drivers/misc/iguard_ctl.c`, `include/linux/iguard_ctx.h`,
`include/linux/iguard_msg.h`, `security/iguard_ctx.c`).

Build with Kleaf:

    tools/bazel build //common-modules/virtual-device:virtual_device_x86_64_dist

The dist contains `bzImage`, `initramfs.img`, and `iguard_ctl.ko`.

## AOSP 15 port

Base tag `android-15.0.0_r36`, TARGET_RELEASE=bp1a. Four projects:
frameworks/base, system/sepolicy, device/google/cuttlefish,
device/generic/goldfish. Apply the four files in `code/android15/` with
`git apply -p1` and copy `code/android15/new-files/` (the Cdac*.java files
go to `frameworks/base/core/java/android/os/`, the .te files to
`system/sepolicy/private/`). A15 also needs this line appended to
`system/sepolicy/contexts/plat_file_contexts_test` so checkfc passes:

    /dev/iguard_ctl	iguard_ctl_device

## AOSP 17 port

Base tag `android-17.0.0_r1` (TUNA). Four projects as above. Apply the
four files in `code/android17/` and copy `code/android17/new-files/` into
`frameworks/base/core/java/android/os/`. The SELinux additions for A17 are
inside `system_sepolicy.diff`.

## Running

tools/cvd/start.sh launches an isolated Cuttlefish instance (instance 9).
Set these variables first:

    CDAC_AOSP_ROOT    path to the patched AOSP 16 tree
    CDAC_PRODUCT_OUT  path to out/target/product/vsoc_x86_64_only
    CDAC_KERNEL_DIST  path to the kernel dist with bzImage and initramfs.img
    CDAC_STOCK_ROOT   path to an unpatched AOSP 16 tree (baseline mode)

    bash tools/cvd/start.sh experimental /absolute/new/runtime
    bash tools/cvd/stop.sh /absolute/new/runtime

The device-side control binary is built from
`tools/iguardctl_test/` as part of system/extras.
