import math
import re
import requests
import json
import urllib3
import urllib.parse
import base64
from xml.etree import ElementTree as ET
import streamlit as st
import tabelas_engine as te
from utils import _secret, limpar_mensagem_ssw, limpar_documento, xml_escape, limpar_cep, mapear_regiao
from config import TABELAS, BROWSER_USER_AGENT
USUARIO_BRASPRESS = _secret("USUARIO_BRASPRESS", "")
SENHA_BRASPRESS = _secret("SENHA_BRASPRESS", "")
DOMINIO_AGEX = _secret("DOMINIO_AGEX", "")
USUARIO_AGEX = _secret("USUARIO_AGEX", "")
SENHA_AGEX = _secret("SENHA_AGEX", "")
DOMINIO_COPEX = _secret("DOMINIO_COPEX", "")
USUARIO_COPEX = _secret("USUARIO_COPEX", "")
SENHA_COPEX = _secret("SENHA_COPEX", "")
DOMINIO_LOGBG = _secret("DOMINIO_LOGBG", "")
USUARIO_LOGBG = _secret("USUARIO_LOGBG", "")
SENHA_LOGBG = _secret("SENHA_LOGBG", "")
MERCADORIA_LOGBG = _secret("MERCADORIA_LOGBG", "")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def calcular_frete_tabela(nome, peso, volume_m3, valor_nf, uf_destino, cidade_destino):
    tab = TABELAS.get(nome)
    if not tab:
        return None

    uf, regiao = mapear_regiao(uf_destino, cidade_destino, nome)
    if not uf or not regiao:
        ufs_ok = sorted({u for (u, _) in tab.get("rotas", {})})
        return {
            "Transportadora": nome,
            "Nº Cotação": "Tabela",
            "Valor Frete (R$)": None,
            "Prazo (Dias Úteis)": 0,
            "Status": f"Não atende {uf_destino or '?'} (cobre: {', '.join(ufs_ok)})",
            "Fonte": "tabela",
            "Composição": None,
        }

    rota = tab["rotas"][(uf, regiao)]
    fator = tab.get("cubagem", 300)
    peso_cubado = volume_m3 * fator if volume_m3 else 0
    peso_calc = max(float(peso), peso_cubado)

    faixas = tab["faixas_peso"]
    vals = rota["vals"]
    frete_peso = None
    faixa_atingida = ""
    for i, limite in enumerate(faixas):
        if peso_calc <= limite:
            frete_peso = vals[i]
            faixa_atingida = f"Até {limite} kg"
            break
    if frete_peso is None:
        if "exc_ton" in rota:
            exc_calc = ((peso_calc - faixas[-1]) / 1000.0) * rota["exc_ton"]
            frete_peso = vals[-1] + exc_calc
            faixa_atingida = f"Acima de {faixas[-1]} kg (+ R$ {rota['exc_ton']:.2f}/ton)"
        else:
            exc_calc = (peso_calc - faixas[-1]) * rota.get("exc", 0)
            frete_peso = vals[-1] + exc_calc
            faixa_atingida = f"Acima de {faixas[-1]} kg (+ R$ {rota.get('exc', 0):.2f}/kg)"

    adv_pct = rota.get("adv", 0)
    gris_pct = rota.get("gris", 0)
    frete_valor = float(valor_nf) * adv_pct
    if tab.get("adv_min"):
        frete_valor = max(frete_valor, tab["adv_min"])
    gris = float(valor_nf) * gris_pct
    if tab.get("gris_min"):
        gris = max(gris, tab["gris_min"])

    ped_unit = rota.get("ped", tab.get("pedagio", {}).get(uf, 0))
    fracoes = max(1, math.ceil(peso_calc / 100)) if peso_calc > 0 else 1
    pedagio = fracoes * ped_unit
    despacho = rota.get("desp", tab.get("despacho", 0))
    tas = rota.get("tas", tab.get("tas", 0))
    total = frete_peso + frete_valor + gris + pedagio + despacho + tas

    composicao = {
        "Região / Rota": f"{uf}/{regiao}",
        "Faixa Aplicada": faixa_atingida,
        "Peso Tarifado": f"{peso_calc:.2f} kg ({'Cubado' if peso_cubado > float(peso) else 'Real'})",
        "Frete Peso": round(frete_peso, 2),
        "Ad Valorem": round(frete_valor, 2),
        "Taxa Ad Valorem": f"{adv_pct * 100:.2f}%" if adv_pct else "Isento",
        "GRIS": round(gris, 2),
        "Taxa GRIS": f"{gris_pct * 100:.2f}%" if gris_pct else "Isento",
        "Pedágio": round(pedagio, 2),
        "Frações Pedágio": f"{fracoes}x (R$ {ped_unit:.2f}/fração)",
        "Despacho": round(despacho, 2),
        "TAS": round(tas, 2),
        "Total": round(total, 2),
    }

    return {
        "Transportadora": nome,
        "Nº Cotação": f"Tabela {uf}/{regiao}",
        "Valor Frete (R$)": round(total, 2),
        "Prazo (Dias Úteis)": 0,
        "Status": "Tarifa negociada estimada",
        "Fonte": "tabela",
        "Composição": composicao,
    }

