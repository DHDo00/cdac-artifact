#!/usr/bin/env bash
# saf_grant_existing.sh <pkg> <activity> <folder> — grant an EXISTING primary folder
# to an app through DocumentsUI (dynamic UI-dump navigation).
set -u
ADB=adb; S=0.0.0.0:6528
PKG=$1; ACT=$2; FOLDER=$3
ui() { $ADB -s $S shell 'uiautomator dump /sdcard/ui.xml >/dev/null 2>&1; cat /sdcard/ui.xml'; }
find_center() { # find_center <text> -> "x y"
  ui | python3 -c "
import sys,re
target='$FOLDER'
x=sys.stdin.read()
best=None
for m in re.finditer(r'text=\"([^\"]*)\"[^>]*?bounds=\"\[(\d+),(\d+)\]\[(\d+),(\d+)\]\"',x):
    t,a,b,c,d=m.groups()
    if t.strip()==target:
        best=((int(a)+int(c))//2,(int(b)+int(d))//2)
        break
print('%s %s'%best if best else '')
"
}
$ADB -s $S shell 'wm dismiss-keyguard' >/dev/null 2>&1
$ADB -s $S shell "am start -n $ACT --ez saf_tree true" >/dev/null 2>&1
sleep 6
found=""
for sw in 1 2 3 4 5 6; do
  C=$(find_center)
  if [ -n "$C" ]; then
    y=${C##* }
    if [ "$y" -lt 780 ]; then found=$C; break; fi
  fi
  $ADB -s $S shell 'input swipe 540 780 540 300 400' >/dev/null 2>&1
  sleep 2
done
if [ -z "$found" ]; then echo "FOLDER_NOT_FOUND_OR_NOT_SCROLLABLE $FOLDER"; exit 1; fi
# tap folder name (navigates into it in the tree picker)
$ADB -s $S shell "input tap $found" >/dev/null 2>&1; sleep 3
# inside folder -> USE THIS FOLDER
UC=$(ui | python3 -c "
import sys,re
x=sys.stdin.read()
for m in re.finditer(r'text=\"USE THIS FOLDER\"[^>]*?bounds=\"\[(\d+),(\d+)\]\[(\d+),(\d+)\]\"',x):
    a,b,c,d=map(int,m.groups()); print((a+c)//2,(b+d)//2); break
")
$ADB -s $S shell "input tap $UC" >/dev/null 2>&1; sleep 3
AC=$(ui | python3 -c "
import sys,re
x=sys.stdin.read()
for m in re.finditer(r'text=\"ALLOW\"[^>]*?bounds=\"\[(\d+),(\d+)\]\[(\d+),(\d+)\]\"',x):
    a,b,c,d=map(int,m.groups()); print((a+c)//2,(b+d)//2); break
")
$ADB -s $S shell "input tap $AC" >/dev/null 2>&1; sleep 6
$ADB -s $S shell "run-as $PKG cat files/grants.txt" 2>&1
