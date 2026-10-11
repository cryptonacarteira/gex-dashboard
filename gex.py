import os
import subprocess
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from plotly.subplots import make_subplots
import plotly.graph_objs as go

MERCADOS = [
    ("SPX", "spx_quotedata.csv"),
    ("NDX", "ndx_quotedata.csv"),
    ("QQQ", "qqq_quotedata.csv"),
]


def ler_mercado(filename):
    with open(filename, encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    spotPrice = float(lines[1].split('Last:')[1].split(',')[0])

    df = pd.read_csv(filename, sep=",", header=None, skiprows=4)
    df.columns = [
        'ExpirationDate', 'Calls', 'CallLastSale', 'CallNet', 'CallBid', 'CallAsk', 'CallVol',
        'CallIV', 'CallDelta', 'CallGamma', 'CallOpenInt', 'StrikePrice', 'Puts', 'PutLastSale',
        'PutNet', 'PutBid', 'PutAsk', 'PutVol', 'PutIV', 'PutDelta', 'PutGamma', 'PutOpenInt'
    ]

    df['ExpirationDate'] = pd.to_datetime(df['ExpirationDate'], format='%a %b %d %Y', errors='coerce')
    df['ExpirationDate'] = df['ExpirationDate'] + timedelta(hours=16)

    colunas_numericas = ['StrikePrice', 'CallIV', 'PutIV', 'CallGamma', 'PutGamma', 'CallOpenInt', 'PutOpenInt']
    for col in colunas_numericas:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df = df.dropna(subset=['StrikePrice', 'CallGamma', 'PutGamma', 'CallOpenInt', 'PutOpenInt'])

    df['CallGEX'] = df['CallGamma'] * df['CallOpenInt'] * 100 * spotPrice * spotPrice * 0.01
    df['PutGEX'] = df['PutGamma'] * df['PutOpenInt'] * 100 * spotPrice * spotPrice * 0.01 * -1
    df['TotalGamma'] = (df['CallGEX'] + df['PutGEX']) / 10**9

    dfAgg = df.groupby(['StrikePrice'])[['CallGEX', 'PutGEX', 'TotalGamma']].sum().sort_index()
    strikes = dfAgg.index.values
    call_wall = dfAgg['CallGEX'].to_numpy() / 10**9
    put_wall = dfAgg['PutGEX'].to_numpy() / 10**9
    net_gex = dfAgg['TotalGamma'].to_numpy()
    total_gamma = df['TotalGamma'].sum()

    # Gamma Flip: strike onde o GEX líquido cruza o zero, mais próximo do spot
    flip = None
    for i in range(len(net_gex) - 1):
        a = net_gex[i]
        b = net_gex[i + 1]
        if (a <= 0) != (b <= 0) and a != b:
            level = strikes[i] + (strikes[i + 1] - strikes[i]) * (-a) / (b - a)
            if flip is None or abs(level - spotPrice) < abs(flip - spotPrice):
                flip = level

    return spotPrice, strikes, call_wall, put_wall, net_gex, flip, total_gamma


def adicionar_painel(fig, row, nome, spotPrice, strikes, call_wall, put_wall, net_gex, flip):
    ymin = min(net_gex.min(), put_wall.min())
    ymax = max(net_gex.max(), call_wall.max())

    fig.add_trace(
        go.Bar(
            x=strikes, y=call_wall, width=6,
            marker_color='rgb(38, 166, 91)',
            marker_line_color='black', marker_line_width=0.15,
            opacity=0.55,
            name=f'{nome} Call Wall',
            hovertemplate=f'{nome} %{{x:,.0f}}<br>Call Wall: %{{y:$,.3f}}<extra></extra>'
        ), row=row, col=1
    )
    fig.add_trace(
        go.Bar(
            x=strikes, y=put_wall, width=6,
            marker_color='rgb(255, 82, 82)',
            marker_line_color='black', marker_line_width=0.15,
            opacity=0.55,
            name=f'{nome} Put Wall',
            hovertemplate=f'{nome} %{{x:,.0f}}<br>Put Wall: %{{y:$,.3f}}<extra></extra>'
        ), row=row, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=strikes, y=net_gex,
            mode='lines+markers',
            line=dict(color='rgb(26, 118, 255)', width=2),
            marker=dict(size=4, color='rgb(26, 118, 255)'),
            name=f'{nome} GEX Líquido',
            hovertemplate=f'{nome} %{{x:,.0f}}<br>GEX Líquido: %{{y:$,.3f}}<extra></extra>'
        ), row=row, col=1
    )

    fig.add_hline(y=0, line=dict(color='grey', width=1, dash='dot'), row=row, col=1)
    fig.add_shape(
        type='line', x0=spotPrice, y0=ymin, x1=spotPrice, y1=ymax,
        line=dict(color='red', width=2, dash='dash'), row=row, col=1
    )
    fig.add_annotation(
        x=spotPrice, y=ymax, text=f'Spot {spotPrice:,.2f}',
        showarrow=False, yanchor='top', xanchor='left',
        bgcolor='rgba(255,255,255,0.8)', bordercolor='red', borderwidth=1,
        row=row, col=1
    )
    if flip is not None:
        fig.add_shape(
            type='line', x0=flip, y0=ymin, x1=flip, y1=ymax,
            line=dict(color='rgb(128, 0, 128)', width=2, dash='dash'), row=row, col=1
        )
        fig.add_annotation(
            x=flip, y=ymax, text=f'Gamma Flip {flip:,.2f}',
            showarrow=False, yanchor='bottom', yshift=-20,
            bgcolor='rgba(255,255,255,0.8)', bordercolor='rgb(128, 0, 128)', borderwidth=1,
            row=row, col=1
        )

    fig.update_xaxes(range=[0.8 * spotPrice, 1.2 * spotPrice], row=row, col=1)
    fig.update_yaxes(tickformat='$,.2f', row=row, col=1)


