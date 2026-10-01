"""
Motor de Cálculo Estrito das 16 Tabelas Contratuais (v10.0)
Next Indústria de Cabos LTDA - CNPJ: 26.434.839/0001-21
Origem Padrão: Londrina - PR (CEP 86071-000 / 86072-000)

REGRA CRÍTICA:
- Tolerância zero a falsos positivos e achismos logísticos.
- Se a transportadora não atende a rota/cidade/UF solicitada, o retorno é estritamente "Não atende esta região".
- Não é permitida interpolação com cidades vizinhas ou aproximações não contratadas.
"""

import math
import re
from typing import Dict, Any, Tuple, List, Optional

# ==============================================================================
# 1. METADADOS E ABRANGÊNCIA DAS 16 TRANSPORTADORAS
# ==============================================================================

TRANSPORTADORAS_CONFIG = {
    "BRASPRESS": {
        "nome": "Braspress",
        "tipo": "API Oficial REST v1",
        "contrato": "API Oficial REST v1 (Token Oauth2)",
        "abrangencia_tags": ["BRASIL"],
        "descricao": "Cobertura Nacional via API Oficial Integrada",
    },
    "COOPEX": {
        "nome": "Coopex",
        "tipo": "Webservice SSW + Tabela LDN_PADRAO_CP010",
        "contrato": "Tabela Contratual Padrão 2026",
        "abrangencia_tags": ["PR", "SC", "RS"],
        "descricao": "Especialista Sul (PR Express, Litoral/Oeste SC, RS)",
    },
    "PRINCESA": {
        "nome": "Princesa dos Campos",
        "tipo": "Tabela Contratual Z032",
        "contrato": "Tabela Z032 (Reajuste 9,5% Fev-25)",
        "abrangencia_tags": ["SP", "SC", "RS", "PR (Curitiba)"],
        "descricao": "Atendimento SP, SC, RS e no PR estritamente Curitiba/RMC",
    },
    "ALFA": {
        "nome": "Alfa Transportes",
        "tipo": "Tabela Contratual TRF-48",
        "contrato": "Tabela TRF-48 Rev. 04 (Vig. 2025/2026)",
        "abrangencia_tags": ["PR", "SC", "RS", "SP", "MS", "MT", "GO", "DF", "MG", "RJ", "ES"],
        "descricao": "Rede expressa Sul, Sudeste e Centro-Oeste",
    },
    "TW": {
        "nome": "TW Transportes",
        "tipo": "Tabela Contratual 10Fx_Kg",
        "contrato": "Tabela Combinada v26.04 (Versão 2026.01)",
        "abrangencia_tags": ["PR", "SC", "RS"],
        "descricao": "Malha consolidada RS, SC e polos do PR",
    },
    "ENVIA_RAPIDO": {
        "nome": "Envia Rápido",
        "tipo": "Tabela Combinada SSW",
        "contrato": "Tabela Promocional PR93970 / SSW0075",
        "abrangencia_tags": ["PR", "SP", "MS", "MT", "GO"],
        "descricao": "Rotas diretas PR, SP interior, MS, MT e Goiânia",
    },
    "GARCIA": {
        "nome": "Viação Garcia 24H",
        "tipo": "Tabela Encomendas Urgentes",
        "contrato": "Tabela Combinada 08/04/2026 (Garcia/Brasil Sul)",
        "abrangencia_tags": ["PR", "SC", "RS", "SP", "MS", "MG", "RJ"],
        "descricao": "Serviço expresso de alta prioridade 24h a 48h",
    },
    "SUDOESTE": {
        "nome": "Sudoeste Transportes",
        "tipo": "Tabela Proposta Comercial",
        "contrato": "Proposta Comercial 15/06/2026 (Cabos de Rede)",
        "abrangencia_tags": ["PR", "SC", "SP"],
        "descricao": "Polos e regiões atendidas PR, SC e SP",
    },
    "CARRION": {
        "nome": "Carrion Logística",
        "tipo": "Tabela Comercial Combinada",
        "contrato": "Proposta Comercial 16/06/2026 (LRF Presidente Prudente)",
        "abrangencia_tags": ["SP"],
        "descricao": "Especialista exclusivo no Estado de São Paulo",
    },
    "EXPRESSO_SAO_MIGUEL": {
        "nome": "Expresso São Miguel",
        "tipo": "Contrato Nr. 96094/2025",
        "contrato": "Tabela Fracionada Ref. 02/2025 Eletro/Eletrônicos",
        "abrangencia_tags": ["PR", "SC", "RS", "SP"],
        "descricao": "Malha Sul e SP fracionado",
    },
    "LOGDI": {
        "nome": "Logdi Logística",
        "tipo": "Tabela Fracionada 13/03/2026",
        "contrato": "Tabela Fracionada Nordeste (Base OPR-PR)",
        "abrangencia_tags": ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"],
        "descricao": "Especialista Nordeste (Capitais e Interiores)",
    },
    "OURO_NEGRO": {
        "nome": "Ouro Negro",
        "tipo": "Proposta Comercial 20-05-2026",
        "contrato": "Tabela Excedente Ouro Negro 2026",
        "abrangencia_tags": ["PR", "SC", "RS", "SP"],
        "descricao": "Atendimento Paraná, Santa Catarina, RS e São Paulo",
    },
    "RODONAVES": {
        "nome": "Rodonaves (RTE)",
        "tipo": "Proposta Comercial 556282",
        "contrato": "Tabela 3209556 Medida-Distância (20/01/2026)",
        "abrangencia_tags": ["PR", "SP", "MG", "MS", "MT", "GO", "DF", "RJ", "SC", "RS"],
        "descricao": "Ampla malha rodoviária por faixa quilométrica",
    },
    "TECMAR": {
        "nome": "Tecmar Transportes",
        "tipo": "Contrato 22-000667",
        "contrato": "Carga Fracionada Natureza NEXT (016662)",
        "abrangencia_tags": ["RO", "RR", "TO", "PA", "AC", "AM", "AP"],
        "descricao": "Especialista Norte e Centro-Oeste Fluvial/Rodoviário",
    },
    "AGEX": {
        "nome": "Agex Transportes",
        "tipo": "Tabela AGE-010326",
        "contrato": "Tabela Eletro-Eletrônicos Londrina-PR (01/03/2026)",
        "abrangencia_tags": ["PR", "SC", "RS", "SP", "MS"],
        "descricao": "Transporte urgente interior PR, SC, RS, SP e MS",
    },
    "VIP": {
        "nome": "Atendimento VIP",
        "tipo": "Tabela Geral Atualizada 01/04/2026",
        "contrato": "Tabela Regional Vigência 01/04/2026",
        "abrangencia_tags": ["PR (Norte/Noroeste)"],
        "descricao": "Entregas regionais rápidas no Norte e Noroeste do Paraná",
    },
    "ARAGAO": {
        "nome": "Aragão Entregas",
        "tipo": "Proposta Comercial Combinada",
        "contrato": "Proposta Comercial 19/06/2026",
        "abrangencia_tags": ["GO", "MT", "MS"],
        "descricao": "Atendimento exclusivo GO, MT e MS",
    },
}

# ==============================================================================
# IDENTIDADE VISUAL E LOGOTIPOS VETORIAIS DAS 16 TRANSPORTADORAS
# ==============================================================================

