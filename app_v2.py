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

# ---------------- Database: local SQLite ----------------
def connect_db():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("""
    CREATE TABLE IF NOT EXISTS signals(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_at TEXT NOT NULL, category TEXT NOT NULL, asset TEXT NOT NULL,
      timeframe TEXT NOT NULL, platform TEXT NOT NULL, direction TEXT NOT NULL,
      score INTEGER, entry TEXT, activation TEXT, stop_loss TEXT,
      tp1 TEXT, tp2 TEXT, rationale TEXT, report TEXT NOT NULL,
      outcome TEXT NOT NULL DEFAULT 'ABERTO', notes TEXT DEFAULT ''
    )""")
    con.commit()
    return con

def save_signal(r):
    con = connect_db()
    cur = con.execute("""
    INSERT INTO signals(created_at,category,asset,timeframe,platform,direction,
      score,entry,activation,stop_loss,tp1,tp2,rationale,report)
    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (r["created_at"],r["category"],r["asset"],r["timeframe"],r["platform"],
          r["direction"],r["score"],r["entry"],r["activation"],r["sl"],
          r["tp1"],r["tp2"],r["rationale"],r["report"]))
    con.commit()
    sid = cur.lastrowid
    con.close()
    return sid

def all_signals():
    con = connect_db()
    rows = [dict(x) for x in con.execute("SELECT * FROM signals ORDER BY id DESC")]
    con.close()
    return rows

def set_outcome(sid, outcome, notes):
    con = connect_db()
    con.execute("UPDATE signals SET outcome=?, notes=? WHERE id=?",
                (outcome, notes, sid))
    con.commit()
    con.close()

# ---------------- Market universe ----------------
FOREX = [
 "EUR/USD","GBP/USD","USD/JPY","USD/CHF","AUD/USD","NZD/USD","USD/CAD",
 "EUR/GBP","EUR/JPY","GBP/JPY","AUD/JPY","EUR/CHF","GBP/CHF",
 "EUR/AUD","GBP/AUD","AUD/NZD","XAU/USD","XAG/USD"
]
STOCK_INDICES = [
 "NAS100 / Nasdaq 100","US30 / Dow Jones","US500 / S&P 500",
 "GER40 / DAX","UK100 / FTSE 100","JP225 / Nikkei 225",
 "AUS200 / ASX 200","EU50 / Euro Stoxx 50","HK50 / Hang Seng"
]
SYNTHETIC = [
 "Boom 1000 Index","Crash 1000 Index","Boom 500 Index","Crash 500 Index",
 "Boom 300 Index","Crash 300 Index","Boom 100 Index","Crash 100 Index",
 "Boom 50 Index","Crash 50 Index","Jump 10 Index","Jump 25 Index",
 "Jump 50 Index","Jump 75 Index","Jump 100 Index","Step Index"
]
TIMEFRAMES = ["M1","M5","M15","M30","H1","H4","D1","W1"]
PLATFORMS = ["Deriv MT5","Deriv cTrader","TradingView","MetaTrader 4","Outra"]

def extract(report, label):
    m = re.search(rf"(?im)^\s*{re.escape(label)}\s*:\s*(.+?)\s*$", report)
    return m.group(1).strip() if m else ""

def parse_direction(report):
    patterns = [
        r"(?im)^\s*DIREÇÃO\s*:\s*(BUY|SELL|AGUARDAR)\b",
        r"(?im)^\s*(?:SINAL|DECISÃO)\s*:\s*(BUY|SELL|AGUARDAR)\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, report)
        if m:
            return m.group(1).upper()
    return None


def parse_score(report):
    patterns = [
        r"(?im)^\s*PONTUAÇÃO TÉCNICA\s*:\s*(\d{1,3})\s*/\s*100",
        r"(?im)^\s*FORÇA (?:BUY|SELL)\s*:\s*(\d{1,3})\s*%",
    ]
    for pattern in patterns:
        m = re.search(pattern, report)
        if m:
            return max(0, min(100, int(m.group(1))))
    return None


def parse_action(report):
    value = extract(report, "AÇÃO").upper()
    if value.startswith("ENTRAR"):
        return "ENTRAR"
    if value.startswith("AGUARDAR"):
        return "AGUARDAR"
    return "AGUARDAR"


def valid_level(value):
    if not value:
        return False
    bad = ("não identificável", "não determinável", "não indicado", "não visível", "não aplicável")
    return not any(x in value.lower() for x in bad)


def safe_action(report):
    """Só autoriza ENTRAR se houver gatilho e níveis ativos minimamente preenchidos."""
    if parse_action(report) != "ENTRAR":
        return "AGUARDAR"
    required = [extract(report, "ATIVAÇÃO"), extract(report, "ENTRADA ATIVA"),
                extract(report, "STOP LOSS ATIVO"), extract(report, "TAKE PROFIT 1 ATIVO")]
    return "ENTRAR" if all(valid_level(x) for x in required) else "AGUARDAR"

def make_prompt(category, asset, timeframe, platform, context):
    market_rules = {
      "Forex": "Forex: considera sessões, liquidez e volatilidade, sem alegar acesso a notícias.",
      "Índices bolsistas": "Índices bolsistas: considera horário, gaps e volatilidade.",
      "Índices sintéticos": "Sintéticos: distingue Boom, Crash, Jump e Step. Não afirmes prever spikes.",
      "Outro": "Identifica o instrumento apenas se a imagem permitir."
    }
    return f"""
És o motor técnico do {APP_NAME}. Responde em português simples e profissional.
CONTEXTO: categoria={category}; ativo={asset}; timeframe={timeframe}; plataforma={platform}; observações={context or 'não fornecidas'}.
{market_rules[category]}

REGRAS IMPORTANTES:
- Tens apenas o screenshot; não tens OHLC nem preços ao vivo.
- Não inventes preços, indicadores, níveis, volume, notícias ou confirmações.
- Lê EMA, RSI, MACD, Zig Zag e Fractals apenas se estiverem visíveis e legíveis.
- Analisa estrutura HH/HL/LH/LL, velas, suportes/resistências, liquidez, rompimento e reteste.
- Compara BUY e SELL separadamente. Dá duas forças técnicas independentes entre 0 e 100; são avaliações subjetivas, NÃO probabilidades de vitória.
- DIREÇÃO indica o lado tecnicamente mais favorecido, mesmo que a força seja modesta. AÇÃO é separada: ENTRAR só com gatilho observável e entrada, SL e TP coerentes; caso contrário AGUARDAR.
- Quando AÇÃO=AGUARDAR, apresenta os dois cenários potenciais BUY e SELL, incluindo zonas, SL e TP apenas se forem identificáveis. Se não, escreve exatamente: Não identificável no gráfico — não inventar.
- Se a imagem for insuficiente, usa DIREÇÃO=AGUARDAR e AÇÃO=AGUARDAR; não fabriques níveis.
- Níveis numéricos apenas se a escala de preço estiver legível. Caso contrário usa referência visual concreta ou a frase de não identificação.
- Não prometas taxa de acerto nem lucro.

DEVOLVE EXATAMENTE ESTES CAMPOS, UMA LINHA POR CAMPO:
DIREÇÃO: BUY / SELL / AGUARDAR
FORÇA BUY: __%
FORÇA SELL: __%
AÇÃO: ENTRAR / AGUARDAR
QUALIDADE DA IMAGEM: BOA / LIMITADA / INSUFICIENTE
TENDÊNCIA E ESTRUTURA: ...
ZONA BUY: ...
SL BUY: ...
TP1 BUY: ...
TP2 BUY: ...
ZONA SELL: ...
SL SELL: ...
TP1 SELL: ...
TP2 SELL: ...
ATIVAÇÃO: ...
ENTRADA ATIVA: ...
STOP LOSS ATIVO: ...
TAKE PROFIT 1 ATIVO: ...
TAKE PROFIT 2 ATIVO: ...
RISCO/RETORNO: ...
MOTIVO DA DECISÃO: ...
CONFIRMAÇÕES VISÍVEIS: ...
INVALIDAÇÃO: ...
O QUE FALTA CONFIRMAR: ...
"""

def image_to_base64(upload):
    img = Image.open(upload)
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((1600,1600))
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=88, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def ask_vision_model(image64, prompt, key, model):
    headers = {
      "Authorization": f"Bearer {key}",
      "Content-Type": "application/json",
      "HTTP-Referer": "https://doncullertrade47.onrender.com",
      "X-Title": APP_NAME
    }
    payload = {
      "model": model,
      "messages": [{"role":"user","content":[
        {"type":"text","text":prompt},
        {"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{image64}"}}
      ]}],
      "temperature":0.1,
      "max_tokens":3500
    }
    try:
        res = requests.post(API_URL, headers=headers, json=payload, timeout=(20,180))
    except requests.exceptions.Timeout:
        raise RuntimeError("Tempo de resposta excedido. Tenta novamente.")
    except requests.exceptions.ConnectionError:
        raise RuntimeError("Não foi possível ligar ao OpenRouter.")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Erro de ligação: {e}")
    if res.status_code != 200:
        try:
            err = res.json().get("error",{}).get("message",res.text)
        except Exception:
            err = res.text
        raise RuntimeError(f"OpenRouter HTTP {res.status_code}: {err}")
    try:
        data = res.json()
        choice = data["choices"][0]
        content = choice["message"]["content"]
    except (ValueError,KeyError,IndexError,TypeError):
        raise RuntimeError("Resposta inesperada ou vazia do modelo.")
    if isinstance(content,list):
        content = "\n".join(x.get("text","") for x in content if isinstance(x,dict))
    if not isinstance(content,str) or not content.strip():
        raise RuntimeError("O modelo devolveu uma resposta vazia.")
    if choice.get("finish_reason") == "length":
        content += "\n\nAVISO: resposta possivelmente incompleta (limite de tokens)."
    return content

# ---------------- Sidebar ----------------
st.markdown("<h1 style='text-align:center'>🦁 DONCULLER-TRADE47</h1>"
            "<p style='text-align:center;color:#9db0c3'>AI Trading Chart Analyzer · V8</p>",
            unsafe_allow_html=True)
st.divider()

with st.sidebar:
    st.header("⚙️ Configuração")
    category = st.selectbox("Categoria", ["Forex","Índices bolsistas","Índices sintéticos","Outro"])
    if category == "Forex":
        choice = st.selectbox("Par / instrumento", FOREX + ["Outro par"])
    elif category == "Índices bolsistas":
        choice = st.selectbox("Índice", STOCK_INDICES + ["Outro índice"])
    elif category == "Índices sintéticos":
        choice = st.selectbox("Índice sintético", SYNTHETIC + ["Outro sintético"])
    else:
        choice = "Outro"
    if choice.startswith("Outro") or choice == "Outro":
        asset = st.text_input("Nome exato do ativo", placeholder="Ex.: BTC/USD, US100, ETH/USD")
    else:
        asset = choice
    timeframe = st.selectbox("Timeframe", TIMEFRAMES, index=2)
    platform = st.selectbox("Plataforma", PLATFORMS)
    context = st.text_area("Contexto adicional (opcional)",
                           placeholder="Ex.: indicadores visíveis, sessão, níveis...")
    st.caption("A opção Outro aceita instrumentos fora das listas.")

api_key = os.getenv("OPENROUTER_API_KEY","").strip()
model = os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL

tab1, tab2, tab3 = st.tabs(["📊 Analisador","🗂️ Histórico WIN/LOSS","📈 Desempenho"])

with tab1:
    st.subheader("Análise do gráfico")
    st.info("Carrega um screenshot nítido. A análise por imagem não equivale a dados OHLC nem a uma cotação em tempo real.")
    upload = st.file_uploader("Screenshot do gráfico", type=["png","jpg","jpeg"])
    if upload:
        try:
            st.image(upload, caption=f"{asset or 'Ativo'} · {timeframe}", use_container_width=True)
        except (UnidentifiedImageError,OSError):
            st.error("O ficheiro não é uma imagem válida.")
    if st.button("🦁 ANALISAR GRÁFICO", use_container_width=True):
        if not api_key:
            st.error("Configura OPENROUTER_API_KEY nas Environment Variables do Render.")
        elif not asset.strip():
            st.warning("Indica o nome do ativo.")
        elif not upload:
            st.warning("Carrega primeiro um screenshot.")
        else:
            try:
                with st.spinner("A comparar BUY e SELL e a analisar o gráfico..."):
                    upload.seek(0)
                    encoded = image_to_base64(upload)
                    prompt = make_prompt(category,asset,timeframe,platform,context)
                    report = ask_vision_model(encoded,prompt,api_key,model)
                direction = parse_direction(report)
                if direction is None:
                    st.error("A resposta da IA veio fora do formato esperado. A análise não foi registada; tenta novamente.")
                    st.stop()
                action = safe_action(report)
                # Compatibilidade com a base SQLite existente: mantêm-se as mesmas colunas.
                active_entry = extract(report, "ENTRADA ATIVA") if action == "ENTRAR" else ""
                active_sl = extract(report, "STOP LOSS ATIVO") if action == "ENTRAR" else ""
                active_tp1 = extract(report, "TAKE PROFIT 1 ATIVO") if action == "ENTRAR" else ""
                active_tp2 = extract(report, "TAKE PROFIT 2 ATIVO") if action == "ENTRAR" else ""
                rec = {
                  "created_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "category":category,"asset":asset,"timeframe":timeframe,
                  "platform":platform,"direction":direction,
                  "score":parse_score(report),"entry":active_entry,
                  "activation":extract(report,"ATIVAÇÃO"),"sl":active_sl,
                  "tp1":active_tp1,"tp2":active_tp2,
                  "rationale":extract(report,"MOTIVO DA DECISÃO"),"report":report
                }
                sid = save_signal(rec)
                st.session_state["report"] = report
                st.session_state["direction"] = direction
                st.session_state["action"] = action
                st.session_state["signal_id"] = sid
                st.success(f"Análise guardada no histórico. ID #{sid}.")
            except Exception as e:
                st.error(str(e))

    if "report" in st.session_state:
        direction = st.session_state["direction"]
        report = st.session_state["report"]
        action = safe_action(report)
        buy_strength = extract(report, "FORÇA BUY") or "Não indicada"
        sell_strength = extract(report, "FORÇA SELL") or "Não indicada"
        score = parse_score(report)
        if direction == "BUY":
            st.markdown('<div class="card"><div class="buy">🟢 DIREÇÃO: BUY</div></div>', unsafe_allow_html=True)
        elif direction == "SELL":
            st.markdown('<div class="card"><div class="sell">🔴 DIREÇÃO: SELL</div></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="card"><div class="wait">🟡 DIREÇÃO: AGUARDAR</div></div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("Força BUY", buy_strength)
        c2.metric("Força SELL", sell_strength)
        c3.metric("AÇÃO", action)
        if action == "AGUARDAR":
            st.warning("AGUARDAR — NÃO ENTRAR. Os cenários abaixo são apenas níveis potenciais, não ordens ativas.")
        else:
            st.success("ENTRADA autorizada pelo relatório. Confirma o gatilho no gráfico antes de executar.")
        st.caption("Forças técnicas estimadas pela leitura visual; não são probabilidades estatísticas de vitória.")

        def show_fields(title, fields):
            with st.container(border=True):
                st.markdown(f"**{title}**")
                for label, key in fields:
                    value = extract(report, key) or "Não identificável no gráfico — não inventar"
                    st.markdown(f"**{label}:** {value}")

        show_fields("🟢 CENÁRIO POTENCIAL BUY", [("Zona de entrada", "ZONA BUY"), ("Stop Loss", "SL BUY"), ("Take Profit 1", "TP1 BUY"), ("Take Profit 2", "TP2 BUY")])
        show_fields("🔴 CENÁRIO POTENCIAL SELL", [("Zona de entrada", "ZONA SELL"), ("Stop Loss", "SL SELL"), ("Take Profit 1", "TP1 SELL"), ("Take Profit 2", "TP2 SELL")])
        if action == "ENTRAR":
            show_fields("🎯 ORDEM ATIVA (condicionada à confirmação)", [("Ativação", "ATIVAÇÃO"), ("Entrada", "ENTRADA ATIVA"), ("Stop Loss", "STOP LOSS ATIVO"), ("Take Profit 1", "TAKE PROFIT 1 ATIVO"), ("Take Profit 2", "TAKE PROFIT 2 ATIVO"), ("Risco/Retorno", "RISCO/RETORNO")])
        show_fields("📊 LEITURA DO GRÁFICO", [("Qualidade da imagem", "QUALIDADE DA IMAGEM"), ("Tendência e estrutura", "TENDÊNCIA E ESTRUTURA"), ("Motivo da decisão", "MOTIVO DA DECISÃO"), ("Confirmações visíveis", "CONFIRMAÇÕES VISÍVEIS"), ("Invalidação", "INVALIDAÇÃO"), ("O que falta confirmar", "O QUE FALTA CONFIRMAR")])
        with st.expander("Ver relatório original completo"):
            st.text(report)
        st.download_button("📥 Descarregar relatório", report,
                           file_name=f"donculler_sinal_{st.session_state['signal_id']}.txt",
                           mime="text/plain")

with tab2:
    st.subheader("Histórico de sinais")
    records = all_signals()
    if not records:
        st.info("Ainda não existem sinais registados.")
    for r in records:
        title = f"#{r['id']} · {r['created_at'][:19]} · {r['asset']} · {r['timeframe']} · {r['direction']} · {r['outcome']}"
        with st.expander(title):
            st.write(f"Categoria: {r['category']} | Plataforma: {r['platform']}")
            st.write(f"Score técnico: {r['score'] if r['score'] is not None else 'Não indicado'}/100")
            st.write(f"Entrada: {r['entry'] or 'Não indicada'}")
            st.write(f"SL: {r['stop_loss'] or 'Não indicado'} | TP1: {r['tp1'] or 'Não indicado'} | TP2: {r['tp2'] or 'Não indicado'}")
            st.text_area("Relatório",r["report"],height=220,key=f"rep_{r['id']}")
            with st.form(f"form_{r['id']}"):
                outcome = st.selectbox("Resultado",["ABERTO","WIN","LOSS","BREAKEVEN","CANCELADO"],
                    index=["ABERTO","WIN","LOSS","BREAKEVEN","CANCELADO"].index(r["outcome"]),
                    key=f"out_{r['id']}")
                notes = st.text_input("Notas / preço de saída / custos",value=r["notes"] or "",
                                      key=f"note_{r['id']}")
                if st.form_submit_button("Guardar resultado"):
                    set_outcome(r["id"],outcome,notes)
                    st.success("Resultado atualizado.")
                    st.rerun()

with tab3:
    st.subheader("Desempenho registado")
    records = all_signals()
    closed = [r for r in records if r["outcome"] in ("WIN","LOSS","BREAKEVEN")]
    wins = sum(r["outcome"]=="WIN" for r in closed)
    losses = sum(r["outcome"]=="LOSS" for r in closed)
    be = sum(r["outcome"]=="BREAKEVEN" for r in closed)
    total_decisive = wins+losses
    rate = f"{wins/total_decisive*100:.1f}%" if total_decisive else "Sem dados"
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Sinais",len(records)); c2.metric("WIN",wins)
    c3.metric("LOSS",losses); c4.metric("BREAKEVEN",be)
    st.metric("Taxa de acerto WIN/(WIN+LOSS)",rate)
    st.caption("Resultados introduzidos manualmente; ainda não são verificados por feed de mercado. BE não entra no cálculo da taxa.")
    grouped = {}
    for r in closed:
        grouped.setdefault(r["asset"],{"WIN":0,"LOSS":0,"BREAKEVEN":0})
        grouped[r["asset"]][r["outcome"]] += 1
    if grouped:
        st.markdown("#### Resultados por ativo")
        for name, vals in sorted(grouped.items()):
            n = vals["WIN"]+vals["LOSS"]
            wr = f"{vals['WIN']/n*100:.1f}%" if n else "Sem dados"
            st.write(f"**{name}:** {vals['WIN']} WIN · {vals['LOSS']} LOSS · {vals['BREAKEVEN']} BE · {wr}")

st.divider()
st.caption("A pontuação técnica não é probabilidade de vitória. Não existe garantia de 100% de acerto. Testa em Demo e considera spread, comissão e slippage.")
st.caption(f"Modelo multimodal configurado: {model}")
