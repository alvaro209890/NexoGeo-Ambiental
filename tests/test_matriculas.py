# -*- coding: utf-8 -*-
"""Testes do M1: validadores BR, config com dominialidade e salvar_dominialidade."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import normalize as nz
from core.config import load_projeto, ProjetoError
from core.matriculas import MatriculasError, salvar_dominialidade


def _projeto_minimo(**extra):
    d = {
        "versao_schema": 1, "imovel": "Fazenda Teste", "raiz_dados": ".",
        "municipio": {"nome": "Vila Rica", "uf": "MT", "ibge": "5108600"},
        "crs": {"utm": 31982},
    }
    d.update(extra)
    return d


class TestValidadores(unittest.TestCase):
    def test_cpf_valido_e_invalido(self):
        self.assertTrue(nz.validar_cpf("529.982.247-25"))
        self.assertFalse(nz.validar_cpf("529.982.247-26"))
        self.assertFalse(nz.validar_cpf("111.111.111-11"))

    def test_cnpj_valido_e_invalido(self):
        self.assertTrue(nz.validar_cnpj("11.222.333/0001-81"))
        self.assertFalse(nz.validar_cnpj("11.222.333/0001-82"))

    def test_cpf_cnpj_vazio_e_tamanho_errado(self):
        self.assertIsNone(nz.validar_cpf_cnpj(""))
        self.assertFalse(nz.validar_cpf_cnpj("123"))

    def test_numero_br(self):
        self.assertAlmostEqual(nz.numero_br("3.823,9140"), 3823.914)
        self.assertAlmostEqual(nz.numero_br("483.8562"), 483.8562)
        self.assertAlmostEqual(nz.numero_br(100), 100.0)
        self.assertIsNone(nz.numero_br("abc"))
        self.assertIsNone(nz.numero_br(None))


class TestConfigDominialidade(unittest.TestCase):
    def _grava(self, d):
        path = os.path.join(tempfile.gettempdir(), "proj_test_m1.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(d, f)
        return path

    def test_so_shape_sem_fazendas(self):
        proj = load_projeto(self._grava(_projeto_minimo()))
        self.assertEqual(proj.fazendas, [])

    def test_dominialidade_carregada(self):
        d = _projeto_minimo(dominialidade={
            "registro": {"cri": "Vila Rica/MT", "cns": "12.345-6"},
            "matriculas": [{"numero": "7.569", "denominacao": "Fazenda X",
                            "proprietario": "Fulana", "cpf_cnpj": "529.982.247-25",
                            "area_ha": 3823.9}],
        })
        proj = load_projeto(self._grava(d))
        self.assertEqual(proj.dominialidade.cri, "Vila Rica/MT")
        self.assertEqual(proj.dominialidade.matriculas[0].numero, "7.569")
        self.assertAlmostEqual(proj.dominialidade.matriculas[0].area_ha, 3823.9)

    def test_uf_fora_de_mt_rejeitada(self):
        d = _projeto_minimo()
        d["municipio"]["uf"] = "PA"
        with self.assertRaises(ProjetoError):
            load_projeto(self._grava(d))


class TestSalvarDominialidade(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.gettempdir(), "proj_test_salvar.json")
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(_projeto_minimo(), f)

    def tearDown(self):
        os.remove(self.path)

    def test_salva_matriculas_conferidas(self):
        salvar_dominialidade(self.path, {"cri": "Vila Rica/MT", "cns": "9"},
                             [{"numero": "7.569", "denominacao": "Fazenda X",
                               "proprietario": "Fulana", "cpf_cnpj": "529.982.247-25",
                               "area_ha": "3.823,9140"}])
        with open(self.path, encoding="utf-8") as f:
            d = json.load(f)
        self.assertEqual(d["dominialidade"]["registro"]["cri"], "Vila Rica/MT")
        self.assertAlmostEqual(d["dominialidade"]["matriculas"][0]["area_ha"], 3823.914)
        # e o projeto recarrega com o bloco novo
        proj = load_projeto(self.path)
        self.assertEqual(proj.dominialidade.matriculas[0].numero, "7.569")

    def test_rejeita_sem_numero(self):
        with self.assertRaises(MatriculasError):
            salvar_dominialidade(self.path, {}, [{"denominacao": "X"}])

    def test_rejeita_cpf_invalido(self):
        with self.assertRaises(MatriculasError):
            salvar_dominialidade(self.path, {}, [{"numero": "1", "cpf_cnpj": "111.111.111-11"}])


if __name__ == "__main__":
    unittest.main()