def cotar_braspress(cep_origem, cep_destino, peso, valor_nf, cubagem_lista, cnpj_remetente, doc_destinatario):
    token = base64.b64encode(f"{USUARIO_BRASPRESS}:{SENHA_BRASPRESS}".encode()).decode()
    headers = {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": BROWSER_USER_AGENT,
    }
    url = "https://api.braspress.com/v1/cotacao/calcular/json"
    remetente_limpo = limpar_documento(cnpj_remetente)
    doc_dest_limpo = limpar_documento(doc_destinatario)
    if not doc_dest_limpo or len(doc_dest_limpo) < 11:
        doc_dest_limpo = remetente_limpo
    total_volumes = sum(int(item.get("Volumes", 0)) for item in cubagem_lista)
    payload = {
        "CnpjRemetente": remetente_limpo,
        "CnpjDestinatario": doc_dest_limpo,
        "Modal": "R",
        "TipoFrete": 1,
        "CepOrigem": limpar_cep(cep_origem),
        "CepDestino": limpar_cep(cep_destino),
        "Peso": float(peso),
        "ValorDeclarado": float(valor_nf),
        "Volumes": int(total_volumes) if total_volumes > 0 else 1,
        "Cubagem": cubagem_lista,
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=(5, 18))
        if response.status_code in [200, 201]:
            dados = response.json()
            prazo_dias = (
                dados.get("prazoEntrega") or dados.get("prazo")
                or dados.get("prazoDias") or dados.get("prazoDiasUteis") or 0
            )
            val_total = float(dados.get("totalFrete", dados.get("valorTotal", 0.0)))
            return {
                "Transportadora": "Braspress",
                "Nº Cotação": str(dados.get("id", dados.get("numeroCotacao", "N/A"))),
                "Valor Frete (R$)": val_total,
                "Prazo (Dias Úteis)": int(prazo_dias),
                "Status": "API oficial confirmada",
                "Fonte": "api",
                "Composição": None,
            }
        try:
            err_data = response.json()
            err_msg = err_data.get("message") or err_data.get("error") or str(err_data)
        except Exception:
            err_msg = response.text[:60]
        return {
            "Transportadora": "Braspress", "Nº Cotação": "-", "Valor Frete (R$)": None,
            "Prazo (Dias Úteis)": 0, "Status": f"API {response.status_code}: {err_msg[:45]}", "Fonte": "api",
            "Composição": None,
        }
    except Exception as e:
        return {
            "Transportadora": "Braspress", "Nº Cotação": "-", "Valor Frete (R$)": None,
            "Prazo (Dias Úteis)": 0, "Status": f"API falha de conexão ({str(e)[:40]})", "Fonte": "api",
            "Composição": None,
        }

