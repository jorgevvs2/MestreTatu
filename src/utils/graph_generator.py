import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import uuid
from typing import List, Dict, Optional

# Paletas de cores para os jogadores e tipos de ação
PLAYER_COLORS = {
    'Ambrael': '#F0F0F0',
    'Frederick': '#8A2BE2',
    'Will': '#4E5058',
    'Modrek': '#FFD700',
    'Kairos': '#228B22',
    'default': '#9E9E9E'
}

ACTION_COLORS = {
    'dano_causado': '#D32F2F',
    'dano_recebido': '#FFC107',
    'cura': '#4CAF50',
    'quedas': '#B0BEC5',  # Cinza azulado para quedas
    'critico_sucesso': '#00C853',
    'critico_falha': '#D50000',
}


def generate_session_graphs(session_rows: List[Dict], session_number: int) -> Optional[str]:
    """
    Gera um painel de gráficos 2x2 para os dados de uma sessão, focado em visualizações chave.
    """
    if not session_rows:
        return None

    df = pd.DataFrame(session_rows)
    df['amount'] = pd.to_numeric(df['amount'])

    # --- Layout 2x2, focado e limpo ---
    fig = make_subplots(
        rows=2, cols=2,
        specs=[
            [{'type': 'bar'}, {'type': 'domain'}],
            [{'type': 'bar'}, {'type': 'bar'}]
        ],
        subplot_titles=(
            'Dano Causado vs Recebido', 'Distribuição de Eliminações',
            'Cura e Quedas', 'Críticos (Sucesso vs Falha)'
        ),
        vertical_spacing=0.25,
        horizontal_spacing=0.1
    )

    # --- DADOS AGREGADOS ---
    dano_causado = df[df['action'] == 'causado'].groupby('player_name')['amount'].sum()
    dano_recebido = df[df['action'] == 'recebido'].groupby('player_name')['amount'].sum()
    cura_realizada = df[df['action'] == 'cura'].groupby('player_name')['amount'].sum()
    quedas = df[df['action'] == 'jogador_caido'].groupby('player_name')['amount'].sum()
    eliminacoes = df[df['action'] == 'eliminacao'].groupby('player_name')['amount'].sum()
    crit_success = df[df['action'] == 'critico_sucesso'].groupby('player_name')['amount'].sum()
    crit_fail = df[df['action'] == 'critico_falha'].groupby('player_name')['amount'].sum()

    # --- GRÁFICOS ---

    # 1. Dano Causado vs Recebido (Gráfico de Barras Agrupado)
    dano_df = pd.DataFrame({'Causado': dano_causado, 'Recebido': dano_recebido}).fillna(0).astype(int)
    if not dano_df.empty:
        fig.add_trace(go.Bar(name='Dano Causado', x=dano_df.index, y=dano_df['Causado'],
                             marker_color=ACTION_COLORS['dano_causado']), row=1, col=1)
        fig.add_trace(go.Bar(name='Dano Recebido', x=dano_df.index, y=dano_df['Recebido'],
                             marker_color=ACTION_COLORS['dano_recebido']), row=1, col=1)

    # 2. Distribuição de Eliminações (Gráfico de Rosca)
    if not eliminacoes.empty:
        pie_colors = [PLAYER_COLORS.get(p, PLAYER_COLORS['default']) for p in eliminacoes.index]
        pull = [0.1 if i == 0 else 0 for i in range(len(eliminacoes))]
        fig.add_trace(go.Pie(
            labels=eliminacoes.index, values=eliminacoes.values, hole=.4,
            marker_colors=pie_colors,
            textinfo='label+value',
            pull=pull,
            textfont_size=14,
            hoverinfo='label+percent+value'
        ), row=1, col=2)

    # 3. Cura e Quedas (Gráfico de Barras Agrupado)
    cura_quedas_df = pd.DataFrame({'Cura': cura_realizada, 'Quedas': quedas}).fillna(0).astype(int)
    if not cura_quedas_df.empty:
        fig.add_trace(go.Bar(name='Cura Realizada', x=cura_quedas_df.index, y=cura_quedas_df['Cura'],
                             marker_color=ACTION_COLORS['cura']), row=2, col=1)
        fig.add_trace(go.Bar(name='Vezes Caído', x=cura_quedas_df.index, y=cura_quedas_df['Quedas'],
                             marker_color=ACTION_COLORS['quedas']), row=2, col=1)

    # 4. Críticos (Sucesso vs Falha) (Gráfico de Barras Agrupado)
    crit_df = pd.DataFrame({'Sucessos': crit_success, 'Falhas': crit_fail}).fillna(0).astype(int)
    if not crit_df.empty:
        fig.add_trace(go.Bar(name='Críticos (Sucesso)', x=crit_df.index, y=crit_df['Sucessos'],
                             marker_color=ACTION_COLORS['critico_sucesso']), row=2, col=2)
        fig.add_trace(go.Bar(name='Críticos (Falha)', x=crit_df.index, y=crit_df['Falhas'],
                             marker_color=ACTION_COLORS['critico_falha']), row=2, col=2)

    # --- Estilização Final do Layout ---
    fig.update_layout(
        title_text=f'Dashboard da Sessão {session_number}',
        title_x=0.5,
        title_font_size=32,
        # --- MELHORIA: Legenda removida para um visual mais limpo ---
        showlegend=False,
        height=1080,
        width=1920,
        template='plotly_dark',
        paper_bgcolor='rgba(30, 30, 30, 1)',
        plot_bgcolor='rgba(43, 45, 49, 1)',
        font=dict(family="Arial, sans-serif", size=14, color="white"),
        bargap=0.3,
        bargroupgap=0.1,
    )

    # Adiciona os valores de texto a todos os gráficos de barra
    fig.update_traces(
        selector=dict(type='bar'),
        texttemplate='%{y}',
        textposition='auto',
        textfont_size=12
    )

    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(255,255,255,0.1)')
    fig.update_xaxes(showgrid=False)
    fig.update_annotations(font_size=20)  # Tamanho dos subtítulos

    # --- Salvando a Imagem ---
    temp_dir = os.path.join("src", "logs", "temp_graphs")
    os.makedirs(temp_dir, exist_ok=True)
    filename = f"dashboard_session_{session_number}_{uuid.uuid4().hex[:8]}.png"
    filepath = os.path.join(temp_dir, filename)

    fig.write_image(filepath, scale=2)

    return filepath