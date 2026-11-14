# DONCULLER-TRADE47 V6

AI Trading Chart Analyzer — análise técnica de gráficos.

## Instalação

1. Instalar as dependências:

   pip install -r requirements.txt

2. Iniciar a aplicação:

   streamlit run app.py

## Configuração no Render

Adicionar a variável secreta:

OPENROUTER_API_KEY

A chave deve ser criada na conta OpenRouter e guardada nas Environment Variables do Render.

O modelo padrão é:

google/gemma-4-26b-a4b-it:free

O modelo pode ser alterado na barra lateral da aplicação.

## Funcionalidades

- Análise visual de screenshots.
- Comparação dos cenários BUY e SELL.
- Decisão BUY, SELL ou AGUARDAR.
- Zona de entrada e condição de ativação.
- Stop Loss e Take Profit 1 e 2.
- Análise de tendência e estrutura de mercado.
- Cálculo de EMA 20 e EMA 50.
- Cálculo de RSI 14.
- Cálculo de MACD.
- Cálculo de ATR 14.
- Identificação de fractais confirmados.
- Importação opcional de dados OHLC em CSV.

## Formato do CSV

O ficheiro deve conter as colunas:

- Open
- High
- Low
- Close

A aplicação utiliza até às últimas 500 velas e exige pelo menos 35 velas válidas.

## Limitações importantes

A aplicação não executa ordens e não recebe cotações em tempo real.

A análise por screenshot depende da qualidade e legibilidade da imagem.

Os indicadores são calculados a partir do CSV quando este é fornecido. Sem CSV, a análise depende da leitura visual do gráfico.

Não existe garantia de 75% ou 100% de acerto. Os resultados devem ser avaliados em conta Demo antes de qualquer utilização com dinheiro real.
