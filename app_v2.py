import os, json, time, re, base64
from io import BytesIO
from datetime import datetime, timezone

import requests
import numpy as np
import pandas as pd
import streamlit as st
import websocket
from PIL import Image, ImageOps, UnidentifiedImageError

APP = "DONCULLER-TRADE47"
VERSION = "V18.0"
WS = os.getenv("DERIV_WS_URL", "wss://api.derivws.com/trading/v1/options/ws/public").strip()
OR_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3.5-super-vl:free").strip()
TF = {"M1":60, "M5":300, "M15":900, "M30":1800, "H1":3600, "H4":14400, "D1":86400}
MIN_RR = 1.5
MAX_ENTRY_DISTANCE_ATR = 1.25

st.set_page_config(page_title=APP, page_icon="🦁", layout="wide")
st.markdown("""<style>
.stApp{background:#071321;color:#edf4fb}
section[data-testid="stSidebar"]{background:#0b1b2d}
.hero,.box{background:#0d2033;border:1px solid #24445e;border-radius:14px;padding:18px}
.buy{color:#25d887;font-size:30px;font-weight:800}
.sell{color:#ff6874;font-size:30px;font-weight:800}
.wait{color:#ffc857;font-size:30px;font-weight:800}
.small{color:#9fb3c8;font-size:13px}
div.stButton>button{background:#16865f;color:white;font-weight:700;min-height:46px}
</style>""", unsafe_allow_html=True)

def deriv(payload, timeout=25):
    ws = None
    try:
        ws = websocket.create_connection(WS, timeout=timeout, enable_multithread=False)
        ws.send(json.dumps(payload))
        end = time.time() + timeout
        while time.time() < end:
            msg = json.loads(ws.recv())
            if msg.get("error"):
                raise RuntimeError(msg["error"].get("message", "Erro Deriv"))
            if msg.get("msg_type"):
                return msg
        raise RuntimeError("Tempo limite da Deriv.")
    except websocket.WebSocketBadStatusException as e:
        raise RuntimeError(f"Deriv recusou a ligação (HTTP {getattr(e, 'status_code', '?')}).") from e
    except (websocket.WebSocketException, OSError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Falha de ligação Deriv: {e}") from e
    finally:
        if ws:
            try: ws.close()
            except Exception: pass

@st.cache_data(ttl=900, show_spinner=False)
def symbols():
    data = deriv({"active_symbols":"brief", "req_id":11}).get("active_symbols")
    if not isinstance(data, list) or not data:
        raise RuntimeError("A Deriv não devolveu instrumentos.")
    return data

def txt(x):
    return re.sub(r"\s+", " ", str(x or "")).strip()

def category(x):
    z = " ".join(txt(x.get(k)) for k in (
        "market_display_name","market","submarket_display_name","submarket","display_name"
    )).lower()
    if "forex" in z or "foreign exchange" in z: return "Forex"
    if any(k in z for k in ("synthetic","derived","continuous")): return "Índices sintéticos"
    if any(k in z for k in ("crypto","cryptocurrency")): return "Cripto"
    if any(k in z for k in ("commodity","metal")): return "Commodities e metais"
    if any(k in z for k in ("stock","indices","index","equities")): return "Índices e acções"
    return "Outros"

def label(x):
    name = txt(x.get("display_name") or x.get("underlying_symbol_name") or x.get("symbol"))
    sym = txt(x.get("underlying_symbol") or x.get("symbol"))
    return f"{name} · {sym}"

def candles(symbol, gran, count=300):
    msg = deriv({
        "ticks_history":symbol, "adjust_start_time":1, "count":count,
        "end":"latest", "start":1, "style":"candles",
        "granularity":gran, "req_id":12
    })
    rows = msg.get("candles")
    if not isinstance(rows, list) or len(rows) < 100:
        raise RuntimeError("Velas insuficientes.")
    d = pd.DataFrame(rows)
    for c in ("open","high","low","close","epoch"):
        if c not in d: raise RuntimeError(f"Resposta OHLC sem campo {c}.")
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=["open","high","low","close","epoch"])
    d = d.sort_values("epoch").drop_duplicates("epoch").reset_index(drop=True)
    valid = (
        (d.high >= d[["open","close","low"]].max(axis=1))
        & (d.low <= d[["open","close","high"]].min(axis=1))
        & (d.high >= d.low)
    )
    d = d.loc[valid].reset_index(drop=True)
    if len(d) < 100: raise RuntimeError("Velas OHLC inválidas ou insuficientes.")
    d = d.iloc[:-1].copy().reset_index(drop=True)
    age = time.time() - float(d.epoch.iloc[-1])
    if age > max(gran * 2.5, 900):
        raise RuntimeError("Dados demasiado antigos; análise cancelada.")
    return d, age

