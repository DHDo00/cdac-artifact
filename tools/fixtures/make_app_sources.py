#!/usr/bin/env python3
"""Generate round-39 client sources by adding a per-request observation field
(reqid) to historical R35/R36 sources. API calls, permission sets, modes and
URI paths are NOT changed. Diffs vs references written next to each source."""
import difflib, pathlib

HERE = pathlib.Path(__file__).resolve().parent

def transform(src_path: pathlib.Path, dst_path: pathlib.Path, extra_edits: list):
    text = src_path.read_text()
    orig = text
    anchor = '    private static final String TAG = "CDAC27_PATH";\n'
    assert anchor in text, f"TAG anchor missing in {src_path}"
    text = text.replace(anchor, anchor + '    private String mReqId;\n', 1)
    anchor = 'String cmd = intent.getStringExtra("cmd");\n        if (cmd == null) { finish(); return; }\n'
    assert anchor in text, f"cmd anchor missing in {src_path}"
    insert = ('String cmd = intent.getStringExtra("cmd");\n'
              '        if (cmd == null) { finish(); return; }\n'
              '        mReqId = intent.getStringExtra("reqid");\n'
              '        if (mReqId == null) mReqId = "NORQ";\n'
              '        Log.i(TAG, "REQ reqid=" + mReqId + " pid=" + android.os.Process.myPid()\n'
              '                + " tid=" + android.os.Process.myTid() + " cmd=" + cmd);\n')
    text = text.replace(anchor, insert, 1)
    old = 'Log.i(TAG, "RESULT fail cmd=" + cmd + " err=" + t.getClass().getSimpleName() + ":" + t.getMessage());'
    new = 'Log.i(TAG, "RESULT fail cmd=" + cmd + " reqid=" + mReqId + " err=" + t.getClass().getSimpleName() + ":" + t.getMessage());'
    assert old in text, "fail line missing"
    text = text.replace(old, new, 1)
    # logRead: static method receives reqid parameter; instance callers pass mReqId
    old = 'private static void logRead(String kind, Uri u, ParcelFileDescriptor pfd, String marker) throws Exception {'
    new = 'private static void logRead(String kind, Uri u, ParcelFileDescriptor pfd, String marker, String reqid) throws Exception {'
    assert old in text, "logRead sig missing"
    text = text.replace(old, new, 1)
    old = ('                + " marker=" + marker + " marker_present=" + markerPresent\n'
           '                + " sha256=" + sha256Hex(all));')
    new = ('                + " marker=" + marker + " marker_present=" + markerPresent\n'
           '                + " sha256=" + sha256Hex(all) + " reqid=" + reqid);')
    assert old in text, "logRead log missing"
    text = text.replace(old, new, 1)
    assert 'logRead("CR", u, pfd, marker);' in text
    text = text.replace('logRead("CR", u, pfd, marker);', 'logRead("CR", u, pfd, marker, mReqId);')
    assert 'logRead("CPC", u, pfd, marker);' in text
    text = text.replace('logRead("CPC", u, pfd, marker);', 'logRead("CPC", u, pfd, marker, mReqId);')
    for old, new in extra_edits:
        assert old in text, f"edit missing in {src_path}: {old[:60]}"
        text = text.replace(old, new)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_text(text)
    diff = difflib.unified_diff(orig.splitlines(True), text.splitlines(True),
                                fromfile=f"a/{src_path.name}", tofile=f"b/{dst_path.name}")
    (dst_path.with_name(dst_path.name + ".reqid.diff")).write_text("".join(diff))

APP_A_EDITS = [
    ('Log.i(TAG, "WRITE_MP fail null-pfd uri=" + u);',
     'Log.i(TAG, "WRITE_MP fail null-pfd uri=" + u + " reqid=" + mReqId);'),
    ('+ " written=" + payload.length + " sha256=" + sha256Hex(payload));',
     '+ " written=" + payload.length + " sha256=" + sha256Hex(payload) + " reqid=" + mReqId);'),
    ('Log.i(TAG, "RESTORE_MP fail null-pfd uri=" + u);',
     'Log.i(TAG, "RESTORE_MP fail null-pfd uri=" + u + " reqid=" + mReqId);'),
    ('+ " written=" + orig.length + " sha256=" + sha256Hex(orig));',
     '+ " written=" + orig.length + " sha256=" + sha256Hex(orig) + " reqid=" + mReqId);'),
    ('Log.i(TAG, "WRITE_DIAG fail null-pfd uri=" + u);',
     'Log.i(TAG, "WRITE_DIAG fail null-pfd uri=" + u + " reqid=" + mReqId);'),
    ('+ " written=" + n);',
     '+ " written=" + n + " reqid=" + mReqId);'),
    ('Log.i(TAG, "RESTORE_DIAG fail null-pfd uri=" + u);',
     'Log.i(TAG, "RESTORE_DIAG fail null-pfd uri=" + u + " reqid=" + mReqId);'),
    ('Log.i(TAG, "MAKE_IMAGE fail insert-null name=" + name); return;',
     'Log.i(TAG, "MAKE_IMAGE fail insert-null name=" + name + " reqid=" + mReqId); return;'),
    ('Log.i(TAG, sb.toString());',
     'Log.i(TAG, sb.toString() + " reqid=" + mReqId);'),
    ('+ " data=" + c.getString(2) + " size=" + c.getLong(3) + " is_pending=" + c.getInt(4));\n            c.close();',
     '+ " data=" + c.getString(2) + " size=" + c.getLong(3) + " is_pending=" + c.getInt(4) + " reqid=" + mReqId);\n            c.close();'),
    ('Log.i(TAG, "STATE fail uri=" + u);',
     'Log.i(TAG, "STATE fail uri=" + u + " reqid=" + mReqId);'),
]
APP_B_EDITS = [
    ('Log.i(TAG, "MAKE_IMAGE fail insert-null name=" + name); return;',
     'Log.i(TAG, "MAKE_IMAGE fail insert-null name=" + name + " reqid=" + mReqId); return;'),
    ('Log.i(TAG, sb.toString());',
     'Log.i(TAG, sb.toString() + " reqid=" + mReqId);'),
    ('+ " data=" + c.getString(2) + " size=" + c.getLong(3) + " is_pending=" + c.getInt(4));\n            c.close();',
     '+ " data=" + c.getString(2) + " size=" + c.getLong(3) + " is_pending=" + c.getInt(4) + " reqid=" + mReqId);\n            c.close();'),
    ('Log.i(TAG, "STATE fail uri=" + u);',
     'Log.i(TAG, "STATE fail uri=" + u + " reqid=" + mReqId);'),
]

src_a = HERE / "ref_app_a_r36/src/com/demo/espafdtest/MainActivity.java"
src_b = HERE / "ref_app_b_r35/src/com/demo/espafdtestb/MainActivity.java"
dst_a = HERE / "app_a/src/com/demo/espafdtest/MainActivity.java"
dst_b = HERE / "app_b/src/com/demo/espafdtestb/MainActivity.java"
transform(src_a, dst_a, APP_A_EDITS)
transform(src_b, dst_b, APP_B_EDITS)
print("OK")
