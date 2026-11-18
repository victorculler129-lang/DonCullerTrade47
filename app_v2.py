import os, re, json, base64, time
from io import BytesIO
from datetime import datetime, timezone

import requests
import numpy as np
import pandas as pd
import streamlit as st
import websocket
from PIL import Image, ImageOps, UnidentifiedImageError

APP = 'DONCULLER-TRADE47'
VERSION = 'V16.0'
OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'
DERIV_WS = os.getenv('DERIV_WS_URL', 'wss://ws.derivws.com/websockets/v3?app_id=1089')
MODEL_DEFAULT = os.getenv('OPENROUTER_MODEL', 'nvidia/nemotron-3.5-super-vl:free').strip()
GRANULARITY = {'M1':60,'M2':120,'M3':180,'M5':300,'M10':600,'M15':900,'M30':1800,'H1':3600,'H2':7200,'H4':14400,'D1':86400}

# Remove a base SQLite legada da V15, caso ainda exista no disco local do serviço.
_old_db = os.path.join(os.getcwd(), 'donculler_history.db')
try:
    if os.path.isfile(_old_db):
        os.remove(_old_db)
except OSError:
    pass

st.set_page_config(page_title=APP, page_icon='🦁', layout='wide')
st.markdown('''<style>
.stApp{background:#071321;color:#edf4fb} section[data-testid="stSidebar"]{background:#0b1b2d}
.hero,.box{background:#0d2033;border:1px solid #24445e;border-radius:14px;padding:18px}
.buy{color:#25d887;font-size:30px;font-weight:800}.sell{color:#ff6874;font-size:30px;font-weight:800}.wait{color:#ffc857;font-size:30px;font-weight:800}
.small{color:#9fb3c8;font-size:13px} div.stButton>button{background:#16865f;color:white;font-weight:700;min-height:46px}
</style>''', unsafe_allow_html=True)

MARKETS = {
 'Índices sintéticos': ['Volatility 10 Index','Volatility 10 (1s) Index','Volatility 25 Index','Volatility 25 (1s) Index','Volatility 50 Index','Volatility 50 (1s) Index','Volatility 75 Index','Volatility 75 (1s) Index','Volatility 100 Index','Volatility 100 (1s) Index','Volatility 150 (1s) Index','Volatility 250 (1s) Index','Boom 300 Index','Boom 500 Index','Boom 600 Index','Boom 900 Index','Boom 1000 Index','Crash 300 Index','Crash 500 Index','Crash 600 Index','Crash 900 Index','Crash 1000 Index','Jump 10 Index','Jump 25 Index','Jump 50 Index','Jump 75 Index','Jump 100 Index','Step Index','Multi Step Index','Range Break 100 Index','Range Break 200 Index','Drift Switch Index'],
 'Forex / metais': ['EUR/USD','GBP/USD','USD/JPY','USD/CHF','AUD/USD','NZD/USD','USD/CAD','EUR/GBP','EUR/JPY','GBP/JPY','XAU/USD','XAG/USD'],
 'Cripto': ['BTC/USD','ETH/USD']}
PLATFORMS=['MetaTrader 5 (MT5)','cTrader','TradingView','Outra plataforma']
TIMEFRAMES=list(GRANULARITY)


def deriv_request(payload, timeout=18):
    ws = websocket.create_connection(DERIV_WS, timeout=timeout, enable_multithread=False)
    try:
        ws.send(json.dumps(payload))
        deadline=time.time()+timeout
        while time.time()<deadline:
            raw=ws.recv()
            if not raw: continue
            msg=json.loads(raw)
            if msg.get('error'):
                raise RuntimeError(msg['error'].get('message','Erro na API Deriv'))
            if msg.get('msg_type'):
                return msg
        raise RuntimeError('Tempo esgotado ao consultar a Deriv.')
    finally:
        ws.close()

@st.cache_data(ttl=3600, show_spinner=False)
def get_deriv_symbols():
    response=deriv_request({'active_symbols':'brief','product_type':'basic'})
    symbols=response.get('active_symbols')
    if not isinstance(symbols,list) or not symbols: raise RuntimeError('A Deriv não devolveu a lista de símbolos.')
    return symbols


def norm(s): return re.sub(r'[^a-z0-9]','',str(s).lower().replace('index',''))