def indicators(d):
    d = d.copy()
    c, h, l = d.close, d.high, d.low
    d["ema20"] = c.ewm(span=20, adjust=False).mean()
    d["ema50"] = c.ewm(span=50, adjust=False).mean()
    delta = c.diff()
    gains = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    losses = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    d["rsi"] = (100 - 100/(1 + gains/losses.replace(0,np.nan))).fillna(50)
    d["macd"] = c.ewm(span=12,adjust=False).mean() - c.ewm(span=26,adjust=False).mean()
    d["macds"] = d.macd.ewm(span=9,adjust=False).mean()
    prev = c.shift(1)
    tr = pd.concat([h-l,(h-prev).abs(),(l-prev).abs()],axis=1).max(axis=1)
    d["atr"] = tr.ewm(alpha=1/14,adjust=False).mean()
    d["fh"], d["fl"] = False, False
    for i in range(2,len(d)-2):
        d.loc[i,"fh"] = h.iloc[i] > max(h.iloc[i-2],h.iloc[i-1],h.iloc[i+1],h.iloc[i+2])
        d.loc[i,"fl"] = l.iloc[i] < min(l.iloc[i-2],l.iloc[i-1],l.iloc[i+1],l.iloc[i+2])
    return d

def nearest_levels(d, entry, side):
    recent = d.iloc[-120:]
    lows = recent.loc[recent.fl,"low"].astype(float)
    highs = recent.loc[recent.fh,"high"].astype(float)
    if side == "BUY":
        targets = sorted(float(v) for v in highs if float(v) > entry)
        obstacle = targets[0] if targets else None
        structure = float(lows.iloc[-1]) if len(lows) else float(recent.low.tail(30).min())
    else:
        targets = sorted((float(v) for v in lows if float(v) < entry), reverse=True)
        obstacle = targets[0] if targets else None
        structure = float(highs.iloc[-1]) if len(highs) else float(recent.high.tail(30).max())
    return structure, obstacle

