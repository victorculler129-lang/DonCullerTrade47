import os
import re
import base64
from io import BytesIO
from datetime import datetime

import requests
import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError

# DONCULLER-TRADE47 V7.0

st.set_page_config(page_title="DONCULLER-TRADE47", page_icon="🦁", layout="wide")
API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
MODEL = "openrouter/free"
API_URL = "https://openrouter.ai/api/v1/chat/completions"

st.markdown("""
<style>
.stApp{background:#071321;color:#edf3fa}
section[data-testid="stSidebar"]{background:#0b1b2d}
.block-container{max-width:1250px;padding-top:1.1rem}
.dc-panel{background:#0d2033;border:1px solid #23415e;border-radius:15px;padding:19px;margin-bottom:14px}
.dc-buy{color:#25d887;font-size:32px;font-weight:850}
.dc-sell{color:#ff6874;font-size:32px;font-weight:850}
.dc-wait{color:#ffc857;font-size:32px;font-weight:850}
div.stButton>button{background:#176b50;color:white;border:0;border-radius:10px;min-height:3rem;font-weight:750}
div.stButton>button:hover{background:#208362;color:white}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="dc-panel"><h1>🦁 DONCULLER-TRADE47</h1><p>AI CHART ANALYZER · V7.0</p></div>', unsafe_allow_html=True)

SYNTHETIC_ASSETS = [
    "Boom 1000","Crash 1000","Boom 500","Crash 500","Boom 300","Crash 300",
    "Boom 100","Crash 100","Boom 50","Crash 50","Jump Index 50","Jump Index","Step Index"
]
FOREX_ASSETS = ["EUR/USD","GBP/USD","XAU/USD"]

with st.sidebar:
    st.header("⚙️ CONFIGURAÇÃO")
    market = st.radio("Mercado", ["Índices sintéticos","Forex"])
    asset = st.selectbox("Ativo", SYNTHETIC_ASSETS if market == "Índices sintéticos" else FOREX_ASSETS)
    timeframe = st.selectbox("Timeframe", ["M1","M5","M15","M30","H1","H4","D1"], index=1)
    platform = st.selectbox("Plataforma", ["Deriv MT5","TradingView","Outra"])
    st.divider()
    st.caption("V7.0 · Análise visual de screenshots")
    st.caption("Modelo: OpenRouter Free Router")


def build_prompt():
    return f"""
És o motor de análise técnica da DONCULLER-TRADE47. Analisa a imagem do gráfico.
Responde em português simples. Não inventes informação nem prometas lucro.

CONTEXTO: Ativo {asset}; Mercado {market}; Timeframe {timeframe}; Plataforma {platform}.

OBJETIVO: identificar a melhor configuração FUTURA entre BUY e SELL.
Avalia as duas direções com os MESMOS critérios. Não favoreças SELL, BUY ou AGUARDAR.
Não tens acesso a cotações em tempo real nem a dados OHLC; só podes ler o screenshot.
Se imagem/preços estiverem ilegíveis, declara isso. Não inventes níveis.

ANALISA:
- Estrutura, tendência, topos/fundos ascendentes e descendentes, impulsos e correções.
- Velas, corpos, pavios, rejeições, engolfos e fechos.
- Suportes, resistências, rompimentos, retestes e falsos rompimentos.
- Zig Zag: pivôs visíveis; nota que o último segmento pode repintar.
- Fractals: fractais superiores/inferiores visíveis e confirmação.
- MACD: cruzamento, direção das linhas e histograma, se visíveis.
- RSI e médias móveis apenas se estiverem visíveis.
Se algum indicador não estiver visível, escreve "Não visível no screenshot".

BUY: procura rejeição de suporte, fundo mais alto, recuperação de nível,
engolfo bullish, rompimento/reteste para cima, fractal inferior confirmado,
Zig Zag ascendente e confirmações MACD/RSI/médias quando visíveis.

SELL: procura rejeição de resistência, topo mais baixo, perda de suporte,
engolfo bearish, rompimento/reteste para baixo, fractal superior confirmado,
Zig Zag descendente e confirmações MACD/RSI/médias quando visíveis.

Boom/Crash/Jump/Step: não deduzas direção pelo nome do ativo nem inventes spikes.
Analisa apenas o comportamento visível.

FORÇA BUY e FORÇA SELL: notas técnicas subjetivas de 0 a 100, NÃO probabilidades
de lucro. Explica os fatores. Diferença pequena entre notas não é sinal suficiente.

BUY ou SELL apenas se existir evidência direcional e configuração operacional:
ativação observável, entrada condicional, invalidação estrutural e objetivos plausíveis.
Se a direção parecer provável mas faltar confirmação, usa AGUARDAR e explica o gatilho.
Se não houver configuração, escreve "SEM CONFIGURAÇÃO VÁLIDA".
SL deve invalidar a ideia; TP1/TP2 devem ser níveis tecnicamente plausíveis.
Se preço não for legível, escreve "INDETERMINÁVEL PELA IMAGEM".

FORMATO:
QUALIDADE DA IMAGEM:
TENDÊNCIA / ESTRUTURA:
VELAS:
ZIG ZAG:
FRACTALS:
MACD:
RSI:
MÉDIAS MÓVEIS:
SUPORTE:
RESISTÊNCIA:

FORÇA BUY (0-100):
MOTIVOS BUY:
FORÇA SELL (0-100):
MOTIVOS SELL:
DIREÇÃO COM MAIOR EVIDÊNCIA:

CENÁRIO BUY:
Entrada/zona:
Ativação:
SL:
TP1:
TP2:
Risco/retorno:
Estado: VÁLIDO ou SEM CONFIGURAÇÃO VÁLIDA

CENÁRIO SELL:
Entrada/zona:
Ativação:
SL:
TP1:
TP2:
Risco/retorno:
Estado: VÁLIDO ou SEM CONFIGURAÇÃO VÁLIDA

DECISÃO FINAL: BUY / SELL / AGUARDAR
JUSTIFICAÇÃO:
O QUE INVALIDA A LEITURA:

A decisão final deve aparecer uma única vez e ser coerente com os cenários.
Não acrescentes texto fora deste formato.
"""


def prepare_image(uploaded):
    try:
        uploaded.seek(0)
        img = ImageOps.exif_transpose(Image.open(uploaded)).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("O ficheiro não é uma imagem válida.") from exc
    if img.width < 300 or img.height < 200:
        raise ValueError("Imagem demasiado pequena. Envia um screenshot mais nítido.")
    img.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    return img


def image_data_url(img):
    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=88, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def extract_text(data):
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"API sem resposta utilizável: {data.get('error', data)}")
    content = ((choices[0] or {}).get("message") or {}).get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") in ("text","output_text"):
                parts.append(item.get("text", ""))
        result = "\n".join(x for x in parts if x).strip()
        if result:
            return result
    raise RuntimeError("O modelo respondeu sem texto. Tenta novamente.")


def analyze_chart(img, prompt):
    if not API_KEY:
        raise RuntimeError("Falta OPENROUTER_API_KEY nas variáveis de ambiente do Render.")
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": image_data_url(img)}}
        ]}],
        "temperature": 0.15,
        "max_tokens": 3500,
        "stream": False
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "X-Title": "DONCULLER-TRADE47"
    }
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=(20,180))
    except requests.Timeout as exc:
        raise RuntimeError("O serviço demorou demasiado. Tenta novamente.") from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"Falha de ligação ao OpenRouter: {exc}") from exc

    errors = {
        401: "Chave API inválida ou não reconhecida.",
        402: "Acesso/créditos insuficientes.",
        403: "Pedido não autorizado.",
        404: "Modelo ou endpoint não encontrado.",
        429: "Limite de pedidos atingido. Aguarda e tenta novamente."
    }
    if response.status_code in errors:
        raise RuntimeError(f"OpenRouter {response.status_code}: {errors[response.status_code]}")
    if not response.ok:
        try:
            detail = (response.json().get("error") or {}).get("message", response.text[:800])
        except ValueError:
            detail = response.text[:800]
        raise RuntimeError(f"OpenRouter {response.status_code}: {detail}")
    try:
        return extract_text(response.json())
    except ValueError as exc:
        raise RuntimeError("O OpenRouter devolveu JSON inválido.") from exc


def detect_signal(report):
    found = re.findall(
        r"^\s*DECIS[AÃ]O\s+FINAL\s*:\s*(BUY|SELL|AGUARDAR)\b",
        report, flags=re.IGNORECASE | re.MULTILINE
    )
    return found[-1].upper() if found else None


# ================= INPUT =================

left, right = st.columns([1.35, 1])
with left:
    st.markdown('<div class="dc-panel"><h3>📷 GRÁFICO PARA ANÁLISE</h3><p>Envia uma captura nítida com velas e escala de preços visíveis.</p></div>', unsafe_allow_html=True)
    uploaded = st.file_uploader("Carregar screenshot", type=["png","jpg","jpeg"], key="chart_upload")
    chart_image = None
    if uploaded is not None:
        try:
            chart_image = prepare_image(uploaded)
            st.image(chart_image, caption=f"{asset} · {timeframe} · {platform}", use_container_width=True)
        except ValueError as exc:
            st.error(str(exc))

with right:
    st.markdown("""
    <div class="dc
