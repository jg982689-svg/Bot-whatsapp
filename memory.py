# -*- coding: utf-8 -*-

import time

CONVERSAS = {}
ULTIMA_MENSAGEM = {}


def iniciar_conversa(numero: str):
    if numero not in CONVERSAS:
        CONVERSAS[numero] = {
            "historico": [],
            "pendentes": []
        }


def salvar_mensagem_temporaria(numero: str, mensagem: str):
    iniciar_conversa(numero)
    CONVERSAS[numero]["pendentes"].append(mensagem)
    ULTIMA_MENSAGEM[numero] = time.time()


def deve_aguardar_mais(numero: str, tempo_espera: int) -> bool:
    tempo_desde_ultima = time.time() - ULTIMA_MENSAGEM.get(numero, 0)
    return tempo_desde_ultima < tempo_espera


def pegar_mensagens_pendentes(numero: str) -> str:
    iniciar_conversa(numero)

    mensagens = CONVERSAS[numero].get("pendentes", [])

    if not mensagens:
        return ""

    texto_final = "\n".join(mensagens).strip()
    CONVERSAS[numero]["pendentes"] = []

    return texto_final


def montar_contexto(numero: str, nova_mensagem: str) -> str:
    iniciar_conversa(numero)

    historico = CONVERSAS[numero].get("historico", [])
    ultimas = historico[-12:]

    texto_historico = ""

    for item in ultimas:
        papel = item.get("role", "cliente")
        conteudo = item.get("content", "")
        texto_historico += f"{papel}: {conteudo}\n"

    return f"""
Histórico recente:
{texto_historico}

Nova mensagem do cliente:
{nova_mensagem}
"""


def salvar_no_historico(numero: str, papel: str, conteudo: str):
    iniciar_conversa(numero)

    CONVERSAS[numero]["historico"].append({
        "role": papel,
        "content": conteudo
    })

    # evita memória infinita
    CONVERSAS[numero]["historico"] = CONVERSAS[numero]["historico"][-30:]