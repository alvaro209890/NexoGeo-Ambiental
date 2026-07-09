# -*- coding: utf-8 -*-
"""Tool validar_mapa + validação nível-spec + auto-correção no loop (plano 09)."""
import json
import os
import unittest

from core.nexomap_agent import run_tool_loop
from core.nexomap_catalog import load_layer_catalog, load_template_manifest
from core.nexomap_tools import TOOL_SCHEMAS, TOOLS, ToolContext, execute_tool
from core.nexomap_validation import validar_mapspec_imap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ctx() -> ToolContext:
    catalog = load_layer_catalog(os.path.join(ROOT, "catalogo", "camadas.json"))
    manifest = load_template_manifest(os.path.join(ROOT, "templates", "layouts", "MANIFEST.json"))
    return ToolContext(catalog=catalog, manifest=manifest, secrets={}, project_name="Teste")


def _spec_base(ctx, template="dinamica_a3_paisagem"):
    spec, msg, _ = execute_tool("criar_mapa", {}, ctx, {"titulo": "Mapa Base", "template": template})
    assert not msg.startswith("erro:"), msg
    return spec


class ValidarMapspecImapTests(unittest.TestCase):
    def test_schemas_cobrem_todas_as_tools(self):
        nomes = {s["function"]["name"] for s in TOOL_SCHEMAS}
        self.assertEqual(nomes, set(TOOLS))
        self.assertIn("validar_mapa", nomes)
        self.assertIn("sugerir_melhorias", nomes)

    def test_titulo_ausente_reprova_hard(self):
        rel = validar_mapspec_imap({"camadas": [{"id": "perimetro"}],
                                    "layout_template": "dinamica_a3_paisagem"})
        self.assertFalse(rel["ok"])
        self.assertIn("titulo_presente", rel["hard_falhos"])

    def test_flagship_conforma(self):
        spec = {
            "titulo": "Mapa IMAP", "layout_template": "dinamica_a3_paisagem",
            "camadas": [{"id": "perimetro"}],
            "metadados_imagem": {"satelite_sensor": "PLANET"},
        }
        rel = validar_mapspec_imap(spec)
        self.assertTrue(rel["ok"], rel["resumo"])
        self.assertEqual(rel["hard_falhos"], [])

    def test_nao_flagship_reprova_legenda_no_rodape(self):
        spec = {"titulo": "Mapa", "layout_template": "dinamica_a3_paisagem",
                "camadas": [{"id": "perimetro"}]}
        rel = validar_mapspec_imap(spec)
        self.assertIn("legenda_no_rodape", rel["hard_falhos"])

    def test_legenda_ancorada_no_rodape_passa_sem_flagship(self):
        spec = {"titulo": "Mapa", "layout_template": "dinamica_a3_paisagem",
                "camadas": [{"id": "perimetro"}],
                "legenda": {"posicao": {"ancora": "bottom-left", "x": 0.02, "y": 0.02}}}
        rel = validar_mapspec_imap(spec)
        self.assertNotIn("legenda_no_rodape", rel["hard_falhos"])

    def test_template_retrato_reprova(self):
        spec = {"titulo": "Mapa", "layout_template": "tematico_a3_retrato",
                "camadas": [{"id": "perimetro"}],
                "metadados_imagem": {"satelite_sensor": "PLANET"}}
        rel = validar_mapspec_imap(spec)
        self.assertIn("template_paisagem", rel["hard_falhos"])


class ToolValidarMapaTests(unittest.TestCase):
    def setUp(self):
        self.ctx = _ctx()

    def test_tool_validar_mapa_retorna_checklist_json(self):
        spec = _spec_base(self.ctx)  # criar_mapa nao e flagship por padrao
        _, msg, done = execute_tool("validar_mapa", spec, self.ctx, {})
        self.assertFalse(done)
        rel = json.loads(msg)
        self.assertIn("legenda_no_rodape", rel["hard_falhos"])

    def test_tool_validar_mapa_apos_metadados_aprova(self):
        spec = _spec_base(self.ctx)
        spec, msg, _ = execute_tool("definir_metadados_imagem", spec, self.ctx,
                                    {"satelite_sensor": "PLANET", "datum": "SIRGAS 2000"})
        self.assertFalse(msg.startswith("erro:"), msg)
        _, msg, _ = execute_tool("validar_mapa", spec, self.ctx, {})
        rel = json.loads(msg)
        self.assertTrue(rel["ok"], rel["resumo"])

    def test_tool_sugerir_melhorias(self):
        spec = _spec_base(self.ctx)
        _, msg, _ = execute_tool("sugerir_melhorias", spec, self.ctx, {})
        sug = json.loads(msg)["sugestoes"]
        self.assertTrue(any("faixa inferior" in s.lower() for s in sug))


def _fake_provider(script):
    it = iter(script)

    def call(messages, tools):
        return next(it)
    return call


def _tool_call(nome, args, cid="c"):
    return {"id": cid, "type": "function",
            "function": {"name": nome, "arguments": json.dumps(args)}}


def _resp(tool_calls=None, content=""):
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return {"choices": [{"message": msg}]}


class AutoCorrecaoNoLoopTests(unittest.TestCase):
    """A IA valida, vê a falha HARD, corrige e revalida antes de finalizar."""

    def setUp(self):
        self.ctx = _ctx()

    def test_ia_autocorrige_legenda_no_rodape(self):
        script = [
            _resp([_tool_call("criar_mapa", {"titulo": "Auto", "template": "dinamica_a3_paisagem"}, "c1")]),
            _resp([_tool_call("validar_mapa", {}, "c2")]),          # acusa legenda_no_rodape
            _resp([_tool_call("definir_metadados_imagem",
                              {"satelite_sensor": "PLANET", "datum": "SIRGAS 2000"}, "c3")]),
            _resp([_tool_call("validar_mapa", {}, "c4")]),          # agora aprova
            _resp([_tool_call("finalizar", {"resumo": "conforme IMAP"}, "c5")]),
        ]
        result = run_tool_loop("faça um mapa IMAP", self.ctx, _fake_provider(script))
        tools_usadas = [t["tool"] for t in result.tool_log]
        self.assertEqual(tools_usadas,
                         ["criar_mapa", "validar_mapa", "definir_metadados_imagem",
                          "validar_mapa", "finalizar"])
        # o penultimo validar_mapa (c4) deve estar aprovado
        ultima_val = [t for t in result.tool_log if t["tool"] == "validar_mapa"][-1]
        self.assertTrue(json.loads(ultima_val["resultado"])["ok"])
        # spec final conforma
        rel = validar_mapspec_imap(result.spec.to_dict())
        self.assertTrue(rel["ok"], rel["resumo"])


if __name__ == "__main__":
    unittest.main()
