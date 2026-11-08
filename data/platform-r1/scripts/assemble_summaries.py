#!/usr/bin/env python3
# Assemble PER_BOOT_SUMMARY.csv, THREE_VERSION_SUMMARY.csv, ARTIFACT_AND_RUNTIME_IDENTITY.csv, TABLE_XV_DATA.md
import csv, json, os, collections
W=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# history boots
hist={
 'A15_1':dict(comparison_boot_index=1,platform='A15',batch_id='A15CLEAN-R1',instance='cvd-8',adb='0.0.0.0:6527',
   boot_id='NOT_RECORDED_historical',fingerprint='…:15/BP1A.250505.005.D1.ced1e38c/…(historical boot)',release='15',sdk='35',
   selinux='Enforcing',kernel='6.12.74-android16-6-maybe-dirty',uidA='10115',uidB='10116',inoX='3358',inoY='3376',sdevX='46',
   planned=30,attempted=30,valid=30,deny_pass=6,allow_pass=24,failures=0,invalid=0,retries=0,
   file_open_deny_final='6',push='41',pop='41',final_policy_count='0',launch_attempts='n/a',stopped='yes(2026-11-01)',
   residual_processes='none(historical stop)',input_images_unchanged='n/a',evidence_gap='historical: boot_id not recorded; per-write scontext not logged'),
 'A16_1':dict(comparison_boot_index=1,platform='A16',batch_id='R35 cvd-35 boot1',instance='cvd-35',adb='0.0.0.0:6554',
   boot_id='NOT_RECORDED_historical',fingerprint='…:16/BP4A.251205.006/eng.test(historical boot)',release='16',sdk='36',
   selinux='Enforcing',kernel='6.12.74-android16-6-maybe-dirty',uidA='10121',uidB='10122',inoX='2931',inoY='2934',sdevX='45',
   planned=30,attempted=30,valid=30,deny_pass=6,allow_pass=24,failures=0,invalid=0,retries=0,
   file_open_deny_final='6',push='35',pop='35',final_policy_count='0',launch_attempts='n/a',stopped='yes(2026-10-29)',
   residual_processes='none(historical stop)',input_images_unchanged='n/a',evidence_gap='historical: boot_id not recorded; per-write scontext not logged'),
 'A17_1':dict(comparison_boot_index=1,platform='A17',batch_id='A17R1 cvd-73 boot1',instance='cvd-73',adb='0.0.0.0:6592',
   boot_id='NOT_RECORDED_historical',fingerprint='…:17/CP2A.260605.016(historical boot)',release='17',sdk='37',
   selinux='Enforcing',kernel='6.12.74-android16-6-maybe-dirty',uidA='10122',uidB='10123',inoX='439',inoY='1533',sdevX='45',
   planned=30,attempted=30,valid=30,deny_pass=6,allow_pass=24,failures=0,invalid=0,retries=0,
   file_open_deny_final='6',push='41',pop='41',final_policy_count='0',launch_attempts='n/a',stopped='yes(2026-10-29)',
   residual_processes='none(historical stop)',input_images_unchanged='n/a',evidence_gap='historical: boot_id not recorded; manifest bookkeeping + 3 unattributed publishes recorded; per-write scontext not logged'),
 'A17_2':dict(comparison_boot_index=2,platform='A17',batch_id='A17R1-B2 cvd-74 boot2',instance='cvd-74',adb='0.0.0.0:6593',
   boot_id='86a4d79b-7725-4fe6-ae5e-1e6ad0771570',fingerprint='…:17/CP2A.260605.016(historical boot)',release='17',sdk='37',
   selinux='Enforcing',kernel='6.12.74-android16-6-maybe-dirty',uidA='10122',uidB='10123',inoX='3546',inoY='3571',sdevX='45',
   planned=30,attempted=30,valid=30,deny_pass=6,allow_pass=24,failures=0,invalid=0,retries=0,
   file_open_deny_final='6',push='43',pop='43',final_policy_count='0',launch_attempts='n/a',stopped='yes(2026-10-29)',
   residual_processes='none(historical stop)',input_images_unchanged='n/a',evidence_gap='historical: preflight debugfs-after-root order bug preserved; per-write scontext not logged'),
}
boots=[]
for k,v in hist.items(): boots.append(v)
for tag in ['a15_boot2','a15_boot3','a16_boot2','a16_boot3','a17_boot3']:
    p=os.path.join(W,'runs',tag,'boot_summary.json')
    if os.path.exists(p):
        s=json.load(open(p)); boots.append(s)
