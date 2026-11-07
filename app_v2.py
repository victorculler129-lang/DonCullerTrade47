import os
import re
import base64
from io import BytesIO

import requests
import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError


# =========================================================
# DONCULLER-TRADE47 V4.1
# AI TRADING CHART ANALYZER
# =========================================================

st.set_page_config(
    page_title="DONCULLER-TRADE47",
    page_icon="🦁",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ======================== DESIGN ==========================

st.markdown(
    """
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
        padding-top: 1.2rem;
    }

    .dc-panel {
        background: #0d2033;
        border: 1px solid #23415e;
        border-radius: 15px;
        padding: 20px;
        margin-bottom: 15px;
    }

    .dc-buy {
        color: #25d887;
        font-size: 30px;
        font-weight: 800;
    }

    .dc-sell {
        color: #ff6874;
        font-size: 30px;
        font-weight: 800;
    }

    .dc-wait {
        color: #ffc857;
        font-size: 30px;
        font-weight: 800;
    }

    div.stButton > button {
        background: #176b50;
        color: white;
        border: 0;
        border-radius: 10px;
        min-height: 3rem;
        font-weight: 700;
    }

    div.stButton > button:hover {
        background: #208362;
        color: white;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


st.markdown(
    """
    <div class="dc-panel">
        <h1>🦁 DONCULLER-TRADE47</h1>
        <p>AI TRADING CHART ANALYZER · V4.1</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ===================== API CONFIGURATION ==================

API_KEY = os.getenv(
    "OPENROUTER_API_KEY",
    ""
).strip()

MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "nvidia/nemotron-3.5-super-vl:free"
).strip()

API_URL = "https://openrouter.ai/api/v1/chat/completions"


# ========================= ASSETS ==========================

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
    "Step Index",
]

FOREX_ASSETS = [
    "EUR/USD",
    "GBP/USD",
    "XAU/USD",
]


# ===================== USER SETTINGS ======================

with st.sidebar:

    st.header("⚙️ CONFIGURAÇÃO")

    market = st.radio(
        "Mercado",
        [
            "Índices sintéticos",
            "Forex",
        ]
    )

    asset_list = (
        SYNTHETIC_ASSETS
        if market == "Índices sintéticos"
        else FOREX_ASSETS
    )

    asset = st.selectbox(
        "Ativo",
        asset_list
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
            "D1",
        ],
        index=1
    )

    platform = st.selectbox(
        "Plataforma",
        [
            "Deriv MT5",
            "TradingView",
            "Outra",
        ]
    )

    st.caption("V4.1 · Análise visual de screenshots")

    st.divider()

    st.caption(
        f"Modelo configurado: {MODEL}"
    )


# ========================= PROMPT ==========================

