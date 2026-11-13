import os
import re
import json
import base64
from io import BytesIO

import requests
import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError


# =========================================================
# CONFIGURAÇÃO
# =========================================================

APP_NAME = "DONCULLER-TRADE47"
API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()

API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "nvidia/nemotron-3.5-super-vl:free"
).strip()

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🦁",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =========================================================
# ESTILO VISUAL
# =========================================================

st.markdown("""
<style>
.stApp {
    background: #071321;
    color: #e8eef5;
}
[data-testid="stSidebar"] {
    background: #0b1b2d;
}
.block-container {
    max-width: 1200px;
    padding-top: 2rem;
}
h1, h2, h3 {
    color: #f0f5fa;
}
.panel {
    background: #0d2033;
    border: 1px solid #203a52;
    border-radius: 12px;
    padding: 18px;
    margin-bottom: 15px;
}
.buy {
    color: #25d887;
    font-size: 30px;
    font-weight: 800;
}
.sell {
    color: #ff6874;
    font-size: 30px;
    font-weight: 800;
}
.wait {
    color: #ffc857;
    font-size: 30px;
    font-weight: 800;
}
.small-note {
    color: #9db0c3;
    font-size: 13px;
}
.stButton button {
    width: 100%;
    min-height: 48px;
    background: #126b57;
    color: white;
    border: none;
    border-radius: 9px;
    font-weight: bold;
}
.stButton button:hover {
    background: #16866b;
    color: white;
}
</style>
""", unsafe_allow_html=True)


# =========================================================
# LISTAS DE ATIVOS
# =========================================================

SYNTHETIC = [
    "Boom 1000", "Crash 1000",
    "Boom 500", "Crash 500",
    "Boom 300", "Crash 300",
    "Boom 100", "Crash 100",
    "Boom 50", "Crash 50",
    "Jump Index 50", "Jump Index",
    "Step Index"
]

FOREX = [
    "EUR/USD",
    "GBP/USD",
    "XAU/USD"
]

TIMEFRAMES = [
    "M1", "M5", "M15", "M30",
    "H1", "H4", "D1"
]

PLATFORMS = [
    "Deriv MT5",
    "Deriv cTrader",
    "TradingView",
    "Outra"
]


# =========================================================
# PROMPT DE ANÁLISE
# =========================================================

def build_prompt(asset, timeframe, platform):

    return f"""
És um analista técnico especializado em leitura de gráficos financeiros.

Analisa exclusivamente a imagem enviada.

DADOS:
Ativo: {asset}
Timeframe: {timeframe}
Plataforma: {platform}

OBJETIVO:
Identificar a melhor oportunidade técnica entre BUY e SELL.
Não escolhas AGUARDAR automaticamente.
Compara sempre as duas possibilidades e seleciona BUY ou SELL
quando existir evidência técnica suficiente.

ANALISA:

1. Tendência principal e estrutura do mercado.
2. Máximos e mínimos: HH, HL, LH e LL.
3. Suportes e resistências visíveis.
4. Zonas de oferta e procura, se identificáveis.
5. Liquidez, varrimentos e possíveis falsas rupturas.
6. Padrões de velas e força dos movimentos.
7. Médias móveis e EMA 20/50, apenas se estiverem visíveis.
8. RSI e MACD, apenas se estiverem visíveis.
9. Zig Zag e Fractals, apenas se estiverem visíveis.
10. Possíveis pontos de entrada e invalidação.

REGRAS IMPORTANTES:

- Não inventes preços, indicadores ou valores que não aparecem na imagem.
- Não afirmes que um indicador confirmou algo se não estiver visível.
- Não confundas uma vela ainda em formação com uma vela fechada.
- Não prevejas spikes como se fossem garantidos.
- Não inventes cotações em tempo real.
- Se a imagem não permitir identificar preços, escreve
  "Preço exato não identificável na imagem".
- Compara BUY e SELL antes de decidir.
- AGUARDAR apenas quando não existir uma oportunidade
  tecnicamente defensável.
- Não forces uma operação só para evitar AGUARDAR.
- A percentagem indicada é uma estimativa técnica subjetiva,
  não uma taxa de acerto comprovada.

FORMATO OBRIGATÓRIO DA RESPOSTA:

## DIREÇÃO
BUY, SELL ou AGUARDAR

## FORÇA DO SINAL
Indica uma estimativa de confiança técnica de 0 a 100%.
Explica brevemente os principais fatores.

## ENTRADA
Indica a zona de entrada ou explica se não é possível
identificar preços na imagem.

## ATIVAÇÃO
Explica o que o preço precisa fazer para ativar a entrada.

## STOP LOSS
Indica o nível técnico de invalidação, se identificável.

## TAKE PROFIT
TP1:
TP2:

## RISCO / RETORNO
Indica a relação risco/retorno estimada, se os preços permitirem.

## CONFIRMAÇÕES
Lista as confirmações realmente visíveis.

## RISCOS
Indica o que pode invalidar a análise.

## DECISÃO FINAL
Uma frase curta e operacional.

Responde em português simples, direto e profissional.
Não apresentes preços fictícios.
"""


