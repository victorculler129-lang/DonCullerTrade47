import os, json, time, re, base64
from io import BytesIO
from datetime import datetime, timezone
import requests, numpy as np, pandas as pd, streamlit as st, websocket
from PIL import Image, ImageOps, UnidentifiedImageError

APP="DONCULLER-TRADE47"; VERSION="V17.0"
WS=os.getenv("DERIV_WS_URL","wss://api.derivws.com/trading/v1/options/ws/public")
OR_URL="https://openrouter.ai/api/v1/chat/completions"
MODEL=os.getenv("OPENROUTER_MODEL","nvidia/nemotron-3.5-super-vl:free").strip()
TF={"M1":60,"M5":300,"M15":900,"M30":1800,"H1":3600,"H4":14400,"D1":86400}
MIN_RR=1.5

st.set_page_config(page_title=APP,page_icon="🦁",layout="wide")
st.markdown("""<style>
.stApp{background:#071321;color:#edf4fb} section[data-testid="stSidebar"]{background:#0b1b2d}
.hero,.box{background:#0d2033;border:1px solid #24445e;border-radius:14px;padding:18px}
.buy{color:#25d887;font-size:30px;font-weight:800}.sell{color:#ff6874;font-size:30px;font-weight:800}
.wait{color:#ffc857;font-size:30px;font-weight:800}.small{color:#9fb3c8;font-size:13px}
div.stButton>button{background:#16865f;color:white;font-weight:700;min-height:46px}
</style>""",unsafe_allow_html=True)

def deriv(payload,timeout=20):
    ws=None
    try:
        ws=websocket.create_connection(WS,timeout=timeout,enable_multithread=False)
        ws.send(json.dumps(payload)); end=time.time()+timeout
        while time.time()<end:
            msg=json.loads(ws.recv())
            if msg.get("error"): raise RuntimeError(msg["error"].get("message","Erro Deriv"))
            if msg.get("msg_type"): return msg
        raise RuntimeError("Tempo limite da Deriv.")
    except websocket.WebSocketBadStatusException as e:
        raise RuntimeError(f"Deriv recusou a ligação (HTTP {getattr(e,'status_code','?')}).") from e
    except (websocket.WebSocketException,OSError) as e:
        raise RuntimeError(f"Falha de ligação Deriv: {e}") from e
    finally:
        if ws:
            try: ws.close()
            except Exception: pass

@st.cache_data(ttl=900,show_spinner=False)
def symbols():
    x=deriv({"active_symbols":"brief","req_id":11}).get("active_symbols")
    if not isinstance(x,list) or not x: raise RuntimeError("A Deriv não devolveu instrumentos.")
    return x

def txt(x): return re.sub(r"\\s+"," ",str(x or "")).strip()
def category(x):
    z=" ".join(txt(x.get(k)) for k in ("market_display_name","market","submarket_display_name","submarket","display_name")).lower()
    if "forex" in z: return "Forex"
    if any(k in z for k in ("synthetic","derived","continuous")): return "Índices sintéticos"
    if any(k in z for k in ("crypto","cryptocurrency")): return "Cripto"
    if any(k in z for k in ("commodity","metal")): return "Commodities e metais"
    if any(k in z for k in ("stock","indices","index","equities")): return "Índices e acções"
    return "Outros"
def label(x):
    return f"{txt(x.get('display_name') or x.get('underlying_symbol_name') or x.get('symbol'))} · {txt(x.get('underlying_symbol') or x.get('symbol'))}"

def candles(symbol,gran,count=300):
    msg=deriv({"ticks_history":symbol,"adjust_start_time":1,"count":count,"end":"latest","start":1,"style":"candles","granularity":gran,"req_id":12})
    rows=msg.get("candles")
    if not isinstance(rows,list) or len(rows)<100: raise RuntimeError("Velas insuficientes.")
    d=pd.DataFrame(rows)
    for c in ("open","high","low","close","epoch"): d[c]=pd.to_numeric(d[c],errors="coerce")
    d=d.dropna().sort_values("epoch").drop_duplicates("epoch").reset_index(drop=True)
    ok=(d.high>=d[["open","close","low"]].max(axis=1))&(d.low<=d[["open","close","high"]].min(axis=1))&(d.high>=d.low)
    d=d[ok].reset_index(drop=True)
    if len(d)<100: raise RuntimeError("Velas OHLC inválidas.")
    d=d.iloc[:-1].copy().reset_index(drop=True) # última vela pode estar aberta
    age=time.time()-float(d.epoch.iloc[-1])
    if age>max(gran*2.5,900): raise RuntimeError("Dados demasiado antigos; análise cancelada.")
    return d,age

