import os
import base64
import re
from io import BytesIO
from datetime import datetime, timezone

import requests
import streamlit as st
from PIL import Image


# =====================================================
# DONCULLER-TRADE47 V2
# AI TRADING CHART ANALYZER
# =====================================================

st.set_page_config(
    page_title="DONCULLER-TRADE47",
    page_icon="🦁",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =====================================================
# DESIGN
# =====================================================

st.markdown("""
<style>

.stApp {
    background-color: #071321;
    color: #edf3fa;
}

section[data-testid="stSidebar"] {
    background-color: #0b1b2d;
    border-right: 1px solid #1d3550;
}

.block-container {
    max-width: 1250px;
    padding-top: 1.5rem;
}

.hero {
    background: linear-gradient(120deg,#102944,#091827);
    border: 1px solid #23415e;
    border-radius: 18px;
    padding: 25px;
    margin-bottom: 20px;
}

.hero h1 {
    color: white;
    font-size: 2rem;
}

.hero p {
    color: #a9bfd4;
}

.panel {
    background: #0d2033;
    border: 1px solid #203b55;
    border-radius: 15px;
    padding: 18px;
    margin-bottom: 12px;
}

.buy {
    color: #25d887;
    font-size: 2.2rem;
    font-weight: 850;
}

.sell {
    color: #ff5c68;
    font-size: 2.2rem;
    font-weight: 850;
}

.wait {
    color: #ffc857;
    font-size: 2.2rem;
    font-weight: 850;
}

.muted {
    color: #a9bfd4;
}

div.stButton > button {
    background: #176b50;
    color: white;
    border: 1px solid #27966f;
    border-radius: 10px;
    min-height: 3rem;
    font-weight: 750;
}

div.stButton > button:hover {
    background: #1b805e;
    color: white;
}

</style>
""", unsafe_allow_html=True)


# =====================================================
# HEADER
# =====================================================

st.markdown("""
<div class="hero">
    <h1>🦁 DONCULLER-TRADE47</h1>
    <p>AI CHART ANALYZER · SYNTHETIC & FOREX · V2</p>
</div>
""", unsafe_allow_html=True)


# =====================================================
# API CONFIGURATION
# =====================================================

API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()

MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "openrouter/free"
).strip()

API_URL = "https://openrouter.ai/api/v1/chat/completions"


# =====================================================
# ASSETS
# =====================================================

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


# =====================================================
# SIDEBAR
# =====================================================

with st.sidebar:

    st.header("⚙️ CONFIGURAÇÃO")

    market = st.radio(
        "Mercado",
        [
            "Índices sintéticos",
            "Forex"
        ]
    )

    if market == "Índices sintéticos":
        assets = SYNTHETIC_ASSETS
    else:
        assets = FOREX_ASSETS

    asset = st.selectbox(
        "Ativo",
        assets
    )

    timeframe = st.selectbox(
        "Timeframe",
        [
            "M1",
            "M5",
            "M15",
            "M30",
            "H1",
            "H4",
            "D1"
        ],
        index=1
    )

    platform = st.selectbox(
        "Plataforma",
        [
            "Deriv MT5",
            "TradingView",
            "Outra"
        ]
    )

    st.divider()

    if market == "Índices sintéticos":
        st.success("Motor: SYNTHETIC AI")
    else:
        st.info("Motor: FOREX AI")

    st.caption("DONCULLER-TRADE47 V2")


# =====================================================
# UPLOAD SECTION
# =====================================================

left, right = st.columns([1.4, 1])

with left:

    st.markdown("""
    <div class="panel">
        <h3>📷 GRÁFICO PARA ANÁLISE</h3>
        <p class="muted">
        Envia uma captura nítida do gráfico.
        Procura deixar visíveis as velas,
        os preços e os indicadores.
        </p>
    </div>
    """, unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        "Carregar screenshot",
        type=["png", "jpg", "jpeg"]
    )

    image = None

    if uploaded_file is not None:

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
        <h3>📊 SISTEMA DE ANÁLISE</h3>
        <p>🟢 BUY — Comprar</p>
        <p>🔴 SELL — Vender</p>
        <p>🟡 AGUARDAR — Sem confirmação</p>
        <hr>
        <p class="muted">
        A análise considera estrutura,
        Price Action e indicadores visíveis.
        </p>
    </div>
    """, unsafe_allow_html=True)


# =====================================================
# ANALYSIS PROMPT
# =====================================================

def build_prompt():

    if market == "Índices sintéticos":

        market_rules = """
        Este é um índice sintético da Deriv.

        Identifica corretamente o tipo de ativo.

        Não assumes que um spike vai acontecer
        apenas porque o gráfico está lateralizado.

        Não inventes ciclos ou padrões.
        """

    else:

        market_rules = """
        Este é um instrumento Forex.

        Considera tendência, estrutura,
        sessões de mercado e Price Action.

        Não inventes notícias económicas
        nem acontecimentos externos.
        """

    prompt = f"""
És o analista técnico da DONCULLER-TRADE47.

ATIVO: {asset}
MERCADO: {market}
TIMEFRAME: {timeframe}
PLATAFORMA: {platform}

{market_rules}

ANALISA O SCREENSHOT.

