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
            signal TEXT, confidence REAL, entry TEXT, sl TEXT, tp TEXT,
            result_status TEXT NOT NULL DEFAULT 'PENDENTE',
            closed_at TEXT, result_note TEXT
        )""")
        # Migração segura: preserva o histórico criado nas versões anteriores.
        columns = {row[1] for row in conn.execute("PRAGMA table_info(history)")}
        if "result_status" not in columns:
            conn.execute("ALTER TABLE history ADD COLUMN result_status TEXT NOT NULL DEFAULT 'PENDENTE'")
        if "closed_at" not in columns:
            conn.execute("ALTER TABLE history ADD COLUMN closed_at TEXT")
        if "result_note" not in columns:
            conn.execute("ALTER TABLE history ADD COLUMN result_note TEXT")
        conn.execute("UPDATE history SET result_status='NAO_APLICAVEL' WHERE signal='AGUARDAR'")


def save_result(meta, result):
    status = "PENDENTE" if result["signal"] in ("BUY", "SELL") else "NAO_APLICAVEL"
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""INSERT INTO history
            (created, market, asset, platform, timeframe, signal, confidence, entry, sl, tp, result_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (datetime.now(timezone.utc).isoformat(), meta["market"], meta["asset"],
             meta["platform"], meta["timeframe"], result["signal"], result["confidence"],
             result["entry"], result["sl"], result["tp"], status))


def update_trade_status(trade_id, status, note=""):
    if status not in ("WINNER", "LOSS", "PENDENTE"):
        raise ValueError("Estado de operação inválido.")
    closed_at = datetime.now(timezone.utc).isoformat() if status in ("WINNER", "LOSS") else None
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE history SET result_status=?, closed_at=?, result_note=? WHERE id=? AND signal IN ('BUY','SELL')",
                     (status, closed_at, note.strip(), int(trade_id)))


def get_trade_stats():
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("""SELECT signal,
            SUM(CASE WHEN result_status='WINNER' THEN 1 ELSE 0 END),
            SUM(CASE WHEN result_status='LOSS' THEN 1 ELSE 0 END),
            SUM(CASE WHEN result_status='PENDENTE' THEN 1 ELSE 0 END)
            FROM history WHERE signal IN ('BUY','SELL') GROUP BY signal""").fetchall()
    stats = {side: {"wins": 0, "losses": 0, "pending": 0} for side in ("BUY", "SELL")}
    for side, wins, losses, pending in rows:
        stats[side] = {"wins": wins or 0, "losses": losses or 0, "pending": pending or 0}
    return stats


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
        raise ValueError("O JSON devolvido não é um objecto.")
    if "buy_score" not in data or "sell_score" not in data:
        raise ValueError("O modelo não devolveu as duas pontuações BUY/SELL.")
    try:
        buy_score = float(data["buy_score"])
        sell_score = float(data["sell_score"])
        confidence = float(data.get("confidence", 0))
    except (TypeError, ValueError):
        raise ValueError("Pontuações BUY/SELL ou confiança inválidas.")
    if not (0 <= buy_score <= 100 and 0 <= sell_score <= 100):
        raise ValueError("As pontuações BUY/SELL devem estar entre 0 e 100.")
    if not 0 <= confidence <= 100:
        raise ValueError("A confiança deve estar entre 0 e 100.")
    if buy_score == 0 and sell_score == 0:
        raise ValueError("A análise não produziu pontuações. Verifica o modelo de visão.")

    result = {
        "signal": "AGUARDAR",
        "confidence": round(confidence, 1),
        "buy_score": round(buy_score, 1),
        "sell_score": round(sell_score, 1),
        "entry": str(data.get("entry") or "").strip(),
        "trigger": str(data.get("trigger") or "").strip(),
        "sl": str(data.get("stop_loss") or data.get("sl") or "").strip(),
        "tp": str(data.get("take_profit") or data.get("tp") or "").strip(),
        "invalidation": str(data.get("invalidation") or "").strip(),
        "setup": str(data.get("setup") or "").strip(),
        "reason": str(data.get("reason") or "").strip()
    }

    # A decisão é calculada pela aplicação, não aceite cegamente do modelo.
    minimum_score = 52
    minimum_advantage = 6
    difference = buy_score - sell_score
    if buy_score >= minimum_score and difference >= minimum_advantage:
        candidate = "BUY"
    elif sell_score >= minimum_score and difference <= -minimum_advantage:
        candidate = "SELL"
    else:
        candidate = "AGUARDAR"

    complete_plan = all((result["entry"], result["trigger"], result["sl"],
                         result["tp"], result["invalidation"]))
    if candidate in ("BUY", "SELL") and complete_plan:
        result["signal"] = candidate
    else:
        result.update(signal="AGUARDAR", entry="", trigger="", sl="",
                      tp="", invalidation="")
        if not result["reason"]:
            result["reason"] = (
                "Não existe vantagem técnica suficiente ou falta um plano "
                "de entrada futura com SL e TP verificáveis."
            )
    return result


def make_prompt(meta):
    return f"""
