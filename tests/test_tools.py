# -*- coding: utf-8 -*-
"""Testes das tools da IA (plano 00): efeito, validacao e loop de orquestracao."""
import json
import os
import unittest

from core.mapspec import mapspec_from_dict, validate_mapspec
from core.nexomap_agent import run_rule_based, run_tool_loop
from core.nexomap_catalog import load_layer_catalog, load_template_manifest
from core.nexomap_tools import (TOOL_SCHEMAS, TOOLS, ToolContext, execute_tool)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ctx() -> ToolContext:
    catalog = load_layer_catalog(os.path.join(ROOT, "catalogo", "camadas.json"))
    manifest = load_template_manifest(os.path.join(ROOT, "templates", "layouts", "MANIFEST.json"))
    return ToolContext(catalog=catalog, manifest=manifest, secrets={}, project_name="Teste")


def _spec_base(ctx: ToolContext) -> dict:
    spec, msg, done = execute_tool("criar_mapa", {}, ctx, {"titulo": "Mapa Base"})
    assert not msg.startswith("erro:"), msg
    return spec


class ToolUnitTests(unittest.TestCase):
    def setUp(self):
        self.ctx = _ctx()
        self.spec = _spec_base(self.ctx)

    def test_schemas_cobrem_todas_as_tools(self):
        nomes_schema = {s["function"]["name"] for s in TOOL_SCHEMAS}
        self.assertEqual(nomes_schema, set(TOOLS))

    def test_criar_mapa_gera_spec_valido(self):
        warnings = validate_mapspec(mapspec_from_dict(self.spec), self.ctx.catalog,
                                    self.ctx.manifest, {})
        self.assertEqual(warnings, [])
        self.assertEqual(self.spec["titulo"], "Mapa Base")

    def test_criar_mapa_sem_titulo_erra(self):
        _, msg, _ = execute_tool("criar_mapa", {}, self.ctx, {"titulo": "  "})
        self.assertTrue(msg.startswith("erro:"))

    def test_mover_elemento_altera_so_o_alvo(self):
        antes = json.dumps(self.spec, sort_keys=True)
        novo, msg, _ = execute_tool("mover_elemento", self.spec, self.ctx, {
            "elemento": "legenda",
            "posicao": {"ancora": "bottom-left", "x": 0.02, "y": 0.02},
            "tamanho": {"largura": 0.28},
        })
        self.assertFalse(msg.startswith("erro:"), msg)
        self.assertEqual(novo["layout"]["elementos"]["legenda"],
                         {"ancora": "bottom-left", "x": 0.02, "y": 0.02, "largura": 0.28})
        # o resto do spec nao mudou
        depois = dict(novo)
        depois.pop("layout")
        base = json.loads(antes)
        base.pop("layout", None)
        self.assertEqual(json.dumps(depois, sort_keys=True), json.dumps(base, sort_keys=True))

    def test_mover_elemento_invalido_erra_sem_mudar_spec(self):
        novo, msg, _ = execute_tool("mover_elemento", self.spec, self.ctx, {
            "elemento": "foguete", "posicao": {"ancora": "bottom-left", "x": 0, "y": 0}})
        self.assertTrue(msg.startswith("erro:"))
        self.assertEqual(novo, self.spec)
        novo, msg, _ = execute_tool("mover_elemento", self.spec, self.ctx, {
            "elemento": "legenda", "posicao": {"ancora": "meio", "x": 0, "y": 0}})
        self.assertTrue(msg.startswith("erro:"))

    def test_alternar_elemento(self):
        novo, msg, _ = execute_tool("alternar_elemento", self.spec, self.ctx,
                                    {"elemento": "titulo_caixa", "visivel": False})
        self.assertFalse(msg.startswith("erro:"), msg)
        self.assertFalse(novo["elementos_layout"]["titulo_caixa"])

    def test_adicionar_e_remover_camada_mantem_valido(self):
        novo, msg, _ = execute_tool("adicionar_camada", self.spec, self.ctx, {
            "fonte": "catalogo.car_sema",
            "estilo": {"linha": "#1d4ed8", "opacidade": 0.2}})
        self.assertFalse(msg.startswith("erro:"), msg)
        self.assertIn("car_sema", [c["id"] for c in novo["camadas"]])
        # auth ausente vira aviso na mensagem, nao erro
        self.assertIn("sema_authkey", msg)
        validate_mapspec(mapspec_from_dict(novo), self.ctx.catalog, self.ctx.manifest, {})

        depois, msg2, _ = execute_tool("remover_camada", novo, self.ctx, {"id": "car_sema"})
        self.assertFalse(msg2.startswith("erro:"), msg2)
        self.assertNotIn("car_sema", [c["id"] for c in depois["camadas"]])

    def test_adicionar_camada_inexistente_erra(self):
        _, msg, _ = execute_tool("adicionar_camada", self.spec, self.ctx,
                                 {"fonte": "catalogo.inventada"})
        self.assertTrue(msg.startswith("erro:"))

    def test_remover_ultima_camada_erra(self):
        _, msg, _ = execute_tool("remover_camada", self.spec, self.ctx, {"id": "perimetro"})
        self.assertTrue(msg.startswith("erro:"))

    def test_editar_legenda_e_tabela(self):
        novo, msg, _ = execute_tool("editar_legenda", self.spec, self.ctx, {
            "titulo": "LEGENDA", "modo": "manual",
            "itens": [{"rotulo": "Perimetro", "tipo": "linha", "cor": "#ff2d00"}]})
        self.assertFalse(msg.startswith("erro:"), msg)
        self.assertEqual(novo["legenda"]["titulo"], "LEGENDA")

        novo2, msg2, _ = execute_tool("criar_tabela", novo, self.ctx, {
            "titulo": "Quantitativo (ha)", "fonte": "manual",
            "colunas": ["Classe", "Area (ha)"], "linhas": [["Total", "100,0"]]})
        self.assertFalse(msg2.startswith("erro:"), msg2)
        self.assertEqual(novo2["tabela"]["colunas"], ["Classe", "Area (ha)"])

    def test_criar_tabela_manual_sem_linhas_erra(self):
        _, msg, _ = execute_tool("criar_tabela", self.spec, self.ctx,
                                 {"titulo": "X", "fonte": "manual"})
        self.assertTrue(msg.startswith("erro:"))

    def test_definir_escala(self):
        novo, msg, _ = execute_tool("definir_escala", self.spec, self.ctx, {"escala": 25000})
        self.assertEqual(novo["escala"], 25000)
        novo2, _, _ = execute_tool("definir_escala", novo, self.ctx, {"escala": "auto"})
        self.assertEqual(novo2["escala"], "auto")
        _, msg3, _ = execute_tool("definir_escala", self.spec, self.ctx, {"escala": -5})
        self.assertTrue(msg3.startswith("erro:"))

    def test_finalizar_marca_done(self):
        _, msg, done = execute_tool("finalizar", self.spec, self.ctx, {"resumo": "pronto"})
        self.assertTrue(done)
        self.assertEqual(msg, "pronto")

    def test_sequencia_de_tools_converge_para_spec_valido(self):
        spec = self.spec
        passos = [
            ("adicionar_camada", {"fonte": "catalogo.embargos_sema",
                                  "estilo": {"linha": "#f97316", "opacidade": 0.4}}),
            ("mover_elemento", {"elemento": "legenda",
                                "posicao": {"ancora": "bottom-left", "x": 0.02, "y": 0.012}}),
            ("definir_titulo", {"titulo": "Embargos SEMA", "subtitulo": "Faz. Teste"}),
            ("definir_metadados_imagem", {"satelite_sensor": "PLANET", "datum": "SIRGAS 2000"}),
            ("editar_estilo_elemento", {"elemento": "titulo",
                                        "props": {"fundo": "white", "cor": "#111827"}}),
        ]
        for nome, args in passos:
            spec, msg, _ = execute_tool(nome, spec, self.ctx, args)
            self.assertFalse(msg.startswith("erro:"), f"{nome}: {msg}")
        parsed = mapspec_from_dict(spec)
        warnings = validate_mapspec(parsed, self.ctx.catalog, self.ctx.manifest, {})
        self.assertEqual(parsed.titulo, "Embargos SEMA")
        self.assertTrue(any("sema_authkey" in w for w in warnings))  # aviso, nao erro


