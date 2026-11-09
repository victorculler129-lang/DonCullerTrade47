import os
import re
import base64
from io import BytesIO
from datetime import datetime

import requests
import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError

# =====================================================
# DONCULLER-TRADE47 V9.0
# =====================================================

st.set_page_config(
    page_title="DONCULLER-TRADE47",
    page_icon="🦁",
    layout="wide"
)

API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()

MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "nvidia/nemotron-3.5-super-vl:free"
).strip()

API_URL = "https://openrouter.ai/api/v1/chat/completions"

# =====================================================
# INTERFACE
# =====================================================

st.markdown("""
<style>

.stApp {
    background-color: #071321;
    color: #edf3fa;
}

.block-container {
    max-width: 1150px;
    padding-top: 1.2rem;
}

section[data-testid="stSidebar"] {
    background-color: #0b1b2d;
}

.header {
    background: linear-gradient(120deg,#0b2035,#123858);
    border: 1px solid #294c6a;
    border-radius: 16px;
    padding: 22px;
    margin-bottom: 20px;
}

.header p {
    color: #a8bfd2;
    margin-bottom: 0;
}

.card {
    background: #0d2033;
    border: 1px solid #29445e;
    border-radius: 14px;
    padding: 18px;
    margin: 12px 0;
}

.buy {
    color: #28dc91;
    font-size: 36px;
    font-weight: 900;
}

.sell {
    color: #ff6675;
    font-size: 36px;
    font-weight: 900;
}

.wait {
    color: #ffd166;
    font-size: 36px;
    font-weight: 900;
}

.small {
    color: #9eb6ca;
    font-size: 12px;
    text-transform: uppercase;
}

div.stButton > button {
    background: #14734f;
    color: white;
    border: none;
    border-radius: 10px;
    min-height: 3rem;
    font-weight: bold;
}

div.stButton > button:hover {
    background: #208d65;
    color: white;
}

</style>
""", unsafe_allow_html=True)


st.markdown("""
<div class="header">
    <h1>🦁 DONCULLER-TRADE47</h1>
    <p>AI TRADING CHART ANALYZER · V9.0</p>
</div>
""", unsafe_allow_html=True)


# =====================================================
# CONFIGURAÇÃO DOS ATIVOS
# =====================================================

