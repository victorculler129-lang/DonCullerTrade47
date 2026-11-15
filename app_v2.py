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
API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_DEFAULT = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3.5-super-vl:free").strip()
DB_PATH = os.getenv("DONCULLER_DB_PATH", "donculler_history.db")

st.set_page_config(page_title=APP, page_icon="🦁", layout="wide")
st.markdown("""
<style>
.stApp {background:#071321;color:#edf4fb;}
section[data-testid="stSidebar"] {background:#0b1b2d;}
.hero,.box {background:#0d2033;border:1px solid #24445e;border-radius:14px;padding:18px;}
.buy {color:#25d887;font-size:30px;font-weight:800;}
.sell {color:#ff6874;font-size:30px;font-weight:800;}
.wait {color:#ffc857;font-size:30px;font-weight:800;}
div.stButton>button {background:#16865f;color:white;font-weight:700;border:0;min-height:46px;}
.small {color:#9fb3c8;font-size:13px;}
</style>
""", unsafe_allow_html=True)

MARKETS = {
    "Forex": ["EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD", "NZD/USD", "USD/CAD", "EUR/GBP", "EUR/JPY", "GBP/JPY", "XAU/USD", "XAG/USD", "Outro par Forex"],
    "Índices Sintético": [
        "Volatility 10 Index", "Volatility 10 (1s) Index", "Volatility 25 Index", "Volatility 25 (1s) Index",
        "Volatility 50 Index", "Volatility 50 (1s) Index", "Volatility 75 Index", "Volatility 75 (1s) Index",
        "Volatility 100 Index", "Volatility 100 (1s) Index", "Volatility 150 (1s) Index", "Volatility 250 (1s) Index",
        "Boom 300 Index", "Boom 500 Index", "Boom 600 Index", "Boom 900 Index", "Boom 1000 Index",
        "Crash 300 Index", "Crash 500 Index", "Crash 600 Index", "Crash 900 Index", "Crash 1000 Index",
        "Jump 10 Index", "Jump 25 Index", "Jump 50 Index", "Jump 75 Index", "Jump 100 Index",
        "Step Index", "Multi Step Index", "Range Break 100 Index", "Range Break 200 Index", "Drift Switch Index", "Outro índice sintético"
    ],
    "Outro": ["Bitcoin (BTC/USD)", "Ethereum (ETH/USD)", "Outra criptomoeda", "US 500", "US 100", "US 30", "Germany 40", "UK 100", "Ação", "Matéria-prima", "Outro ativo"]
}
PLATFORMS = ["MetaTrader 5 (MT5)", "cTrader", "TradingView", "Outra plataforma"]
TIMEFRAMES = ["M1", "M2", "M3", "M5", "M10", "M15", "M30", "H1", "H2", "H4", "D1", "W1", "MN1"]


