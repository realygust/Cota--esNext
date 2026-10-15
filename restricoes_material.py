"""
Restrições de material por transportadora (tabela contratual) e sua aplicação
aos resultados de cotação. Regra única usada pelos cartões individuais e pelo TOP 3.
"""
import unicodedata

AVISO_MATERIAL = "⚠️ Confirme se a transportadora transporta este material."

# Tabela contratual (conteúdo inalterado; movida de main.py).
RESTRICOES_MATERIAIS = {
    "AGEX": {"Pallet": "LEVA", "Bobina": "LEVA"},
    "ALFA": {"Pallet": "LEVA", "Bobina": "LEVA"},
    "ANDORINHA": {"Pallet": "NÃO LEVA", "Bobina": "NÃO LEVA"},
    "ATUAL CARGAS": {"Pallet": "CONSULTAR REGIAO", "Bobina": "CONSULTAR REGIAO"},
    "AVIÕES TRANSPORTES": {"Pallet": "LEVA", "Bobina": "LEVA"},
    "BASSO": {"Pallet": "LEVA", "Bobina": "LEVA"},
    "BERTOLINI": {"Pallet": "LEVA", "Bobina": "LEVA"},
    "BRASPRESS": {"Pallet": "LEVA", "Bobina": "NÃO LEVA"},
    "BRASUL": {"Pallet": "LEVA", "Bobina": "LEVA"},
    "CARRION": {"Pallet": "LEVA", "Bobina": "LEVA"},
    "CARVALIMA": {"Pallet": "NÃO LEVA", "Bobina": "NÃO LEVA"},
    "CONECTLOG": {"Pallet": "LEVA", "Bobina": "LEVA"},
    "COOPEX": {"Pallet": "LEVA", "Bobina": "LEVA"},
    "CORREIOS": {"Pallet": "NÃO LEVA", "Bobina": "NÃO LEVA"},
    "CRUZEIRO DO SUL": {"Pallet": "NÃO LEVA", "Bobina": "NÃO LEVA"},
    "DESTAK": {"Pallet": "LEVA", "Bobina": "LEVA"},
    "ENVIA RAPIDO": {"Pallet": "NÃO LEVA", "Bobina": "NÃO LEVA"},
    "EUCATUR": {"Pallet": "LEVA", "Bobina": "LEVA"},
    "EXCELLENCE": {"Pallet": "LEVA", "Bobina": "LEVA"},
    "EXPRESSO SÃO MIGUEL": {"Pallet": "NÃO LEVA", "Bobina": "NÃO LEVA"},
    "FAST PÉROLA": {"Pallet": "NÃO LEVA", "Bobina": "NÃO LEVA"},
    "GARCIA": {"Pallet": "NÃO LEVA", "Bobina": "NÃO LEVA"},
    "GOL": {"Pallet": "NÃO LEVA", "Bobina": "NÃO LEVA"},
    "LOGDI": {"Pallet": "LEVA", "Bobina": "LEVA"},
    "MAEX": {"Pallet": "LEVA", "Bobina": "LEVA"},
    "MENEGHIM": {"Pallet": "LEVA", "Bobina": "LEVA"},
    "MIRA": {"Pallet": "LEVA", "Bobina": "LEVA"},
    "MID": {"Pallet": "LEVA", "Bobina": "LEVA"},
    "MMS": {"Pallet": "LEVA", "Bobina": "LEVA"},
    "PATRUS": {"Pallet": "CONSULTAR REGIAO", "Bobina": "CONSULTAR REGIAO"},
    "PLAV": {"Pallet": "LEVA", "Bobina": "LEVA"},
    "PORTO 43": {"Pallet": "LEVA", "Bobina": "LEVA"},
    "PRINCESA": {"Pallet": "LEVA", "Bobina": "LEVA"},
    "REUNIDAS CARGAS": {"Pallet": "LEVA", "Bobina": "CONSULTAR REGIAO"},
    "RICO": {"Pallet": "LEVA", "Bobina": "LEVA"},
    "RODONAVES": {"Pallet": "LEVA", "Bobina": "LEVA"},
    "SUDOESTE": {"Pallet": "LEVA", "Bobina": "LEVA"},
    "TECMAR": {"Pallet": "LEVA", "Bobina": "LEVA"},
    "TRANSLOVATO": {"Pallet": "LEVA", "Bobina": "LEVA"},
    "VIP": {"Pallet": "NÃO LEVA", "Bobina": "NÃO LEVA"},
    "RPA CARGO": {"Pallet": "LEVA", "Bobina": "LEVA"},
}


def _norm(texto):
    """Maiúsculas, sem acentos e com espaços normalizados (ex.: 'Envia Rápido' == 'ENVIA RAPIDO')."""
    s = unicodedata.normalize("NFKD", str(texto or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.upper().replace("_", " ").split())


def _chave_transportadora(nome, restricoes):
    nome_n = _norm(nome)
    if not nome_n:
        return None
    for k in restricoes:
        k_n = _norm(k)
        if k_n in nome_n or nome_n in k_n:
            return k
    return None


def avaliar_material(nome_transportadora, tipos_materiais, restricoes=None):
    """
    Retorna (excluir, aviso) para uma transportadora e os tipos de material da carga.

    - 'Outro' nunca filtra nem avisa.
    - Material sem nenhuma regra contratual cadastrada (ex.: Caixa, Saco) não gera restrição.
    - NÃO LEVA para qualquer material presente exclui a transportadora.
    - CONSULTAR REGIAO / NÃO INFORMADO (sem linha cadastrada para a transportadora) mantêm com aviso.
    """
    restricoes = RESTRICOES_MATERIAIS if restricoes is None else restricoes
    materiais_regulados = {m for regras in restricoes.values() for m in regras}
    chave = _chave_transportadora(nome_transportadora, restricoes)

    aviso = False
    for mat in tipos_materiais or []:
        if mat == "Outro" or mat not in materiais_regulados:
            continue
        aceite = restricoes[chave].get(mat, "NÃO INFORMADO") if chave else "NÃO INFORMADO"
        if aceite == "NÃO LEVA":
            return True, None
        if aceite in ("CONSULTAR REGIAO", "NÃO INFORMADO"):
            aviso = True
    return False, (AVISO_MATERIAL if aviso else None)


def aplicar_restricoes_material(resultados, tipos_materiais, restricoes=None):
    """Filtra a lista de resultados e define 'Aviso_Material' nos cartões que precisam de confirmação."""
    filtrados = []
    for r in resultados:
        if not r.get("Atendida"):
            filtrados.append(r)
            continue
        # Princesa dos Campos não sofre alteração.
        if "PRINCESA" in _norm(r.get("Transportadora", "")):
            filtrados.append(r)
            continue
        excluir, aviso = avaliar_material(r.get("Transportadora", ""), tipos_materiais, restricoes)
        if excluir:
            continue
        if aviso:
            r["Aviso_Material"] = aviso
        filtrados.append(r)
    return filtrados