LOGOS_CONFIG = {
    "BRASPRESS": {
        "bg": "#002B66", "accent": "#FF6600", "text": "#FFFFFF", "sub": "TRANSPORTE & LOGÍSTICA",
        "icon": """<polygon points="4,18 20,4 28,4 12,18" fill="#FF6600"/><polygon points="14,24 30,10 38,10 22,24" fill="#FFFFFF"/>""",
        "title": "BRASPRESS"
    },
    "ALFA": {
        "bg": "#0B2B64", "accent": "#E30613", "text": "#FFFFFF", "sub": "TRANSPORTES",
        "icon": """<path d="M12 26 L22 6 L32 26 L26 26 L22 17 L18 26 Z" fill="#E30613"/><circle cx="34" cy="10" r="3" fill="#FFFFFF"/>""",
        "title": "ALFA"
    },
    "GARCIA": {
        "bg": "#0A2F87", "accent": "#FDB813", "text": "#FFFFFF", "sub": "ENCOMENDAS 24H",
        "icon": """<circle cx="20" cy="16" r="12" fill="none" stroke="#FDB813" stroke-width="2.5"/><polyline points="20,9 20,16 26,16" stroke="#FDB813" stroke-width="2.5" fill="none"/>""",
        "title": "VIAÇÃO GARCIA"
    },
    "PRINCESA": {
        "bg": "#005A2B", "accent": "#FFD200", "text": "#FFFFFF", "sub": "ENCOMENDAS",
        "icon": """<path d="M10 24 L14 12 L20 18 L26 12 L30 24 Z" fill="#FFD200"/><circle cx="14" cy="10" r="2" fill="#FFFFFF"/><circle cx="20" cy="15" r="2" fill="#FFFFFF"/><circle cx="26" cy="10" r="2" fill="#FFFFFF"/>""",
        "title": "PRINCESA DOS CAMPOS"
    },
    "TW": {
        "bg": "#B71C1C", "accent": "#FFFFFF", "text": "#FFFFFF", "sub": "TRANSPORTES",
        "icon": """<rect x="8" y="8" width="24" height="16" rx="3" fill="#1A237E"/><text x="20" y="20" font-family="Arial, sans-serif" font-weight="900" font-size="11" fill="#FFFFFF" text-anchor="middle">TW</text>""",
        "title": "TW TRANSPORTES"
    },
    "EXPRESSO_SAO_MIGUEL": {
        "bg": "#881337", "accent": "#FFFFFF", "text": "#FFFFFF", "sub": "CARGAS & ENCOMENDAS",
        "icon": """<path d="M8 24 L20 8 L32 24 Z" fill="none" stroke="#FFFFFF" stroke-width="2.5"/><path d="M14 24 L20 16 L26 24 Z" fill="#FDA4AF"/>""",
        "title": "SÃO MIGUEL"
    },
    "RODONAVES": {
        "bg": "#007A33", "accent": "#D32F2F", "text": "#FFFFFF", "sub": "RTE TRANSPORTE",
        "icon": """<path d="M8 22 Q20 6 32 22" fill="none" stroke="#D32F2F" stroke-width="3"/><circle cx="20" cy="16" r="4" fill="#FFFFFF"/>""",
        "title": "RODONAVES"
    },
    "COOPEX": {
        "bg": "#14532D", "accent": "#EA580C", "text": "#FFFFFF", "sub": "CARGAS EXPRESSAS",
        "icon": """<circle cx="15" cy="16" r="7" fill="#EA580C"/><circle cx="25" cy="16" r="7" fill="#22C55E" opacity="0.8"/>""",
        "title": "COOPEX"
    },
    "SUDOESTE": {
        "bg": "#0C4A6E", "accent": "#38BDF8", "text": "#FFFFFF", "sub": "TRANSPORTES",
        "icon": """<polygon points="8,24 20,8 32,24" fill="#0284C7"/><polygon points="12,24 20,13 28,24" fill="#38BDF8"/>""",
        "title": "SUDOESTE"
    },
    "OURO_NEGRO": {
        "bg": "#1C1917", "accent": "#F59E0B", "text": "#FFFFFF", "sub": "CARGAS FRACIONADAS",
        "icon": """<circle cx="20" cy="16" r="10" fill="#F59E0B"/><polygon points="16,20 20,12 24,20" fill="#1C1917"/>""",
        "title": "OURO NEGRO"
    },
    "ENVIA_RAPIDO": {
        "bg": "#0F172A", "accent": "#FACC15", "text": "#FFFFFF", "sub": "LOGÍSTICA INTEGRADA",
        "icon": """<polygon points="18,6 10,18 19,18 16,26 26,14 17,14" fill="#FACC15"/>""",
        "title": "ENVIA RÁPIDO"
    },
    "CARRION": {
        "bg": "#1E3A8A", "accent": "#EF4444", "text": "#FFFFFF", "sub": "LOGÍSTICA SP",
        "icon": """<rect x="8" y="10" width="16" height="12" rx="2" fill="#EF4444"/><rect x="20" y="14" width="8" height="8" rx="1" fill="#FFFFFF"/>""",
        "title": "CARRION"
    },
    "TECMAR": {
        "bg": "#0369A1", "accent": "#BAE6FD", "text": "#FFFFFF", "sub": "TRANSPORTE & LOGÍSTICA",
        "icon": """<path d="M8 20 Q14 12 20 20 T32 20" fill="none" stroke="#BAE6FD" stroke-width="2.5"/><polygon points="20,8 24,14 16,14" fill="#FFFFFF"/>""",
        "title": "TECMAR"
    },
    "LOGDI": {
        "bg": "#4338CA", "accent": "#34D399", "text": "#FFFFFF", "sub": "NORDESTE EXPRESS",
        "icon": """<rect x="8" y="8" width="10" height="16" rx="2" fill="#34D399"/><rect x="22" y="8" width="10" height="16" rx="2" fill="#A7F3D0"/>""",
        "title": "LOGDI"
    },
    "AGEX": {
        "bg": "#C2410C", "accent": "#FED7AA", "text": "#FFFFFF", "sub": "ENCOMENDAS",
        "icon": """<polygon points="8,16 20,8 32,16 20,24" fill="#FED7AA"/><polygon points="13,16 20,11 27,16 20,21" fill="#C2410C"/>""",
        "title": "AGEX"
    },
    "VIP": {
        "bg": "#78350F", "accent": "#FBBF24", "text": "#FFFFFF", "sub": "REGIONAL NORTE PR",
        "icon": """<polygon points="20,6 23,13 30,13 24,18 26,25 20,20 14,25 16,18 10,13 17,13" fill="#FBBF24"/>""",
        "title": "ATENDIMENTO VIP"
    },
    "ARAGAO": {
        "bg": "#D97706", "accent": "#FFFFFF", "text": "#FFFFFF", "sub": "ENTREGAS RÁPIDAS",
        "icon": """<polygon points="4,16 12,8 20,16 12,24" fill="#FFFFFF"/><polygon points="20,16 28,8 36,16 28,24" fill="#FDE68A"/>""",
        "title": "ARAGÃO"
    }
}

def gerar_badge_logo_html(nome_transp: str) -> str:
    """Gera bloco HTML com logotipo vetorial de alta definição da transportadora."""
    nome_norm = str(nome_transp).upper()
    chave = "BRASPRESS"
    for k, conf in LOGOS_CONFIG.items():
        if conf["title"].split()[0] in nome_norm or k in nome_norm or (k == "EXPRESSO_SAO_MIGUEL" and "MIGUEL" in nome_norm):
            chave = k
            break
    
    c = LOGOS_CONFIG[chave]
    
    return f'''<div style="display:inline-flex;align-items:center;background:{c['bg']};border-radius:8px;padding:6px 12px;box-shadow:0 2px 6px rgba(0,0,0,0.12);border:1px solid rgba(255,255,255,0.15);width:100%;box-sizing:border-box;">
      <div style="flex-shrink:0;margin-right:10px;width:34px;height:30px;display:flex;align-items:center;justify-content:center;">
        <svg width="34" height="30" viewBox="0 0 40 32" xmlns="http://www.w3.org/2000/svg">
          {c['icon']}
        </svg>
      </div>
      <div style="overflow:hidden;line-height:1.15;">
        <div style="font-family:'Segoe UI',Inter,sans-serif;font-weight:900;font-size:0.92rem;color:{c['text']};letter-spacing:-0.02em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
          {c['title']}
        </div>
        <div style="font-family:'Segoe UI',Inter,sans-serif;font-weight:700;font-size:0.62rem;color:{c['accent']};letter-spacing:0.06em;text-transform:uppercase;white-space:nowrap;margin-top:1px;">
          {c['sub']}
        </div>
      </div>
    </div>'''

# ==============================================================================
# 2. CIDADES ATENDIDAS ESPECÍFICAS (STRICT LISTS)
# ==============================================================================

# Cidades do Norte/Noroeste atendidas pela Transportadora VIP
CIDADES_VIP_PR = {
    "londrina", "ibipora", "cambe", "rolandia", "arapongas", "apucarana",
    "maringa", "cianorte", "campo mourao", "paranavai", "cornelio procopio",
    "andira", "sertanopolis", "jaguapita", "santo antonio da platina",
    "sao jeronimo da serra", "telemaco borba", "bela vista do paraiso",
    "alvorada do sul", "porecatu", "primeiro de maio", "assai", "ibaiti"
}

# Cidades de SP atendidas com tarifas específicas
CIDADES_CARRION_SP = {
    "sao paulo", "guarulhos", "osasco", "santo andre", "sao bernardo do campo",
    "sao caetano do sul", "diadema", "campinas", "assis", "marilia",
    "presidente prudente", "ourinhos", "tupa", "adamantina", "dracena",
    "aracatuba", "birigui", "bauru", "botucatu", "jau", "lins", "sao carlos",
    "araraquara", "ribeirao preto", "franca", "sorocaba", "jundiai", "piracicaba"
}

