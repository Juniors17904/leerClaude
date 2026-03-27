"""
Panel flotante de control de voz para Claude Code en VSCode.
Siempre encima de todo. Ejecutar: python panel.py
"""
import tkinter as tk
from tkinter import scrolledtext
import threading
import asyncio
import os
import tempfile
import time
import speech_recognition as sr
import edge_tts
import pygame
import pyautogui
import pygetwindow as gw

VOZ = "es-MX-DaliaNeural"

class Panel:
    def __init__(self, root):
        self.root = root
        self.mic_activo = False
        self.hablando = False
        self.tts_activo = True
        self.escucha_auto = False
        self.cancelar_mensaje = False

        pygame.mixer.init()
        self._build_ui()
        # Limpia cola TTS de sesión anterior
        cola = "c:/Proyectos/Lector/tts_cola.txt"
        if os.path.exists(cola):
            os.remove(cola)
        self._log("Sistema listo", "ok")

        # Inicia escucha automáticamente
        self.mic_activo = True
        self.btn_mic.config(text="⏹  Parar mic", bg="#b91c1c")
        threading.Thread(target=self._ciclo_escucha, daemon=True).start()

        # Monitor de cola TTS
        threading.Thread(target=self._monitor_tts, daemon=True).start()

    # ── UI ─────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.root.title("")
        self.root.geometry("320x280")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.95)
        self.root.overrideredirect(True)
        self.root.configure(bg="#000000")

        # Barra título / drag
        barra = tk.Frame(self.root, bg="#111111", height=24, cursor="fleur")
        barra.pack(fill="x")
        barra.bind("<ButtonPress-1>", self._drag_start)
        barra.bind("<B1-Motion>",     self._drag_move)

        tk.Label(barra, text="⬡ Voz Claude", bg="#111111", fg="#9ca3af",
                 font=("Consolas", 8)).pack(side="left", padx=8)
        tk.Button(barra, text="✕", command=self.root.destroy,
                  bg="#111111", fg="#6b7280", font=("Consolas", 9),
                  relief="flat", bd=0, cursor="hand2",
                  activebackground="#ef4444", activeforeground="white"
                  ).pack(side="right", padx=6)

        # Estado grande
        self.lbl_estado = tk.Label(
            self.root, text="● LISTO", bg="#000000", fg="#10b981",
            font=("Consolas", 10, "bold"), anchor="w", padx=10
        )
        self.lbl_estado.pack(fill="x", pady=(6, 2))

        # Log de actividad
        self.log = scrolledtext.ScrolledText(
            self.root, height=9, wrap=tk.WORD,
            bg="#050505", fg="#e5e7eb",
            font=("Consolas", 8), borderwidth=0,
            padx=6, pady=4, state="disabled"
        )
        self.log.pack(fill="both", expand=True, padx=6, pady=4)
        self.log.tag_config("ok",      foreground="#10b981")
        self.log.tag_config("voz",     foreground="#f59e0b", font=("Consolas", 8, "bold"))
        self.log.tag_config("accion",  foreground="#818cf8")
        self.log.tag_config("error",   foreground="#ef4444")
        self.log.tag_config("claude",  foreground="#6ee7b7")

        # Botones
        frame = tk.Frame(self.root, bg="#000000")
        frame.pack(fill="x", padx=6, pady=(0, 6))

        self.btn_mic = tk.Button(
            frame, text="🎙️  Hablar", command=self._toggle_mic,
            bg="#1d4ed8", fg="white", font=("Consolas", 9, "bold"),
            relief="flat", pady=5, cursor="hand2",
            activebackground="#2563eb"
        )
        self.btn_mic.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_tts = tk.Button(
            frame, text="🔊 Voz ON", command=self._toggle_tts,
            bg="#065f46", fg="white", font=("Consolas", 9, "bold"),
            relief="flat", pady=5, cursor="hand2",
            activebackground="#047857"
        )
        self.btn_tts.pack(side="left", fill="x", expand=True)

    # ── Drag ───────────────────────────────────────────────────────────────────
    def _drag_start(self, e):
        self._x, self._y = e.x, e.y

    def _drag_move(self, e):
        x = self.root.winfo_x() + e.x - self._x
        y = self.root.winfo_y() + e.y - self._y
        self.root.geometry(f"+{x}+{y}")

    # ── Log ────────────────────────────────────────────────────────────────────
    def _log(self, texto, tag="ok"):
        def _write():
            self.log.config(state="normal")
            self.log.insert(tk.END, f"{texto}\n", tag)
            self.log.see(tk.END)
            self.log.config(state="disabled")
        self.root.after(0, _write)

    def _set_estado(self, texto, color):
        self.root.after(0, lambda: self.lbl_estado.config(text=texto, fg=color))

    # ── Toggle mic ─────────────────────────────────────────────────────────────
    def _toggle_mic(self):
        if not self.mic_activo:
            self.mic_activo = True
            self.cancelar_mensaje = False
            self.btn_mic.config(text="⏹  Cancelar", bg="#b91c1c")
            threading.Thread(target=self._ciclo_escucha, daemon=True).start()
        else:
            # Solo cancela el mensaje actual, no detiene el mic
            self.cancelar_mensaje = True
            self.escucha_auto = False
            self._log("Cancelado — di 'activar comando'", "accion")

    # ── Toggle TTS ─────────────────────────────────────────────────────────────
    def _toggle_tts(self):
        self.tts_activo = not self.tts_activo
        if self.tts_activo:
            self.btn_tts.config(text="🔊 Voz ON",  bg="#065f46")
            self._log("Voz activada", "ok")
        else:
            self.btn_tts.config(text="🔇 Voz OFF", bg="#374151")
            self._log("Voz desactivada", "accion")
            pygame.mixer.music.stop()

    # ── Ciclo de escucha ────────────────────────────────────────────────────────
    def _ciclo_escucha(self):
        self._log("Di 'activar comando' para hablar", "ok")
        pulso = ["👂 .", "👂 ..", "👂 ..."]
        pi = 0

        rec = sr.Recognizer()
        rec.energy_threshold = 300
        rec.dynamic_energy_threshold = False

        with sr.Microphone() as source:
            rec.adjust_for_ambient_noise(source, duration=1)
            self._log("Micrófono listo — di 'activar comando'", "ok")

            while self.mic_activo:
                # Si Claude acaba de hablar, activa directo sin palabra clave
                if self.escucha_auto:
                    self.escucha_auto = False
                    activado = True
                else:
                    activado = False
                    rec.pause_threshold = 0.6
                    self._set_estado(f"{pulso[pi % 3]}  di 'activar comando'", "#4b5563")
                    pi += 1

                    try:
                        audio = rec.listen(source, timeout=1, phrase_time_limit=4)
                    except sr.WaitTimeoutError:
                        continue

                    try:
                        cmd = rec.recognize_google(audio, language="es-ES").lower()
                        self._log(f'👂 oí: "{cmd}"', "accion")
                    except (sr.UnknownValueError, Exception):
                        continue

                    if "cancelar" in cmd:
                        self.hablando = False
                        self.escucha_auto = False
                        self.cancelar_mensaje = True
                        pygame.mixer.music.stop()
                        self._log("⏹ Cancelado", "error")
                        self._set_estado("👂  di 'activar comando'", "#4b5563")
                        continue

                    if any(p in cmd for p in ["activar comando", "activar komando", "activar comand", "activar coman"]):
                        if self.hablando:
                            self.hablando = False
                            pygame.mixer.music.stop()
                        activado = True

                if activado:
                    threading.Thread(target=self._pitido, daemon=True).start()
                    self._log("✓ Activado — habla ahora", "ok")
                    self._set_estado("🎙️  ESCUCHANDO...", "#f59e0b")

                    self.cancelar_mensaje = False
                    rec.pause_threshold = 0.7
                    try:
                        audio2 = rec.listen(source, timeout=10, phrase_time_limit=30)
                        if self.cancelar_mensaje:
                            continue
                        self._set_estado("⏳  PROCESANDO...", "#8b5cf6")
                        texto = rec.recognize_google(audio2, language="es-ES")
                        if "cancelar" in texto.lower():
                            self._log("⏹ Cancelado", "error")
                            self._set_estado("👂  di 'activar comando'", "#4b5563")
                            continue
                        self._log(f'🗣 Tú: "{texto}"', "voz")
                        self._set_estado("⌨️  ESCRIBIENDO...", "#6366f1")
                        self._escribir_en_vscode(texto)
                        self._log("✓ Enviado", "ok")
                        self._set_estado("⏳  Esperando respuesta...", "#4b5563")
                    except sr.WaitTimeoutError:
                        self._log("No escuché nada — di 'activar comando'", "error")
                    except sr.UnknownValueError:
                        self._log("No entendí — intenta de nuevo", "error")
                        self.escucha_auto = True  # reintenta sin pedir "activar comando"
                    finally:
                        rec.pause_threshold = 0.6

        self._set_estado("● LISTO", "#10b981")

    def _escribir_en_vscode(self, texto):
        ventanas = gw.getWindowsWithTitle("Visual Studio Code")
        if not ventanas:
            self._log("No encontré VSCode abierto", "error")
            return
        ventanas[0].activate()
        time.sleep(0.2)
        # Pega via portapapeles para soportar tildes y caracteres especiales
        self.root.clipboard_clear()
        self.root.clipboard_append(texto)
        self.root.update()
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.1)
        pyautogui.press("enter")

    # ── Pitido ─────────────────────────────────────────────────────────────────
    def _tono(self, freq, ms):
        import numpy as np
        sample_rate = 44100
        samples = int(sample_rate * ms / 1000)
        t = np.linspace(0, ms / 1000, samples, False)
        fade = np.ones(samples)
        fade[-int(samples * 0.2):] = np.linspace(1, 0, int(samples * 0.2))
        wave = (np.sin(2 * np.pi * freq * t) * fade * 32767).astype(np.int16)
        wave = np.column_stack([wave, wave])
        pygame.sndarray.make_sound(wave).play()
        time.sleep(ms / 1000 + 0.05)

    def _pitido(self, freq=1400, ms=120):
        """Tu activación: un pitido agudo corto"""
        threading.Thread(target=self._tono, args=(freq, ms), daemon=True).start()

    def _pitido_respuesta(self):
        """Claude va a hablar: dos tonos ascendentes suaves"""
        import numpy as np
        sample_rate = 44100
        for freq, ms in [(500, 100), (900, 180)]:
            samples = int(sample_rate * ms / 1000)
            t = np.linspace(0, ms / 1000, samples, False)
            fade = np.ones(samples)
            fade[-int(samples * 0.3):] = np.linspace(1, 0, int(samples * 0.3))
            wave = (np.sin(2 * np.pi * freq * t) * fade * 32767).astype(np.int16)
            wave = np.column_stack([wave, wave])
            pygame.sndarray.make_sound(wave).play()
            time.sleep(ms / 1000 + 0.06)

    # ── Monitor cola TTS ───────────────────────────────────────────────────────
    def _monitor_tts(self):
        cola = "c:/Proyectos/Lector/tts_cola.txt"
        esperando = False
        while True:
            try:
                if os.path.exists(cola):
                    with open(cola, "r", encoding="utf-8") as f:
                        texto = f.read().strip()
                    os.remove(cola)
                    if texto:
                        esperando = False
                        self.hablar(texto)
                elif not self.hablando and not esperando:
                    # Muestra "esperando respuesta" solo después de enviar
                    pass
            except Exception:
                pass
            time.sleep(0.1)

    # ── TTS ────────────────────────────────────────────────────────────────────
    def hablar(self, texto):
        if not self.tts_activo or not texto.strip():
            return
        threading.Thread(target=self._tts, args=(texto,), daemon=True).start()

    def _limpiar_texto(self, texto):
        import re
        texto = re.sub(r'\*+', '', texto)
        texto = re.sub(r'#+\s*', '', texto)
        texto = re.sub(r'`[^`]*`', '', texto)
        texto = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', texto)
        texto = re.sub(r'[-•]\s+', '', texto)
        texto = re.sub(r'\n{2,}', '. ', texto)
        texto = re.sub(r'\n', ' ', texto)
        texto = re.sub(r'\s+', ' ', texto)
        return texto.strip()

    def _tts(self, texto):
        self.hablando = True
        self._pitido_respuesta()
        self._set_estado("🔊  HABLANDO...", "#6366f1")
        palabras = texto.split()[:8]
        preview = " ".join(palabras) + ("..." if len(texto.split()) > 8 else "")
        self._log(f'🤖 "{preview}"', "claude")

        texto = self._limpiar_texto(texto)

        # Divide por oraciones para que se lea todo sin cortes
        import re
        partes = re.split(r'(?<=[.!?])\s+', texto)
        # Agrupa oraciones en fragmentos de max 150 chars
        fragmentos = []
        actual = ""
        for parte in partes:
            if len(actual) + len(parte) < 150:
                actual += (" " if actual else "") + parte
            else:
                if actual:
                    fragmentos.append(actual)
                actual = parte
        if actual:
            fragmentos.append(actual)

        try:
            archivos = [None] * len(fragmentos)

            def pregenerar(i, frag):
                try:
                    tmp = tempfile.mktemp(suffix=".mp3")
                    asyncio.run(self._gen_audio(frag, tmp))
                    archivos[i] = tmp
                except Exception:
                    archivos[i] = ""

            # Genera el primero ya
            t = threading.Thread(target=pregenerar, args=(0, fragmentos[0]), daemon=True)
            t.start()

            for i, frag in enumerate(fragmentos):
                if not self.hablando or not self.tts_activo:
                    break

                # Espera que el audio actual esté listo
                while archivos[i] is None:
                    time.sleep(0.05)

                # Pregenerá el siguiente mientras reproduce este
                if i + 1 < len(fragmentos):
                    threading.Thread(target=pregenerar, args=(i + 1, fragmentos[i + 1]), daemon=True).start()

                if not archivos[i]:
                    continue

                pygame.mixer.music.load(archivos[i])
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy() and self.hablando and self.tts_activo:
                    time.sleep(0.05)
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
                try:
                    os.remove(archivos[i])
                except Exception:
                    pass

        except Exception as ex:
            self._log(f"Error TTS: {ex}", "error")

        self.hablando = False
        self._set_estado("🎙️  ESCUCHANDO..." if self.mic_activo else "● LISTO",
                         "#f59e0b" if self.mic_activo else "#10b981")

    async def _gen_audio(self, texto, ruta):
        await edge_tts.Communicate(texto, VOZ).save(ruta)


# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    root.update_idletasks()
    w, h = 320, 280
    x = root.winfo_screenwidth() - w - 20
    root.geometry(f"{w}x{h}+{x}+40")

    app = Panel(root)
    root.mainloop()
