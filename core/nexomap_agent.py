# -*- coding: utf-8 -*-
"""Loop de orquestracao IA <-> tools (plano 00).

A IA recebe o pedido + contexto e responde com ``tool_calls``; o loop executa
cada tool sobre o MapSpec em memoria (``core/nexomap_tools.py``), devolve o
resultado (role ``tool``) e repete ate a IA chamar ``finalizar`` (ou o limite de
passos). O provedor e injetado (``call_provider``) para permitir mock nos testes;
o real vive em ``nexomap_ai.run_tools``.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from core.mapspec import MapSpec, apply_rule_based_edit, mapspec_from_dict
from core.nexomap_catalog import public_context
from core.nexomap_tools import TOOL_SCHEMAS, ToolContext, execute_tool

MAX_STEPS_DEFAULT = 12
TIMEOUT_S_DEFAULT = 300.0


@dataclass
class AgentResult:
    spec: MapSpec
    tool_log: list[dict] = field(default_factory=list)
    resumo: str = ""
    provider: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "mapspec": self.spec.to_dict(),
            "tool_log": self.tool_log,
            "resumo": self.resumo,
            "provider": self.provider,
            "warnings": self.warnings,
        }


def _system_prompt_tools() -> str:
    return (
        "Voce e o operador cartografico do NexoMap AI (padrao IMAP, Mato Grosso). "
        "Voce NUNCA reescreve o MapSpec inteiro: opera o mapa exclusivamente pelas "
        "tools fornecidas, em chamadas atomicas e minimas. "
        "Fluxo: (1) se precisar, consulte estado_atual/listar_camadas; (2) aplique as "
        "tools que o pedido exige; (3) chame finalizar com um resumo curto. "
        "Nunca invente camadas, templates ou endpoints — so os ids do contexto/catalogo. "
        "Se um resultado de tool comecar com 'erro:', corrija os argumentos e tente de "
        "novo (no maximo 2 tentativas por tool). "
        "Posicoes: x,y em fracao da pagina [0..1] com origem inferior-esquerda; ancoras "
        "in-map-* referem-se ao quadro do mapa. 'Rodape' = ancoras bottom-*; "
        "'topo' = top-*. O padrao IMAP recente usa titulo em caixa branca no topo-centro."
    )


def _user_context(prompt: str, spec: dict | None, ctx: ToolContext) -> str:
    payload = {
        "pedido_usuario": prompt,
        "mapspec_atual": spec,  # None => crie com criar_mapa
        "permitido": public_context(ctx.catalog, ctx.manifest),
        "projeto": ctx.project_name,
    }
    return json.dumps(payload, ensure_ascii=False)


def run_tool_loop(prompt: str, ctx: ToolContext, call_provider,
                  spec_dict: dict | None = None, max_steps: int = MAX_STEPS_DEFAULT,
                  timeout_s: float = TIMEOUT_S_DEFAULT,
                  on_tool_call = None) -> AgentResult:
    """Roda o loop IA<->tools ate ``finalizar``/resposta final/limites.

    ``call_provider(messages, tools) -> dict`` no formato chat completions.
    ``spec_dict=None`` significa mapa novo (a IA deve chamar ``criar_mapa``).
    ``on_tool_call(nome, args, resultado)`` callback opcional p/ streaming.
    """
    messages: list[dict] = [
        {"role": "system", "content": _system_prompt_tools()},
        {"role": "user", "content": _user_context(prompt, spec_dict, ctx)},
    ]
    spec = spec_dict
    tool_log: list[dict] = []
    warnings: list[str] = []
    resumo = ""
    inicio = time.monotonic()

    for _ in range(max_steps):
        if time.monotonic() - inicio > timeout_s:
            warnings.append(f"loop de tools excedeu o timeout de {timeout_s:.0f}s")
            break
        resp = call_provider(messages, TOOL_SCHEMAS)
        try:
            msg = resp["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as e:
            raise ValueError(f"resposta do provedor invalida: {e}") from e

        calls = msg.get("tool_calls") or []
        if not calls:
            resumo = (msg.get("content") or "").strip()
            break

        messages.append({"role": "assistant", "content": msg.get("content") or "",
                         "tool_calls": calls})
        finalizou = False
        for call in calls:
            nome = ((call.get("function") or {}).get("name")) or ""
            raw_args = ((call.get("function") or {}).get("arguments")) or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
            except json.JSONDecodeError:
                args = {}
            if spec is None and nome not in ("criar_mapa", "estado_atual", "listar_camadas"):
                resultado = "erro: nao ha mapa ainda; chame criar_mapa primeiro"
                done = False
            else:
                spec_novo, resultado, done = execute_tool(nome, spec or {}, ctx, args)
                if not resultado.startswith("erro:"):
                    spec = spec_novo
            tool_log.append({"tool": nome, "args": args, "resultado": resultado})
            messages.append({"role": "tool", "tool_call_id": call.get("id", ""),
                             "content": resultado})
            if on_tool_call:
                try:
                    on_tool_call(nome, args, resultado)
                except Exception:
                    pass
            if done:
                finalizou = True
                resumo = args.get("resumo") or resultado
        if finalizou:
            break
    else:
        warnings.append(f"loop de tools atingiu o limite de {max_steps} passos sem finalizar")

    if spec is None:
        raise ValueError("a IA nao criou um mapa (nenhuma tool criar_mapa executada)")
    return AgentResult(spec=mapspec_from_dict(spec), tool_log=tool_log,
                       resumo=resumo, warnings=warnings)


def run_rule_based(prompt: str, ctx: ToolContext, spec_dict: dict) -> AgentResult:
    """Fallback deterministico sem IA: reusa ``apply_rule_based_edit`` e registra
    o efeito como um pseudo-tool_call (auditavel do mesmo jeito)."""
    atual = mapspec_from_dict(spec_dict)
    editado = apply_rule_based_edit(atual, prompt, ctx.catalog, ctx.manifest)
    log = [{"tool": "apply_rule_based_edit", "args": {"instrucao": prompt},
            "resultado": "edicao deterministica aplicada (fallback sem IA)"}]
    return AgentResult(spec=editado, tool_log=log, provider="local_rules",
                       resumo="edicao deterministica aplicada",
                       warnings=["IA indisponivel ou nao configurada; fallback deterministico"])
