# -*- coding: utf-8 -*-
"""Teste AO VIVO do loop de tools com DeepSeek (plano 00).

Pulado por padrao: exige DEEPSEEK_API_KEY no ambiente (nunca hardcodar chave).
Opcional: SEMA_AUTHKEY para a camada de embargos vir com feicoes reais.

    DEEPSEEK_API_KEY=... python -m pytest tests/live -q
"""
import json
import os
import tempfile
import unittest

from tests.test_layout import _write_project


@unittest.skipUnless(os.environ.get("DEEPSEEK_API_KEY"), "sem DEEPSEEK_API_KEY no ambiente")
class DeepSeekToolsLiveTests(unittest.TestCase):
    def test_embargos_e_legenda_no_rodape_via_tools(self):
        from core.nexomap_generator import chat_tools

        with tempfile.TemporaryDirectory() as tmp:
            project_path = _write_project(tmp)
            secrets = {
                "nexomap_ai_provider": "deepseek",
                "deepseek_api_key": os.environ["DEEPSEEK_API_KEY"],
                "nexomap_deepseek_model": os.environ.get("NEXOMAP_DEEPSEEK_MODEL",
                                                         "deepseek-v4-pro"),
            }
            if os.environ.get("SEMA_AUTHKEY"):
                secrets["sema_authkey"] = os.environ["SEMA_AUTHKEY"]
            with open(os.path.join(tmp, "secrets.local.json"), "w", encoding="utf-8") as f:
                json.dump(secrets, f)

            result = chat_tools(
                project_path,
                "Crie um mapa com os embargos da SEMA e mova a legenda para o rodape, "
                "no canto inferior esquerdo da pagina.",
                allow_local_ai_fallback=False, use_basemap=False)

            tools_usadas = [t["tool"] for t in result["tool_calls"]]
            self.assertIn("adicionar_camada", tools_usadas, msg=str(result["tool_calls"]))
            self.assertIn("mover_elemento", tools_usadas, msg=str(result["tool_calls"]))

            spec = result["mapspec"]
            ids = [c["id"] for c in spec["camadas"]]
            self.assertIn("embargos_sema", ids, msg=str(ids))
            leg = (spec.get("layout") or {}).get("elementos", {}).get("legenda") or {}
            self.assertTrue(str(leg.get("ancora", "")).startswith(("bottom", "in-map-bottom")),
                            msg=str(leg))
            self.assertTrue(os.path.exists(result["outputs"]["pdf"]))


if __name__ == "__main__":
    unittest.main()
