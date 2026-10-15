"""Testes das restrições de material por transportadora e da renderização dos cartões/TOP 3."""
import re
from unittest import mock

import pytest

import restricoes_material as rm
from restricoes_material import AVISO_MATERIAL, aplicar_restricoes_material, avaliar_material


def _res(nome, valor=100.0, prazo=3):
    return {"Transportadora": nome, "Valor Frete (R$)": valor, "Prazo (Dias Úteis)": prazo,
            "Atendida": True, "Peso Tarifado": "50.00 kg"}


# ---------- 3. NÃO LEVA exclui ----------

def test_nao_leva_exclui():
    assert avaliar_material("Braspress", ["Bobina"]) == (True, None)
    out = aplicar_restricoes_material([_res("Braspress"), _res("Coopex")], ["Bobina"])
    assert [r["Transportadora"] for r in out] == ["Coopex"]


def test_nome_com_acento_e_caixa_diferente_ainda_casa_com_a_regra():
    # 'ENVIA RÁPIDO' (nome retornado pela tabela) x chave 'ENVIA RAPIDO'
    assert avaliar_material("ENVIA RÁPIDO", ["Pallet"]) == (True, None)
    assert avaliar_material("Expresso São Miguel", ["Bobina"]) == (True, None)
    assert avaliar_material("VIAÇÃO GARCIA 24H", ["Pallet"]) == (True, None)


# ---------- 4. CONSULTAR REGIAO / NÃO INFORMADO mantêm com aviso ----------

def test_consultar_regiao_mantem_com_aviso():
    assert avaliar_material("PATRUS", ["Pallet"]) == (False, AVISO_MATERIAL)
    assert avaliar_material("Reunidas Cargas", ["Bobina"]) == (False, AVISO_MATERIAL)


def test_nao_informado_transportadora_sem_regra_mantem_com_aviso():
    # TW não possui linha na tabela contratual -> NÃO INFORMADO para Pallet/Bobina
    assert avaliar_material("TW TRANSPORTES", ["Pallet"]) == (False, AVISO_MATERIAL)
    out = aplicar_restricoes_material([_res("TW TRANSPORTES")], ["Bobina"])
    assert len(out) == 1 and out[0]["Aviso_Material"] == "⚠️ Confirme se a transportadora transporta este material."


def test_leva_nao_exibe_aviso():
    out = aplicar_restricoes_material([_res("Coopex")], ["Pallet"])
    assert len(out) == 1 and "Aviso_Material" not in out[0]


# ---------- 5. Materiais misturados ----------

def test_materiais_misturados_qualquer_nao_leva_exclui():
    # Braspress: Pallet LEVA, Bobina NÃO LEVA -> excluída se houver Bobina
    assert avaliar_material("Braspress", ["Pallet", "Bobina"])[0] is True
    assert avaliar_material("Braspress", ["Pallet"]) == (False, None)


def test_materiais_misturados_aviso_se_qualquer_consultar():
    # Reunidas: Pallet LEVA, Bobina CONSULTAR REGIAO
    assert avaliar_material("Reunidas Cargas", ["Pallet", "Bobina"]) == (False, AVISO_MATERIAL)
    assert avaliar_material("Reunidas Cargas", ["Pallet"]) == (False, None)


def test_nao_leva_prevalece_sobre_aviso():
    assert avaliar_material("Braspress", ["Pallet", "Bobina", "Outro"])[0] is True


# ---------- 6. 'Outro' e materiais sem regra não filtram nem avisam ----------

def test_outro_nao_filtra_nem_avisa():
    for nome in ["Braspress", "PATRUS", "TW TRANSPORTES", "ENVIA RÁPIDO", "Expresso São Miguel"]:
        assert avaliar_material(nome, ["Outro"]) == (False, None), nome
    assert avaliar_material("Braspress", []) == (False, None)


