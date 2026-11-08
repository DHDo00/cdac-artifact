# FAILURES.md — 第 39 轮失败/异常/重试/超时记录

## 最终计数：零项
- 启动失败/启动超时：0（3 次启动尝试全部 ADB_OK，46–48 次轮询内完成，见 06_runtime/attempts.log）。
- 正式请求失败（预期允许却 FAIL）/预期不符/超时/重试：0。
- 规则安装/读回失败：0（每次状态切换 add/dump 或 clear/dump 均与冻结字段一致）。
- 恢复失败：0（每 boot 60 次 RESTORE_PASS，backing 回 e22785cd…）。
- 额外 boot / 替换失败单元 / campaign 重跑：0。
- EXCLUSIONS.csv 零数据行；UNRESOLVED 与 OTHER_FAILURE 计数均为 0。
