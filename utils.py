import pandas as pd
import requests
import json
import os
from datetime import datetime
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

def xml_escape(valor):
    return html.escape(str(valor or ""), quote=True)

@st.cache_data(show_spinner=False, ttl=3600)
def buscar_cep(cep_str):
    if not cep_str: return None
    cep = str(cep_str).replace('-', '').replace('.', '').replace(' ', '').strip()
    if len(cep) != 8: return None
    try:
        resp = requests.get(f'https://viacep.com.br/ws/{cep}/json/', timeout=5)
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
        
        resp2 = requests.get(f'https://brasilapi.com.br/api/cep/v1/{cep}', timeout=5)
        if resp2.status_code == 200:
            dados2 = resp2.json()
            return {
                'uf': dados2.get('state'),
                'cidade': dados2.get('city'),
                'bairro': dados2.get('neighborhood'),
                'logradouro': dados2.get('street', ''),
                'complemento': '',
            }
    except Exception as e:
        import streamlit as st
        st.error(f"Erro técnico na busca do CEP: {e}")
    return None

def buscar_empresa_cnpj(cnpj):
    """BrasilAPI + ReceitaWS -> razão social, CEP e endereço completo do CNPJ."""
    cnpj_limpo = limpar_documento(cnpj)
    if len(cnpj_limpo) != 14:
        return {"ok": False, "texto": "", "cep": "", "razao": ""}
    
    # 1. Tentar BrasilAPI primeiro
    nome, logradouro, numero, bairro, cidade, uf, cep = "", "", "", "", "", "", ""
    sucesso = False
    
    try:
        headers = {"User-Agent": BROWSER_USER_AGENT}
        res = requests.get(f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}", headers=headers, timeout=8)
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
            res_r = requests.get(f"https://www.receitaws.com.br/v1/cnpj/{cnpj_limpo}", timeout=8)
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