def test_material_sem_regra_contratual_nao_inventa_restricao():
    # Caixa e Saco não têm regra cadastrada para nenhuma transportadora
    for nome in ["Braspress", "TW TRANSPORTES", "Expresso São Miguel"]:
        assert avaliar_material(nome, ["Caixa"]) == (False, None), nome
        assert avaliar_material(nome, ["Saco", "Outro"]) == (False, None), nome


def test_outro_misturado_avalia_apenas_os_demais():
    assert avaliar_material("Braspress", ["Outro", "Bobina"])[0] is True


def test_nao_atendida_e_princesa_nao_sao_alteradas():
    nao_atendida = {"Transportadora": "Braspress", "Atendida": False, "Valor Frete (R$)": None}
    princesa = _res("PRINCESA DOS CAMPOS")
    out = aplicar_restricoes_material([nao_atendida, princesa], ["Bobina"])
    assert out == [nao_atendida, princesa] and "Aviso_Material" not in princesa


def test_tabela_contratual_inalterada():
    assert len(rm.RESTRICOES_MATERIAIS) == 41
    assert rm.RESTRICOES_MATERIAIS["BRASPRESS"] == {"Pallet": "LEVA", "Bobina": "NÃO LEVA"}
    assert rm.RESTRICOES_MATERIAIS["REUNIDAS CARGAS"] == {"Pallet": "LEVA", "Bobina": "CONSULTAR REGIAO"}


# ---------- 7. Cartões e TOP 3 continuam sendo gerados (e mostram o aviso só no cartão) ----------

def _cotacao(resultados):
    return {
        "data_hora": "13/10/2026 17:00:00", "remetente": "26434839000121", "destinatario": "11222333000144",
        "origem_cep": "86071000", "origem_texto": "Londrina/PR", "destino_cep": "89240000",
        "destino_texto": "Sao Francisco do Sul/SC", "uf_dest": "SC", "cidade_dest": "Sao Francisco do Sul",
        "peso": 50.0, "volume_m3": 0.12, "peso_cubado": 36.0, "peso_tarifado": 50.0, "valor_nf": 1000.0,
        "volumes_qtd": 2, "volumes_data": [], "resultados": resultados, "obs": "",
    }


@pytest.fixture
def app_renderizado():
    from streamlit.testing.v1 import AppTest
    import db_historico

    brutos = [_res("Coopex", 100.0, 3), _res("TW TRANSPORTES", 110.0, 4), _res("Braspress", 90.0, 2),
              _res("ALFA TRANSPORTES", 120.0, 5)]
    filtrados = aplicar_restricoes_material(brutos, ["Bobina"])  # Braspress sai; TW fica com aviso

    with mock.patch.object(db_historico, "init_db", lambda: None), \
         mock.patch.object(db_historico, "obter_cotacoes", lambda *a, **k: []):
        at = AppTest.from_file("main.py", default_timeout=60)
        at.session_state["user"] = {"id": 1, "nome": "t", "email": "t@t", "role": "ADMIN", "status": "ATIVO"}
        at.session_state["cookie_init_done"] = True
        at.session_state["ultima_cotacao"] = _cotacao(filtrados)
        at.run()
        yield at, filtrados


def test_cartoes_e_top3_sao_gerados_com_aviso_somente_no_cartao(app_renderizado):
    at, filtrados = app_renderizado
    assert not at.exception, [e.value for e in at.exception]
    assert "Braspress" not in [r["Transportadora"] for r in filtrados]

    cartoes = [m.value for m in at.markdown if "card-ranking-pos" in m.value]
    assert len(cartoes) == 3  # TOP 3 gerado

    com_aviso = [c for c in cartoes if AVISO_MATERIAL in c]
    assert len(com_aviso) == 1  # só o cartão da TW (110,00 -> 2º lugar)
    assert "card-ranking-pos2" in com_aviso[0]

    # sem banner global: nenhum outro markdown traz o aviso
    outros = [m.value for m in at.markdown if AVISO_MATERIAL in m.value and "card-ranking-pos" not in m.value]
    assert outros == []
    # sem coluna extra de avisos na tabela
    for df in at.dataframe:
        assert not any("aviso" in str(c).lower() for c in df.value.columns)
