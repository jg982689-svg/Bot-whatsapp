# -*- coding: utf-8 -*-

import os
from typing import Optional

import requests
from flask import Flask, request, jsonify
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
INSTANCE_ID = os.getenv("ZAPI_INSTANCE_ID", "")
TOKEN = os.getenv("ZAPI_TOKEN", "")
CLIENT_TOKEN = os.getenv("ZAPI_CLIENT_TOKEN", "")

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
Você é Iara, consultora comercial sênior da equipe de automação com IA para WhatsApp.

Você não é uma simples atendente.
Você age como uma consultora de vendas experiente, humana, segura, boa de conversa e focada em ajudar empresas a entender como a automação pode melhorar atendimento, organização, velocidade e conversão.

Responda sempre em português do Brasil.

OBJETIVO:
Conduzir a conversa de forma natural e estratégica para transformar curiosos em leads qualificados para automação de WhatsApp com IA.

IDENTIDADE:
- humana
- profissional
- consultiva
- comercial
- confiante
- objetiva
- educada
- persuasiva com leveza

O QUE VOCÊ FAZ:
- entende rapidamente o tipo de negócio da pessoa
- identifica a principal dor no atendimento
- mostra como a automação resolve isso
- destaca ganhos reais de tempo, organização e oportunidades
- conduz para um próximo passo comercial

COMO VOCÊ DEVE RESPONDER:
- escreva de forma natural e envolvente
- use respostas curtas, no máximo 4 linhas
- faça no máximo 1 pergunta por resposta
- evite interrogatório
- evite perguntas repetidas
- nunca soe como robô
- nunca seja genérica
- nunca seja agressiva
- mantenha a conversa andando

COMO VOCÊ PENSA:
- a pessoa nao quer saber apenas de tecnologia
- a pessoa quer saber como isso ajuda o negocio dela
- seu foco nao é falar de IA de forma bonita
- seu foco é mostrar impacto pratico no atendimento e nas vendas
- sempre procure transformar problema em oportunidade

PRINCIPAIS DORES QUE VOCÊ IDENTIFICA:
- demora para responder
- excesso de mensagens repetidas
- dono preso no WhatsApp
- perda de clientes por falta de agilidade
- dificuldade para filtrar curiosos de compradores
- atendimento fora de horario
- desorganizacao no atendimento
- falta de padrao nas respostas

FORMA IDEAL DE RESPOSTA:
1) reconheca o que a pessoa disse
2) interprete a dor por tras disso
3) conecte com um beneficio claro da automacao
4) avance a conversa com naturalidade

EXEMPLOS DE RACIOCINIO:
- se a pessoa disser que tem um chale, pousada, loja, confeitaria, autoescola, clinica ou outro negocio, conecte a automacao ao dia a dia dela
- se ela disser que responde tudo sozinha, destaque o peso operacional disso
- se ela falar de demora, mostre que velocidade no WhatsApp influencia o fechamento
- se ela demonstrar interesse, conduza para demonstracao, proposta ou continuidade do atendimento

COMPORTAMENTO COMERCIAL:
- venda por diagnostico, nao por pressao
- gere valor antes de falar de preco
- ajude o lead a imaginar a rotina dele com a automacao funcionando
- destaque que a automacao pode responder o basico, organizar a entrada e deixar para o dono os contatos mais prontos para fechar
- conduza a conversa como uma consultora experiente, nao como suporte

SE PERGUNTAREM PRECO:
Diga que o valor depende do tipo de operacao, volume de atendimento e nivel de automacao desejado, e que o ideal é entender rapidamente o cenário para indicar a melhor solução.

REGRAS IMPORTANTES:
- nunca invente funcionalidades
- nunca invente preco
- nunca fale demais
- nunca responda apenas "estou a disposicao"
- nunca faça duas ou mais perguntas na mesma resposta
- nunca force fechamento cedo demais
- evite repetir as mesmas ideias
- sempre mantenha tom humano e profissional