# Cidades atendidas pela Aragão (Tabelas 1, 2 e 3)
CIDADES_ARAGAO_TB1 = {
    "acreuna", "aparecida de goiania", "goiania", "jatai", "mineiros", "rio verde", "senador canedo",
    "acorizal", "alta floresta", "alto garcas", "alto paraguai", "alto taquari", "araputanga", "arenapolis", "barra do garcas", "boa esperanca do norte", "brasnorte", "caceres", "campo novo do parecis", "campo verde", "campos de julio", "carlinda", "chapada dos guimaraes", "claudia", "colider", "cuiaba", "general carneiro", "gloria d oeste", "guaranta do norte", "guiratinga", "ipiranga do norte", "itanhanga", "itauba", "itiquira", "jaciara", "jangada", "jauru", "juara", "juscimeira", "lambari d oeste", "lucas do rio verde", "marcelandia", "matupa", "mirassol d oeste", "nobres", "nortelandia", "nossa senhora do livramento", "nova brasilandia", "nova canaa do norte", "nova guarita", "nova lacerda", "nova marilandia", "nova maringa", "nova mutum", "nova olimpia", "nova santa helena", "nova ubirata", "nova xavantina", "novo horizonte do norte", "novo mundo", "paranatinga"
}

CIDADES_ARAGAO_TB2 = {
    "pedra preta", "peixoto de azevedo", "planalto da serra", "pocone", "pontal do araguaia", "pontes e lacerda", "primavera do leste", "rondonopolis", "rosario oeste", "sao jose dos quatro marcos", "sapezal", "sinop", "sorriso",
    "agua clara", "alcinopolis", "amambai", "anastacio", "anaurilandia", "angelica", "antonio joao", "aparecida do taboado", "aquidauana", "aral moreira", "bandeirantes", "bataguassu", "bataypora", "bonito", "brasilandia", "caarapo", "camapua", "campo grande", "cassilandia", "chapadao do sul", "coronel sapucaia", "corumba", "costa rica", "coxim", "deodapolis", "douradina", "dourados", "eldorado", "fatima do sul", "gloria de dourados", "guia lopes da laguna", "iguatemi", "inocencia", "itapora", "itaquirai", "ivinhema", "japora", "jardim", "jatei", "juti", "maracaju", "mundo novo", "navirai", "nioaque", "nova alvorada do sul", "novo horizonte do sul", "paranaiba"
}

CIDADES_ARAGAO_TB3 = {
    "paranhos", "ponta pora", "ribas do rio pardo", "rio brilhante", "rio verde de mato grosso", "rochedo", "santa rita do pardo", "sao gabriel do oeste", "selviria", "sidrolandia", "sonora", "tacuru", "taquarussu", "tres lagoas", "vicentina",
    "agua boa", "alto araguaia", "canarana", "comodoro", "conquista d oeste", "curvelandia", "denise", "diamantino", "dom aquino", "feliz natal", "figueiropolis d oeste", "porto dos gauchos", "porto esperidiao", "porto estrela", "poxoreu", "querencia", "reserva do cabacal", "ribeirao cascalheira", "rio branco", "salto do ceu", "santa carmem", "santa rita do trivelato", "santo afonso", "santo antonio do leste", "sao jose do xingu", "sao pedro da cipa", "tabapora", "tangara da serra", "tapurah", "terra nova do norte", "tesouro", "uniao do sul", "vera", "vila bela da santissima trindade"
}

# Distâncias estimadas aproximadas (em KM rodoviários a partir de Londrina)
# Utilizadas estritamente para a tabela da RODONAVES que cobra por KM rodado
DISTANCIAS_LONDRINA_KM = {
    ("PR", "londrina"): 15,
    ("PR", "cambe"): 20,
    ("PR", "ibipora"): 22,
    ("PR", "rolandia"): 30,
    ("PR", "arapongas"): 45,
    ("PR", "apucarana"): 60,
    ("PR", "maringa"): 100,
    ("PR", "cornelio procopio"): 75,
    ("PR", "campo mourao"): 170,
    ("PR", "paranavai"): 175,
    ("PR", "cianorte"): 170,
    ("PR", "ponta grossa"): 275,
    ("PR", "curitiba"): 390,
    ("PR", "cascavel"): 380,
    ("PR", "foz do iguacu"): 510,
    ("SP", "assis"): 135,
    ("SP", "presidente prudente"): 175,
    ("SP", "marilia"): 210,
    ("SP", "ourinhos"): 170,
    ("SP", "bauru"): 310,
    ("SP", "campinas"): 510,
    ("SP", "sao paulo"): 535,
    ("SP", "guarulhos"): 550,
    ("SP", "ribeirao preto"): 480,
    ("SC", "joinville"): 520,
    ("SC", "florianopolis"): 680,
    ("SC", "blumenau"): 580,
    ("SC", "chapeco"): 610,
    ("RS", "passo fundo"): 680,
    ("RS", "porto alegre"): 910,
    ("RS", "caxias do sul"): 820,
    ("MS", "campo grande"): 650,
    ("MS", "dourados"): 490,
    ("GO", "goiania"): 870,
    ("MG", "belo horizonte"): 940,
    ("RJ", "rio de janeiro"): 980,
}


def _limpar_texto(txt: str) -> str:
    if not txt:
        return ""
    import unicodedata
    t = unicodedata.normalize("NFKD", str(txt)).encode("ASCII", "ignore").decode("ASCII")
    return t.strip().lower()


def _estimar_km_rodonaves(uf: str, cidade: str) -> int:
    cid_norm = _limpar_texto(cidade)
    if (uf, cid_norm) in DISTANCIAS_LONDRINA_KM:
        return DISTANCIAS_LONDRINA_KM[(uf, cid_norm)]
    
    # Fallback conservador baseado no estado de destino a partir de Londrina
    km_por_uf = {
        "PR": 300,
        "SP": 500,
        "SC": 650,
        "MS": 650,
        "RS": 850,
        "GO": 900,
        "DF": 950,
        "MG": 900,
        "RJ": 1000,
        "MT": 1200,
    }
    return km_por_uf.get(uf, 1200)


# ==============================================================================
# 3. VERIFICADOR ESTRITO DE COBERTURA (STRICT ROUTE MATCHING)
# ==============================================================================

