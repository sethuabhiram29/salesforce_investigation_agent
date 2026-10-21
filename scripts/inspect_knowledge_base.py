import pandas as pd

df_sop = pd.read_excel('data/sop_scenarios_selected_sheets.xlsx', sheet_name='sop_scenarios')
print(f"TOTAL SOPS IN KNOWLEDGE BASE EXCEL: {len(df_sop)}")
for idx, r in df_sop.iterrows():
    print(f"[{r['id']}] Domain: {r['domain']}")
    print(f"  Title/Description: {r['description']}")
    print(f"  Prerequisites: {r.get('prerequisites', 'N/A')}")
    print("-" * 50)

print("\n=== INVESTIGATION.CSV SCENARIOS ===")
df_inv = pd.read_csv('data/investigation.csv')
for dom, grp in df_inv.groupby('domain'):
    print(f"=== Domain: {dom} ===")
    scenarios = grp[['scenario_id', 'scenario_name', 'skill_id']].drop_duplicates()
    for _, s in scenarios.iterrows():
        print(f"  {s['scenario_id']} ({s['skill_id']}): {s['scenario_name']}")