def indicators(d):
    d=d.copy(); c,h,l=d.close,d.high,d.low
    d["ema20"]=c.ewm(span=20,adjust=False).mean(); d["ema50"]=c.ewm(span=50,adjust=False).mean()
    delta=c.diff(); g=delta.clip(lower=0).ewm(alpha=1/14,adjust=False).mean()
    loss=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
    d["rsi"]=(100-100/(1+g/loss.replace(0,np.nan))).fillna(50)
    d["macd"]=c.ewm(span=12,adjust=False).mean()-c.ewm(span=26,adjust=False).mean()
    d["macds"]=d.macd.ewm(span=9,adjust=False).mean()
    prev=c.shift(1); tr=pd.concat([h-l,(h-prev).abs(),(l-prev).abs()],axis=1).max(axis=1)
    d["atr"]=tr.ewm(alpha=1/14,adjust=False).mean()
    d["fh"]=False; d["fl"]=False
    for i in range(2,len(d)-2):
        d.loc[i,"fh"]=h.iloc[i]>max(h.iloc[i-2],h.iloc[i-1],h.iloc[i+1],h.iloc[i+2])
        d.loc[i,"fl"]=l.iloc[i]<min(l.iloc[i-2],l.iloc[i-1],l.iloc[i+1],l.iloc[i+2])
    return d

def plan(d):
    a,b=d.iloc[-1],d.iloc[-2]; p=float(a.close); atr=float(a.atr)
    if not np.isfinite(atr) or atr<=0: raise RuntimeError("ATR inválido.")
    buy=sell=0; br=[]; sr=[]
    if a.ema20>a.ema50 and p>a.ema20: buy+=2; br.append("EMA20/50 alinhadas para alta")
    if a.ema20<a.ema50 and p<a.ema20: sell+=2; sr.append("EMA20/50 alinhadas para baixa")
    if a.macd>a.macds: buy+=1; br.append("MACD positivo")
    elif a.macd<a.macds: sell+=1; sr.append("MACD negativo")
    if 50<a.rsi<68: buy+=1; br.append(f"RSI {a.rsi:.1f}")
    elif 32<a.rsi<50: sell+=1; sr.append(f"RSI {a.rsi:.1f}")
    if a.close>a.open and a.close>b.close: buy+=1; br.append("vela fechada compradora")
    elif a.close<a.open and a.close<b.close: sell+=1; sr.append("vela fechada vendedora")
    side="BUY" if buy>=3 and buy-sell>=2 else "SELL" if sell>=3 and sell-buy>=2 else "AGUARDAR"
    out=dict(side=side,buy=buy,sell=sell,price=p,atr=atr,rsi=float(a.rsi),ema20=float(a.ema20),ema50=float(a.ema50),
             macd=float(a.macd),macds=float(a.macds),br=br,sr=sr,lo=None,hi=None,entry=None,sl=None,tp=None,rr=None,
             state="Sem operação validada",trigger="—",invalid="—")
    if side=="AGUARDAR": return out
    recent=d.iloc[-100:]; lows=recent.loc[recent.fl,"low"].tail(8); highs=recent.loc[recent.fh,"high"].tail(8)
    swinglo=float(lows.min()) if len(lows) else float(recent.low.tail(20).min())
    swinghi=float(highs.max()) if len(highs) else float(recent.high.tail(20).max())
    half=max(.12*atr,abs(p)*.00002)
    if side=="BUY":
        anchor=min(p,float(a.ema20)); lo,hi=anchor-half,anchor+half
        sl=min(swinglo-.25*atr,lo-.8*atr); risk=hi-sl
        tp=max(swinghi if swinghi>hi else hi+2*atr,hi+MIN_RR*risk)
        entry=(lo+hi)/2; rr=(tp-entry)/(entry-sl)
        trigger=f"Esperar recuo à zona {lo:.5f}–{hi:.5f} e fecho de vela novamente comprador."
        invalid=f"Fecho abaixo de {sl:.5f} ou quebra do fundo estrutural."
        valid=sl<lo<hi<tp
    else:
        anchor=max(p,float(a.ema20)); lo,hi=anchor-half,anchor+half
        sl=max(swinghi+.25*atr,hi+.8*atr); risk=sl-lo
        tp=min(swinglo if swinglo<lo else lo-2*atr,lo-MIN_RR*risk)
        entry=(lo+hi)/2; rr=(entry-tp)/(sl-entry)
        trigger=f"Esperar subida à zona {lo:.5f}–{hi:.5f} e fecho de vela novamente vendedora."
        invalid=f"Fecho acima de {sl:.5f} ou quebra do topo estrutural."
        valid=tp<lo<hi<sl
    # Não perseguir uma entrada que já ficou demasiado distante.
    if min(abs(p-lo),abs(p-hi))>1.25*atr:
        out["state"]="CENÁRIO EXPIRADO — não entrar; actualizar análise"
        out["trigger"]="Preço afastado da zona planeada. Esperar nova configuração."
        return out
    if not valid or not np.isfinite([entry,sl,tp,rr]).all() or rr<MIN_RR:
        out["side"]="AGUARDAR"; out["state"]="Níveis rejeitados pela validação de risco"
        return out
    out.update(lo=lo,hi=hi,entry=entry,sl=sl,tp=tp,rr=rr,state="ZONA PENDENTE — aguardar activação",trigger=trigger,invalid=invalid)
    return out

