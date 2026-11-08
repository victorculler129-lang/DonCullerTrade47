import os
import re
import base64
from io import BytesIO

import requests
import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError


# =========================================================
# DONCULLER-TRADE47 V6.0
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
        <p>AI TRADING CHART ANALYZER · V6.0</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ===================== API CONFIGURATION ==================

API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()

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

    st.caption("V6.0 · Análise visual de screenshots")

    st.divider()

    st.caption(f"Modelo configurado: {MODEL}")


# ========================= PROMPT ==========================

def build_prompt():

    return f"""
És o motor profissional de análise técnica da
DONCULLER-TRADE47 V6.0.

A tua tarefa é analisar o screenshot enviado e identificar
a melhor oportunidade técnica entre BUY e SELL.

Não tens acesso a cotações em tempo real,
ao histórico OHLC nem aos dados internos dos indicadores.

CONTEXTO

Ativo: {asset}
Mercado: {market}
Timeframe: {timeframe}
Plataforma: {platform}

==================================================
1. LEITURA DO GRÁFICO
==================================================

Primeiro verifica:

- Se a imagem está legível.
- Se as velas estão visíveis.
- Se a escala de preços está visível.
- Se existem indicadores no gráfico.
- Se o timeframe e o ativo correspondem ao contexto.

Não inventes informações que não aparecem na imagem.

==================================================
2. ESTRUTURA DO MERCADO
==================================================

Analisa:

- Tendência principal.
- Topos e fundos.
- Topos ascendentes ou descendentes.
- Fundos ascendentes ou descendentes.
- Impulsos e correções.
- Suportes e resistências.
- Rompimentos.
- Falsos rompimentos.
- Mudanças de estrutura.

Não assumas que uma tendência anterior continuará
necessariamente na mesma direção.

==================================================
3. ANÁLISE DAS VELAS
==================================================

Observa:

- Corpos das velas.
- Pavios superiores e inferiores.
- Rejeições.
- Engolfo bullish.
- Engolfo bearish.
- Doji.
- Velas de força.
- Sequências de velas.
- Fechamentos acima ou abaixo de níveis importantes.

Distingue uma vela isolada de uma confirmação real.

==================================================
4. INDICADORES TÉCNICOS
==================================================

ZIG ZAG:

Analisa os últimos topos e fundos confirmados.
Procura mudanças de direção e alterações na estrutura.

FRACTALS:

Analisa fractais superiores e inferiores.
Procura confirmações de reversão e continuação.

MACD:

Analisa cruzamentos bullish e bearish,
direção das linhas e histograma, quando visíveis.

RSI:

Analisa força compradora e vendedora,
zonas extremas e divergências, quando visíveis.

MÉDIAS MÓVEIS:

Analisa inclinação, posição das velas
e possíveis cruzamentos, quando visíveis.

Se um indicador não estiver visível, escreve:
Não visível no screenshot.

Não inventes valores de indicadores.

==================================================
5. AVALIAÇÃO BUY — COMPRA
==================================================

Procura oportunidades BUY através de:

- Rejeição de suporte.
- Fundos ascendentes.
- Recuperação de uma zona importante.
- Engolfo bullish.
- Rompimento bullish confirmado.
- Rompimento seguido de reteste.
- Fractal inferior confirmado.
- Zig Zag a mostrar mudança para estrutura ascendente.
- MACD a favorecer movimento comprador.
- RSI a recuperar força compradora.
- Médias móveis a favorecer compras.

Uma queda anterior não é motivo suficiente
para escolher SELL.

Avalia a possibilidade de reversão bullish.

==================================================
6. AVALIAÇÃO SELL — VENDA
==================================================

Procura oportunidades SELL através de:

- Rejeição de resistência.
- Topos descendentes.
- Perda de suporte.
- Engolfo bearish.
- Rompimento bearish confirmado.
- Rompimento seguido de reteste.
- Fractal superior confirmado.
- Zig Zag a mostrar mudança para estrutura descendente.
- MACD a favorecer movimento vendedor.
- RSI a perder força compradora.
- Médias móveis a favorecer vendas.

Uma subida anterior não é motivo suficiente
para escolher BUY.

Avalia a possibilidade de reversão bearish.

==================================================
7. ÍNDICES SINTÉTICOS
==================================================

Quando o ativo for Boom, Crash, Jump ou Step Index:

- Analisa o comportamento efetivamente visível.
- Observa a estrutura antes e depois dos movimentos fortes.
- Não assumes a direção apenas pelo nome do ativo.
- Não inventes a ocorrência de um spike.
- Não confundas uma pequena correção com uma reversão confirmada.

Não escolhas BUY ou SELL automaticamente
por causa do nome do índice.

==================================================
8. FORÇA BUY E SELL
==================================================

Atribui duas notas técnicas independentes:

FORÇA BUY: 0 a 100.
FORÇA SELL: 0 a 100.

As notas representam força técnica observada,
não probabilidades reais de lucro.

Avalia as duas direções com os mesmos critérios.

Não atribuas notas elevadas sem confirmações.

Não favoreças SELL por defeito.
Não favoreças BUY por defeito.

==================================================
9. ESCOLHA DA DIREÇÃO
==================================================

Compara os dois cenários.

Escolhe BUY quando:

- A evidência compradora for suficientemente forte.
- Existir uma configuração de compra identificável.
- For possível indicar uma condição de ativação.
- A invalidação e os objetivos forem tecnicamente plausíveis.

Escolhe SELL quando:

- A evidência vendedora for suficientemente forte.
- Existir uma configuração de venda identificável.
- For possível indicar uma condição de ativação.
- A invalidação e os objetivos forem tecnicamente plausíveis.

Escolhe AGUARDAR quando:

- A imagem não permitir uma leitura adequada.
- As evidências forem contraditórias.
- Não existir configuração válida.
- Os preços não permitirem estabelecer níveis com segurança.

IMPORTANTE:

Não escolhas AGUARDAR automaticamente.

Não escolhas SELL apenas porque o preço está a cair.

Não escolhas BUY apenas porque o preço está a subir.

Procura primeiro uma oportunidade válida nas duas direções.

Se BUY apresentar evidência claramente superior e uma
configuração válida, escolhe BUY.

Se SELL apresentar evidência claramente superior e uma
configuração válida, escolhe SELL.

Se nenhuma direção apresentar configuração válida,
escolhe AGUARDAR.

Não fabriques operações para satisfazer o utilizador.

==================================================
10. ENTRADA E GESTÃO DE RISCO
==================================================

Para cada cenário válido, apresenta:

Entrada/zona:
Preço ou zona de entrada tecnicamente identificável.

Ativação:
Condição observável necessária antes de entrar.

SL:
Nível de invalidação estrutural.

TP1:
Primeiro objetivo técnico.

TP2:
Segundo objetivo técnico.

Risco/retorno estimado:
Relação aproximada entre risco e recompensa.

Não inventes preços.

Se a escala não permitir identificar os preços,
escreve:

INDETERMINÁVEL PELA IMAGEM.

Não apresentes uma entrada como garantida.

==================================================
11. FORMATO OBRIGATÓRIO DA RESPOSTA
==================================================

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

Se um cenário não for válido, escreve:
SEM CONFIGURAÇÃO VÁLIDA.

A decisão final deve ser coerente com a análise
e com os cenários apresentados.

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
            "O modelo atingiu o limite de tokens "
            "antes de terminar a resposta. "
            "Tenta novamente."
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
        quality=90,
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

        "temperature": 0.15,

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
            "OpenRouter 401: chave API não reconhecida."
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

        r"DECIS[AÃ]O\s+FINAL\s*[:\-]\s*"
        r"\**\s*(BUY|SELL|AGUARDAR)\b",

        r"SINAL\s+PRINCIPAL\s*[:\-]\s*"
        r"\**\s*(BUY|SELL|AGUARDAR)\b",

        r"DIRE[CÇ][AÃ]O\s+FINAL\s*[:\-]\s*"
        r"\**\s*(BUY|SELL|AGUARDAR)\b",

    ]

    for pattern in patterns:

        matches = re.findall(
            pattern,
            report_text,
            re.IGNORECASE
        )

        if matches:

            return matches[-1].upper()

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

            <p>Análise de estrutura, velas,
            Zig Zag, Fractais, MACD e outros
            indicadores visíveis.</p>
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
        file_name="DonCullerTrade47_V6.txt",
        mime="text/plain",
        use_container_width=True
    )


# ========================= FOOTER =========================

st.divider()

st.caption(
    "DONCULLER-TRADE47 · AI CHART ANALYZER · V6.0"
)

st.warning(
    "Esta versão analisa screenshots; não recebe cotações "
    "em tempo real, não calcula indicadores a partir de dados OHLC "
    "e não executa operações. Os níveis lidos visualmente "
    "podem estar imprecisos. Testa em conta Demo "
    "e confirma os preços diretamente na plataforma."
)
