# CLIENT_CHANGE_RECORD.md — 客户端调整记录（第 39 轮）

## 变更内容
仅为逐请求观测增加 `reqid`（唯一请求标识）：
1. MainActivity 增加实例字段 `mReqId`；onCreate 读取 intent extra `reqid`；
2. 每次调用开始前打一行 `REQ reqid=… pid=… tid=… cmd=…`；
3. 所有结果行（成功/失败）追加 `reqid=…` 后缀。
- 未改任何 API 调用、权限集、mode（"r"/"w"）、URI/Provider 路径、规则或机制。
- app_a 基于 R36 `ref_app_a_r36`（含 make_image/read_cr/read_cpc/write_mp/
  restore_mp/write_diag/restore_diag/query_state）；app_b 基于 R35 `ref_app_b_r35`。
- 生成器：`make_app_sources.py`；逐行 diff：`app_*/src/…/MainActivity.java.reqid.diff`。

## 语义不变核对
| 维度 | app_a | app_b |
|---|---|---|
| 包/权限 | com.demo.espafdtest；无 permission（owner 视图） | com.demo.espafdtestb；READ_MEDIA_IMAGES（redacted 视图） |
| M 读 API | ContentProviderClient.openFile(uri,"r") → txn14 openFile | 同左 |
| L 读 API | ContentProviderClient.openFile(uri,"r") → txn14 openFile | 不用于 L |
| L 写 API | ContentResolver.openFileDescriptor(uri,"w") → txn15 openAssetFile | 不用于 L |
| mode | "r"/"w" 与历史一致 | "r" |
| 路径 | MediaStore.Images insert → media URI → MediaProvider 6/501 | 同左 |
| write 载荷 | image1.jpg 标记位替换 token（与 R36 相同算法） | — |

## APK 冻结哈希（构建前源码冻结）
见 00_inputs/INPUT_AND_VERSION_CHECK.md。
