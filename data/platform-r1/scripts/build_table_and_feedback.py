#!/usr/bin/env python3
import csv, os, json, collections
W=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rows=list(csv.DictReader(open(os.path.join(W,'PER_BOOT_SUMMARY.csv'))))
by=collections.defaultdict(list)
for r in rows: by[r['platform']].append(r)
def totals(plat):
    bs=by[plat]
    return dict(boots=len(bs), planned=sum(int(b['planned']) for b in bs), attempted=sum(int(b['attempted']) for b in bs),
                valid=sum(int(b['valid']) for b in bs), deny=sum(int(b['deny_pass']) for b in bs),
                allow=sum(int(b['allow_pass']) for b in bs), fail=sum(int(b['failures']) for b in bs),
                invalid=sum(int(b['invalid']) for b in bs), retries=sum(int(b['retries']) for b in bs))
A=totals('A15'); B=totals('A16'); C=totals('A17')
def row(name, a, b, c): return f"| {name} | {a} | {b} | {c} |"
lines=[]
lines.append("# TABLE_XV_DATA.md — 供用户手工填入 Overleaf 的数据与脚注")
lines.append("")
lines.append("以下为实际核验值（2026-11-02）。表头按截图三列：A15 修正制品 / A16 R35 制品：原批次及重复 / A17 既有制品及重复。")
lines.append("“每 boot 规模”与“全组总量”分行给出；只填实际核验值，未补齐/失败就保留真实结果。")
lines.append("")
lines.append("## 主表（手工填入 Overleaf）")
lines.append("")
lines.append("| 项目 | A15 修正制品 | A16 R35 制品：原批次及重复 | A17 既有制品及重复 |")
lines.append("|---|---|---|---|")
lines.append(row("独立启动数", A['boots'], B['boots'], C['boots']))
lines.append(row("每 boot 正式请求", 30, 30, 30))
lines.append(row("全组正式请求", A['planned'], B['planned'], C['planned']))
lines.append(row("真实拒止", A['deny'], B['deny'], C['deny']))
lines.append(row("允许/恢复", A['allow'], B['allow'], C['allow']))
lines.append("")
lines.append("每版每 boot 明细（PER_BOOT_SUMMARY.csv）：")
for p in ['A15','A16','A17']:
    lines.append(f"- {p}：" + "；".join(f"boot{b['comparison_boot_index']} {b['batch_id']} {b['attempted']}尝试/{b['valid']}有效/{b['deny_pass']}拒+{b['allow_pass']}允许/{b['failures']}失败/{b['invalid']}无效/{b['retries']}重试" for b in by[p]))
lines.append("")
lines.append("## 脚注（必须随表注明）")
lines.append("1. 每版使用同一冻结制品、三个独立启动；A16 列为 R35 冻结制品（原始批次 boot1 + 新增重复 boot2/boot3），")
lines.append("   合计 90 请求不能全写成历史 R35 原有数据；A15 采用修正制品（system.img=70c2ab35…，Binder=859a38a7…），")
lines.append("   新增批次原件单列；A15 旧制品（186ea808…）单列历史、不并入本表。")
lines.append("2. 正式分母不包含空策略预检、装规/读回/撤规、4/301 清理诊断或全局发布计数；静态结论与源码资格不计运行请求。")
lines.append("3. 三版共用 CDAC Linux 6.12.74 A16 谱系内核制品 kernel_openkeychain_dist；A15 原生 6.6 未做 CDAC 回移，")
lines.append("   A17 未做任意内核兼容验证。")
lines.append("4. 只支持 MediaProvider txn14 openFile→6/501 单路线+指定组合的调用者选择性、主体反转、撤规恢复；")
lines.append("   B0–B3 是实验块，不是论文资格条件 B1–B4。")
lines.append("5. 3 boot 是项目重复验证设计，不是统计充分性的通用门槛；9 个 boot 分属三版各自制品，不合并为 270/270。")
open(os.path.join(W,'TABLE_XV_DATA.md'),'w').write('\n'.join(lines)+'\n')
print('\n'.join(lines[:20]))
