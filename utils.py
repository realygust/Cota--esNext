import pandas as pd
import requests
import json
import os
from datetime import datetime
import time
import re
import streamlit as st
import html
from config import HISTORICO_FILE, TABELAS, CAPITAIS, BROWSER_USER_AGENT

def _secret(chave, padrao=""):
    try:
        if hasattr(st, "secrets") and chave in st.secrets:
            return st.secrets[chave]
    except Exception:
        pass
    return padrao

import db_historico
# Inicialização do banco delegada exclusivamente ao main.py

def carregar_historico():
    # Depreciado, use db_historico.obter_cotacoes() diretamente se possível
    # Mas para retrocompatibilidade provisória:
    return db_historico.obter_cotacoes()

def salvar_historico_item(item, owner_user_id=None):
    db_historico.salvar_cotacao(item, owner_user_id)

def limpar_historico_arquivo():
    # Não vamos mais limpar fisicamente, mas manter a função caso o main.py chame
    pass

def formatar_moeda(valor):
    if valor is None or str(valor).strip() == '' or str(valor).lower() == 'nan':
        return "Não informado"
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except ValueError:
        return "Não informado"

def limpar_mensagem_ssw(texto):
    if not texto:
        return ""
    texto = html.unescape(str(texto))
    texto = re.sub(r"<[^>]+>", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()

def limpar_documento(valor):
    return re.sub(r"\D", "", str(valor or ""))

def limpar_cep(valor):
    return int(re.sub(r"\D", "", str(valor or "0")))


# ---------- Volumes: sanitização e totais (fonte única para cartões, confirmação e cotação) ----------

COLUNAS_VOLUMES = ["Tipo", "Qtd", "Alt (cm)", "Larg (cm)", "Comp (cm)", "Peso Total (kg)"]
FATOR_CUBAGEM = 300


def safe_float(val):
    try:
        if val is None or pd.isna(val):
            return 0.0
    except (TypeError, ValueError):
        pass
    if isinstance(val, bool):
        return float(val)
    try:
        return float(val)  # int, float, numpy.*, Decimal
    except (TypeError, ValueError):
        pass
    s = str(val).strip().replace(",", ".")
    try:
        return float(s) if s else 0.0
    except ValueError:
        return 0.0


def safe_int(val):
    return int(safe_float(val))


def sanear_volumes(df):
    """DataFrame editado -> DataFrame sanitizado (colunas nomeadas, valores numéricos válidos e >= 0)."""
    df_calc = (df if df is not None else pd.DataFrame()).copy().reset_index(drop=True)
    for c in COLUNAS_VOLUMES:
        if c not in df_calc.columns:
            df_calc[c] = "Outro" if c == "Tipo" else 0.0
    df_calc["Qtd"] = df_calc["Qtd"].apply(lambda v: max(safe_int(v), 0))
    for c in ("Alt (cm)", "Larg (cm)", "Comp (cm)", "Peso Total (kg)"):
        df_calc[c] = df_calc[c].apply(lambda v: max(safe_float(v), 0.0))
    df_calc["Tipo"] = df_calc["Tipo"].fillna("Outro").astype(str).str.strip()
    df_calc.loc[df_calc["Tipo"] == "", "Tipo"] = "Outro"
    return df_calc


def resumir_volumes(df_sanitizado, fator=FATOR_CUBAGEM):
    """Totais a partir do DataFrame sanitizado. Linhas com Qtd = 0 não contribuem com nada."""
    ativos = df_sanitizado[df_sanitizado["Qtd"] > 0]
    qtd = int(ativos["Qtd"].sum())
    peso_real = float(ativos["Peso Total (kg)"].sum())
    volume_m3 = float((ativos["Qtd"] * ativos["Alt (cm)"] * ativos["Larg (cm)"] * ativos["Comp (cm)"]).sum() / 1000000.0)
    peso_cubado = volume_m3 * fator
    tipos = ativos["Tipo"].dropna().unique().tolist() or ["Outro"]
    return {
        "qtd": qtd,
        "peso_real": peso_real,
        "volume_m3": volume_m3,
        "peso_cubado": peso_cubado,
        "peso_tarifado": max(peso_real, peso_cubado),
        "e_cubado": peso_cubado > peso_real,
        "tipos": tipos,
    }

def xml_escape(valor):
    return html.escape(str(valor or ""), quote=True)

# Resultados negativos (CEP/CNPJ não localizado) e falhas temporárias das APIs NÃO entram no
# cache de 1h: ficam retidos só por alguns segundos, evitando repetir a consulta externa a
# cada rerun do Streamlit sem manter um erro temporário como se fosse resultado válido.
_NEGATIVO_TTL_S = 30
_NEGATIVOS = {}


def _negativo_ativo(chave):
    expira = _NEGATIVOS.get(chave)
    if expira is None:
        return False
    if time.monotonic() >= expira:
        _NEGATIVOS.pop(chave, None)
        return False
    return True


def _registrar_negativo(chave):
    _NEGATIVOS[chave] = time.monotonic() + _NEGATIVO_TTL_S


class _SemResultado(Exception):
    """Consulta sem resultado válido; lançada para que o st.cache_data não a armazene."""

    def __init__(self, falha_tecnica=None):
        super().__init__(str(falha_tecnica or ""))
        self.falha_tecnica = falha_tecnica


# (connect, read): conexão que não abre falha rápido e aciona o fallback.
_TIMEOUT_CEP = (3.05, 5)
_TIMEOUT_BRASILAPI_CNPJ = (3.05, 4)
_TIMEOUT_RECEITAWS = (3.05, 8)


CEP_OK = "ok"
CEP_NAO_ENCONTRADO = "nao_encontrado"
CEP_INDISPONIVEL = "indisponivel"
CEP_INVALIDO = "invalido"

# Status dos negativos recentes (mesma chave de _NEGATIVOS; só é lido enquanto o TTL curto vale).
_NEGATIVO_STATUS = {}


@st.cache_data(show_spinner=False, ttl=3600)
def _buscar_cep_valido(cep):
    """Só retorna (e portanto só é cacheado por 1h) um CEP encontrado.

    Lança _SemResultado(falha_tecnica=None) quando o CEP não existe e
    _SemResultado(falha_tecnica=<erro>) quando não foi possível confirmar (conectividade/5xx/etc.).
    """
    falha = None
    nao_existe = False
    try:
        resp = requests.get(f'https://viacep.com.br/ws/{cep}/json/', timeout=_TIMEOUT_CEP)
        if resp.status_code == 200:
            dados = resp.json()
            if 'erro' not in dados:
                return {
                    'uf': dados.get('uf'),
                    'cidade': dados.get('localidade'),
                    'bairro': dados.get('bairro'),
                    'logradouro': dados.get('logradouro', ''),
                    'complemento': dados.get('complemento', ''),
                }
            nao_existe = True  # ViaCEP respondeu e disse que o CEP não existe
        elif resp.status_code == 400:
            nao_existe = True  # formato rejeitado pelo ViaCEP
        else:
            falha = RuntimeError(f"ViaCEP HTTP {resp.status_code}")
    except Exception as e:
        falha = e

    # Fallback: BrasilAPI (ViaCEP expirou, falhou, deu 5xx ou não achou)
    try:
        resp2 = requests.get(f'https://brasilapi.com.br/api/cep/v1/{cep}', timeout=_TIMEOUT_CEP)
        if resp2.status_code == 200:
            dados2 = resp2.json()
            return {
                'uf': dados2.get('state'),
                'cidade': dados2.get('city'),
                'bairro': dados2.get('neighborhood'),
                'logradouro': dados2.get('street', ''),
                'complemento': '',
            }
        if resp2.status_code == 404:
            # 404 só vale como "não existe" se o ViaCEP não ficou indisponível
            # (ViaCEP fora do ar + 404 da BrasilAPI: não dá para afirmar; segue como indisponível)
            if falha is None:
                nao_existe = True
        else:
            falha = falha or RuntimeError(f"BrasilAPI HTTP {resp2.status_code}")
            if nao_existe:
                falha = None  # ViaCEP já confirmou a inexistência; falha da BrasilAPI é irrelevante
    except Exception as e:
        if not nao_existe:
            falha = e
    if nao_existe:
        raise _SemResultado(None)
    raise _SemResultado(falha or RuntimeError("consulta de CEP indisponível"))


def consultar_cep(cep_str):
    """Retorna (dados|None, status) com status em CEP_OK/CEP_NAO_ENCONTRADO/CEP_INDISPONIVEL/CEP_INVALIDO."""
    if not cep_str:
        return None, CEP_INVALIDO
    cep = str(cep_str).replace('-', '').replace('.', '').replace(' ', '').strip()
    if len(cep) != 8:
        return None, CEP_INVALIDO
    chave = ("cep", cep)
    if _negativo_ativo(chave):
        return None, _NEGATIVO_STATUS.get(chave, CEP_NAO_ENCONTRADO)
    try:
        return _buscar_cep_valido(cep), CEP_OK
    except _SemResultado as e:
        status = CEP_NAO_ENCONTRADO if e.falha_tecnica is None else CEP_INDISPONIVEL
        _registrar_negativo(chave)
        _NEGATIVO_STATUS[chave] = status
        return None, status


def buscar_cep(cep_str):
    return consultar_cep(cep_str)[0]


@st.cache_data(show_spinner=False, ttl=3600)
def _buscar_empresa_cnpj_valida(cnpj_limpo):
    # 1. Tentar BrasilAPI primeiro
    nome, logradouro, numero, bairro, cidade, uf, cep = "", "", "", "", "", "", ""
    sucesso = False
    
    try:
        headers = {"User-Agent": BROWSER_USER_AGENT}
        res = requests.get(f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}", headers=headers, timeout=_TIMEOUT_BRASILAPI_CNPJ)
        if res.status_code == 200:
            d = res.json()
            nome = d.get("razao_social") or d.get("nome_fantasia") or ""
            logradouro = d.get("logradouro", "")
            numero = d.get("numero", "")
            bairro = d.get("bairro", "")
            cidade = d.get("municipio", "")
            uf = d.get("uf", "")
            cep = re.sub(r"\D", "", str(d.get("cep", "")))
            if nome:
                sucesso = True
    except Exception:
        pass
        
    # 2. Fallback para ReceitaWS se falhar ou vier sem nome
    if not sucesso:
        try:
            res_r = requests.get(f"https://www.receitaws.com.br/v1/cnpj/{cnpj_limpo}", timeout=_TIMEOUT_RECEITAWS)
            if res_r.status_code == 200:
                dr = res_r.json()
                if dr.get("status") != "ERROR":
                    nome = dr.get("nome") or dr.get("fantasia") or nome
                    logradouro = dr.get("logradouro") or logradouro
                    numero = dr.get("numero") or numero
                    bairro = dr.get("bairro") or bairro
                    cidade = dr.get("municipio") or cidade
                    uf = dr.get("uf") or uf
                    cep_bruto = dr.get("cep", "")
                    cep = re.sub(r"\D", "", cep_bruto) if cep_bruto else cep
                    if nome:
                        sucesso = True
        except Exception:
            pass

    if sucesso:
        end = " ".join(x for x in [logradouro, numero] if x).strip()
        partes = [p for p in [nome, end, bairro, f"{cidade}/{uf}" if cidade else "", f"CEP {cep}" if cep else ""] if p]
        return {
            "ok": True,
            "texto": " — ".join(partes),
            "razao": nome,
            "cidade": cidade,
            "uf": uf,
            "cep": cep,
            "logradouro": logradouro,
            "numero": numero,
            "bairro": bairro,
        }
        
    raise _SemResultado()


def buscar_empresa_cnpj(cnpj):
    """BrasilAPI + ReceitaWS -> razão social, CEP e endereço completo do CNPJ."""
    cnpj_limpo = limpar_documento(cnpj)
    if len(cnpj_limpo) != 14:
        return {"ok": False, "texto": "", "cep": "", "razao": ""}
    if _negativo_ativo(("cnpj", cnpj_limpo)):
        return {"ok": False, "texto": "", "cep": "", "razao": ""}
    try:
        return _buscar_empresa_cnpj_valida(cnpj_limpo)
    except _SemResultado:
        _registrar_negativo(("cnpj", cnpj_limpo))
        return {"ok": False, "texto": "", "cep": "", "razao": ""}

def mapear_regiao(uf, cidade, transportadora):
    uf = (uf or "").upper().strip()
    cidade_n = (cidade or "").lower().strip()
    tab = TABELAS.get(transportadora, {})
    rotas = tab.get("rotas", {})

    if cidade_n in CAPITAIS:
        u, r = CAPITAIS[cidade_n]
        if u == uf and (uf, r) in rotas:
            return uf, r

    if transportadora == "ENVIA_RAPIDO":
        if (uf, "CAPITAL") in rotas and cidade_n in ["sao paulo", "são paulo", "curitiba", "londrina"]:
            return uf, "CAPITAL"
        if (uf, "GERAL") in rotas:
            return uf, "GERAL"

    if transportadora == "COOPEX" and uf == "PR":
        express = ["apucarana", "arapongas", "cornelio procopio", "cornélio procópio", "londrina"]
        if any(x in cidade_n for x in express) and (uf, "EXPRESS") in rotas:
            return uf, "EXPRESS"
    if transportadora == "COOPEX" and uf == "SC":
        if any(x in cidade_n for x in ["florianopolis", "florianópolis", "tubarao", "criciuma", "criciúma"]):
            return uf, "LITORAL_S"
        if any(x in cidade_n for x in ["joinville", "blumenau", "itajai"]):
            return uf, "LITORAL_N"
        if (uf, "OESTE") in rotas:
            return uf, "OESTE"

    default = tab.get("default_regiao", "INT1")
    if (uf, default) in rotas:
        return uf, default
    for (u, r) in rotas:
        if u == uf:
            return u, r
    return None, None

