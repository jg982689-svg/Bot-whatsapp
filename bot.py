from flask import Flask, request
import requests

app = Flask(__name__)

# DADOS Z-API
ZAPI_INSTANCE = "SEU_ID"
ZAPI_TOKEN = "SEU_TOKEN"

# OPENAI
OPENAI_KEY = "SUA_KEY"

def perguntar_ia(mensagem):
    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENAI_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "system",
                "content": "Você é atendente de um chalé, responde de forma simpática, objetiva e sempre tenta levar o cliente a fazer uma reserva."
            },
            {
                "role": "user",
                "content": mensagem
            }
        ]
    }

    response = requests.post(url, headers=headers, json=data)
    return response.json()['choices'][0]['message']['content']


def enviar_mensagem(numero, texto):
    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"

    payload = {
        "phone": numero,
        "message": texto
    }

    requests.post(url, json=payload)


@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json

    try:
        mensagem = data['text']['message']
        numero = data['phone']

        resposta = perguntar_ia(mensagem)
        enviar_mensagem(numero, resposta)

    except Exception as e:
        print("Erro:", e)

    return "ok"


if __name__ == "__main__":
    app.run(port=3000)