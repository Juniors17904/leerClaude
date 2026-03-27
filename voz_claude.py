import tkinter as tk
from tkinter import scrolledtext
import threading
import asyncio
import os
import tempfile
import speech_recognition as sr
import edge_tts
import pygame
import anthropic
import time

# ── Configuración ──────────────────────────────────────────────────────────────
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
VOZ_ES  = "es-MX-DaliaNeural"
# ───────────────────────────────────────────────────────────────────────────────

class VozClaude:
    def __init__(self, root):
        self.root = root
        self.client = anthropic.Anthropic(api_key=API_KEY)
        self.historial = []
        self.hablando = False
        self.modo_voz = True
        self.activo = True   # escucha continua

        pygame.mixer.init()
        self._build_ui()

        # Inicia el ciclo de escucha en hilo separado
        threading.Thread(target=self._ciclo_escucha, daemon=True).start()
        self._log("Escuchando... habla cuando quieras.", "sistema")

    # ── UI ─────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.root.title("Voz Claude")
        self.root.geometry("380x500")
        self.root.resizable(True, True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.95)
        self.root.configure(bg="#1a1a2e")
        self.root.protocol("WM_DELETE_WINDOW", self._cerrar)

        self.lbl_estado = tk.Label(
            self.root, text="🎙️ ESCUCHANDO", bg="#1a1a2e", fg="#00ff88",
            font=("Consolas", 10, "bold"), anchor="w", padx=10
        )
        self.lbl_estado.pack(fill="x", pady=(8, 0))

        self.chat = scrolledtext.ScrolledText(
            self.root, wrap=tk.WORD, bg="#0d0d1a", fg="#e0e0e0",
            font=("Consolas", 10), borderwidth=0, padx=8, pady=8,
            state="disabled"
        )
        self.chat.pack(fill="both", expand=True, padx=8, pady=6)
        self.chat.tag_config("tu",      foreground="#64b5f6", font=("Consolas", 10, "bold"))
        self.chat.tag_config("claude",  foreground="#a5d6a7", font=("Consolas", 10))
        self.chat.tag_config("sistema", foreground="#ffcc80", font=("Consolas", 9, "italic"))

        self.btn_voz = tk.Button(
            self.root, text="🔊 Voz ON  —  clic para apagar",
            command=self._toggle_voz,
            bg="#2e7d32", fg="white", font=("Consolas", 9),
            relief="flat", pady=8, cursor="hand2"
        )
        self.btn_voz.pack(fill="x", padx=8, pady=(0, 8))

    # ── Toggle voz ─────────────────────────────────────────────────────────────
    def _toggle_voz(self):
        self.modo_voz = not self.modo_voz
        if self.modo_voz:
            self.btn_voz.config(text="🔊 Voz ON  —  clic para apagar", bg="#2e7d32")
        else:
            self.btn_voz.config(text="🔇 Voz OFF —  clic para encender", bg="#555")

    # ── Ciclo de escucha continua ───────────────────────────────────────────────
    def _ciclo_escucha(self):
        rec = sr.Recognizer()
        rec.pause_threshold = 1.0
        rec.energy_threshold = 300

        with sr.Microphone() as mic:
            rec.adjust_for_ambient_noise(mic, duration=1)
            while self.activo:
                # Si Claude está hablando, espera
                if self.hablando:
                    time.sleep(0.2)
                    continue

                self.root.after(0, lambda: self.lbl_estado.config(
                    text="🎙️ ESCUCHANDO", fg="#00ff88"))
                try:
                    audio = rec.listen(mic, timeout=None, phrase_time_limit=30)
                    self.root.after(0, lambda: self.lbl_estado.config(
                        text="⏳ PROCESANDO...", fg="#ffcc80"))

                    texto = rec.recognize_google(audio, language="es-ES")
                    self.root.after(0, lambda t=texto: self._procesar(t))

                except sr.UnknownValueError:
                    pass  # no entendió, sigue escuchando
                except Exception:
                    time.sleep(0.5)

    # ── Enviar a Claude ─────────────────────────────────────────────────────────
    def _procesar(self, texto):
        self._log(f"Tú: {texto}", "tu")
        threading.Thread(target=self._llamar_claude, args=(texto,), daemon=True).start()

    def _llamar_claude(self, texto):
        self.root.after(0, lambda: self.lbl_estado.config(
            text="🤔 PENSANDO...", fg="#ce93d8"))

        self.historial.append({"role": "user", "content": texto})
        try:
            resp = self.client.messages.create(
                model="claude-opus-4-6",
                max_tokens=1024,
                system="Eres un asistente útil. Responde de forma concisa y natural para ser leído en voz alta.",
                messages=self.historial
            )
            respuesta = resp.content[0].text
            self.historial.append({"role": "assistant", "content": respuesta})
            self.root.after(0, lambda r=respuesta: self._log(f"Claude: {r}", "claude"))

            if self.modo_voz:
                threading.Thread(target=self._hablar_tts, args=(respuesta,), daemon=True).start()

        except Exception as ex:
            self.root.after(0, lambda: self._log(f"Error: {ex}", "sistema"))

    # ── TTS ────────────────────────────────────────────────────────────────────
    def _hablar_tts(self, texto):
        self.hablando = True
        self.root.after(0, lambda: self.lbl_estado.config(
            text="🔊 HABLANDO...", fg="#ce93d8"))
        try:
            tmp = tempfile.mktemp(suffix=".mp3")
            asyncio.run(self._generar_audio(texto, tmp))
            pygame.mixer.music.load(tmp)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            os.remove(tmp)
        except Exception as ex:
            self.root.after(0, lambda: self._log(f"Error TTS: {ex}", "sistema"))
        self.hablando = False

    async def _generar_audio(self, texto, ruta):
        await edge_tts.Communicate(texto, VOZ_ES).save(ruta)

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _log(self, texto, tag="sistema"):
        self.chat.config(state="normal")
        self.chat.insert(tk.END, texto + "\n\n", tag)
        self.chat.see(tk.END)
        self.chat.config(state="disabled")

    def _cerrar(self):
        self.activo = False
        self.root.destroy()


# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: Falta ANTHROPIC_API_KEY")
        print("Ejecútalo así:  set ANTHROPIC_API_KEY=sk-ant-...  &&  python voz_claude.py")
        input("Enter para salir...")
        exit(1)

    root = tk.Tk()
    app = VozClaude(root)
    root.mainloop()
