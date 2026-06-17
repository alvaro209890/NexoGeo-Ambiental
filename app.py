# -*- coding: utf-8 -*-
"""Shell desktop — sobe a API (que serve a UI já buildada) e abre a janela pywebview.

    python app.py        # janela do app (requer ui/dist buildado e pywebview)

Sem pywebview instalado, mantém o servidor no ar e instrui a abrir no navegador.
"""
from __future__ import annotations

import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from api.app import app

HOST, PORT = "127.0.0.1", 8000


def _serve():
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


def main():
    threading.Thread(target=_serve, daemon=True).start()
    url = f"http://{HOST}:{PORT}"
    try:
        import webview
    except ImportError:
        print(f"pywebview não instalado — abra {url} no navegador (pip install pywebview p/ a janela).")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        return
    time.sleep(0.6)  # dá um instante para o servidor subir
    webview.create_window("Análise de Área", url, width=1100, height=720, min_size=(820, 560))
    webview.start()


if __name__ == "__main__":
    main()