with st.sidebar:

    st.header("⚙️ CONFIGURAÇÃO")

    market = st.selectbox(
        "Mercado",
        ["Índices Sintéticos", "Forex"]
    )

    if market == "Índices Sintéticos":

        assets = [
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

    else:

        assets = [
            "EUR/USD",
            "GBP/USD",
            "XAU/USD"
        ]

    asset = st.selectbox("Ativo", assets)

    timeframe = st.selectbox(
        "Timeframe",
        ["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
        index=2
    )

    platform = st.selectbox(
        "Plataforma",
        ["Deriv MT5", "TradingView", "Outra"]
    )

    st.divider()

    st.caption("Motor de análise visual")
    st.caption("Modelo: " + MODEL)


# =====================================================
# PROMPT PRINCIPAL
# =====================================================

def create_prompt():

    return f"""
És o analista técnico profissional da DONCULLER-TRADE47.

Analisa a imagem do gráfico enviada pelo utilizador.

INFORMAÇÕES:

Ativo: {asset}
Mercado: {market}
Timeframe: {timeframe}
Plataforma: {platform}

OBJETIVO:

Encontrar a melhor oportunidade futura entre BUY e SELL.

Não favoreças nenhuma direção.
Compara os dois cenários utilizando os mesmos critérios.

ANÁLISE TÉCNICA:

1. Tendência principal.
2. Estrutura do mercado.
3. Topos e fundos.
4. Suportes e resistências.
5. Velas e padrões de reversão.
6. Rompimentos e retestes.
7. Zig Zag, se estiver visível.
8. Fractals, se estiverem visíveis.
9. MACD, se estiver visível.
10. RSI, se estiver visível.
11. Médias móveis, se estiverem visíveis.

Não inventes indicadores que não aparecem na imagem.

CENÁRIO BUY:

Procura:
- Rejeição de suporte.
- Fundos ascendentes.
- Recuperação de estrutura.
- Rompimento de resistência.
- Reteste positivo.
- Fractal inferior confirmado.
- Confirmação do MACD, se visível.

CENÁRIO SELL:

Procura:
- Rejeição de resistência.
- Topos descendentes.
- Perda de suporte.
- Rompimento descendente.
- Reteste negativo.
- Fractal superior confirmado.
- Confirmação do MACD, se visível.

ÍNDICES SINTÉTICOS:

Não escolhas BUY ou SELL apenas pelo nome Boom, Crash,
Jump ou Step.

Analisa o comportamento efetivamente visível.

DECISÃO:

Compara a força dos cenários BUY e SELL.

Se BUY tiver melhores confirmações, escolhe BUY.

Se SELL tiver melhores confirmações, escolhe SELL.

Se não existir uma configuração tecnicamente válida,
escolhe AGUARDAR.

Não escolhas sempre AGUARDAR.
Não escolhas sempre SELL.
Não escolhas sempre BUY.

A confiança representa uma avaliação técnica subjetiva,
não uma probabilidade garantida de lucro.

ENTRADA:

Indica preço ou zona de entrada quando a escala estiver legível.
Também podes indicar uma entrada condicional após confirmação.

STOP LOSS:

Coloca o SL onde a estrutura da operação fica invalidada.

TAKE PROFIT:

Apresenta TP1 e TP2 tecnicamente plausíveis.

Não inventes preços.
Se não conseguires ler a escala, escreve "PREÇO NÃO LEGÍVEL".

FORMATO OBRIGATÓRIO:

ATIVO:
TIMEFRAME:

DIREÇÃO FINAL: BUY / SELL / AGUARDAR

FORÇA BUY: __/100
FORÇA SELL: __/100

CONFIANÇA DA ANÁLISE: __/100

ENTRADA:
ATIVAÇÃO:
STOP LOSS:
TAKE PROFIT 1:
TAKE PROFIT 2:

RISCO/RETORNO:

TENDÊNCIA:
ESTRUTURA:
SUPORTE:
RESISTÊNCIA:

ZIG ZAG:
FRACTALS:
MACD:
RSI:
MÉDIAS MÓVEIS:

CONFIRMAÇÕES:
1.
2.
3.

CENÁRIO CONTRÁRIO:
INVALIDAÇÃO:

RESUMO OPERACIONAL:

Responde em português simples.
Sê direto e profissional.
Evita explicações desnecessárias.
Não acrescentes texto fora do relatório.
"""


# =====================================================
# PREPARAR IMAGEM
# =====================================================

def prepare_image(uploaded):

    try:

        uploaded.seek(0)

        image = Image.open(uploaded)

        image = ImageOps.exif_transpose(image)

        image = image.convert("RGB")

        if image.width < 250 or image.height < 180:

            raise ValueError(
                "Screenshot demasiado pequeno."
            )

        image.thumbnail(
            (1800, 1800),
            Image.Resampling.LANCZOS
        )

        return image

    except (UnidentifiedImageError, OSError, ValueError) as error:

        raise ValueError(
            "Não foi possível abrir a imagem. "
            "Envia um screenshot PNG ou JPG válido."
        ) from error


# =====================================================
# CONVERTER IMAGEM
# =====================================================

def encode_image(image):

    buffer = BytesIO()

    image.save(
        buffer,
        format="JPEG",
        quality=90,
        optimize=True
    )

    encoded = base64.b64encode(
        buffer.getvalue()
    ).decode("utf-8")

    return "data:image/jpeg;base64," + encoded


# =====================================================
# EXTRAIR RESPOSTA DA IA
# =====================================================

def extract_response(data):

    choices = data.get("choices")

    if not choices:

        raise RuntimeError(
            "O modelo não devolveu resultados: "
            + str(data)[:1200]
        )

    message = choices[0].get("message", {})

    content = message.get("content")

    if isinstance(content, str):

        if content.strip():

            return content.strip()

    if isinstance(content, list):

        parts = []

        for item in content:

            if isinstance(item, str):

                parts.append(item)

            elif isinstance(item, dict):

                text_part = item.get("text")

                if text_part:

                    parts.append(text_part)

        result = "\n".join(parts).strip()

        if result:

            return result

    refusal = message.get("refusal")

    if refusal:

        raise RuntimeError(
            "O modelo recusou a análise: " + str(refusal)
        )

    finish_reason = choices[0].get("finish_reason")

    raise RuntimeError(
        "O modelo não enviou texto utilizável. "
        "Finalização: " + str(finish_reason)
        + ". Resposta técnica: "
        + str(message)[:1200]
    )


# =====================================================
# ANÁLISE DO GRÁFICO
# =====================================================

def analyze_chart(image):

    if not API_KEY:

        raise RuntimeError(
            "OPENROUTER_API_KEY não encontrada no Render."
        )

    image_url = encode_image(image)

    payload = {

        "model": MODEL,

        "messages": [

            {

                "role": "user",

                "content": [

                    {
                        "type": "text",
                        "text": create_prompt()
                    },

                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url
                        }
                    }

                ]

            }

        ],

        "temperature": 0.15,

        "max_tokens": 2500,

        "stream": False

    }

    headers = {

        "Authorization": f"Bearer {API_KEY}",

        "Content-Type": "application/json",

        "HTTP-Referer": "https://doncullertrade47.onrender.com",

        "X-Title": "DONCULLER-TRADE47"

    }

    try:

        response = requests.post(
            API_URL,
            headers=headers,
            json=payload,
            timeout=(20, 180)
        )

    except requests.Timeout:

        raise RuntimeError(
            "O modelo demorou demasiado. Tenta novamente."
        )

    except requests.RequestException as error:

        raise RuntimeError(
            "Erro de ligação ao OpenRouter: " + str(error)
        )

    try:

        data = response.json()

    except ValueError:

        raise RuntimeError(
            "Resposta inválida do servidor: "
            + response.text[:1000]
        )

    if not response.ok:

        error = data.get("error", {})

        if isinstance(error, dict):

            detail = error.get(
                "message",
                str(error)
            )

        else:

            detail = str(error)

        raise RuntimeError(
            f"OpenRouter HTTP {response.status_code}: {detail}"
        )

    return extract_response(data)


