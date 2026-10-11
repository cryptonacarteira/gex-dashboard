import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from gex import carregar_df

MERCADOS = [
    ("SPX", "spx_quotedata.csv"),
    ("NDX", "ndx_quotedata.csv"),
    ("QQQ", "qqq_quotedata.csv"),
    ("EWZ", "ewz_quotedata.csv"),
    ("SPY", "spy_quotedata.csv"),
    ("IWM", "iwm_quotedata.csv"),
    ("VIX", "vix_quotedata.csv"),
]

PASTA_HISTORICO = "historico"

REGIOES = [
    ("Gex 1", 0.90),
    ("Gex 2", 0.95),
    ("Gex 3", 0.98),
    ("Gex 4", 0.995),
    ("Gex 5", 1.005),
    ("Gex 6", 1.02),
    ("Gex 7", 1.05),
    ("Gex 8", 1.10),
    ("Gex 9", 1.20),
]

NOMES_REGIOES = [nome for nome, _ in REGIOES] + ["Gex 10"]


def regiao(strike, spot):
    pct = strike / spot
    for nome, limite in REGIOES:
        if pct < limite:
            return nome
    return "Gex 10"


def computar(df, spot):
    calls = df[df['CallGEX'] != 0].groupby('StrikePrice')['CallGEX'].sum() / 10**9
    puts = df[df['PutGEX'] != 0].groupby('StrikePrice')['PutGEX'].sum() / 10**9
    total = (df.groupby('StrikePrice')[['CallGEX', 'PutGEX']].sum().sum(axis=1)) / 10**9
    idx = calls.index.union(puts.index).union(total.index).sort_values()
    return calls.reindex(idx).fillna(0.0), puts.reindex(idx).fillna(0.0), total.reindex(idx).fillna(0.0)