def find_symbol(asset, symbols):
    wanted=norm(asset)
    candidates=[]
    for item in symbols:
        names=[item.get('display_name',''),item.get('underlying_symbol',''),item.get('symbol','')]
        if any(norm(n)==wanted for n in names if n): candidates.append(item)
    # Forex symbols may be represented with an alias/display name; require exact normalized pair.
    if not candidates and '/' in asset:
        compact=asset.replace('/','').upper()
        candidates=[x for x in symbols if compact in [str(x.get('symbol','')).upper(),str(x.get('underlying_symbol','')).upper()]]
    if len(candidates)!=1:
        raise RuntimeError('Não encontrei uma correspondência única e exacta deste activo na Deriv. Não vou substituir por outro símbolo.')
    item=candidates[0]
    return item.get('underlying_symbol') or item.get('symbol'), item.get('display_name') or asset


def get_candles(symbol, granularity, count=220):
    msg=deriv_request({'ticks_history':symbol,'adjust_start_time':1,'count':count,'end':'latest','start':1,'style':'candles','granularity':granularity})
    candles=msg.get('candles')
    if not isinstance(candles,list) or len(candles)<80: raise RuntimeError('Dados históricos insuficientes recebidos da Deriv.')
    df=pd.DataFrame(candles)
    for col in ['open','high','low','close']:
        df[col]=pd.to_numeric(df[col],errors='coerce')
    df['epoch']=pd.to_numeric(df['epoch'],errors='coerce')
    df=df.dropna(subset=['open','high','low','close','epoch']).sort_values('epoch').drop_duplicates('epoch').reset_index(drop=True)
    valid=(df['high']>=df[['open','close','low']].max(axis=1)) & (df['low']<=df[['open','close','high']].min(axis=1))
    df=df[valid].reset_index(drop=True)
    if len(df)<80: raise RuntimeError('As velas recebidas não passaram na validação OHLC.')
    age=time.time()-float(df.epoch.iloc[-1])
    if age > max(granularity*3, 900): raise RuntimeError(f'Última vela demasiado antiga ({int(age)} segundos). Análise cancelada.')
    return df, age


def indicators(df):
    d=df.copy(); c=d.close; h=d.high; l=d.low
    d['ema20']=c.ewm(span=20,adjust=False).mean(); d['ema50']=c.ewm(span=50,adjust=False).mean()
    delta=c.diff(); gain=delta.clip(lower=0).ewm(alpha=1/14,adjust=False).mean(); loss=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
    rs=gain/loss.replace(0,np.nan); d['rsi']=100-(100/(1+rs)); d['rsi']=d.rsi.fillna(50)
    ema12=c.ewm(span=12,adjust=False).mean(); ema26=c.ewm(span=26,adjust=False).mean(); d['macd']=ema12-ema26; d['macd_signal']=d.macd.ewm(span=9,adjust=False).mean()
    prev=c.shift(1); tr=pd.concat([(h-l),(h-prev).abs(),(l-prev).abs()],axis=1).max(axis=1); d['atr']=tr.ewm(alpha=1/14,adjust=False).mean()
    d['fractal_high']=False; d['fractal_low']=False
    for i in range(2,len(d)-2):
        d.loc[i,'fractal_high']=h.iloc[i]>max(h.iloc[i-2],h.iloc[i-1],h.iloc[i+1],h.iloc[i+2])
        d.loc[i,'fractal_low']=l.iloc[i]<min(l.iloc[i-2],l.iloc[i-1],l.iloc[i+1],l.iloc[i+2])
    return d


