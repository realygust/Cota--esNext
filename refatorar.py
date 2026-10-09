import ast
import os

with open('main.py', 'r', encoding='utf-8') as f:
    code = f.read()

tree = ast.parse(code)
functions = {}
for node in tree.body:
    if isinstance(node, ast.FunctionDef):
        functions[node.name] = ast.get_source_segment(code, node)

def write_module(filename, imports, func_names):
    content = imports + "\n\n"
    for name in func_names:
        if name in functions:
            content += functions[name] + "\n\n"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

# 1. utils.py
utils_imports = """import json
import os
from datetime import datetime
import re
import streamlit as st
from config import HISTORICO_FILE"""

utils_funcs = [
    '_secret',
    'carregar_historico',
    'salvar_historico_item',
    'limpar_historico_arquivo',
    'formatar_moeda',
    'limpar_mensagem_ssw',
    'limpar_documento',
    'limpar_cep',
    'xml_escape',
    'buscar_endereco_cep',
    'buscar_empresa_cnpj',
    'mapear_regiao'
]
write_module('utils.py', utils_imports, utils_funcs)

# 2. api_services.py
api_imports = """import requests
import json
import urllib3
import urllib.parse
from xml.etree import ElementTree as ET
import streamlit as st
import tabelas_engine as te
from utils import _secret, limpar_mensagem_ssw, limpar_documento, xml_escape
from config import (
    USUARIO_BRASPRESS, SENHA_BRASPRESS,
    DOMINIO_AGEX, USUARIO_AGEX, SENHA_AGEX,
    DOMINIO_COPEX, USUARIO_COPEX, SENHA_COPEX,
    DOMINIO_LOGBG, USUARIO_LOGBG, SENHA_LOGBG, MERCADORIA_LOGBG
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
"""
api_funcs = [
    'calcular_frete_tabela',
    'cotar_braspress',
    'rastrear_braspress',
    'cotar_ssw_wsdl'
]
write_module('api_services.py', api_imports, api_funcs)

# 3. excel_generator.py
excel_imports = """import base64
import io
import pandas as pd
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from datetime import datetime
from utils import formatar_moeda
"""
excel_funcs = [
    'gerar_excel_cotacao',
    'gerar_excel_entregas'
]
write_module('excel_generator.py', excel_imports, excel_funcs)

# 4. whatsapp_generator.py
wa_imports = """import urllib.parse
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
    "plav": "55438416965"
}
"""
wa_funcs = [
    'obter_numero_wa',
    'gerar_badge_logo_html'
]
write_module('whatsapp_generator.py', wa_imports, wa_funcs)

print("Modulos extraidos com sucesso!")
