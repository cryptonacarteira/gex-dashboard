import os
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

PASTA_HISTORICO = "historico"
SAIDA = "dashboard_completo.html"

CALL_COLOR = "rgb(38, 166, 91)"
PUT_COLOR = "rgb(255, 82, 82)"
NET_COLOR = "rgb(26, 118, 255)"
FLIP_COLOR = "rgb(128, 0, 128)"
SPOT_COLOR = "rgb(200, 60, 60)"
REGIAO_CORES = [
    "#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
    "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac",
]
NOMES_REGIOES = [f"Gex {i}" for i in range(1, 11)]


def carregar(nome):
    caminho = os.path.join(PASTA_HISTORICO, nome)
    if not os.path.exists(caminho):
        return pd.DataFrame()
    return pd.read_csv(caminho, encoding="utf-8", sep=";", decimal=",")


def botao_ativos(ativos, traces_por_ativo):
    buttons = []
    n = len(ativos)
    for i, a in enumerate(ativos):
        mask = [False] * (n * traces_por_ativo)
        for j in range(traces_por_ativo):
            mask[i * traces_por_ativo + j] = True
        buttons.append(dict(label=a, method="update", args=[{"visible": mask}]))
    return buttons


def fig_historico(teste):
    ativos = sorted(teste["Ativo"].unique())
    fig = go.Figure()
    for i, a in enumerate(ativos):
        vis = i == 0
        d = teste[teste["Ativo"] == a].sort_values("Data")
        fig.add_trace(go.Scatter(
            x=d["Data"], y=d["Call Wall"], name=f"{a} Call Wall", legendgroup=a,
            mode="lines+markers", visible=vis, line=dict(color=CALL_COLOR, width=2)))
        fig.add_trace(go.Scatter(
            x=d["Data"], y=d["Put Wall"], name=f"{a} Put Wall", legendgroup=a,
            mode="lines+markers", visible=vis, line=dict(color=PUT_COLOR, width=2)))
        fig.add_trace(go.Scatter(
            x=d["Data"], y=d["Gamma Flip"], name=f"{a} Gamma Flip", legendgroup=a,
            mode="lines+markers", visible=vis, line=dict(color=FLIP_COLOR, width=2, dash="dot")))
        fig.add_trace(go.Scatter(
            x=d["Data"], y=d["Spot"], name=f"{a} Spot", legendgroup=a,
            mode="lines+markers", visible=vis, line=dict(color=SPOT_COLOR, width=2, dash="dash")))
    fig.update_layout(
        title="Call Wall · Put Wall · Gamma Flip · Spot (histórico)",
        template="plotly_white", hovermode="x unified", height=520,
        legend=dict(orientation="h", y=-0.2),
        updatemenus=[dict(buttons=botao_ativos(ativos, 4), direction="down",
                          showactive=True, x=0.0, y=1.15, xanchor="left", yanchor="top")],
        margin=dict(t=110))
    return fig


def fig_call_put(teste):
    ativos = sorted(teste["Ativo"].unique())
    fig = go.Figure()
    for i, a in enumerate(ativos):
        vis = i == 0
        d = teste[teste["Ativo"] == a].sort_values("Data")
        fig.add_trace(go.Bar(
            x=d["Data"], y=d["Call"], name=f"{a} Call", legendgroup=a,
            visible=vis, marker_color=CALL_COLOR))
        fig.add_trace(go.Bar(
            x=d["Data"], y=d["Put"], name=f"{a} Put", legendgroup=a,
            visible=vis, marker_color=PUT_COLOR))
    fig.update_layout(
        title="Call vs Put (GEX $Bn por data)",
        template="plotly_white", barmode="relative", height=480,
        legend=dict(orientation="h", y=-0.2),
        updatemenus=[dict(buttons=botao_ativos(ativos, 2), direction="down",
                          showactive=True, x=0.0, y=1.15, xanchor="left", yanchor="top")],
        margin=dict(t=110))
    return fig


def fig_regioes(teste):
    d = teste.groupby("Data")[NOMES_REGIOES].sum().sort_index()
    fig = go.Figure()
    for i, reg in enumerate(NOMES_REGIOES):
        fig.add_trace(go.Scatter(
            x=d.index, y=d[reg], name=reg, mode="lines",
            stackgroup="one", line=dict(width=0.5, color=REGIAO_CORES[i])))
    fig.update_layout(
        title="GEX por região (Gex 1..10, área empilhada · $Bn)",
        template="plotly_white", hovermode="x unified", height=520,
        legend=dict(orientation="h", y=-0.2))
    return fig


