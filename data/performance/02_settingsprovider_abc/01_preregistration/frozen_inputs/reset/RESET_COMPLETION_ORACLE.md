# Reset completion oracle

A reset is complete only when all of the following machine checks pass:

- immutable pre-state and post-state snapshots have boot UUID, arm, rule hash, switch hash, counter map, log watermark, and host/guest timestamps;
- two consecutive complete post-reset counter snapshots have an identical frozen trial-sensitive projection and their read timestamps are after cleanup and the log watermark; both full raw snapshots are retained even when broader counters advance;
- trial-scoped deltas are computed against the captured pre-state, never against an assumed boot-global zero;
- runtime policy is empty, all switches are neutral, context/frame depth is zero, and no rule residue is present;
- expected A-arm diagnostic pop-fail is explicitly consumed before the next arm; unexpected pop-fail remains a hard failure;
- acquire/release/outstanding descriptor accounting is balanced;
- parser watermark proves no late event can be attributed to the next trial;
- any missing field, timeout, unstable read, or mismatch returns `RESET_FAIL` and stops execution.
