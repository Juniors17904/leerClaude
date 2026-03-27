"""
Escucha tu voz continuamente y escribe el texto en la ventana activa (VSCode).
Ejecuta este script aparte: python escuchar.py
"""
import speech_recognition as sr
import pyautogui
import time
import sys

def main():
    rec = sr.Recognizer()
    rec.pause_threshold = 1.0
    rec.energy_threshold = 300

    print("Escuchando... habla cuando quieras.")
    print("Ctrl+C para salir.\n")

    with sr.Microphone() as mic:
        rec.adjust_for_ambient_noise(mic, duration=1)
        while True:
            try:
                print("[ esperando... ]")
                audio = rec.listen(mic, timeout=None, phrase_time_limit=30)
                print("[ procesando... ]")
                texto = rec.recognize_google(audio, language="es-ES")
                print(f"Tú dijiste: {texto}")

                # Escribe el texto en la ventana activa y presiona Enter
                time.sleep(0.2)
                pyautogui.typewrite(texto, interval=0.03)
                pyautogui.press("enter")

            except sr.UnknownValueError:
                pass
            except KeyboardInterrupt:
                print("\nSaliendo...")
                sys.exit(0)
            except Exception as ex:
                print(f"Error: {ex}")
                time.sleep(0.5)

if __name__ == "__main__":
    main()