def rastrear_braspress(nf, cnpj_remetente):
    """Rastreia NF na Braspress com cabeçalho de navegador para evitar HTTP 403."""
    token = base64.b64encode(f"{USUARIO_BRASPRESS}:{SENHA_BRASPRESS}".encode()).decode()
    headers = {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": BROWSER_USER_AGENT,
    }
    nf_limpa = re.sub(r"\D", "", str(nf or ""))
    cnpj_limpo = limpar_documento(cnpj_remetente)
    url = f"https://api.braspress.com/v1/tracking/remetente/{cnpj_limpo}/nf/{nf_limpa}"
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code in [200, 201]:
            data = r.json()
            eventos = data.get("tracking", data.get("eventos", []))
            if not eventos and isinstance(data, list):
                eventos = data

            status_geral = "Em processamento"
            ultima_ocorrencia = ""
            data_ocorrencia = ""
            data_entrega = data.get("dataEntrega", "")
            previsao_entrega = data.get("previsaoEntrega", data.get("dataPrevisao", ""))

            if eventos and len(eventos) > 0:
                ultimo_evt = eventos[-1]
                descricao_evt = str(ultimo_evt.get("descricao", ultimo_evt.get("status", "")))
                data_ocorrencia = str(ultimo_evt.get("data", ultimo_evt.get("dataHora", "")))
                ultima_ocorrencia = descricao_evt

                desc_lower = descricao_evt.lower()
                if "entregue" in desc_lower or "entrega realizada" in desc_lower:
                    status_geral = "Entregue"
                    if not data_entrega:
                        data_entrega = data_ocorrencia
                elif "saiu para entrega" in desc_lower or "em rota" in desc_lower:
                    status_geral = "Saiu para Entrega"
                elif "retido" in desc_lower or "avaria" in desc_lower or "recusad" in desc_lower or "devolu" in desc_lower:
                    status_geral = "Ocorrência / Retido"
                elif "transito" in desc_lower or "transferencia" in desc_lower or "coletado" in desc_lower:
                    status_geral = "Em Trânsito"
            elif data.get("status"):
                status_geral = str(data.get("status"))

            return {
                "sucesso": True,
                "codigo": r.status_code,
                "nf": nf_limpa,
                "status": status_geral,
                "previsao": previsao_entrega,
                "data_entrega": data_entrega,
                "ultima_ocorrencia": ultima_ocorrencia,
                "data_ocorrencia": data_ocorrencia,
                "destino": data.get("cidadeDestino", data.get("destino", "")),
                "valor_frete": data.get("totalFrete", data.get("valorFrete", "")),
                "eventos": eventos,
                "raw": data,
            }
        return {
            "sucesso": False,
            "codigo": r.status_code,
            "nf": nf_limpa,
            "status": f"NF não localizada (HTTP {r.status_code})" if r.status_code == 404 else f"Erro {r.status_code}",
            "previsao": "",
            "data_entrega": "",
            "ultima_ocorrencia": "Sem registro recente na transportadora",
            "data_ocorrencia": "",
            "destino": "",
            "valor_frete": "",
            "eventos": [],
            "raw": r.text,
        }
    except Exception as e:
        return {
            "sucesso": False,
            "codigo": 500,
            "nf": nf_limpa,
            "status": f"Falha de conexão ({str(e)[:35]})",
            "previsao": "",
            "data_entrega": "",
            "ultima_ocorrencia": str(e)[:50],
            "data_ocorrencia": "",
            "destino": "",
            "valor_frete": "",
            "eventos": [],
            "raw": str(e),
        }

def cotar_ssw_wsdl(
    nome_transportadora, dominio, usuario, senha,
    cep_origem, cep_destino, peso, valor_nf, cubagem_lista,
    cnpj_remetente, doc_destinatario, mercadoria=1,
):
    url = "https://ssw.inf.br/ws/sswCotacao/index.php"
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": "urn:sswinfbr.sswCotacao#cotacao",
        "User-Agent": BROWSER_USER_AGENT,
    }
    remetente = limpar_documento(cnpj_remetente)
    destinatario = limpar_documento(doc_destinatario)
    if not destinatario:
        destinatario = remetente
    cep_o = limpar_cep(cep_origem)
    cep_d = limpar_cep(cep_destino)
    total_volumes = sum(int(item.get("Volumes", 0)) for item in cubagem_lista)
    if total_volumes <= 0:
        total_volumes = 1

    volume_total = 0.0
    for item in cubagem_lista:
        try:
            volume_total += (
                float(item.get("Altura", 0)) * float(item.get("Largura", 0))
                * float(item.get("Comprimento", 0)) * int(item.get("Volumes", 1))
            )
        except Exception:
            pass

    primeiro = cubagem_lista[0] if cubagem_lista else {"Altura": 0.3, "Largura": 0.3, "Comprimento": 0.4}
    altura = float(primeiro.get("Altura", 0.3))
    largura = float(primeiro.get("Largura", 0.3))
    comprimento = float(primeiro.get("Comprimento", 0.4))

    def montar_envelope(pagador):
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
 xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
 xmlns:urn="urn:sswinfbr.sswCotacao">
  <soapenv:Header/>
  <soapenv:Body>
    <urn:cotar soapenv:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
      <dominio xsi:type="xsd:string">{xml_escape(dominio)}</dominio>
      <login xsi:type="xsd:string">{xml_escape(usuario)}</login>
      <senha xsi:type="xsd:string">{xml_escape(senha)}</senha>
      <cnpjPagador xsi:type="xsd:string">{xml_escape(pagador)}</cnpjPagador>
      <cepOrigem xsi:type="xsd:integer">{cep_o}</cepOrigem>
      <cepDestino xsi:type="xsd:integer">{cep_d}</cepDestino>
      <valorNF xsi:type="xsd:decimal">{float(valor_nf):.2f}</valorNF>
      <quantidade xsi:type="xsd:integer">{total_volumes}</quantidade>
      <peso xsi:type="xsd:decimal">{float(peso):.3f}</peso>
      <volume xsi:type="xsd:decimal">{volume_total:.4f}</volume>
      <mercadoria xsi:type="xsd:integer">{int(mercadoria)}</mercadoria>
      <cnpjDestinatario xsi:type="xsd:string">{xml_escape(destinatario)}</cnpjDestinatario>
      <coletar xsi:type="xsd:string">S</coletar>
      <entDificil xsi:type="xsd:string">N</entDificil>
      <destContribuinte xsi:type="xsd:string">S</destContribuinte>
      <qtdePares xsi:type="xsd:integer">0</qtdePares>
      <altura xsi:type="xsd:decimal">{altura:.3f}</altura>
      <largura xsi:type="xsd:decimal">{largura:.3f}</largura>
      <comprimento xsi:type="xsd:decimal">{comprimento:.3f}</comprimento>
      <fatorMultiplicador xsi:type="xsd:integer">1</fatorMultiplicador>
      <cnpjRemetente xsi:type="xsd:string">{xml_escape(remetente)}</cnpjRemetente>
    </urn:cotar>
  </soapenv:Body>
