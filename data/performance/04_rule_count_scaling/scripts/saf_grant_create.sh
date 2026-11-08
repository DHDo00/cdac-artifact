#!/usr/bin/env bash
# saf_grant_create.sh <pkg> <activity> <folder> — create folder & grant (port 6540)
set -u
ADB=adb; S=0.0.0.0:6540
PKG=$1; ACT=$2; FOLDER=$3
$ADB -s $S shell 'wm dismiss-keyguard' >/dev/null 2>&1
$ADB -s $S shell "am start -n $ACT --ez saf_tree true" >/dev/null 2>&1
sleep 6
$ADB -s $S shell 'input tap 1016 536'; sleep 2
$ADB -s $S shell "input tap 640 264; input text $FOLDER; input keyevent 111"; sleep 1
$ADB -s $S shell 'input tap 864 636'; sleep 3
$ADB -s $S shell 'input tap 640 880'; sleep 3
$ADB -s $S shell 'input tap 948 607'; sleep 6
$ADB -s $S shell "run-as $PKG cat files/grants.txt" 2>&1