def comment_image(img,meta,p,model):
    key=os.getenv("OPENROUTER_API_KEY","").strip()
    if not key: return "Comentário visual indisponível: falta OPENROUTER_API_KEY."
    im=ImageOps.exif_transpose(img).convert("RGB"); im.thumbnail((1300,1300))
    b=BytesIO(); im.save(b,"JPEG",quality=82)
    prompt=(f"Comenta em português, até 4 frases, apenas o que vês no screenshot. Plataforma {meta['platform']}, activo Deriv {meta['display']}, timeframe {meta['tf']}. "
            f"Não alteres o sinal nem os níveis calculados a partir de OHLC. Não inventes dados.")
    payload={"model":model,"temperature":.1,"max_tokens":300,"messages":[{"role":"user","content":[{"type":"text","text":prompt},{"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+base64.b64encode(b.getvalue()).decode()}}]}]}
    try:
        r=requests.post(OR_URL,headers={"Authorization":"Bearer "+key,"Content-Type":"application/json","HTTP-Referer":"https://doncullertrade47.onrender.com","X-Title":APP},json=payload,timeout=(20,90))
        r.raise_for_status(); c=r.json()["choices"][0]["message"]["content"]
        return " ".join(x.get("text","") for x in c if isinstance(x,dict)) if isinstance(c,list) else str(c)
    except Exception: return "Comentário visual indisponível; os níveis técnicos não foram alterados."

def f(x): return "—" if x is None else f"{x:.5f}".rstrip("0").rstrip(".")

st.markdown(f'<div class="hero"><div class="small">{VERSION} · GESTÃO DE ENTRADA, SL E TP</div><h1>🦁 {APP}</h1><span class="small">Instrumentos listados dinamicamente pela Deriv</span></div>',unsafe_allow_html=True)
try:
    with st.sidebar:
        st.subheader("Configuração")
        if st.button("🔄 Actualizar instrumentos"): symbols.clear()
        rows=symbols(); groups={}
        for x in rows: groups.setdefault(category(x),[]).append(x)
        order=["Índices sintéticos","Forex","Cripto","Commodities e metais","Índices e acções","Outros"]
        cats=[x for x in order if groups.get(x)]
        cat=st.selectbox("Mercado",cats)
        opts=sorted(groups[cat],key=label)
        chosen=st.selectbox("Instrumento",[label(x) for x in opts])
        item=next(x for x in opts if label(x)==chosen)
        platform=st.selectbox("Plataforma do gráfico",["Deriv MT5","MT5 de outro broker","cTrader","TradingView","Outra"])
        tf=st.selectbox("Timeframe",list(TF),index=1)
        model=st.text_input("Modelo OpenRouter",MODEL)
        st.caption("A lista inclui todos os instrumentos devolvidos pela Deriv; não inventa pares ou símbolos indisponíveis.")
except Exception as e:
    st.error(f"Não foi possível obter os instrumentos Deriv: {e}"); st.stop()

left,right=st.columns([1.05,.95],gap="large")
with left:
    st.subheader("Screenshot")
    upload=st.file_uploader("Carrega o gráfico",type=["png","jpg","jpeg","webp"],key="v17_upload")
    img=None
    if upload:
        try:
            img=Image.open(upload); img.load(); st.image(img,caption="Imagem recebida",use_container_width=True)
        except (UnidentifiedImageError,OSError): st.error("Imagem inválida.")
    st.warning("O activo e timeframe escolhidos têm de corresponder exactamente ao screenshot. Activos de outro broker podem ter preços diferentes.")
    run=st.button("🦁 ANALISAR COM DADOS DERIV",use_container_width=True)
with right:
    st.subheader("Resultado V17")
    if run:
        if img is None: st.warning("Carrega primeiro o screenshot.")
        else:
            try:
                sym=item.get("underlying_symbol") or item.get("symbol")
                with st.spinner("A obter velas fechadas e a validar os níveis..."):
                    d,age=candles(sym,TF[tf]); d=indicators(d); p=plan(d)
                    meta={"platform":platform,"display":chosen,"tf":tf}
                    visual=comment_image(img,meta,p,model.strip())
                    st.session_state["v17"]={"p":p,"age":age,"epoch":int(d.epoch.iloc[-1]),"sym":sym,"meta":meta,"visual":visual}
            except Exception as e:
                st.session_state.pop("v17",None); st.error(str(e))
    result=st.session_state.get("v17")
    if result:
        p=result["p"]; cls={"BUY":"buy","SELL":"sell","AGUARDAR":"wait"}[p["side"]]
        st.markdown(f'<div class="box"><div class="{cls}">{p["side"]}</div><b>{result["meta"]["display"]} · {tf}</b><br><span class="small">Deriv OHLC · {result["sym"]}</span></div>',unsafe_allow_html=True)
        st.caption(f"Força técnica: BUY {p['buy']} · SELL {p['sell']} — não é probabilidade de vitória.")
        st.write(f"**Último fecho confirmado:** {f(p['price'])}")
        st.write(f"**RSI:** {p['rsi']:.1f} | **EMA20:** {f(p['ema20'])} | **EMA50:** {f(p['ema50'])}")
        st.write(f"**MACD:** {f(p['macd'])} | **Sinal:** {f(p['macds'])} | **ATR:** {f(p['atr'])}")
        st.write("**Evidências BUY:** "+("; ".join(p["br"]) or "Sem confirmação."))
        st.write("**Evidências SELL:** "+("; ".join(p["sr"]) or "Sem confirmação."))
        st.write(f"**Estado:** {p['state']}")
        if p["entry"] is not None:
            st.success(f"**Zona de entrada:** {f(p['lo'])} – {f(p['hi'])}\n\n**Entrada de referência:** {f(p['entry'])}")
            st.write(f"**Stop Loss estrutural:** {f(p['sl'])}")
            st.write(f"**Take Profit técnico:** {f(p['tp'])}")
            st.write(f"**Risco/retorno calculado:** 1:{p['rr']:.2f}")
            st.write("**Activação:** "+p["trigger"]); st.write("**Invalidação:** "+p["invalid"])
            st.warning("Zona pendente, não é ordem imediata. Revalida o preço antes de entrar; se a zona ficar para trás, cancela e analisa novamente.")
        else: st.info(p["trigger"] if p["state"].startswith("CENÁRIO EXPIRADO") else "Sem níveis operacionais válidos. Não entrar.")
        st.markdown("**Comentário visual**"); st.write(result["visual"])
        st.caption(f"Última vela fechada: {datetime.fromtimestamp(result['epoch'],timezone.utc):%Y-%m-%d %H:%M UTC} · idade {int(result['age'])} s.")
    else: st.caption("O relatório aparecerá aqui após a análise.")
st.divider()
st.markdown('<div class="small">V17 não guarda histórico. A lista é dinâmica, mas limitada aos instrumentos que a Deriv disponibiliza nesta API. O SL considera estrutura e ATR; o TP respeita um RR mínimo planeado, mas nenhum método garante que o mercado o alcance. Testar primeiro em Demo.</div>',unsafe_allow_html=True)
