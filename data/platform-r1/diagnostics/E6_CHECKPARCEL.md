# E6_CHECKPARCEL.md — checkParcel 与 CHECK_PARCEL_SIZE（只读核验）

## 1. 源码
- A15 Binder.java:95 `public static final boolean CHECK_PARCEL_SIZE = false;`
  （A16:94、A17:91 同为 false）。
- `static void checkParcel(IBinder obj, int code, Parcel parcel, String msg)`（A15:1280 起）：
  `if (CHECK_PARCEL_SIZE && parcel.dataSize() >= 800*1024) { … sb.append… }`
  → 编译期常量 false ⇒ 分支为死代码。注释中的 800k 阈值只在 CHECK_PARCEL_SIZE=true 时生效。
- 调用点：修正 A15 的 finally 内 `checkParcel(this, code, reply, "Unreasonably large…")`，
  位于 `CdacBinderContext.exit` **之后**（三段 finally 副本同序）。

## 2. 产物核验（dex，对应已运行制品）
- 输入：`…/framework-minus-apex/android_common/aligned/framework.jar`
  sha256=2bf9d97ef94d373e663796cf080133ea773abb21478c28bc7f02ff7f06e598ef（mtime 11-01 14:26，
  与固定制品 system.img 70c2ab35 同构建）。
- classes3.dex sha256=543fa3481674792845754a7428b3cf926d8b179f5df04ac5f48f74193fc405cc。
- `dexdump -d`（build-tools 35.0.1，工具 sha 见 04_dex/dexdump_tool_sha.txt）rc=0；
  `Binder.checkParcel` 方法体 = **仅 `return-void`**（04_dex/raw_checkParcel.txt）。
  无 RuntimeException 字符串/无 800*1024 常量/无 try-catch。
- 结论：固定制品中 checkParcel 不会抛；E6 不可触发。

## 3. 与其它机制的边界
- Binder 传输层的 `TransactionTooLargeException`（BinderProxy/驱动）是不同机制，不属
  checkParcel；不混用。
- exit-before-checkParcel 的次序仍是防御性结构属性（若未来配置翻转常量/分支），
  但本轮不把它当作“已触发的运行路径”。修正本身是为 E5 做的，E6 仅次序声明。

## 4. 勘误
- 原表述“超大 reply 会由 checkParcel 抛 RuntimeException/E6” → 改为：
  “CHECK_PARCEL_SIZE=false 常量折叠，固定制品 checkParcel 为 return-void；E6 不触发，
  仅保留 exit 在 checkParcel 之前的次序属性”。