def technical_decision(d):
    last=d.iloc[-1]; prev=d.iloc[-2]; close=float(last.close); atr=float(last.atr)
    if not np.isfinite(atr) or atr<=0: raise RuntimeError('ATR inválido; não é possível calcular níveis de risco.')
    buy=0; sell=0; why_buy=[]; why_sell=[]
    if last.ema20>last.ema50 and close>last.ema20: buy+=2; why_buy.append('preço acima das EMA20/50 com alinhamento positivo' if last.ema20>last.ema50 else 'preço acima da EMA20')
    elif last.ema20<last.ema50 and close<last.ema20: sell+=2; why_sell.append('preço abaixo das EMA20/50 com alinhamento negativo')
    if last.macd>last.macd_signal: buy+=1; why_buy.append('MACD acima da linha de sinal')
    elif last.macd<last.macd_signal: sell+=1; why_sell.append('MACD abaixo da linha de sinal')
    if 50<last.rsi<68: buy+=1; why_buy.append(f'RSI {last.rsi:.1f}, momentum comprador sem sobrecompra extrema')
    elif 32<last.rsi<50: sell+=1; why_sell.append(f'RSI {last.rsi:.1f}, momentum vendedor sem sobrevenda extrema')
    if close>prev.close and last.close>last.open: buy+=1; why_buy.append('última vela fechou positiva')
    elif close<prev.close and last.close<last.open: sell+=1; why_sell.append('última vela fechou negativa')
    if buy>=3 and buy-sell>=2: side='BUY'
    elif sell>=3 and sell-buy>=2: side='SELL'
    else: side='AGUARDAR'
    # Levels anchored to actual latest Deriv close; no arbitrary model prices.
    if side=='BUY': entry=close; sl=close-1.2*atr; tp=close+1.8*atr
    elif side=='SELL': entry=close; sl=close+1.2*atr; tp=close-1.8*atr
    else: entry=sl=tp=None
    return {'signal':side,'buy_score':buy,'sell_score':sell,'close':close,'rsi':float(last.rsi),'ema20':float(last.ema20),'ema50':float(last.ema50),'macd':float(last.macd),'macd_signal':float(last.macd_signal),'atr':atr,'entry':entry,'sl':sl,'tp':tp,'rr':1.5 if side!='AGUARDAR' else None,'buy_evidence':why_buy,'sell_evidence':why_sell,'last_epoch':int(last.epoch)}


