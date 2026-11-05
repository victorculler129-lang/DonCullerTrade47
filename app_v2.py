import os
import re
import base64
from io import BytesIO

import requests
import streamlit as st
from PIL import Image


# ==========================================
# DONCULLER-TRADE47 V3.1
# ==========================================

st.set_page_config(
    page_title="DONCULLER-TRADE47",
    page_icon="🦁",
    layout="wide"
)


# ==========================================
# DESIGN
# ==========================================

st.markdown("""
<style>
.stApp {
    background-color: #071321;
    color: #edf3fa;
}

section[data-testid="stSidebar"] {
    background-color: #0b1b2d;
}

.block-container {
    max-width: 1250px;
    padding-top: 1.5rem;
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

div.stButton > button {
    background: #176b50;
    color: white;
    border-radius: 10px;
    min-height: 3rem;
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
<p>AI TRADING CHART ANALYZER · V3.1</p>
</div>
""", unsafe_allow_html=True)


# ==========================================
# API CONFIGURATION
# ==========================================

API_KEY = os.getenv(
    "OPENROUTER_API_KEY", ""
).strip()

MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "nvidia/nemotron-3.5-super-vl:free"
).strip()

API_URL = "https://openrouter.ai/api/v1/chat/completions"


# ==========================================
# ASSETS
# ==========================================

SYNTHETIC_ASSETS = [
    "Boom 1000",
    "Crash 1000",
    "Boom 500",
    "Crash 500",
    "Boom 300",
    "Crash 300",
    "Boom 100",
    "Crash 100",
    "Boom 50",
    "Crash 50",
    "Jump Index 50",
    "Jump Index",
    "Step Index"
]

FOREX_ASSETS = [
    "EUR/USD",
    "GBP/USD",
    "XAU/USD"
]


# ==========================================
# CONFIGURATION
# ==========================================

