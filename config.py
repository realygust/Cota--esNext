"""
Configuração centralizada do sistema.
Constantes, origens, contatos e versão.
Credenciais são acessadas SOMENTE via st.secrets em runtime.
"""

APP_VERSION = "1.0.0"
APP_TITLE = "Sistema de Cotações & Logística"
APP_COMPANY = "NEXT CABLE"
HISTORICO_FILE = "historico_cotacoes.json"
BROWSER_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
ENTREGAS_FILE = "entregas.xlsx"
CNPJ_EMPRESA = "26434839000121"

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

ORIGENS = {
    "NEXT Matriz (Londrina/PR)": {"cnpj": CNPJ_EMPRESA, "cep": "86071000"},
    "R NET Telecom (Londrina/PR)": {"cnpj": "11275512000187", "cep": "86010070"},
    "GB Souza (Londrina/PR)": {"cnpj": "11572216000148", "cep": "86026090"},
    "NEXT Filial MG (Belo Horizonte/MG)": {"cnpj": "26434839000474", "cep": "30810600"},
    "NEXT Filial GO (Anápolis/GO)": {"cnpj": "26434839000202", "cep": "75114300"},
    "Outra Origem (Digitar Manualmente)": {"cnpj": "", "cep": ""},
}

CONTATOS_TRANSPORTADORAS = {
    "braspress": "551122233500",
    "brasul": "554399652615",
    "sudoeste": "554398660050",
    "coopex": "554388705800",
    "rico": "554388705800",
    "aragão": "554388705800",
    "aragao": "554388705800",
    "alfa": "554230354979",
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
}


def obter_numero_wa(nome_transportadora: str) -> str:
    nome_limpo = str(nome_transportadora).lower().strip()
    for chave, numero in CONTATOS_TRANSPORTADORAS.items():
        if chave in nome_limpo:
            return numero
    return ""