def image_comment(image, meta, tech, api_key, model):
    if not api_key: return 'Comentário visual não disponível: OPENROUTER_API_KEY não configurada.'
    im=ImageOps.exif_transpose(image).convert('RGB'); im.thumbnail((1400,1400)); b=BytesIO(); im.save(b,'JPEG',quality=82)
    prompt=(f"Analisa visualmente este screenshot em português. Plataforma {meta['platform']}; ativo selecionado {meta['asset']}; timeframe {meta['timeframe']}. "
    f"Dados OHLC independentes da Deriv: {meta['deriv_name']}, fecho {tech['close']}, RSI {tech['rsi']:.1f}, EMA20 {tech['ema20']}, EMA50 {tech['ema50']}. "
    "Comenta apenas o que é legível na imagem. Não determines nem alteres BUY/SELL, não inventes preços, não declares que o símbolo coincide se não estiver visível. Até 4 frases.")
    payload={'model':model,'temperature':0.1,'max_tokens':350,'messages':[{'role':'user','content':[{'type':'text','text':prompt},{'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(b.getvalue()).decode()}}]}]}
    r=requests.post(OPENROUTER_URL,headers={'Authorization':'Bearer '+api_key,'Content-Type':'application/json','HTTP-Referer':'https://doncullertrade47.onrender.com','X-Title':APP},json=payload,timeout=(20,90))
    if r.status_code>=400: return f'Comentário visual indisponível (OpenRouter HTTP {r.status_code}).'
    try: return str(r.json()['choices'][0]['message']['content']).strip()
    except Exception: return 'O modelo não devolveu comentário visual utilizável.'


def fmt(v): return '—' if v is None else f'{v:.5f}'.rstrip('0').rstrip('.')

st.markdown(f'<div class="hero"><div class="small">{VERSION} · DADOS OHLC DERIV + VALIDAÇÃO LOCAL</div><h1>🦁 {APP}</h1><span class="small">Dados de mercado primeiro. Screenshot como confirmação visual.</span></div>',unsafe_allow_html=True)
with st.sidebar:
    st.subheader('Configuração')
    market=st.selectbox('Mercado',list(MARKETS))
    asset=st.selectbox('Activo',MARKETS[market])
    platform=st.selectbox('Plataforma do gráfico',PLATFORMS)
    timeframe=st.selectbox('Timeframe',TIMEFRAMES,index=3)
    model=st.text_input('Modelo OpenRouter',MODEL_DEFAULT)
    st.caption('OPENROUTER_API_KEY é configurada nas Environment Variables do Render.')

left,right=st.columns([1.05,.95],gap='large')
with left:
    st.subheader('Screenshot')
    upload=st.file_uploader('Carrega o gráfico',type=['png','jpg','jpeg','webp'],key='v16_image')
    image_obj=None
    if upload:
        try:
            image_obj=Image.open(upload); image_obj.load(); st.image(image_obj,caption='Imagem recebida',use_container_width=True)
        except (UnidentifiedImageError,OSError): st.error('Imagem inválida. Envia PNG ou JPG.')
    st.info('Confirma que o símbolo e o timeframe seleccionados correspondem exactamente ao gráfico. A Deriv será a fonte OHLC; a imagem não substitui essa confirmação.')
    run=st.button('🦁 ANALISAR COM DADOS DERIV',use_container_width=True)
with right:
    st.subheader('Resultado V16')
    if run:
        if not image_obj: st.warning('Carrega primeiro um screenshot válido.')
        elif timeframe not in GRANULARITY: st.error('Timeframe não suportado pela fonte Deriv.')
        else:
            try:
                with st.spinner('A confirmar símbolo e a obter velas reais da Deriv...'):
                    symbols=get_deriv_symbols(); symbol,deriv_name=find_symbol(asset,symbols)
                    candles,age=get_candles(symbol,GRANULARITY[timeframe]); data=indicators(candles); tech=technical_decision(data)
                    meta={'market':market,'asset':asset,'platform':platform,'timeframe':timeframe,'deriv_name':deriv_name}
                    comment=image_comment(image_obj,meta,tech,os.getenv('OPENROUTER_API_KEY','').strip(),model.strip())
                    st.session_state['v16_result']={'tech':tech,'comment':comment,'meta':meta,'age':age,'symbol':symbol}
            except Exception as e:
                st.session_state.pop('v16_result',None); st.error(str(e))
    result=st.session_state.get('v16_result')
    if result:
        t=result['tech']; sig=t['signal']; cls={'BUY':'buy','SELL':'sell','AGUARDAR':'wait'}[sig]
        st.markdown(f'<div class="box"><div class="{cls}">{sig}</div><b>{result["meta"]["asset"]} · {result["meta"]["timeframe"]}</b><br><span class="small">Fonte: Deriv · {result["symbol"]}</span></div>',unsafe_allow_html=True)
        st.caption(f'Força técnica calculada: BUY {t["buy_score"]}/4 · SELL {t["sell_score"]}/4 — não é probabilidade de vitória.')
        st.write(f'**Preço de fecho da última vela:** {fmt(t["close"])}')
        st.write(f'**RSI:** {t["rsi"]:.1f} | **EMA20:** {fmt(t["ema20"])} | **EMA50:** {fmt(t["ema50"])}')
        st.write(f'**MACD:** {fmt(t["macd"])} | **Sinal MACD:** {fmt(t["macd_signal"])} | **ATR:** {fmt(t["atr"])}')
        st.write('**Evidências BUY:** '+('; '.join(t['buy_evidence']) or 'Sem confirmação suficiente.'))
        st.write('**Evidências SELL:** '+('; '.join(t['sell_evidence']) or 'Sem confirmação suficiente.'))
        if sig!='AGUARDAR':
            st.success(f'Entrada de referência: {fmt(t["entry"])}')
            st.write(f'**Stop Loss:** {fmt(t["sl"])}')
            st.write(f'**Take Profit:** {fmt(t["tp"])}')
            st.write('**Risco/retorno planeado:** 1:1,50')
            st.warning('A entrada é uma referência calculada no fecho da última vela. Espera por nova confirmação/activação; não é ordem automática.')
        else: st.info('Os indicadores não apresentam vantagem mínima e concordante. Não há entrada validada neste momento.')
        st.markdown('**Verificação visual do screenshot**')
        st.write(result['comment'])
        st.caption(f'Última vela: {datetime.fromtimestamp(t["last_epoch"],timezone.utc).strftime("%Y-%m-%d %H:%M UTC")} · idade aproximada: {int(result["age"])} s.')
    else: st.caption('O relatório aparecerá aqui depois da análise.')

st.divider()
st.markdown('<div class="small">V16 não guarda histórico de sinais nem resultados. A análise técnica é calculada localmente a partir de velas públicas da Deriv. O screenshot é comentário complementar. A correspondência do símbolo no gráfico externo deve ser confirmada pelo utilizador. Não há execução automática de ordens nem taxa de acerto garantida. Testa primeiro em conta Demo.</div>',unsafe_allow_html=True)
