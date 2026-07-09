# -*- coding: utf-8 -*-
"""Gera a SÉRIE COMPLETA de mapas IMAP a partir do NÚMERO DO CAR (100% WFS).

Uso:
    .venv\\Scripts\\python.exe projetos\\car_web\\rodar_serie_car.py "MT313839/2025"

Requer a ``sema_authkey`` em secrets.local.json (raiz do repo OU projetos/car_web/)
para as camadas da SEMA (ATP, SIMCAR, tipologia, uso consolidado, embargos_sema).
Camadas públicas (FUNAI, MapBiomas, IBAMA) não precisam de chave.
"""
import os, sys

# raiz do repo = dois níveis acima deste arquivo (projetos/car_web/..)
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
os.chdir(REPO)

from core.nexomap_generator import gerar_serie_por_car, SERIE_CAR_PADRAO

if __name__ == "__main__":
    numero = sys.argv[1] if len(sys.argv) > 1 else ""
    if not numero:
        print("uso: rodar_serie_car.py \"<NUMERO_DO_CAR>\"  (ex.: MT313839/2025)")
        sys.exit(1)
    modelos = sys.argv[2].split(",") if len(sys.argv) > 2 else SERIE_CAR_PADRAO
    print(f"CAR: {numero}  |  modelos: {modelos}\n")
    r = gerar_serie_por_car(numero, modelos=modelos)
    c = r["car"]
    print(f"Imóvel: {c.get('nome')}  |  {c.get('area_ha')} ha  |  origem: {c.get('origem')}\n")
    for m in r["mapas"]:
        print(f"[{m['modelo']:16s}] ok={m['ok']}  camadas={m.get('camadas')}")
        print(f"    PDF: {m['pdf']}")
    for e in r["erros"]:
        print(f"[{e['modelo']:16s}] ERRO: {e['erro']}")
