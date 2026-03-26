"""
Hook para Claude Code - lee en voz alta la respuesta del asistente.
Se ejecuta automaticamente cuando Claude termina de responder.
"""
import sys
import json
import asyncio
import os
import tempfile
import pygame
import time
import edge_tts

VOZ = "es-MX-DaliaNeural"

async def generar_audio(texto, ruta):
    await edge_tts.Communicate(texto, VOZ).save(ruta)

def hablar(texto):
    if not texto.strip():
        return
    pygame.mixer.init()
    tmp = tempfile.mktemp(suffix=".mp3")
    asyncio.run(generar_audio(texto, tmp))
    pygame.mixer.music.load(tmp)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        time.sleep(0.1)
    pygame.mixer.music.stop()
    pygame.mixer.quit()
    os.remove(tmp)

COLA = "c:/Proyectos/Lector/tts_cola.txt"

LOG = "c:/Proyectos/Lector/hook_debug.txt"

if __name__ == "__main__":
    try:
        raw = sys.stdin.read()
        # Guarda lo que recibe para debug
        with open(LOG, "w", encoding="utf-8") as f:
            f.write(raw)
        data = json.loads(raw)
        texto = data.get("last_assistant_message", "").strip()
        if texto:
            with open(COLA, "w", encoding="utf-8") as f:
                f.write(texto)
    except Exception as e:
        sys.stderr.write(f"Error leer.py: {e}\n")
