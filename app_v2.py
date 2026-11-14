import os
import re
import base64
import sqlite3
from io import BytesIO
from datetime import datetime, timezone

import requests
import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError

APP_NAME = "DONCULLER-TRADE47"
DB_PATH = os.getenv("SIGNAL_DB_PATH", "donculler_signals.db")
API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "nvidia/nemotron-3.5-super-vl:free"

st.set_page_config(page_title=APP_NAME, page_icon="🦁", layout="wide")

st.markdown("""
<style>
.stApp{background:#071321;color:#e8eef5}
[data-testid="stSidebar"]{background:#0b1b2d}
.block-container{max-width:1250px;padding-top:1.5rem}
h1,h2,h3{color:#f0f5fa}
div[data-testid="stMetric"]{background:#0d2033;border:1px solid #203a52;padding:12px;border-radius:10px}
.card{background:#0d2033;border:1px solid #203a52;border-radius:12px;padding:16px;margin:8px 0}
.buy{color:#25d887;font-size:28px;font-weight:800}
.sell{color:#ff6874;font-size:28px;font-weight:800}
.wait{color:#ffc857;font-size:28px;font-weight:800}
</style>
""", unsafe_allow_html=True)


# ---------------- DATABASE ----------------

def connect_db():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row

    con.execute("""
    CREATE TABLE IF NOT EXISTS signals(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_at TEXT NOT NULL,
      category TEXT NOT NULL,
      asset TEXT NOT NULL,
      timeframe TEXT NOT NULL,
      platform TEXT NOT NULL,
      direction TEXT NOT NULL,
      score INTEGER,
      entry TEXT,
      activation TEXT,
      stop_loss TEXT,
      tp1 TEXT,
      tp2 TEXT,
      rationale TEXT,
      report TEXT NOT NULL,
      outcome TEXT NOT NULL DEFAULT 'ABERTO',
      notes TEXT DEFAULT ''
    )
    """)

    con.commit()
    return con