def _fake_provider(script):
    """Provedor mock: devolve cada resposta do roteiro em sequencia."""
    it = iter(script)

    def call(messages, tools):
        return next(it)
    return call


def _tool_call(nome, args, cid="call_1"):
    return {"id": cid, "type": "function",
            "function": {"name": nome, "arguments": json.dumps(args)}}


def _resp(tool_calls=None, content=""):
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return {"choices": [{"message": msg}]}


class AgentLoopTests(unittest.TestCase):
    def setUp(self):
        self.ctx = _ctx()

    def test_loop_executa_tools_e_finaliza(self):
        script = [
            _resp([_tool_call("criar_mapa", {"titulo": "Mapa Agent"}, "c1")]),
            _resp([
                _tool_call("adicionar_camada", {"fonte": "catalogo.embargos_sema"}, "c2"),
                _tool_call("mover_elemento", {"elemento": "legenda",
                                              "posicao": {"ancora": "bottom-left",
                                                          "x": 0.02, "y": 0.012}}, "c3"),
            ]),
            _resp([_tool_call("finalizar", {"resumo": "embargos + legenda no rodape"}, "c4")]),
        ]
        result = run_tool_loop("Adicione embargos da SEMA e mova a legenda para o rodape",
                               self.ctx, _fake_provider(script))
        self.assertEqual(result.spec.titulo, "Mapa Agent")
        self.assertIn("embargos_sema", [c.id for c in result.spec.camadas])
        self.assertEqual(result.spec.layout["elementos"]["legenda"]["ancora"], "bottom-left")
        self.assertEqual(result.resumo, "embargos + legenda no rodape")
        self.assertEqual([t["tool"] for t in result.tool_log],
                         ["criar_mapa", "adicionar_camada", "mover_elemento", "finalizar"])
        self.assertEqual(result.warnings, [])

    def test_loop_respeita_limite_de_passos(self):
        # roteiro infinito que nunca finaliza
        def call(messages, tools):
            return _resp([_tool_call("estado_atual", {}, "cX")])
        spec0, _, _ = execute_tool("criar_mapa", {}, self.ctx, {"titulo": "Loop"})
        result = run_tool_loop("teste", self.ctx, call, spec_dict=spec0, max_steps=3)
        self.assertTrue(any("limite" in w for w in result.warnings))
        self.assertEqual(len(result.tool_log), 3)

    def test_erro_de_tool_volta_para_a_ia_sem_perder_o_spec(self):
        script = [
            _resp([_tool_call("criar_mapa", {"titulo": "Mapa Erro"}, "c1")]),
            _resp([_tool_call("adicionar_camada", {"fonte": "catalogo.nao_existe"}, "c2")]),
            _resp([_tool_call("finalizar", {"resumo": "ok"}, "c3")]),
        ]
        result = run_tool_loop("teste", self.ctx, _fake_provider(script))
        erros = [t for t in result.tool_log if t["resultado"].startswith("erro:")]
        self.assertEqual(len(erros), 1)
        self.assertEqual(result.spec.titulo, "Mapa Erro")

    def test_sem_criar_mapa_e_sem_spec_levanta(self):
        script = [_resp(content="nada a fazer")]
        with self.assertRaises(ValueError):
            run_tool_loop("teste", self.ctx, _fake_provider(script))

    def test_fallback_deterministico(self):
        spec0, _, _ = execute_tool("criar_mapa", {}, self.ctx, {"titulo": "Fallback"})
        result = run_rule_based("adicionar embargos", self.ctx, spec0)
        self.assertEqual(result.provider, "local_rules")
        self.assertIn("embargos_sema", [c.id for c in result.spec.camadas])
        self.assertEqual(result.tool_log[0]["tool"], "apply_rule_based_edit")


if __name__ == "__main__":
    unittest.main()
