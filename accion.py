"""
Hook PreToolUse - anuncia en voz alta la acción que Claude va a hacer.
"""
import sys
import json
import os

COLA = "c:/Proyectos/Lector/tts_cola.txt"

MENSAJES = {
    "Read":       "Leyendo archivo...",
    "Edit":       "Modificando código...",
    "Write":      "Escribiendo archivo...",
    "Bash":       "Ejecutando comando...",
    "Glob":       "Buscando archivos...",
    "Grep":       "Buscando en el código...",
    "Agent":      "Analizando...",
    "WebSearch":  "Buscando en internet...",
    "WebFetch":   "Consultando página web...",
    "TodoWrite":  "Actualizando tareas...",
}

if __name__ == "__main__":
    try:
        data = json.loads(sys.stdin.read())
        tool = data.get("tool_name", "")
        mensaje = MENSAJES.get(tool, "")

        if mensaje:
            # Espera que el panel no esté reproduciendo antes de escribir
            with open(COLA, "w", encoding="utf-8") as f:
                f.write(mensaje)
    except Exception as e:
        sys.stderr.write(f"Error accion.py: {e}\n")