def save_signal(r):
    con = connect_db()

    cur = con.execute("""
    INSERT INTO signals(
      created_at,category,asset,timeframe,platform,direction,
      score,entry,activation,stop_loss,tp1,tp2,rationale,report
    )
    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        r["created_at"], r["category"], r["asset"],
        r["timeframe"], r["platform"], r["direction"],
        r["score"], r["entry"], r["activation"],
        r["sl"], r["tp1"], r["tp2"],
        r["rationale"], r["report"]
    ))

    con.commit()
    sid = cur.lastrowid
    con.close()

    return sid


def all_signals():
    con = connect_db()
    rows = [
        dict(x) for x in
        con.execute("SELECT * FROM signals ORDER BY id DESC")
    ]
    con.close()
    return rows


def set_outcome(sid, outcome, notes):
    con = connect_db()

    con.execute(
        "UPDATE signals SET outcome=?, notes=? WHERE id=?",
        (outcome, notes, sid)
    )

    con.commit()
    con.close()


# ---------------- ATIVOS ----------------

FOREX = [
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF",
    "AUD/USD", "NZD/USD", "USD/CAD",
    "EUR/GBP", "EUR/JPY", "GBP/JPY", "AUD/JPY",
    "EUR/CHF", "GBP/CHF", "EUR/AUD", "GBP/AUD",
    "AUD/NZD", "XAU/USD", "XAG/USD"
]

STOCK_INDICES = [
    "NAS100 / Nasdaq 100",
    "US30 / Dow Jones",
    "US500 / S&P 500",
    "GER40 / DAX",
    "UK100 / FTSE 100",
    "JP225 / Nikkei 225",
    "AUS200 / ASX 200",
    "EU50 / Euro Stoxx 50",
    "HK50 / Hang Seng"
]

SYNTHETIC = [
    "Boom 1000 Index", "Crash 1000 Index",
    "Boom 500 Index", "Crash 500 Index",
    "Boom 300 Index", "Crash 300 Index",
    "Boom 100 Index", "Crash 100 Index",
    "Boom 50 Index", "Crash 50 Index",
    "Jump 10 Index", "Jump 25 Index",
    "Jump 50 Index", "Jump 75 Index",
    "Jump 100 Index", "Step Index"
]

TIMEFRAMES = [
    "M1", "M5", "M15", "M30",
    "H1", "H4", "D1", "W1"
]

PLATFORMS = [
    "Deriv MT5",
    "Deriv cTrader",
    "TradingView",
    "MetaTrader 4",
    "Outra"
]


# ---------------- EXTRAÇÃO DO RELATÓRIO ----------------

def extract(report, label):
    m = re.search(
        rf"(?im)^\s*{re.escape(label)}\s*:\s*(.+?)\s*$",
        report
    )

    return m.group(1).strip() if m else ""


def parse_direction(report):
    m = re.search(
        r"(?im)^\s*DIREÇÃO\s*:\s*(BUY|SELL|AGUARDAR)\b",
        report
    )

    return m.group(1).upper() if m else "AGUARDAR"


def parse_score(report):
    m = re.search(
        r"(?i)PONTUAÇÃO TÉCNICA\s*:\s*(\d{1,3})\s*/\s*100",
        report
    )

    return max(0, min(100, int(m.group(1)))) if m else None


# ---------------- MOTOR DE ANÁLISE ----------------

def make_prompt(category, asset, timeframe, platform, context):

    market_rules = {
        "Forex": (
            "Mercado Forex: considera sessões, liquidez e volatilidade. "
            "Não afirmes consultar notícias ou calendário económico sem fonte de dados."
        ),

        "Índices bolsistas": (
            "Índices de bolsa: considera horário da bolsa, gaps e volatilidade. "
            "Não confundas NAS100/US30/US500/GER40 com Forex ou sintéticos."
        ),

        "Índices sintéticos": (
            "Sintéticos: distingue cada Boom, Crash, Jump e Step. "
            "Não afirmes prever spikes nem inventes probabilidades de spike."
        ),

        "Outro": (
            "Outro mercado: identifica o instrumento pelo nome e imagem. "
            "Se não conseguires identificar a classe, declara essa limitação."
        )
    }

    return f"""
És o motor de análise técnica do {APP_NAME}.

Responde em português simples, objetivo e profissional.
A qualidade do sinal é mais importante do que gerar muitos sinais.

CONTEXTO:
Categoria: {category}
Ativo: {asset}
Timeframe: {timeframe}
Plataforma: {platform}
Observações: {context or 'Não fornecidas'}

{market_rules[category]}

LIMITES DA FONTE:

Recebes apenas um screenshot.
Não tens feed OHLC, cotações ao vivo, histórico completo,
notícias, spread ou volume real, salvo se estiverem
explicitamente visíveis e legíveis na imagem.

Não inventes preços, valores de indicadores, notícias
ou confirmações.

Se a escala ou o preço não estiver legível,
não forneças níveis numéricos fictícios.

PROCESSO OBRIGATÓRIO:

1. Avalia a qualidade e legibilidade da imagem.
2. Analisa tendência e estrutura HH, HL, LH e LL.
3. Analisa velas, suportes e resistências.
4. Analisa oferta, procura, rompimentos e retestes.
5. Analisa liquidez e possíveis varrimentos.
6. Avalia EMA, RSI, MACD, Zig Zag e Fractals
   apenas quando estiverem visíveis.
7. Compara o cenário BUY com o cenário SELL.
8. Identifica o cenário com melhor evidência.
9. Verifica entrada, ativação e invalidação.
10. Não forces BUY ou SELL.
11. Usa AGUARDAR quando não existir vantagem técnica demonstrável.

A pontuação de 0 a 100 é um score técnico subjetivo,
NÃO é uma probabilidade de vitória.

FORMATO EXATO:

DIREÇÃO: BUY / SELL / AGUARDAR
PONTUAÇÃO TÉCNICA: __/100 (não é probabilidade)
QUALIDADE DA IMAGEM: BOA / LIMITADA / INSUFICIENTE
TENDÊNCIA E ESTRUTURA: ...
CENÁRIO BUY: ...
CENÁRIO SELL: ...
MOTIVO DA DECISÃO: ...
ENTRADA: ...
ATIVAÇÃO: ...
STOP LOSS: ...
TAKE PROFIT 1: ...
TAKE PROFIT 2: ...
RISCO/RETORNO: ...
CONFIRMAÇÕES VISÍVEIS: ...
INVALIDAÇÃO: ...
O QUE FALTA CONFIRMAR: ...

Quando a imagem for insuficiente, diz isso sem inventar uma análise.
"""


# ---------------- IMAGEM ----------------

def image_to_base64(upload):

    img = Image.open(upload)
    img = ImageOps.exif_transpose(img).convert("RGB")

    img.thumbnail((1600, 1600))

    buf = BytesIO()

    img.save(
        buf,
        format="JPEG",
        quality=88,
        optimize=True
    )

    return base64.b64encode(
        buf.getvalue()
    ).decode("utf-8")


# ---------------- OPENROUTER ----------------

def ask_vision_model(image64, prompt, key, model):

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://doncullertrade47.onrender.com",
        "X-Title": APP_NAME
    }

    # Envia apenas UM modelo.
    # Não envia lista "models" nem alternativas automáticas.

    payload = {
        "model": model,

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
                            "url": f"data:image/jpeg;base64,{image64}"
                        }
                    }
                ]
            }
        ],

        "temperature": 0.1,
        "max_tokens": 3500
    }

    try:
        res = requests.post(
            API_URL,
            headers=headers,
            json=payload,
            timeout=(20, 180)
        )

    except requests.exceptions.Timeout:
        raise RuntimeError(
            "Tempo de resposta excedido. Tenta novamente."
        )

    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Não foi possível ligar ao OpenRouter."
        )

    except requests.exceptions.RequestException as e:
        raise RuntimeError(
            f"Erro de ligação: {e}"
        )

    if res.status_code != 200:

        try:
            err = res.json().get(
                "error", {}
            ).get("message", res.text)

        except Exception:
            err = res.text

        raise RuntimeError(
            f"OpenRouter HTTP {res.status_code}: {err}"
        )

    try:
        data = res.json()
        choice = data["choices"][0]
        content = choice["message"]["content"]

    except (ValueError, KeyError, IndexError, TypeError):
        raise RuntimeError(
            "Resposta inesperada ou vazia do modelo."
        )

    if isinstance(content, list):
        content = "\n".join(
            x.get("text", "")
            for x in content
            if isinstance(x, dict)
        )

    if not isinstance(content, str) or not content.strip():
        raise RuntimeError(
            "O modelo devolveu uma resposta vazia."
        )

    if choice.get("finish_reason") == "length":
        content += (
            "\n\nAVISO: resposta possivelmente incompleta "
            "(limite de tokens)."
        )

    return content


# ---------------- INTERFACE ----------------

st.markdown(
    "<h1 style='text-align:center'>🦁 DONCULLER-TRADE47</h1>"
    "<p style='text-align:center;color:#9db0c3'>"
    "AI Trading Chart Analyzer · V6.1"
    "</p>",
    unsafe_allow_html=True
)

st.divider()


# ---------------- CONFIGURAÇÃO ----------------

with st.sidebar:

    st.header("⚙️ Configuração")

    category = st.selectbox(
        "Categoria",
        [
            "Forex",
            "Índices bolsistas",
            "Índices sintéticos",
            "Outro"
        ]
    )

    if category == "Forex":
        choice = st.selectbox(
            "Par / instrumento",
            FOREX + ["Outro par"]
        )

    elif category == "Índices bolsistas":
        choice = st.selectbox(
            "Índice",
            STOCK_INDICES + ["Outro índice"]
        )

    elif category == "Índices sintéticos":
        choice = st.selectbox(
            "Índice sintético",
            SYNTHETIC + ["Outro sintético"]
        )

    else:
        choice = "Outro"

    if choice.startswith("Outro") or choice == "Outro":

        asset = st.text_input(
            "Nome exato do ativo",
            placeholder="Ex.: BTC/USD, US100, ETH/USD"
        )

    else:
        asset = choice

    timeframe = st.selectbox(
        "Timeframe",
        TIMEFRAMES,
        index=2
    )

    platform = st.selectbox(
        "Plataforma",
        PLATFORMS
    )

    context = st.text_area(
        "Contexto adicional (opcional)",
        placeholder="Ex.: indicadores visíveis, sessão, níveis..."
    )

    st.caption(
        "A opção Outro aceita instrumentos fora das listas."
    )


# ---------------- CHAVE E MODELO ----------------

api_key = os.getenv(
    "OPENROUTER_API_KEY", ""
).strip()

# Modelo fixo para evitar que OPENROUTER_MODEL
# substitua o modelo ou encaminhe para vários modelos.

model = DEFAULT_MODEL


# ---------------- ABAS ----------------

tab1, tab2, tab3 = st.tabs([
    "📊 Analisador",
    "🗂️ Histórico WIN/LOSS",
    "📈 Desempenho"
])


# ---------------- ANALISADOR ----------------

with tab1:

    st.subheader("Análise do gráfico")

    st.info(
        "Carrega um screenshot nítido. "
        "A análise por imagem não equivale a dados OHLC "
        "nem a uma cotação em tempo real."
    )

    upload = st.file_uploader(
        "Screenshot do gráfico",
        type=["png", "jpg", "jpeg"]
    )

    if upload:

        try:
            st.image(
                upload,
                caption=f"{asset or 'Ativo'} · {timeframe}",
                use_container_width=True
            )

        except (UnidentifiedImageError, OSError):
            st.error(
                "O ficheiro não é uma imagem válida."
            )

    if st.button(
        "🦁 ANALISAR GRÁFICO",
        use_container_width=True
    ):

        if not api_key:

            st.error(
                "Configura OPENROUTER_API_KEY "
                "nas Environment Variables do Render."
            )

        elif not asset.strip():

            st.warning(
                "Indica o nome do ativo."
            )

        elif not upload:

            st.warning(
                "Carrega primeiro um screenshot."
            )

        else:

            try:

                with st.spinner(
                    "A comparar BUY e SELL e a analisar o gráfico..."
                ):

                    upload.seek(0)

                    encoded = image_to_base64(upload)

                    prompt = make_prompt(
                        category,
                        asset,
                        timeframe,
                        platform,
                        context
                    )

                    report = ask_vision_model(
                        encoded,
                        prompt,
                        api_key,
                        model
                    )

                direction = parse_direction(report)

                rec = {
                    "created_at": datetime.now(
                        timezone.utc
                    ).isoformat(timespec="seconds"),

                    "category": category,
                    "asset": asset,
                    "timeframe": timeframe,
                    "platform": platform,
                    "direction": direction,
                    "score": parse_score(report),

                    "entry": extract(report, "ENTRADA"),
                    "activation": extract(report, "ATIVAÇÃO"),
                    "sl": extract(report, "STOP LOSS"),
                    "tp1": extract(report, "TAKE PROFIT 1"),
                    "tp2": extract(report, "TAKE PROFIT 2"),

                    "rationale": extract(
                        report,
                        "MOTIVO DA DECISÃO"
                    ),

                    "report": report
                }

                sid = save_signal(rec)

                st.session_state["report"] = report
                st.session_state["direction"] = direction
                st.session_state["signal_id"] = sid

                st.success(
                    f"Análise guardada no histórico. ID #{sid}."
                )

            except Exception as e:

                st.error(str(e))


    # ---------------- RESULTADO ----------------

    if "report" in st.session_state:

        direction = st.session_state["direction"]

        st.markdown(
            '<div class="card">',
            unsafe_allow_html=True
        )

        if direction == "BUY":

            st.markdown(
                '<div class="buy">🟢 BUY</div>',
                unsafe_allow_html=True
            )

        elif direction == "SELL":

            st.markdown(
                '<div class="sell">🔴 SELL</div>',
                unsafe_allow_html=True
            )

        else:

            st.markdown(
                '<div class="wait">🟡 AGUARDAR</div>',
                unsafe_allow_html=True
            )

        st.markdown(
            st.session_state["report"]
        )

        st.markdown(
            "</div>",
            unsafe_allow_html=True
        )

        st.download_button(
            "📥 Descarregar relatório",
            st.session_state["report"],
            file_name=(
                f"donculler_sinal_"
                f"{st.session_state['signal_id']}.txt"
            ),
            mime="text/plain"
        )


# ---------------- HISTÓRICO ----------------

with tab2:

    st.subheader("Histórico de sinais")

    records = all_signals()

    if not records:

        st.info(
            "Ainda não existem sinais registados."
        )

    for r in records:

        title = (
            f"#{r['id']} · {r['created_at'][:19]} · "
            f"{r['asset']} · {r['timeframe']} · "
            f"{r['direction']} · {r['outcome']}"
        )

        with st.expander(title):

            st.write(
                f"Categoria: {r['category']} | "
                f"Plataforma: {r['platform']}"
            )

            st.write(
                f"Score técnico: "
                f"{r['score'] if r['score'] is not None else 'Não indicado'}/100"
            )

            st.write(
                f"Entrada: {r['entry'] or 'Não indicada'}"
            )

            st.write(
                f"SL: {r['stop_loss'] or 'Não indicado'} | "
                f"TP1: {r['tp1'] or 'Não indicado'} | "
                f"TP2: {r['tp2'] or 'Não indicado'}"
            )

            st.text_area(
                "Relatório",
                r["report"],
                height=220,
                key=f"rep_{r['id']}"
            )

            with st.form(f"form_{r['id']}"):

                outcome = st.selectbox(
                    "Resultado",
                    [
                        "ABERTO",
                        "WIN",
                        "LOSS",
                        "BREAKEVEN",
                        "CANCELADO"
                    ],
                    index=[
                        "ABERTO",
                        "WIN",
                        "LOSS",
                        "BREAKEVEN",
                        "CANCELADO"
                    ].index(r["outcome"]),
                    key=f"out_{r['id']}"
                )

                notes = st.text_input(
                    "Notas / preço de saída / custos",
                    value=r["notes"] or "",
                    key=f"note_{r['id']}"
                )

                if st.form_submit_button(
                    "Guardar resultado"
                ):

                    set_outcome(
                        r["id"],
                        outcome,
                        notes
                    )

                    st.success(
                        "Resultado atualizado."
                    )

                    st.rerun()


# ---------------- DESEMPENHO ----------------

with tab3:

    st.subheader("Desempenho registado")

    records = all_signals()

    closed = [
        r for r in records
        if r["outcome"] in (
            "WIN",
            "LOSS",
            "BREAKEVEN"
        )
    ]

    wins = sum(
        r["outcome"] == "WIN"
        for r in closed
    )

    losses = sum(
        r["outcome"] == "LOSS"
        for r in closed
    )

    be = sum(
        r["outcome"] == "BREAKEVEN"
        for r in closed
    )

    total_decisive = wins + losses

    rate = (
        f"{wins / total_decisive * 100:.1f}%"
        if total_decisive
        else "Sem dados"
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Sinais", len(records))
    c2.metric("WIN", wins)
    c3.metric("LOSS", losses)
    c4.metric("BREAKEVEN", be)

    st.metric(
        "Taxa de acerto WIN/(WIN+LOSS)",
        rate
    )

    st.caption(
        "Resultados introduzidos manualmente; "
        "ainda não são verificados por feed de mercado. "
        "BE não entra no cálculo da taxa."
    )

    grouped = {}

    for r in closed:

        grouped.setdefault(
            r["asset"],
            {
                "WIN": 0,
                "LOSS": 0,
                "BREAKEVEN": 0
            }
        )

        grouped[r["asset"]][r["outcome"]] += 1

    if grouped:

        st.markdown(
            "#### Resultados por ativo"
        )

        for name, vals in sorted(grouped.items()):

            n = vals["WIN"] + vals["LOSS"]

            wr = (
                f"{vals['WIN'] / n * 100:.1f}%"
                if n
                else "Sem dados"
            )

            st.write(
                f"**{name}:** "
                f"{vals['WIN']} WIN · "
                f"{vals['LOSS']} LOSS · "
                f"{vals['BREAKEVEN']} BE · "
                f"{wr}"
            )


# ---------------- AVISOS ----------------

st.divider()

st.caption(
    "A pontuação técnica não é probabilidade de vitória. "
    "Não existe garantia de 100% de acerto. "
    "Testa em Demo e considera spread, comissão e slippage."
)

st.caption(
    f"Modelo multimodal fixo: {model}"
)
