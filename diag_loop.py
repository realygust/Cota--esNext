import pandas as pd
df = pd.DataFrame([{'Qtd': 2.0, 'Alt (cm)': 22.0, 'Larg (cm)': 22.0, 'Comp (cm)': 13.0, 'Peso Total (kg)': 43.0}])
total_volumes_qtd = 0
peso_real_total = 0.0
volume_total_m3 = 0.0
for _, row in df.iterrows():
    try:
        raw_qtd = row.get('Qtd')
        q = int(float(raw_qtd)) if pd.notna(raw_qtd) and str(raw_qtd).strip() != '' else 0
        if q == 0 or pd.isna(q): continue
        raw_alt = row.get('Alt (cm)')
        a = float(raw_alt) if pd.notna(raw_alt) and str(raw_alt).strip() != '' else 0.0
        raw_larg = row.get('Larg (cm)')
        l = float(raw_larg) if pd.notna(raw_larg) and str(raw_larg).strip() != '' else 0.0
        raw_comp = row.get('Comp (cm)')
        c = float(raw_comp) if pd.notna(raw_comp) and str(raw_comp).strip() != '' else 0.0
        raw_peso = row.get('Peso Total (kg)')
        pu = float(raw_peso) if pd.notna(raw_peso) and str(raw_peso).strip() != '' else 0.0
        total_volumes_qtd += q
        peso_real_total += pu
        volume_total_m3 += (q * (a * l * c)) / 1000000.0
    except Exception as e: print(e)
print(f'total_volumes_qtd: {total_volumes_qtd}')
print(f'peso_real_total: {peso_real_total}')
print(f'volume_total_m3: {volume_total_m3}')