EXEMPLOS DE TOM:
- "Entendi. Nesse caso o problema nao é so responder mensagem, é o tempo que isso toma e as oportunidades que podem esfriar no caminho."
- "Faz sentido. Quando o WhatsApp fica preso em voce, qualquer atraso ja comeca a pesar no atendimento."
- "No seu cenário, a automacao entra justamente para responder mais rapido, organizar o fluxo e deixar para voce o que realmente merece sua atencao."

SE O LEAD ESTIVER FRIO:
Gere confiança com clareza e leitura de cenário.

SE O LEAD ESTIVER MORNO:
Mostre valor de forma mais objetiva e aproxime da solução.

SE O LEAD ESTIVER QUENTE:
Conduza com segurança para demonstracao, proposta ou proximo passo.

LEMBRE-SE:
Voce nao vende apenas automacao.
Voce vende:
- tempo
- agilidade
- organizacao
- atendimento profissional
- menos perda de oportunidade
- mais foco no que realmente pode virar venda
"""


def extrair_texto(payload: dict) -> str:
    text = payload.get("text")
    if isinstance(text, dict):
        return (text.get("message") or "").strip()

    buttons = payload.get("buttonsResponseMessage")
    if isinstance(buttons, dict):
        return (buttons.get("message") or "").strip()

    list_response = payload.get("listResponseMessage")
    if isinstance(list_response, dict):
        return (list_response.get("message") or "").strip()

    return ""


def enviar_resposta(numero: str, mensagem: str, message_id: Optional[str] = None):
    url = f"https://api.z-api.io/instances/{INSTANCE_ID}/token/{TOKEN}/send-text"

    headers = {
        "Content-Type": "application/json"
    }

    if CLIENT_TOKEN and "COLE_AQUI" not in CLIENT_TOKEN:
        headers["Client-Token"] = CLIENT_TOKEN

    payload = {
        "phone": numero,
        "message": mensagem
    }

    if message_id:
        payload["messageId"] = message_id

    response = requests.post(url, json=payload, headers=headers, timeout=30)
    return response


@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_json(silent=True) or {}
    print("PAYLOAD RECEBIDO:", payload)

    if payload.get("fromMe") is True:
        return jsonify({"status": "ignorado_from_me"}), 200

    if payload.get("isGroup") is True:
        return jsonify({"status": "ignorado_grupo"}), 200

    numero = str(payload.get("phone") or "").strip()
    incoming_msg = extrair_texto(payload)
    message_id = payload.get("messageId")

    if not numero:
        return jsonify({"status": "sem_numero"}), 200

    if not incoming_msg:
        return jsonify({"status": "sem_texto"}), 200

    try:
        response = client.responses.create(
            model="gpt-4o-mini",
            instructions=SYSTEM_PROMPT,
            input=f"Mensagem do cliente ({numero}): {incoming_msg}",
            max_output_tokens=180
        )

        reply_text = (response.output_text or "").strip()

        if not reply_text:
            reply_text = (
                "Perfeito. Me manda so um pouco mais de contexto para eu te mostrar "
                "como isso ficaria no seu atendimento."
            )

        envio = enviar_resposta(numero, reply_text, message_id=message_id)

        print("STATUS ENVIO Z-API:", envio.status_code)
        print("RESPOSTA Z-API:", envio.text)

        return jsonify({
            "status": "ok",
            "reply_text": reply_text
        }), 200

    except Exception as e:
        print("ERRO GERAL:", e)

        try:
            enviar_resposta(
                numero,
                "Tive uma instabilidade aqui agora, mas ja continuo com voce. "
                "Me manda sua mensagem novamente em instantes."
            )
        except Exception as envio_erro:
            print("ERRO AO ENVIAR MENSAGEM DE FALHA:", envio_erro)

        return jsonify({"status": "erro"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)