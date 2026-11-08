import os
import re
import base64
from io import BytesIO

import requests
import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError

# =========================================================
# DONCULLER-TRADE47 V5.0
# Análise visual de screenshots — não usa cotações ao vivo
# =========================================================

st.set_page_config(
    page_title="DONCULLER-TRADE47",
    page_icon="🦁",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.stApp {background:#071321;color:#edf3fa}
section[data-testid="stSidebar"] {background:#0b1b2d}
.block-container {max-width:1250px;padding-top:1.2rem}
.dc-panel {background:#0d2033;border:1px solid #23415e;border-radius:15px;padding:20px;margin-bottom:15px}
.dc-buy {color:#25d887;font-size:30px;font-weight:800}
.dc-sell {color:#ff6874;font-size:30px;font-weight:800}
.dc-wait {color:#ffc857;font-size:30px;font-weight:800}
div.stButton>button {background:#176b50;color:white;border:0;border-radius:10px;min-height:3rem;font-weight:700}
div.stButton>button:hover {background:#208362;color:white}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="dc-panel">
<h1>🦁 DONCULLER-TRADE47</h1>
<p>AI TRADING CHART ANALYZER · V5.0</p>
</div>
""", unsafe_allow_html=True)

# ---------------- API ----------------
API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
MODEL = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3.5-super-vl:free").strip()
API_URL = "https://openrouter.ai/api/v1/chat/completions"

# ---------------- ATIVOS ----------------
SYNTHETIC_ASSETS = [
    "Boom 1000", "Crash 1000", "Boom 500", "Crash 500",
    "Boom 300", "Crash 300", "Boom 100", "Crash 100",
    "Boom 50", "Crash 50", "Jump Index 50", "Jump Index", "Step Index"
]
FOREX_ASSETS = ["EUR/USD", "GBP/USD", "XAU/USD"]

with st.sidebar:
    st.header("⚙️ CONFIGURAÇÃO")
    market = st.radio("Mercado", ["Índices sintéticos", "Forex"])
    asset = st.selectbox("Ativo", SYNTHETIC_ASSETS if market == "Índices sintéticos" else FOREX_ASSETS)
    timeframe = st.selectbox("Timeframe", ["M1", "M5", "M15", "M30", "H1", "H4", "D1"], index=1)
    platform = st.selectbox("Plataforma", ["Deriv MT5", "TradingView", "Outra"])
    st.caption("V5.0 · Avaliação equilibrada BUY/SELL")
    st.divider()
    st.caption(f"Modelo: {MODEL}")

# ---------------- PROMPT ----------------
def build_prompt():
    return f"""
És o motor de análise técnica da DONCULLER-TRADE47 V5.0.
Analisa exclusivamente a imagem. Não tens acesso a cotações ao vivo nem a dados OHLC.

CONTEXTO: Ativo {asset}; mercado {market}; timeframe {timeframe}; plataforma {platform}.

REGRA FUNDAMENTAL DE EQUILÍBRIO:
Avalia BUY e SELL separadamente, com os MESMOS critérios e sem preferência inicial por qualquer lado.
Não assumas que a tendência anterior continuará. Considera reversões, rejeições, rompimentos e falsos rompimentos.
Não escolhas SELL apenas porque houve uma queda anterior, nem BUY apenas porque houve uma subida anterior.
Primeiro identifica a estrutura atual e o preço relativamente aos suportes/resistências; depois compara os dois cenários.
Uma pontuação maior não basta: o cenário vencedor precisa de entrada, ativação, SL e TP1 coerentes.
Se BUY for mais forte e válido, a decisão pode e deve ser BUY. Se SELL for mais forte e válido, pode e deve ser SELL.
AGUARDAR só quando nenhum dos dois cenários tiver evidência e níveis minimamente confiáveis. Não uses AGUARDAR por rotina.

ANÁLISE:
- Estrutura: topos/fundos, tendência, impulsos, correções, suportes, resistências, rompimentos e rejeições.
- Velas: corpos, pavios, engolfo e sequência, apenas quando legíveis.
- Zig Zag e Fractals: descreve apenas se estiverem visíveis.
- MACD, RSI e médias móveis: descreve apenas se estiverem visíveis e legíveis.
- Nunca inventes valores de indicadores nem preços. Se ilegível, escreve "Indeterminável pela imagem".
- As pontuações são notas técnicas subjetivas de 0 a 100, não probabilidades de lucro.
- Se a escala permitir, indica preços aproximados e assinala que são leituras visuais.
- Define SL além da invalidação estrutural e TP em níveis plausíveis. Não inventes níveis.
- Se não houver setup válido num dos lados, escreve "Sem configuração válida".

FORMATO EXATO:
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

CENÁRIO BUY
Estado: VÁLIDO ou SEM CONFIGURAÇÃO VÁLIDA
Entrada/zona:
Ativação:
SL:
TP1:
TP2:
Risco/retorno estimado:

CENÁRIO SELL
Estado: VÁLIDO ou SEM CONFIGURAÇÃO VÁLIDA
Entrada/zona:
Ativação:
SL:
TP1:
TP2:
Risco/retorno estimado:

DIREÇÃO COM MAIOR EVIDÊNCIA: BUY / SELL / NENHUMA
DECISÃO FINAL: BUY / SELL / AGUARDAR
JUSTIFICAÇÃO:
O QUE INVALIDA A LEITURA:

A decisão final deve corresponder à comparação real das duas pontuações e à validade dos cenários.
Responde em português simples, sem texto fora deste formato.
"""

# ---------------- IMAGEM ----------------
def prepare_image(uploaded):
    try:
        uploaded.seek(0)
        img = Image.open(uploaded)
        img = ImageOps.exif_transpose(img).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("O ficheiro não é uma imagem válida.") from exc
    if img.width < 300 or img.height < 200:
        raise ValueError("A imagem é demasiado pequena. Envia um screenshot mais nítido.")
    img.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
    return img

# ---------------- OPENROUTER ----------------
def extract_response_text(data):
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"A API não devolveu escolhas: {data.get('error') or data}")
    choice = choices[0] or {}
    message = choice.get("message") or {}
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") in ("text", "output_text"):
                parts.append(item.get("text", ""))
        result = "\n".join(x for x in parts if x).strip()
        if result:
            return result
    raise RuntimeError(
        "O modelo não devolveu texto final. "
        f"finish_reason={choice.get('finish_reason')}; "
        f"message_keys={list(message.keys())}; usage={data.get('usage')}"
    )

def analyze_chart(chart_image, prompt):
    if not API_KEY:
        raise RuntimeError("Falta OPENROUTER_API_KEY no Render.")
    buffer = BytesIO()
    chart_image.save(buffer, format="JPEG", quality=90, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    payload = {
        "model": MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}}
            ]
        }],
        "temperature": 0.1,
        "max_tokens": 3500,
        "stream": False
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "X-Title": "DONCULLER-TRADE47"
    }
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=(20, 180))
    except requests.Timeout as exc:
        raise RuntimeError("O OpenRouter demorou demasiado a responder. Tenta novamente.") from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"Falha de ligação ao OpenRouter: {exc}") from exc

    if response.status_code == 401:
        raise RuntimeError("OpenRouter 401: chave API não reconhecida. Não publiques a chave.")
    if response.status_code == 402:
        raise RuntimeError("OpenRouter 402: créditos ou acesso insuficientes para este modelo.")
    if response.status_code == 403:
        raise RuntimeError("OpenRouter 403: pedido não autorizado ou chave sem permissões.")
    if response.status_code == 404:
        raise RuntimeError(f"OpenRouter 404: modelo ou endpoint não encontrado ({MODEL}).")
    if response.status_code == 429:
        raise RuntimeError("OpenRouter 429: limite de pedidos atingido. Aguarda e tenta novamente.")
    if response.status_code >= 500:
        raise RuntimeError(f"OpenRouter temporariamente indisponível ({response.status_code}).")
    if not response.ok:
        try:
            body = response.json()
            detail = (body.get("error") or {}).get("message") or str(body)[:1000]
        except ValueError:
            detail = response.text[:1000]
        raise RuntimeError(f"OpenRouter {response.status_code}: {detail}")
    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError("O OpenRouter devolveu uma resposta que não é JSON válido.") from exc
    return extract_response_text(data)

# ---------------- DECISÃO EQUILIBRADA ----------------
def extract_score(report, side):
    patterns = [
        rf"FORÇA\s+{side}\s*\(0\s*[-–]\s*100\)\s*:\s*(\d{{1,3}})",
        rf"FORÇA\s+{side}\b[^:\n]*:\s*(\d{{1,3}})"
    ]
    for pattern in patterns:
        match = re.search(pattern, report, re.IGNORECASE)
        if match:
            value = int(match.group(1))
            return value if 0 <= value <= 100 else None
    return None

def scenario_is_valid(report, side):
    section_match = re.search(
        rf"CENÁRIO\s+{side}\b(.*?)(?=CENÁRIO\s+(?:BUY|SELL)\b|DIREÇÃO\s+COM\s+MAIOR|DECISÃO\s+FINAL|$)",
        report, re.IGNORECASE | re.DOTALL
    )
    if not section_match:
        return False
    section = section_match.group(1)
    if re.search(r"SEM\s+CONFIGURAÇÃO\s+VÁLIDA", section, re.IGNORECASE):
        return False
    for label in ("Entrada", "Ativação", "SL", "TP1"):
        match = re.search(rf"{label}\s*:\s*([^\n]+)", section, re.IGNORECASE)
        if not match:
            return False
        value = match.group(1).strip().lower()
        if not value or any(term in value for term in (
            "indeterminável", "não disponível", "sem configuração", "não definido", "n/a"
        )):
            return False
    return True

def resolve_signal(report):
    buy_score = extract_score(report, "BUY")
    sell_score = extract_score(report, "SELL")
    buy_valid = scenario_is_valid(report, "BUY")
    sell_valid = scenario_is_valid(report, "SELL")

    candidates = []
    if buy_valid and buy_score is not None and buy_score >= 60:
        candidates.append(("BUY", buy_score))
    if sell_valid and sell_score is not None and sell_score >= 60:
        candidates.append(("SELL", sell_score))

    if not candidates:
        return "AGUARDAR", buy_score, sell_score, "Nenhum cenário atingiu os critérios mínimos com níveis completos."
    candidates.sort(key=lambda item: item[1], reverse=True)
    if len(candidates) == 2 and candidates[0][1] - candidates[1][1] < 8:
        return "AGUARDAR", buy_score, sell_score, "As forças BUY e SELL estão demasiado próximas."
    return candidates[0][0], buy_score, sell_score, "Decisão calculada pela comparação das forças e validade dos cenários."

def replace_final_decision(report, signal):
    pattern = r"DECIS[AÃ]O\s+FINAL\s*:\s*(?:BUY|SELL|AGUARDAR)"
    replacement = f"DECISÃO FINAL: {signal}"
    if re.search(pattern, report, re.IGNORECASE):
        return re.sub(pattern, replacement, report, count=1, flags=re.IGNORECASE)
    return report.rstrip() + "\n\n" + replacement

# ---------------- INTERFACE ----------------
left, right = st.columns([1.35, 1])
with left:
    st.markdown("""
    <div class="dc-panel">
    <h3>📷 GRÁFICO PARA ANÁLISE</h3>
    <p>Envia uma captura nítida, com velas e escala de preços visíveis.</p>
    </div>
    """, unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Carregar screenshot", type=["png", "jpg", "jpeg"], key="chart_upload")
    chart_image = None
    if uploaded_file is not None:
        try:
            chart_image = prepare_image(uploaded_file)
            st.image(chart_image, caption=f"{asset} · {timeframe} · {platform}", use_container_width=True)
        except ValueError as exc:
            st.error(str(exc))

with right:
    st.markdown("""
    <div class="dc-panel">
    <h3>📊 MOTOR DE ANÁLISE</h3>
    <p>🟢 BUY — Comprar</p>
    <p>🔴 SELL — Vender</p>
    <p>🟡 AGUARDAR — Sem confirmação suficiente</p>
    <hr>
    <p>Compara os dois cenários com critérios simétricos.</p>
    </div>
    """, unsafe_allow_html=True)
    st.info("A análise usa apenas a imagem. Indicadores invisíveis não podem ser confirmados nem calculados com rigor.")

if st.button("🦁 ANALISAR GRÁFICO", use_container_width=True, disabled=(chart_image is None)):
    try:
        with st.spinner("A DONCULLER-TRADE47 está a analisar BUY e SELL..."):
            raw_report = analyze_chart(chart_image, build_prompt())
        signal, buy_score, sell_score, reason = resolve_signal(raw_report)
        report = replace_final_decision(raw_report, signal)
        st.session_state["last_result"] = report
        st.session_state["last_signal"] = signal
        st.session_state["last_scores"] = (buy_score, sell_score)
        st.session_state["last_reason"] = reason
        st.session_state["last_asset"] = asset
        st.session_state["last_timeframe"] = timeframe
        st.session_state["last_market"] = market
        st.session_state["last_platform"] = platform
    except Exception as exc:
        st.error(f"Erro durante a análise: {exc}")

# ---------------- RESULTADOS ----------------
if "last_result" in st.session_state:
    report = st.session_state["last_result"]
    signal = st.session_state.get("last_signal", "AGUARDAR")
    buy_score, sell_score = st.session_state.get("last_scores", (None, None))
    st.divider()
    st.subheader("📊 RELATÓRIO DE ANÁLISE")
    st.caption(
        f"Ativo: {st.session_state.get('last_asset', '')} | "
        f"Timeframe: {st.session_state.get('last_timeframe', '')} | "
        f"Mercado: {st.session_state.get('last_market', '')} | "
        f"Plataforma: {st.session_state.get('last_platform', '')}"
    )
    if signal == "BUY":
        st.markdown('<div class="dc-panel dc-buy">🟢 BUY</div>', unsafe_allow_html=True)
    elif signal == "SELL":
        st.markdown('<div class="dc-panel dc-sell">🔴 SELL</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="dc-panel dc-wait">🟡 AGUARDAR</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    c1.metric("Força BUY", "Não identificada" if buy_score is None else f"{buy_score}/100")
    c2.metric("Força SELL", "Não identificada" if sell_score is None else f"{sell_score}/100")
    st.caption(st.session_state.get("last_reason", ""))
    st.markdown(report)
    st.download_button(
        "⬇️ DESCARREGAR RELATÓRIO",
        data=report,
        file_name="DonCullerTrade47_V5_0.txt",
        mime="text/plain",
        use_container_width=True
    )

st.divider()
st.caption("DONCULLER-TRADE47 · AI CHART ANALYZER · V5.0")
st.warning(
    "Ferramenta de análise visual, não recebe cotações em tempo real, "
    "não executa operações e não garante resultados. Pontuações são avaliações "
    "subjetivas do modelo. Confirma preços e níveis no MT5 e testa em Demo."
)