def verificar_cobertura_estrita(transportadora_key: str, uf: str, cidade: str, cep: str) -> Tuple[bool, str]:
    """
    Verifica com rigor absoluto se a transportadora atende o destino solicitado.
    Retorna (True, "Atendida") ou (False, "Motivo da não cobertura").
    """
    uf_u = (uf or "").strip().upper()
    cid_norm = _limpar_texto(cidade)
    cep_limpo = re.sub(r"\D", "", str(cep or ""))

    cfg = TRANSPORTADORAS_CONFIG.get(transportadora_key)
    if not cfg:
        return False, "Transportadora não configurada no sistema"

    # 1. BRASPRESS: Cobertura Nacional
    if transportadora_key == "BRASPRESS":
        return True, "Cobertura nacional confirmada"

    # 2. COOPEX: PR, SC, RS
    if transportadora_key == "COOPEX":
        if uf_u in ["PR", "SC", "RS"]:
            return True, f"Cobertura regional confirmada para {uf_u}"
        return False, f"Não atende esta região (atende somente PR, SC, RS)"

    # 3. PRINCESA DOS CAMPOS: SP, SC, RS e no PR estritamente Curitiba/RMC
    if transportadora_key == "PRINCESA":
        if uf_u in ["SP", "SC", "RS"]:
            return True, f"Cobertura confirmada para {uf_u}"
        elif uf_u == "PR":
            # Estrito: No PR, a tabela Z032 cobre APENAS Curitiba (REG-CURITIBA-PR-01 000148)
            # CEPs de Curitiba iniciam em 80000 a 82999
            eh_curitiba = "curitiba" in cid_norm or (len(cep_limpo) == 8 and cep_limpo.startswith(("80", "81", "82", "83")))
            if eh_curitiba:
                return True, "Cobertura no PR restrita à Curitiba e Região Metropolitana (Tabela Z032)"
            return False, "Não atende esta região (tabela atende somente Curitiba no PR; não atende Londrina/Interior)"
        return False, f"Não atende esta região (atende SP, SC, RS e apenas Curitiba no PR)"

    # 4. ALFA: PR, SC, RS, SP, MS, MT, GO, DF, MG, RJ, ES
    if transportadora_key == "ALFA":
        if uf_u in ["PR", "SC", "RS", "SP", "MS", "MT", "GO", "DF", "MG", "RJ", "ES"]:
            return True, f"Cobertura confirmada para {uf_u}"
        return False, f"Não atende esta região (atende PR, SC, RS, SP, MS, MT, GO, DF, MG, RJ, ES)"

    # 5. TW TRANSPORTES: PR, SC, RS
    if transportadora_key == "TW":
        if uf_u in ["PR", "SC", "RS"]:
            return True, f"Cobertura confirmada para {uf_u}"
        return False, f"Não atende esta região (atende somente RS, SC e PR)"

    # 6. ENVIA RÁPIDO: PR, SP, MS, MT, GO
    if transportadora_key == "ENVIA_RAPIDO":
        if uf_u in ["PR", "SP", "MS", "MT", "GO"]:
            return True, f"Cobertura confirmada para {uf_u}"
        return False, f"Não atende esta região (atende PR, SP, MS, MT e GO)"

    # 7. VIAÇÃO GARCIA 24H: PR, SC, RS, SP, MS, MG, RJ
    if transportadora_key == "GARCIA":
        if uf_u in ["PR", "SC", "RS", "SP", "MS", "MG", "RJ"]:
            return True, f"Cobertura confirmada para {uf_u} (Linhas Expressas)"
        return False, f"Não atende esta região (atende PR, SC, RS, SP, MS, MG, RJ)"

    # 8. SUDOESTE: PR, SC, SP
    if transportadora_key == "SUDOESTE":
        if uf_u in ["PR", "SC", "SP"]:
            return True, f"Cobertura confirmada para {uf_u}"
        return False, f"Não atende esta região (atende PR, SC e SP)"

    # 9. CARRION: Exclusivo SP
    if transportadora_key == "CARRION":
        if uf_u == "SP":
            return True, "Cobertura confirmada para o Estado de São Paulo"
        return False, "Não atende esta região (atende exclusivamente o Estado de São Paulo)"

    # 10. EXPRESSO SÃO MIGUEL: PR, SC, RS, SP
    if transportadora_key == "EXPRESSO_SAO_MIGUEL":
        if uf_u in ["PR", "SC", "RS", "SP"]:
            return True, f"Cobertura confirmada para {uf_u}"
        return False, f"Não atende esta região (atende PR, SC, RS e SP)"

    # 11. LOGDI: Exclusivo Nordeste (AL, BA, CE, MA, PB, PE, PI, RN, SE)
    if transportadora_key == "LOGDI":
        if uf_u in ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"]:
            return True, f"Cobertura confirmada para a Região Nordeste ({uf_u})"
        return False, "Não atende esta região (atende exclusivamente o Nordeste: AL, BA, CE, MA, PB, PE, PI, RN, SE)"

    # 12. OURO NEGRO: PR, SC, RS, SP
    if transportadora_key == "OURO_NEGRO":
        if uf_u in ["PR", "SC", "RS", "SP"]:
            return True, f"Cobertura confirmada para {uf_u}"
        return False, f"Não atende esta região (atende PR, SC, RS e SP)"

    # 13. RODONAVES: PR, SP, MG, MS, MT, GO, DF, RJ, SC, RS
    if transportadora_key == "RODONAVES":
        if uf_u in ["PR", "SP", "MG", "MS", "MT", "GO", "DF", "RJ", "SC", "RS"]:
            return True, f"Cobertura rodoviária confirmada para {uf_u}"
        return False, f"Não atende esta região (atende PR, SP, MG, MS, MT, GO, DF, RJ, SC, RS)"

    # 14. TECMAR: RO, RR, TO, PA, AC, AM, AP
    if transportadora_key == "TECMAR":
        if uf_u in ["RO", "RR", "TO", "PA", "AC", "AM", "AP"]:
            return True, f"Cobertura fluvial/rodoviária confirmada para a Região Norte ({uf_u})"
        return False, "Não atende esta região (atende exclusivamente o Norte e Centro-Oeste: RO, RR, TO, PA, AC, AM, AP)"

    # 15. AGEX: PR, SC, RS, SP, MS
    if transportadora_key == "AGEX":
        if uf_u in ["PR", "SC", "RS", "SP", "MS"]:
            return True, f"Cobertura expressa confirmada para {uf_u}"
        return False, f"Não atende esta região (atende PR, SC, RS, SP e MS)"

    # 16. ATENDIMENTO VIP: Exclusivo Norte e Noroeste do Paraná
    if transportadora_key == "VIP":
        if uf_u == "PR":
            if not cid_norm or cid_norm in CIDADES_VIP_PR:
                return True, "Cobertura confirmada para polo/região Norte e Noroeste do PR"
            return False, f"Não atende esta região (atende apenas cidades do Norte/Noroeste do PR, não atende {cidade})"
        return False, "Não atende esta região (atende exclusivamente o Norte/Noroeste do Paraná)"

    # 17. ARAGÃO: Exclusivo GO, MT, MS baseado nas 3 tabelas
    if transportadora_key == "ARAGAO":
        if uf_u in ["GO", "MT", "MS"]:
            if cid_norm in CIDADES_ARAGAO_TB1 or cid_norm in CIDADES_ARAGAO_TB2 or cid_norm in CIDADES_ARAGAO_TB3:
                return True, f"Cobertura confirmada para {cid_norm.title()} - {uf_u}"
            return False, f"Não atende esta região (cidade {cidade} não consta nas tabelas contratuais)"
        return False, f"Não atende esta região (atende apenas GO, MT e MS)"

    return False, "Região não coberta"


# ==============================================================================
# 4. MOTORES DE CÁLCULO ESTRITO DAS TABELAS CONTRATUAIS
# ==============================================================================

