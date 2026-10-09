import urllib.parse
import streamlit as st
import tabelas_engine as te

CONTATOS_TRANSPORTADORAS = {
    "braspress": "551122233500",
    "brasul": "554399652615",
    "sudoeste": "558000413223",
    "coopex": "554388705800",
    "rico": "554388705800",
    "aragão": "554388705800",
    "aragao": "554388705800",
    "alfa": "554333799606",
    "tecmar": "554399680511",
    "vip": "554333560099",
    "bertolini": "555421023000",
    "plav": "55438416965",
    "tw": "555484389905",
    "envia": "554388198906",
    "carrion": "554399724200",
    "são miguel": "554933616666",
    "sao miguel": "554933616666",
    "logdi": "554135932400",
    "ouro negro": "554396753456",
    "agex": "554333051700",
    "rodonaves": "554374001084",
    "(rte)": "554374001084",
    "garcia": "554399192354",
    "princesa": "558004210000",
}


def obter_numero_wa(nome_transportadora):
    nome_limpo = str(nome_transportadora).lower().strip()
    for chave, numero in CONTATOS_TRANSPORTADORAS.items():
        if chave in nome_limpo:
            return numero
    return ""

def gerar_badge_logo_html(nome_transp: str) -> str:
    """Gera bloco HTML com logotipo da transportadora para os cards e tabelas."""
    try:
        if hasattr(te, "gerar_badge_logo_html"):
            return te.gerar_badge_logo_html(nome_transp)
    except Exception:
        pass
    return f'<div style="background-color: #f0f2f6; padding: 5px 10px; border-radius: 5px; display: inline-block; font-weight: bold; color: #31333F;">{nome_transp}</div>'


def _limpar_doc(val):
    if val is None:
        return ""
    import re
    s = str(val).strip()
    digits = re.sub(r"\D", "", s)
    return digits if digits else s


def _formatar_num(v):
    try:
        f = float(v)
        if f.is_integer():
            return str(int(f))
        s = f"{f:.2f}".rstrip("0").rstrip(".")
        return s.replace(".", ",")
    except Exception:
        return str(v)


def _formatar_valor_moeda(valor):
    if valor is None or str(valor).strip() == "" or str(valor).lower() == "nan":
        return "R$ 0,00"
    try:
        f = float(valor)
        return f"R$ {f:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def gerar_mensagem_wa(cot_info, valor_estimado):
    """
    Gera a mensagem exata de validação de frete para WhatsApp
    conforme padrão Next Cable.
    """
    rem = _limpar_doc(cot_info.get("remetente", "")) or "N/A"
    cep_rem = _limpar_doc(cot_info.get("origem_cep", "")) or "N/A"
    dest = _limpar_doc(cot_info.get("destinatario", "")) or "N/A"
    cep_dest = _limpar_doc(cot_info.get("destino_cep", "")) or "N/A"

    v_data = cot_info.get("volumes_data", [])
    linhas_comp = []
    tot_qtd = 0
    tot_peso = 0.0

    for v in v_data:
        try:
            qtd = int(float(v.get("Qtd", 0)))
        except (ValueError, TypeError):
            qtd = 0
        if qtd <= 0:
            continue

        try:
            peso_l = float(v.get("Peso Total (kg)", 0.0))
        except (ValueError, TypeError):
            peso_l = 0.0

        tot_qtd += qtd
        tot_peso += peso_l

        tipo_mat = str(v.get("Tipo", "Outro")).strip()
        desc = str(v.get("descricao", "") or v.get("Descricao", "")).strip()

        if tipo_mat == "Outro" and desc:
            nome_mat = f"Outro ({desc})"
        elif tipo_mat:
            nome_mat = tipo_mat
        else:
            nome_mat = "Outro"

        vol_txt = "volume" if qtd == 1 else "volumes"
        alt = _formatar_num(v.get("Alt (cm)", 0))
        larg = _formatar_num(v.get("Larg (cm)", 0))
        comp = _formatar_num(v.get("Comp (cm)", 0))
        peso_txt = _formatar_num(peso_l)

        linhas_comp.append(
            f"• {nome_mat}: {qtd} {vol_txt} — dimensões por volume: {alt} × {larg} × {comp} cm — peso total da linha: {peso_txt} kg"
        )

    tot_vol_txt = "volume" if tot_qtd == 1 else "volumes"
    tot_peso_txt = _formatar_num(tot_peso)

    bloco_comp = "\n".join(linhas_comp)
    val_nf = _formatar_valor_moeda(cot_info.get("valor_nf", 0))
    val_est = _formatar_valor_moeda(valor_estimado)

    msg = (
        "Olá! Por gentileza, poderiam validar esta cotação de frete?\n\n"
        f"Remetente: CNPJ {rem} — CEP {cep_rem}\n"
        f"Destinatário: CNPJ {dest} — CEP {cep_dest}\n\n"
        "Composição da carga:\n"
        f"{bloco_comp}\n\n"
        f"Totais: {tot_qtd} {tot_vol_txt} | {tot_peso_txt} kg\n"
        f"Valor da NF: {val_nf}\n"
        f"Estimativa via tabela: {val_est}\n\n"
        "Poderiam confirmar se o valor está de acordo com a tabela comercial que temos com vocês?"
    )
    return msg


def gerar_link_wa(nome_transportadora, cot_info, valor_estimado):
    """Gera link wa.me pronto com número da transportadora e mensagem codificada."""
    numero = obter_numero_wa(nome_transportadora)
    msg = gerar_mensagem_wa(cot_info, valor_estimado)
    return f"https://wa.me/{numero}?text={urllib.parse.quote(msg)}"

