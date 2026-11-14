import os, io, re, json, base64
from datetime import datetime, timezone
import requests
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image, ImageOps

APP = "DONCULLER-TRADE47"
API = "https://openrouter.ai/api/v1/chat/completions"
KEY = os.getenv("OPENROUTER_API_KEY", "")
DEFAULT_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemma-4-26b-a4b-it:free")
FALLBACK_MODELS = [
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "nvidia/nemotron-nano-12b-v2-vl:free",
    "openrouter/free",
]

st.set_page_config(page_title=APP, page_icon="📊", layout="wide")
st.markdown("""
<style>
.stApp{background:#071426;color:#edf3fb}
.block-container{max-width:1180px;padding-top:1.5rem}
h1,h2,h3{color:#f3f7ff}
div[data-testid="stMetric"]{background:#10243d;border:1px solid #294866;padding:12px;border-radius:12px}
</style>""", unsafe_allow_html=True)
st.title("📊 DONCULLER-TRADE47")
st.caption("AI Trading Chart Analyzer · Leitura técnica estruturada")

def prep_image(file):
    file.seek(0)
    im=ImageOps.exif_transpose(Image.open(file)).convert("RGB")
    im.thumbnail((1800,1800))
    b=io.BytesIO()
    im.save(b,format="JPEG",quality=88,optimize=True)
    return "data:image/jpeg;base64,"+base64.b64encode(b.getvalue()).decode()

def read_ohlc(file):
    df=pd.read_csv(file)
    aliases={
        "open":["open","o","abertura"],
        "high":["high","h","max","máxima","maxima"],
        "low":["low","l","min","mínima","minima"],
        "close":["close","c","fecho","fechamento"]
    }
    cols={str(c).strip().lower():c for c in df.columns}
    ren={}
    for target,names in aliases.items():
        for n in names:
            if n in cols:
                ren[cols[n]]=target
                break
    df=df.rename(columns=ren)
    if not all(x in df.columns for x in ["open","high","low","close"]):
        raise ValueError("CSV precisa de Open, High, Low e Close.")
    for x in ["open","high","low","close"]:
        df[x]=pd.to_numeric(df[x],errors="coerce")
    df=df.dropna(subset=["open","high","low","close"]).tail(500).reset_index(drop=True)
    if len(df)<35:
        raise ValueError("Envia pelo menos 35 velas válidas; idealmente 200.")
    if (df.high<df.low).any():
        raise ValueError("Há velas inválidas: High inferior a Low.")
    return df