def build_prompt():

    return f"""
És o analista técnico da DONCULLER-TRADE47 V4.1.

Analisa apenas o gráfico apresentado na imagem.

Não tens acesso a cotações em tempo real,
ao histórico OHLC nem aos dados internos dos indicadores.

CONTEXTO

Ativo: {asset}
Mercado: {market}
Timeframe: {timeframe}
Plataforma: {platform}

REGRAS DE LEITURA

1. Verifica se o screenshot é legível.
Confirma se os preços podem ser lidos.

2. Analisa:

- Topos e fundos.
- Tendência.
- Impulsos.
- Correções.
- Suportes.
- Resistências.
- Rompimentos.
- Falsos rompimentos.

3. Analisa as velas:

- Corpos.
- Pavios.
- Rejeições.
- Engolfo.
- Doji.
- Sequências.

4. INDICADORES:

ZIG ZAG:
Analisa topos, fundos e mudanças de direção
quando estiver visível.

FRACTALS:
Analisa fractals superiores e inferiores
quando estiverem visíveis.

MACD:
Analisa cruzamentos e direção
quando estiver visível.

RSI:
Analisa força e divergências
quando estiver visível.

MÉDIAS MÓVEIS:
Analisa inclinação e cruzamentos
quando estiverem visíveis.

Não inventes valores.

Se não estiver visível, escreve:
Não visível no screenshot.

5. FORÇA BUY E SELL

As forças BUY e SELL são notas técnicas
subjetivas de 0 a 100.

Não são probabilidades reais de lucro.

6. DIREÇÃO

Não escolhas AGUARDAR automaticamente.

Escolhe BUY quando existir evidência suficiente
de uma oportunidade de compra.

Escolhe SELL quando existir evidência suficiente
de uma oportunidade de venda.

Escolhe AGUARDAR quando não existirem
confirmações suficientes.

Nunca forces operações.

7. PREÇOS

Não inventes preços.

Se não conseguires ler os preços,
escreve:

INDETERMINÁVEL PELA IMAGEM.

8. ENTRADA

A entrada futura deve depender
de uma condição observável.

9. GESTÃO DE RISCO

Define SL além da invalidação estrutural.

Define TP em níveis tecnicamente plausíveis.

10. Não prometas lucros.

FORMATO OBRIGATÓRIO

QUALIDADE DO SCREENSHOT:

TENDÊNCIA:

ESTRUTURA E VELAS:

ZIG ZAG:

FRACTALS:

MACD:

RSI:

MÉDIAS MÓVEIS:

SUPORTE:

RESISTÊNCIA:

FORÇA BUY (0-100):

FORÇA SELL (0-100):

DIREÇÃO COM MAIOR EVIDÊNCIA:

CENÁRIO BUY

Entrada/zona:
Ativação:
SL:
TP1:
TP2:
Risco/retorno estimado:

CENÁRIO SELL

Entrada/zona:
Ativação:
SL:
TP1:
TP2:
Risco/retorno estimado:

DECISÃO FINAL: BUY / SELL / AGUARDAR

JUSTIFICAÇÃO:

O QUE INVALIDA A LEITURA:

Se um cenário não for tecnicamente válido,
escreve:

SEM CONFIGURAÇÃO VÁLIDA.

Usa português simples, direto e operacional.

Não acrescentes explicações fora deste formato.
"""


# ================= IMAGE PROCESSING ======================

def prepare_image(uploaded):

    try:

        uploaded.seek(0)

        img = Image.open(uploaded)

        img = ImageOps.exif_transpose(img).convert("RGB")

    except (
        UnidentifiedImageError,
        OSError,
        ValueError
    ) as exc:

        raise ValueError(
            "O ficheiro não é uma imagem válida."
        ) from exc

    if img.width < 300 or img.height < 200:

        raise ValueError(
            "A imagem é demasiado pequena. "
            "Envia um screenshot mais nítido."
        )

    img.thumbnail(
        (1800, 1800),
        Image.Resampling.LANCZOS
    )

    return img


# ================= RESPONSE EXTRACTION ===================

def extract_response_text(data):

    choices = data.get("choices") or []

    if not choices:

        api_error = data.get("error") or {}

        raise RuntimeError(
            f"A API não devolveu escolhas: {api_error}"
        )

    choice = choices[0] or {}

    message = choice.get("message") or {}

    content = message.get("content")

    if isinstance(content, str) and content.strip():

        return content.strip()

    if isinstance(content, list):

        text_parts = []

        for item in content:

            if isinstance(item, str):

                text_parts.append(item)

            elif isinstance(item, dict):

                if item.get("type") in (
                    "text",
                    "output_text"
                ):

                    text_parts.append(
                        item.get("text", "")
                    )

        result = "\n".join(
            part for part in text_parts if part
        ).strip()

        if result:

            return result

    finish_reason = choice.get(
        "finish_reason",
        "não informado"
    )

    details = {
        "finish_reason": finish_reason,
        "message_keys": list(message.keys()),
        "usage": data.get("usage"),
    }

    if finish_reason == "length":

        raise RuntimeError(
            "O modelo esgotou o limite de tokens "
            "antes de produzir a resposta final. "
            "Tenta novamente. "
            + str(details)
        )

    raise RuntimeError(
        "O OpenRouter respondeu, mas não enviou "
        "texto final. Diagnóstico: "
        + str(details)
    )


