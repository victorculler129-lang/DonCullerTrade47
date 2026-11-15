import os, re, json, sqlite3, base64
from io import BytesIO
from datetime import datetime, timezone

import requests
import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError

APP = "DONCULLER-TRADE47"
MODEL_DEFAULT = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3.5-super-vl:free").strip()
API = "https://openrouter.ai/api/v1/chat/completions"
DB = os.getenv("DONCULLER_DB_PATH", "donculler_history.db")

st.set_page_config(page_title=APP, page_icon="🦁", layout="wide")

st.markdown("""
<style>
.stApp{background:#071321;color:#edf4fb}
section[data-testid="stSidebar"]{background:#0b1b2d}
.hero,.box{background:#0d2033;border:1px solid #24445e;border-radius:14px;padding:18px}
.buy{color:#25d887;font-size:30px;font-weight:800}
.sell{color:#ff6874;font-size:30px;font-weight:800}
.wait{color:#ffc857;font-size:30px;font-weight:800}
div.stButton>button{background:#16865f;color:white;font-weight:700;border:0;min-height:46px}
.small{color:#9fb3c8;font-size:13px}
</style>
""", unsafe_allow_html=True)

MARKETS = {
    "Forex": [
        "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD",
        "NZD/USD", "USD/CAD", "EUR/GBP", "EUR/JPY", "GBP/JPY",
        "XAU/USD", "XAG/USD", "Outro par Forex"
    ],
    "Índices Sintético": [
        "Volatility 10 Index", "Volatility 10 (1s) Index",
        "Volatility 25 Index", "Volatility 25 (1s) Index",
        "Volatility 50 Index", "Volatility 50 (1s) Index",
        "Volatility 75 Index", "Volatility 75 (1s) Index",
        "Volatility 100 Index", "Volatility 100 (1s) Index",
        "Volatility 150 (1s) Index", "Volatility 250 (1s) Index",
        "Boom 300 Index", "Boom 500 Index", "Boom 600 Index",
        "Boom 900 Index", "Boom 1000 Index",
        "Crash 300 Index", "Crash 500 Index", "Crash 600 Index",
        "Crash 900 Index", "Crash 1000 Index",
        "Jump 10 Index", "Jump 25 Index", "Jump 50 Index",
        "Jump 75 Index", "Jump 100 Index",
        "Step Index", "Multi Step Index",
        "Range Break 100 Index", "Range Break 200 Index",
        "Drift Switch Index", "Outro índice sintético"
    ],
    "Outro": [
        "Bitcoin (BTC/USD)", "Ethereum (ETH/USD)",
        "Outra criptomoeda", "US 500", "US 100", "US 30",
        "Germany 40", "UK 100", "Ação", "Matéria-prima",
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
    "M1", "M2", "M3", "M5", "M10", "M15", "M30",
    "H1", "H2", "H4", "D1", "W1", "MN1"
]


def db_init():
    with sqlite3.connect(DB) as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS history(
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


def save(meta, r):
    with sqlite3.connect(DB) as c:
        c.execute("""
        INSERT INTO history(
            created, market, asset, platform, timeframe,
            signal, confidence, entry, sl, tp
        )
        VALUES(?,?,?,?,?,?,?,?,?,?)
        """, (
            datetime.now(timezone.utc).isoformat(),
            meta["market"],
            meta["asset"],
            meta["platform"],
            meta["timeframe"],
            r["signal"],
            r["confidence"],
            r["entry"],
            r["sl"],
            r["tp"]
        ))


def parse_json(s):
    s = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        (s or "").strip(),
        flags=re.I
    )

    try:
        return json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", s, re.S)

        if not m:
            raise ValueError("A IA não devolveu JSON válido.")

        return json.loads(m.group())


def validate(d):
    signal = str(d.get("signal", "")).upper().strip()

    if signal not in ("BUY", "SELL", "AGUARDAR"):
        raise ValueError("Sinal inválido.")

    try:
        confidence = float(d.get("confidence"))
    except:
        raise ValueError("Percentagem inválida.")

    if not 0 <= confidence <= 100:
        raise ValueError("Percentagem fora do intervalo.")

    r = {
        "signal": signal,
        "confidence": round(confidence, 1),
        "entry": str(d.get("entry") or "").strip(),
        "sl": str(d.get("stop_loss") or "").strip(),
        "tp": str(d.get("take_profit") or "").strip()
    }

    if signal == "AGUARDAR":
        return {
            **r,
            "entry": "",
            "sl": "",
            "tp": ""
        }

    if not all((r["entry"], r["sl"], r["tp"])):
        raise ValueError(
            "BUY/SELL sem entrada, SL e TP fundamentados. Sinal recusado."
        )

    return r


def analyze(image, meta, key, model):

    prompt = f"""
És um analista técnico rigoroso.
Analisa somente informação legível na imagem.

Mercado: {meta['market']}
Ativo: {meta['asset']}
Plataforma: {meta['platform']}
Timeframe: {meta['timeframe']}

Escolhe exatamente um resultado:
BUY, SELL ou AGUARDAR.

Avalia:
- Tendência do mercado.
- Estrutura HH/HL/LH/LL.
- Velas e padrões de preço.
- Suportes e resistências.
- Rompimentos e retestes.
- RSI e MACD.
- Médias móveis.
- Fractals e Zig Zag, apenas se estiverem visíveis.

BUY ou SELL só com evidência técnica suficiente.
Caso contrário, escolhe AGUARDAR.

Não inventes preços, escalas, indicadores ou níveis.
Se não conseguires determinar entrada, Stop Loss e Take Profit
a partir da imagem, escolhe AGUARDAR.

A entrada deve ser futura e incluir uma condição objetiva de ativação.

A confiança é uma estimativa da qualidade da evidência visual.
NÃO é uma probabilidade comprovada de lucro.

Responde somente com JSON válido:

{{
"signal":"BUY ou SELL ou AGUARDAR",
"confidence":0,
"entry":"zona/preço futuro e condição de ativação; vazio em AGUARDAR",
"stop_loss":"nível; vazio em AGUARDAR",
"take_profit":"nível; vazio em AGUARDAR"
}}

Sem texto adicional.

Se AGUARDAR, o utilizador verá somente AGUARDAR e a percentagem.
"""

    im = ImageOps.exif_transpose(image).convert("RGB")
    im.thumbnail((1800, 1800))

    b = BytesIO()
    im.save(b, format="JPEG", quality=88, optimize=True)

    payload = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": 700,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": prompt
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/jpeg;base64,"
                        + base64.b64encode(b.getvalue()).decode()
                    }
                }
            ]
        }]
    }

    try:
        resp = requests.post(
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
    except requests.RequestException as e:
        raise RuntimeError(f"Falha de ligação: {e}")

    if resp.status_code == 429:
        raise RuntimeError(
            "Limite de utilização OpenRouter atingido (HTTP 429). "
            "Aguarda a reposição da quota."
        )

    if resp.status_code in (401, 403):
        raise RuntimeError(
            "Chave OpenRouter recusada. Confirma OPENROUTER_API_KEY no Render."
        )

    if resp.status_code >= 400:
        raise RuntimeError(
            f"Erro OpenRouter {resp.status_code}: {resp.text[:900]}"
        )

    try:
        content = resp.json()["choices"][0]["message"]["content"]

        if isinstance(content, list):
            content = "\n".join(
                x.get("text", "")
                for x in content
                if isinstance(x, dict)
            )

        return validate(parse_json(content))

    except (
        KeyError,
        IndexError,
        TypeError,
        json.JSONDecodeError,
        ValueError
    ) as e:
        raise RuntimeError(f"Resposta inválida/incompleta da IA: {e}")


# INICIALIZAÇÃO

db_init()

st.markdown(
    f"""
    <div class="hero">
        <div class="small">V9.0 · AI TRADING CHART ANALYZER</div>
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
        list(MARKETS)
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


# ÁREA PRINCIPAL

c1, c2 = st.columns(
    [1.1, 0.9],
    gap="large"
)


with c1:

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


with c2:

    st.subheader("Resultado")

    if run:

        key = os.getenv(
            "OPENROUTER_API_KEY",
            ""
        ).strip()

        if preview is None:
            st.warning("Carrega primeiro um screenshot válido.")

        elif not key:
            st.error(
                "Configura OPENROUTER_API_KEY "
                "nas Environment Variables do Render."
            )

        elif not model.strip():
            st.error("Indica um modelo OpenRouter.")

        else:

            meta = {
                "market": market,
                "asset": asset,
                "platform": platform,
                "timeframe": timeframe
            }

            with st.spinner("A analisar o gráfico..."):

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

                except Exception as e:

                    st.session_state.pop(
                        "v9_result",
                        None
                    )

                    st.error(str(e))

    result = st.session_state.get("v9_result")

    if result:

        sig = result["signal"]

        css = {
            "BUY": "buy",
            "SELL": "sell",
            "AGUARDAR": "wait"
        }[sig]

        st.markdown(
            f"""
            <div class="box">
                <div class="{css}">
                    {sig} — {result["confidence"]:.1f}%
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        if sig in ("BUY", "SELL"):

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

with sqlite3.connect(DB) as c:

    rows = c.execute("""
        SELECT created, market, asset, platform,
        timeframe, signal, confidence
        FROM history
        ORDER BY id DESC
        LIMIT 50
    """).fetchall()


if rows:

    st.dataframe(
        [
            {
                "Data UTC": x[0][:19].replace("T", " "),
                "Mercado": x[1],
                "Ativo": x[2],
                "Plataforma": x[3],
                "Timeframe": x[4],
                "Sinal": x[5],
                "Confiança": f"{x[6]:.1f}%"
            }
            for x in rows
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
    cotações em tempo real nem executa ordens. Testa em Demo
    antes de considerar dinheiro real.
    </div>
    """,
    unsafe_allow_html=True
)
