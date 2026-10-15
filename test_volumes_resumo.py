"""Testes do resumo de volumes (cartões), textos do campo 'Outro', WhatsApp e Nova Cotação."""
import os
import re

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import utils
import whatsapp_generator

MAIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")

LINHA_OUTRO = {"Tipo": "Outro", "Qtd": 22, "Alt (cm)": 22.0, "Larg (cm)": 22.0, "Comp (cm)": 22.0, "Peso Total (kg)": 20.0}
LINHA_CAIXA = {"Tipo": "Caixa", "Qtd": 10, "Alt (cm)": 11.0, "Larg (cm)": 11.0, "Comp (cm)": 11.0, "Peso Total (kg)": 60.0}


# ---------- funções puras ----------

def _resumo(linhas):
    return utils.resumir_volumes(utils.sanear_volumes(pd.DataFrame(linhas)))


def test_cenario_da_captura_funcao_pura():
    r = _resumo([LINHA_OUTRO, LINHA_CAIXA])
    assert r["qtd"] == 32
    assert r["peso_real"] == pytest.approx(80.0)
    assert r["volume_m3"] == pytest.approx(0.2476, abs=5e-5)
    assert r["peso_cubado"] == pytest.approx(0.247566 * 300)
    assert r["peso_tarifado"] == pytest.approx(80.0)


def test_sanitizacao_aceita_tipos_numpy_texto_e_nan():
    df = pd.DataFrame([
        {"Tipo": "Caixa", "Qtd": pd.Series([3], dtype="Int64")[0], "Alt (cm)": "10,5", "Larg (cm)": None,
         "Comp (cm)": float("nan"), "Peso Total (kg)": "5,5"},
    ])
    s = utils.sanear_volumes(df)
    assert s.loc[0, "Qtd"] == 3 and s.loc[0, "Alt (cm)"] == 10.5 and s.loc[0, "Peso Total (kg)"] == 5.5
    assert s.loc[0, "Larg (cm)"] == 0 and s.loc[0, "Comp (cm)"] == 0


def test_linha_com_qtd_zero_nao_contribui():
    r = _resumo([LINHA_CAIXA, dict(LINHA_OUTRO, Qtd=0)])  # peso 20 kg e dimensões, mas Qtd 0
    assert r["qtd"] == 10
    assert r["peso_real"] == pytest.approx(60.0)
    assert r["volume_m3"] == pytest.approx(10 * 11 ** 3 / 1e6)
    assert r["tipos"] == ["Caixa"]


# ---------- AppTest: tela real ----------

def _chave(at):
    return f"tabela_volumes_fixa_{at.session_state['editor_version'] if 'editor_version' in at.session_state else 0}"


def _cartoes(at):
    out = []
    for m in at.markdown:
        if "Volumes / Cubagem" in m.value:
            out = re.findall(r">\s*([\d.,]+)\s*(?:<span[^>]*>\s*(?:vols|kg)|m³)", m.value)
    return out  # [volumes, m3, peso real, peso cobrado]


def _editor(at, edited=None, added=None, deleted=None):
    at.session_state[_chave(at)] = {
        "edited_rows": edited or {}, "added_rows": added or [], "deleted_rows": deleted or [],
    }
    at.run()
    assert not at.exception, [e.value for e in at.exception]


@pytest.fixture
def app():
    at = AppTest.from_file(MAIN, default_timeout=90)
    at.session_state["user"] = {"id": 1, "nome": "t", "email": "t@t", "role": "ADMIN", "status": "ATIVO"}
    at.session_state["cookie_init_done"] = True
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _valores(m3):
    return f"{m3:.4f}"


def test_cenario_da_captura_na_tela_e_tab_nao_apaga(app):
    _editor(app, edited={0: LINHA_OUTRO}, added=[LINHA_CAIXA])
    assert _cartoes(app) == ["32", "0.2476", "80.00", "80.00"]
    app.run()  # Tab/rerun sem alteração: nada some
    assert _cartoes(app) == ["32", "0.2476", "80.00", "80.00"]


def test_alterar_qtd_e_peso_atualiza_todos_os_cartoes(app):
    _editor(app, edited={0: LINHA_OUTRO}, added=[LINHA_CAIXA])
    _editor(app, edited={0: dict(LINHA_OUTRO, Qtd=1, **{"Peso Total (kg)": 5.0})}, added=[LINHA_CAIXA])
    vols, m3, real, cobrado = _cartoes(app)
    esperado_m3 = (22 ** 3 + 10 * 11 ** 3) / 1e6
    assert (vols, real) == ("11", "65.00")
    assert m3 == _valores(esperado_m3)
    assert cobrado == "65.00"


def test_qtd_zero_nao_conta_peso_nem_cubagem(app):
    _editor(app, edited={0: dict(LINHA_OUTRO, Qtd=0)}, added=[LINHA_CAIXA])
    assert _cartoes(app) == ["10", _valores(10 * 11 ** 3 / 1e6), "60.00", "60.00"]