print('boot summaries found:', len(boots))
for b in boots: print(b.get('platform'), b.get('comparison_boot_index'), b.get('batch_id'))
# PER_BOOT_SUMMARY
cols=['comparison_boot_index','platform','batch_id','instance','adb','boot_id','artifact_set','planned','attempted','valid','deny_pass','allow_pass','failures','invalid','retries','file_open_deny_final','push','pop','final_policy_count','launch_attempts_failed','stopped','residual_processes','input_images_unchanged','evidence_gap']
artifacts={'A15':'fixed A15 system.img=70c2ab35… super=36ae6e22… + kernel_openkeychain_dist','A16':'C19_media system.img=009b68dc… super=55f51a09… + kernel_openkeychain_dist','A17':'A17 system.img=ce6dc748… super=24d98b2a… + kernel_openkeychain_dist'}
with open('PER_BOOT_SUMMARY.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore'); w.writeheader()
    for b in sorted(boots,key=lambda x:(['A15','A16','A17'].index(x['platform']),int(x['comparison_boot_index']))):
        b['artifact_set']=artifacts[b['platform']]
        w.writerow(b)
print('PER_BOOT_SUMMARY.csv written')
# THREE_VERSION_SUMMARY
with open('THREE_VERSION_SUMMARY.csv','w',newline='') as f:
    w=csv.writer(f)
    w.writerow(['platform','artifact','comparison_boot_indices','batches_included','total_planned','total_attempted','total_valid','total_deny_pass','total_allow_pass','total_failures','total_invalid','total_retries','note'])
    for plat in ['A15','A16','A17']:
        bs=[b for b in boots if b['platform']==plat]
        bs.sort(key=lambda x:int(x['comparison_boot_index']))
        n=len(bs); tp=sum(int(b['planned']) for b in bs); ta=sum(int(b['attempted']) for b in bs); tv=sum(int(b['valid']) for b in bs)
        td=sum(int(b['deny_pass']) for b in bs); tal=sum(int(b['allow_pass']) for b in bs)
        tf=sum(int(b['failures']) for b in bs); ti=sum(int(b['invalid']) for b in bs); tr=sum(int(b['retries']) for b in bs)
        note='' if plat!='A16' else 'R35 frozen artifact: original batch (boot1) + new replications (boot2/3)'
        w.writerow([plat,artifacts[plat],','.join(str(b['comparison_boot_index']) for b in bs),','.join(b['batch_id'] for b in bs),tp,ta,tv,td,tal,tf,ti,tr,note])
print('THREE_VERSION_SUMMARY.csv written')
# ARTIFACT_AND_RUNTIME_IDENTITY
with open('ARTIFACT_AND_RUNTIME_IDENTITY.csv','w',newline='') as f:
    w=csv.writer(f)
    w.writerow(['comparison_boot_index','platform','batch_id','instance','adb','boot_id','fingerprint','release','sdk','kernel','selinux','uidA','uidB','inoX','inoY','sdevX','system_img_sha256','super_img_sha256','kernel_bzImage_sha256','kernel_initramfs_sha256','host_cvd_internal_start_sha256','app_a_sha256','app_b_sha256','iguardctl_sha256','source_of_values'])
    hashes={'A15':['70c2ab3567d6b485fd548f214cbdf36931894b12d3376628e6279b86de9b8244','36ae6e22570c50591dd83a0e81ed55978cd574ca8614a30f1ce4562c8e19e4b3','595c988e9ad075d60b8525d740485e7022afc54b4d9943db568cad132e78cf9f'],
            'A16':['009b68dc765c460e08daf39dcadf288667fab8714a0499ad95cb35bd35fd5a48','55f51a092a2ff2161a95f10ff3c900f6441144d8b3da1262682f8c423acf3838','2021b5e8efc755fc6826b050e075bac2949e3538040d32655a210a1fae27e60a'],
            'A17':['ce6dc7489f3fbbf44f259ac30e78a689de5723f21b416aee69cd516e699bbff4','24d98b2a45e8f6488dd35426335afb457ad50a621aa778d5d33d884655e70090','81216ac57c0c16c5aa323c4c85fcecddd1c0d82c268bbdc872ca761ba7c92fd8']}
    kbz='0c0f7e4cde1ac2e4745737f271eb4d3434c5b09e4fc2ed5cafcdc2d5e20a653b'; kini='0fa2d5599d311e7d4790f238efd0fd1536b12b27be55ea67ad6214f9ed2aa992'
    for b in sorted(boots,key=lambda x:(['A15','A16','A17'].index(x['platform']),int(x['comparison_boot_index']))):
        h=hashes[b['platform']]
        w.writerow([b['comparison_boot_index'],b['platform'],b['batch_id'],b['instance'],b['adb'],b['boot_id'],b['fingerprint'],b['release'],b['sdk'],b['kernel'],b['selinux'],b['uidA'],b['uidB'],b['inoX'],b['inoY'],b['sdevX'],h[0],h[1],kbz,kini,h[2],'b2c52635e15d60aab650adfc208c7080d4f283490e4f725378f3d6350d7e2a69','f2d4da7311aa59bc5796d266ac80d79036dfde61c12f11f39876d0ea81592818','493e8e80db4598d669509482f20deb7a7d2ce3d31d983211dd4cbbdc049d7b08',('historical ledger' if b['batch_id'] in ('A15CLEAN-R1','R35 cvd-35 boot1','A17R1 cvd-73 boot1','A17R1-B2 cvd-74 boot2') else 'this round preflight/matrix')])
print('ARTIFACT_AND_RUNTIME_IDENTITY.csv written')
