import os
import re
import json
import sqlite3
import base64
from io import BytesIO
from datetime import datetime, timezone

import requests
import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError

APP = "DONCULLER-TRADE47"
MODEL_DEFAULT = os.getenv(
    "OPENROUTER_MODEL",
    "nvidia/nemotron-3.5-super-vl:free"
).strip()
API = "https://openrouter.ai/api/v1/chat/completions"
DB = os.getenv("DONCULLER_DB_PATH", "donculler_history.db")

st.set_page_config(
    page_title=APP,
    page_icon="🦁",
    layout="wide"
)

st.markdown("""
<style>
.stApp {
    background: #071321;
    color: #edf4fb;
}
section[data-testid="stSidebar"] {
    background: #0b1b2d;
}
.hero, .box {
    background: #0d2033;
    border: 1px solid #24445e;
    border-radius: 14px;
    padding: 18px;
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
div.stButton > button {
    background: #16865f;
    color: white;
    font-weight: 700;
    border: 0;
    min-height: 46px;
}
.small {
    color: #9fb3c8;
    font-size: 13px;
}
</style>
""", unsafe_allow_html=True)


MARKETS = {
    "Forex": [
        "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF",
        "AUD/USD", "NZD/USD", "USD/CAD", "EUR/GBP",
        "EUR/JPY", "GBP/JPY", "XAU/USD", "XAG/USD",
        "Outro par Forex"
    ],

    "Índices Sintético": [
        "Volatility 10 Index",
        "Volatility 10 (1s) Index",
        "Volatility 25 Index",
        "Volatility 25 (1s) Index",
        "Volatility 50 Index",
        "Volatility 50 (1s) Index",
        "Volatility 75 Index",
        "Volatility 75 (1s) Index",
        "Volatility 100 Index",
        "Volatility 100 (1s) Index",
        "Volatility 150 (1s) Index",
        "Volatility 250 (1s) Index",
        "Boom 300 Index",
        "Boom 500 Index",
        "Boom 600 Index",
        "Boom 900 Index",
        "Boom 1000 Index",
        "Crash 300 Index",
        "Crash 500 Index",
        "Crash 600 Index",
        "Crash 900 Index",
        "Crash 1000 Index",
        "Jump 10 Index",
        "Jump 25 Index",
        "Jump 50 Index",
        "Jump 75 Index",
        "Jump 100 Index",
        "Step Index",
        "Multi Step Index",
        "Range Break 100 Index",
        "Range Break 200 Index",
        "Drift Switch Index",
        "Outro índice sintético"
    ],

    "Outro": [
        "Bitcoin (BTC/USD)",
        "Ethereum (ETH/USD)",
        "Outra criptomoeda",
        "US 500",
        "US 100",
        "US 30",
        "Germany 40",
        "UK 100",
        "Ação",
        "Matéria-prima",
        "Outro ativo"
    ]
}

PLATFORMS = [
    "MetaTrader 5 (MT5)",
    "cTrader",
    "TradingView",
    "Outra plataforma"
]

FRAMES = [
    "M1", "M2", "M3", "M5", "M10", "M15",
    "M30", "H1", "H2", "H4", "D1", "W1", "MN1"
]


def db_init():
    with sqlite3.connect(DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY,
                created TEXT,
                market TEXT,
                asset TEXT,
                platform TEXT,
                timeframe TEXT,
                signal TEXT,
                confidence REAL,
                entry TEXT,
                sl TEXT,
                tp TEXT
            )
        """)


def save(meta, result):
    with sqlite3.connect(DB) as conn:
        conn.execute("""
            INSERT INTO history (
                created, market, asset, platform,
                timeframe, signal, confidence,
                entry, sl, tp
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now(timezone.utc).isoformat(),
            meta["market"],
            meta["asset"],
            meta["platform"],
            meta["timeframe"],
            result["signal"],
            result["confidence"],
            result["entry"],
            result["sl"],
            result["tp"]
        ))


def parse_json(response_text):
    """
    Extrai JSON mesmo quando o modelo acrescenta
    blocos Markdown ou texto em volta da resposta.
    """
    if not isinstance(response_text, str):
        raise ValueError("A resposta da IA não é texto.")

    text = response_text.strip()

    # Remove blocos Markdown ```json ... ```
    text = re.sub(
        r"^\s*```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE
    )
    text = re.sub(r"\s*```\s*$", "", text)

    # Primeiro tenta interpretar a resposta inteira.
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # Procura o primeiro objeto JSON válido.
    decoder = json.JSONDecoder()

    for match in re.finditer(r"\{", text):
        try:
            data, _ = decoder.raw_decode(text[match.start():])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue

    raise ValueError(
        "A IA não devolveu um objeto JSON válido. "
        "Tenta novamente ou verifica o modelo configurado."
    )


