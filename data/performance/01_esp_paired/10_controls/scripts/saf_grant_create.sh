#!/usr/bin/env bash
# saf_grant_create.sh <pkg> <activity> <new_folder> — CREATE new folder in SAF picker
# and grant it (used for first app per tree).
set -u
ADB=adb; S=0.0.0.0:6528
PKG=$1; ACT=$2; FOLDER=$3
$ADB -s $S shell 'wm dismiss-keyguard' >/dev/null 2>&1
$ADB -s $S shell "am start -n $ACT --ez saf_tree true" >/dev/null 2>&1
sleep 6
$ADB -s $S shell 'input tap 1016 536'; sleep 2          # CREATE NEW FOLDER
$ADB -s $S shell "input tap 640 264; input text $FOLDER; input keyevent 111"; sleep 1
$ADB -s $S shell 'input tap 864 636'; sleep 3           # OK
$ADB -s $S shell 'input tap 640 880'; sleep 3           # USE THIS FOLDER
$ADB -s $S shell 'input tap 948 607'; sleep 6           # ALLOW
$ADB -s $S shell "run-as $PKG cat files/grants.txt" 2>&1