def plan(d):
    a, b = d.iloc[-1], d.iloc[-2]
    price, atr = float(a.close), float(a.atr)
    if not np.isfinite(atr) or atr <= 0: raise RuntimeError("ATR inválido.")

    buy = sell = 0
    br, sr = [], []
    if a.ema20 > a.ema50 and price > a.ema20:
        buy += 2; br.append("EMA20 acima da EMA50 e preço acima da EMA20")
    if a.ema20 < a.ema50 and price < a.ema20:
        sell += 2; sr.append("EMA20 abaixo da EMA50 e preço abaixo da EMA20")
    if a.macd > a.macds:
        buy += 1; br.append("MACD acima da linha de sinal")
    elif a.macd < a.macds:
        sell += 1; sr.append("MACD abaixo da linha de sinal")
    if 50 < a.rsi < 68:
        buy += 1; br.append(f"RSI {a.rsi:.1f}")
    elif 32 < a.rsi < 50:
        sell += 1; sr.append(f"RSI {a.rsi:.1f}")
    if a.close > a.open and a.close > b.close:
        buy += 1; br.append("Vela fechada compradora")
    elif a.close < a.open and a.close < b.close:
        sell += 1; sr.append("Vela fechada vendedora")

    side = "BUY" if buy >= 3 and buy-sell >= 2 else "SELL" if sell >= 3 and sell-buy >= 2 else "AGUARDAR"
    out = {
        "side":side,"buy":buy,"sell":sell,"price":price,"atr":atr,
        "rsi":float(a.rsi),"ema20":float(a.ema20),"ema50":float(a.ema50),
        "macd":float(a.macd),"macds":float(a.macds),"br":br,"sr":sr,
        "lo":None,"hi":None,"entry":None,"sl":None,"tp":None,"rr":None,
        "state":"Sem operação validada","trigger":"Sem activação.",
        "invalid":"—","obstacle":None
    }
    if side == "AGUARDAR":
        out["trigger"] = "Confirmações BUY/SELL insuficientes ou contraditórias."
        return out

    # Preserva a zona de entrada V17 em torno da EMA20.
    half = max(0.12*atr, abs(price)*0.00002)
    anchor = min(price,float(a.ema20)) if side == "BUY" else max(price,float(a.ema20))
    lo, hi = anchor-half, anchor+half
    entry = (lo+hi)/2
    swing, obstacle = nearest_levels(d,entry,side)

    if side == "BUY":
        # Preserva o SL V17: swing estrutural e margem ATR.
        sl = min(swing-0.25*atr, lo-0.8*atr)
        risk = entry-sl
        if obstacle is None: obstacle = entry+2.0*atr  # fallback ATR apenas sem resistência identificada
        tp = float(obstacle)
        rr = (tp-entry)/risk if risk > 0 else 0
        if price < lo:
            out["state"] = "CENÁRIO EXPIRADO / ZONA ATRAVESSADA"
            out["trigger"] = "Preço já passou abaixo da zona BUY. Não entrar; actualizar análise."
            return out
        zone_state = "ZONA ALCANÇADA — aguardar confirmação" if lo <= price <= hi else "ZONA PENDENTE — aguardar recuo"
        trigger = (
            "Preço dentro da zona. Aguardar vela fechada compradora e confirmar o fundo."
            if lo <= price <= hi else
            f"Esperar recuo à zona {lo:.5f}–{hi:.5f} e fecho de vela novamente comprador."
        )
        valid = sl < lo < hi < tp
        invalid = f"Fecho abaixo de {sl:.5f} ou quebra confirmada do fundo estrutural."
    else:
        # Preserva o SL V17: swing estrutural e margem ATR.
        sl = max(swing+0.25*atr, hi+0.8*atr)
        risk = sl-entry
        if obstacle is None: obstacle = entry-2.0*atr
        tp = float(obstacle)
        rr = (entry-tp)/risk if risk > 0 else 0
        if price > hi:
            out["state"] = "CENÁRIO EXPIRADO / ZONA ULTRAPASSADA"
            out["trigger"] = "Preço já passou acima da zona SELL. Não entrar; actualizar análise."
            return out
        zone_state = "ZONA ALCANÇADA — aguardar confirmação" if lo <= price <= hi else "ZONA PENDENTE — aguardar subida"
        trigger = (
            "Preço dentro da zona. Aguardar vela fechada vendedora e confirmar o topo."
            if lo <= price <= hi else
            f"Esperar subida à zona {lo:.5f}–{hi:.5f} e fecho de vela novamente vendedora."
        )
        valid = tp < lo < hi < sl
        invalid = f"Fecho acima de {sl:.5f} ou quebra confirmada do topo estrutural."

    distance = lo-price if price < lo else price-hi if price > hi else 0.0
    if distance > MAX_ENTRY_DISTANCE_ATR*atr:
        out["state"] = "CENÁRIO EXPIRADO — preço afastado da zona"
        out["trigger"] = "Preço afastou-se demasiado da zona. Cancelar cenário e analisar novamente."
        return out

    # Correcção: não forçar TP para além de suporte/resistência para fabricar RR.
    if not valid or not np.isfinite([entry,sl,tp,rr]).all() or rr < MIN_RR:
        out["side"] = "AGUARDAR"
        out["state"] = "OPERAÇÃO REJEITADA — obstáculo/risco desfavorável"
        out["trigger"] = f"O obstáculo técnico não oferece RR mínimo de 1:{MIN_RR:.1f}. Não forçar o TP."
        out["obstacle"] = obstacle
        return out

    out.update({
        "lo":float(lo),"hi":float(hi),"entry":float(entry),
        "sl":float(sl),"tp":float(tp),"rr":float(rr),
        "state":zone_state,"trigger":trigger,"invalid":invalid,
        "obstacle":float(obstacle)
    })
    return out