def validate(data):
    if not isinstance(data, dict):
        raise ValueError("Formato de resposta inválido.")

    signal = str(data.get("signal", "")).upper().strip()

    if signal not in ("BUY", "SELL", "AGUARDAR"):
        raise ValueError("A IA devolveu um sinal desconhecido.")

    try:
        confidence = float(data.get("confidence"))
    except (TypeError, ValueError):
        raise ValueError("Percentagem de confiança inválida.")

    if not 0 <= confidence <= 100:
        raise ValueError("Percentagem fora do intervalo permitido.")

    result = {
        "signal": signal,
        "confidence": round(confidence, 1),
        "entry": str(data.get("entry") or "").strip(),
        "sl": str(data.get("stop_loss") or "").strip(),
        "tp": str(data.get("take_profit") or "").strip()
    }

    if signal == "AGUARDAR":
        result["entry"] = ""
        result["sl"] = ""
        result["tp"] = ""
        return result

    if not all([
        result["entry"],
        result["sl"],
        result["tp"]
    ]):
        raise ValueError(
            "BUY/SELL sem entrada, SL e TP. "
            "O sinal foi recusado para evitar níveis inventados."
        )

    return result


def analyze(image, meta, key, model):

    prompt = f"""
És um analista técnico rigoroso de gráficos financeiros.

Analisa somente a informação que está realmente visível
e legível no screenshot.

Mercado: {meta['market']}
Ativo: {meta['asset']}
Plataforma: {meta['platform']}
Timeframe: {meta['timeframe']}

Escolhe exatamente um resultado:
BUY, SELL ou AGUARDAR.

Considera, quando estiverem visíveis:
- Tendência do mercado.
- Estrutura HH, HL, LH e LL.
- Padrões de velas.
- Suportes e resistências.
- Rompimentos e retestes.
- RSI.
- MACD.
- Médias móveis.
- Fractals.
- Zig Zag.

Não inventes preços, indicadores ou níveis que não
consigas identificar na imagem.

BUY ou SELL somente quando existir evidência técnica
suficiente.

Se não conseguires determinar uma entrada futura,
Stop Loss e Take Profit fundamentados, escolhe AGUARDAR.

A entrada deve ser futura e conter uma condição objetiva
de ativação.

A confiança é uma estimativa da qualidade da evidência
visual. Não representa uma probabilidade comprovada
de lucro.

Responde exclusivamente com JSON válido, sem Markdown
e sem explicações adicionais.

Formato obrigatório:

{{
  "signal": "BUY",
  "confidence": 70,
  "entry": "Zona futura e condição de ativação",
  "stop_loss": "Nível de Stop Loss",
  "take_profit": "Nível de Take Profit"
}}

Para SELL, utiliza "SELL".
Para AGUARDAR, utiliza:

{{
  "signal": "AGUARDAR",
  "confidence": 50,
  "entry": "",
  "stop_loss": "",
  "take_profit": ""
}}
"""

    image = ImageOps.exif_transpose(image).convert("RGB")
    image.thumbnail((1800, 1800))

    buffer = BytesIO()
    image.save(
        buffer,
        format="JPEG",
        quality=88,
        optimize=True
    )

    encoded_image = base64.b64encode(
        buffer.getvalue()
    ).decode("utf-8")

    payload = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": 900,
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
                                + encoded_image
                            )
                        }
                    }
                ]
            }
        ]
    }

    try:
        response = requests.post(
            API,
            headers={
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json",
                "HTTP-Referer": "https://doncullertrade47.onrender.com",
                "X-Title": APP
            },
            json=payload,
            timeout=(20, 150)
        )
    except requests.RequestException as error:
        raise RuntimeError(
            f"Falha de ligação ao OpenRouter: {error}"
        )

    if response.status_code == 429:
        raise RuntimeError(
            "Limite de utilização OpenRouter atingido (HTTP 429). "
            "Aguarda a reposição da quota."
        )

    if response.status_code in (401, 403):
        raise RuntimeError(
            "Chave OpenRouter recusada. "
            "Confirma OPENROUTER_API_KEY no Render."
        )

    if response.status_code >= 400:
        raise RuntimeError(
            f"Erro OpenRouter {response.status_code}: "
            f"{response.text[:900]}"
        )

    try:
        api_data = response.json()
        content = api_data["choices"][0]["message"]["content"]

        if isinstance(content, list):
            content = "\n".join(
                item.get("text", "")
                for item in content
                if isinstance(item, dict)
            )

        parsed = parse_json(content)
        return validate(parsed)

    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise RuntimeError(
            f"Resposta inválida/incompleta da IA: {error}"
        )