1. Identifica a tendência principal.
2. Analisa a estrutura do mercado.
3. Identifica máximos e mínimos.
4. Analisa Price Action.
5. Identifica suportes e resistências.
6. Verifica Zig Zag, se estiver visível.
7. Verifica Fractals, se estiverem visíveis.
8. Analisa MACD, se estiver visível.
9. Analisa RSI, se estiver visível.
10. Verifica médias móveis, se estiverem visíveis.

Não inventes valores de indicadores.

COMPARAÇÃO:

Avalia o cenário BUY e o cenário SELL.

Escolhe apenas uma direção principal
quando existir evidência técnica suficiente.

Não forces uma entrada.

ENTRADA:

Indica uma zona de entrada futura
e a condição necessária para ativá-la.

STOP LOSS:

Indica um nível de invalidação técnica.

TAKE PROFIT:

Indica um alvo coerente com a estrutura.

Se os preços não estiverem legíveis,
escreve "indeterminável pela imagem".

A pontuação técnica não representa
uma probabilidade real de lucro.

RESPONDE NESTE FORMATO:

ATIVO:
TIMEFRAME:
QUALIDADE DA IMAGEM:

TENDÊNCIA:
ESTRUTURA:
PRICE ACTION:

ZIG ZAG:
FRACTALS:
MACD:
RSI:
MÉDIAS MÓVEIS:

SUPORTE:
RESISTÊNCIA:

PONTUAÇÃO BUY:
PONTUAÇÃO SELL:

SINAL PRINCIPAL: BUY / SELL / AGUARDAR

ENTRADA FUTURA:
CONDIÇÃO DE ATIVAÇÃO:

STOP LOSS:
TAKE PROFIT:
RISCO/RETORNO:

INVALIDAÇÃO:
JUSTIFICAÇÃO:

LIMITAÇÕES:

Usa português simples e direto.
Não prometas resultados.
Não inventes preços.
"""

    return prompt


# =====================================================
# OPENROUTER API
# =====================================================

def analyze_chart(chart_image, prompt):

    buffer = BytesIO()

    chart_image.save(
        buffer,
        format="JPEG",
        quality=88
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

        "max_tokens": 1600
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
        timeout=120
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


# =====================================================
# ANALYSIS BUTTON
# =====================================================

if st.button(
    "🦁 ANALISAR GRÁFICO",
    use_container_width=True,
    disabled=(image is None)
):

    if not API_KEY:

        st.error(
            "A variável OPENROUTER_API_KEY "
            "não foi encontrada no Render."
        )

    else:

        try:

            with st.spinner(
                "A DONCULLER-TRADE47 está a analisar..."
            ):

                prompt = build_prompt()

                result = analyze_chart(
                    image,
                    prompt
                )

                st.session_state["last_result"] = result

                st.session_state["last_asset"] = asset

                st.session_state["last_timeframe"] = timeframe

                st.session_state["last_market"] = market

                st.session_state["last_timestamp"] = (
                    datetime.now(timezone.utc).isoformat()
                )

        except requests.exceptions.Timeout:

            st.error(
                "A análise demorou demasiado tempo. "
                "Tenta novamente."
            )

        except requests.exceptions.RequestException as error:

            st.error(
                f"Erro de ligação: {error}"
            )

        except Exception as error:

            st.error(
                f"Erro durante a análise: {error}"
            )


# =====================================================
# RESULTS
# =====================================================

if "last_result" in st.session_state:

    result = st.session_state["last_result"]

    st.divider()

    st.subheader("📊 RELATÓRIO DE ANÁLISE")

    st.caption(
        f"Ativo: {st.session_state['last_asset']} "
        f"| Timeframe: {st.session_state['last_timeframe']} "
        f"| Mercado: {st.session_state['last_market']}"
    )

    # Identifica a linha do sinal principal
    signal_match = re.search(
        r"SINAL PRINCIPAL\s*:\s*(BUY|SELL|AGUARDAR)",
        result,
        re.IGNORECASE
    )

    signal = (
        signal_match.group(1).upper()
        if signal_match
        else "AGUARDAR"
    )

    if signal == "BUY":

        st.markdown("""
        <div class="panel">
            <div class="buy">🟢 BUY</div>
            <p>Possível oportunidade de compra.</p>
        </div>
        """, unsafe_allow_html=True)

    elif signal == "SELL":

        st.markdown("""
        <div class="panel">
            <div class="sell">🔴 SELL</div>
            <p>Possível oportunidade de venda.</p>
        </div>
        """, unsafe_allow_html=True)

    else:

        st.markdown("""
        <div class="panel">
            <div class="wait">🟡 AGUARDAR</div>
            <p>Sem confirmação técnica suficiente.</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown(result)

    st.download_button(
        label="⬇️ DESCARREGAR RELATÓRIO",
        data=result,
        file_name="DonCullerTrade47_relatorio.txt",
        mime="text/plain"
    )


# =====================================================
# FOOTER
# =====================================================

st.divider()

st.caption(
    "DONCULLER-TRADE47 · AI CHART ANALYZER · V2"
)

st.warning(
    "Esta versão analisa screenshots. "
    "Ainda não recebe cotações em tempo real, "
    "não calcula indicadores a partir de dados OHLC "
    "e não executa operações. "
    "Testa todos os sinais em conta Demo."
)