# =====================================================
# IDENTIFICAR DECISÃO
# =====================================================

def get_direction(report):

    match = re.search(
        r"(?im)^\s*DIREÇÃO FINAL\s*:\s*(BUY|SELL|AGUARDAR)\b",
        report
    )

    if match:

        return match.group(1).upper()

    return "INDEFINIDA"


# =====================================================
# CARREGAR SCREENSHOT
# =====================================================

st.subheader("📷 CARREGAR GRÁFICO")

uploaded = st.file_uploader(
    "Seleciona o screenshot do teu gráfico",
    type=["png", "jpg", "jpeg", "webp"]
)

image = None

if uploaded:

    if uploaded.size > 8 * 1024 * 1024:

        st.error(
            "A imagem ultrapassa 8 MB. "
            "Envia uma imagem mais leve."
        )

    else:

        try:

            image = prepare_image(uploaded)

            st.image(
                image,
                caption=f"{asset} | {timeframe}",
                use_container_width=True
            )

        except ValueError as error:

            st.error(str(error))


# =====================================================
# EXECUTAR ANÁLISE
# =====================================================

st.divider()

if st.button(
    "🦁 ANALISAR GRÁFICO",
    disabled=image is None,
    use_container_width=True
):

    try:

        with st.spinner(
            "A analisar o gráfico e a comparar BUY com SELL..."
        ):

            result = analyze_chart(image)

        st.session_state["report"] = result

        st.session_state["direction"] = get_direction(result)

        st.session_state["analysis_time"] = (
            datetime.now().strftime("%d/%m/%Y %H:%M")
        )

        st.session_state["analysis_asset"] = asset

        st.session_state["analysis_timeframe"] = timeframe

    except Exception as error:

        st.error(str(error))


# =====================================================
# MOSTRAR RESULTADO
# =====================================================

if "report" in st.session_state:

    report = st.session_state["report"]

    direction = st.session_state["direction"]

    st.divider()

    st.subheader("📊 RESULTADO DA ANÁLISE")

    st.caption(
        st.session_state.get("analysis_asset", "")
        + " | "
        + st.session_state.get("analysis_timeframe", "")
        + " | "
        + st.session_state["analysis_time"]
    )

    if direction == "BUY":

        st.markdown(
            '<div class="card buy">🟢 BUY</div>',
            unsafe_allow_html=True
        )

    elif direction == "SELL":

        st.markdown(
            '<div class="card sell">🔴 SELL</div>',
            unsafe_allow_html=True
        )

    elif direction == "AGUARDAR":

        st.markdown(
            '<div class="card wait">🟡 AGUARDAR</div>',
            unsafe_allow_html=True
        )

    else:

        st.warning(
            "Não foi possível reconhecer a decisão final. "
            "Não uses este relatório como sinal."
        )

    st.markdown(report)

    st.download_button(
        "⬇️ DESCARREGAR RELATÓRIO",

        data=report,

        file_name="DonCullerTrade47_analise.txt",

        mime="text/plain",

        use_container_width=True
    )


# =====================================================
# RODAPÉ
# =====================================================

st.divider()

st.caption(
    "DONCULLER-TRADE47 V9.0 | AI TRADING CHART ANALYZER"
)

st.warning(
    "A aplicação analisa apenas screenshots. "
    "Não recebe cotações em tempo real, não executa operações "
    "e não garante lucros. Confirma os níveis no MT5 "
    "e testa primeiro em conta Demo."
)