with st.sidebar:

    st.header("⚙️ CONFIGURAÇÃO")

    market = st.radio(
        "Mercado",
        ["Índices sintéticos", "Forex"]
    )

    assets = (
        SYNTHETIC_ASSETS
        if market == "Índices sintéticos"
        else FOREX_ASSETS
    )

    asset = st.selectbox(
        "Ativo",
        assets
    )

    timeframe = st.selectbox(
        "Timeframe",
        ["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
        index=1
    )

    platform = st.selectbox(
        "Plataforma",
        ["Deriv MT5", "TradingView", "Outra"]
    )

    st.caption("DONCULLER-TRADE47 V3.1")


# ==========================================
# SCREENSHOT
# ==========================================

left, right = st.columns([1.4, 1])

with left:

    st.markdown("""
    <div class="panel">
    <h3>📷 GRÁFICO PARA ANÁLISE</h3>
    <p>Envia uma captura nítida do gráfico.</p>
    </div>
    """, unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        "Carregar screenshot",
        type=["png", "jpg", "jpeg"]
    )

    image = None

    if uploaded_file:

        try:

            image = Image.open(
                uploaded_file
            ).convert("RGB")

            st.image(
                image,
                caption=f"{asset} · {timeframe}",
                use_container_width=True
            )

        except Exception:

            st.error(
                "Não foi possível abrir a imagem."
            )


with right:

    st.markdown("""
    <div class="panel">
    <h3>📊 MOTOR DE ANÁLISE</h3>
    <p>🟢 BUY — Comprar</p>
    <p>🔴 SELL — Vender</p>
    <p>🟡 AGUARDAR — Sem confirmação</p>
    <hr>
    <p>Leitura visual de velas, indicadores e movimentos.</p>
    </div>
    """, unsafe_allow_html=True)


# ==========================================
# PROMPT V3.1
# ==========================================

def build_prompt():

    return f"""
És o analista técnico principal da
DONCULLER-TRADE47 V3.1.

ATIVO: {asset}
MERCADO: {market}
TIMEFRAME: {timeframe}
PLATAFORMA: {platform}

A tua tarefa é analisar profundamente
o screenshot enviado.

Não respondas apenas AGUARDAR.

===============================
1. LEITURA DAS VELAS
===============================

Analisa:

- Velas de alta e baixa.
- Corpos das velas.
- Pavios superiores e inferiores.
- Tamanho das sombras.
- Engolfo de alta e baixa.
- Doji.
- Pin Bar.
- Rejeições de preço.
- Sequências de velas.
- Força dos compradores.
- Força dos vendedores.

Dá atenção especial às últimas velas.

===============================
2. INDICADORES
===============================

Analisa quando estiverem visíveis:

ZIG ZAG:
- Topos.
- Fundos.
- Mudanças de direção.

FRACTALS:
- Fractals superiores.
- Fractals inferiores.
- Possíveis reversões.

MACD:
- Cruzamentos.
- Direção.
- Força do movimento.
- Divergências visíveis.

RSI:
- Força.
- Sobrecompra.
- Sobrevenda.
- Divergências visíveis.

MÉDIAS MÓVEIS:
- Inclinação.
- Cruzamentos.
- Posição do preço.

Não inventes valores.
Se não estiver visível, informa.

===============================
3. MOVIMENTOS DO MERCADO
===============================

Identifica:

- Tendência principal.
- Tendência atual.
- Impulsos.
- Correções.
- Máximos e mínimos.
- Suportes.
- Resistências.
- Rompimentos.
- Falsos rompimentos.
- Mudanças de estrutura.
- Possíveis reversões.

===============================
4. COMPARAÇÃO BUY E SELL
===============================

Avalia separadamente:

FORÇA BUY: 0 a 100
FORÇA SELL: 0 a 100

Estas pontuações representam
avaliação técnica, não probabilidades
reais de lucro.

Compara:

- Estrutura.
- Velas.
- Indicadores.
- Movimento.
- Suportes e resistências.

Identifica a direção com maior
evidência técnica.

Não escolhas AGUARDAR por defeito.

Se BUY apresentar confirmação
suficiente, escolhe BUY.

Se SELL apresentar confirmação
suficiente, escolhe SELL.

Se nenhuma direção apresentar
confirmação suficiente, escolhe
AGUARDAR e explica porquê.

Não forces operações.

===============================
5. CENÁRIO BUY
===============================

ENTRADA FUTURA:
CONDIÇÃO DE ATIVAÇÃO:
STOP LOSS:
TAKE PROFIT 1:
TAKE PROFIT 2:
RISCO/RETORNO:

===============================
6. CENÁRIO SELL
===============================

ENTRADA FUTURA:
CONDIÇÃO DE ATIVAÇÃO:
STOP LOSS:
TAKE PROFIT 1:
TAKE PROFIT 2:
RISCO/RETORNO:

Os níveis devem respeitar
a estrutura e a escala de preços.

Se não conseguires ler os preços,
escreve:
INDETERMINÁVEL PELA IMAGEM.

Não inventes números.

===============================
7. DECISÃO FINAL
===============================

Responde obrigatoriamente:

ATIVO:
TIMEFRAME:
QUALIDADE DO SCREENSHOT:

TENDÊNCIA PRINCIPAL:
MOVIMENTO ATUAL:
LEITURA DAS VELAS:

ZIG ZAG:
FRACTALS:
MACD:
RSI:
MÉDIAS MÓVEIS:

SUPORTE:
RESISTÊNCIA:

FORÇA BUY:
FORÇA SELL:

DIREÇÃO COM MAIOR FORÇA:

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

DECISÃO FINAL: BUY / SELL / AGUARDAR

JUSTIFICAÇÃO:
CONDIÇÃO NECESSÁRIA PARA ENTRAR:

===============================
REGRAS FINAIS
===============================

- Nunca omitas os cenários BUY e SELL.
- Nunca respondas somente AGUARDAR.
- Explica sempre a razão da decisão.
- Não inventes preços.
- Não inventes indicadores.
- Não confundas correção com reversão.
- Não prometas lucros.
- Usa português simples e direto.
- Considera a qualidade do screenshot.
- Não trates pontuações como probabilidades.
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

    encoded_image = base64.b64encode(
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
                            "url":
                            f"data:image/jpeg;base64,{encoded_image}"
                        }
                    }

                ]
            }

        ],

        "temperature": 0.1,

        "max_tokens": 3500
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

        raise RuntimeError(
            "A IA não devolveu uma resposta."
        )

    content = choices[0].get(
        "message", {}
    ).get("content", "")

    if isinstance(content, list):

        content = "\n".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict)
        )

    if not str(content).strip():

        raise RuntimeError(
            "A resposta da IA está vazia."
        )

    return str(content).strip()


# ==========================================
# ANALYSIS BUTTON
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
                "A DONCULLER-TRADE47 está a analisar..."
            ):

                result = analyze_chart(
                    image,
                    build_prompt()
                )

                st.session_state["last_result"] = result

                st.session_state["last_asset"] = asset

                st.session_state["last_timeframe"] = timeframe

                st.session_state["last_market"] = market

        except Exception as error:

            st.error(
                f"Erro durante a análise: {error}"
            )


# ==========================================
# RESULTS V3.1
# ==========================================

if "last_result" in st.session_state:

    result = st.session_state["last_result"]

    st.divider()

    st.subheader("📊 RELATÓRIO DE ANÁLISE")

    st.caption(
        f"Ativo: {st.session_state['last_asset']} "
        f"| Timeframe: {st.session_state['last_timeframe']} "
        f"| Mercado: {st.session_state['last_market']}"
    )

    patterns = [

        r"DECIS[AÃ]O FINAL\s*:\s*(BUY|SELL|AGUARDAR)",

        r"SINAL PRINCIPAL\s*:\s*(BUY|SELL|AGUARDAR)",

        r"DIRE[CÇ][AÃ]O FINAL\s*:\s*(BUY|SELL|AGUARDAR)"

    ]

    signal = None

    for pattern in patterns:

        match = re.search(
            pattern,
            result,
            re.IGNORECASE
        )

        if match:

            signal = match.group(1).upper()
            break

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

    elif signal == "AGUARDAR":

        st.markdown(
            '<div class="panel wait">🟡 AGUARDAR</div>',
            unsafe_allow_html=True
        )

    else:

        st.error(
            "A IA não apresentou uma decisão "
            "num formato reconhecido. "
            "O resultado não será classificado "
            "automaticamente como AGUARDAR."
        )

    st.markdown(result)

    st.download_button(
        "⬇️ DESCARREGAR RELATÓRIO",
        data=result,
        file_name="DonCullerTrade47_V3_1.txt",
        mime="text/plain"
    )


# ==========================================
# FOOTER
# ==========================================

st.divider()

st.caption(
    "DONCULLER-TRADE47 · AI CHART ANALYZER · V3.1"
)

st.warning(
    "Esta aplicação analisa screenshots. "
    "Ainda não recebe cotações em tempo real, "
    "não calcula indicadores diretamente de dados OHLC "
    "e não executa operações. "
    "Todos os sinais devem ser testados em conta Demo."
)
