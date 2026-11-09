import os
import re
import base64
from io import BytesIO
from datetime import datetime

import requests
import streamlit as st
from PIL import Image, ImageOps

# ==========================================
# DONCULLER-TRADE47 V8.0
# ==========================================

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

# ==========================================
# DESIGN
# ==========================================

st.markdown("""
<style>
.stApp {
    background: #071321;
    color: #edf3fa;
}

.block-container {
    max-width: 1150px;
    padding-top: 1.5rem;
}

section[data-testid="stSidebar"] {
    background: #0b1b2d;
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
    margin: 10px 0;
}

.buy {
    color: #28dc91;
    font-size: 35px;
    font-weight: 900;
}

.sell {
    color: #ff6675;
    font-size: 35px;
    font-weight: 900;
}

.wait {
    color: #ffd166;
    font-size: 35px;
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
<p>AI TRADING CHART ANALYZER · VERSION 8.0</p>
</div>
""", unsafe_allow_html=True)

# ==========================================
# CONFIGURAÇÃO
# ==========================================

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
    st.caption("DONCULLER-TRADE47 V8.0")

# ==========================================
# PROMPT DE ANÁLISE
# ==========================================

def create_prompt():

    return f"""
És o analista técnico profissional da DONCULLER-TRADE47.

Analisa cuidadosamente o screenshot enviado.

INFORMAÇÕES:
Ativo: {asset}
Mercado: {market}
Timeframe: {timeframe}
Plataforma: {platform}

O TEU OBJETIVO:

Encontrar a melhor oportunidade futura de BUY ou SELL.

Não favoreças nenhuma direção.
Analisa BUY e SELL com os mesmos critérios.

ANÁLISE TÉCNICA OBRIGATÓRIA:

1. Tendência principal.
2. Estrutura de mercado.
3. Topos e fundos.
4. Suportes e resistências.
5. Velas e padrões de reversão.
6. Rompimentos e retestes.
7. Zig Zag, se visível.
8. Fractals, se visíveis.
9. MACD, se visível.
10. RSI e médias móveis, se visíveis.

Não inventes indicadores que não aparecem na imagem.

ANÁLISE BUY:

Procura:
- Recuperação de suporte.
- Fundo mais alto.
- Rompimento de resistência.
- Reteste positivo.
- Fractal inferior confirmado.
- Confirmação de MACD, se visível.

ANÁLISE SELL:

Procura:
- Rejeição de resistência.
- Topo mais baixo.
- Perda de suporte.
- Reteste negativo.
- Fractal superior confirmado.
- Confirmação de MACD, se visível.

ÍNDICES SINTÉTICOS:

Não escolhas BUY ou SELL apenas pelo nome Boom, Crash,
Jump ou Step. Analisa o comportamento real do gráfico.

DECISÃO:

Compara a força dos dois cenários.

Se BUY tiver melhores confirmações, escolhe BUY.

Se SELL tiver melhores confirmações, escolhe SELL.

Se nenhum cenário tiver confirmação suficiente, escolhe AGUARDAR.

Não escolhas sempre AGUARDAR.
Não escolhas sempre SELL.
Não escolhas sempre BUY.

A confiança é uma avaliação técnica subjetiva, não uma
probabilidade garantida de lucro.

ENTRADA:

Apresenta uma entrada específica ou uma zona de entrada.
Se necessário, utiliza uma condição de ativação, como
fecho de vela acima ou abaixo de determinado nível.

STOP LOSS:

Coloca o SL onde a estrutura da operação fica invalidada.

TAKE PROFIT:

Apresenta TP1 e TP2 em níveis tecnicamente plausíveis.

IMPORTANTE:

Não inventes preços.
Se a escala de preços não estiver legível, escreve
"Preço não legível na imagem".

FORMATO DA RESPOSTA:

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

CONFIRMAÇÕES:
1.
2.
3.

CENÁRIO CONTRÁRIO:
INVALIDAÇÃO:

RESUMO OPERACIONAL:

Responde em português simples.
Evita explicações longas.
Não acrescentes texto fora do relatório.
"""

# ==========================================
# PREPARAÇÃO DA IMAGEM
# ==========================================

def prepare_image(uploaded):

    try:

        uploaded.seek(0)

        image = Image.open(uploaded)

        image = ImageOps.exif_transpose(image)

        image = image.convert("RGB")

        if image.width < 250 or image.height < 180:
            raise ValueError("Screenshot demasiado pequeno.")

        image.thumbnail((1800, 1800), Image.Resampling.LANCZOS)

        return image

    except Exception as error:

        raise ValueError(
            "Não foi possível abrir a imagem. "
            "Envia outro screenshot."
        ) from error


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

# ==========================================
# INTELIGÊNCIA ARTIFICIAL
# ==========================================

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

        "max_tokens": 2200,

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
            f"Erro de ligação: {error}"
        )

    if not response.ok:

        try:

            data = response.json()

            detail = data.get(
                "error", {}
            ).get(
                "message",
                response.text[:600]
            )

        except Exception:

            detail = response.text[:600]

        raise RuntimeError(
            f"OpenRouter ({response.status_code}): {detail}"
        )

    try:

        data = response.json()

        content = data["choices"][0]["message"]["content"]

        if isinstance(content, list):

            content = "\n".join(
                item.get("text", "")
                for item in content
                if isinstance(item, dict)
                and item.get("type") in ["text", "output_text"]
            )

        if not content or not str(content).strip():

            raise ValueError("Resposta vazia.")

        return str(content).strip()

    except Exception as error:

        raise RuntimeError(
            "O modelo devolveu uma resposta inválida."
        ) from error

# ==========================================
# IDENTIFICAR DIREÇÃO
# ==========================================

def get_direction(report):

    match = re.search(
        r"(?im)^\s*DIREÇÃO FINAL\s*:\s*(BUY|SELL|AGUARDAR)\b",
        report
    )

    if match:

        return match.group(1).upper()

    return "INDEFINIDA"

# ==========================================
# INTERFACE PRINCIPAL
# ==========================================

st.subheader("📷 CARREGAR GRÁFICO")

uploaded = st.file_uploader(
    "Seleciona o screenshot do teu gráfico",
    type=["png", "jpg", "jpeg", "webp"]
)

image = None

if uploaded:

    if uploaded.size > 8 * 1024 * 1024:

        st.error("A imagem ultrapassa 8 MB.")

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

st.divider()

if st.button(
    "🦁 ANALISAR GRÁFICO",
    disabled=image is None,
    use_container_width=True
):

    try:

        with st.spinner(
            "A analisar estrutura, indicadores e oportunidades..."
        ):

            result = analyze_chart(image)

        st.session_state["report"] = result

        st.session_state["direction"] = get_direction(result)

        st.session_state["analysis_time"] = datetime.now().strftime(
            "%d/%m/%Y %H:%M"
        )

    except Exception as error:

        st.error(str(error))

# ==========================================
# RESULTADO
# ==========================================

if "report" in st.session_state:

    report = st.session_state["report"]

    direction = st.session_state["direction"]

    st.divider()

    st.subheader("📊 RESULTADO DA ANÁLISE")

    st.caption(
        "Análise realizada em: "
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
            "Não foi possível identificar a direção final. "
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

st.divider()

st.caption(
    "DONCULLER-TRADE47 V8.0 | AI TRADING ANALYZER"
)

st.warning(
    "Ferramenta de análise visual. Não executa operações "
    "nem garante lucros. Confirma sempre os níveis no MT5 "
    "e testa primeiro em conta Demo."
    )