def db_init():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT NOT NULL,
            market TEXT, asset TEXT, platform TEXT, timeframe TEXT,
            signal TEXT, confidence REAL, entry TEXT, sl TEXT, tp TEXT
        )""")


def save_result(meta, result):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""INSERT INTO history
            (created, market, asset, platform, timeframe, signal, confidence, entry, sl, tp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (datetime.now(timezone.utc).isoformat(), meta["market"], meta["asset"],
             meta["platform"], meta["timeframe"], result["signal"], result["confidence"],
             result["entry"], result["sl"], result["tp"]))


def extract_text(content):
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, dict):
        for key in ("text", "output_text", "content"):
            if key in content:
                try:
                    value = extract_text(content[key])
                    if value:
                        return value
                except ValueError:
                    continue
        raise ValueError("A resposta veio num objeto sem texto utilizável.")
    if isinstance(content, list):
        chunks = []
        for item in content:
            if isinstance(item, str) and item.strip():
                chunks.append(item.strip())
            elif isinstance(item, dict):
                for key in ("text", "output_text", "content"):
                    if key in item:
                        try:
                            part = extract_text(item[key])
                            if part:
                                chunks.append(part)
                                break
                        except ValueError:
                            continue
        if chunks:
            return "\n".join(chunks).strip()
        raise ValueError("A resposta veio em blocos sem texto utilizável.")
    if content is None:
        raise ValueError("A API devolveu content vazio ou null.")
    raise ValueError(f"Formato de conteúdo não suportado: {type(content).__name__}.")


def parse_json(content):
    text = extract_text(content).lstrip("\ufeff").strip()
    text = re.sub(r"^\s*```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            obj, _ = decoder.raw_decode(text[match.start():])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    raise ValueError("A resposta textual não contém um objeto JSON válido.")


def validate_result(data):
    if not isinstance(data, dict):
        raise ValueError("O JSON devolvido não é um objeto.")
    signal = str(data.get("signal", "")).strip().upper()
    if signal not in {"BUY", "SELL", "AGUARDAR"}:
        raise ValueError("A IA não devolveu BUY, SELL ou AGUARDAR.")
    try:
        confidence = float(data.get("confidence"))
        buy_score = float(data.get("buy_score", 0))
        sell_score = float(data.get("sell_score", 0))
    except (TypeError, ValueError):
        raise ValueError("Confiança ou pontuações BUY/SELL inválidas.")
    if not 0 <= confidence <= 100:
        raise ValueError("A confiança deve estar entre 0 e 100.")
    if not (0 <= buy_score <= 100 and 0 <= sell_score <= 100):
        raise ValueError("As pontuações BUY/SELL devem estar entre 0 e 100.")

    result = {
        "signal": signal, "confidence": round(confidence, 1),
        "buy_score": round(buy_score, 1), "sell_score": round(sell_score, 1),
        "entry": str(data.get("entry") or "").strip(),
        "sl": str(data.get("stop_loss") or data.get("sl") or "").strip(),
        "tp": str(data.get("take_profit") or data.get("tp") or "").strip(),
        "reason": str(data.get("reason") or "").strip()
    }

    # Validação independente: impede que o modelo ignore os limiares pedidos.
    if signal == "BUY" and (buy_score < 65 or buy_score - sell_score < 10):
        raise ValueError("BUY recusado: pontuação abaixo do mínimo ou sem vantagem suficiente.")
    if signal == "SELL" and (sell_score < 65 or sell_score - buy_score < 10):
        raise ValueError("SELL recusado: pontuação abaixo do mínimo ou sem vantagem suficiente.")
    if signal == "AGUARDAR":
        result.update(entry="", sl="", tp="")
        return result
    if not all((result["entry"], result["sl"], result["tp"])):
        raise ValueError("BUY/SELL sem entrada futura, Stop Loss e Take Profit. Sinal recusado.")
    return result


def make_prompt(meta):
    return f"""
És o analista técnico do DONCULLER-TRADE47. Analisa o screenshot e responde em português.
Mercado: {meta['market']} | Ativo: {meta['asset']}
Plataforma: {meta['platform']} | Timeframe: {meta['timeframe']}

MÉTODO:
1. Identifica tendência recente: alta, baixa ou lateral.
2. Avalia estrutura HH/HL ou LH/LL, suportes/resistências e reacção do preço.
3. Avalia velas, rompimento/reteste e momentum.
4. Considera RSI, MACD, médias móveis, Fractals e Zig Zag APENAS se estiverem
   claramente visíveis. Não inventes indicadores nem valores.
5. Em Boom/Crash, não escolhas uma direcção pelo nome do activo nem pela
   expectativa de spike. Usa apenas a evidência visível.
6. Não confundas uma recuperação curta com inversão confirmada.

PONTUAÇÃO EQUILIBRADA:
Avalia BUY e SELL separadamente, sem favorecer AGUARDAR por defeito.
Atribui pontuação de 0 a 100 a cada lado:
- Tendência e estrutura: até 30.
- Zona técnica, suporte/resistência, rompimento/reteste: até 25.
- Velas e momentum: até 25.
- Confluência de indicadores que estejam visíveis: até 20.
Não dês pontos por indicadores ausentes. Pontuação é força da evidência
visual, NÃO probabilidade real de lucro.

DECISÃO:
- BUY se buy_score >= 65 e buy_score exceder sell_score em pelo menos 10,
  com entrada futura condicional, SL e TP coerentes e visíveis.