def test_adicionar_e_excluir_linhas_mantem_totais(app):
    extra = {"Tipo": "Pallet", "Qtd": 1, "Alt (cm)": 100.0, "Larg (cm)": 100.0, "Comp (cm)": 100.0, "Peso Total (kg)": 10.0}
    _editor(app, edited={0: LINHA_OUTRO}, added=[LINHA_CAIXA, extra])
    vols, m3, real, cobrado = _cartoes(app)
    assert (vols, real) == ("33", "90.00") and m3 == _valores((22 ** 4 + 10 * 11 ** 3 + 1e6) / 1e6)
    assert cobrado == f"{(22 ** 4 + 10 * 11 ** 3 + 1e6) / 1e6 * 300:.2f}"  # cubado (374,27) > real (90)
    # exclui a linha original (índice 0): sobram as adicionadas
    _editor(app, added=[LINHA_CAIXA, extra], deleted=[0])
    assert _cartoes(app)[0] == "11" and _cartoes(app)[2] == "70.00"
    # remove a linha extra
    _editor(app, added=[LINHA_CAIXA], deleted=[0])
    assert _cartoes(app) == ["10", _valores(10 * 11 ** 3 / 1e6), "60.00", "60.00"]


def test_textos_do_campo_descricao_de_outro(app):
    _editor(app, edited={0: LINHA_OUTRO}, added=[LINHA_CAIXA])
    campos = [t for t in app.text_input if (t.label or "").startswith("Descrição do tipo de volume")]
    assert len(campos) == 1  # só a linha do tipo Outro
    c = campos[0]
    assert c.label.startswith("Descrição do tipo de volume (opcional)")
    assert c.placeholder == "Ex.: engradado, tambor ou embalagem especial"
    assert any("não o produto dentro dele" in x.value and "tipo Caixa" in x.value for x in app.caption)
    assert not [t for t in app.text_input if "Descrição do material" in (t.label or "")]


def test_descricao_de_outro_vai_para_o_whatsapp(app):
    _editor(app, edited={0: LINHA_OUTRO}, added=[LINHA_CAIXA])
    campo = [t for t in app.text_input if (t.label or "").startswith("Descrição do tipo de volume")][0]
    campo.set_value("engradado de madeira").run()
    volumes = app.session_state["volumes_data"]
    assert volumes[0]["descricao"] == "engradado de madeira"
    msg = whatsapp_generator.gerar_mensagem_wa({"volumes_data": volumes}, 100.0)
    assert "Outro (engradado de madeira): 22 volumes" in msg
    assert "Caixa: 10 volumes" in msg


def test_nova_cotacao_limpa_todos_os_indicadores(app):
    _editor(app, edited={0: LINHA_OUTRO}, added=[LINHA_CAIXA])
    assert _cartoes(app)[0] == "32"
    btn = [b for b in app.sidebar.button if b.key == "nav_Nova Cotação"][0]
    btn.click().run()
    assert not app.exception, [e.value for e in app.exception]
    assert _cartoes(app) == ["0", "0.0000", "0.00", "0.00"]


# ---------- Dados da captura 2: 1 linha, Caixa 2 x 22x22x22, 60 kg ----------

CAIXA_2 = {"Tipo": "Caixa", "Qtd": 2, "Alt (cm)": 22.0, "Larg (cm)": 22.0, "Comp (cm)": 22.0, "Peso Total (kg)": 60.0}


def test_utils_expoe_funcoes_usadas_pelo_main():
    for nome in ("safe_float", "safe_int", "sanear_volumes", "resumir_volumes", "FATOR_CUBAGEM"):
        assert hasattr(utils, nome), nome


def test_safe_float_none_nan_numeros_e_virgula():
    assert utils.safe_float(None) == 0.0 and utils.safe_float(float("nan")) == 0.0
    assert utils.safe_float(7) == 7.0 and utils.safe_float(2.5) == 2.5
    assert utils.safe_float("12,75") == 12.75 and utils.safe_float(" ") == 0.0
    assert utils.safe_int("3") == 3 and utils.safe_int(2.0) == 2


def test_captura_caixa_2_na_tela_sem_erro_tab_e_nova_cotacao(app):
    _editor(app, edited={0: CAIXA_2})
    assert not [e for e in app.error if "Erro na tabela" in e.value]
    assert _cartoes(app) == ["2", "0.0213", "60.00", "60.00"]
    app.run()  # Tab
    assert _cartoes(app) == ["2", "0.0213", "60.00", "60.00"]
    _editor(app, edited={0: dict(CAIXA_2, Qtd=3, **{"Peso Total (kg)": 90.0})})
    assert _cartoes(app) == ["3", "0.0319", "90.00", "90.00"]
    btn = [b for b in app.sidebar.button if b.key == "nav_Nova Cotação"][0]
    btn.click().run()
    assert _cartoes(app) == ["0", "0.0000", "0.00", "0.00"]
