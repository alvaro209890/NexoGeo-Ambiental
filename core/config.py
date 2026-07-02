# -*- coding: utf-8 -*-
"""Esquema e carregamento do projeto.json (Fase 0).

Um "projeto" = uma análise de um imóvel. Tudo que muda entre análises vive aqui;
o código das automações nunca tem fazenda/CAR escrito dentro.

Uso (a partir da pasta software/):
    python -m core.config <caminho-da-analise>/projeto.json
"""
from __future__ import annotations
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

SCHEMA_VERSION = 1


class ProjetoError(Exception):
    """Erro de validação/carregamento de um projeto.json."""


@dataclass
class Municipio:
    nome: str
    uf: str
    ibge: str


@dataclass
class Matricula:
    numero: str
    area_ha: Optional[float] = None


@dataclass
class MatriculaDominial:
    """Uma linha da tabela de Dominialidade (Seção 1 da pré-análise).

    Preenchida pela extração IA dos PDFs de matrícula + conferência do analista
    (grade da UI), ou manualmente no projeto.json.
    """
    numero: str
    denominacao: str = ""
    proprietario: str = ""
    cpf_cnpj: str = ""
    area_ha: Optional[float] = None


@dataclass
class Dominialidade:
    """Registro cartorial do imóvel: CRI/CNS + matrículas."""
    cri: str = ""          # comarca do Cartório de Registro de Imóveis (ex.: "Vila Rica/MT")
    cns: str = ""          # nº CNS do cartório
    matriculas: list[MatriculaDominial] = field(default_factory=list)


@dataclass
class Fazenda:
    id: str
    nome: str
    shape_car: str            # nome da pasta/shape do CAR (ex.: "CAR_ATP (69)")
    car_federal: str = ""
    car_estadual: str = ""
    recibo_pdf: str = ""      # nome do recibo PDF do CAR em <consultas>/CAR/
    matriculas: list[Matricula] = field(default_factory=list)


@dataclass
class Pastas:
    shapes: str = "Shapes"
    car: str = "Shapes/CAR"
    consultas: str = "Consultas_Publicas"
    resultados: str = "Automacoes/Resultados"


@dataclass
class Projeto:
    versao_schema: int
    imovel: str
    municipio: Municipio
    crs_utm: int
    crs_geo: int
    data_consulta: str          # "auto" ou "DD/MM/AAAA"
    raiz_dados: str             # pasta-raiz dos dados (absoluta ou relativa ao arquivo)
    pastas: Pastas
    fazendas: list[Fazenda]
    mapa_campos: dict[str, str]
    automacoes: list[str]
    cliente: str = ""
    quantitativos: dict[str, Any] = field(default_factory=dict)
    area_total: list[dict] = field(default_factory=list)   # visão de registro (matrícula)
    dominialidade: Dominialidade = field(default_factory=Dominialidade)
    _arquivo: str = ""          # caminho absoluto do projeto.json carregado

    # ---- derivados ----
    def data_consulta_efetiva(self) -> str:
        if self.data_consulta.strip().lower() == "auto":
            return date.today().strftime("%d/%m/%Y")
        return self.data_consulta

    def raiz_abs(self) -> str:
        if os.path.isabs(self.raiz_dados):
            return os.path.normpath(self.raiz_dados)
        base = os.path.dirname(os.path.abspath(self._arquivo))
        return os.path.normpath(os.path.join(base, self.raiz_dados))

    def caminho(self, chave: str) -> str:
        """Resolve uma das pastas (shapes/car/consultas/resultados) para caminho absoluto."""
        rel = getattr(self.pastas, chave)
        return os.path.normpath(os.path.join(self.raiz_abs(), rel))

    def fazenda_por_id(self, fid: str) -> Optional[Fazenda]:
        return next((f for f in self.fazendas if f.id == fid), None)


def _req(d: dict, chave: str, contexto: str):
    if chave not in d:
        raise ProjetoError(f"campo obrigatório ausente: {contexto}.{chave}")
    return d[chave]


