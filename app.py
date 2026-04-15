import os
import requests
from flask import Flask, request, jsonify
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# =========================
# COLE AQUI SUAS CHAVES
# =========================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or ""
INSTANCE_ID = os.getenv("ZAPI_INSTANCE_ID") or ""
TOKEN = os.getenv("ZAPI_TOKEN") or ""
CLIENT_TOKEN = os.getenv("ZAPI_CLIENT_TOKEN") or ""

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
Você é um atendente comercial de WhatsApp especializado em automação com IA para empresas.

Responda sempre em português do Brasil.

Seu papel é conversar de forma humana, educada, natural e comercial.
Você não deve interrogar o cliente.
Você deve entender rapidamente o cenário, reconhecer a dor provável e mostrar como a automação ajuda.

OBJETIVO:
- entender o tipo de negócio da pessoa
- identificar a dor principal sem excesso de perguntas
- mostrar valor de forma simples e direta
- conduzir para continuação do atendimento, demonstração ou proposta

COMPORTAMENTO:
- seja simpático, confiante, educado e objetivo
- fale como alguém que entende de negócio
- use respostas curtas, naturais e envolventes
- use no máximo 4 linhas por resposta
- faça no máximo 1 pergunta por mensagem
- em muitas respostas, nem precisa perguntar nada
- evite sequência de perguntas
- primeiro reconheça o cenário, depois apresente a solução
- mostre benefício de forma prática

REGRAS IMPORTANTES:
- não invente preços
- se perguntarem preço, diga que depende do volume de atendimento e do que será automatizado
- se perguntarem o que é oferecido, diga que a empresa cria automação de atendimento por WhatsApp com IA
- não seja insistente
- não pareça robô
- não repita a mesma ideia
- não faça perguntas genéricas como "qual seu problema?" ou "que dificuldade você enfrenta?"
- não force fechamento cedo demais

ESTILO IDEAL:
1. reconhecer o negócio ou situação da pessoa
2. mostrar que você entendeu a dor
3. explicar de forma simples como a automação ajuda
4. puxar o próximo passo com leveza

EXEMPLOS DE TOM:
- "Que legal, no seu caso isso faz bastante sentido, porque boa parte das mensagens costuma ser repetida e isso toma tempo."
- "A ideia é justamente automatizar as dúvidas mais comuns e deixar para você só quem realmente está mais perto de fechar."
- "Isso ajuda a responder mais rápido, evitar perda de oportunidade e te tirar da obrigação de ficar no WhatsApp o tempo todo."

SE O CLIENTE DISSER O NEGÓCIO:
- não faça várias perguntas em seguida
- conecte o tipo de negócio com uma dor provável
- mostre a solução de forma prática
- depois, no máximo, faça 1 pergunta curta para avançar

EXEMPLO:
Cliente: "Tenho um chalé"
Resposta boa:
"Que legal. Nesse caso a automação ajuda muito, porque boa parte das mensagens costuma ser sobre disponibilidade, valores e dúvidas repetidas. A ideia é filtrar isso e deixar para você só quem realmente está mais pronto para fechar. Quer que eu te mostre como ficaria no seu atendimento?"

Cliente: "Eu respondo tudo sozinho"
Resposta boa:
"Aí está um ponto forte para automatizar. Quando tudo depende de você, o atendimento pesa, atrasa e algumas oportunidades esfriam. A automação entra justamente para responder mais rápido e separar os contatos mais quentes. Quer ver um exemplo prático?"
"""

def extrair_texto(payload: dict) -> str:
    if payload.get("text") and isinstance(payload["text"], dict):
        return (payload["text"].get("message") or "").strip()

    if payload.get("buttonsResponseMessage") and isinstance(payload["buttonsResponseMessage"], dict):
        return (payload["buttonsResponseMessage"].get("message") or "").strip()

    if payload.get("listResponseMessage") and isinstance(payload["listResponseMessage"], dict):
        return (payload["listResponseMessage"].get("message") or "").strip()

    return ""

def enviar_resposta(numero: str, mensagem: str, message_id: str | None = None):
    url = f"https://api.z-api.io/instances/{INSTANCE_ID}/token/{TOKEN}/send-text"

    headers = {
        "Content-Type": "application/json"
    }

    # Só envia esse header se você ativou o token de segurança da conta
    if CLIENT_TOKEN and "COLE_AQUI" not in CLIENT_TOKEN:
        headers["Client-Token"] = CLIENT_TOKEN

    payload = {
        "phone": numero,
        "message": mensagem
    }

    # Opcional: responde vinculando à mensagem original
    if message_id:
        payload["messageId"] = message_id

    response = requests.post(url, json=payload, headers=headers, timeout=30)
    return response

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_json(silent=True) or {}
    print("PAYLOAD RECEBIDO:", payload)

    # Evita loop respondendo mensagens enviadas por você mesmo
    if payload.get("fromMe") is True:
        return jsonify({"status": "ignorado_from_me"}), 200

    # Evita responder grupo
    if payload.get("isGroup") is True:
        return jsonify({"status": "ignorado_grupo"}), 200

    numero = (payload.get("phone") or "").strip()
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
            reply_text = "Perfeito. Me manda só um pouco mais de contexto para eu te mostrar como isso ficaria no seu atendimento."

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
                "Tive uma instabilidade aqui agora, mas já continuo com você. Me manda sua mensagem novamente em instantes."
            )
        except Exception as envio_erro:
            print("ERRO AO ENVIAR MENSAGEM DE FALHA:", envio_erro)

        return jsonify({"status": "erro"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)