def indicators(df):
    c=df.close
    e20=c.ewm(span=20,adjust=False).mean()
    e50=c.ewm(span=50,adjust=False).mean()
    e12=c.ewm(span=12,adjust=False).mean()
    e26=c.ewm(span=26,adjust=False).mean()
    macd=e12-e26
    sig=macd.ewm(span=9,adjust=False).mean()
    d=c.diff()
    gain=d.clip(lower=0).ewm(alpha=1/14,adjust=False).mean()
    loss=(-d.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
    rs=gain/loss.replace(0,np.nan)
    rsi=100-100/(1+rs)
    tr=pd.concat([
        df.high-df.low,
        (df.high-c.shift()).abs(),
        (df.low-c.shift()).abs()
    ],axis=1).max(axis=1)
    atr=tr.rolling(14).mean()
    fh=[]
    fl=[]
    for i in range(max(2,len(df)-80),len(df)-2):
        if df.high[i]>max(df.high[i-2:i].tolist()+df.high[i+1:i+3].tolist()):
            fh.append(float(df.high[i]))
        if df.low[i]<min(df.low[i-2:i].tolist()+df.low[i+1:i+3].tolist()):
            fl.append(float(df.low[i]))
    last=float(c.iloc[-1])
    hist=float((macd-sig).iloc[-1])
    return {
        "candles":len(df),
        "last_close":last,
        "ema20":float(e20.iloc[-1]),
        "ema50":float(e50.iloc[-1]),
        "rsi14":None if pd.isna(rsi.iloc[-1]) else round(float(rsi.iloc[-1]),2),
        "macd":round(float(macd.iloc[-1]),6),
        "macd_signal":round(float(sig.iloc[-1]),6),
        "macd_histogram":round(hist,6),
        "atr14":None if pd.isna(atr.iloc[-1]) else float(atr.iloc[-1]),
        "confirmed_fractal_high":fh[-5:],
        "confirmed_fractal_low":fl[-5:],
        "ema_alignment":"bullish" if last>e20.iloc[-1]>e50.iloc[-1] else "bearish" if last<e20.iloc[-1]<e50.iloc[-1] else "mixed",
        "macd_state":"bullish" if hist>0 else "bearish" if hist<0 else "neutral"
    }

def prompt(asset,tf,platform,style,metrics):
    return f"""
És o analista técnico do {APP}. Faz uma análise rigorosa do screenshot e dos dados OHLC abaixo.
Responde em português simples, direto e operacional.
ATIVO={asset}; TIMEFRAME={tf}; PLATAFORMA={platform}; ESTILO={style}
OHLC/INDICADORES CALCULADOS={json.dumps(metrics,ensure_ascii=False)}

Avalia tendência, estrutura HH/HL/LH/LL, impulso/correção, suporte/resistência,
liquidez, falsas rupturas, velas, EMA, RSI, MACD, fractais e swings tipo ZigZag.
Compara cenário BUY e SELL antes da decisão. Não digas que viste um indicador que não aparece.
Se houver dados OHLC, usa os valores numéricos. Se só houver screenshot, nunca inventes preços:
se a escala não for legível, declara que o preço não pode ser identificado com precisão.
Escolhe BUY ou SELL se existir configuração confirmada; AGUARDAR só quando faltar confirmação
ou os dados forem insuficientes. Não forces sinal.
Define entrada como zona + gatilho de ativação; SL por invalidação estrutural; TP1/TP2 em níveis
plausíveis. Se não for possível calcular, declara isso. Não inventes probabilidades nem prometas 75%.
A qualidade (Baixa/Média/Alta) é qualidade da evidência, não chance de vitória.
Fractais só são confirmados com duas velas à direita. Não declares ZigZag confirmado sem parâmetros.
Devolve APENAS JSON válido com estas chaves:
{{
"decision":"BUY|SELL|AGUARDAR","reason":"motivo curto","trend":"estrutura/tendência",
"buy_case":"cenário comprador","sell_case":"cenário vendedor",
"entry_zone":"zona ou não identificável","activation":"gatilho exato",
"stop_loss":"nível/regra","take_profit_1":"alvo 1","take_profit_2":"alvo 2",
"risk_reward":"relação ou não calculável","invalidation":"condição que invalida",
"confirmations":["..."],"conflicts":["..."],"confidence_quality":"Baixa|Média|Alta",
"missing_data":["..."],"next_action":"próxima ação curta"
}}
"""

def parse_json(s):
    s=(s or "").strip()
    s=re.sub(r"^```(?:json)?\s*|\s*```$","",s,flags=re.I)
    try:
        return json.loads(s)
    except Exception:
        m=re.search(r"\{.*\}",s,re.S)
        if m:
            return json.loads(m.group())
        raise ValueError("O modelo não devolveu JSON válido. Tenta novamente ou muda de modelo.")

def analyze(model,pr,image):
    if not KEY:
        raise RuntimeError("OPENROUTER_API_KEY não está configurada no Render.")
    model=(model or DEFAULT_MODEL).strip()
    chain=[model]+[m for m in FALLBACK_MODELS if m != model]
    payload={
        "model":model,
        "models":chain,
        "temperature":0.15,
        "max_tokens":2200,
        "stream":False,
        "messages":[
            {
                "role":"system",
                "content":"Responde apenas com JSON válido. Nunca inventes preços."
            },
            {
                "role":"user",
                "content":[
                    {"type":"text","text":pr},
                    {"type":"image_url","image_url":{"url":image}}
                ]
            }
        ]
    }
    headers={
        "Authorization":"Bearer "+KEY,
        "Content-Type":"application/json",
        "HTTP-Referer":"https://doncullertrade47.onrender.com",
        "X-Title":APP
    }
    res=requests.post(API,headers=headers,json=payload,timeout=150)
    if res.status_code!=200:
        detail=res.text[:1200]
        if res.status_code==429:
            raise RuntimeError(
                "Os modelos disponíveis recusaram o pedido por limite 429. "
                "Aguarda e tenta mais tarde. Detalhe: "+detail
            )
        raise RuntimeError(f"OpenRouter HTTP {res.status_code}: {detail}")
    body=res.json()
    choices=body.get("choices") or []
    if not choices:
        raise RuntimeError("A API não devolveu uma resposta utilizável.")
    msg=choices[0].get("message") or {}
    content=msg.get("content")
    if isinstance(content,list):
        content="".join(x.get("text","") for x in content if isinstance(x,dict))
    if not content:
        raise RuntimeError("Resposta vazia do modelo. Confirma se o modelo aceita imagens ou escolhe outro.")
    result=parse_json(content)
    if result.get("decision") not in ["BUY","SELL","AGUARDAR"]:
        raise ValueError("Decisão inválida recebida.")
    for k in [
        "reason","trend","entry_zone","activation","stop_loss",
        "take_profit_1","take_profit_2","invalidation","confidence_quality"
    ]:
        if k not in result:
            raise ValueError("Relatório incompleto: falta "+k)
    return result

with st.sidebar:
    st.header("Configuração")
    asset=st.selectbox("Ativo",[
        "Boom 1000","Crash 1000","Boom 500","Crash 500",
        "Boom 300","Crash 300","Boom 100","Crash 100",
        "Boom 50","Crash 50","Jump Index 50","Jump Index",
        "Step Index","EUR/USD","GBP/USD","XAU/USD","Outro"
    ])
    if asset=="Outro":
        asset=st.text_input("Nome do ativo","")
    tf=st.selectbox("Timeframe",["M1","M5","M15","M30","H1","H4","D1"])
    platform=st.selectbox("Plataforma",[
        "Deriv MT5","TradingView","Deriv cTrader","Outra"
    ])
    style=st.selectbox("Estilo",["Scalping","Intraday","Swing"])
    model=st.text_input("Modelo OpenRouter",DEFAULT_MODEL)
    st.caption("A chave secreta permanece no Render: OPENROUTER_API_KEY.")

col1,col2=st.columns([1,1])
with col1:
    st.subheader("Screenshot do gráfico")
    shot=st.file_uploader(
        "PNG, JPG ou WEBP",
        type=["png","jpg","jpeg","webp"]
    )
    if shot:
        st.image(shot,use_container_width=True)

with col2:
    st.subheader("Dados OHLC (opcional, recomendado)")
    csv=st.file_uploader(
        "CSV com Open, High, Low e Close",
        type=["csv"]
    )
    st.caption("O screenshot permite leitura visual. O CSV permite calcular indicadores com preços reais.")

metrics={}
if csv:
    try:
        df=read_ohlc(csv)
        metrics=indicators(df)
        st.success(f"CSV válido: {len(df)} velas.")
        with st.expander("Ver indicadores calculados"):
            st.json(metrics)
    except Exception as e:
        st.error("Erro no CSV: "+str(e))
        metrics={}

if st.button("🔎 ANALISAR GRÁFICO",type="primary",use_container_width=True):
    if not shot:
        st.error("Carrega o screenshot primeiro.")
    else:
        try:
            with st.spinner("A comparar BUY e SELL e a analisar a estrutura..."):
                report=analyze(
                    model.strip(),
                    prompt(asset,tf,platform,style,metrics),
                    prep_image(shot)
                )
                st.session_state.report=report
                st.session_state.meta=(
                    f"{asset} · {tf} · {model} · "
                    f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}"
                )
        except Exception as e:
            st.error("Falha na análise: "+str(e))