És o analista técnico principal do DONCULLER-TRADE47.
Analisa APENAS o screenshot. Responde em português simples e operacional.
Mercado: {meta['market']} | Activo: {meta['asset']}
Plataforma: {meta['platform']} | Timeframe: {meta['timeframe']}

OBJECTIVO:
Encontrar a melhor oportunidade FUTURA, BUY ou SELL. Compara obrigatoriamente
os dois lados. Não escolhas AGUARDAR por hábito quando existir uma configuração
técnica negociável.

LEITURA:
- HH/HL favorecem BUY; LH/LL favorecem SELL.
- Avalia tendência, pullback, rejeição, rompimento, reteste, zonas, velas e momentum.
- RSI, MACD, médias móveis, Fractals e Zig Zag só contam se estiverem visíveis.
- Não escolhas a direcção pelo nome Boom/Crash/Jump.
- Não retires pontos apenas porque faltam indicadores.
- Não inventes preços, níveis, indicadores ou padrões.

PONTUAÇÃO OBRIGATÓRIA (0–100, separada):
- Estrutura/tendência: até 35.
- Zona, swing e pullback: até 25.
- Velas e momentum: até 25.
- Indicadores visíveis: até 15.
Devolve dois números reais entre 0 e 100; não uses zero/zero por defeito.
Pontuação é força técnica, NÃO percentagem de vitória.

DECISÃO:
- Escolhe BUY se o cenário de alta for superior e tiver plano condicional válido.
- Escolhe SELL se o cenário de baixa for superior e tiver plano condicional válido.
- Não exijas sempre rompimento e reteste simultaneamente.
- Se a tendência estiver esticada, procura entrada futura após pullback/rejeição.
- AGUARDAR apenas se o gráfico estiver lateral/contraditório, ilegível ou
  nenhum lado permitir definir entrada, SL e TP tecnicamente.
- Não inventes sinal só para evitar AGUARDAR.

PLANO PARA BUY/SELL:
trigger = condição objectiva antes da entrada;
entry = preço ou zona de entrada futura;
stop_loss = nível que invalida a ideia, além do swing relevante;
take_profit = próxima zona técnica visível;
invalidation = condição que cancela a configuração.
Usa preços exactos apenas se forem legíveis; caso contrário usa zona visual
inequívoca. Se nem isso for possível, escolhe AGUARDAR.

Responde APENAS com JSON válido:
{{
 "signal":"BUY ou SELL ou AGUARDAR",
 "confidence":0,
 "buy_score":0,
 "sell_score":0,
 "setup":"continuação, pullback ou reversão",
 "trigger":"condição objectiva antes da entrada",
 "entry":"preço ou zona de entrada futura",
 "stop_loss":"nível de SL",
 "take_profit":"nível de TP",
 "invalidation":"condição que cancela a ideia",
 "reason":"justificação curta da direcção escolhida"
}}
Em BUY/SELL, todos os campos do plano devem estar preenchidos.
Em AGUARDAR, os campos do plano ficam vazios.
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
        st.markdown(f"**Configuração:** {result['setup'] or 'Não especificada'}")
        st.markdown(f"**Gatilho de activação:** {result['trigger']}")
        st.markdown(f"**Entrada futura:** {result['entry']}")
        st.markdown(f"**Stop Loss:** {result['sl']}")
        st.markdown(f"**Take Profit:** {result['tp']}")
        st.markdown(f"**Invalidação:** {result['invalidation']}")