def comment_image(img, meta, model):
    key = os.getenv("OPENROUTER_API_KEY","").strip()
    if not key: return "Comentário visual indisponível: falta OPENROUTER_API_KEY."
    im = ImageOps.exif_transpose(img).convert("RGB")
    im.thumbnail((1300,1300))
    buf = BytesIO(); im.save(buf,"JPEG",quality=82)
    prompt = (
        f"Comenta em português, até 4 frases, apenas o que vês no screenshot. "
        f"Plataforma {meta['platform']}, activo Deriv {meta['display']}, timeframe {meta['tf']}. "
        "Não alteres o sinal nem os níveis OHLC. Não inventes dados."
    )
    payload = {
        "model":model,"temperature":0.1,"max_tokens":300,
        "messages":[{"role":"user","content":[
            {"type":"text","text":prompt},
            {"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+base64.b64encode(buf.getvalue()).decode()}}
        ]}]
    }
    try:
        r = requests.post(OR_URL,headers={
            "Authorization":"Bearer "+key,"Content-Type":"application/json",
            "HTTP-Referer":"https://doncullertrade47.onrender.com","X-Title":APP
        },json=payload,timeout=(20,90))
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        return " ".join(x.get("text","") for x in content if isinstance(x,dict)) if isinstance(content,list) else str(content)
    except Exception:
        return "Comentário visual indisponível; os níveis técnicos não foram alterados."

def fmt(x):
    if x is None: return "—"
    try:
        if not np.isfinite(float(x)): return "—"
        return f"{float(x):.8f}".rstrip("0").rstrip(".")
    except (TypeError,ValueError):
        return "—"

st.markdown(
    f'<div class="hero"><div class="small">{VERSION} · SL/TP V17 PRESERVADOS E APERFEIÇOADOS</div>'
    f'<h1>🦁 {APP}</h1><span class="small">Instrumentos listados dinamicamente pela Deriv</span></div>',
    unsafe_allow_html=True
)

try:
    with st.sidebar:
        st.subheader("Configuração")
        if st.button("🔄 Actualizar instrumentos"): symbols.clear()
        rows = symbols()
        groups = {}
        for item in rows: groups.setdefault(category(item),[]).append(item)
        order = ["Índices sintéticos","Forex","Cripto","Commodities e metais","Índices e acções","Outros"]
        cats = [name for name in order if groups.get(name)]
        cat = st.selectbox("Mercado",cats)
        opts = sorted(groups[cat],key=label)
        chosen = st.selectbox("Instrumento",[label(x) for x in opts])
        item = next(x for x in opts if label(x)==chosen)
        platform = st.selectbox("Plataforma do gráfico",["Deriv MT5","MT5 de outro broker","cTrader","TradingView","Outra"])
        tf = st.selectbox("Timeframe",list(TF),index=1)
        model = st.text_input("Modelo OpenRouter",MODEL)
        st.caption("A lista inclui os instrumentos devolvidos pela Deriv; não inventa símbolos indisponíveis.")
except Exception as e:
    st.error(f"Não foi possível obter os instrumentos Deriv: {e}")
    st.stop()

left,right = st.columns([1.05,.95],gap="large")
with left:
    st.subheader("Screenshot")
    upload = st.file_uploader("Carrega o gráfico",type=["png","jpg","jpeg","webp"],key="v18_upload")
    img = None
    if upload:
        try:
            img = Image.open(upload); img.load()
            st.image(img,caption="Imagem recebida",use_container_width=True)
        except (UnidentifiedImageError,OSError):
            st.error("Imagem inválida.")
    st.warning("O activo e timeframe escolhidos devem corresponder exactamente ao screenshot. Activos de outro broker podem ter preços diferentes.")
    run = st.button("🦁 ANALISAR COM DADOS DERIV",use_container_width=True)

with right:
    st.subheader("Resultado V18")
    if run:
        if img is None:
            st.warning("Carrega primeiro o screenshot.")
        else:
            try:
                sym = item.get("underlying_symbol") or item.get("symbol")
                if not sym: raise RuntimeError("Código do instrumento não fornecido pela Deriv.")
                with st.spinner("A obter velas fechadas e a validar entrada, SL e TP..."):
                    d,age = candles(sym,TF[tf])
                    d = indicators(d)
                    p = plan(d)
                    meta = {"platform":platform,"display":chosen,"tf":tf}
                    visual = comment_image(img,meta,model.strip())
                    st.session_state["v18"] = {
                        "p":p,"age":age,"epoch":int(d.epoch.iloc[-1]),
                        "sym":sym,"meta":meta,"visual":visual
                    }
            except Exception as e:
                st.session_state.pop("v18",None)
                st.error(str(e))

    result = st.session_state.get("v18")
    if result:
        p = result["p"]
        cls = {"BUY":"buy","SELL":"sell","AGUARDAR":"wait"}[p["side"]]
        st.markdown(
            f'<div class="box"><div class="{cls}">{p["side"]}</div>'
            f'<b>{result["meta"]["display"]} · {result["meta"]["tf"]}</b><br>'
            f'<span class="small">Deriv OHLC · {result["sym"]}</span></div>',
            unsafe_allow_html=True
        )
        st.caption(f"Força técnica: BUY {p['buy']} · SELL {p['sell']} — não é probabilidade de vitória.")
        st.write(f"**Último fecho confirmado:** {fmt(p['price'])}")
        st.write(f"**RSI:** {p['rsi']:.1f} | **EMA20:** {fmt(p['ema20'])} | **EMA50:** {fmt(p['ema50'])}")
        st.write(f"**MACD:** {fmt(p['macd'])} | **Sinal:** {fmt(p['macds'])} | **ATR:** {fmt(p['atr'])}")
        st.write("**Evidências BUY:** "+("; ".join(p["br"]) or "Sem confirmação."))
        st.write("**Evidências SELL:** "+("; ".join(p["sr"]) or "Sem confirmação."))
        st.write(f"**Estado:** {p['state']}")
        if p["entry"] is not None:
            st.success(f"**Zona de entrada:** {fmt(p['lo'])} – {fmt(p['hi'])}\n\n**Entrada de referência:** {fmt(p['entry'])}")
            st.write(f"**Stop Loss estrutural:** {fmt(p['sl'])}")
            st.write(f"**Take Profit técnico:** {fmt(p['tp'])}")
            st.write(f"**Risco/retorno calculado:** 1:{p['rr']:.2f}")
            st.write("**Activação:** "+p["trigger"])
            st.write("**Invalidação:** "+p["invalid"])
            st.warning("Zona pendente, não é ordem imediata. Confirma o preço actual antes de entrar; se a zona ficar para trás, cancela e analisa novamente.")
        else:
            st.info(p["trigger"])
        st.markdown("**Comentário visual**")
        st.write(result["visual"])
        st.caption(
            f"Última vela fechada: {datetime.fromtimestamp(result['epoch'],timezone.utc):%Y-%m-%d %H:%M UTC} "
            f"· idade {int(result['age'])} s."
        )
    else:
        st.caption("O relatório aparecerá aqui após a análise.")

st.divider()
st.markdown(
    '<div class="small">V18 não guarda histórico e não executa operações. Preserva a base de SL/TP da V17 '
    '(swings, ATR e RR mínimo de 1:1,5), mas deixa de forçar o Take Profit para além de um obstáculo técnico '
    'identificado. Se o espaço até ao obstáculo for insuficiente, rejeita a operação. A lista depende dos '
    'instrumentos disponibilizados pela Deriv nesta API. Testar primeiro em Demo; nenhum método garante resultados.</div>',
    unsafe_allow_html=True
)