# ================= IMAGE ANALYSIS ========================

def analyze_chart(chart_image, prompt):

    if not API_KEY:

        raise RuntimeError(
            "Falta OPENROUTER_API_KEY no Render."
        )

    buffer = BytesIO()

    chart_image.save(
        buffer,
        format="JPEG",
        quality=88,
        optimize=True
    )

    encoded = base64.b64encode(
        buffer.getvalue()
    ).decode("ascii")

    payload = {

        "model": MODEL,

        "messages": [

            {
                "role": "user",

                "content": [

                    {
                        "type": "text",
                        "text": prompt,
                    },

                    {
                        "type": "image_url",

                        "image_url": {

                            "url": (
                                f"data:image/jpeg;base64,{encoded}"
                            )

                        }
                    }

                ]
            }

        ],

        "reasoning": {
            "enabled": False
        },

        "temperature": 0.2,

        "max_tokens": 4500,

        "stream": False,

    }

    headers = {

        "Authorization": f"Bearer {API_KEY}",

        "Content-Type": "application/json",

        "X-Title": "DONCULLER-TRADE47",

    }

    try:

        response = requests.post(
            API_URL,
            headers=headers,
            json=payload,
            timeout=(20, 180)
        )

    except requests.Timeout as exc:

        raise RuntimeError(
            "O OpenRouter demorou demasiado a responder. "
            "Tenta novamente."
        ) from exc

    except requests.RequestException as exc:

        raise RuntimeError(
            f"Falha de ligação ao OpenRouter: {exc}"
        ) from exc

    if response.status_code == 401:

        raise RuntimeError(
            "OpenRouter 401: chave API não reconhecida. "
            "Não publiques a chave."
        )

    if response.status_code == 402:

        raise RuntimeError(
            "OpenRouter 402: créditos ou acesso "
            "insuficientes para este modelo."
        )

    if response.status_code == 403:

        raise RuntimeError(
            "OpenRouter 403: pedido não autorizado "
            "ou chave sem permissões."
        )

    if response.status_code == 404:

        raise RuntimeError(
            f"OpenRouter 404: modelo ou endpoint "
            f"não encontrado ({MODEL})."
        )

    if response.status_code == 429:

        raise RuntimeError(
            "OpenRouter 429: limite de pedidos atingido. "
            "Aguarda e tenta novamente."
        )

    if response.status_code >= 500:

        raise RuntimeError(
            f"OpenRouter temporariamente indisponível "
            f"({response.status_code})."
        )

    if not response.ok:

        try:

            body = response.json()

            detail = (
                (body.get("error") or {}).get("message")
                or str(body)[:1000]
            )

        except ValueError:

            detail = response.text[:1000]

        raise RuntimeError(
            f"OpenRouter {response.status_code}: {detail}"
        )

    try:

        data = response.json()

    except ValueError as exc:

        raise RuntimeError(
            "O OpenRouter devolveu uma resposta "
            "que não é JSON válido."
        ) from exc

    return extract_response_text(data)


# ================= SIGNAL DETECTION ======================

def detect_signal(report_text):

    patterns = [

        r"DECIS[AÃ]O\s+FINAL\s*:\s*(BUY|SELL|AGUARDAR)\b",

        r"SINAL\s+PRINCIPAL\s*:\s*(BUY|SELL|AGUARDAR)\b",

        r"DIRE[CÇ][AÃ]O\s+FINAL\s*:\s*(BUY|SELL|AGUARDAR)\b",

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            report_text,
            re.IGNORECASE
        )

        if match:

            return match.group(1).upper()

    return None


# ================= SCREENSHOT AREA =======================