# INICIALIZAÇÃO
db_init()

st.markdown(
    f"""
    <div class="hero">
        <div class="small">V9.1 · AI TRADING CHART ANALYZER</div>
        <h1>🦁 {APP}</h1>
        <span class="small">Análise de gráficos por imagem</span>
    </div>
    """,
    unsafe_allow_html=True
)


# CONFIGURAÇÃO
with st.sidebar:
    st.subheader("Configuração")

    market = st.selectbox(
        "Mercado",
        list(MARKETS.keys())
    )

    asset = st.selectbox(
        "Instrumento",
        MARKETS[market]
    )

    platform = st.selectbox(
        "Plataforma",
        PLATFORMS
    )

    timeframe = st.selectbox(
        "Timeframe",
        FRAMES,
        index=3
    )

    model = st.text_input(
        "Modelo OpenRouter",
        MODEL_DEFAULT
    )

    st.caption(
        "A chave é obtida de OPENROUTER_API_KEY "
        "nas variáveis de ambiente do Render."
    )


# INTERFACE PRINCIPAL
col1, col2 = st.columns(
    [1.1, 0.9],
    gap="large"
)

with col1:
    st.subheader("Screenshot do gráfico")

    upload = st.file_uploader(
        "Carrega uma imagem",
        type=["png", "jpg", "jpeg", "webp"]
    )

    preview = None

    if upload:
        try:
            preview = Image.open(upload)
            st.image(
                preview,
                caption="Gráfico carregado",
                use_container_width=True
            )
        except UnidentifiedImageError:
            st.error("Imagem inválida.")

    run = st.button(
        "🦁 ANALISAR GRÁFICO",
        use_container_width=True
    )


with col2:
    st.subheader("Resultado")

    if run:
        key = os.getenv(
            "OPENROUTER_API_KEY",
            ""
        ).strip()

        if preview is None:
            st.warning(
                "Carrega primeiro um screenshot válido."
            )

        elif not key:
            st.error(
                "Configura OPENROUTER_API_KEY "
                "nas Environment Variables do Render."
            )

        elif not model.strip():
            st.error(
                "Indica um modelo OpenRouter."
            )

        else:
            meta = {
                "market": market,
                "asset": asset,
                "platform": platform,
                "timeframe": timeframe
            }

            with st.spinner(
                "A analisar o gráfico..."
            ):
                try:
                    result = analyze(
                        preview,
                        meta,
                        key,
                        model.strip()
                    )

                    save(meta, result)

                    st.session_state["v9_result"] = result
                    st.session_state["v9_meta"] = meta

                except Exception as error:
                    st.session_state.pop(
                        "v9_result",
                        None
                    )

                    st.error(str(error))

    result = st.session_state.get("v9_result")

    if result:
        signal = result["signal"]

        css = {
            "BUY": "buy",
            "SELL": "sell",
            "AGUARDAR": "wait"
        }[signal]

        st.markdown(
            f"""
            <div class="box">
                <div class="{css}">
                    {signal} — {result["confidence"]:.1f}%
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        if signal in ("BUY", "SELL"):
            st.markdown(
                f"**Futura entrada:** {result['entry']}"
            )

            st.markdown(
                f"**SL:** {result['sl']}"
            )

            st.markdown(
                f"**TP:** {result['tp']}"
            )

    else:
        st.info(
            "O resultado aparecerá aqui após a análise."
        )


# HISTÓRICO
st.divider()
st.subheader("Histórico")

with sqlite3.connect(DB) as conn:
    rows = conn.execute("""
        SELECT
            created,
            market,
            asset,
            platform,
            timeframe,
            signal,
            confidence
        FROM history
        ORDER BY id DESC
        LIMIT 50
    """).fetchall()

if rows:
    st.dataframe(
        [
            {
                "Data UTC": row[0][:19].replace("T", " "),
                "Mercado": row[1],
                "Ativo": row[2],
                "Plataforma": row[3],
                "Timeframe": row[4],
                "Sinal": row[5],
                "Confiança": f"{row[6]:.1f}%"
            }
            for row in rows
        ],
        use_container_width=True,
        hide_index=True
    )
else:
    st.caption(
        "Ainda não existem análises guardadas."
    )


st.markdown(
    """
    <div class="small">
    A percentagem é uma estimativa da IA baseada no screenshot,
    não uma taxa de acerto comprovada. A aplicação não recebe
    cotações em tempo real nem executa ordens.
    Testa em Demo antes de considerar dinheiro real.
    </div>
    """,
    unsafe_allow_html=True
)