# =========================================================
# PREPARAÇÃO DA IMAGEM
# =========================================================

def prepare_image(uploaded_file):

    image = Image.open(uploaded_file)
    image = ImageOps.exif_transpose(image)
    image = image.convert("RGB")

    # Redimensionar imagens muito grandes
    image.thumbnail((1600, 1600))

    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=88, optimize=True)

    encoded = base64.b64encode(
        buffer.getvalue()
    ).decode("utf-8")

    return encoded


# =========================================================
# ANÁLISE OPENROUTER
# =========================================================

def analyze_chart(image_base64, asset, timeframe, platform):

    if not API_KEY:
        raise RuntimeError(
            "A chave OPENROUTER_API_KEY não foi encontrada "
            "nas variáveis Environment do Render."
        )

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://doncullertrade47.onrender.com",
        "X-Title": "DONCULLER-TRADE47"
    }

    prompt = build_prompt(asset, timeframe, platform)

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
                                + image_base64
                            )
                        }
                    }
                ]
            }
        ],
        "temperature": 0.15,
        "max_tokens": 3500
    }

    try:
        response = requests.post(
            API_URL,
            headers=headers,
            json=payload,
            timeout=(20, 180)
        )

    except requests.exceptions.Timeout:
        raise RuntimeError(
            "O modelo demorou demasiado a responder. "
            "Tenta novamente."
        )

    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Falha de ligação ao OpenRouter. "
            "Verifica a ligação e tenta novamente."
        )

    except requests.exceptions.RequestException as error:
        raise RuntimeError(
            f"Erro de comunicação: {error}"
        )

    if response.status_code != 200:

        try:
            error_data = response.json()
            error_message = error_data.get(
                "error", {}
            ).get("message", response.text)

        except Exception:
            error_message = response.text

        raise RuntimeError(
            f"OpenRouter HTTP {response.status_code}: "
            f"{error_message}"
        )

    try:
        data = response.json()

    except ValueError:
        raise RuntimeError(
            "O OpenRouter devolveu uma resposta inválida."
        )

    choices = data.get("choices", [])

    if not choices:
        raise RuntimeError(
            "O modelo não devolveu uma análise."
        )

    choice = choices[0]
    message = choice.get("message", {})
    content = message.get("content", "")

    if isinstance(content, list):
        text_parts = []

        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    text_parts.append(item.get("text", ""))

        content = "\n".join(text_parts)

    if not isinstance(content, str) or not content.strip():
        raise RuntimeError(
            "A resposta do modelo veio vazia. "
            "Tenta novamente."
        )

    finish_reason = choice.get("finish_reason", "")

    if finish_reason == "length":
        content += (
            "\n\nNota: a resposta atingiu o limite de tokens "
            "e pode estar incompleta."
        )

    return content


# =========================================================
# CABEÇALHO
# =========================================================

st.markdown(
    "<h1 style='text-align:center;'>🦁 DONCULLER-TRADE47</h1>",
    unsafe_allow_html=True
)

st.markdown(
    "<p style='text-align:center;color:#9db0c3;'>"
    "AI Trading Chart Analyzer"
    "</p>",
    unsafe_allow_html=True
)

st.divider()


# =========================================================
# MENU LATERAL
# =========================================================