def main():
    agora = datetime.now()
    os.makedirs(PASTA_HISTORICO, exist_ok=True)

    path_gex_total = os.path.join(PASTA_HISTORICO, 'GexTotal.csv')
    path_gex_tabela = os.path.join(PASTA_HISTORICO, 'GexTabela.csv')
    path_teste = os.path.join(PASTA_HISTORICO, 'teste.csv')
    path_range = os.path.join(PASTA_HISTORICO, 'RangeIV.csv')
    path_calendario = os.path.join(PASTA_HISTORICO, 'Calendario.csv')

    col_gex_total = ['Data', 'Ativo', 'Strike', 'Call', 'Put', 'Total']
    col_gex_tabela = ['Data', 'Ativo', 'Strike', 'Gex', 'GEX Total (Bn)']
    col_teste = ['Data', 'Ativo', 'Spot', 'Put Wall', 'Call Wall', 'Gamma Flip'] + NOMES_REGIOES + ['Call', 'Put', 'Gex Total (Bn)', 'IV Medio']
    col_range = ['Data', 'Ativo', 'IV Medio', 'IV Max-Min', 'Range %']
    col_calendario = ['Date', 'Dia', 'Mes', 'Ano', 'Call Dia Anterior', 'DesvKEY']

    def carregar_historico(path, colunas):
        if os.path.exists(path):
            df = pd.read_csv(path, encoding='utf-8', sep=';', decimal=',')
            for c in colunas:
                if c not in df.columns:
                    df[c] = np.nan
            return df[colunas]
        return pd.DataFrame(columns=colunas)

    def mesclar(path, colunas, novo, chaves):
        existente = carregar_historico(path, colunas)
        df = pd.concat([existente, novo], ignore_index=True)
        df['Data'] = pd.to_datetime(df['Data'], errors='coerce').dt.strftime('%Y-%m-%d')
        chave = df[chaves].astype(str).agg('|'.join, axis=1)
        df = df.assign(_k=chave).drop_duplicates(subset='_k', keep='last').drop(columns='_k')
        for c in df.columns:
            if c not in chaves and c != 'Gex':
                df[c] = pd.to_numeric(df[c], errors='coerce')
        if 'Strike' in df.columns:
            df['Strike'] = pd.to_numeric(df['Strike'], errors='coerce')
        df = df.sort_values(chaves).reset_index(drop=True)
        df.to_csv(path, index=False, encoding='utf-8', sep=';', decimal=',', float_format='%.8f')
        return df

    gex_total_hoje = []
    gex_tabela_hoje = []
    teste_hoje = []
    range_hoje = []

    for nome, csv_file in MERCADOS:
        if not os.path.exists(csv_file):
            print(f"Erro: O arquivo {csv_file} não foi encontrado na pasta.")
            continue
        df, spot = carregar_df(csv_file)
        df['CallGEX'] = df['CallGamma'] * df['CallOpenInt'] * 100 * spot * spot * 0.01
        df['PutGEX'] = df['PutGamma'] * df['PutOpenInt'] * 100 * spot * spot * 0.01 * -1
        df = df[(df['CallGEX'] != 0) | (df['PutGEX'] != 0)]

        calls, puts, total = computar(df, spot)
        data = pd.Timestamp(agora.date()).normalize().date()

        for s in total.index:
            gex_total_hoje.append([data, nome, float(s), float(calls.loc[s]), float(puts.loc[s]), float(total.loc[s])])
            gex_tabela_hoje.append([data, nome, float(s), regiao(s, spot), float(total.loc[s])])

        put_wall = float(puts.idxmin())
        call_wall = float(calls.idxmax())
        flip = None
        for i in range(len(total) - 1):
            a = total.iloc[i]
            b = total.iloc[i + 1]
            if (a <= 0) != (b <= 0) and a != b:
                s0 = total.index[i]
                s1 = total.index[i + 1]
                nv = s0 + (s1 - s0) * (-a) / (b - a)
                if flip is None or abs(nv - spot) < abs(flip - spot):
                    flip = nv

        gex_por_regiao = {reg: 0.0 for reg in NOMES_REGIOES}
        for s in total.index:
            gex_por_regiao[regiao(s, spot)] += float(total.loc[s])

        linha = [data, nome, float(spot), put_wall, call_wall, flip if flip is not None else np.nan]
        linha += [gex_por_regiao[reg] for reg in NOMES_REGIOES]
        linha += [float(calls.sum()), float(puts.sum()), float(total.sum())]

        iv_ok = df[(df['CallIV'].notna() & (df['CallIV'] > 0)) | (df['PutIV'].notna() & (df['PutIV'] > 0))]
        iv_medio = np.nan
        iv_max_min = np.nan
        range_pct = np.nan
        if len(iv_ok) > 0:
            serie_iv = pd.concat([
                iv_ok.loc[iv_ok['CallIV'] > 0, 'CallIV'],
                iv_ok.loc[iv_ok['PutIV'] > 0, 'PutIV'],
            ])
            serie_iv = serie_iv[serie_iv.notna() & (serie_iv > 0)]
            if len(serie_iv) > 0:
                iv_medio = float(serie_iv.mean())
                iv_max_min = float(serie_iv.max() - serie_iv.min())
                range_pct = float((serie_iv.max() - serie_iv.min()) / serie_iv.mean() * 100)
        linha.append(iv_medio)

        teste_hoje.append(linha)
        range_hoje.append([data, nome, iv_medio, iv_max_min, range_pct])
        print(f"  {nome}: spot={spot:,.2f} GEX total=${total.sum():,.2f}Bn put_wall={put_wall:,.0f} call_wall={call_wall:,.0f}")

    if not teste_hoje:
        print("Nenhum dado disponível.")
        return

    mesclar(path_gex_total, col_gex_total, pd.DataFrame(gex_total_hoje, columns=col_gex_total), ['Data', 'Ativo', 'Strike'])
    mesclar(path_gex_tabela, col_gex_tabela, pd.DataFrame(gex_tabela_hoje, columns=col_gex_tabela), ['Data', 'Ativo', 'Strike'])
    teste_final = mesclar(path_teste, col_teste, pd.DataFrame(teste_hoje, columns=col_teste), ['Data', 'Ativo'])
    mesclar(path_range, col_range, pd.DataFrame(range_hoje, columns=col_range), ['Data', 'Ativo'])

    calendario_lista = []
    datas = sorted(teste_final['Data'].astype(str).unique())
    primeira_data = pd.Timestamp(datas[0]).date()
    for d in datas:
        ts = pd.Timestamp(d).date()
        dia_anterior = ts - timedelta(days=1)
        while dia_anterior.isoformat() not in datas and dia_anterior >= primeira_data:
            dia_anterior -= timedelta(days=1)
        call_ant = np.nan
        if dia_anterior.isoformat() in datas:
            call_ant = float(teste_final[teste_final['Data'].astype(str) == dia_anterior.isoformat()]['Call'].sum())
        rows_d = teste_final[teste_final['Data'].astype(str) == d]
        desv = rows_d['Gamma Flip'].astype(float).notna()
        desv_key = np.nan
        if desv.any():
            f = rows_d.loc[desv, 'Gamma Flip'].astype(float)
            sp = rows_d.loc[desv, 'Spot'].astype(float)
            desv_key = float((np.abs(sp - f) / f * 100).mean())
        calendario_lista.append([ts, ts.day, ts.month, ts.year, call_ant, desv_key])

    pd.DataFrame(calendario_lista, columns=col_calendario).to_csv(path_calendario, index=False, encoding='utf-8', sep=';', decimal=',', float_format='%.8f')

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] Histórico atualizado em {PASTA_HISTORICO}/")
    for nome_arq in ['GexTotal.csv', 'GexTabela.csv', 'teste.csv', 'RangeIV.csv', 'Calendario.csv']:
        p = os.path.join(PASTA_HISTORICO, nome_arq)
        print(f"  {nome_arq}: {os.path.getsize(p):,} bytes - {sum(1 for _ in open(p, encoding='utf-8'))} linhas")


if __name__ == '__main__':
    main()