if "report" in st.session_state:
    r=st.session_state.report
    st.divider()
    st.subheader("Resultado")
    st.caption(st.session_state.get("meta",""))
    d=r["decision"]
    if d=="BUY":
        st.success("🟢 BUY")
    elif d=="SELL":
        st.error("🔴 SELL")
    else:
        st.warning("🟡 AGUARDAR")

    st.markdown("### Porquê")
    st.write(r["reason"])
    st.markdown("### Leitura do mercado")
    st.write(r["trend"])

    a,b=st.columns(2)
    with a:
        st.markdown("**Cenário BUY**")
        st.write(r.get("buy_case","—"))
    with b:
        st.markdown("**Cenário SELL**")
        st.write(r.get("sell_case","—"))

    st.markdown("### Plano operacional")
    x,y,z=st.columns(3)
    x.metric("Zona de entrada",str(r["entry_zone"]))
    y.metric("Stop Loss",str(r["stop_loss"]))
    z.metric("Qualidade",str(r["confidence_quality"]))

    x,y,z=st.columns(3)
    x.metric("Take Profit 1",str(r["take_profit_1"]))
    y.metric("Take Profit 2",str(r["take_profit_2"]))
    z.metric("Risco/Retorno",str(r.get("risk_reward","Não calculável")))

    st.markdown("**Ativação:** "+str(r["activation"]))
    st.markdown("**Invalidação:** "+str(r["invalidation"]))

    st.markdown("### Confirmações")
    for v in r.get("confirmations",[]):
        st.write("✓ "+str(v))

    if r.get("conflicts"):
        st.markdown("### Contradições/riscos")
        for v in r["conflicts"]:
            st.write("• "+str(v))

    if r.get("missing_data"):
        st.markdown("### Dados em falta")
        for v in r["missing_data"]:
            st.write("• "+str(v))

    st.info("Próxima ação: "+str(r.get("next_action","—")))

    with st.expander("Relatório JSON completo"):
        st.json(r)

st.divider()
st.caption(
    "Ferramenta de apoio, não executa ordens nem recebe cotações em tempo real. "
    "A meta de 75% só pode ser avaliada com histórico de sinais e testes Demo; "
    "não é garantia. Um screenshot isolado não garante precisão de preço."
)