db_init()
st.markdown(
    f'<div class="hero"><div class="small">V12.0 · BUY/SELL + CONTROLO DE WINNERS/LOSSES</div>'
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
                    st.session_state["v12_result"] = result
                    st.session_state["v12_meta"] = meta
                except Exception as exc:
                    st.session_state.pop("v12_result", None)
                    st.error(str(exc))
    current_result = st.session_state.get("v12_result")
    if current_result:
        show_result(current_result)
    else:
        st.caption("O resultado aparecerá aqui após a análise.")

st.divider()
st.subheader("📊 Desempenho real — WINNERS e LOSSES")
st.caption("Regista manualmente o resultado de cada sinal depois de a operação terminar. A aplicação não acompanha cotações nem confirma resultados automaticamente.")
stats = get_trade_stats()
all_wins = sum(stats[x]["wins"] for x in ("BUY", "SELL"))
all_losses = sum(stats[x]["losses"] for x in ("BUY", "SELL"))
all_closed = all_wins + all_losses

def show_side_stats(side):
    data = stats[side]
    closed = data["wins"] + data["losses"]
    rate = (data["wins"] / closed * 100) if closed else 0.0
    st.metric(f"{side} — taxa de acerto", f"{rate:.1f}%" if closed else "Sem dados", help="WINNERS ÷ (WINNERS + LOSSES). Sinais pendentes não entram no cálculo.")
    st.caption(f"WINNERS: {data['wins']} · LOSSES: {data['losses']} · Pendentes: {data['pending']}")

c1, c2, c3 = st.columns(3)
with c1:
    show_side_stats("BUY")
with c2:
    show_side_stats("SELL")
with c3:
    overall_rate = (all_wins / all_closed * 100) if all_closed else 0.0
    st.metric("Geral — taxa de acerto", f"{overall_rate:.1f}%" if all_closed else "Sem dados")
    st.caption(f"WINNERS: {all_wins} · LOSSES: {all_losses} · Fechadas: {all_closed}")

st.subheader("Registar resultado de um sinal")
with sqlite3.connect(DB_PATH) as conn:
    pending_rows = conn.execute("""SELECT id, created, signal, asset, timeframe, entry, sl, tp
        FROM history WHERE signal IN ('BUY','SELL') AND result_status='PENDENTE' ORDER BY id DESC""").fetchall()
if pending_rows:
    options = {
        f"#{r[0]} · {r[2]} · {r[3]} · {r[4]} · {r[1][:16].replace('T',' ')}": r
        for r in pending_rows
    }
    with st.form("trade_result_form"):
        chosen_label = st.selectbox("Sinal concluído", list(options.keys()))
        chosen_status = st.radio("Resultado", ["WINNER", "LOSS"], horizontal=True)
        result_note = st.text_input("Nota opcional (ex.: TP atingido / SL atingido)")
        submitted = st.form_submit_button("Guardar resultado", use_container_width=True)
        if submitted:
            update_trade_status(options[chosen_label][0], chosen_status, result_note)
            st.success(f"Resultado do sinal #{options[chosen_label][0]} guardado: {chosen_status}.")
            st.rerun()
else:
    st.info("Não há sinais BUY/SELL pendentes para classificar.")

st.subheader("Histórico de análises e resultados")
with sqlite3.connect(DB_PATH) as conn:
    rows = conn.execute(
        "SELECT id, created, market, asset, platform, timeframe, signal, confidence, result_status, entry, sl, tp "
        "FROM history ORDER BY id DESC LIMIT 100"
    ).fetchall()
if rows:
    history_data = [{
        "ID": r[0], "Data UTC": r[1][:19].replace("T", " "), "Mercado": r[2],
        "Ativo": r[3], "Plataforma": r[4], "Timeframe": r[5],
        "Sinal": r[6], "Força/Confiança": f"{r[7]:.1f}", "Resultado": r[8],
        "Entrada": r[9], "SL": r[10], "TP": r[11]
    } for r in rows]
    st.dataframe(history_data, use_container_width=True, hide_index=True)
    import csv
    from io import StringIO
    csv_buffer = StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=list(history_data[0].keys()))
    writer.writeheader()
    writer.writerows(history_data)
    st.download_button("Descarregar histórico CSV", csv_buffer.getvalue().encode("utf-8-sig"), "donculler_trade47_historico.csv", "text/csv")
else:
    st.caption("Ainda não existem análises guardadas.")

st.markdown(
    '<div class="small">A confiança e as pontuações são estimativas baseadas na imagem, '
    'não taxas de acerto comprovadas. As taxas WINNER/LOSS são calculadas a partir dos resultados que regista manualmente. A aplicação não recebe cotações em tempo real nem executa ordens. Testa em Demo antes de considerar dinheiro real.</div>',
    unsafe_allow_html=True
)
