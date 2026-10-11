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
    ("EWZ", "ewz_quotedata.csv"),
    ("SPY", "spy_quotedata.csv"),
    ("IWM", "iwm_quotedata.csv"),
    ("VIX", "vix_quotedata.csv"),
]

MAX_EXP_INDIVIDUAIS = 6
TR_PER_MARKET = 8


def carregar_df(filename):
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
    return df, spotPrice


def filtrar(df, filtro, now):
    if filtro is None:
        return df
    kind, val = filtro
    if kind == 'date':
        return df[df['ExpirationDate'].dt.normalize() == pd.Timestamp(val).normalize()]
    if kind == 'range':
        return df[df['ExpirationDate'] <= now + timedelta(days=val)]
    return df


def agregar(df, spotPrice):
    if len(df) == 0:
        return None

    df = df.copy()
    df['CallGEX'] = df['CallGamma'] * df['CallOpenInt'] * 100 * spotPrice * spotPrice * 0.01
    df['PutGEX'] = df['PutGamma'] * df['PutOpenInt'] * 100 * spotPrice * spotPrice * 0.01 * -1
    df['TotalGamma'] = (df['CallGEX'] + df['PutGEX']) / 10**9

    dfAgg = df.groupby(['StrikePrice'])[['CallGEX', 'PutGEX', 'TotalGamma']].sum().sort_index()
    strikes = dfAgg.index.values
    call_wall = dfAgg['CallGEX'].to_numpy() / 10**9
    put_wall = dfAgg['PutGEX'].to_numpy() / 10**9
    net_gex = dfAgg['TotalGamma'].to_numpy()
    total_gamma = df['TotalGamma'].sum()

    flip = None
    for i in range(len(net_gex) - 1):
        a = net_gex[i]
        b = net_gex[i + 1]
        if (a <= 0) != (b <= 0) and a != b:
            level = strikes[i] + (strikes[i + 1] - strikes[i]) * (-a) / (b - a)
            if flip is None or abs(level - spotPrice) < abs(flip - spotPrice):
                flip = level

    return {
        'spot': spotPrice,
        'strikes': strikes,
        'call_wall': call_wall,
        'put_wall': put_wall,
        'net_gex': net_gex,
        'flip': flip,
        'total_gamma': total_gamma,
        'call_wall_strike': strikes[int(np.argmax(call_wall))],
        'put_wall_strike': strikes[int(np.argmin(put_wall))],
    }


def add_painel(fig, row, nome, d, visible):
    if d is None:
        for _ in range(TR_PER_MARKET):
            fig.add_trace(go.Scatter(x=[], y=[], showlegend=False, visible=visible), row=row, col=1)
        return

    strikes = d['strikes']
    spot = d['spot']
    call_wall = d['call_wall']
    put_wall = d['put_wall']
    net = d['net_gex']
    flip = d['flip']

    ymin = min(net.min(), put_wall.min())
    ymax = max(net.max(), call_wall.max())
    x0 = 0.8 * spot
    x1 = 1.2 * spot

    diffs = np.diff(strikes)
    diffs = diffs[diffs > 0]
    step = float(np.median(diffs)) if len(diffs) else (x1 - x0) / 100.0
    bar_width = step * 0.75

    fig.add_trace(go.Bar(
        x=strikes, y=call_wall, width=bar_width,
        marker_color='rgb(38, 166, 91)', marker_line_color='black', marker_line_width=0.15,
        opacity=0.55, showlegend=False, visible=visible,
        hovertemplate=f'{nome} %{{x:,.1f}}<br>Call Wall: %{{y:$,.3f}}<extra></extra>'
    ), row=row, col=1)
    fig.add_trace(go.Bar(
        x=strikes, y=put_wall, width=bar_width,
        marker_color='rgb(255, 82, 82)', marker_line_color='black', marker_line_width=0.15,
        opacity=0.55, showlegend=False, visible=visible,
        hovertemplate=f'{nome} %{{x:,.1f}}<br>Put Wall: %{{y:$,.3f}}<extra></extra>'
    ), row=row, col=1)
    fig.add_trace(go.Scatter(
        x=strikes, y=net, mode='lines+markers',
        line=dict(color='rgb(26, 118, 255)', width=2), marker=dict(size=4, color='rgb(26, 118, 255)'),
        showlegend=False, visible=visible,
        hovertemplate=f'{nome} %{{x:,.1f}}<br>GEX Líquido: %{{y:$,.3f}}<extra></extra>'
    ), row=row, col=1)

    fig.add_trace(go.Scatter(x=[x0, x1], y=[0, 0], mode='lines',
        line=dict(color='grey', width=1, dash='dot'), showlegend=False, visible=visible, hoverinfo='skip'), row=row, col=1)
    fig.add_trace(go.Scatter(x=[spot, spot], y=[ymin, ymax], mode='lines',
        line=dict(color='red', width=2, dash='dash'), showlegend=False, visible=visible, hoverinfo='skip'), row=row, col=1)
    if flip is not None:
        fig.add_trace(go.Scatter(x=[flip, flip], y=[ymin, ymax], mode='lines',
            line=dict(color='rgb(128, 0, 128)', width=2, dash='dash'), showlegend=False, visible=visible, hoverinfo='skip'), row=row, col=1)
    else:
        fig.add_trace(go.Scatter(x=[], y=[], mode='lines', showlegend=False, visible=visible), row=row, col=1)

    fig.add_trace(go.Scatter(x=[spot], y=[ymax], mode='text', text=[f'Spot {spot:,.2f}'],
        textposition='top left', textfont=dict(color='red', size=12), showlegend=False, visible=visible, hoverinfo='skip'), row=row, col=1)
    if flip is not None:
        fig.add_trace(go.Scatter(x=[flip], y=[ymax], mode='text', text=[f'Flip {flip:,.2f}'],
            textposition='bottom right', textfont=dict(color='rgb(128, 0, 128)', size=12), showlegend=False, visible=visible, hoverinfo='skip'), row=row, col=1)
    else:
        fig.add_trace(go.Scatter(x=[], y=[], mode='text', showlegend=False, visible=visible), row=row, col=1)

    fig.update_xaxes(range=[x0, x1], row=row, col=1)
    fig.update_yaxes(tickformat='$,.2f', row=row, col=1)


