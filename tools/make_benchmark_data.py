import csv, random, sys
from pathlib import Path
random.seed(7)
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
N_CO, N_TK, N_TC, N_AS, N_TECH = 2000, 300_000, 250_000, 100_000, 60
cos = [(f"C{i:05d}", f"Client {i} Pty Ltd") for i in range(N_CO)]
techs = [(f"U{i:03d}", f"Tech Person {i}") for i in range(N_TECH)]
summ = ["User locked out after MFA reset","VPN packet loss at branch","Veeam backup failed, NAS disk full",
        "Outlook mailbox full","Laptop BSOD after dock","Windows update patch reboot","Printer offline","New starter setup"]
with open(out/"companies.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["company_id","company_name","mrr","stack_cost"])
    for cid,n in cos: w.writerow([cid,n,round(random.uniform(800,12000),2),round(random.uniform(150,3000),2)])
with open(out/"tickets.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["ticket_id","company_id","company_name","tech_id","tech_name","summary","sla_met","status"])
    for i in range(N_TK):
        c=random.choice(cos); t=random.choice(techs)
        w.writerow([f"T{i}",c[0],c[1],t[0],t[1],random.choice(summ),random.random()<0.85,random.choice(["open","closed"])])
with open(out/"time_costs.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["entry_id","company_id","company_name","tech_id","tech_name","hours","hourly_cost","billable"])
    for i in range(N_TC):
        c=random.choice(cos); t=random.choice(techs)
        w.writerow([f"E{i}",c[0],c[1],t[0],t[1],round(random.uniform(0.25,4),2),random.choice([55,62,65,72]),random.random()<0.7])
with open(out/"assets.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["asset_id","company_id","company_name","hostname","os_supported","patch_compliant","warranty_days_left"])
    for i in range(N_AS):
        c=random.choice(cos)
        w.writerow([f"A{i}",c[0],c[1],f"HOST-{i:06d}",random.random()<0.9,random.random()<0.8,random.randint(-400,1200)])
print("records:", N_CO+N_TK+N_TC+N_AS)
