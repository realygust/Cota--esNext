"""Testes das consultas externas de CEP/CNPJ: cache, timeouts e fallbacks (chamadas simuladas)."""
from unittest import mock

import pytest
import requests

import utils


def _resp(status=200, payload=None):
    r = mock.Mock()
    r.status_code = status
    r.json.return_value = payload if payload is not None else {}
    return r


VIACEP_OK = {"uf": "PR", "localidade": "Londrina", "bairro": "Centro", "logradouro": "Rua X"}
BRASILAPI_CEP_OK = {"state": "SC", "city": "Joinville", "neighborhood": "Centro", "street": "Rua Y"}
BRASILAPI_CNPJ_OK = {"razao_social": "EMPRESA TESTE LTDA", "logradouro": "Rua A", "numero": "10",
                     "bairro": "Centro", "municipio": "Londrina", "uf": "PR", "cep": "86010-070"}
RECEITAWS_OK = {"status": "OK", "nome": "EMPRESA RECEITA LTDA", "logradouro": "Rua B", "numero": "20",
                "bairro": "Centro", "municipio": "Curitiba", "uf": "PR", "cep": "80010-000"}


@pytest.fixture(autouse=True)
def limpar_caches():
    utils._buscar_cep_valido.clear()
    utils._buscar_empresa_cnpj_valida.clear()
    utils._NEGATIVOS.clear()
    yield
    utils._buscar_cep_valido.clear()
    utils._buscar_empresa_cnpj_valida.clear()
    utils._NEGATIVOS.clear()


# ---------- 1. Consulta repetida não gera chamadas externas desnecessárias ----------

def test_cep_repetido_usa_cache():
    with mock.patch.object(utils.requests, "get", return_value=_resp(200, VIACEP_OK)) as g:
        a = utils.buscar_cep("86071000")
        b = utils.buscar_cep("86071-000")  # mesma consulta, formato diferente
    assert a == b and a["cidade"] == "Londrina"
    assert g.call_count == 1


def test_cnpj_repetido_usa_cache():
    with mock.patch.object(utils.requests, "get", return_value=_resp(200, BRASILAPI_CNPJ_OK)) as g:
        a = utils.buscar_empresa_cnpj("11.222.333/0001-44")
        b = utils.buscar_empresa_cnpj("11222333000144")
    assert a["ok"] and a == b
    assert g.call_count == 1


def test_cep_invalido_curto_nao_consulta_api():
    with mock.patch.object(utils.requests, "get") as g:
        assert utils.buscar_cep("123") is None
        assert utils.buscar_cep("") is None
    g.assert_not_called()


def test_negativo_nao_repete_consulta_dentro_do_ttl_curto():
    respostas = [_resp(200, {"erro": True}), _resp(404)]
    with mock.patch.object(utils.requests, "get", side_effect=respostas) as g:
        assert utils.buscar_cep("00000000") is None
        assert utils.buscar_cep("00000000") is None  # rerun logo em seguida: sem nova consulta
    assert g.call_count == 2  # ViaCEP + BrasilAPI da 1ª chamada apenas


# ---------- Resultado negativo / erro temporário NÃO fica em cache por 1h ----------

def test_erro_temporario_cep_nao_fica_em_cache():
    with mock.patch.object(utils.requests, "get", side_effect=requests.Timeout("t")):
        assert utils.buscar_cep("86071000") is None
    # TTL curto vence e a API volta: deve consultar de novo e devolver resultado válido
    utils._NEGATIVOS.clear()
    with mock.patch.object(utils.requests, "get", return_value=_resp(200, VIACEP_OK)) as g:
        res = utils.buscar_cep("86071000")
    assert res and res["uf"] == "PR"
    assert g.call_count == 1


def test_negativo_expira_apos_ttl():
    chave = ("cep", "86071000")
    utils._registrar_negativo(chave)
    assert utils._negativo_ativo(chave)
    utils._NEGATIVOS[chave] = 0  # já expirado
    assert not utils._negativo_ativo(chave)


def test_cnpj_falha_nao_fica_em_cache_e_recupera():
    with mock.patch.object(utils.requests, "get", side_effect=requests.Timeout("t")):
        r = utils.buscar_empresa_cnpj("11222333000144")
    assert r["ok"] is False
    utils._NEGATIVOS.clear()
    with mock.patch.object(utils.requests, "get", return_value=_resp(200, BRASILAPI_CNPJ_OK)):
        r2 = utils.buscar_empresa_cnpj("11222333000144")
    assert r2["ok"] is True and r2["razao"] == "EMPRESA TESTE LTDA"


# ---------- 2. Timeouts e falhas acionam fallbacks, sem espera indefinida ----------

def test_viacep_timeout_aciona_brasilapi():
    def fake_get(url, **kw):
        if "viacep" in url:
            raise requests.Timeout("lento")
        return _resp(200, BRASILAPI_CEP_OK)

    with mock.patch.object(utils.requests, "get", side_effect=fake_get):
        res = utils.buscar_cep("89200000")
    assert res and res["uf"] == "SC" and res["cidade"] == "Joinville"


def test_brasilapi_cnpj_timeout_aciona_receitaws():
    def fake_get(url, **kw):
        if "brasilapi" in url:
            raise requests.Timeout("lento")
        return _resp(200, RECEITAWS_OK)

    with mock.patch.object(utils.requests, "get", side_effect=fake_get):
        r = utils.buscar_empresa_cnpj("11222333000144")
    assert r["ok"] and r["razao"] == "EMPRESA RECEITA LTDA"