</soapenv:Envelope>"""

    tentativas = [remetente, destinatario]
    ultimo_erro = ""

    for pagador_atual in tentativas:
        envelope = montar_envelope(pagador_atual)
        try:
            resp = requests.post(url, data=envelope.encode("utf-8"), headers=headers, timeout=(5, 14))
            if resp.status_code >= 500:
                ultimo_erro = f"HTTP {resp.status_code}"
                continue
            root_soap = ET.fromstring(resp.content)
            return_elem = next((e for e in root_soap.iter() if e.tag.endswith("return")), None)
            if return_elem is None or not (return_elem.text or "").strip():
                ultimo_erro = "Retorno vazio da API"
                continue

            cotacao = ET.fromstring(return_elem.text.strip())

            def find_text(tag):
                el = cotacao.find(tag)
                if el is not None and el.text:
                    return el.text.strip()
                for item in cotacao.iter():
                    if item.tag.split("}")[-1] == tag and item.text:
                        return item.text.strip()
                return ""

            erro = int(find_text("erro") or -1)
            mensagem = limpar_mensagem_ssw(find_text("mensagem"))

            if erro in (0, 1):
                frete_texto = (find_text("totalFrete") or "0").strip()
                if "," in frete_texto and "." in frete_texto:
                    frete_texto = frete_texto.replace(".", "").replace(",", ".")
                elif "," in frete_texto:
                    frete_texto = frete_texto.replace(",", ".")
                frete_val = float(frete_texto)
                prazo_val = int(float(find_text("prazo") or 0))

                status = "API oficial confirmada" if erro == 0 else (
                    f"API com ressalva: {mensagem[:65]}" if mensagem else "API oficial com ressalva"
                )

                def parse_moeda(tag):
                    v = find_text(tag) or "0"
                    v = v.replace(".", "").replace(",", ".") if ("," in v and "." in v) else v.replace(",", ".")
                    try:
                        return float(v)
                    except Exception:
                        return 0.0

                comp_ssw = {
                    "Região / Rota": find_text("tabCalculo") or "Tabela SSW",
                    "Faixa Aplicada": f"Peso Cálculo: {find_text('pesoCalculo') or peso} kg",
                    "Peso Tarifado": f"{find_text('pesoCalculo') or peso} kg",
                    "Frete Peso": parse_moeda("fretePeso"),
                    "Ad Valorem": parse_moeda("freteValor"),
                    "Taxa Ad Valorem": "-",
                    "GRIS": parse_moeda("gris"),
                    "Taxa GRIS": "-",
                    "Pedágio": parse_moeda("pedagio"),
                    "Frações Pedágio": "-",
                    "Despacho": parse_moeda("despacho"),
                    "TAS": parse_moeda("tas"),
                    "Impostos": parse_moeda("impostos"),
                    "Total": frete_val,
                }

                return {
                    "Transportadora": nome_transportadora,
                    "Nº Cotação": "SSW Oficial",
                    "Valor Frete (R$)": frete_val,
                    "Prazo (Dias Úteis)": prazo_val,
                    "Status": status,
                    "Fonte": "api",
                    "Composição": comp_ssw,
                }

            ultimo_erro = mensagem if mensagem else f"Erro SSW {erro}"
            msg_lower = ultimo_erro.lower()
            if any(termo in msg_lower for termo in ["invalido", "inválido", "senha", "dominio", "domínio", "bloqueado", "nao cadastrado"]):
                break

        except Exception as e:
            ultimo_erro = str(e)[:70]
            break

    return {
        "Transportadora": nome_transportadora,
        "Nº Cotação": "-",
        "Valor Frete (R$)": None,
        "Prazo (Dias Úteis)": 0,
        "Status": ultimo_erro[:75] if ultimo_erro else "Falha SSW",
        "Fonte": "api",
        "Composição": None,
    }

