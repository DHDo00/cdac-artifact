#!/usr/bin/env python3
# Independent re-derivation of per-request verdicts from raw app/framework evidence.
import os, re, csv, glob
boots=['a15_boot2','a15_boot3','a16_boot2','a16_boot3','a17_boot3']
deny={'B1_AX','B2_BX'}
allok=True
for b in boots:
    d=f'runs/{b}/matrix'
    mism=[]
    ok_deny=ok_allow=0
    for labfile in sorted(glob.glob(f'{d}/B*_app.txt')):
        lab=os.path.basename(labfile)[:-8]
        pref=re.sub(r'_\d+$','',lab)
        app=open(labfile,errors='replace').read()
        fw=open(f'{d}/{lab}_framework.txt',errors='replace').read()
        app_fail='RESULT fail' in app and 'EACCES' in app
        app_ok='READ_CPC ok' in app
        dec_match=('matched=1' in fw) and (bool(re.search(r'reason=(a15cdac_r14a|a15cdac_rev|cdac35_r14a|cdac35_rev)',fw)))
        enf_deny=('-13' in fw) and ('deny-now' in fw)
        if pref in deny:
            good = app_fail and dec_match and enf_deny and (not app_ok)
            if good: ok_deny+=1
            else: mism.append(lab)
        else:
            good = app_ok and (not app_fail) and (not enf_deny)
            if good: ok_allow+=1
            else: mism.append(lab)
    status='PASS' if (ok_deny==6 and ok_allow==24 and not mism) else 'FAIL'
    if status=='FAIL': allok=False
    print(f'{b}: deny={ok_deny}/6 allow={ok_allow}/24 mismatches={mism} -> {status}')
print('INDEPENDENT_RECHECK=', 'PASS' if allok else 'FAIL')