def test_brasilapi_cnpj_http_500_aciona_receitaws():
    def fake_get(url, **kw):
        if "brasilapi" in url:
            return _resp(500)
        return _resp(200, RECEITAWS_OK)

    with mock.patch.object(utils.requests, "get", side_effect=fake_get):
        assert utils.buscar_empresa_cnpj("11222333000144")["ok"]


def test_todas_requisicoes_externas_tem_timeout_explicito():
    chamadas = []

    def fake_get(url, **kw):
        chamadas.append((url, kw.get("timeout")))
        return _resp(500)

    with mock.patch.object(utils.requests, "get", side_effect=fake_get):
        utils.buscar_cep("86071000")
        utils.buscar_empresa_cnpj("11222333000144")
    assert len(chamadas) == 4  # ViaCEP, BrasilAPI CEP, BrasilAPI CNPJ, ReceitaWS
    for url, timeout in chamadas:
        assert isinstance(timeout, tuple) and len(timeout) == 2, url
        connect, read = timeout
        assert 0 < connect <= 5 and 0 < read <= 10, (url, timeout)


def test_api_de_frete_usa_timeout_de_conexao(monkeypatch):
    import api_services as ap

    visto = {}

    def fake_post(url, **kw):
        visto["timeout"] = kw.get("timeout")
        raise requests.ConnectTimeout("sem rota")

    monkeypatch.setattr(ap.requests, "post", fake_post)
    cub = [{"Altura": 0.3, "Largura": 0.4, "Comprimento": 0.5, "Volumes": 1}]
    r1 = ap.cotar_braspress("86071000", "89240000", 10.0, 1000.0, cub, "11222333000144", "55666777000188")
    assert r1["Valor Frete (R$)"] is None and isinstance(visto["timeout"], tuple)

    visto.clear()
    r2 = ap.cotar_ssw_wsdl("Coopex", "COP", "u", "s", "86071000", "89240000", 10.0, 1000.0, cub,
                           "11222333000144", "55666777000188", 1)
    assert r2["Valor Frete (R$)"] is None and isinstance(visto["timeout"], tuple)


# ---------- CEP: "não encontrado" x "serviço indisponível" ----------

def test_cep_viacep_conexao_falha_brasilapi_funciona():
    def fake_get(url, **kw):
        if "viacep" in url:
            raise requests.ConnectionError("[Errno 113] No route to host")
        return _resp(200, BRASILAPI_CEP_OK)

    with mock.patch.object(utils.requests, "get", side_effect=fake_get):
        res, status = utils.consultar_cep("86072000")
    assert status == utils.CEP_OK and res["cidade"] == "Joinville"


def test_cep_viacep_5xx_brasilapi_funciona():
    def fake_get(url, **kw):
        if "viacep" in url:
            return _resp(503)
        return _resp(200, BRASILAPI_CEP_OK)

    with mock.patch.object(utils.requests, "get", side_effect=fake_get):
        res, status = utils.consultar_cep("86072000")
    assert status == utils.CEP_OK and res["uf"] == "SC"


def test_cep_ambas_falham_conectividade_e_indisponivel_sem_cache_longo():
    with mock.patch.object(utils.requests, "get", side_effect=requests.ConnectionError("sem rota")) as g:
        res, status = utils.consultar_cep("86072000")
        res2, status2 = utils.consultar_cep("86072000")  # rerun: sem novas chamadas
    assert res is None and status == utils.CEP_INDISPONIVEL == status2
    assert g.call_count == 2
    # passado o TTL curto, nova tentativa e recuperação (nada de falha guardada por 1h)
    utils._NEGATIVOS.clear()
    with mock.patch.object(utils.requests, "get", return_value=_resp(200, VIACEP_OK)):
        res3, status3 = utils.consultar_cep("86072000")
    assert status3 == utils.CEP_OK and res3["uf"] == "PR"


def test_cep_viacep_ok_negativo_e_brasilapi_5xx_ainda_e_nao_encontrado():
    def fake_get(url, **kw):
        return _resp(200, {"erro": True}) if "viacep" in url else _resp(500)

    with mock.patch.object(utils.requests, "get", side_effect=fake_get):
        assert utils.consultar_cep("00000000") == (None, utils.CEP_NAO_ENCONTRADO)


def test_cep_viacep_5xx_e_brasilapi_404_nao_afirma_inexistente():
    def fake_get(url, **kw):
        return _resp(502) if "viacep" in url else _resp(404)

    with mock.patch.object(utils.requests, "get", side_effect=fake_get):
        assert utils.consultar_cep("86072000") == (None, utils.CEP_INDISPONIVEL)


def test_cep_realmente_nao_encontrado():
    def fake_get(url, **kw):
        return _resp(200, {"erro": True}) if "viacep" in url else _resp(404)

    with mock.patch.object(utils.requests, "get", side_effect=fake_get):
        assert utils.consultar_cep("00000000") == (None, utils.CEP_NAO_ENCONTRADO)


def test_cep_indisponivel_permite_preenchimento_manual_sem_novas_chamadas():
    with mock.patch.object(utils.requests, "get", side_effect=requests.Timeout("t")) as g:
        res, status = utils.consultar_cep("86072000")
        # Fluxo do main.py: sem dados e CEP de 8 dígitos -> UF/cidade manuais montam info_d
        man_uf, man_cidade = "PR", "Londrina"
        info_d = None
        if not res and status in (utils.CEP_INDISPONIVEL, utils.CEP_NAO_ENCONTRADO):
            info_d = {"ok": True, "cidade": man_cidade, "uf": man_uf}
        utils.consultar_cep("86072000")  # reruns durante a digitação manual
    assert info_d == {"ok": True, "cidade": "Londrina", "uf": "PR"}
    assert g.call_count == 2  # só a 1ª consulta (ViaCEP + BrasilAPI)