with st.sidebar:

    st.markdown("## ⚙️ CONFIGURAÇÃO")

    category = st.radio(
        "Categoria de mercado",
        ["Índices sintéticos", "Forex"]
    )

    if category == "Índices sintéticos":
        asset_list = SYNTHETIC
    else:
        asset_list = FOREX

    asset = st.selectbox(
        "Ativo",
        asset_list
    )

    timeframe = st.selectbox(
        "Timeframe",
        TIMEFRAMES,
        index=1
    )

    platform = st.selectbox(
        "Plataforma",
        PLATFORMS
    )

    st.divider()

    st.markdown("### Modelo de análise")
    st.caption(MODEL)

    st.markdown(
        "<p class='small-note'>"
        "A análise depende da qualidade e dos elementos "
        "visíveis no screenshot."
        "</p>",
        unsafe_allow_html=True
    )


# =========================================================
# ÁREA PRINCIPAL
# =========================================================

st.markdown("## 📊 ANÁLISE DO GRÁFICO")

st.markdown(
    "<div class='panel'>"
    "Carrega um screenshot nítido do gráfico. "
    "Sempre que possível, mostra as velas, escala de preços "
    "e indicadores utilizados."
    "</div>",
    unsafe_allow_html=True
)

uploaded_file = st.file_uploader(
    "Carregar screenshot do gráfico",
    type=["png", "jpg", "jpeg"],
    key="chart_upload"
)


if uploaded_file:

    try:
        preview = Image.open(uploaded_file)
        preview = ImageOps.exif_transpose(preview)

        st.image(
            preview,
            caption=f"{asset} | {timeframe}",
            use_container_width=True
        )

    except UnidentifiedImageError:
        st.error("O ficheiro enviado não é uma imagem válida.")


st.markdown("")


# =========================================================
# BOTÃO DE ANÁLISE
# =========================================================

if st.button("🦁 ANALISAR GRÁFICO"):

    if uploaded_file is None:
        st.warning(
            "Primeiro, carrega o screenshot do gráfico."
        )

    elif not API_KEY:
        st.error(
            "A chave OPENROUTER_API_KEY não foi encontrada "
            "no Render."
        )

    else:

        try:
            with st.spinner(
                "A analisar estrutura, velas e indicadores..."
            ):

                uploaded_file.seek(0)

                image_base64 = prepare_image(
                    uploaded_file
                )

                result = analyze_chart(
                    image_base64,
                    asset,
                    timeframe,
                    platform
                )

            st.session_state["last_result"] = result
            st.session_state["last_asset"] = asset
            st.session_state["last_timeframe"] = timeframe

        except Exception as error:
            st.error(str(error))


# =========================================================
# RESULTADO
# =========================================================

if "last_result" in st.session_state:

    st.divider()

    st.markdown("## 📈 RELATÓRIO DE ANÁLISE")

    st.markdown(
        f"**Ativo:** {st.session_state['last_asset']}  \n"
        f"**Timeframe:** {st.session_state['last_timeframe']}"
    )

    result = st.session_state["last_result"]

    direction = "AGUARDAR"

    match = re.search(
        r"##\s*DIREÇÃO\s*[\r\n]+"
        r"\s*(BUY|SELL|AGUARDAR)",
        result,
        re.IGNORECASE
    )

    if match:
        direction = match.group(1).upper()

    if direction == "BUY":
        st.markdown(
            "<div class='panel'><div class='buy'>🟢 BUY</div>"
            "</div>",
            unsafe_allow_html=True
        )

    elif direction == "SELL":
        st.markdown(
            "<div class='panel'><div class='sell'>🔴 SELL</div>"
            "</div>",
            unsafe_allow_html=True
        )

    else:
        st.markdown(
            "<div class='panel'><div class='wait'>🟡 AGUARDAR</div>"
            "</div>",
            unsafe_allow_html=True
        )

    st.markdown(result)

    st.download_button(
        label="📥 DESCARREGAR RELATÓRIO",
        data=result,
        file_name="DonCullerTrade47_Relatorio.txt",
        mime="text/plain"
    )

    st.caption(
        "A análise é uma estimativa técnica baseada na imagem. "
        "Não representa uma taxa de acerto comprovada nem garante lucro."
)
