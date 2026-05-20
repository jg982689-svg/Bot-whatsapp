# -*- coding: utf-8 -*-

import os
import time
import threading
from typing import Optional

import requests
from flask import Flask, request, jsonify
from openai import OpenAI
from dotenv import load_dotenv

from audio_utils import transcrever_audio
from iara_prompt import SYSTEM_PROMPT_IARA
from memory import (
    salvar_mensagem_temporaria,
    deve_aguardar_mais,
    pegar_mensagens_pendentes,
    montar_contexto,
    salvar_no_historico
)

load_dotenv()

app = Flask(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
INSTANCE_ID = os.getenv("ZAPI_INSTANCE_ID", "")
TOKEN = os.getenv("ZAPI_TOKEN", "")
CLIENT_TOKEN = os.getenv("ZAPI_CLIENT_TOKEN", "")

client = OpenAI(api_key=OPENAI_API_KEY)

TEMPO_ESPERA_SEGUNDOS = 7
MENSAGENS_PROCESSADAS = set()
TIMERS_RESPOSTA = {}
LOCK = threading.Lock()

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


def extrair_url_audio(payload: dict) -> str:
    audio = payload.get("audio")
    if isinstance(audio, dict):
        return (
            audio.get("audioUrl")
            or audio.get("url")
            or audio.get("mediaUrl")
            or ""
        ).strip()

    audio_msg = payload.get("audioMessage")
    if isinstance(audio_msg, dict):
        return (
            audio_msg.get("audioUrl")
            or audio_msg.get("url")
            or audio_msg.get("mediaUrl")
            or ""
        ).strip()

    return (
        payload.get("audioUrl")
        or payload.get("mediaUrl")
        or payload.get("url")
        or ""
    ).strip()


def enviar_resposta(numero: str, mensagem: str, message_id: Optional[str] = None):
    url = f"https://api.z-api.io/instances/{INSTANCE_ID}/token/{TOKEN}/send-text"

    headers = {"Content-Type": "application/json"}

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


def gerar_resposta_iara(numero: str, mensagem_cliente: str) -> str:
    contexto = montar_contexto(numero, mensagem_cliente)

    response = client.responses.create(
        model="gpt-4o-mini",
        instructions=SYSTEM_PROMPT_IARA,
        input=contexto,
        max_output_tokens=220
    )

    resposta = (response.output_text or "").strip()

    if not resposta:
        resposta = "Perfeito 😊 Me confirma só mais um detalhe para eu te ajudar certinho?"

    salvar_no_historico(numero, "cliente", mensagem_cliente)
    salvar_no_historico(numero, "Iara", resposta)

    return resposta

def processar_resposta_depois(numero: str, message_id: Optional[str] = None):
    try:
        mensagem_final = pegar_mensagens_pendentes(numero)

        if not mensagem_final:
            print("Sem mensagens pendentes para:", numero)
            return

        reply_text = gerar_resposta_iara(numero, mensagem_final)

        envio = enviar_resposta(numero, reply_text, message_id=message_id)

        print("STATUS ENVIO Z-API:", envio.status_code)
        print("RESPOSTA Z-API:", envio.text)

    except Exception as e:
        print("ERRO AO PROCESSAR RESPOSTA:", e)

        try:
            enviar_resposta(
                numero,
                "Tive uma instabilidade aqui agora, mas já continuo com você. Pode me mandar sua mensagem novamente?"
            )
        except Exception as envio_erro:
            print("ERRO AO ENVIAR MENSAGEM DE FALHA:", envio_erro)

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_json(silent=True) or {}
    print("PAYLOAD RECEBIDO:", payload)

    if payload.get("fromMe") is True:
        return jsonify({"status": "ignorado_from_me"}), 200

    if payload.get("isGroup") is True:
        return jsonify({"status": "ignorado_grupo"}), 200

    numero = str(payload.get("phone") or "").strip()
    message_id = payload.get("messageId")

    if message_id and message_id in MENSAGENS_PROCESSADAS:
        return jsonify({"status": "mensagem_ja_processada"}), 200

    if message_id:
        MENSAGENS_PROCESSADAS.add(message_id)

    if not numero:
        return jsonify({"status": "sem_numero"}), 200

    incoming_msg = extrair_texto(payload)

    if not incoming_msg:
        audio_url = extrair_url_audio(payload)

        if audio_url:
            try:
                incoming_msg = transcrever_audio(
                    audio_url=audio_url,
                    openai_api_key=OPENAI_API_KEY,
                    client_token=CLIENT_TOKEN
                )
                print("ÁUDIO TRANSCRITO:", incoming_msg)
            except Exception as erro_audio:
                print("ERRO AO TRANSCREVER ÁUDIO:", erro_audio)
                enviar_resposta(
                    numero,
                    "Não consegui entender esse áudio agora 😕 Pode me mandar por texto, por favor?",
                    message_id=message_id
                )
                return jsonify({"status": "erro_audio"}), 200

    if not incoming_msg:
        return jsonify({"status": "sem_texto_ou_audio"}), 200

        
    try:
        salvar_mensagem_temporaria(numero, incoming_msg)

        with LOCK:
            timer_antigo = TIMERS_RESPOSTA.get(numero)

            if timer_antigo:
                timer_antigo.cancel()

            novo_timer = threading.Timer(
                TEMPO_ESPERA_SEGUNDOS,
                processar_resposta_depois,
                args=[numero, message_id]
            )

            TIMERS_RESPOSTA[numero] = novo_timer
            novo_timer.start()

        return jsonify({
            "status": "mensagem_recebida_aguardando_cliente_parar"
        }), 200

    except Exception as e:
        print("ERRO GERAL:", e)

        try:
            enviar_resposta(
                numero,
                "Tive uma instabilidade aqui agora, mas já continuo com você. Pode me mandar sua mensagem novamente?"
            )
        except Exception as envio_erro:
            print("ERRO AO ENVIAR MENSAGEM DE FALHA:", envio_erro)

        return jsonify({"status": "erro"}), 200            
        print("ERRO GERAL:", e)

        try:
            enviar_resposta(
                numero,
                "Tive uma instabilidade aqui agora, mas já continuo com você. Pode me mandar sua mensagem novamente?"
            )
        except Exception as envio_erro:
            print("ERRO AO ENVIAR MENSAGEM DE FALHA:", envio_erro)

        return jsonify({"status": "erro"}), 200
@app.route("/", methods=["GET"])
def home():
    return "Iara - WhatsApp IA da Tudo Começa Na Farinha rodando ✅"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)