def montar_tabela(rows_table, visible):
    colunas = ['Mercado', 'Spot', 'GEX Total ($Bn)', 'Gamma Flip', 'Call Wall', 'Put Wall']
    mercado, spot, total, flip, cw, pw = [], [], [], [], [], []
    for nome, sp, d in rows_table:
        mercado.append(nome)
        spot.append(f"{sp:,.2f}")
        if d is None:
            total.append('-')
            flip.append('-')
            cw.append('-')
            pw.append('-')
        else:
            total.append(f"${d['total_gamma']:,.2f}")
            flip.append(f"{d['flip']:,.2f}" if d['flip'] is not None else 'n/d')
            cw.append(f"{d['call_wall_strike']:,.0f}")
            pw.append(f"{d['put_wall_strike']:,.0f}")

    return go.Table(
        columnwidth=[70, 110, 130, 120, 100, 100],
        visible=visible,
        header=dict(values=colunas, fill_color='rgb(26, 118, 255)',
                    font=dict(color='white', size=14, family='Arial'), align='center', height=32),
        cells=dict(values=[mercado, spot, total, flip, cw, pw],
                   fill_color='rgb(245, 248, 252)', font=dict(color='black', size=13, family='Arial'),
                   align='center', height=30)
    )


def processar_gex_e_enviar():
    now = datetime.now()

    mercados = []
    for nome, csv_file in MERCADOS:
        if not os.path.exists(csv_file):
            print(f"Erro: O arquivo {csv_file} não foi encontrado na pasta.")
            continue
        df, spot = carregar_df(csv_file)
        mercados.append((nome, spot, df))

    n = len(mercados)
    if n == 0:
        print("Nenhum dado disponível.")
        return

    exp_union = sorted({pd.Timestamp(x).normalize()
                        for _, _, df in mercados
                        for x in df['ExpirationDate'].dropna().unique()})

    views = [
        ('Todas as expirações', None),
        ('0DTE (mais próxima)', ('date', exp_union[0])),
        ('Próximos 7 dias', ('range', 7)),
        ('Próximos 30 dias', ('range', 30)),
    ]
    for e in exp_union[1:1 + MAX_EXP_INDIVIDUAIS]:
        views.append((f"Venc {e.strftime('%d/%m/%Y')}", ('date', e)))

    fig = make_subplots(
        rows=n + 1, cols=1, shared_xaxes=False, vertical_spacing=0.05,
        row_heights=[0.10] + [0.90 / n] * n,
        specs=[[{'type': 'table'}]] + [[{'type': 'xy'}]] * n,
        subplot_titles=[''] + [nome for nome, _, _ in mercados]
    )

    tr_per_view = 1 + n * TR_PER_MARKET
    total = tr_per_view * len(views)

    for vi, (label, filtro) in enumerate(views):
        vis = (vi == 0)
        rows_table = []
        for nome, spot, df in mercados:
            df_sel = filtrar(df, filtro, now)
            d = agregar(df_sel, spot)
            rows_table.append((nome, spot, d))

        fig.add_trace(montar_tabela(rows_table, visible=vis), row=1, col=1)
        for ri, (name, sp, d) in enumerate(rows_table, start=2):
            add_painel(fig, ri, name, d, vis)

    buttons = []
    for vi, (label, _) in enumerate(views):
        mask = [False] * total
        for i in range(vi * tr_per_view, (vi + 1) * tr_per_view):
            mask[i] = True
        buttons.append(dict(label=label, method='update', args=[{'visible': mask}]))

    fig.update_layout(
        title={
            'text': 'Gamma Exposure: ' + ' | '.join(nome for nome, _, _ in mercados) + ' (US$ bilhões por 1% de movimento)',
            'font': {'size': 20, 'family': 'Arial Black'}
        },
        barmode='overlay',
        showlegend=False,
        plot_bgcolor='white',
        font=dict(family='Arial', size=12, color='black'),
        updatemenus=[dict(
            buttons=buttons, direction='down', showactive=True,
            x=0.0, y=1.02, xanchor='left', yanchor='top',
            bgcolor='white', bordercolor='rgba(0,0,0,0.4)', font=dict(size=13)
        )],
        width=1750,
        height=int(300 + 780 * n),
        margin=dict(t=150)
    )
    fig.update_annotations(font_size=16)

    output_html = 'dashboard_gex.html'
    fig.write_html(output_html)

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{timestamp}] Gráfico GEX atualizado e salvo em {output_html} ({len(views)} visões)')
    for nome, spot, df in mercados:
        d = agregar(df, spot)
        flip_txt = f"{d['flip']:,.2f}" if d['flip'] is not None else 'n/d'
        print(f"  {nome}: spot={spot:,.2f} total=${d['total_gamma']:,.2f}Bn gamma_flip={flip_txt}")

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