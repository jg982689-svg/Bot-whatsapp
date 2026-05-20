# -*- coding: utf-8 -*-

import os
import tempfile
import requests
from openai import OpenAI


def transcrever_audio(
    audio_url: str,
    openai_api_key: str,
    client_token: str = ""
) -> str:
    """
    Baixa o áudio recebido pelo WhatsApp/Z-API,
    envia para a OpenAI transcrever
    e devolve o texto.
    """

    if not audio_url:
        return ""

    headers = {}

    if client_token and "COLE_AQUI" not in client_token:
        headers["Client-Token"] = client_token

    resposta = requests.get(audio_url, headers=headers, timeout=40)
    resposta.raise_for_status()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as arquivo:
        arquivo.write(resposta.content)
        caminho_audio = arquivo.name

    try:
        client = OpenAI(api_key=openai_api_key)

        with open(caminho_audio, "rb") as audio_file:
            transcricao = client.audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",
                file=audio_file,
                language="pt"
            )

        return (transcricao.text or "").strip()

    finally:
        try:
            os.remove(caminho_audio)
        except Exception:
            pass