- SELL se sell_score >= 65 e sell_score exceder buy_score em pelo menos 10,
  com entrada futura condicional, SL e TP coerentes e visíveis.
- AGUARDAR se nenhum lado cumprir esses critérios ou se o gráfico não
  permitir definir níveis com segurança.
- Não escolhas AGUARDAR só porque o preço já se moveu muito: procura uma
  possível entrada futura após pullback, reteste ou quebra confirmada.
  Não persigas o preço.
- A entrada deve indicar uma condição futura objectiva. SL invalida a ideia;
  TP aponta para uma zona técnica seguinte. Não inventes números.
- confidence mede a qualidade da evidência visual, não taxa de acerto.

Responde APENAS com JSON válido:
{{
 "signal":"BUY ou SELL ou AGUARDAR",
 "confidence":0,
 "buy_score":0,
 "sell_score":0,
 "entry":"",
 "stop_loss":"",
 "take_profit":"",
 "reason":""
}}
Em AGUARDAR, entry, stop_loss e take_profit ficam vazios.
Em BUY/SELL, preenche os três com níveis legíveis e fundamentados.
""".strip()


def call_openrouter(image, meta, api_key, model):
    image = ImageOps.exif_transpose(image).convert("RGB")
    image.thumbnail((1600, 1600))
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=85, optimize=True)
    image_b64 = base64.b64encode(buffer.getvalue()).decode("ascii")

    payload = {
        "model": model, "temperature": 0.1, "max_tokens": 1600,
        "reasoning": {"effort": "none", "exclude": True},
        "response_format": {"type": "json_object"},
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": make_prompt(meta)},
                {"type": "image_url", "image_url": {
                    "url": "data:image/jpeg;base64," + image_b64
                }}
            ]
        }]
    }
    headers = {
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
        "HTTP-Referer": "https://doncullertrade47.onrender.com", "X-Title": APP
    }
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=(20, 150))
    except requests.RequestException as exc:
        raise RuntimeError(f"Falha de ligação ao OpenRouter: {exc}") from exc

    if response.status_code == 429:
        raise RuntimeError("Limite OpenRouter atingido (HTTP 429). Aguarda a reposição da quota.")
    if response.status_code in (401, 403):
        raise RuntimeError("Chave OpenRouter recusada. Confirma OPENROUTER_API_KEY no Render.")
    if response.status_code >= 400:
        raise RuntimeError(f"Erro OpenRouter {response.status_code}: {response.text[:900]}")
    try:
        body = response.json()
    except ValueError as exc:
        raise RuntimeError(f"OpenRouter não devolveu JSON: {response.text[:400]}") from exc
    if not isinstance(body, dict):
        raise RuntimeError("Resposta da API em formato inesperado.")
    if body.get("error"):
        raise RuntimeError(f"Erro comunicado pelo modelo: {str(body['error'])[:600]}")
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError(f"OpenRouter não devolveu choices: {str(body)[:600]}")
    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message") or {}
    if not isinstance(message, dict):
        raise RuntimeError("Mensagem do modelo em formato inesperado.")
    if message.get("refusal"):
        raise RuntimeError(f"O modelo recusou a análise: {str(message['refusal'])[:400]}")
    content = message.get("content")
    finish = first.get("finish_reason", "desconhecido")
    if content is None or content == "":
        if message.get("reasoning") or message.get("reasoning_details"):
            raise RuntimeError("O modelo devolveu raciocínio, mas não a resposta final. Verifica a compatibilidade do modelo de visão em OPENROUTER_MODEL.")
        raise RuntimeError(f"O modelo devolveu conteúdo vazio (finish_reason: {finish}).")
    try:
        return validate_result(parse_json(content))
    except ValueError as exc:
        preview = str(content)[:300].replace("\n", " ")
        raise RuntimeError(f"Resposta inválida/incompleta: {exc} (finish_reason: {finish}; início: {preview})") from exc


def show_result(result):
    signal = result["signal"]
    css = {"BUY": "buy", "SELL": "sell", "AGUARDAR": "wait"}[signal]
    st.markdown(
        f'<div class="box"><div class="{css}">{signal} — {result["confidence"]:.1f}%</div></div>',
        unsafe_allow_html=True
    )
    st.caption(f"Força BUY: {result['buy_score']:.0f}/100 | Força SELL: {result['sell_score']:.0f}/100")
    if result["reason"]:
        st.write(result["reason"])
    if signal in ("BUY", "SELL"):
        st.markdown(f"**Entrada futura:** {result['entry']}")
        st.markdown(f"**Stop Loss:** {result['sl']}")
        st.markdown(f"**Take Profit:** {result['tp']}")


db_init()
st.markdown(
    f'<div class="hero"><div class="small">V9.4 · AVALIAÇÃO EQUILIBRADA BUY/SELL</div>'
    f'<h1>🦁 {APP}</h1><span class="small">Análise técnica de gráficos por imagem</span></div>',
    unsafe_allow_html=True
)

with st.sidebar:
    st.subheader("Configuração")
    market = st.selectbox("Mercado", list(MARKETS.keys()))
    asset = st.selectbox("Instrumento", MARKETS[market])
    platform = st.selectbox("Plataforma", PLATFORMS)
    timeframe = st.selectbox("Timeframe", TIMEFRAMES, index=3)
    model = st.text_input("Modelo OpenRouter", MODEL_DEFAULT)
    st.caption("A chave é lida de OPENROUTER_API_KEY nas variáveis de ambiente do Render.")

left, right = st.columns([1.1, 0.9], gap="large")
with left:
    st.subheader("Screenshot do gráfico")
    uploaded = st.file_uploader("Carrega uma imagem", type=["png", "jpg", "jpeg", "webp"], key="chart_upload")
    preview = None
    if uploaded is not None:
        try:
            preview = Image.open(uploaded)
            preview.load()
            st.image(preview, caption="Gráfico carregado", use_container_width=True)
        except (UnidentifiedImageError, OSError):
            st.error("Não foi possível abrir esta imagem. Envia novamente em PNG ou JPG.")
    analyze_button = st.button("🦁 ANALISAR GRÁFICO", use_container_width=True)

with right:
    st.subheader("Resultado")
    if analyze_button:
        api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if preview is None:
            st.warning("Carrega primeiro um screenshot válido.")
        elif not api_key:
            st.error("Falta OPENROUTER_API_KEY nas Environment Variables do Render.")
        elif not model.strip():
            st.error("Indica um modelo OpenRouter.")
        else:
            meta = {"market": market, "asset": asset, "platform": platform, "timeframe": timeframe}
            with st.spinner("A analisar o gráfico..."):
                try:
                    result = call_openrouter(preview, meta, api_key, model.strip())
                    save_result(meta, result)
                    st.session_state["v94_result"] = result
                    st.session_state["v94_meta"] = meta
                except Exception as exc:
                    st.session_state.pop("v94_result", None)
                    st.error(str(exc))
    current_result = st.session_state.get("v94_result")
    if current_result:
        show_result(current_result)
    else:
        st.caption("O resultado aparecerá aqui após a análise.")

st.divider()
st.subheader("Histórico")
with sqlite3.connect(DB_PATH) as conn:
    rows = conn.execute(
        "SELECT created, market, asset, platform, timeframe, signal, confidence "
        "FROM history ORDER BY id DESC LIMIT 50"
    ).fetchall()
if rows:
    st.dataframe([{
        "Data UTC": r[0][:19].replace("T", " "), "Mercado": r[1],
        "Ativo": r[2], "Plataforma": r[3], "Timeframe": r[4],
        "Sinal": r[5], "Confiança": f"{r[6]:.1f}%"
    } for r in rows], use_container_width=True, hide_index=True)
else:
    st.caption("Ainda não existem análises guardadas.")

st.markdown(
    '<div class="small">A confiança e as pontuações são estimativas baseadas na imagem, '
    'não taxas de acerto comprovadas. A aplicação não recebe cotações em tempo real '
    'nem executa ordens. Testa em Demo antes de considerar dinheiro real.</div>',
    unsafe_allow_html=True
)
