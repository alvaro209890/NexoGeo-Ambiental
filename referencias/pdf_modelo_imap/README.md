# PDFs-modelo IMAP (referência visual oficial)

Mapas **reais do cliente**, feitos à mão no ArcMap (análise Lauri — Fazenda Trevisol
Lote 65 + Lote Rural nº 66-A, Querência/MT, A4 paisagem). São o **gabarito visual** do
renderer flagship: todo ajuste de layout em `core/nexomap_renderer.py` deve ser comparado
lado a lado com estes arquivos. Guia do padrão extraído deles:
[`docs/PADRAO_IMAP_RENDERER.md`](../../docs/PADRAO_IMAP_RENDERER.md).

> A junção de todos num único PDF existe em `referencias/Mapas_unidos.pdf`
> (não duplicada aqui). O perfil de conformidade usado pelo `validar_contra_modelo`
> está em `referencias/perfil_imap.json`.

## Conteúdo

### Série Dinâmica (temporal, satélite + AVN/AC/AUAS + tabela)
| Arquivo | Observação |
|---|---|
| `Dinamica_2000_v2.pdf`, `Dinamica_2005.pdf`, `Dinamica_2009.pdf`, `Dinamica_2013.pdf`, `Dinamica_2015.pdf` | Landsat, anos históricos |
| `Dinamica_2008_LANDSAT.pdf`, `Dinamica_2008_AC.pdf`, `Dinamica_2008_V2.pdf` | Variações do marco 2008 (Landsat / com AC / revisada) |
| `Dinamica_2012.pdf`, `Dinamica_2017.pdf`, `Dinamica_2019.pdf`, `Dinamica_2023.pdf`, `Dinamica_2025.pdf` | Série intermediária |
| `Dinamica_2026.pdf` | **Modelo principal** usado na calibração do renderer |
| `Dinamica_2026_quantitativos.pdf` | Mesmo mapa com a tabela de quantitativos (modelo da tabela) |

### Temáticos
| Arquivo | Camadas de referência |
|---|---|
| `Tipologia.pdf` | Tipologia vegetal (fundo WMS SEMA/Radam, verde temático) |
| `Terras_Indigenas.pdf` | Terras indígenas FUNAI |
| `Unidade_de_Conservação.pdf` | Unidades de conservação |
| `Embargos_IBAMA.pdf` | Embargos IBAMA |
| `Embargos_SEMA_SIGA_Poligono.pdf` | Embargos SEMA/SIGA (polígonos) |
| `Autos_de_infração.pdf` | Autos de infração |
| `Alertas_PRODES_VF_2.pdf` | Alertas PRODES/INPE |
| `Alertas_MAPBIOMAS_2.pdf` | Alertas MapBiomas |
| `Area_de_plantio_com_estrada_sem_tabela_v3.pdf` | Área de plantio + estradas (sem tabela) |
| `Mapa_AIR_SIGEF_Simplificado.pdf`, `Mapa_AIR_SIGEF_Sobreposicoes.pdf` | AIR × SIGEF (fundiário) |

## O que conferir ao comparar um mapa gerado

1. Grade DMS: rótulos `52°15'0"W` (~3 por eixo), ticks pretos, **sem linhas internas**.
2. Moldura preta grossa; caixa de título branca com borda preta no topo-centro.
3. Seta de norte ArcMap (triângulo preto/branco) no canto superior direito.
4. Lotes: vermelho `#c00000` / azul `#00b0f0` grossos, rótulo branco com halo (nome + matrícula).
5. Tabela branca com grade preta, cabeçalho e TOTAL em negrito, flutuando no mapa.
6. Faixa inferior: minimapa de municípios (laranja + caixinha MT + retângulo vermelho),
   METADADOS IMAGEM centralizado, Legenda com retângulos vazados, logo IMAP.
7. Sem barra de escala e sem rodapé "Fontes:".