left, right = st.columns([1.35, 1])

with left:

    st.markdown(
        """
        <div class="dc-panel">
            <h3>📷 GRÁFICO PARA ANÁLISE</h3>
            <p>Envia uma captura nítida, com velas
            e escala de preços visíveis.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader(
        "Carregar screenshot",
        type=[
            "png",
            "jpg",
            "jpeg"
        ],
        key="chart_upload"
    )

    chart_image = None

    if uploaded_file is not None:

        try:

            chart_image = prepare_image(
                uploaded_file
            )

            st.image(
                chart_image,
                caption=(
                    f"{asset} · {timeframe} · {platform}"
                ),
                use_container_width=True
            )

        except ValueError as exc:

            st.error(str(exc))


with right:

    st.markdown(
        """
        <div class="dc-panel">
            <h3>📊 MOTOR DE ANÁLISE</h3>

            <p>🟢 BUY — Comprar</p>
            <p>🔴 SELL — Vender</p>
            <p>🟡 AGUARDAR — Sem confirmação suficiente</p>

            <hr>

            <p>Leitura visual de velas, estrutura
            e indicadores que estejam visíveis.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.info(
        "A análise usa apenas a imagem enviada. "
        "Indicadores que não estejam visíveis "
        "não podem ser calculados com rigor."
    )


# ===================== ANALYSIS BUTTON ===================

if st.button(
    "🦁 ANALISAR GRÁFICO",
    use_container_width=True,
    disabled=(chart_image is None),
):

    try:

        with st.spinner(
            "A DONCULLER-TRADE47 está a analisar..."
        ):

            report = analyze_chart(
                chart_image,
                build_prompt()
            )

        st.session_state["last_result"] = report

        st.session_state["last_asset"] = asset

        st.session_state["last_timeframe"] = timeframe

        st.session_state["last_market"] = market

        st.session_state["last_platform"] = platform

    except Exception as exc:

        st.error(
            f"Erro durante a análise: {exc}"
        )


# ======================== RESULTS =========================

if "last_result" in st.session_state:

    report = st.session_state["last_result"]

    signal = detect_signal(report)

    st.divider()

    st.subheader(
        "📊 RELATÓRIO DE ANÁLISE"
    )

    st.caption(
        f"Ativo: {st.session_state.get('last_asset', '')} | "
        f"Timeframe: {st.session_state.get('last_timeframe', '')} | "
        f"Mercado: {st.session_state.get('last_market', '')} | "
        f"Plataforma: {st.session_state.get('last_platform', '')}"
    )

    if signal == "BUY":

        st.markdown(
            '<div class="dc-panel dc-buy">🟢 BUY</div>',
            unsafe_allow_html=True
        )

    elif signal == "SELL":

        st.markdown(
            '<div class="dc-panel dc-sell">🔴 SELL</div>',
            unsafe_allow_html=True
        )

    elif signal == "AGUARDAR":

        st.markdown(
            '<div class="dc-panel dc-wait">🟡 AGUARDAR</div>',
            unsafe_allow_html=True
        )

    else:

        st.warning(
            "A IA não apresentou uma decisão "
            "no formato esperado. "
            "Não consideres o sinal validado."
        )

    st.markdown(report)

    st.download_button(
        "⬇️ DESCARREGAR RELATÓRIO",
        data=report,
        file_name="DonCullerTrade47_V4_1.txt",
        mime="text/plain",
        use_container_width=True
    )


# ========================= FOOTER =========================

st.divider()

st.caption(
    "DONCULLER-TRADE47 · AI CHART ANALYZER · V4.1"
)

st.warning(
    "Esta versão analisa screenshots; não recebe cotações "
    "em tempo real, não calcula indicadores a partir de dados OHLC "
    "e não executa operações. Os níveis lidos visualmente "
    "podem estar imprecisos. Testa em conta Demo "
    "e confirma os preços diretamente na plataforma."
)