def fig_perfil(gex_total, max_datas=60):
    datas = sorted(gex_total["Data"].unique())
    if len(datas) > max_datas:
        datas = datas[-max_datas:]
    gex_total = gex_total[gex_total["Data"].isin(datas)]
    combos = list(gex_total.groupby(["Ativo", "Data"]))

    fig = go.Figure()
    botoes = []
    labels = []
    for idx, ((ativo, data), g) in enumerate(combos):
        g = g.sort_values("Strike")
        vis = idx == 0
        base = len(fig.data)
        fig.add_trace(go.Bar(x=g["Strike"], y=g["Call"], name="Call",
                             visible=vis, marker_color=CALL_COLOR, opacity=0.6))
        fig.add_trace(go.Bar(x=g["Strike"], y=g["Put"], name="Put",
                             visible=vis, marker_color=PUT_COLOR, opacity=0.6))
        fig.add_trace(go.Scatter(x=g["Strike"], y=g["Total"], name="GEX Líquido",
                                 mode="lines+markers", visible=vis,
                                 line=dict(color=NET_COLOR, width=2)))
        labels.append(f"{ativo} · {data}")
    total_traces = len(fig.data)
    for idx, label in enumerate(labels):
        mask = [False] * total_traces
        for j in range(3):
            mask[idx * 3 + j] = True
        botoes.append(dict(label=label, method="update", args=[{"visible": mask}]))

    fig.update_layout(
        title="Perfil de GEX por strike (selecione ativo e data)",
        template="plotly_white", barmode="overlay", height=600,
        hovermode="x unified", bargap=0.05,
        updatemenus=[dict(buttons=botoes, direction="down", showactive=True,
                          x=0.0, y=1.16, xanchor="left", yanchor="top",
                          bgcolor="white")],
        margin=dict(t=140))
    return fig


def tabela_resumo(teste):
    ult = teste.sort_values("Data").groupby("Ativo").tail(1)
    ult = ult.sort_values("Ativo")
    ult = ult[["Ativo", "Data", "Spot", "Call Wall", "Put Wall", "Gamma Flip", "Gex Total (Bn)"]]
    return go.Figure(data=[go.Table(
        header=dict(values=["Ativo", "Data", "Spot", "Call Wall", "Put Wall", "Gamma Flip", "GEX Total ($Bn)"],
                    fill_color=NET_COLOR, font=dict(color="white", size=13), align="center"),
        cells=dict(values=[ult[c] for c in ult.columns],
                   fill_color="white", font=dict(size=12), align="center",
                   format=["", "", ".2f", ".2f", ".2f", ".2f", ".2f"]))])


def montar_html(figuras):
    partes = []
    for i, (titulo, fig) in enumerate(figuras):
        primeiro = i == 0
        partes.append(f"<h2 style='font-family:Arial;margin:28px 0 4px'>{titulo}</h2>")
        partes.append(pio.to_html(fig, full_html=False, include_plotlyjs=("cdn" if primeiro else False)))
    corpo = "\n".join(partes)
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    return f"""<!DOCTYPE html>
<html lang="pt-br"><head><meta charset="utf-8">
<title>Dashboard GEX</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body style="margin:0;padding:24px;background:#f5f8fc;font-family:Arial">
<h1 style="font-family:Arial">Dashboard GEX — Futuros &amp; Índices</h1>
<p style="color:#666;font-family:Arial">Atualizado em {agora}</p>
{corpo}
</body></html>"""


def main():
    teste = carregar("teste.csv")
    gex_total = carregar("GexTotal.csv")
    if teste.empty:
        print("Sem histórico ainda. Rode primeiro o historico.py.")
        return

    figuras = [
        ("Resumo do último dia", tabela_resumo(teste)),
        ("Call Wall / Put Wall / Gamma Flip / Spot", fig_historico(teste)),
        ("Call vs Put", fig_call_put(teste)),
        ("GEX por região", fig_regioes(teste)),
    ]
    if not gex_total.empty:
        figuras.append(("Perfil de GEX por strike", fig_perfil(gex_total)))

    with open(SAIDA, "w", encoding="utf-8") as f:
        f.write(montar_html(figuras))

    print(f"Dashboard gerado: {SAIDA} ({os.path.getsize(SAIDA):,} bytes, {len(teste['Data'].unique())} dia(s) de histórico)")


if __name__ == "__main__":
    main()