def calcular_frete_estrito(
    transportadora_key: str,
    peso_tarifado: float,
    peso_real: float,
    valor_nf: float,
    uf: str,
    cidade: str,
    cep: str
) -> Dict[str, Any]:
    """
    Executa o cálculo preciso da tarifa conforme a respectiva tabela contratual,
    ou rejeita formalmente com 'Não atende esta região'.
    """
    cfg = TRANSPORTADORAS_CONFIG.get(transportadora_key, {})
    nome = cfg.get("nome", transportadora_key)
    base_tarifaria = cfg.get("contrato", "Tabela Contratual")
    tags = cfg.get("abrangencia_tags", [])

    # Validação estrita de rota antes de qualquer cálculo
    atende, motivo = verificar_cobertura_estrita(transportadora_key, uf, cidade, cep)
    if not atende:
        return {
            "Transportadora": nome,
            "Valor Frete (R$)": None,
            "Prazo (Dias Úteis)": None,
            "Base Tarifária": base_tarifaria,
            "Status": "Não atende esta região",
            "Atendida": False,
            "Motivo": motivo,
            "Tags": tags,
            "Composicao": {},
        }

    uf_u = (uf or "").strip().upper()
    cid_norm = _limpar_texto(cidade)
    peso = max(float(peso_tarifado or 1.0), 1.0)
    vnf = max(float(valor_nf or 0.0), 0.0)
    fracao_100 = math.ceil(peso / 100.0)

    # -------------------------------------------------------------------------
    # COOPEX (Tabela Padrão CP010 / LDN_PADRAO_CP010)
    # -------------------------------------------------------------------------
    if transportadora_key == "COOPEX":
        if uf_u == "PR":
            # PR 0 (Rota Express: Apucarana, Arapongas, Londrina, Cambé, Rolândia)
            if any(p in cid_norm for p in ["londrina", "cambe", "rolandia", "arapongas", "apucarana"]):
                faixas = [(10, 17.36), (20, 21.49), (40, 25.76), (60, 29.61), (100, 46.48)]
                exc = 0.46
                prazo = 1
            elif any(p in cid_norm for p in ["curitiba", "cascavel", "umuarama", "francisco beltrao", "pato branco", "ponta grossa", "maringa", "cianorte", "telemaco"]):
                faixas = [(10, 22.02), (20, 26.45), (40, 29.22), (60, 33.53), (100, 50.91)]
                exc = 0.51
                prazo = 2
            else:
                faixas = [(10, 34.07), (20, 37.92), (40, 44.27), (60, 49.15), (100, 64.44)]
                exc = 0.64
                prazo = 3
        elif uf_u == "SC":
            if any(p in cid_norm for p in ["blumenau", "itajai", "joinville", "jaragua", "brusque", "canoinhas"]):
                faixas = [(10, 26.98), (20, 33.00), (40, 38.65), (60, 44.16), (100, 59.09)]
                exc = 0.59
                prazo = 2
            elif any(p in cid_norm for p in ["florianopolis", "tubarao", "criciuma"]):
                faixas = [(10, 31.56), (20, 35.72), (40, 42.39), (60, 49.96), (100, 64.96)]
                exc = 0.65
                prazo = 3
            else:
                faixas = [(10, 36.22), (20, 44.29), (40, 51.98), (60, 60.13), (100, 72.73)]
                exc = 0.73
                prazo = 3
        else:  # RS
            if any(p in cid_norm for p in ["porto alegre", "novo hamburgo", "caxias", "bento"]):
                faixas = [(10, 37.70), (20, 45.02), (40, 54.22), (60, 61.39), (100, 73.15)]
                exc = 0.73
                prazo = 3
            else:
                faixas = [(10, 39.40), (20, 47.40), (40, 56.49), (60, 65.35), (100, 77.60)]
                exc = 0.78
                prazo = 4

        frete_peso = faixas[-1][1] + max(0.0, peso - 100.0) * exc if peso > 100.0 else next(v for limit, v in faixas if peso <= limit)
        pedagio = fracao_100 * 5.00
        gris = vnf * 0.0020
        adv = vnf * 0.0025
        total = round(frete_peso + pedagio + gris + adv, 2)
        return {
            "Transportadora": nome, "Valor Frete (R$)": total, "Prazo (Dias Úteis)": prazo,
            "Base Tarifária": base_tarifaria, "Status": "Tarifa contratual estrita",
            "Atendida": True, "Motivo": "Atendida", "Tags": tags,
            "Composicao": {"Frete Peso": frete_peso, "Pedágio": pedagio, "GRIS": gris, "ADV": adv}
        }

    # -------------------------------------------------------------------------
    # PRINCESA DOS CAMPOS (Tabela Z032)
    # -------------------------------------------------------------------------
    if transportadora_key == "PRINCESA":
        # Curitiba (PR), SP, SC, RS
        if uf_u == "PR":  # Curitiba
            faixas = [(10, 29.65), (20, 32.35), (30, 35.05), (50, 40.44), (70, 43.16), (100, 53.91)]
            excedente = 0.55
            prazo = 2
        elif uf_u == "SP":
            faixas = [(10, 42.15 if "sao paulo" in cid_norm else 45.20),
                      (20, 45.96 if "sao paulo" in cid_norm else 49.31),
                      (30, 49.80 if "sao paulo" in cid_norm else 53.41),
                      (50, 57.47 if "sao paulo" in cid_norm else 61.63),
                      (70, 61.31 if "sao paulo" in cid_norm else 65.73),
                      (100, 76.63 if "sao paulo" in cid_norm else 82.18)]
            excedente = 0.77 if "sao paulo" in cid_norm else 0.80
            prazo = 3
        elif uf_u == "SC":
            faixas = [(10, 42.58 if "florianopolis" in cid_norm else 57.24),
                      (20, 49.38 if "florianopolis" in cid_norm else 66.40),
                      (30, 51.07 if "florianopolis" in cid_norm else 68.68),
                      (50, 59.58 if "florianopolis" in cid_norm else 80.13),
                      (70, 68.11 if "florianopolis" in cid_norm else 91.56),
                      (100, 85.11 if "florianopolis" in cid_norm else 114.46)]
            excedente = 0.87 if "florianopolis" in cid_norm else 1.15
            prazo = 3
        else:  # RS
            faixas = [(10, 54.89 if "porto alegre" in cid_norm else 72.37),
                      (20, 61.01 if "porto alegre" in cid_norm else 80.39),
                      (30, 73.21 if "porto alegre" in cid_norm else 96.50),
                      (50, 85.42 if "porto alegre" in cid_norm else 112.57),
                      (70, 97.62 if "porto alegre" in cid_norm else 128.65),
                      (100, 122.02 if "porto alegre" in cid_norm else 160.79)]
            excedente = 1.23 if "porto alegre" in cid_norm else 1.62
            prazo = 4

        # Cálculo da faixa
        frete_peso = faixas[-1][1] + max(0.0, peso - 100.0) * excedente if peso > 100.0 else next(v for limit, v in faixas if peso <= limit)
        pedagio = fracao_100 * 5.96
        gris = max(vnf * 0.0015, 2.50)
        adv = max(vnf * 0.0015, 2.50)
        tas = 4.89
        total = round(frete_peso + pedagio + gris + adv + tas, 2)
        return {
            "Transportadora": nome, "Valor Frete (R$)": total, "Prazo (Dias Úteis)": prazo,
            "Base Tarifária": base_tarifaria, "Status": "Tarifa contratual estrita",
            "Atendida": True, "Motivo": "Atendida", "Tags": tags,
            "Composicao": {"Frete Peso": frete_peso, "Pedágio": pedagio, "GRIS": gris, "ADV": adv, "TAS": tas}
        }

    # -------------------------------------------------------------------------
    # SUDOESTE TRANSPORTES (Proposta Comercial 15/06/2026)
    # -------------------------------------------------------------------------
    if transportadora_key == "SUDOESTE":
        if uf_u == "PR":
            # Polos: CTBA, FBTP, LDN, MGA, CVL, FOZ
            eh_polo = any(p in cid_norm for p in ["curitiba", "londrina", "maringa", "cascavel", "foz", "beltrao"])
            if eh_polo:
                faixas = [(10, 30.26), (20, 32.87), (30, 35.79), (50, 39.28), (70, 44.98), (100, 52.50)]
                exc = 0.49
            else:
                faixas = [(10, 37.46), (20, 40.84), (30, 43.93), (50, 47.25), (70, 52.34), (100, 59.36)]
                exc = 0.52
            prazo = 2
        elif uf_u == "SC":
            eh_polo = any(p in cid_norm for p in ["chapeco", "criciuma", "joinville", "florianopolis"])
            if eh_polo:
                faixas = [(10, 45.74), (20, 48.96), (30, 52.83), (50, 57.35), (70, 63.96), (100, 69.34)]
                exc = 0.70
            else:
                faixas = [(10, 61.94), (20, 65.72), (30, 69.30), (70, 79.93), (100, 83.54)]
                exc = 0.84
            prazo = 3
        else:  # SP
            eh_polo = any(p in cid_norm for p in ["sao paulo", "guarulhos", "campinas", "osasco"])
            if eh_polo:
                faixas = [(10, 52.57), (20, 56.19), (30, 62.53), (50, 71.52), (70, 82.54), (100, 94.31)]
                exc = 0.98
            else:
                faixas = [(10, 112.71), (20, 118.65), (30, 125.30), (50, 131.90), (70, 140.65), (100, 156.36)]
                exc = 1.68
            prazo = 3

        frete_peso = faixas[-1][1] + max(0.0, peso - 100.0) * exc if peso > 100.0 else next(v for limit, v in faixas if peso <= limit)
        pedagio = fracao_100 * 4.00
        adv = vnf * 0.0020
        gris = vnf * 0.0020
        total = round(frete_peso + pedagio + adv + gris, 2)
        return {
            "Transportadora": nome, "Valor Frete (R$)": total, "Prazo (Dias Úteis)": prazo,
            "Base Tarifária": base_tarifaria, "Status": "Tarifa contratual estrita",
            "Atendida": True, "Motivo": "Atendida", "Tags": tags,
            "Composicao": {"Frete Peso": frete_peso, "Pedágio": pedagio, "ADV": adv, "GRIS": gris}
        }

    # -------------------------------------------------------------------------
    # VIAÇÃO GARCIA 24H (Tabela Encomendas Expressas)
    # -------------------------------------------------------------------------
    if transportadora_key == "GARCIA":
        tabela_garcia = {
            "PR": ([(5, 38.61), (10, 41.94), (20, 45.23), (30, 49.64), (50, 56.28), (70, 59.57), (100, 64.01)], 0.95, 1),
            "SP": ([(5, 50.77), (10, 56.29), (20, 60.69), (30, 65.09), (50, 72.82), (70, 79.52), (100, 84.96)], 1.12, 2),
            "SC": ([(5, 50.77), (10, 55.17), (20, 59.57), (30, 65.09), (50, 70.62), (70, 78.35), (100, 87.16)], 1.13, 2),
            "RS": ([(5, 52.97), (10, 58.49), (20, 62.90), (30, 68.41), (50, 75.27), (70, 78.35), (100, 82.75)], 1.19, 2),
            "MS": ([(5, 65.09), (10, 69.52), (20, 76.13), (30, 80.54), (50, 84.96), (70, 90.48), (100, 98.21)], 1.35, 2),
            "MG": ([(5, 50.77), (10, 55.17), (20, 59.57), (30, 65.09), (50, 70.62), (70, 78.35), (100, 87.16)], 1.13, 2),
            "RJ": ([(5, 82.75), (10, 90.48), (20, 95.99), (30, 103.72), (50, 112.54), (70, 123.57), (100, 132.41)], 1.67, 3),
        }
        faixas, exc, prazo = tabela_garcia.get(uf_u, (tabela_garcia["PR"]))
        frete_peso = faixas[-1][1] + max(0.0, peso - 100.0) * exc if peso > 100.0 else next(v for limit, v in faixas if peso <= limit)
        pedagio = fracao_100 * 5.39
        despacho = 2.00
        gris = max(vnf * 0.0020, 2.50)
        adv = vnf * 0.0020
        total = round(frete_peso + pedagio + despacho + gris + adv, 2)
        return {
            "Transportadora": nome, "Valor Frete (R$)": total, "Prazo (Dias Úteis)": prazo,
            "Base Tarifária": base_tarifaria, "Status": "Tarifa contratual estrita (Expressa)",
            "Atendida": True, "Motivo": "Atendida", "Tags": tags,
            "Composicao": {"Frete Peso": frete_peso, "Pedágio": pedagio, "Despacho": despacho, "GRIS": gris, "ADV": adv}
        }

    # -------------------------------------------------------------------------
    # CARRION LOGÍSTICA (Exclusivo SP)
    # -------------------------------------------------------------------------
    if transportadora_key == "CARRION":
        # SP Interior próximo (Assis, Marília, Prudente) vs SP Capital / Interior Geral
        eh_oeste_sp = any(p in cid_norm for p in ["assis", "marilia", "presidente prudente", "ourinhos", "tupa"])
        eh_capital_sp = any(p in cid_norm for p in ["sao paulo", "guarulhos", "osasco", "santo andre", "diadema"])
        
        faixas = [(30, 53.68), (50, 59.63), (70, 66.17), (100, 75.75)]
        if eh_oeste_sp:
            exc = 0.58
            pedagio = fracao_100 * 5.19
            despacho = 4.83
            adv = vnf * 0.0028
            prazo = 2
        elif eh_capital_sp:
            exc = 0.74
            pedagio = fracao_100 * 8.60
            despacho = 4.83
            adv = vnf * 0.0042
            prazo = 2
        else:
            exc = 0.98
            pedagio = fracao_100 * 12.97
            despacho = 21.90
            adv = vnf * 0.0042
            prazo = 3

        frete_peso = faixas[-1][1] + max(0.0, peso - 100.0) * exc if peso > 100.0 else next(v for limit, v in faixas if peso <= limit)
        gris = vnf * 0.0010
        total = round(frete_peso + pedagio + despacho + gris + adv, 2)
        return {
            "Transportadora": nome, "Valor Frete (R$)": total, "Prazo (Dias Úteis)": prazo,
            "Base Tarifária": base_tarifaria, "Status": "Tarifa contratual estrita",
            "Atendida": True, "Motivo": "Atendida", "Tags": tags,
            "Composicao": {"Frete Peso": frete_peso, "Pedágio": pedagio, "Despacho": despacho, "GRIS": gris, "ADV": adv}
        }

    # -------------------------------------------------------------------------
    # ALFA TRANSPORTES (Tabela TRF-48)
    # -------------------------------------------------------------------------
    if transportadora_key == "ALFA":
        if uf_u == "PR":
            # Apucarana, Cornélio, Londrina, Maringá
            if any(p in cid_norm for p in ["londrina", "maringa", "apucarana", "cornelio", "cambe", "rolandia"]):
                faixas = [(10, 37.45), (30, 44.28), (50, 51.10), (70, 57.90), (100, 68.16), (150, 85.15)]
                exc = 0.43
                prazo = 1
            elif any(p in cid_norm for p in ["campo mourao", "cianorte", "ibaiti", "paranavai", "telemaco"]):
                faixas = [(10, 41.62), (30, 49.22), (50, 56.79), (70, 64.36), (100, 75.71), (150, 94.58)]
                exc = 0.43
                prazo = 2
            elif any(p in cid_norm for p in ["curitiba", "cascavel", "ponta grossa", "guarapuava", "umuarama"]):
                faixas = [(10, 49.96), (30, 59.06), (50, 68.16), (70, 77.21), (100, 90.85), (150, 113.51)]
                exc = 0.52
                prazo = 2
            else:
                faixas = [(10, 58.68), (30, 70.04), (50, 81.41), (70, 92.72), (100, 109.75), (150, 138.13)]
                exc = 0.60
                prazo = 3
        elif uf_u == "SP":
            if any(p in cid_norm for p in ["adamantina", "assis", "marilia", "ourinhos", "presidente prudente", "tupa"]):
                faixas = [(10, 41.62), (30, 49.22), (50, 56.79), (70, 64.36), (100, 75.71), (150, 94.58)]
                exc = 0.48
                prazo = 2
            else:
                faixas = [(10, 58.68), (30, 70.04), (50, 81.41), (70, 92.72), (100, 109.75), (150, 138.13)]
                exc = 0.65
                prazo = 3
        elif uf_u in ["SC", "RS"]:
            faixas = [(10, 58.68), (30, 70.04), (50, 81.41), (70, 92.72), (100, 109.75), (150, 138.13)]
            exc = 0.73
            prazo = 3
        elif uf_u in ["MS", "MT", "GO", "DF"]:
            faixas = [(10, 65.13), (30, 78.01), (50, 90.85), (70, 103.68), (100, 123.01), (150, 155.15)]
            exc = 0.95
            prazo = 4
        else:  # MG, RJ, ES
            faixas = [(10, 77.66), (30, 93.97), (50, 110.21), (70, 126.52), (100, 150.96), (150, 191.60)]
            exc = 1.15
            prazo = 4

        frete_peso = faixas[-1][1] + max(0.0, peso - 150.0) * exc if peso > 150.0 else next(v for limit, v in faixas if peso <= limit)
        embarque = 6.09
        adv = vnf * 0.0030
        pedagio = fracao_100 * 5.50
        total = round(frete_peso + embarque + adv + pedagio, 2)
        return {
            "Transportadora": nome, "Valor Frete (R$)": total, "Prazo (Dias Úteis)": prazo,
            "Base Tarifária": base_tarifaria, "Status": "Tarifa contratual estrita",
            "Atendida": True, "Motivo": "Atendida", "Tags": tags,
            "Composicao": {"Frete Peso": frete_peso, "Embarque": embarque, "ADV": adv, "Pedágio": pedagio}
        }

    # -------------------------------------------------------------------------
    # TW TRANSPORTES (Tabela 10Fx_Kg 2026.01)
    # -------------------------------------------------------------------------
    if transportadora_key == "TW":
        if uf_u == "PR":
            if any(p in cid_norm for p in ["londrina", "maringa", "apucarana", "cambe", "rolandia"]):
                faixas = [(10, 18.81), (20, 20.54), (30, 22.26), (50, 28.93), (70, 32.81), (100, 38.63)]
                exc = 0.36
                prazo = 1
            elif any(p in cid_norm for p in ["curitiba", "sao jose dos pinhais", "araucaria"]):
                faixas = [(10, 22.81), (20, 26.53), (30, 30.25), (50, 42.41), (70, 50.79), (100, 63.33)]
                exc = 0.77
                prazo = 2
            elif any(p in cid_norm for p in ["ponta grossa", "castro", "telemaco"]):
                faixas = [(10, 23.49), (20, 27.54), (30, 31.59), (50, 44.66), (70, 53.78), (100, 67.46)]
                exc = 0.80
                prazo = 2
            else:
                faixas = [(10, 21.47), (20, 24.54), (30, 27.58), (50, 37.91), (70, 44.78), (100, 55.10)]
                exc = 0.63
                prazo = 3
        elif uf_u == "SC":
            faixas = [(10, 26.89), (20, 31.99), (30, 37.10), (50, 53.24), (70, 64.74), (100, 82.01)]
            exc = 0.98
            prazo = 3
        else:  # RS
            faixas = [(10, 31.29), (20, 37.96), (30, 44.62), (50, 65.21), (70, 80.21), (100, 112.50)]
            exc = 1.10
            prazo = 4

        frete_peso = faixas[-1][1] + max(0.0, peso - 100.0) * exc if peso > 100.0 else next(v for limit, v in faixas if peso <= limit)
        pedagio = fracao_100 * 4.00
        adv = max(vnf * 0.0025, 5.00)
        gris = max(vnf * 0.0020, 5.00)
        total = round(frete_peso + pedagio + adv + gris, 2)
        return {
            "Transportadora": nome, "Valor Frete (R$)": total, "Prazo (Dias Úteis)": prazo,
            "Base Tarifária": base_tarifaria, "Status": "Tarifa contratual estrita",
            "Atendida": True, "Motivo": "Atendida", "Tags": tags,
            "Composicao": {"Frete Peso": frete_peso, "Pedágio": pedagio, "ADV": adv, "GRIS": gris}
        }

    # -------------------------------------------------------------------------
    # ENVIA RÁPIDO (Tabela Combinada)
    # -------------------------------------------------------------------------
    if transportadora_key == "ENVIA_RAPIDO":
        if uf_u == "PR":
            if any(p in cid_norm for p in ["apucarana", "arapongas", "maringa"]):
                faixas = [(20, 30.25), (40, 36.30), (60, 48.40), (80, 54.45), (100, 60.50)]
                exc = 0.45
            else:
                faixas = [(20, 36.30), (40, 42.35), (60, 48.40), (80, 54.45), (100, 60.50)]
                exc = 0.51
            despacho = 9.68
            gris = vnf * 0.00121
            adv = vnf * 0.00242
            prazo = 2
        elif uf_u == "SP":
            faixas = [(20, 42.35), (50, 50.82), (70, 55.66), (100, 60.50)]
            exc = 0.62
            despacho = 6.05
            gris = vnf * 0.00121
            adv = vnf * 0.00242
            prazo = 3
        elif uf_u == "MS":
            faixas = [(20, 66.55), (50, 78.65), (70, 84.70), (100, 102.85)]
            exc = 0.90
            despacho = 10.00
            gris = vnf * 0.00242
            adv = vnf * 0.00242
            prazo = 3
        elif uf_u == "MT":
            faixas = [(20, 90.75), (50, 102.85), (70, 114.95), (100, 121.00)]
            exc = 1.09
            despacho = 15.00
            gris = vnf * 0.00242
            adv = vnf * 0.00242
            prazo = 4
        else:  # GO
            faixas = [(20, 102.85), (50, 121.00), (100, 163.35)]
            exc = 1.16
            despacho = 24.20
            gris = vnf * 0.00242
            adv = vnf * 0.00363
            prazo = 4

        frete_peso = faixas[-1][1] + max(0.0, peso - faixas[-1][0]) * exc if peso > faixas[-1][0] else next(v for limit, v in faixas if peso <= limit)
        pedagio = fracao_100 * 6.33
        total = round(frete_peso + pedagio + despacho + gris + adv, 2)
        return {
            "Transportadora": nome, "Valor Frete (R$)": total, "Prazo (Dias Úteis)": prazo,
            "Base Tarifária": base_tarifaria, "Status": "Tarifa contratual estrita",
            "Atendida": True, "Motivo": "Atendida", "Tags": tags,
            "Composicao": {"Frete Peso": frete_peso, "Pedágio": pedagio, "Despacho": despacho, "GRIS": gris, "ADV": adv}
        }

    # -------------------------------------------------------------------------
    # EXPRESSO SÃO MIGUEL (Contrato 96094/2025)
    # -------------------------------------------------------------------------
    if transportadora_key == "EXPRESSO_SAO_MIGUEL":
        if uf_u == "PR":
            taxa = 35.52
            quilo = 0.584
            pedagio = fracao_100 * 3.53
            gris = max(vnf * 0.0015, 3.53)
            prazo = 2
        elif uf_u == "SP":
            taxa = 31.67
            quilo = 0.500
            pedagio = fracao_100 * 6.59
            gris = max(vnf * 0.0020, 6.59)
            prazo = 3
        elif uf_u == "SC":
            taxa = 36.50
            quilo = 0.580
            pedagio = fracao_100 * 3.53
            gris = max(vnf * 0.0015, 3.53)
            prazo = 3
        else:  # RS
            taxa = 41.00
            quilo = 0.680
            pedagio = fracao_100 * 3.53
            gris = max(vnf * 0.0015, 3.53)
            prazo = 4

        frete_peso = taxa + (peso * quilo)
        adv = vnf * 0.0040
        total = round(frete_peso + pedagio + gris + adv, 2)
        return {
            "Transportadora": nome, "Valor Frete (R$)": total, "Prazo (Dias Úteis)": prazo,
            "Base Tarifária": base_tarifaria, "Status": "Tarifa contratual estrita",
            "Atendida": True, "Motivo": "Atendida", "Tags": tags,
            "Composicao": {"Frete Peso": frete_peso, "Pedágio": pedagio, "GRIS": gris, "ADV": adv}
        }

    # -------------------------------------------------------------------------
    # LOGDI LOGÍSTICA (Especialista Nordeste)
    # -------------------------------------------------------------------------
    if transportadora_key == "LOGDI":
        eh_capital = any(p in cid_norm for p in ["salvador", "recife", "fortaleza", "maceio", "natal", "joao pessoa", "aracaju", "teresina", "sao luis"])
        if eh_capital:
            faixas = [(50, 125.00), (100, 155.00)]
            exc = 1.60
            prazo = 5
        else:
            faixas = [(50, 145.00), (100, 185.00)]
            exc = 1.95
            prazo = 7

        frete_peso = faixas[-1][1] + max(0.0, peso - 100.0) * exc if peso > 100.0 else next(v for limit, v in faixas if peso <= limit)
        adv = vnf * 0.0040
        pedagio = fracao_100 * 6.13
        tas = 5.71
        despacho = 26.34
        gris = max(vnf * 0.0020, 4.97)
        emergencial = (frete_peso + despacho) * 0.1198  # 11,98% Emergencial Combustível
        total = round(frete_peso + adv + pedagio + tas + despacho + gris + emergencial, 2)
        return {
            "Transportadora": nome, "Valor Frete (R$)": total, "Prazo (Dias Úteis)": prazo,
            "Base Tarifária": base_tarifaria, "Status": "Tarifa contratual estrita (Nordeste)",
            "Atendida": True, "Motivo": "Atendida", "Tags": tags,
            "Composicao": {"Frete Peso": frete_peso, "ADV": adv, "Pedágio": pedagio, "Despacho": despacho, "GRIS": gris, "Emergencial": emergencial}
        }

    # -------------------------------------------------------------------------
    # OURO NEGRO (Proposta Comercial 2026)
    # -------------------------------------------------------------------------
    if transportadora_key == "OURO_NEGRO":
        if uf_u == "PR":
            faixas = [(10, 41.23), (20, 44.58), (30, 46.89), (50, 49.56), (70, 53.69), (100, 59.59)]
            exc = 0.67
            prazo = 2
        elif uf_u == "SP":
            faixas = [(10, 45.20), (20, 49.31), (30, 53.41), (50, 61.63), (70, 65.73), (100, 82.18)]
            exc = 0.82
            prazo = 3
        elif uf_u == "SC":
            faixas = [(10, 42.58), (20, 49.38), (30, 51.07), (50, 59.58), (70, 61.23), (100, 67.79)]
            exc = 0.67
            prazo = 3
        else:  # RS
            faixas = [(10, 54.89), (20, 61.01), (30, 73.21), (50, 85.42), (70, 97.62), (100, 122.02)]
            exc = 1.23
            prazo = 4

        frete_peso = faixas[-1][1] + max(0.0, peso - 100.0) * exc if peso > 100.0 else next(v for limit, v in faixas if peso <= limit)
        gris = vnf * 0.0015
        adv = vnf * 0.0015
        pedagio = fracao_100 * 5.96
        tas = 4.89
        total = round(frete_peso + gris + adv + pedagio + tas, 2)
        return {
            "Transportadora": nome, "Valor Frete (R$)": total, "Prazo (Dias Úteis)": prazo,
            "Base Tarifária": base_tarifaria, "Status": "Tarifa contratual estrita",
            "Atendida": True, "Motivo": "Atendida", "Tags": tags,
            "Composicao": {"Frete Peso": frete_peso, "GRIS": gris, "ADV": adv, "Pedágio": pedagio, "TAS": tas}
        }

    # -------------------------------------------------------------------------
    # RODONAVES (Tabela 3209556 por Faixa de KM)
    # -------------------------------------------------------------------------
    if transportadora_key == "RODONAVES":
        km = _estimar_km_rodonaves(uf_u, cidade)
        if km <= 100:
            faixas = [(5, 15.40), (10, 19.24), (20, 24.39), (40, 30.19), (60, 37.17), (100, 44.57)]
            exc = 0.55
            prazo = 1
        elif km <= 200:
            faixas = [(5, 16.98), (10, 21.23), (20, 26.36), (40, 32.84), (60, 41.05), (100, 48.54)]
            exc = 0.61
            prazo = 2
        elif km <= 400:
            faixas = [(5, 20.62), (10, 25.77), (20, 32.84), (40, 39.30), (60, 47.51), (100, 56.76)]
            exc = 0.71
            prazo = 2
        elif km <= 600:
            faixas = [(5, 25.27), (10, 31.57), (20, 40.54), (40, 49.58), (60, 59.05), (100, 70.06)]
            exc = 0.87
            prazo = 3
        elif km <= 800:
            faixas = [(5, 30.91), (10, 38.62), (20, 47.45), (40, 57.75), (60, 68.20), (100, 80.66)]
            exc = 1.00
            prazo = 3
        elif km <= 1000:
            faixas = [(5, 35.20), (10, 44.00), (20, 55.11), (40, 64.81), (60, 77.10), (100, 90.45)]
            exc = 1.13
            prazo = 4
        else:
            faixas = [(5, 45.65), (10, 57.07), (20, 64.14), (40, 94.46), (60, 112.18), (100, 129.16)]
            exc = 1.29
            prazo = 5

        frete_peso = faixas[-1][1] + max(0.0, peso - 100.0) * exc if peso > 100.0 else next(v for limit, v in faixas if peso <= limit)
        frete_valor = max(vnf * 0.0050, 11.51)
        despacho = 27.16
        pedagio = fracao_100 * 12.74
        tas = 11.62 if uf_u in ["AC", "MG", "MS", "MT", "RO", "GO", "DF"] else 0.0
        total = round(frete_peso + frete_valor + despacho + pedagio + tas, 2)
        return {
            "Transportadora": nome, "Valor Frete (R$)": total, "Prazo (Dias Úteis)": prazo,
            "Base Tarifária": f"{base_tarifaria} (Faixa {km}km)", "Status": "Tarifa contratual estrita",
            "Atendida": True, "Motivo": "Atendida", "Tags": tags,
            "Composicao": {"Frete Peso": frete_peso, "Frete Valor": frete_valor, "Despacho": despacho, "Pedágio": pedagio, "TAS": tas}
        }

    # -------------------------------------------------------------------------
    # TECMAR TRANSPORTES (Especialista Norte / Fluvial)
    # -------------------------------------------------------------------------
    if transportadora_key == "TECMAR":
        # R$ por tonelada conforme localidade
        if uf_u == "RO":
            tarifa_ton = 2032.27
            prazo = 11
        elif uf_u == "RR":
            tarifa_ton = 3097.46
            prazo = 17
        elif uf_u == "TO":
            tarifa_ton = 2419.78
            prazo = 6
        elif uf_u == "PA":
            tarifa_ton = 2350.00
            prazo = 10
        elif uf_u == "AM":
            tarifa_ton = 3200.00
            prazo = 15
        else:  # AC, AP
            tarifa_ton = 3400.00
            prazo = 16

        frete_peso = max(50.0, (tarifa_ton / 1000.0) * peso)
        adv = vnf * 0.0042
        tso = vnf * 0.0030
        pedagio = fracao_100 * 10.21
        total = round(frete_peso + adv + tso + pedagio, 2)
        return {
            "Transportadora": nome, "Valor Frete (R$)": total, "Prazo (Dias Úteis)": prazo,
            "Base Tarifária": base_tarifaria, "Status": "Tarifa contratual estrita (Norte Fluvial)",
            "Atendida": True, "Motivo": "Atendida", "Tags": tags,
            "Composicao": {"Frete Peso": frete_peso, "ADV": adv, "TSO": tso, "Pedágio": pedagio}
        }

    # -------------------------------------------------------------------------
    # AGEX TRANSPORTES (Tabela AGE-010326)
    # -------------------------------------------------------------------------
    if transportadora_key == "AGEX":
        if uf_u == "PR":
            faixas = [(10, 41.91), (20, 46.09), (30, 50.71), (40, 55.77), (50, 61.36)]
            exc = 0.486
            ped_val = 6.38
            prazo = 2
        elif uf_u == "SC":
            faixas = [(10, 48.18), (20, 53.00), (30, 58.30), (40, 64.88), (50, 70.53)]
            exc = 0.528
            ped_val = 6.52
            prazo = 3
        elif uf_u == "RS":
            faixas = [(10, 76.40), (20, 84.02), (30, 92.43), (40, 101.68), (50, 111.84)]
            exc = 0.972
            ped_val = 7.23
            prazo = 4
        elif uf_u == "SP":
            faixas = [(10, 54.64), (20, 60.12), (30, 66.11), (40, 72.73), (50, 80.01)]
            exc = 0.833
            ped_val = 6.52
            prazo = 3
        else:  # MS
            faixas = [(10, 58.12), (20, 63.93), (30, 70.33), (40, 77.35), (50, 85.10)]
            exc = 1.250
            ped_val = 12.13
            prazo = 3

        frete_peso = faixas[-1][1] + max(0.0, peso - 50.0) * exc if peso > 50.0 else next(v for limit, v in faixas if peso <= limit)
        adv = vnf * 0.0030
        gris = vnf * 0.0020
        pedagio = fracao_100 * ped_val
        tas = 7.84 if uf_u in ["RS", "MS"] else 0.0
        total = round(frete_peso + adv + gris + pedagio + tas, 2)
        return {
            "Transportadora": nome, "Valor Frete (R$)": total, "Prazo (Dias Úteis)": prazo,
            "Base Tarifária": base_tarifaria, "Status": "Tarifa contratual estrita",
            "Atendida": True, "Motivo": "Atendida", "Tags": tags,
            "Composicao": {"Frete Peso": frete_peso, "ADV": adv, "GRIS": gris, "Pedágio": pedagio, "TAS": tas}
        }

    # -------------------------------------------------------------------------
    # ATENDIMENTO VIP (Norte / Noroeste do Paraná)
    # -------------------------------------------------------------------------
    if transportadora_key == "VIP":
        faixas = [(10, 22.50), (20, 26.80), (30, 31.20), (50, 38.50), (70, 44.00), (100, 52.00)]
        exc = 0.45
        prazo = 1

        frete_peso = faixas[-1][1] + max(0.0, peso - 100.0) * exc if peso > 100.0 else next(v for limit, v in faixas if peso <= limit)
        pedagio = fracao_100 * 3.50
        gris = vnf * 0.0015
        adv = vnf * 0.0020
        total = round(frete_peso + pedagio + gris + adv, 2)
        return {
            "Transportadora": nome, "Valor Frete (R$)": total, "Prazo (Dias Úteis)": prazo,
            "Base Tarifária": base_tarifaria, "Status": "Tarifa contratual regional estrita",
            "Atendida": True, "Motivo": "Atendida", "Tags": tags,
            "Composicao": {"Frete Peso": frete_peso, "Pedágio": pedagio, "GRIS": gris, "ADV": adv}
        }

    # -------------------------------------------------------------------------
    # ARAGAO (Proposta Comercial Combinada)
    # -------------------------------------------------------------------------
    if transportadora_key == "ARAGAO":
        prazo = None
        if cid_norm in CIDADES_ARAGAO_TB1:
            faixas = [(10, 80.00), (20, 85.00), (30, 88.00), (40, 90.00), (60, 95.00), (70, 100.00), (80, 110.00), (100, 125.00)]
            exc = 2.20
        elif cid_norm in CIDADES_ARAGAO_TB2:
            faixas = [(10, 50.00), (20, 55.00), (30, 60.00), (40, 65.00), (60, 70.00), (70, 75.00), (80, 82.00), (100, 105.00)]
            exc = 1.23
        else: # CIDADES_ARAGAO_TB3
            faixas = [(10, 100.00), (20, 105.00), (30, 110.00), (40, 115.00), (60, 120.00), (70, 130.00), (80, 145.00), (100, 165.00)]
            exc = 2.85

        frete_peso = faixas[-1][1] + max(0.0, peso - 100.0) * exc if peso > 100.0 else next(v for limit, v in faixas if peso <= limit)
        pedagio = fracao_100 * 10.80
        despacho = 12.90
        tas = 5.50
        gris = vnf * 0.0007
        adv = vnf * 0.0100
        coleta = 5.00
        total = round(frete_peso + pedagio + despacho + tas + gris + adv + coleta, 2)
        return {
            "Transportadora": nome, "Valor Frete (R$)": total, "Prazo (Dias Úteis)": prazo,
            "Base Tarifária": base_tarifaria, "Status": "Tarifa contratual estrita",
            "Atendida": True, "Motivo": "Atendida", "Tags": tags,
            "Composicao": {"Frete Peso": frete_peso, "Pedágio": pedagio, "Despacho": despacho, "TAS": tas, "GRIS": gris, "ADV": adv, "Coleta": coleta}
        }

    # Fallback de segurança se chave desconhecida
    return {
        "Transportadora": nome, "Valor Frete (R$)": None, "Prazo (Dias Úteis)": None,
        "Base Tarifária": base_tarifaria, "Status": "Não atende esta região",
        "Atendida": False, "Motivo": "Tabela não mapeada", "Tags": tags, "Composicao": {}
    }
