import csv, random
random.seed(42)
clients = [  # id, name, mrr, stack, monthly hours, tech-hours skew
 ("C01","Harbour Legal Group",5200,1150,38),
 ("C02","Bayside Logistics Pty Ltd",2400,680,61),
 ("C03","Canberra MedTech Clinic",6800,1420,44),
 ("C04","Southern Cross Accounting",3900,820,22),
 ("C05","Ironbark Builders",1850,540,47),
 ("C06","Molonglo Dental Studio",2900,610,19),
 ("C07","Kestrel Freight Co",4100,1240,72),
 ("C08","Wattle Grove Aged Care",7400,1980,58),
]
techs=[("U01","Liam Vance",65),("U02","Maya Lin",62),("U03","Priya Nair",72),("U04","Tom Okafor",58)]
notes=["User locked out of M365 after MFA reset","Site-to-site VPN packet loss","Veeam backup failed, NAS disk full",
"Outlook mailbox not syncing","Laptop BSOD after dock firmware","Windows Update patch reboot loop","Printer offline on level 2",
"Phishing email reported by staff","Firewall rule change for new supplier portal","DNS resolution failing at branch",
"New starter onboarding","Teams calls dropping","RAID degraded on file server","Password reset request"]
with open("drop/companies.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["company_id","company_name","mrr","stack_cost"])
    for c in clients: w.writerow([c[0],c[1],c[2],c[3]])
tk=open("drop/tickets.csv","w",newline=""); tw=csv.writer(tk); tw.writerow(["ticket_id","company_id","company_name","tech_id","tech_name","summary","sla_met","status"])
tc=open("drop/time_costs.csv","w",newline=""); cw=csv.writer(tc); cw.writerow(["entry_id","company_id","company_name","tech_id","tech_name","hours","hourly_cost","billable"])
n=e=0
for cid,name,mrr,stack,hrs in clients:
    left=hrs
    while left>0:
        t=random.choice(techs); h=min(left,round(random.uniform(0.5,3.5),1)); left=round(left-h,1)
        cw.writerow([f"E{e:04d}",cid,name,t[0],t[1],h,t[2],random.random()<0.75]); e+=1
        if random.random()<0.6:
            sla = random.random() < (0.97 if hrs<40 else 0.78)
            tw.writerow([f"T{n:04d}",cid,name,t[0],t[1],random.choice(notes),sla,random.choice(["open","closed","closed"])]); n+=1
with open("drop/assets.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["asset_id","company_id","company_name","hostname","os_supported","patch_compliant","warranty_days_left"])
    a=0
    for cid,name,*_ in clients:
        pre="".join(x[0] for x in name.split()[:3]).upper()
        for i in range(random.randint(8,22)):
            w.writerow([f"A{a:04d}",cid,name,f"{pre}-PC-{i:02d}",random.random()<0.9,random.random()<0.82,random.randint(-300,900)]); a+=1
print(n,"tickets",e,"time entries",a,"assets")