def load_projeto(path: str) -> Projeto:
    """Lê e valida um projeto.json, devolvendo um objeto Projeto."""
    if not os.path.exists(path):
        raise ProjetoError(f"arquivo não encontrado: {path}")
    with open(path, "r", encoding="utf-8") as f:
        try:
            d = json.load(f)
        except json.JSONDecodeError as e:
            raise ProjetoError(f"JSON inválido em {path}: {e}")

    versao = int(d.get("versao_schema", SCHEMA_VERSION))
    if versao != SCHEMA_VERSION:
        raise ProjetoError(f"versao_schema {versao} != suportada {SCHEMA_VERSION}")

    m = _req(d, "municipio", "projeto")
    municipio = Municipio(
        _req(m, "nome", "municipio"), _req(m, "uf", "municipio"), str(_req(m, "ibge", "municipio"))
    )
    if municipio.uf.strip().upper() != "MT":
        raise ProjetoError(
            f"município '{municipio.nome}' tem uf='{municipio.uf}': esta versão suporta apenas "
            "imóveis em Mato Grosso (MT) — decisão §0.1 do PLANO_MELHORIAS"
        )

    crs = d.get("crs", {})
    crs_utm = int(crs.get("utm") if crs.get("utm") is not None else _req(d, "crs_utm", "projeto"))
    crs_geo = int(crs.get("geografico", 4674))

    # fazendas é OPCIONAL: sem ela o projeto roda em "modo só shape" (a pré-análise
    # descobre os CARs pela camada SEMA MVW_REQUERIMENTO_ATP a partir do zip).
    fazendas: list[Fazenda] = []
    ids: set[str] = set()
    for i, fz in enumerate(d.get("fazendas", [])):
        ctx = f"fazendas[{i}]"
        fid = str(_req(fz, "id", ctx))
        if fid in ids:
            raise ProjetoError(f"id de fazenda duplicado: {fid}")
        ids.add(fid)
        mats = [Matricula(str(mt.get("numero", "")), mt.get("area_ha"))
                for mt in fz.get("matriculas", [])]
        fazendas.append(Fazenda(
            id=fid, nome=_req(fz, "nome", ctx), shape_car=_req(fz, "shape_car", ctx),
            car_federal=fz.get("car_federal", ""), car_estadual=fz.get("car_estadual", ""),
            recibo_pdf=fz.get("recibo_pdf", ""), matriculas=mats,
        ))
    dom = d.get("dominialidade", {}) or {}
    reg = dom.get("registro", {}) or {}
    dominialidade = Dominialidade(
        cri=str(reg.get("cri", "")),
        cns=str(reg.get("cns", "")),
        matriculas=[
            MatriculaDominial(
                numero=str(mt.get("numero", "")),
                denominacao=str(mt.get("denominacao", "")),
                proprietario=str(mt.get("proprietario", "")),
                cpf_cnpj=str(mt.get("cpf_cnpj", "")),
                area_ha=(float(mt["area_ha"]) if mt.get("area_ha") not in (None, "") else None),
            )
            for mt in dom.get("matriculas", [])
        ],
    )

    at = d.get("area_total", {})
    area_total = at.get("itens", []) if isinstance(at, dict) else (at or [])

    pd_ = d.get("pastas", {})
    pastas = Pastas(
        shapes=pd_.get("shapes", "Shapes"),
        car=pd_.get("car", "Shapes/CAR"),
        consultas=pd_.get("consultas", "Consultas_Publicas"),
        resultados=pd_.get("resultados", "Automacoes/Resultados"),
    )

    return Projeto(
        versao_schema=versao,
        imovel=_req(d, "imovel", "projeto"),
        cliente=d.get("cliente", ""),
        municipio=municipio,
        crs_utm=crs_utm, crs_geo=crs_geo,
        data_consulta=str(d.get("data_consulta", "auto")),
        raiz_dados=_req(d, "raiz_dados", "projeto"),
        pastas=pastas,
        fazendas=fazendas,
        mapa_campos=d.get("mapa_campos", {}),
        automacoes=d.get("automacoes", []),
        quantitativos=d.get("quantitativos", {}),
        area_total=area_total,
        dominialidade=dominialidade,
        _arquivo=os.path.abspath(path),
    )


def _main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("uso: python -m core.config <projeto.json>")
        return 2
    proj = load_projeto(argv[1])
    print(f"Projeto      : {proj.imovel}" + (f"  (cliente: {proj.cliente})" if proj.cliente else ""))
    print(f"Município    : {proj.municipio.nome}/{proj.municipio.uf} ({proj.municipio.ibge})")
    print(f"CRS          : UTM {proj.crs_utm} | geográfico {proj.crs_geo}")
    print(f"Data consulta: {proj.data_consulta_efetiva()}  (config: {proj.data_consulta})")
    print(f"Raiz de dados: {proj.raiz_abs()}")
    for chave in ("shapes", "car", "consultas", "resultados"):
        p = proj.caminho(chave)
        print(f"  {chave:11s}: {p}  [{'ok' if os.path.exists(p) else 'FALTA'}]")
    print(f"Automações   : {', '.join(proj.automacoes) or '—'}")
    dom = proj.dominialidade
    print(f"Dominialidade: {len(dom.matriculas)} matrícula(s)"
          + (f" | CRI {dom.cri} (CNS: {dom.cns})" if dom.cri else " | registro não informado"))
    if not proj.fazendas:
        print("Fazendas     : nenhuma no projeto (modo só shape: CARs descobertos pela SEMA)")
    print(f"Fazendas ({len(proj.fazendas)}):")
    for fz in proj.fazendas:
        amat = sum(mt.area_ha or 0 for mt in fz.matriculas)
        car = os.path.join(proj.caminho("car"), fz.shape_car, "CAR_ATP.shp")
        print(f"  - {fz.nome:26s} | CAR est. {fz.car_estadual or '—':14s} | "
              f"{len(fz.matriculas)} matr. ({amat:9.4f} ha) | shp[{'ok' if os.path.exists(car) else 'FALTA'}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