TABELAS = {
    "AGEX": {
        "cubagem": 300,
        "faixas_peso": [10, 30, 50, 70, 100],
        "rotas": {
            ("PR", "CAPITAL"): {"vals": [36.44, 39.88, 44.10, 48.50, 53.34], "exc": 0.292, "adv": 0.0030, "gris": 0.0020},
            ("PR", "INT1"):    {"vals": [41.91, 46.09, 50.71, 55.77, 61.36], "exc": 0.486, "adv": 0.0030, "gris": 0.0020},
            ("PR", "INT2"):    {"vals": [48.18, 53.00, 58.30, 64.88, 70.53], "exc": 0.528, "adv": 0.0030, "gris": 0.0020},
            ("SC", "CAPITAL"): {"vals": [48.18, 53.00, 58.30, 64.88, 70.53], "exc": 0.528, "adv": 0.0030, "gris": 0.0020},
            ("SC", "INT1"):    {"vals": [48.18, 53.00, 58.30, 64.88, 70.53], "exc": 0.528, "adv": 0.0030, "gris": 0.0020},
            ("SC", "INT2"):    {"vals": [55.66, 61.23, 67.34, 74.09, 81.49], "exc": 0.694, "adv": 0.0030, "gris": 0.0020},
            ("RS", "CAPITAL"): {"vals": [63.67, 70.03, 77.02, 84.74, 93.21], "exc": 0.694, "adv": 0.0030, "gris": 0.0020},
            ("RS", "INT1"):    {"vals": [76.40, 84.02, 92.43, 101.68, 111.84], "exc": 0.972, "adv": 0.0030, "gris": 0.0020},
            ("RS", "INT2"):    {"vals": [89.11, 98.04, 107.83, 117.23, 129.95], "exc": 1.111, "adv": 0.0030, "gris": 0.0020},
            ("SP", "CAPITAL"): {"vals": [60.72, 69.53, 76.49, 84.14, 92.55], "exc": 0.972, "adv": 0.0030, "gris": 0.0020},
            ("SP", "INT1"):    {"vals": [54.64, 60.12, 66.11, 72.73, 80.01], "exc": 0.833, "adv": 0.0030, "gris": 0.0020},
            ("SP", "INT2"):    {"vals": [54.64, 60.12, 66.11, 72.73, 80.01], "exc": 0.833, "adv": 0.0030, "gris": 0.0020},
            ("MS", "CAPITAL"): {"vals": [58.12, 63.93, 70.33, 77.35, 85.10], "exc": 1.250, "adv": 0.0030, "gris": 0.0020},
            ("MS", "INT1"):    {"vals": [63.31, 69.62, 76.60, 84.25, 92.68], "exc": 1.319, "adv": 0.0035, "gris": 0.0020},
            ("MS", "INT2"):    {"vals": [76.40, 84.02, 92.43, 101.68, 111.84], "exc": 1.389, "adv": 0.0040, "gris": 0.0020},
        },
        "pedagio": {"PR": 6.38, "SC": 6.52, "SP": 6.52, "RS": 7.23, "MS": 12.13},
        "gris_min": 4.70, "adv_min": 0.0, "tas": 0.0, "despacho": 0.0, "default_regiao": "INT1",
    },
    "COOPEX": {
        "cubagem": 300,
        "faixas_peso": [10, 20, 40, 60, 100],
        "rotas": {
            ("PR", "EXPRESS"): {"vals": [17.36, 21.49, 25.76, 29.61, 46.48], "exc": 0.381, "adv": 0.0036, "gris": 0.0018},
            ("PR", "INT1"):    {"vals": [22.02, 26.45, 29.22, 33.53, 50.91], "exc": 0.423, "adv": 0.0036, "gris": 0.0018},
            ("PR", "INT2"):    {"vals": [34.07, 37.92, 44.27, 49.15, 64.44], "exc": 0.510, "adv": 0.0036, "gris": 0.0018},
            ("SC", "LITORAL_N"): {"vals": [26.98, 33.00, 38.65, 44.16, 59.09], "exc": 0.554, "adv": 0.0036, "gris": 0.0018},
            ("SC", "LITORAL_S"): {"vals": [31.56, 35.72, 42.39, 49.96, 64.96], "exc": 0.576, "adv": 0.0036, "gris": 0.0018},
            ("SC", "OESTE"):     {"vals": [36.22, 44.29, 51.98, 60.13, 72.73], "exc": 0.614, "adv": 0.0036, "gris": 0.0018},
            ("RS", "CAPITAL"): {"vals": [37.70, 45.02, 54.22, 61.39, 73.15], "exc": 0.633, "adv": 0.0036, "gris": 0.0018},
            ("RS", "INT1"):    {"vals": [39.40, 47.40, 56.49, 65.35, 77.60], "exc": 0.649, "adv": 0.0036, "gris": 0.0018},
            ("RS", "FRONTEIRA"): {"vals": [57.79, 62.97, 74.40, 86.42, 102.25], "exc": 0.826, "adv": 0.0036, "gris": 0.0018},
            ("SP", "INT1"):    {"vals": [32.64, 36.96, 43.85, 51.68, 67.20], "exc": 0.599, "adv": 0.0036, "gris": 0.0018},
            ("SP", "INT2"):    {"vals": [35.91, 40.65, 48.24, 56.85, 73.92], "exc": 0.628, "adv": 0.0036, "gris": 0.0018},
        },
        "pedagio": {"PR": 4.5, "SC": 4.5, "RS": 4.5, "SP": 4.5},
        "gris_min": 3.15, "adv_min": 4.9, "tas": 3.15, "despacho": 0.0, "default_regiao": "INT1",
    },
    "PRINCESA": {
        "cubagem": 300,
        "faixas_peso": [10, 20, 30, 50, 70, 100],
        "rotas": {
            ("SP", "CAPITAL"): {"vals": [42.15, 45.96, 49.80, 57.47, 61.31, 76.63], "exc": 0.77, "adv": 0.0033, "gris": 0.0011, "ped": 5.9},
            ("PR", "CAPITAL"): {"vals": [29.65, 32.35, 35.05, 40.44, 43.16, 53.91], "exc": 0.55, "adv": 0.0033, "gris": 0.0011, "ped": 4.97},
            ("SC", "CAPITAL"): {"vals": [42.58, 49.38, 51.07, 59.58, 68.11, 85.11], "exc": 0.87, "adv": 0.0033, "gris": 0.0011, "ped": 5.9},
            ("RS", "CAPITAL"): {"vals": [54.89, 61.01, 73.21, 85.42, 97.62, 122.02], "exc": 1.23, "adv": 0.0033, "gris": 0.0011, "ped": 5.9},
            ("RS", "INT1"):    {"vals": [72.37, 80.39, 96.50, 112.57, 128.65, 160.79], "exc": 1.62, "adv": 0.0033, "gris": 0.0011, "ped": 5.9},
            ("SC", "INT1"):    {"vals": [57.24, 66.40, 68.68, 80.13, 91.56, 114.46], "exc": 1.15, "adv": 0.0033, "gris": 0.0011, "ped": 5.9},
            ("SP", "INT1"):    {"vals": [45.20, 49.31, 53.41, 61.63, 65.73, 82.18], "exc": 0.80, "adv": 0.0033, "gris": 0.0011, "ped": 5.9},
        },
        "pedagio": {}, "gris_min": 0.0, "adv_min": 0.0, "tas": 0.0, "despacho": 0.0, "default_regiao": "INT1",
    },
    "TW": {
        "cubagem": 300,
        "faixas_peso": [10, 20, 30, 50, 70, 100],
        "rotas": {
            ("RS", "CAPITAL"): {"vals": [31.29, 37.86, 44.62, 61.23, 76.12, 112.50], "exc": 1.351, "adv": 0.0040, "gris": 0.0020, "ped": 4.00},
            ("RS", "INT1"):    {"vals": [32.26, 39.12, 46.18, 63.71, 85.71, 107.53], "exc": 1.250, "adv": 0.0035, "gris": 0.0020, "ped": 4.00},
            ("SC", "CAPITAL"): {"vals": [26.80, 31.99, 37.17, 51.24, 64.74, 80.41], "exc": 0.980, "adv": 0.0025, "gris": 0.0020, "ped": 4.00},
            ("SC", "INT1"):    {"vals": [28.25, 35.25, 41.44, 60.56, 74.40, 95.38], "exc": 1.105, "adv": 0.0030, "gris": 0.0020, "ped": 4.00},
            ("PR", "CAPITAL"): {"vals": [22.81, 28.05, 32.52, 45.41, 55.79, 69.53], "exc": 0.770, "adv": 0.0025, "gris": 0.0020, "ped": 4.00},
            ("PR", "INT1"):    {"vals": [23.49, 27.54, 31.59, 44.06, 53.78, 67.40], "exc": 0.804, "adv": 0.0025, "gris": 0.0020, "ped": 4.00},
            ("PR", "INT2"):    {"vals": [16.81, 20.54, 23.26, 29.53, 32.81, 38.63], "exc": 0.355, "adv": 0.0020, "gris": 0.0020, "ped": 4.00},
            ("SP", "CAPITAL"): {"vals": [36.24, 42.56, 48.82, 66.92, 76.63, 98.29], "exc": 0.705, "adv": 0.0025, "gris": 0.0020, "ped": 4.00},
            ("SP", "INT1"):    {"vals": [39.14, 45.89, 52.66, 74.43, 89.62, 112.44], "exc": 0.844, "adv": 0.0025, "gris": 0.0020, "ped": 4.00},
            ("SP", "INT2"):    {"vals": [40.91, 47.75, 54.87, 78.17, 94.62, 118.75], "exc": 0.913, "adv": 0.0025, "gris": 0.0020, "ped": 4.00},
        },
        "pedagio": {}, "gris_min": 5.00, "adv_min": 0.0, "tas": 4.00, "despacho": 0.0, "default_regiao": "INT1",
    },
    "ENVIA_RAPIDO": {
        "cubagem": 300,
        "faixas_peso": [20, 35, 50, 70, 100],
        "rotas": {
            ("RJ", "GERAL"): {"vals": [220, 230, 235, 255, 285], "exc_ton": 2400, "adv": 0.0030, "gris": 0.0020, "ped": 10, "desp": 10},
            ("SP", "GERAL"): {"vals": [85, 90, 95, 105, 115], "exc_ton": 950, "adv": 0.0030, "gris": 0.0020, "ped": 10, "desp": 10},
            ("SP", "CAPITAL"): {"vals": [105, 115, 125, 135, 145], "exc_ton": 1000, "adv": 0.0030, "gris": 0.0020, "ped": 10, "desp": 10},
            ("MG", "GERAL"): {"vals": [220, 235, 245, 260, 290], "exc_ton": 2400, "adv": 0.0030, "gris": 0.0020, "ped": 10, "desp": 20},
            ("BA", "GERAL"): {"vals": [255, 265, 275, 285, 320], "exc_ton": 2500, "adv": 0.0050, "gris": 0.0030, "ped": 10, "desp": 10},
            ("ES", "GERAL"): {"vals": [255, 265, 275, 285, 320], "exc_ton": 2500, "adv": 0.0050, "gris": 0.0020, "ped": 10, "desp": 10},
            ("PR", "GERAL"): {"vals": [40, 45, 50, 55, 60], "exc_ton": 430, "adv": 0.0020, "gris": 0.0010, "ped": 5, "desp": 5},
            ("PR", "CAPITAL"): {"vals": [40, 45, 50, 55, 60], "exc_ton": 430, "adv": 0.0020, "gris": 0.0010, "ped": 0, "desp": 5},
            ("GO", "GERAL"): {"vals": [140, 155, 165, 175, 190], "exc_ton": 1150, "adv": 0.0030, "gris": 0.0020, "ped": 10, "desp": 10},
            ("MT", "GERAL"): {"vals": [190, 215, 235, 258, 270], "exc_ton": 2400, "adv": 0.0050, "gris": 0.0030, "ped": 12, "desp": 20, "tas": 15},
            ("MS", "GERAL"): {"vals": [85, 90, 100, 115, 120], "exc_ton": 850, "adv": 0.0030, "gris": 0.0020, "ped": 5, "desp": 5, "tas": 5},
            ("DF", "GERAL"): {"vals": [110, 125, 145, 165, 180], "exc_ton": 1150, "adv": 0.0030, "gris": 0.0020, "ped": 12, "desp": 10, "tas": 10},
            ("RO", "GERAL"): {"vals": [110, 125, 135, 150, 180], "exc_ton": 1150, "adv": 0.0030, "gris": 0.0020, "ped": 10, "desp": 10, "tas": 10},
            ("PB", "GERAL"): {"vals": [255, 265, 275, 285, 320], "exc_ton": 2500, "adv": 0.0030, "gris": 0.0020, "ped": 12, "desp": 20},
            ("PE", "GERAL"): {"vals": [255, 265, 275, 285, 320], "exc_ton": 2500, "adv": 0.0030, "gris": 0.0020, "ped": 12, "desp": 20},
            ("CE", "GERAL"): {"vals": [255, 265, 275, 285, 320], "exc_ton": 2500, "adv": 0.0030, "gris": 0.0020, "ped": 12, "desp": 20},
            ("RN", "GERAL"): {"vals": [255, 265, 275, 285, 320], "exc_ton": 2500, "adv": 0.0030, "gris": 0.0020, "ped": 12, "desp": 20},
            ("SE", "GERAL"): {"vals": [255, 265, 275, 285, 320], "exc_ton": 2500, "adv": 0.0030, "gris": 0.0020, "ped": 12, "desp": 20},
            ("AL", "GERAL"): {"vals": [255, 265, 275, 285, 320], "exc_ton": 2500, "adv": 0.0030, "gris": 0.0020, "ped": 12, "desp": 20},
            ("MA", "GERAL"): {"vals": [255, 265, 275, 285, 320], "exc_ton": 2500, "adv": 0.0030, "gris": 0.0020, "ped": 12, "desp": 20},
            ("PA", "GERAL"): {"vals": [255, 265, 275, 285, 320], "exc_ton": 2500, "adv": 0.0030, "gris": 0.0002, "ped": 12, "desp": 20},
            ("TO", "GERAL"): {"vals": [85, 90, 95, 100, 110], "exc_ton": 950, "adv": 0.0030, "gris": 0.0020, "ped": 10, "desp": 10},
        },
        "pedagio": {}, "gris_min": 0.0, "adv_min": 0.0, "tas": 0.0, "despacho": 0.0, "default_regiao": "GERAL",
    },
}

CAPITAIS = {
    "curitiba": ("PR", "CAPITAL"), "londrina": ("PR", "CAPITAL"), "maringa": ("PR", "CAPITAL"),
    "maringá": ("PR", "CAPITAL"), "florianopolis": ("SC", "CAPITAL"), "florianópolis": ("SC", "CAPITAL"),
    "joinville": ("SC", "CAPITAL"), "porto alegre": ("RS", "CAPITAL"),
    "sao paulo": ("SP", "CAPITAL"), "são paulo": ("SP", "CAPITAL"),
    "rio de janeiro": ("RJ", "GERAL"), "campinas": ("SP", "INT1"),
    "campo grande": ("MS", "CAPITAL"), "brasilia": ("DF", "GERAL"), "brasília": ("DF", "GERAL"),
}