def processar_gex_e_enviar():
    n = len(MERCADOS)
    fig = make_subplots(
        rows=n, cols=1, shared_xaxes=False, vertical_spacing=0.07,
        subplot_titles=[m[0] for m in MERCADOS]
    )

    for row, (nome, csv_file) in enumerate(MERCADOS, start=1):
        if not os.path.exists(csv_file):
            print(f"Erro: O arquivo {csv_file} não foi encontrado na pasta.")
            continue
        spot, strikes, cw, pw, net, flip, total = ler_mercado(csv_file)
        adicionar_painel(fig, row, nome, spot, strikes, cw, pw, net, flip)
        flip_txt = f'{flip:,.2f}' if flip is not None else 'n/d'
        print(f'{nome}: spot={spot:,.2f} total=${total:,.2f}Bn gamma_flip={flip_txt}')

    fig.update_layout(
        title={
            'text': 'Gamma Exposure: SPX | NDX | QQQ (US$ bilhões por 1% de movimento)',
            'font': {'size': 20, 'family': 'Arial Black'}
        },
        barmode='overlay',
        showlegend=False,
        plot_bgcolor='white',
        font=dict(family='Arial', size=12, color='black'),
        width=1750,
        height=2400
    )
    fig.update_annotations(font_size=18)

    output_html = 'dashboard_gex.html'
    fig.write_html(output_html)

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{timestamp}] Gráfico GEX atualizado e salvo em {output_html}')

    if os.environ.get('GEX_SKIP_GIT') == '1':
        print('Modo CI: commit/push delegado ao workflow do GitHub.')
        return

    try:
        subprocess.run(['git', 'add', output_html], check=True)
        for _, csv_file in MERCADOS:
            if os.path.exists(csv_file):
                subprocess.run(['git', 'add', csv_file], check=True)
        commit_msg = f'Auto update GEX dashboard: {timestamp}'
        subprocess.run(['git', 'commit', '-m', commit_msg], check=True)
        subprocess.run(['git', 'push'], check=True)
        print('Push do Dashboard GEX para o GitHub realizado com sucesso!')
    except subprocess.CalledProcessError as e:
        print(f'Aviso do Git (sem alterações novas para commitar): {e}')


if __name__ == '__main__':
    processar_gex_e_enviar()