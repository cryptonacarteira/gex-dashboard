import os
import subprocess
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from scipy.stats import norm
import plotly.graph_objs as go

def processar_gex_e_enviar():
    filename = 'spx_quotedata.csv'
    
    if not os.path.exists(filename):
        print(f"Erro: O arquivo {filename} não foi encontrado na pasta.")
        return

    # 1. Leitura e processamento dos dados do arquivo de opções
    optionsFile = open(filename, encoding='utf-8', errors='ignore')
    optionsFileData = optionsFile.readlines()
    optionsFile.close()

    spotLine = optionsFileData[1]
    spotPrice = float(spotLine.split('Last:')[1].split(',')[0])
    fromStrike = 0.8 * spotPrice
    toStrike = 1.2 * spotPrice

    # Carrega o DataFrame ignorando o cabeçalho original do CBOE
    df = pd.read_csv(filename, sep=",", header=None, skiprows=4)
    df.columns = [
        'ExpirationDate','Calls','CallLastSale','CallNet','CallBid','CallAsk','CallVol',
        'CallIV','CallDelta','CallGamma','CallOpenInt','StrikePrice','Puts','PutLastSale',
        'PutNet','PutBid','PutAsk','PutVol','PutIV','PutDelta','PutGamma','PutOpenInt'
    ]

    df['ExpirationDate'] = pd.to_datetime(df['ExpirationDate'], format='%a %b %d %Y', errors='coerce')
    df['ExpirationDate'] = df['ExpirationDate'] + timedelta(hours=16)
    
    # Converte colunas numéricas com segurança
    colunas_numericas = ['StrikePrice', 'CallIV', 'PutIV', 'CallGamma', 'PutGamma', 'CallOpenInt', 'PutOpenInt']
    for col in colunas_numericas:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df = df.dropna(subset=['StrikePrice', 'CallGamma', 'PutGamma', 'CallOpenInt', 'PutOpenInt'])

    # 2. Cálculo do Gamma Exposure (GEX)
    df['CallGEX'] = df['CallGamma'] * df['CallOpenInt'] * 100 * spotPrice * spotPrice * 0.01
    df['PutGEX'] = df['PutGamma'] * df['PutOpenInt'] * 100 * spotPrice * spotPrice * 0.01 * -1
    df['TotalGamma'] = (df['CallGEX'] + df['PutGEX']) / 10**9

    dfAgg = df.groupby(['StrikePrice'])[['CallGEX', 'PutGEX', 'TotalGamma']].sum()
    strikes = dfAgg.index.values
    x_data = strikes
    y_data = dfAgg['TotalGamma'].to_numpy()

    # 3. Criação do Gráfico com Plotly
    fig = go.Figure(
        go.Bar(
            x=x_data,
            y=y_data,
            width=6,
            marker_color='rgb(26, 118, 255)',
            marker_line_color='black',
            marker_line_width=0.15,
            name='Gamma Exposure'
        )
    )

    fig.add_shape(
        type='line',
        x0=spotPrice,
        y0=min(y_data) if len(y_data) > 0 else 0,
        x1=spotPrice,
        y1=max(y_data) if len(y_data) > 0 else 1,
        line=dict(color='red', width=2, dash='dash')
    )

    total_gamma_sum = df['TotalGamma'].sum()
    fig.update_layout(
        title={
            'text': f"Total Gamma: ${total_gamma_sum:,.2f} Bn per 1% SPX Move",
            'font': {'size': 20, 'family': 'Arial Black'}
        },
        xaxis_title='Strike',
        yaxis_title='Spot Gamma Exposure ($ billions/1% move)',
        xaxis=dict(range=[fromStrike, toStrike]),
        yaxis=dict(tickformat='$,.2f'),
        plot_bgcolor='white',
        font=dict(family='Arial', size=12, color='black'),
        width=1750,
        height=800
    )

    # Salva o dashboard interativo atualizado em HTML na pasta
    output_html = "dashboard_gex.html"
    fig.write_html(output_html)
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] Gráfico GEX atualizado e salvo em {output_html}")

    # Em modo CI (GitHub Actions), o commit/push é feito pelo workflow
    if os.environ.get('GEX_SKIP_GIT') == '1':
        print("Modo CI: commit/push delegado ao workflow do GitHub.")
        return

    # 4. Envio automático para o GitHub (modo local)
    try:
        subprocess.run(["git", "add", output_html], check=True)
        if os.path.exists("spx_quotedata.csv"):
            subprocess.run(["git", "add", "spx_quotedata.csv"], check=True)
            
        commit_msg = f"Auto update GEX dashboard: {timestamp}"
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        subprocess.run(["git", "push"], check=True)
        print("Push do Dashboard GEX para o GitHub realizado com sucesso!")
        
    except subprocess.CalledProcessError as e:
        print(f"Aviso do Git (sem alterações novas para commitar): {e}")

if __name__ == "__main__":
    processar_gex_e_enviar()