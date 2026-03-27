"""
Hook para Claude Code - lee en voz alta la respuesta del asistente.
"""
import sys
import json
import os

COLA = "c:/Proyectos/Lector/tts_cola.txt"

def extraer_texto_completo(transcript_path):
    if not transcript_path or not os.path.exists(transcript_path):
        return ""

    lineas = []
    with open(transcript_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    lineas.append(json.loads(line))
                except Exception:
                    pass

    # Encuentra el ultimo mensaje de usuario real (no tool_result)
    ultimo_usuario = -1
    for i, entrada in enumerate(lineas):
        if entrada.get("type") == "user":
            content = entrada.get("message", {}).get("content", [])
            if isinstance(content, list):
                # Solo cuenta si tiene texto, no tool_result
                if any(b.get("type") == "text" for b in content):
                    ultimo_usuario = i
            elif isinstance(content, str):
                ultimo_usuario = i

    if ultimo_usuario == -1:
        return ""

    # Recoge todo el texto de los mensajes assistant DESPUÉS del ultimo usuario
    textos = []
    for entrada in lineas[ultimo_usuario:]:
        if entrada.get("type") == "assistant":
            content = entrada.get("message", {}).get("content", [])
            if isinstance(content, list):
                for bloque in content:
                    if bloque.get("type") == "text":
                        t = bloque.get("text", "").strip()
                        if t:
                            textos.append(t)

    return " ".join(textos)

if __name__ == "__main__":
    try:
        data = json.loads(sys.stdin.read())
        transcript_path = data.get("transcript_path", "")

        texto = extraer_texto_completo(transcript_path)

        if not texto:
            texto = data.get("last_assistant_message", "").strip()

        if texto:
            with open(COLA, "w", encoding="utf-8") as f:
                f.write(texto)
    except Exception as e:
        sys.stderr.write(f"Error leer.py: {e}\n")
