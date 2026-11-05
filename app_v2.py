import os
import re
import base64
from io import BytesIO
from datetime import datetime, timezone

import requests
import streamlit as st
from PIL import Image


# ==========================================
# DONCULLER-TRADE47 V3
# ==========================================

st.set_page_config(
    page_title="DONCULLER-TRADE47",
    page_icon="🦁",
    layout="wide"
)

st.markdown("""
<style>
.stApp {
    background: #071321;
    color: #edf3fa;
}
section[data-testid="stSidebar"] {
    background: #0b1b2d;
}
.block-container {
    max-width: 1250px;
}
.panel {
    background: #0d2033;
    border: 1px solid #23415e;
    border-radius: 15px;
    padding: 20px;
    margin-bottom: 15px;
}
.buy {
    color: #25d887;
    font-size: 32px;
    font-weight: bold;
}
.sell {
    color: #ff5c68;
    font-size: 32px;
    font-weight: bold;
}
.wait {
    color: #ffc857;
    font-size: 32px;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)


# ==========================================
# HEADER
# ==========================================

st.markdown("""
<div class="panel">
<h1>🦁 DONCULLER-TRADE47</h1>
<p>AI TRADING CHART ANALYZER · VERSION 3</p>
</div>
""", unsafe_allow_html=True)


# ==========================================
# API
# ==========================================

API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()

MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "nvidia/nemotron-3.5-super-vl:free"
).strip()

API_URL = "https://openrouter.ai/api/v1/chat/completions"


# ==========================================
# ASSETS
# ==========================================

SYNTHETIC_ASSETS = [
    "Boom 1000", "Crash 1000",
    "Boom 500", "Crash 500",
    "Boom 300", "Crash 300",
    "Boom 100", "Crash 100",
    "Boom 50", "Crash 50",
    "Jump Index 50", "Jump Index",
    "Step Index"
]

FOREX_ASSETS = [
    "EUR/USD", "GBP/USD", "XAU/USD"
]


# ==========================================
# SIDEBAR
# ==========================================

with st.sidebar:

    st.header("CONFIGURAÇÃO")

    market = st.radio(
        "Mercado",
        ["Índices sintéticos", "Forex"]
    )

    assets = (
        SYNTHETIC_ASSETS
        if market == "Índices sintéticos"
        else FOREX_ASSETS
    )

    asset = st.selectbox("Ativo", assets)

    timeframe = st.selectbox(
        "Timeframe",
        ["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
        index=1
    )

    platform = st.selectbox(
        "Plataforma",
        ["Deriv MT5", "TradingView", "Outra"]
    )

    st.caption("DONCULLER-TRADE47 V3")


# ==========================================
# SCREENSHOT
# ==========================================

left, right = st.columns([1.4, 1])

with left:

    st.markdown(
        '<div class="panel"><h3>GRÁFICO PARA ANÁLISE</h3></div>',
        unsafe_allow_html=True
    )

    uploaded_file = st.file_uploader(
        "Carregar screenshot",
        type=["png", "jpg", "jpeg"]
    )

    image = None

    if uploaded_file:

        try:
            image = Image.open(uploaded_file).convert("RGB")

            st.image(
                image,
                caption=f"{asset} - {timeframe}",
                use_container_width=True
            )

        except Exception:
            st.error("Não foi possível abrir a imagem.")

with right:

    st.markdown("""
    <div class="panel">
    <h3>MOTOR DE ANÁLISE</h3>
    <p>🟢 BUY - Comprar</p>
    <p>🔴 SELL - Vender</p>
    <p>🟡 AGUARDAR - Sem confirmação</p>
    <hr>
    <p>Análise visual de velas, indicadores e movimentos.</p>
    </div>
    """, unsafe_allow_html=True)


# ==========================================
# PROMPT V3
# ==========================================

def build_prompt():

    return f"""
És o analista técnico da DONCULLER-TRADE47 V3.

ATIVO: {asset}
MERCADO: {market}
TIMEFRAME: {timeframe}
PLATAFORMA: {platform}

Analisa cuidadosamente o screenshot.

1. LEITURA DAS VELAS

Analisa:
- Velas de alta e baixa.
- Corpos e pavios.
- Sombras superiores e inferiores.
- Engolfo de alta e baixa.
- Doji.
- Pin Bar.
- Rejeições de preço.
- Sequências de velas.
- Força dos compradores e vendedores.

2. INDICADORES

Analisa quando estiverem visíveis:

- Zig Zag: topos, fundos e mudanças de direção.
- Fractals: pontos de reversão.
- MACD: cruzamentos e força.
- RSI: força e zonas extremas.
- Médias móveis: inclinação e cruzamentos.

Se não estiverem visíveis, informa isso.
Nunca inventes valores.

3. MOVIMENTOS

Identifica:
- Tendência principal.
- Impulsos e correções.
- Máximos e mínimos.
- Suportes e resistências.
- Rompimentos e falsos rompimentos.
- Mudanças de estrutura.
- Possíveis reversões.

4. COMPARAÇÃO

Compara BUY e SELL.

Atribui pontuação técnica de 0 a 100
para cada direção.

As pontuações não são probabilidades
reais de lucro.

Escolhe a direção com maior evidência
quando houver confirmação suficiente.

Não forces operações.

5. CENÁRIO BUY

Apresenta:

Entrada futura:
Condição de ativação:
Stop Loss:
Take Profit 1:
Take Profit 2:
Risco/retorno:

6. CENÁRIO SELL

Apresenta:

Entrada futura:
Condição de ativação:
Stop Loss:
Take Profit 1:
Take Profit 2:
Risco/retorno:

Os preços devem respeitar a estrutura
e a escala visível do gráfico.

Não inventes preços.
Se não forem legíveis, informa.

7. RELATÓRIO FINAL

ATIVO:
TIMEFRAME:
QUALIDADE DO SCREENSHOT:

TENDÊNCIA:
MOVIMENTO ATUAL:
LEITURA DAS VELAS:

ZIG ZAG:
FRACTALS:
MACD:
RSI:
MÉDIAS MÓVEIS:

SUPORTE:
RESISTÊNCIA:

PONTUAÇÃO BUY:
PONTUAÇÃO SELL:

CENÁRIO BUY:
ENTRADA FUTURA:
ATIVAÇÃO:
SL:
TP1:
TP2:

CENÁRIO SELL:
ENTRADA FUTURA:
ATIVAÇÃO:
SL:
TP1:
TP2:

SINAL PRINCIPAL: BUY / SELL / AGUARDAR

DIREÇÃO COM MAIOR FORÇA:
JUSTIFICAÇÃO:
O QUE PRECISA ACONTECER PARA ENTRAR:

REGRAS:

- Nunca respondas apenas AGUARDAR.
- Quando aguardares, apresenta os dois cenários.
- Não inventes preços nem indicadores.
- Não confundas correção com reversão.
- Usa português simples e direto.
- Não prometas resultados.
"""


# ==========================================
# IMAGE ANALYSIS
# ==========================================

def analyze_chart(chart_image, prompt):

    buffer = BytesIO()

    chart_image.save(
        buffer,
        format="JPEG",
        quality=90
    )

    encoded = base64.b64encode(
        buffer.getvalue()
    ).decode("utf-8")

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": (
                                "data:image/jpeg;base64,"
                                + encoded
                            )
                        }
                    }
                ]
            }
        ],
        "temperature": 0.1,
        "max_tokens": 3000
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "X-Title": "DONCULLER-TRADE47"
    }

    response = requests.post(
        API_URL,
        headers=headers,
        json=payload,
        timeout=180
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Erro OpenRouter {response.status_code}: "
            f"{response.text[:1000]}"
        )

    data = response.json()

    choices = data.get("choices", [])

    if not choices:
        raise RuntimeError("A IA não devolveu resultados.")

    content = choices[0]["message"].get("content", "")

    if isinstance(content, list):
        content = "\n".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict)
        )

    if not str(content).strip():
        raise RuntimeError("A resposta da IA está vazia.")

    return str(content).strip()


# ==========================================
# ANALYZE BUTTON
# ==========================================

if st.button(
    "🦁 ANALISAR GRÁFICO",
    use_container_width=True,
    disabled=(image is None)
):

    if not API_KEY:

        st.error(
            "OPENROUTER_API_KEY não encontrada no Render."
        )

    else:

        try:

            with st.spinner(
                "A DONCULLER-TRADE47 está a analisar o gráfico..."
            ):

                result = analyze_chart(
                    image,
                    build_prompt()
                )

                st.session_state["last_result"] = result
                st.session_state["last_asset"] = asset
                st.session_state["last_timeframe"] = timeframe

        except Exception as error:

            st.error(f"Erro na análise: {error}")


# ==========================================
# RESULTS
# ==========================================

if "last_result" in st.session_state:

    result = st.session_state["last_result"]

    st.divider()

    st.subheader("RELATÓRIO DE ANÁLISE")

    st.caption(
        f"{st.session_state['last_asset']} | "
        f"{st.session_state['last_timeframe']}"
    )

    match = re.search(
        r"SINAL PRINCIPAL\s*:\s*(BUY|SELL|AGUARDAR)",
        result,
        re.IGNORECASE
    )

    signal = (
        match.group(1).upper()
        if match
        else "AGUARDAR"
    )

    if signal == "BUY":

        st.markdown(
            '<div class="panel buy">🟢 BUY</div>',
            unsafe_allow_html=True
        )

    elif signal == "SELL":

        st.markdown(
            '<div class="panel sell">🔴 SELL</div>',
            unsafe_allow_html=True
        )

    else:

        st.markdown(
            '<div class="panel wait">🟡 AGUARDAR</div>',
            unsafe_allow_html=True
        )

    st.markdown(result)

    st.download_button(
        "DESCARREGAR RELATÓRIO",
        data=result,
        file_name="DonCullerTrade47_V3.txt",
        mime="text/plain"
    )


# ==========================================
# FOOTER
# ==========================================

st.divider()

st.caption("DONCULLER-TRADE47 V3")

st.warning(
    "A análise é feita a partir de screenshots. "
    "O sistema ainda não recebe cotações em tempo real, "
    "não calcula indicadores diretamente de dados OHLC "
    "e não executa operações. "
    "Testa sempre em conta Demo."
)
