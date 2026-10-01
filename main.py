
# ================= IMPORTAÇÕES REFATORADAS =================
import utils
import api_services
import excel_generator
import whatsapp_generator
from config import *
import html
# ============================================================

_secret = utils._secret
carregar_historico = utils.carregar_historico
salvar_historico_item = utils.salvar_historico_item
limpar_historico_arquivo = utils.limpar_historico_arquivo
formatar_moeda = utils.formatar_moeda
limpar_mensagem_ssw = utils.limpar_mensagem_ssw
limpar_documento = utils.limpar_documento
limpar_cep = utils.limpar_cep
xml_escape = utils.xml_escape
buscar_cep = utils.buscar_cep
buscar_empresa_cnpj = utils.buscar_empresa_cnpj
mapear_regiao = utils.mapear_regiao

calcular_frete_tabela = api_services.calcular_frete_tabela
cotar_braspress = api_services.cotar_braspress
rastrear_braspress = api_services.rastrear_braspress
cotar_ssw_wsdl = api_services.cotar_ssw_wsdl

gerar_excel_cotacao = excel_generator.gerar_excel_cotacao
gerar_excel_entregas = excel_generator.gerar_excel_entregas

obter_numero_wa = whatsapp_generator.obter_numero_wa
gerar_badge_logo_html = whatsapp_generator.gerar_badge_logo_html

# Alias the dictionary constants in case they are used in main
CONTATOS_TRANSPORTADORAS = whatsapp_generator.CONTATOS_TRANSPORTADORAS
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import html
import io
import json
import math
import os
import re
import urllib.parse
import urllib3
from xml.etree import ElementTree as ET

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
import pandas as pd
import requests
import streamlit as st
import tabelas_engine as te
import importlib
try:
    importlib.reload(te)
except Exception as e:
    import logging
    logging.warning(f"Failed to reload te: {e}")

import importlib
try:
    import db_historico
    importlib.reload(db_historico)
except Exception as e:
    import logging
    logging.warning(f"Failed to reload db_historico: {e}")

import db_historico
db_historico.init_db()





urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuração da página
st.set_page_config(
    page_title="Cotação de Frete - Next Cable",
    layout="wide",
    initial_sidebar_state="expanded",
)

import importlib
try:
    from streamlit_cookies_controller import CookieController
except ImportError:
    CookieController = None

def check_auth():
    if "user" not in st.session_state:
        st.session_state.user = None

    if "cookie_init_done" not in st.session_state:
        st.session_state.cookie_init_done = False

    cookie_controller = CookieController() if CookieController else None
    
    # Tentativa de login automático via cookie
    if cookie_controller and st.session_state.user is None:
        saved_token = cookie_controller.get('nextcable_session_token')
        if saved_token:
            user_db = db_historico.authenticate_session_token(saved_token)
            if user_db and user_db.get("status") == "ATIVO":
                st.session_state.user = user_db
            else:
                cookie_controller.remove('nextcable_session_token')
        else:
            if not st.session_state.cookie_init_done:
                st.session_state.cookie_init_done = True
                # Pausa a execução no primeiro render para evitar o flash da tela de login.
                # O componente CookieController enviará os cookies do cliente e acionará um rerun automático.
                st.stop()

    has_oidc = "auth" in st.secrets

    if has_oidc:
        if not st.experimental_user.is_logged_in:
            st.login()
            st.stop()
        else:
            email = st.experimental_user.email
            nome = st.experimental_user.name or email
            user_db = db_historico.get_user_by_email(email)
            if not user_db:
                users_count = db_historico.execute_query("SELECT COUNT(*) as c FROM usuarios", fetchone=True)["c"]
                role = "ADMIN" if users_count == 0 else "VENDEDOR"
                pwd = os.urandom(8).hex()
                user_id = db_historico.create_user(email, nome, pwd, role)
                user_db = db_historico.get_user_by_id(user_id)
            if user_db["status"] == "ATIVO":
                st.session_state.user = user_db
            else:
                st.error("Usuário bloqueado.")
                st.stop()
    else:
        if not st.session_state.user:
            login_placeholder = st.empty()
            with login_placeholder.container():
                st.markdown("""
                <style>
                [data-testid="stSidebar"] { display: none !important; }
                [data-testid="stHeader"] { display: none !important; }
                
                .block-container {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    min-height: 90vh;
                    padding-top: 2rem !important;
                }
                
                div[data-testid="stForm"] {
                    border: none !important;
                    padding: 0 !important;
                }
                
                .logo-text {
                    font-size: 1.4rem;
                    font-weight: 800;
                    color: #0f172a;
                    text-align: center;
                    margin-top: 15px;
                    margin-bottom: 2px;
                    letter-spacing: -0.02em;
                }
                .sub-text {
                    font-size: 0.85rem;
                    color: #64748b;
                    text-align: center;
                    margin-bottom: 25px;
                    font-weight: 600;
                }
                
                div[data-testid="stFormSubmitButton"] > button {
                    background: #000033 !important;
                    color: #ffffff !important;
                    border: none !important;
                    border-radius: 8px !important;
                    font-weight: 700 !important;
                    height: 46px !important;
                    margin-top: 10px !important;
                    box-shadow: 0 4px 6px -1px rgba(0, 0, 51, 0.2) !important;
                    transition: all 0.2s ease !important;
                    letter-spacing: 0.03em !important;
                }
                div[data-testid="stFormSubmitButton"] > button:hover {
                    box-shadow: 0 6px 12px -2px rgba(0, 0, 51, 0.3) !important;
                    opacity: 0.95 !important;
                }
                
                .stTextInput label {
                    font-size: 0.8rem !important;
                    color: #334155 !important;
                    font-weight: 600 !important;
                }
                .stTextInput input {
                    border-radius: 8px !important;
                    border: 1px solid #cbd5e1 !important;
                    padding: 10px 14px !important;
                    font-size: 0.95rem !important;
                    color: #0f172a !important;
                }
                .stTextInput input:focus {
                    border-color: #000033 !important;
                    box-shadow: 0 0 0 3px rgba(0, 0, 51, 0.15) !important;
                }
                
                .support-text {
                    font-size: 0.75rem;
                    color: #94a3b8;
                    text-align: center;
                    margin-top: 25px;
                    font-weight: 500;
                }
                </style>
                """, unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([1, 1.5, 1])
                with col2:
                    with st.container(border=True):
                        import base64 as _b64_login
                        _logo_login_b64 = ""
                        if os.path.exists("logo_next.png"):
                            with open("logo_next.png", "rb") as _flg:
                                _logo_login_b64 = _b64_login.b64encode(_flg.read()).decode()
                        if _logo_login_b64:
                            st.markdown(f"""
                            <div style="text-align:center; margin-top: 10px;">
                                <img src="data:image/png;base64,{_logo_login_b64}" style="max-width:180px;height:auto;" />
                            </div>
                            <div class='sub-text' style='margin-top:10px;'>Logística & Cotações</div>
                            """, unsafe_allow_html=True)
                        else:
                            st.markdown("""
                            <div style="text-align:center; margin-top: 10px;">
                                <div style="display:inline-flex; width:56px; height:56px; background:#000033; border-radius:14px; align-items:center; justify-content:center; color:white; font-weight:800; font-size:1.6rem; box-shadow:0 6px 10px -2px rgba(0,0,51,0.25);">NC</div>
                            </div>
                            <div class='logo-text'>Next Cable</div>
                            <div class='sub-text'>Logística & Cotações</div>
                            """, unsafe_allow_html=True)
                        
                        with st.form("login_form", border=False):
                            email = st.text_input("E-mail", placeholder="vendedor@nextcable.com.br")
                            password = st.text_input("Senha", type="password", placeholder="••••••••")
                            manter_conectado = st.checkbox("Manter conectado", value=True)
                            
                            submit = st.form_submit_button("ENTRAR", use_container_width=True)
                            
                            if submit:
                                try:
                                    user_db = db_historico.authenticate_local_user(email, password)
                                    if user_db:
                                        if user_db["status"] != "ATIVO":
                                            st.error("Usuário bloqueado.")
                                        else:
                                            st.session_state.user = user_db
                                            if manter_conectado:
                                                st.session_state.pending_cookie_token = db_historico.create_session_token(user_db['id'])
                                    else:
                                        st.error("E-mail ou senha incorretos.")
                                except Exception:
                                    st.error("E-mail ou senha incorretos.")
                        
                        st.markdown("<div class='support-text'>Problemas para acessar? Procure o administrador.</div>", unsafe_allow_html=True)
            
            if not st.session_state.user:
                st.stop()
            else:
                login_placeholder.empty()
                if "pending_cookie_token" in st.session_state and cookie_controller:
                    cookie_controller.set('nextcable_session_token', st.session_state.pending_cookie_token, max_age=60*60*24*30)
                    del st.session_state.pending_cookie_token

check_auth()

APP_VERSION = "Sistema de Cotações Logísticas"

# Estilo Visual Enterprise / SaaS Moderno (Stripe/Shopify UI vibe)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

#footer {visibility: hidden;}
.stApp {
    background-color: #f8fafc;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

/* Sidebar SaaS */
section[data-testid="stSidebar"] {
    background-color: #000033 !important;
    border-right: none !important;
}
section[data-testid="stSidebar"] .stButton > button {
    border-radius: 6px !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    text-align: left !important;
    justify-content: flex-start !important;
    padding: 10px 14px !important;
    margin-bottom: 2px !important;
    transition: all 0.15s ease !important;
    min-height: 40px !important;
    color: #cbd5e1 !important;
    background-color: transparent !important;
    border: none !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background-color: rgba(255, 255, 255, 0.1) !important;
    color: #ffffff !important;
}
section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background-color: rgba(255, 255, 255, 0.15) !important;
    color: #ffffff !important;
    font-weight: 600 !important;
    border-left: 3px solid #ffffff !important;
    padding-left: 11px !important;
}
section[data-testid="stSidebar"] [data-testid="stExpander"] {
    background-color: #000033 !important;
    border: 1px solid rgba(255, 255, 255, 0.2) !important;
}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary {
    color: #e2e8f0 !important;
}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {
    color: #f1f5f9 !important;
}

/* Inputs */
.stTextInput label, .stNumberInput label, .stSelectbox label, .stTextArea label {
    color: #334155 !important;
    font-weight: 600 !important;
    font-size: 0.8rem !important;
    letter-spacing: 0.01em !important;
}
.stTextInput > div > div > input, .stNumberInput > div > div > input {
    background: #ffffff !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 6px !important;
    font-size: 0.88rem !important;
    color: #0f172a !important;
    padding: 8px 12px !important;
    transition: border-color 0.15s, box-shadow 0.15s;
}
.stTextInput > div > div > input:focus, .stNumberInput > div > div > input:focus {
    border-color: #000033 !important;
    box-shadow: 0 0 0 2px rgba(0,0,51,0.15) !important;
}
.stTextArea textarea {
    border: 1px solid #cbd5e1 !important;
    border-radius: 6px !important;
    font-size: 0.88rem !important;
}
.stTextArea textarea:focus {
    border-color: #000033 !important;
    box-shadow: 0 0 0 2px rgba(0,0,51,0.15) !important;
}

/* CTA Button */
.btn-cta > div > button {
    background-color: #000033 !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    border-radius: 8px !important;
    height: 48px !important;
    border: none !important;
    transition: background-color 0.15s ease !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important;
    letter-spacing: 0.02em !important;
}
.btn-cta > div > button:hover {
    background-color: #00004d !important;
}

/* Containers */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 10px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
}
.block-container { padding-top: 4.5rem !important; padding-bottom: 3rem !important; max-width: 1200px !important; }

/* Section titles */
.section-title {
    font-size: 0.88rem;
    font-weight: 700;
    color: #0f172a;
    letter-spacing: 0.02em;
    border-bottom: 2px solid #e2e8f0;
    padding-bottom: 10px;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.section-title .num {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    background: #0f172a;
    color: #ffffff;
    border-radius: 6px;
    font-size: 0.72rem;
    font-weight: 700;
}

/* Badges de Ranking e Smart Tags */
.badge-ranking {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 0.7rem;
    font-weight: 600;
    padding: 4px 8px;
    border-radius: 4px;
    text-transform: uppercase;
}
.badge-pos1 { background: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }
.badge-pos2 { background: #e0f2fe; color: #075985; border: 1px solid #bae6fd; }
.badge-pos3 { background: #f1f5f9; color: #475569; border: 1px solid #e2e8f0; }
.badge-fast { background: #fef9c3; color: #854d0e; border: 1px solid #fef08a; }

/* Expanders */
[data-testid="stExpander"] {
    background-color: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 8px !important;
}
[data-testid="stExpander"] summary {
    color: #334155 !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
}

/* Dialog fix - word wrap */
[data-testid="stDialog"] [data-testid="stMarkdownContainer"] p {
    word-break: break-word !important;
    overflow-wrap: break-word !important;
    white-space: normal !important;
}
[data-testid="stDialog"] .stButton > button {
    white-space: normal !important;
    height: auto !important;
    min-height: 48px !important;
}

/* Selectbox */
.stSelectbox > div > div {
    border-radius: 6px !important;
}

/* DataEditor */
[data-testid="stDataFrame"] {
    border-radius: 8px !important;
}
</style>
""", unsafe_allow_html=True)




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
MERCADORIA_LOGBG = int(_secret("MERCADORIA_LOGBG", 110))







# ===================== PERSISTÊNCIA DE HISTÓRICO ============# ===================== UTILITÁRIOS =====================
# (Funções movidas para utils.py)
# ===================== INTEGRAÇÃO BRASPRESS (OFICIAL API) =====================
# (Funções movidas para api_services.py)
# ===================== INTEGRAÇÃO SSW WSDL (OFICIAL API) =====================
# (Funções movidas para api_services.py)
# ===================== GERADORES DE EXCEL PROFISSIONAIS =====================
# (Funções movidas para excel_generator.py) =====================




# ====================== SIDEBAR ENTERPRISE ======================
with st.sidebar:
    import base64 as _b64_sb
    _logo_sb_b64 = ""
    if os.path.exists("logo_next.png"):
        with open("logo_next.png", "rb") as _fsb:
            _logo_sb_b64 = _b64_sb.b64encode(_fsb.read()).decode()
    if _logo_sb_b64:
        st.markdown(
            f"""
            <div style="padding:20px 0 20px 0;margin-bottom:24px;text-align:center;">
              <img src="data:image/png;base64,{_logo_sb_b64}" style="max-width:180px;height:auto;" />
              <div style="font-size:0.75rem;color:#cbd5e1;font-weight:600;margin-top:10px;">Logística & Cotações</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div style="padding:20px 0 20px 0;margin-bottom:24px;">
              <div style="display:flex;align-items:center;gap:12px;">
                <div translate="no" class="notranslate" style="width:36px;height:36px;background:#000033;border-radius:8px;display:flex;align-items:center;justify-content:center;color:white;font-weight:800;font-size:1.1rem;box-shadow:0 4px 6px -1px rgba(0,0,51,0.2);">NC</div>
                <div>
                  <div translate="no" class="notranslate" style="font-size:1.05rem;font-weight:700;color:#f1f5f9;letter-spacing:-0.02em;">Next Cable</div>
                  <div style="font-size:0.75rem;color:#cbd5e1;font-weight:600;">Logística & Cotações</div>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='font-size:0.65rem;font-weight:700;color:#cbd5e1;margin-bottom:8px;letter-spacing:0.08em;text-transform:uppercase;padding:0 4px;'>Menu</div>", unsafe_allow_html=True)

    modulos = [
        "Nova Cotação",
        "Rastreamento de Pedidos",
        "Histórico de Cotações",
    ]
    u = st.session_state.get("user") or {}
    if u.get("role") == "ADMIN":
        modulos.append("Painel Admin")

    if "active_module" not in st.session_state or st.session_state.active_module not in modulos:
        st.session_state.active_module = "Nova Cotação"

    for m in modulos:
        is_active = (st.session_state.active_module == m)
        btn_type = "primary" if is_active else "secondary"
        if st.button(m, key=f"nav_{m}", use_container_width=True, type=btn_type):
            if m == "Nova Cotação":
                # Limpeza COMPLETA do estado de cotação
                keys_to_keep = ["user", "active_module", "df_empresas", "origem_select", "hist_pagina", "hist_busca", "hist_status", "hist_periodo", "session_token"]
                for key in list(st.session_state.keys()):
                    if key not in keys_to_keep and not key.startswith("nav_") and not key.startswith("pag_") and not key.startswith("FormSubmitter:") and not key.startswith("st"):
                        del st.session_state[key]
            
            st.session_state.active_module = m
            st.rerun()
        if m == "Rastreamento de Pedidos":
            st.markdown("<div style='text-align:center; margin-top:-8px; margin-bottom:12px;'><span style='background:rgba(255,255,255,0.1); color:#cbd5e1; font-size:10px; font-weight:700; padding:3px 10px; border-radius:10px; letter-spacing:0.05em; text-transform:uppercase; border:1px solid rgba(255,255,255,0.2);'>Em breve</span></div>", unsafe_allow_html=True)

    aba = st.session_state.active_module

    st.markdown("<div style='margin-top:28px;padding-top:16px;border-top:1px solid rgba(255,255,255,0.1);'></div>", unsafe_allow_html=True)

    if st.button("Sair", key="btn_logout", use_container_width=True):
        if "auth" in st.secrets:
            st.logout()
        else:
            _user_to_logout = st.session_state.get("user")
            if "user" in st.session_state:
                del st.session_state["user"]
            cookie_controller_logout = CookieController() if CookieController else None
            if cookie_controller_logout:
                if _user_to_logout:
                    db_historico.clear_session_token(_user_to_logout['id'])
                cookie_controller_logout.remove('nextcable_session_token')
            st.rerun()

    st.markdown("<div style='margin-top:28px;padding-top:16px;border-top:1px solid rgba(255,255,255,0.1);'></div>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:0.65rem;font-weight:700;color:#cbd5e1;margin-bottom:8px;letter-spacing:0.08em;text-transform:uppercase;padding:0 4px;'>Transportadoras</div>", unsafe_allow_html=True)

    with st.expander("Abrangência (16 Transportadoras)"):
        for k, cfg in te.TRANSPORTADORAS_CONFIG.items():
            tags_html = " ".join([f"<span style='background:#334155;color:#cbd5e1;padding:2px 6px;border-radius:4px;font-size:0.6rem;font-weight:600;margin-right:3px;'>{t}</span>" for t in cfg["abrangencia_tags"]])
            st.markdown(
                f"<div style='margin-bottom:10px;border-bottom:1px solid #334155;padding-bottom:8px;'>"
                f"<div style='font-weight:600;color:#e2e8f0;font-size:0.82rem;'>{cfg['nome']}</div>"
                f"<div style='margin:4px 0;'>{tags_html}</div>"
                f"<div style='font-size:0.72rem;color:#94a3b8;'>{cfg['descricao']}</div>"
                f"</div>",
                unsafe_allow_html=True
            )

    st.markdown(f"<div style='margin-top:40px;font-size:0.68rem;color:#94a3b8;text-align:center;'>{APP_VERSION.split('—')[0].strip()}</div>", unsafe_allow_html=True)


# ==============================================================================
# MÓDULO 1: NOVA COTAÇÃO (COM SMART TRIAGE, GRID DINÂMICO E AUTO-COMPLETE)
# ==============================================================================
if aba == "Nova Cotação":
    st.markdown("<div style='font-size:1.5rem;font-weight:800;color:#0f172a;margin-bottom:4px;letter-spacing:-0.03em;'>Nova Cotação</div>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:0.82rem;color:#64748b;margin-bottom:20px;'>Preencha os dados abaixo para consultar as melhores opções de frete em tempo real.</div>", unsafe_allow_html=True)

    # Últimas cotações — bloco discreto
    try:
        import db_historico
        u = st.session_state.get("user", {})
        ultimas = db_historico.obter_cotacoes(status="Todas", limit=3, owner_user_id=u.get("id"), role=u.get("role", "VENDEDOR"))
        if ultimas:
            with st.expander("📋 Últimas cotações", expanded=False):
                for idx_uc, uc in enumerate(ultimas):
                    _uc_status = uc.get('status', 'PENDENTE').upper()
                    _uc_nome = uc.get('nome_cliente', '')
                    _uc_dest = uc.get('cidade_uf_destino', '')
                    try:
                        _uc_dt = datetime.fromisoformat(uc.get('created_at', '')).strftime("%d/%m %H:%M")
                    except Exception:
                        _uc_dt = ""
                    
                    _badge_color = "#fef9c3" if _uc_status == "PENDENTE" else "#dcfce7" if _uc_status == "APROVADA" else "#fee2e2"
                    _badge_text = "#854d0e" if _uc_status == "PENDENTE" else "#166534" if _uc_status == "APROVADA" else "#991b1b"
                    
                    uc_cols = st.columns([3, 1, 1])
                    with uc_cols[0]:
                        st.markdown(f"<div style='font-size:13px;color:#334155;'><b>{_uc_nome or uc.get('cnpj_cliente', '')}</b> — {_uc_dest} <span style='color:#94a3b8;font-size:12px;'>{_uc_dt}</span> <span style='background:{_badge_color};color:{_badge_text};padding:2px 6px;border-radius:4px;font-size:10px;font-weight:700;margin-left:4px;'>{_uc_status}</span></div>", unsafe_allow_html=True)
                    with uc_cols[1]:
                        if st.button("Retomar", key=f"uc_retomar_{idx_uc}", use_container_width=True):
                            st.session_state.acao_retomar = uc["id"]
                            st.session_state.active_module = "Histórico de Cotações"
                            st.rerun()
    except Exception:
        pass

    # Barra elegante e compacta de Origem
    with st.container(border=True):
        st.markdown("<div class='section-title'><span class='num'>1</span>Local de Origem</div>", unsafe_allow_html=True)
        origens_dict = {
            "NEXT Matriz": {"cnpj": "26434839000121", "cep": "86071000", "cidade": "Londrina", "uf": "PR", "bairro": "Parque Comercial Quati"},
            "R NET": {"cnpj": "11275512000187", "cep": "86010070", "cidade": "Londrina", "uf": "PR", "bairro": "Centro"},
            "GB SOUZA": {"cnpj": "11572216000148", "cep": "86026090", "cidade": "Londrina", "uf": "PR", "bairro": "Centro"},
            "NEXT Filial MG": {"cnpj": "26434839000474", "cep": "30810600", "cidade": "Belo Horizonte", "uf": "MG", "bairro": "Paqueta"},
            "NEXT Filial GO": {"cnpj": "26434839000202", "cep": "75114300", "cidade": "Anápolis", "uf": "GO", "bairro": "JK Nova Capital"},
            "Outra Origem (Digitar Manualmente)": {"cnpj": "", "cep": "", "cidade": "", "uf": "", "bairro": ""}
        }

        origem_selecionada = st.selectbox("Selecione a Origem", list(origens_dict.keys()), key="origem_select", label_visibility="collapsed")

        if origem_selecionada == "Outra Origem (Digitar Manualmente)":
            c_cnpj, c_cep = st.columns(2)
            with c_cnpj:
                cnpj_remetente = st.text_input("CNPJ Origem", key="cnpj_rem_inp")
            with c_cep:
                cep_origem = st.text_input("CEP Origem", key="cep_o_inp")
                
            if cep_origem:
                cep_origem = cep_origem.replace('-', '').replace(' ', '')
                
            res_cep_o = buscar_cep(cep_origem)
            if res_cep_o:
                info_o = {
                    "ok": True,
                    "texto": f"{res_cep_o.get('bairro', '')} · {res_cep_o.get('cidade', '')}/{res_cep_o.get('uf', '')}",
                    "cidade": res_cep_o.get("cidade", ""),
                    "uf": res_cep_o.get("uf", "")
                }
            else:
                info_o = {"ok": False, "texto": "", "cidade": "", "uf": ""}
        else:
            cnpj_remetente = origens_dict[origem_selecionada]["cnpj"]
            cep_origem = origens_dict[origem_selecionada]["cep"]
            cidade_o = origens_dict[origem_selecionada]["cidade"]
            uf_o = origens_dict[origem_selecionada]["uf"]
            bairro_o = origens_dict[origem_selecionada]["bairro"]
            
            info_o = {
                "ok": True,
                "texto": f"{bairro_o} · {cidade_o}/{uf_o}",
                "cidade": cidade_o,
                "uf": uf_o
            }
            st.markdown(f"<div style='display: flex; justify-content: flex-start; margin: 4px 0 10px 0;'><div style='background-color: #f8fafc; border: 1px solid #e2e8f0; border-left: 4px solid #0ea5e9; border-radius: 6px; padding: 6px 14px; font-size: 12px; font-family: sans-serif;'><span style='color: #0f172a; font-weight: 700;'>ORIGEM:</span> <span style='color: #475569;'>{origem_selecionada}</span> &nbsp;&nbsp;|&nbsp;&nbsp; <span style='color: #0f172a; font-weight: 700;'>CNPJ:</span> <span style='color: #475569;'>{cnpj_remetente}</span> &nbsp;&nbsp;|&nbsp;&nbsp; <span style='color: #0f172a; font-weight: 700;'>CEP:</span> <span style='color: #475569;'>{cep_origem}</span></div></div>", unsafe_allow_html=True)

        st.session_state.cnpj_rem_custom = cnpj_remetente
        st.session_state.cep_rem_custom = cep_origem

    st.write("") # Espaçador sutil
    
    # 2. Dados de Destinatário (100% largura)
    with st.container(border=True):
        st.markdown("<div class='section-title'><span class='num'>2</span>Dados do Destinatário</div>", unsafe_allow_html=True)
        doc_destinatario = st.text_input("CNPJ / CPF do Destinatário", key="cnpj_input")
        doc_limpo = limpar_documento(doc_destinatario)

        if len(doc_limpo) == 14:
            info_emp_dest = buscar_empresa_cnpj(doc_limpo)
            

            
            if info_emp_dest and info_emp_dest.get("ok"):
                _razao = info_emp_dest.get('razao', '')
                _logr = info_emp_dest.get('logradouro', '')
                _num = info_emp_dest.get('numero', '')
                _bairro = info_emp_dest.get('bairro', '')
                _cidade = info_emp_dest.get('cidade', '')
                _uf_emp = info_emp_dest.get('uf', '')
                _cep_emp = info_emp_dest.get('cep', '')
                _cep_fmt = f"{_cep_emp[:5]}-{_cep_emp[5:]}" if len(_cep_emp) == 8 else _cep_emp
                _end_parts = [p for p in [f"{_logr}, {_num}" if _logr else "", _bairro] if p]
                _end_str = " — ".join(_end_parts) if _end_parts else "Endereço não disponível"
                # Auto-preenchimento do CEP
                if st.session_state.get("last_cnpj_fetched") != doc_limpo:
                    st.session_state.last_cnpj_fetched = doc_limpo
                    st.session_state.razao_social = info_emp_dest.get("razao", "")
                    if info_emp_dest.get("cep"):
                        st.session_state.cep_d = info_emp_dest.get("cep")
                        st.session_state.logradouro = info_emp_dest.get("logradouro")
                        st.session_state.numero = info_emp_dest.get("numero")
                        st.session_state.bairro = info_emp_dest.get("bairro")
                        st.session_state.cidade = info_emp_dest.get("cidade")
                        st.session_state.uf = info_emp_dest.get("uf")
                        st.rerun()
            else:
                if st.session_state.get("last_cnpj_fetched") != doc_limpo:
                    st.session_state.last_cnpj_fetched = doc_limpo
                    st.warning("Não foi possível consultar automaticamente os dados cadastrais deste CNPJ no momento.\n\nIsso não impede a cotação. Continue informando o CEP de destino.")
        elif len(doc_limpo) > 0:
            if "razao_social" in st.session_state and st.session_state.razao_social != "":
                st.session_state.razao_social = ""
                st.session_state.last_cnpj_fetched = ""
        else:
            if "razao_social" in st.session_state and st.session_state.razao_social != "":
                st.session_state.razao_social = ""
                st.session_state.last_cnpj_fetched = ""

        cep_destino = st.text_input("CEP Destino", key="cep_d")
        if cep_destino:
            cep_destino = cep_destino.replace('-', '').replace(' ', '')

        res_cep = buscar_cep(cep_destino)
        if res_cep:
            info_d = {
                "ok": True,
                "cidade": res_cep.get("cidade", ""),
                "uf": res_cep.get("uf", ""),
                "bairro": res_cep.get("bairro", ""),
                "logradouro": "",
                "texto": f"{res_cep.get('bairro', '')} · {res_cep.get('cidade', '')}/{res_cep.get('uf', '')}"
            }
        else:
            if cep_destino and len(cep_destino) == 8:
                st.warning("CEP não localizado na base dos Correios. Por favor, insira a UF e Cidade manualmente abaixo para prosseguir com a cotação.")
                c1_man, c2_man = st.columns([1, 3])
                with c1_man:
                    man_uf = st.text_input("UF (ex: SP)", key="man_uf", max_chars=2).upper()
                with c2_man:
                    man_cidade = st.text_input("Cidade", key="man_cidade")
                
                if man_uf and man_cidade:
                    info_d = {
                        "ok": True,
                        "cidade": man_cidade.strip(),
                        "uf": man_uf.strip(),
                        "bairro": "Não informado",
                        "logradouro": "",
                        "texto": f"Preenchimento Manual · {man_cidade.strip()}/{man_uf.strip()}"
                    }
                else:
                    info_d = {"ok": False, "cidade": "", "uf": "", "bairro": "", "logradouro": "", "texto": ""}
            else:
                info_d = {"ok": False, "cidade": "", "uf": "", "bairro": "", "logradouro": "", "texto": ""}

        if info_d["ok"]:
            _logr = info_d.get('logradouro', '')
            _bairro = info_d.get('bairro', '')
            _cidade = info_d.get('cidade', '')
            _uf = info_d.get('uf', '')
            _cep = cep_destino
            
            # Se a busca por CNPJ salvou os dados da empresa, usamos
            _nome = ""
            if len(doc_limpo) == 14 and st.session_state.get('razao_social'):
                _nome = f"<div translate='no' class='notranslate' style='font-weight:700;font-size:0.95rem;color:#000033;margin-bottom:6px;'>{st.session_state.get('razao_social')}</div>"
                if not _logr: _logr = st.session_state.get('logradouro', '')
                if not _bairro: _bairro = st.session_state.get('bairro', '')
            
            # Montar a string do endereço completo
            _partes = [p for p in [_logr, _bairro] if p]
            _end_str = ", ".join(_partes) if _partes else "Endereço não informado"
            _cep_fmt = f"{_cep[:5]}-{_cep[5:]}" if len(_cep) == 8 else _cep

            st.markdown(
                f"""
                <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:6px;padding:8px 12px;margin-top:-5px;margin-bottom:15px;width:100%;box-sizing:border-box;">
                  {_nome}
                  <div style="font-size:0.82rem;color:#1d4ed8;font-weight:500;">
                    {_end_str}, {_cidade}/{_uf} CEP {_cep_fmt}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.write("") # Espaçador sutil

    # 3. Informações da Carga (100% largura)
    with st.container(border=True):
        st.markdown("<div class='section-title'><span class='num'>3</span>Informações da Carga</div>", unsafe_allow_html=True)
        valor_nf_str = st.text_input("Valor Total da NF (R$)", placeholder="Ex: 6.908,13", key="valor_nf_input")
        valor_nf = None
        if valor_nf_str:
            try:
                import re
                # Mantém apenas números, vírgula e ponto
                v_str = re.sub(r'[^\d,\.]', '', valor_nf_str)
                if ',' in v_str:
                    # Se tem vírgula, a última é o separador decimal
                    parts = v_str.rsplit(',', 1)
                    inteiro = parts[0].replace('.', '')
                    decimal = parts[1]
                    valor_nf = float(f"{inteiro}.{decimal}")
                else:
                    # Se não tem vírgula, trata o ponto (se houver) como decimal
                    valor_nf = float(v_str)
                val_nf_fmt = utils.formatar_moeda(valor_nf)
                st.markdown(f"<div style='font-size:0.75rem; color:#64748b; margin-top:-10px; margin-bottom:10px; padding-left:4px;'>Confirmado: {val_nf_fmt}</div>", unsafe_allow_html=True)
            except ValueError:
                st.error("Formato inválido. Use um formato como 6.908,13")
        obs_carga = st.text_area("Observações (Opcional)", key="obs_carga_input", height=68)

    # 4. ESPECIFICAÇÃO DE VOLUMES (LARGURA TOTAL 100% — SEM CORTES)
    with st.container(border=True):
        st.markdown("<div class='section-title'><span class='num'>4</span>Especificação de Volumes</div>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:0.8rem;color:#64748b;margin-bottom:14px;'>Informe as dimensões de cada volume. Pesos cubado e tarifado são calculados em tempo real.</div>", unsafe_allow_html=True)

        # Inicializar estado base para a tabela se necessário
        if "volumes_base" not in st.session_state:
            import pandas as pd
            if "volumes_data" in st.session_state and st.session_state.volumes_data:
                st.session_state.volumes_base = pd.DataFrame(st.session_state.volumes_data)
            else:
                st.session_state.volumes_base = pd.DataFrame([{"Qtd": 0, "Alt (cm)": 0.0, "Larg (cm)": 0.0, "Comp (cm)": 0.0, "Peso Total (kg)": 0.0}])
        
        # Se o widget interno do Streamlit foi desmontado (ex: troca de aba), restauramos a base com o último backup
        if "tabela_volumes_fixa" not in st.session_state:
            if "volumes_data" in st.session_state and st.session_state.volumes_data:
                import pandas as pd
                st.session_state.volumes_base = pd.DataFrame(st.session_state.volumes_data)

        try:
            df_volumes_editado = st.data_editor(
                st.session_state.volumes_base, # NUNCA atualizamos isso de volta para não resetar o componente!
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True,
                key="tabela_volumes_fixa",
                column_config={
                    "Qtd": st.column_config.NumberColumn("Qtd", min_value=0, step=1, default=0, required=True),
                    "Alt (cm)": st.column_config.NumberColumn("Alt (cm)", min_value=0.0, step=1.0, default=0.0, required=True),
                    "Larg (cm)": st.column_config.NumberColumn("Larg (cm)", min_value=0.0, step=1.0, default=0.0, required=True),
                    "Comp (cm)": st.column_config.NumberColumn("Comp (cm)", min_value=0.0, step=1.0, default=0.0, required=True),
                    "Peso Total (kg)": st.column_config.NumberColumn("Peso Total (kg)", min_value=0.0, step=0.5, default=0.0, format="%.2f", required=True),
                },
            )

            # Sanitização Imediata (A Bala de Prata)
            df_volumes_editado = df_volumes_editado.fillna(0)

            if df_volumes_editado is not None:
                # Atualizar APENAS o backup final para não quebrar o estado nativo do Streamlit
                st.session_state.volumes_data = df_volumes_editado.to_dict(orient="records")

            # Funções de conversão super robustas para garantir que valores vazios ou com vírgula nunca falhem silenciosamente
            def safe_float(val):
                if pd.isna(val) or val is None:
                    return 0.0
                s = str(val).strip().replace(',', '.')
                if not s:
                    return 0.0
                try:
                    return float(s)
                except:
                    return 0.0

            def safe_int(val):
                return int(safe_float(val))

            # Recálculo automático em tempo real garantido
            calc_volumes_qtd = 0
            calc_peso_real = 0.0
            calc_volume_m3 = 0.0

            if df_volumes_editado is not None and not df_volumes_editado.empty:
                # Extração direta usando vetorização com fallback seguro:
                qtd_col = "Qtd" if "Qtd" in df_volumes_editado.columns else df_volumes_editado.columns[0]
                peso_col = "Peso Total (kg)" if "Peso Total (kg)" in df_volumes_editado.columns else (df_volumes_editado.columns[4] if len(df_volumes_editado.columns) > 4 else None)
                
                try:
                    calc_volumes_qtd = int(df_volumes_editado[qtd_col].apply(safe_float).sum())
                except:
                    pass
                    
                try:
                    if peso_col:
                        calc_peso_real = float(df_volumes_editado[peso_col].apply(safe_float).sum())
                except:
                    pass

                for _, row in df_volumes_editado.iterrows():
                    try:
                        _q = safe_int(row.get(qtd_col)) if not pd.isna(row.get(qtd_col)) else safe_int(row.iloc[0] if len(row) > 0 else 0)
                        _a = safe_float(row.get("Alt (cm)")) if not pd.isna(row.get("Alt (cm)")) else safe_float(row.iloc[1] if len(row) > 1 else 0)
                        _l = safe_float(row.get("Larg (cm)")) if not pd.isna(row.get("Larg (cm)")) else safe_float(row.iloc[2] if len(row) > 2 else 0)
                        _c = safe_float(row.get("Comp (cm)")) if not pd.isna(row.get("Comp (cm)")) else safe_float(row.iloc[3] if len(row) > 3 else 0)
                        
                        calc_volume_m3 += (_q * (_a * _l * _c)) / 1000000.0
                    except Exception as e:
                        import logging
                        logging.warning(f"Erro ao processar volume (cubagem): {e}")

            fator_cubagem = 300
            calc_peso_cubado = calc_volume_m3 * fator_cubagem
            calc_peso_tarifado = max(calc_peso_real, calc_peso_cubado)
            calc_e_cubado = calc_peso_cubado > calc_peso_real
            
            # Update global variables used downstream
            total_volumes_qtd = calc_volumes_qtd
            peso_real_total = calc_peso_real
            volume_total_m3 = calc_volume_m3
            peso_cubado_total = calc_peso_cubado
            peso_tarifado = calc_peso_tarifado
            e_cubado = calc_e_cubado

        except Exception as e:
            st.error(f"Erro na tabela: {e}")
            total_volumes_qtd = 0
            peso_real_total = 0.0
            volume_total_m3 = 0.0
            peso_tarifado = 0.0
            e_cubado = False
        
        texto_regra = "Cobrança por Cubagem" if e_cubado else "Cobrança por Peso Real"
        cor_destaque = "#000033" if e_cubado else "#059669"

        # Resumo de Volumes - Grid Customizado (garante mesma altura visual e previne quebras)
        st.markdown(f"""
        <div style="padding-bottom:16px;">
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-top: 16px;">
            <div style="display: flex; flex-direction: column; justify-content: center; background:#f8fafc; border:1px solid #e2e8f0; border-top:3px solid #0ea5e9; border-radius:8px; padding:16px 12px; text-align:center;">
                <div style="font-size:0.7rem; color:#64748b; text-transform:uppercase; font-weight:700; letter-spacing:0.04em; margin-bottom:8px;">Volumes / Cubagem</div>
                <div style="font-size:1.25rem; font-weight:700; color:#0f172a; margin-bottom:4px;">{total_volumes_qtd} <span style="font-size:0.8rem; font-weight:500; color:#64748b;">vols</span></div>
                <div style="font-size:0.85rem; color:#475569;">{volume_total_m3:.4f} m³</div>
            </div>
            <div style="display: flex; flex-direction: column; justify-content: center; background:#f8fafc; border:1px solid #e2e8f0; border-top:3px solid #64748b; border-radius:8px; padding:16px 12px; text-align:center;">
                <div style="font-size:0.7rem; color:#64748b; text-transform:uppercase; font-weight:700; letter-spacing:0.04em; margin-bottom:8px;">Peso Total Real</div>
                <div style="font-size:1.25rem; font-weight:700; color:#0f172a; margin-bottom:4px;">{peso_real_total:.2f} <span style="font-size:0.8rem; font-weight:500; color:#64748b;">kg</span></div>
            </div>
            <div style="display: flex; flex-direction: column; justify-content: center; background:#f8fafc; border:1px solid #e2e8f0; border-top:3px solid {cor_destaque}; border-radius:8px; padding:16px 12px; text-align:center;">
                <div style="font-size:0.7rem; color:#64748b; text-transform:uppercase; font-weight:700; letter-spacing:0.04em; margin-bottom:8px;">Peso Cobrado</div>
                <div style="font-size:1.25rem; font-weight:800; color:{cor_destaque}; margin-bottom:4px;">{peso_tarifado:.2f} <span style="font-size:0.8rem; font-weight:600; color:#64748b;">kg</span></div>
                <div style="font-size:0.75rem; color:#64748b; line-height:1.2; word-break:break-word;">{texto_regra}</div>
            </div>
        </div>
        </div>
        """, unsafe_allow_html=True)


    st.write("")
    # Botão de Ação Primária
    st.markdown('<style> div.stButton > button p { font-weight: 800 !important; font-size: 16px !important; letter-spacing: 0.5px; } </style>', unsafe_allow_html=True)
    st.markdown('<div class="btn-cta">', unsafe_allow_html=True)
    btn_processar = st.button("PROCESSAR COTAÇÕES", use_container_width=True, type="primary", disabled=st.session_state.get("processando_cotacao", False))
    st.markdown('</div>', unsafe_allow_html=True)

    # Placeholder para Skeleton Loader ou Resultados
    placeholder_resultados = st.empty()

    @st.dialog("Confirmação de Dados")
    def confirm_quote():
        # Dados do destinatário
        _rs = st.session_state.get('razao_social', '')
        _cd = info_d.get('cidade', '')
        _uf = info_d.get('uf', '')
        if _rs:
            st.markdown(f"**Destinatário:** <span translate='no' class='notranslate'>{_rs}</span>", unsafe_allow_html=True)
        st.markdown(f"**CNPJ/CPF:** {doc_destinatario}")
        st.markdown(f"**Destino:** {_cd}/{_uf} — CEP {cep_destino}")
        st.markdown(f"**Remetente:** {cnpj_remetente} — CEP {cep_origem}")
        
        v_nf = valor_nf if valor_nf else 0.0
        st.markdown(f"**Valor NF:** R$ {v_nf:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."))
        
        dims = []
        for _, row in df_volumes_editado.iterrows():
            try:
                q = safe_int(row.get("Qtd"))
                if q <= 0:
                    continue
                a = safe_int(row.get('Alt (cm)'))
                l = safe_int(row.get('Larg (cm)'))
                c = safe_int(row.get('Comp (cm)'))
                dims.append(f"{c}x{l}x{a}")
            except Exception:
                pass
        
        st.markdown(f"**Volumes:** {total_volumes_qtd} — {', '.join(dims)} cm")
        st.markdown(f"**Peso Real:** {peso_real_total:.2f} kg | **Cubagem:** {volume_total_m3:.4f} m³")
        st.markdown(f"**Peso Tarifado:** {peso_tarifado:.2f} kg ({texto_regra})")
        
        st.write("")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Confirmar e Cotar", type="primary", use_container_width=True):
                st.session_state.processar_confirmado = True
                st.session_state.processando_cotacao = True
                st.rerun()
        with col2:
            if st.button("Voltar", use_container_width=True):
                st.rerun()

    if btn_processar:
        if origem_selecionada not in ["NEXT Matriz", "R NET", "GB SOUZA"]:
            st.warning("As tabelas de frete integradas são exclusivas para as operações de Londrina (NEXT Matriz, R NET e GB).")
            st.stop()
        if not cep_origem or str(cep_origem).strip() == "":
            st.warning('Por favor, preencha o CEP de Origem.')
            st.stop()
        if not cep_destino or str(cep_destino).strip() == "":
            st.warning('Por favor, preencha o CEP de Destino.')
            st.stop()
        if valor_nf is None or valor_nf <= 0:
            st.warning('Por favor, preencha o Valor Total da Nota Fiscal.')
            st.stop()
        if peso_real_total is None or peso_real_total <= 0:
            st.warning('Por favor, preencha as Dimensões e o Peso Total da Carga.')
            st.stop()
            
        erros = []
        cep_o_num = re.sub(r"\D", "", str(cep_origem))
        cep_d_num = re.sub(r"\D", "", str(cep_destino))

        if len(cep_o_num) != 8:
            erros.append("O CEP de Origem deve conter 8 dígitos válidos.")
        elif not info_o.get("ok"):
            erros.append(f"CEP de Origem '{cep_origem}' não localizado.")

        if len(cep_d_num) != 8:
            erros.append("O CEP de Destino deve conter 8 dígitos válidos.")
        elif not info_d.get("ok"):
            erros.append(f"CEP de Destino '{cep_destino}' não localizado.")

        if total_volumes_qtd is None or total_volumes_qtd <= 0 or volume_total_m3 is None or volume_total_m3 <= 0:
            erros.append("Adicione ao menos um volume com dimensões válidas.")

        if erros:
            for erro in erros:
                st.error(f"⚠️ {erro}")
        else:
            confirm_quote()

    if st.session_state.get("processar_confirmado"):
        st.session_state.processar_confirmado = False
        # Exibir Skeleton Loaders imediatamente (Feedback de alta performance)
        with placeholder_resultados.container():
                st.markdown(
                    """
                    <div style="margin:20px 0;">
                      <div style="color:#4f46e5;font-weight:700;font-size:0.9rem;margin-bottom:12px;display:flex;align-items:center;gap:8px;">
                        <span class="badge-triage badge-rapida">⚡ PROCESSANDO EM PARALELO</span> Consultando APIs oficiais e tabelas simultaneamente...
                      </div>
                      <div style="display:grid;grid-template-columns:repeat(3, 1fr);gap:14px;">
                        <div class="skeleton-card"></div>
                        <div class="skeleton-card"></div>
                        <div class="skeleton-card"></div>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        cubagem_lista = []
        for _, row in df_volumes_editado.iterrows():
            try:
                q = safe_int(row.get("Qtd"))
                if q <= 0:
                    continue
                a = safe_float(row.get("Alt (cm)")) / 100.0
                l = safe_float(row.get("Larg (cm)")) / 100.0
                c = safe_float(row.get("Comp (cm)")) / 100.0

                cubagem_lista.append({"Altura": a, "Largura": l, "Comprimento": c, "Volumes": q})
            except Exception as e:
                import logging
                logging.warning(f"Erro ao processar volume (cubagem_lista): {e}")

        uf_dest = info_d.get("uf", "")
        cidade_dest = info_d.get("cidade", "")

        # 1. Consultas a APIs Oficiais em Paralelo
        with st.spinner('Buscando os melhores preços...'):
            futures = {}
            with ThreadPoolExecutor(max_workers=5) as executor:
                if USUARIO_BRASPRESS and SENHA_BRASPRESS:
                    futures["braspress"] = executor.submit(
                        cotar_braspress, cep_origem, cep_destino, peso_real_total, valor_nf,
                        cubagem_lista, cnpj_remetente, doc_destinatario
                    )

                if DOMINIO_COPEX and USUARIO_COPEX:
                    futures["coopex"] = executor.submit(
                        cotar_ssw_wsdl, "Coopex", DOMINIO_COPEX, USUARIO_COPEX, SENHA_COPEX,
                        cep_origem, cep_destino, peso_real_total, valor_nf, cubagem_lista,
                        cnpj_remetente, doc_destinatario, 1
                    )

            # Processamento Braspress
            if "braspress" in futures:
                try:
                    r_braspress = futures["braspress"].result(timeout=20)
                    if r_braspress.get("Valor Frete (R$)") is not None:
                        r_braspress["Atendida"] = True
                        r_braspress["Tags"] = ["BRASIL"]
                        r_braspress["Base Tarifária"] = "API Oficial REST v1 (Token Oauth2)"
                        r_braspress["Motivo"] = "Cobertura Nacional Confirmada"
                    else:
                        r_braspress["Atendida"] = False
                        r_braspress["Status"] = "Fora do ar / Indisponível"
                        r_braspress["Motivo"] = "API Oficial Braspress retornou erro ou indisponibilidade temporária"
                        r_braspress["Tags"] = ["BRASIL"]
                        r_braspress["Base Tarifária"] = "API Oficial REST v1"
                except Exception as e:
                    r_braspress = {"Transportadora": "Braspress", "Nº Cotação": "-", "Valor Frete (R$)": None, "Prazo (Dias Úteis)": 0, "Status": "Fora do ar / Indisponível", "Atendida": False, "Motivo": f"Timeout ou erro de conexão: {str(e)[:30]}", "Tags": ["BRASIL"], "Base Tarifária": "API Oficial REST v1"}
            else:
                r_braspress = {"Transportadora": "Braspress", "Nº Cotação": "-", "Valor Frete (R$)": None, "Prazo (Dias Úteis)": 0, "Status": "Fora do ar / Indisponível", "Atendida": False, "Motivo": "Credenciais da API Braspress não configuradas", "Tags": ["BRASIL"], "Base Tarifária": "API Oficial REST v1"}

            # Processamento Coopex
            if "coopex" in futures:
                try:
                    r_coopex = futures["coopex"].result(timeout=20)
                    if r_coopex.get("Valor Frete (R$)") is not None:
                        r_coopex["Atendida"] = True
                        r_coopex["Tags"] = ["PR", "SC", "RS"]
                        r_coopex["Base Tarifária"] = "Webservice SSW WSDL Oficial"
                        r_coopex["Motivo"] = "Webservice SSW Confirmado"
                    else:
                        r_coopex = te.calcular_frete_estrito("COOPEX", peso_tarifado, peso_real_total, valor_nf, uf_dest, cidade_dest, cep_destino)
                except Exception:
                    r_coopex = te.calcular_frete_estrito("COOPEX", peso_tarifado, peso_real_total, valor_nf, uf_dest, cidade_dest, cep_destino)
            else:
                r_coopex = te.calcular_frete_estrito("COOPEX", peso_tarifado, peso_real_total, valor_nf, uf_dest, cidade_dest, cep_destino)

        # 2. Avaliação Rigorosa das 14 Demais Tabelas Contratuais Homologadas
        chaves_tabelas = [
            "PRINCESA", "ALFA", "TW", "ENVIA_RAPIDO", "GARCIA", "SUDOESTE",
            "CARRION", "EXPRESSO_SAO_MIGUEL", "LOGDI", "OURO_NEGRO",
            "RODONAVES", "TECMAR", "AGEX", "VIP", "ARAGAO"
        ]

        resultados_tabelas = [
            te.calcular_frete_estrito(k, peso_tarifado, peso_real_total, valor_nf, uf_dest, cidade_dest, cep_destino)
            for k in chaves_tabelas
        ]

        resultados = [r_braspress, r_coopex] + resultados_tabelas

        # Salvar na sessão
        st.session_state.ultima_cotacao = {
            "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "remetente": cnpj_remetente,
            "destinatario": doc_destinatario,
            "origem_cep": cep_origem,
            "origem_texto": info_o.get("texto", ""),
            "destino_cep": cep_destino,
            "destino_texto": info_d.get("texto", ""),
            "uf_dest": uf_dest,
            "cidade_dest": cidade_dest,
            "peso": peso_real_total,
            "volume_m3": volume_total_m3,
            "peso_cubado": peso_cubado_total,
            "peso_tarifado": peso_tarifado,
            "valor_nf": valor_nf,
            "volumes_qtd": total_volumes_qtd,
            "volumes_data": st.session_state.get("volumes_data", []),

            "resultados": resultados,
            "obs": obs_carga,
        }

        # Histórico com a melhor oferta válida
        opcoes_validas_hist = [r for r in resultados if r.get("Atendida") and r.get("Valor Frete (R$)") is not None]
        if opcoes_validas_hist:
            df_temp_v = pd.DataFrame(opcoes_validas_hist).sort_values("Valor Frete (R$)").reset_index(drop=True)
            melhor_item = df_temp_v.iloc[0]
            u = st.session_state.get("user", {})
            salvar_historico_item({
                "id": f"COT-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                "cnpj_cliente": doc_destinatario,
                "nome_cliente": st.session_state.get('razao_social', ''),
                "cidade_uf_destino": f"{cidade_dest}/{uf_dest}".strip("/"),
                "cep_destino": cep_destino,
                "valor_nf": valor_nf,
                "qtd_volumes": total_volumes_qtd,
                "peso_real": peso_real_total,
                "peso_cubado": peso_cubado_total,
                "peso_tarifado": peso_tarifado,
                "volumes_data": st.session_state.get("volumes_data", []),
                "origem": f"{info_o.get('cidade','')}/{info_o.get('uf','')}".strip("/"),
                "cep_origem": cep_origem,
                "melhor_transportadora": melhor_item["Transportadora"],
                "melhor_valor": melhor_item["Valor Frete (R$)"],
                "melhor_prazo": int(melhor_item.get("Prazo (Dias Úteis)") or 0),
                "melhor_tipo": melhor_item.get("Base Tarifária", "Tabela Contratual"),
                "razao_social": st.session_state.get('razao_social', ''),
                "logradouro": st.session_state.get('logradouro', ''),
                "numero": st.session_state.get('numero', ''),
                "bairro": st.session_state.get('bairro', ''),
                "cidade": st.session_state.get('cidade', ''),
                "uf": st.session_state.get('uf', ''),
                "resultados": resultados
            }, owner_user_id=u.get("id"))

        placeholder_resultados.empty()

    # ================= APRESENTAÇÃO DOS RESULTADOS (ESTRITA E SEGREGADA) =================
    if "ultima_cotacao" in st.session_state and st.session_state.ultima_cotacao:
        cot_info = st.session_state.ultima_cotacao
        resultados = cot_info.get("resultados", [])

        opcoes_atendidas = [r for r in resultados if r.get("Atendida") and r.get("Valor Frete (R$)") is not None]
        opcoes_indisponiveis = [r for r in resultados if not r.get("Atendida") or r.get("Valor Frete (R$)") is None]

        df_valid = pd.DataFrame(opcoes_atendidas)
        if not df_valid.empty:
            df_valid = df_valid.sort_values("Valor Frete (R$)").reset_index(drop=True)

        st.markdown("<div style='border-top:2px solid #e2e8f0;margin:24px 0 20px 0;'></div>", unsafe_allow_html=True)

        # Cabeçalho da Seção de Resultados com dados do destinatário
        _rs_header = st.session_state.get('razao_social', '')
        _dest_label = f"<b translate='no' class='notranslate'>{_rs_header}</b> — " if _rs_header else ""
        
        col_res_header, col_res_excel, col_res_wa = st.columns([2.2, 1, 1.3], vertical_alignment="bottom")
        with col_res_header:
            st.markdown(
                f"<div style='font-size:1.3rem;font-weight:800;color:#0f172a;margin-bottom:4px;letter-spacing:-0.02em;'>Comparativo de Ofertas</div>"
                f"<div style='font-size:0.82rem;color:#64748b;margin-bottom:16px;line-height:1.5;'>{_dest_label}{cot_info.get('cidade_dest','')}/{cot_info.get('uf_dest','')} (CEP {cot_info.get('destino_cep','')}) &nbsp;·&nbsp; {cot_info.get('peso',0):.2f} kg &nbsp;·&nbsp; NF {formatar_moeda(cot_info.get('valor_nf'))}</div>",
                unsafe_allow_html=True,
            )
        with col_res_excel:
            df_all = pd.DataFrame(resultados)
            df_all["_ordem"] = df_all["Valor Frete (R$)"].isna().astype(int)
            df_all = df_all.sort_values(["_ordem", "Valor Frete (R$)"]).drop(columns=["_ordem"]).reset_index(drop=True)
            excel_bytes = gerar_excel_cotacao(cot_info, df_all)
            import base64
            b64_excel = base64.b64encode(excel_bytes).decode()
            nome_arquivo = f"cotacao_{cot_info.get('destino_cep')}_{datetime.now():%Y%m%d_%H%M}.xlsx"
            href_excel = f'<a download="{nome_arquivo}" href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64_excel}" style="display:block; text-align:center; background-color:#ffffff; color:#334155; border:1px solid #cbd5e1; border-radius:6px; font-weight:600; font-size:0.85rem; padding:10px 14px; text-decoration:none; box-shadow:0 1px 2px rgba(0,0,0,0.05); margin-bottom:16px; transition:all 0.2s;">Download Excel</a>'
            st.markdown(href_excel, unsafe_allow_html=True)
        with col_res_wa:
            if len(df_valid) > 0:
                v_data = cot_info.get('volumes_data', [])
                if v_data:
                    dim_list = [f"{int(float(v.get('Comp (cm)', 0)))}x{int(float(v.get('Larg (cm)', 0)))}x{int(float(v.get('Alt (cm)', 0)))}" for v in v_data]
                    dimensoes_resumidas = "\\n".join(dim_list)
                else:
                    dimensoes_resumidas = "N/A"
                
                melhor_op = df_valid.iloc[0]
                
                obs_text = f"\\n\\n*Observações:* {cot_info.get('obs')}" if cot_info.get('obs') else ""
                msg_completa = (
                    f"Olá!\\n"
                    f"Por gentileza, peço a validação desta cotação de frete:\\n\\n"
                    f"CNPJ remetente: {cot_info.get('remetente', 'N/A')}\\n"
                    f"CEP remetente: {cot_info.get('origem_cep', 'N/A')}\\n"
                    f"CNPJ destinatário: {cot_info.get('destinatario', 'N/A')}\\n"
                    f"CEP destinatário: {cot_info.get('destino_cep', 'N/A')}\\n"
                    f"Volumes: {cot_info.get('volumes_qtd', 0)}\\n"
                    f"Medidas:\\n"
                    f"{dimensoes_resumidas}\\n"
                    f"Peso: {cot_info.get('peso', 0):.2f}kg\\n"
                    f"Valor da NF: {utils.formatar_moeda(cot_info.get('valor_nf'))}\\n\\n"
                    f"*Estimativa via Tabela :* *{formatar_moeda(melhor_op['Valor Frete (R$)'])}*\\n\\n"
                    f"Pode confirmar se o valor bate com a tabela que temos com vocês?{obs_text}"
                )
                numero_wa = obter_numero_wa(melhor_op['Transportadora'])
                link_wa_geral = f"https://wa.me/{numero_wa}?text={urllib.parse.quote(msg_completa).replace('%5Cn', '%0A')}"
                href_wa = f'<a target="_blank" href="{link_wa_geral}" style="display:block; text-align:center; background-color:#10b981; color:#ffffff; border-radius:6px; font-weight:600; font-size:0.85rem; padding:11px 14px; text-decoration:none; box-shadow:0 1px 2px rgba(16,185,129,0.2); margin-bottom:16px; transition:all 0.2s;">Compartilhar Melhor Opção</a>'
                st.markdown(href_wa, unsafe_allow_html=True)

        if len(df_valid) == 0:
            st.error("Nenhuma transportadora atende este destino nas condições contratuais informadas.")
        else:
            # ================= TOP 3 RANKING (OPÇÕES DISTINTAS POR MENOR PREÇO) =================
            # Filtra para obter até 3 transportadoras distintas ordenadas estritamente pelo Menor Preço
            top_candidatos = []
            transp_vistas = set()
            for _, r_cand in df_valid.iterrows():
                nome_t = r_cand["Transportadora"]
                if nome_t not in transp_vistas:
                    transp_vistas.add(nome_t)
                    top_candidatos.append(r_cand)
                if len(top_candidatos) == 3:
                    break

            # Identificar o menor prazo global de entrega entre todas as opções válidas
            df_com_prazo = df_valid[df_valid["Prazo (Dias Úteis)"] > 0]
            min_prazo_global = int(df_com_prazo["Prazo (Dias Úteis)"].min()) if not df_com_prazo.empty else None

            prazo_op1 = int(top_candidatos[0]["Prazo (Dias Úteis)"]) if (
                len(top_candidatos) > 0 and pd.notna(top_candidatos[0]["Prazo (Dias Úteis)"]) and int(top_candidatos[0]["Prazo (Dias Úteis)"]) > 0
            ) else 0

            st.markdown(
                '<div style="font-size:0.84rem;font-weight:800;color:#0f172a;letter-spacing:0.04em;text-transform:uppercase;margin:12px 0 8px 0;">'
                'TOP 3 OPÇÕES (RANKING POR MENOR PREÇO)'
                '</div>',
                unsafe_allow_html=True
            )

            cols_ranking = st.columns(len(top_candidatos))

            for idx, r_item in enumerate(top_candidatos):
                pos = idx + 1
                col_atual = cols_ranking[idx]

                with col_atual:
                    prazo_val = int(r_item["Prazo (Dias Úteis)"]) if pd.notna(r_item["Prazo (Dias Úteis)"]) and int(r_item["Prazo (Dias Úteis)"]) > 0 else 0
                    p_txt = f"{prazo_val} dias úteis" if prazo_val > 0 else "A confirmar"
                    
                    # Verificação de Smart Tags (Regras de Negócio de Desempate e Agilidade)
                    is_mais_rapida = (min_prazo_global is not None and prazo_val == min_prazo_global)
                    entrega_antes_do_primeiro = (pos > 1 and prazo_op1 > 0 and 0 < prazo_val < prazo_op1)

                    # Estilização por posição
                    if pos == 1:
                        card_class = "card-ranking-pos1"
                        badge_pos_html = '<span class="badge-ranking badge-pos1">🏆 1º Lugar</span>'
                        preco_cor = "#047857"
                        if len(top_candidatos) > 1:
                            dif_econ = float(top_candidatos[1]["Valor Frete (R$)"]) - float(r_item["Valor Frete (R$)"])
                            dica_html = f'<div style="font-size:0.75rem;color:#059669;font-weight:600;margin-top:8px;padding-top:8px;border-top:1px dashed #bbf7d0;">Economia de {formatar_moeda(dif_econ)} vs. 2ª opção</div>'
                        else:
                            dica_html = ''
                    elif pos == 2:
                        card_class = "card-ranking-pos2"
                        badge_pos_html = '<span class="badge-ranking badge-pos2">🥈 2ª Opção</span>'
                        preco_cor = "#0284c7"
                        if entrega_antes_do_primeiro:
                            dias_eco = prazo_op1 - prazo_val
                            dica_html = f'<div style="font-size:0.75rem;color:#b45309;font-weight:600;margin-top:8px;padding-top:8px;border-top:1px dashed #fed7aa;">⚡ Entrega {dias_eco} dia(s) antes da 1ª opção</div>'
                        else:
                            dica_html = ''
                    else:
                        card_class = "card-ranking-pos3"
                        badge_pos_html = '<span class="badge-ranking badge-pos3">🥉 3ª Opção</span>'
                        preco_cor = "#1e293b"
                        if entrega_antes_do_primeiro:
                            dias_eco = prazo_op1 - prazo_val
                            dica_html = f'<div style="font-size:0.75rem;color:#b45309;font-weight:600;margin-top:8px;padding-top:8px;border-top:1px dashed #fed7aa;">⚡ Entrega {dias_eco} dia(s) antes da 1ª opção</div>'
                        else:
                            dica_html = ''

                    # Smart Tag "Mais Rápida"
                    smart_tag_html = ""
                    if is_mais_rapida:
                        smart_tag_html = f'<span class="badge-ranking badge-fast">⚡ Mais Rápida ({prazo_val}D)</span>'
                    elif entrega_antes_do_primeiro:
                        smart_tag_html = '<span class="badge-ranking badge-fast">⚡ Mais Rápida</span>'

                    # Logo oficial da transportadora (SVG ou Fallback)
                    logo_html = gerar_badge_logo_html(r_item["Transportadora"])

                    # Tags de abrangência removidas conforme Ticket 5
                    tags_html = ""

                    # Link WhatsApp da opção
                    v_data = cot_info.get('volumes_data', [])
                    if v_data:
                        dim_list = [f"{int(float(v.get('Comp (cm)', 0)))}x{int(float(v.get('Larg (cm)', 0)))}x{int(float(v.get('Alt (cm)', 0)))}" for v in v_data]
                        dimensoes_resumidas = "\\n".join(dim_list)
                    else:
                        dimensoes_resumidas = "N/A"

                    obs_text = f"\\n\\n*Observações:* {cot_info.get('obs')}" if cot_info.get('obs') else ""
                    msg_card = (
                        f"Olá!\\n"
                        f"Por gentileza, peço a validação desta cotação de frete:\\n\\n"
                        f"CNPJ remetente: {cot_info.get('remetente', 'N/A')}\\n"
                        f"CEP remetente: {cot_info.get('origem_cep', 'N/A')}\\n"
                        f"CNPJ destinatário: {cot_info.get('destinatario', 'N/A')}\\n"
                        f"CEP destinatário: {cot_info.get('destino_cep', 'N/A')}\\n"
                        f"Volumes: {cot_info.get('volumes_qtd', 0)}\\n"
                        f"Medidas:\\n"
                        f"{dimensoes_resumidas}\\n"
                        f"Peso: {cot_info.get('peso', 0):.2f}kg\\n"
                        f"Valor da NF: {utils.formatar_moeda(cot_info.get('valor_nf'))}\\n\\n"
                        f"*Estimativa via Tabela :* *{formatar_moeda(r_item['Valor Frete (R$)'])}*\\n\\n"
                        f"Pode confirmar se o valor bate com a tabela que temos com vocês?{obs_text}"
                    )
                    numero_wa = obter_numero_wa(r_item['Transportadora'])
                    link_wa_card = f"https://wa.me/{numero_wa}?text={urllib.parse.quote(msg_card).replace('%5Cn', '%0A')}"

                    card_html = f"""
                    <div class="{card_class}" style="background:#ffffff; border:1px solid #e2e8f0; border-radius:12px; padding:20px; box-shadow:0 1px 3px rgba(0,0,0,0.05); text-align:center; position:relative; overflow:hidden; margin-bottom:16px;">
                      <div style="display:flex; justify-content:center; align-items:center; gap:6px; margin-bottom:16px;">
                        {badge_pos_html} {smart_tag_html}
                      </div>
                      <div style="margin-bottom:16px;">
                        {logo_html}
                      </div>
                      <div style="margin-bottom:20px;">
                        <div style="font-size:0.75rem; font-weight:700; color:#64748b; text-transform:uppercase; letter-spacing:0.04em; margin-bottom:2px;">Custo Estimado</div>
                        <div style="font-size:2rem; font-weight:800; color:#0f172a; line-height:1.2;">
                          {formatar_moeda(r_item['Valor Frete (R$)'])}
                        </div>
                      </div>
                      <div style="background:#f8fafc; border:1px solid #f1f5f9; border-radius:8px; padding:12px; margin-bottom:20px; text-align:left;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                          <span style="font-size:0.8rem; color:#475569; font-weight:600;">Prazo Previsto</span>
                          <span style="font-size:0.85rem; color:#0f172a; font-weight:700;">{p_txt}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                          <span style="font-size:0.8rem; color:#475569; font-weight:600;">Peso Tarifado</span>
                          <span style="font-size:0.85rem; color:#0f172a; font-weight:700;">{r_item.get('Peso Tarifado', f"{cot_info.get('peso_tarifado', 0):.2f} kg")}</span>
                        </div>
                        {dica_html}
                      </div>
                      <a href="{link_wa_card}" target="_blank" style="display:block; background:#10b981; color:#ffffff; font-weight:600; font-size:0.85rem; padding:10px; border-radius:6px; text-decoration:none; transition:background 0.2s;">
                        Enviar Proposta
                      </a>
                    </div>
                    """
                    st.markdown(card_html.replace('\n', ''), unsafe_allow_html=True)


            st.write("")
            # ================= TABELA DE OPÇÕES VÁLIDAS =================
            st.markdown(
                """
                <div style="margin-top:30px; margin-bottom:15px;">
                    <div style="font-size:16px; font-weight:700; color:#1e293b; border-bottom:2px solid #e2e8f0; padding-bottom:8px;">Todas as Opções de Transportadoras</div>
                </div>
                """, unsafe_allow_html=True
            )
        df_t = df_valid.copy()
        df_t["Prazo"] = df_t["Prazo (Dias Úteis)"].apply(
            lambda x: f"{int(x)} dias" if pd.notna(x) and int(x) > 0 else "A confirmar"
        )
        
        # Ensure 'Base Tarifária' or any similar column is removed before display
        columns_to_drop = [c for c in df_t.columns if "base" in c.lower() or "ordem" in c.lower()]
        df_t = df_t.drop(columns=columns_to_drop, errors='ignore')

        def gerar_link_wa(row):
            valor = formatar_moeda(row["Valor Frete (R$)"])
            prazo_val = int(row["Prazo (Dias Úteis)"]) if pd.notna(row["Prazo (Dias Úteis)"]) else 0
            prazo_str = f"{prazo_val} dias úteis" if prazo_val > 0 else "A confirmar"
            tipo_str = row.get("Base Tarifária", "Tabela Contratual")
            v_data = cot_info.get('volumes_data', [])
            if v_data:
                dim_list = [f"{int(float(v.get('Comp (cm)', 0)))}x{int(float(v.get('Larg (cm)', 0)))}x{int(float(v.get('Alt (cm)', 0)))}" for v in v_data]
                dimensoes_resumidas = "\\n".join(dim_list)
            else:
                dimensoes_resumidas = "N/A"

            obs_text = f"\n\n*Observações:* {cot_info.get('obs')}" if cot_info.get('obs') else ""
            msg = (
                f"Olá!\n"
                f"Por gentileza, peço a validação desta cotação de frete:\n\n"
                f"CNPJ remetente: {cot_info.get('remetente', 'N/A')}\n"
                f"CEP remetente: {cot_info.get('origem_cep', 'N/A')}\n"
                f"CNPJ destinatário: {cot_info.get('destinatario', 'N/A')}\n"
                f"CEP destinatário: {cot_info.get('destino_cep', 'N/A')}\n"
                f"Volumes: {cot_info.get('volumes_qtd', 0)}\n"
                f"Medidas:\n"
                f"{dimensoes_resumidas}\n"
                f"Peso: {cot_info.get('peso', 0):.2f}kg\n"
                f"Valor da NF: {utils.formatar_moeda(cot_info.get('valor_nf'))}\n\n"
                f"*Estimativa via Tabela :* *{valor}*\n\n"
                f"Pode confirmar se o valor bate com a tabela que temos com vocês?{obs_text}"
            )
            numero_wa = obter_numero_wa(row['Transportadora'])
            return f"https://wa.me/{numero_wa}?text={urllib.parse.quote(msg).replace('%5Cn', '%0A')}"


        df_t["Ação"] = df_t.apply(gerar_link_wa, axis=1)
        st.dataframe(
            df_t[["Transportadora", "Valor Frete (R$)", "Prazo", "Ação"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Transportadora": st.column_config.TextColumn("Transportadora", width="medium"),
                "Valor Frete (R$)": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f", width="small"),
                "Prazo": st.column_config.TextColumn("Prazo", width="small"),
                "Ação": st.column_config.LinkColumn("WhatsApp", display_text="Enviar Proposta", width="small")
            },
        )

        # Seção de Transportadoras Não Atendidas / Indisponíveis (Tolerância Zero a Falsos Positivos)
        if opcoes_indisponiveis:
            st.write("")
            with st.expander(f"Transportadoras Sem Atendimento ou Fora do Ar ({len(opcoes_indisponiveis)})", expanded=False):
                st.caption(
                    "As opções abaixo foram excluídas do comparativo comercial porque a rota não consta nas tabelas "
                    "contratuais vigentes da Next Cable ou porque a API não retornou resposta operacional."
                )
                for item_un in opcoes_indisponiveis:
                    nome_t = item_un.get("Transportadora", "")
                    tags_t = item_un.get("Tags", [])
                    tags_html = " ".join([
                        f"<span style='background:#f1f5f9;color:#64748b;padding:1px 5px;border-radius:4px;font-size:0.7rem;font-weight:700;border:1px solid #e2e8f0;'>[{t}]</span>"
                        for t in tags_t
                    ])
                    motivo_t = item_un.get("Motivo", item_un.get("Status", "Não atende esta localidade"))
                    eh_api = "api" in str(item_un.get("Base Tarifária", "")).lower() or "conexão" in motivo_t.lower() or "credenciais" in motivo_t.lower() or "fora do ar" in str(item_un.get("Status", "")).lower()
                    status_badge = "⚠️ Fora do ar / Indisponível" if eh_api else "🚫 Não atende esta região"
                    badge_style = "background:#fef3c7;color:#92400e;border:1px solid #fde68a;" if eh_api else "background:#f1f5f9;color:#475569;border:1px solid #cbd5e1;"

                    st.markdown(
                        f"""
                        <div style="background:#ffffff;border:1px solid #e2e8f0;border-left:4px solid #94a3b8;border-radius:6px;padding:8px 12px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center;">
                          <div>
                            <div style="font-weight:700;color:#334155;font-size:0.88rem;">
                              {nome_t} <span style="margin-left:8px;">{tags_html}</span>
                            </div>
                            <div style="color:#64748b;font-size:0.78rem;margin-top:3px;">
                              {motivo_t}
                            </div>
                          </div>
                          <div>
                            <span style="{badge_style}padding:3px 10px;border-radius:12px;font-size:0.72rem;font-weight:700;white-space:nowrap;">
                              {status_badge}
                            </span>
                          </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

        # Finalizar o estado de processamento
        st.session_state.processando_cotacao = False

# ==============================================================================
# MÓDULO 2: RASTREAMENTO DE PEDIDOS & ENTREGAS
# ==============================================================================
elif aba == "Rastreamento de Pedidos":
    st.markdown(
        """
        <div style="margin-bottom: 20px;">
            <div style="font-size:1.5rem;font-weight:800;color:#0f172a;margin-bottom:4px;letter-spacing:-0.03em;">Gestão e Rastreamento de Entregas</div>
            <div style="font-size:0.82rem;color:#64748b;">Carregue, gerencie e atualize o status de todas as cargas expedidas. O sistema consulta as transportadoras em paralelo.</div>
        </div>
        """, unsafe_allow_html=True
    )

    sub_aba = st.radio("Modo de Rastreamento", ["Painel de Entregas em Lote", "Rastreamento Individual"], horizontal=True, label_visibility="collapsed")

    if sub_aba == "Painel de Entregas em Lote":

        if "df_entregas" not in st.session_state:
            try:
                db_entregas = db_historico.get_all_entregas()
                if db_entregas:
                    import json
                    registros = []
                    for e in db_entregas:
                        try:
                            r = json.loads(e.get("dados_json", "{}"))
                            r["Nota Fiscal"] = e.get("nf", "")
                            r["Status"] = e.get("status", "")
                            registros.append(r)
                        except Exception:
                            pass
                    st.session_state.df_entregas = pd.DataFrame(registros)
                else:
                    st.session_state.df_entregas = pd.DataFrame(columns=[
                        "CNPJ", "Nota Fiscal", "Status", "Previsão de Entrega", "Data de Entrega",
                        "Última Ocorrência", "Data Ocorrência", "Destino", "Valor Frete"
                    ])
            except Exception:
                st.session_state.df_entregas = pd.DataFrame(columns=[
                    "CNPJ", "Nota Fiscal", "Status", "Previsão de Entrega", "Data de Entrega",
                    "Última Ocorrência", "Data Ocorrência", "Destino", "Valor Frete"
                ])

        if st.session_state.df_entregas.empty:
            st.session_state.df_entregas = pd.DataFrame([
                {"CNPJ": "26434839000121", "Nota Fiscal": "10025", "Status": "Aguardando Consulta", "Previsão de Entrega": "", "Data de Entrega": "", "Última Ocorrência": "", "Data Ocorrência": "", "Destino": "São Paulo/SP", "Valor Frete": ""},
                {"CNPJ": "26434839000121", "Nota Fiscal": "10026", "Status": "Aguardando Consulta", "Previsão de Entrega": "", "Data de Entrega": "", "Última Ocorrência": "", "Data Ocorrência": "", "Destino": "Curitiba/PR", "Valor Frete": ""},
            ])

        col_up1, col_up2 = st.columns([2.5, 1])
        with col_up2:
            arq_up = st.file_uploader("Subir outra planilha de entregas", type=["xlsx", "xls", "csv"], key="up_entregas")
            if arq_up is not None:
                try:
                    df_novo = pd.read_csv(arq_up) if arq_up.name.endswith(".csv") else pd.read_excel(arq_up)
                    st.session_state.df_entregas = df_novo
                    st.success("Planilha carregada!")
                except Exception as e:
                    st.error(f"Erro: {e}")

        df_atual = st.session_state.df_entregas
        if not df_atual.empty and "Status" in df_atual.columns:
            total_nfs = len(df_atual)
            status_series = df_atual["Status"].astype(str).str.lower()
            n_entregue = status_series.str.contains("entregue").sum()
            n_transito = (status_series.str.contains("trânsito") | status_series.str.contains("transito") | status_series.str.contains("saiu")).sum()
            n_ocorr = (status_series.str.contains("ocorrência") | status_series.str.contains("retido") | status_series.str.contains("erro")).sum()

            k1, k2, k3, k4 = st.columns(4)
            with k1:
                st.markdown(f"""<div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:15px; text-align:center;"><div style="font-size:12px; font-weight:600; color:#64748b; text-transform:uppercase;">Total de Entregas</div><div style="font-size:24px; font-weight:700; color:#0f172a; margin-top:5px;">{total_nfs}</div></div>""", unsafe_allow_html=True)
            with k2:
                st.markdown(f"""<div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:15px; text-align:center;"><div style="font-size:12px; font-weight:600; color:#64748b; text-transform:uppercase;">Entregues</div><div style="font-size:24px; font-weight:700; color:#10b981; margin-top:5px;">{n_entregue}</div></div>""", unsafe_allow_html=True)
            with k3:
                st.markdown(f"""<div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:15px; text-align:center;"><div style="font-size:12px; font-weight:600; color:#64748b; text-transform:uppercase;">Em Trânsito</div><div style="font-size:24px; font-weight:700; color:#000033; margin-top:5px;">{n_transito}</div></div>""", unsafe_allow_html=True)
            with k4:
                st.markdown(f"""<div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:15px; text-align:center;"><div style="font-size:12px; font-weight:600; color:#64748b; text-transform:uppercase;">Ocorrências / Atrasos</div><div style="font-size:24px; font-weight:700; color:#ef4444; margin-top:5px;">{n_ocorr}</div></div>""", unsafe_allow_html=True)
            st.write("")

        df_entregas_editado = st.data_editor(
            st.session_state.df_entregas,
            num_rows="dynamic",
            width="stretch",
            hide_index=True,
            column_config={
                "CNPJ": st.column_config.TextColumn("CNPJ Remetente"),
                "Nota Fiscal": st.column_config.TextColumn("Nº NF", required=True),
                "Status": st.column_config.TextColumn("Status"),
                "Previsão de Entrega": st.column_config.TextColumn("Previsão"),
                "Data de Entrega": st.column_config.TextColumn("Data Entrega"),
                "Última Ocorrência": st.column_config.TextColumn("Última Ocorrência"),
                "Data Ocorrência": st.column_config.TextColumn("Data Ocorrência"),
                "Destino": st.column_config.TextColumn("Destino"),
                "Valor Frete": st.column_config.TextColumn("Valor Frete"),
            }
        )
        st.session_state.df_entregas = df_entregas_editado

        st.write("")
        b1, b2, b3 = st.columns([1.5, 1, 1])
        with b1:
            btn_atualizar_lote = st.button("Atualizar Status das Entregas", use_container_width=True, type="primary")
        with b2:
            if st.button("Salvar no Banco", use_container_width=True):
                try:
                    import json
                    # Obtem os NFs que foram salvos antes para excluir os removidos (opcional, por simplicidade faremos apenas upsert)
                    for _, row in df_entregas_editado.iterrows():
                        nf = str(row.get("Nota Fiscal", ""))
                        if not nf or nf == "nan":
                            continue
                        cnpj = str(row.get("CNPJ", ""))
                        status = str(row.get("Status", ""))
                        cidade = str(row.get("Destino", ""))
                        
                        # Converte a row pra dict e garante q não tem NaN
                        row_dict = {k: ("" if pd.isna(v) else v) for k, v in row.to_dict().items()}
                        dados_json = json.dumps(row_dict, ensure_ascii=False)
                        
                        db_historico.upsert_entrega(nf, "", cnpj, cidade, "", "", status, dados_json)
                    st.success(f"Entregas salvas com sucesso no banco de dados!")
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
        with b3:
            excel_entregas_bytes = gerar_excel_entregas(df_entregas_editado)
            st.download_button(
                "Exportar Planilha Atualizada",
                data=excel_entregas_bytes,
                file_name=f"entregas_atualizadas_{datetime.now():%Y%m%d_%H%M}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        if btn_atualizar_lote:
            if df_entregas_editado.empty:
                st.warning("Nenhuma nota fiscal para atualizar.")
            else:
                with st.spinner("Consultando status de todas as remessas em paralelo..."):
                    df_proc = df_entregas_editado.copy()

                    def rastrear_linha(idx, r):
                        nf = str(r.get("Nota Fiscal", "")).strip()
                        cnpj = str(r.get("CNPJ", "")).strip() or "26434839000121"
                        if not nf:
                            return idx, None
                        res_track = rastrear_braspress(nf, cnpj)
                        return idx, res_track

                    with ThreadPoolExecutor(max_workers=8) as executor:
                        futs = [executor.submit(rastrear_linha, i, r) for i, r in df_proc.iterrows()]
                        for f in as_completed(futs):
                            i_idx, res = f.result()
                            if res:
                                df_proc.at[i_idx, "Status"] = res["status"]
                                if res["previsao"]:
                                    df_proc.at[i_idx, "Previsão de Entrega"] = res["previsao"]
                                if res["data_entrega"]:
                                    df_proc.at[i_idx, "Data de Entrega"] = res["data_entrega"]
                                if res["ultima_ocorrencia"]:
                                    df_proc.at[i_idx, "Última Ocorrência"] = res["ultima_ocorrencia"]
                                if res["data_ocorrencia"]:
                                    df_proc.at[i_idx, "Data Ocorrência"] = res["data_ocorrencia"]
                                if res["destino"] and not df_proc.at[i_idx, "Destino"]:
                                    df_proc.at[i_idx, "Destino"] = res["destino"]
                                if res["valor_frete"]:
                                    df_proc.at[i_idx, "Valor Frete"] = formatar_moeda(res["valor_frete"])

                    st.session_state.df_entregas = df_proc
                    try:
                        import json
                        for _, row in df_proc.iterrows():
                            nf = str(row.get("Nota Fiscal", ""))
                            if not nf or nf == "nan":
                                continue
                            cnpj = str(row.get("CNPJ", ""))
                            status = str(row.get("Status", ""))
                            cidade = str(row.get("Destino", ""))
                            
                            row_dict = {k: ("" if pd.isna(v) else v) for k, v in row.to_dict().items()}
                            dados_json = json.dumps(row_dict, ensure_ascii=False)
                            db_historico.upsert_entrega(nf, "", cnpj, cidade, "", "", status, dados_json)
                    except Exception:
                        pass
                    st.success("Atualização em lote concluída e salva no banco de dados!")
                    st.rerun()

    elif sub_aba == "Rastreamento Individual":
        st.markdown(
            """
            <div style="margin-bottom: 20px;">
                <span style="font-size: 14px; color: #64748b;">Consulta individual detalhada de carga com histórico de ocorrências.</span>
            </div>
            """, unsafe_allow_html=True
        )
        c_ri1, c_ri2 = st.columns([1, 2], gap="medium")
        with c_ri1:
            with st.container(border=True):
                nf_ind = st.text_input("Número da Nota Fiscal (NF)")
                cnpj_ind = st.text_input("CNPJ Remetente", value="26434839000121")
                btn_rastrear_ind = st.button("Rastrear NF Agora", use_container_width=True, type="primary")

        with c_ri2:
            if btn_rastrear_ind and nf_ind:
                with st.spinner("Consultando sistema de tracking..."):
                    res_ind = rastrear_braspress(nf_ind, cnpj_ind)
                    with st.container(border=True):
                        if res_ind["sucesso"]:
                            st.success(f"Status Atual da NF {nf_ind}: {res_ind['status']}")
                            col_info1, col_info2 = st.columns(2)
                            with col_info1:
                                if res_ind["previsao"]:
                                    st.write(f"**Previsão de Entrega:** {res_ind['previsao']}")
                                if res_ind["data_entrega"]:
                                    st.write(f"**Entregue em:** {res_ind['data_entrega']}")
                                if res_ind["destino"]:
                                    st.write(f"**Destino:** {res_ind['destino']}")
                            with col_info2:
                                if res_ind["ultima_ocorrencia"]:
                                    st.write(f"**Última Ocorrência:** {res_ind['ultima_ocorrencia']}")
                                if res_ind["data_ocorrencia"]:
                                    st.write(f"**Data do Evento:** {res_ind['data_ocorrencia']}")

                            st.markdown("---")
                            st.markdown("**Histórico de Ocorrências:**")
                            eventos = res_ind.get("eventos", [])
                            if eventos:
                                for e in reversed(eventos):
                                    d_txt = e.get("data", e.get("dataHora", "Data N/D"))
                                    desc_txt = e.get("descricao", e.get("status", ""))
                                    st.markdown(
                                        f'<div style="border-left:3px solid #10b981;padding-left:12px;margin-bottom:10px;">'
                                        f'<div style="font-weight:700;color:#000033;font-size:0.85rem;">{d_txt}</div>'
                                        f'<div style="color:#334155;font-size:0.82rem;">{desc_txt}</div>'
                                        f'</div>',
                                        unsafe_allow_html=True,
                                    )
                            else:
                                st.info("Sem eventos detalhados cadastrados até o momento.")
                        else:
                            st.error(f"{res_ind['status']}")
                            st.caption("Verifique o número da nota fiscal e o CNPJ do remetente.")


# ==============================================================================
# MÓDULO 4: HISTÓRICO DE COTAÇÕES
# ==============================================================================
elif aba == "Histórico de Cotações":
    st.markdown(
        """
        <div style="margin-bottom: 20px;">
            <div style="font-size:1.5rem;font-weight:800;color:#0f172a;margin-bottom:4px;letter-spacing:-0.03em;">Histórico de Cotações</div>
            <div style="font-size:0.82rem;color:#64748b;">Acompanhe cotações pendentes. Toda cotação tem um prazo de 1 semana (7 dias) para ser aprovada ou editada, após isso ela expira.</div>
        </div>
        """, unsafe_allow_html=True
    )

    import db_historico
    from datetime import datetime
    import pandas as pd
    import json

    @st.dialog("Aprovar Cotação")
    def aprovar_cotacao_dialog(cot_id, dados):
        st.write(f"Você está aprovando a cotação **#{cot_id}**")
        resultados = dados.get("resultados", [])
        opcoes = []
        if resultados:
            for r in resultados:
                if r.get("Atendida") and r.get("Valor Frete (R$)"):
                    val = r.get("Valor Frete (R$)", 0)
                    transp = r.get("Transportadora", "N/D")
                    opcoes.append(f"{transp} - R$ {val:,.2f}")
        else:
            melhor_transp = dados.get("melhor_transportadora")
            melhor_valor = dados.get("melhor_valor")
            if melhor_transp and melhor_valor is not None:
                opcoes.append(f"{melhor_transp} - R$ {float(melhor_valor):,.2f}")
        
        if not opcoes:
            st.warning("Nenhuma opção de frete válida encontrada no registro.")
            if st.button("Cancelar", key=f"cancel_aprov_{cot_id}"):
                st.rerun()
            return

        selecionada = st.selectbox("Selecione a transportadora vencedora:", opcoes, key=f"sel_transp_{cot_id}")
        
        if st.button("Confirmar Aprovação", type="primary", key=f"btn_confirm_aprov_{cot_id}"):
            transp_nome = selecionada.split(" - R$")[0]
            try:
                # Remove possible formatting chars like dots and fix commas
                valor_str = selecionada.split(" - R$ ")[1].replace(".", "").replace(",", ".")
                valor = float(valor_str)
            except:
                valor = 0.0
            
            u = st.session_state.get("user", {})
            db_historico.aprovar_cotacao(cot_id, transp_nome, valor, owner_user_id=u.get("id"), role=u.get("role", "VENDEDOR"))
            st.rerun()

    # Processar ações de exclusão e retomada
    if "acao_excluir" in st.session_state:
        cot_id = st.session_state.acao_excluir
        u = st.session_state.get("user", {})
        db_historico.excluir_cotacao(cot_id, owner_user_id=u.get("id"), role=u.get("role", "VENDEDOR"))
        del st.session_state.acao_excluir
        st.rerun()

    if "acao_retomar" in st.session_state:
        cot_id = st.session_state.acao_retomar
        # Precisamos buscar os dados json originais
        u = st.session_state.get("user", {})
        item = db_historico.obter_cotacao_por_id(cot_id, owner_user_id=u.get("id"), role=u.get("role", "VENDEDOR"))
        if item and item.get("dados_json"):
            import json
            dados = json.loads(item["dados_json"])
            st.session_state.cnpj_input = dados.get("cnpj_cliente", dados.get("doc_destinatario", ""))
            st.session_state.cep_d = dados.get("cep_destino", "")
            valor_nf = item.get('valor_nf')
            st.session_state.valor_nf_input = str(valor_nf) if valor_nf is not None else ""
            
            # Restaurar volumes
            restored_volumes = dados.get("volumes_data", [])
            st.session_state.volumes_base = pd.DataFrame(restored_volumes) if restored_volumes else pd.DataFrame([{"Qtd": 0, "Alt (cm)": 0.0, "Larg (cm)": 0.0, "Comp (cm)": 0.0, "Peso Total (kg)": 0.0}])
            st.session_state.volumes_data = restored_volumes
            if "tabela_volumes_fixa" in st.session_state:
                del st.session_state["tabela_volumes_fixa"]
                
            st.session_state.active_module = "Nova Cotação"
        del st.session_state.acao_retomar
        st.rerun()

    # Forçar CSS nos botões via nth-of-type (já que :contains não é suportado pelo CSS padrão)
    # Forçar CSS nos botões via nth-child (já que :contains não é suportado e Streamlit usa stColumn)
    st.markdown('''<style>
/* Botão Aprovar: Verde (Fica na 2ª coluna da linha de ações) */
div[data-testid="stHorizontalBlock"] > div:nth-child(2) button,
div[data-testid="stColumn"]:nth-child(2) button,
div[data-testid="column"]:nth-child(2) button {
    background-color: #16a34a !important;
    border-color: #16a34a !important;
}
div[data-testid="stHorizontalBlock"] > div:nth-child(2) button p,
div[data-testid="stColumn"]:nth-child(2) button p,
div[data-testid="column"]:nth-child(2) button p {
    color: #ffffff !important;
    font-weight: 600 !important;
}

/* Botão Excluir: Vermelho (Fica na 2ª sub-coluna da 4ª coluna da linha de ações) */
div[data-testid="stHorizontalBlock"] > div:nth-child(4) div[data-testid="stHorizontalBlock"] > div:nth-child(2) button,
div[data-testid="stColumn"]:nth-child(4) div[data-testid="stColumn"]:nth-child(2) button,
div[data-testid="column"]:nth-child(4) div[data-testid="column"]:nth-child(2) button {
    background-color: #dc2626 !important;
    border-color: #dc2626 !important;
}
div[data-testid="stHorizontalBlock"] > div:nth-child(4) div[data-testid="stHorizontalBlock"] > div:nth-child(2) button p,
div[data-testid="stColumn"]:nth-child(4) div[data-testid="stColumn"]:nth-child(2) button p,
div[data-testid="column"]:nth-child(4) div[data-testid="column"]:nth-child(2) button p {
    color: #ffffff !important;
    font-weight: 600 !important;
}

/* Modal de Exclusão - Botão Cancelar (2ª Coluna do Modal) */
div[role="dialog"] div[data-testid="stHorizontalBlock"] > div:nth-child(2) button,
div[role="dialog"] div[data-testid="stColumn"]:nth-child(2) button,
div[role="dialog"] div[data-testid="column"]:nth-child(2) button,
div[data-testid="stDialog"] div[data-testid="stHorizontalBlock"] > div:nth-child(2) button,
div[data-testid="stDialog"] div[data-testid="stColumn"]:nth-child(2) button,
div[data-testid="stDialog"] div[data-testid="column"]:nth-child(2) button {
    background-color: #f1f5f9 !important; 
    color: #475569 !important; 
    border: 1px solid #cbd5e1 !important; 
}
div[role="dialog"] div[data-testid="stHorizontalBlock"] > div:nth-child(2) button p,
div[role="dialog"] div[data-testid="stColumn"]:nth-child(2) button p,
div[role="dialog"] div[data-testid="column"]:nth-child(2) button p,
div[data-testid="stDialog"] div[data-testid="stHorizontalBlock"] > div:nth-child(2) button p,
div[data-testid="stDialog"] div[data-testid="stColumn"]:nth-child(2) button p,
div[data-testid="stDialog"] div[data-testid="column"]:nth-child(2) button p {
    color: #475569 !important;
}

/* Modal de Exclusão - Botão Sim, Excluir (1ª Coluna do Modal) */
div[role="dialog"] div[data-testid="stHorizontalBlock"] > div:nth-child(1) button,
div[role="dialog"] div[data-testid="stColumn"]:nth-child(1) button,
div[role="dialog"] div[data-testid="column"]:nth-child(1) button,
div[data-testid="stDialog"] div[data-testid="stHorizontalBlock"] > div:nth-child(1) button,
div[data-testid="stDialog"] div[data-testid="stColumn"]:nth-child(1) button,
div[data-testid="stDialog"] div[data-testid="column"]:nth-child(1) button {
    background-color: #dc2626 !important; 
    color: #ffffff !important; 
    border-color: #dc2626 !important; 
}
div[role="dialog"] div[data-testid="stHorizontalBlock"] > div:nth-child(1) button p,
div[role="dialog"] div[data-testid="stColumn"]:nth-child(1) button p,
div[role="dialog"] div[data-testid="column"]:nth-child(1) button p,
div[data-testid="stDialog"] div[data-testid="stHorizontalBlock"] > div:nth-child(1) button p,
div[data-testid="stDialog"] div[data-testid="stColumn"]:nth-child(1) button p,
div[data-testid="stDialog"] div[data-testid="column"]:nth-child(1) button p {
    color: #ffffff !important;
}
</style>''', unsafe_allow_html=True)

    # Filtros
    c1, c2, c3 = st.columns([2.5, 1, 1])
    with c1:
        busca = st.text_input("Buscar (ID, CNPJ, Cliente, Cidade, Transportadora)", placeholder="Digite para pesquisar...", key="hist_busca")
    with c2:
        status_filtro = st.selectbox("Status", ["Todas", "Pendente", "Aprovada", "Expirada", "Excluídas"], key="hist_status")
    with c3:
        periodo_filtro = st.selectbox("Período", ["Todos", "Hoje", "Últimos 7 dias", "Últimos 30 dias", "Últimos 90 dias"], key="hist_periodo")

    periodo_val = periodo_filtro if periodo_filtro != "Todos" else None

    # Paginação
    POR_PAGINA = 20
    if "hist_pagina" not in st.session_state:
        st.session_state.hist_pagina = 0
    
    u = st.session_state.get("user", {})
    total_cotacoes = db_historico.contar_cotacoes(status=status_filtro, search=busca or None, periodo=periodo_val, owner_user_id=u.get("id"), role=u.get("role", "VENDEDOR"))
    total_paginas = max(1, (total_cotacoes + POR_PAGINA - 1) // POR_PAGINA)
    
    # Reset page if filters changed
    if st.session_state.hist_pagina >= total_paginas:
        st.session_state.hist_pagina = 0

    offset = st.session_state.hist_pagina * POR_PAGINA
    historico_valido = db_historico.obter_cotacoes(
        status=status_filtro, search=busca or None, limit=POR_PAGINA, offset=offset, periodo=periodo_val, owner_user_id=u.get("id"), role=u.get("role", "VENDEDOR")
    )

    if not historico_valido:
        st.info("Nenhuma cotação encontrada com os filtros atuais.")
    else:
        # CSS para cores dos botões — duplo fallback (seletor :has + posicional)
        st.markdown('''<style>
        div.stButton > button:has(p:contains("Aprovar")) { background-color: #16a34a !important; color: #ffffff !important; border: none !important; }
        div.stButton > button:has(p:contains("Excluir")) { background-color: #dc2626 !important; color: #ffffff !important; border: none !important; }
        </style>''', unsafe_allow_html=True)

        # Dialog: Visualizar Cotação
        @st.dialog("Detalhes da Cotação", width="large")
        def visualizar_cotacao_dialog(cot_id, item_data, payload_data):
            st.markdown(f"### #{cot_id}")
            
            _razao = payload_data.get('razao_social', payload_data.get('nome_cliente', item_data.get('nome_cliente', '')))
            _cnpj = item_data.get('cnpj_cliente', '')
            if _razao:
                st.markdown(f"**Cliente:** {_razao}")
            if _cnpj:
                st.markdown(f"**CNPJ:** {_cnpj}")
            
            # Endereço
            _parts = [p for p in [
                payload_data.get('logradouro', ''),
                payload_data.get('numero', ''),
            ] if p]
            _end = ", ".join(_parts) if _parts else ""
            _bairro = payload_data.get('bairro', '')
            _cidade = payload_data.get('cidade', item_data.get('cidade_uf_destino', '').split('/')[0])
            _uf = payload_data.get('uf', '')
            _cep = item_data.get('cep_destino', '')
            
            dest_parts = [p for p in [_end, _bairro] if p]
            dest_str = " — ".join(dest_parts)
            if _cidade:
                dest_str += f" — {_cidade}/{_uf}" if dest_str else f"{_cidade}/{_uf}"
            if _cep:
                dest_str += f" | CEP: {_cep}"
            if dest_str:
                st.markdown(f"**Destino:** {dest_str}")
            
            c1v, c2v, c3v = st.columns(3)
            with c1v:
                st.metric("Valor NF", utils.formatar_moeda(item_data.get('valor_nf')))
            with c2v:
                st.metric("Peso Real", f"{item_data.get('peso_real', 0):.2f} kg")
            with c3v:
                st.metric("Peso Tarifado", f"{item_data.get('peso_tarifado', 0):.2f} kg")
            
            # Volumes
            vols = payload_data.get('volumes_data', [])
            if vols:
                st.markdown("**Volumes:**")
                st.dataframe(pd.DataFrame(vols), use_container_width=True, hide_index=True)
            
            # Resultados das transportadoras
            resultados = payload_data.get('resultados', [])
            if resultados:
                st.markdown("**Transportadoras Cotadas:**")
                df_res = pd.DataFrame(resultados)
                cols_show = [c for c in ["Transportadora", "Valor Frete (R$)", "Prazo (Dias Úteis)", "Atendida", "Motivo"] if c in df_res.columns]
                if cols_show:
                    df_res_display = df_res[cols_show].copy()
                    df_res_display = df_res_display.sort_values("Valor Frete (R$)", na_position="last")
                    st.dataframe(df_res_display, use_container_width=True, hide_index=True)
            
            # Aprovação
            status_item = item_data.get('status', '').upper()
            if status_item == "APROVADA":
                t_aprov = item_data.get('transportadora_aprovada', 'N/D')
                v_aprov = item_data.get('valor_frete_aprovado', 0)
                d_aprov = item_data.get('approved_at', '')
                try:
                    d_aprov_fmt = datetime.fromisoformat(d_aprov).strftime("%d/%m/%Y %H:%M")
                except Exception:
                    d_aprov_fmt = d_aprov
                st.success(f"**Frete aprovado:** {t_aprov} — R$ {v_aprov:,.2f} | Aprovado em: {d_aprov_fmt}")
            
            if st.button("Fechar", key=f"fechar_viz_{cot_id}", use_container_width=True):
                st.rerun()

        # Dialog: Confirmar Exclusão
        @st.dialog("Confirmar Exclusão")
        def confirmar_exclusao_dialog(cot_id):
            st.warning(f"Tem certeza que deseja excluir a cotação **#{cot_id}**?")
            st.caption("A cotação será marcada como excluída e não aparecerá mais na lista principal.")
            col_sim, col_nao = st.columns(2)
            with col_sim:
                if st.button("Sim, Excluir", key=f"confirm_del_{cot_id}", type="primary", use_container_width=True):
                    db_historico.excluir_cotacao(cot_id, owner_user_id=u.get("id"), role=u.get("role", "VENDEDOR"))
                    st.rerun()
            with col_nao:
                if st.button("Cancelar", key=f"cancel_del_{cot_id}", use_container_width=True):
                    st.rerun()

        for i, item in enumerate(historico_valido):
            with st.container(border=True):
                status = item.get('status', 'PENDENTE').upper()
                
                if status == "APROVADA":
                    cor_badge = "background:#dcfce7; color:#166534; border:1px solid #bbf7d0;"
                elif status == "EXPIRADA":
                    cor_badge = "background:#fee2e2; color:#991b1b; border:1px solid #fecaca;"
                elif status == "EXCLUÍDA":
                    cor_badge = "background:#f1f5f9; color:#475569; border:1px solid #e2e8f0;"
                else: # PENDENTE
                    cor_badge = "background:#fef9c3; color:#854d0e; border:1px solid #fef08a;"
                
                # Parse the ISO datetime for display
                try:
                    dt_obj = datetime.fromisoformat(item.get('created_at', ''))
                    dh_str = dt_obj.strftime("%d/%m/%Y %H:%M")
                except Exception:
                    dh_str = item.get('created_at', 'N/A')

                import json
                try:
                    payload = json.loads(item.get("dados_json", "{}"))
                except Exception:
                    payload = {}
                    
                doc_cli = item.get('cnpj_cliente', 'N/A')
                valor_nf = item.get('valor_nf', 0)
                
                # Valores com fallback para compatibilidade com registros antigos
                razao_render = payload.get('razao_social', payload.get('nome_cliente', item.get('nome_cliente', '')))
                logradouro_render = payload.get('logradouro', payload.get('endereco', ''))
                numero_render = payload.get('numero', '')
                bairro_render = payload.get('bairro', '')
                cidade_render = payload.get('cidade', payload.get('cidade_dest', ''))
                uf_render = payload.get('uf', payload.get('uf_dest', ''))
                
                # Fallback para cidade_uf_destino se campos individuais vazios
                if not cidade_render and item.get('cidade_uf_destino'):
                    parts = item.get('cidade_uf_destino', '').split('/')
                    cidade_render = parts[0] if len(parts) > 0 else ''
                    uf_render = parts[1] if len(parts) > 1 else uf_render
                
                # Montar endereço limpo SEM separadores vazios
                end_parts = []
                if logradouro_render:
                    end_str = logradouro_render
                    if numero_render:
                        end_str += f", {numero_render}"
                    end_parts.append(end_str)
                if bairro_render:
                    end_parts.append(bairro_render)
                
                destino_str = " — ".join(end_parts) if end_parts else ""
                if cidade_render:
                    loc_str = f"{cidade_render}/{uf_render}" if uf_render else cidade_render
                    destino_str = f"{destino_str} — {loc_str}" if destino_str else loc_str
                
                # Nome ou fallback
                nome_display = razao_render if razao_render else "Empresa não informada"
                if nome_display == "Empresa não informada" and doc_cli and len(doc_cli) == 14:
                    try:
                        info_emp = buscar_empresa_cnpj(doc_cli)
                        if info_emp and info_emp.get("ok"):
                            nome_display = info_emp.get("razao", "Empresa não informada")
                    except Exception:
                        pass
                
                # Alerta de expiração
                alerta_expiracao_html = ""
                if status == "PENDENTE":
                    try:
                        exp_dt = datetime.fromisoformat(item.get('expires_at', ''))
                        dias_restantes = (exp_dt - datetime.now()).days
                        if dias_restantes <= 0:
                            alerta_expiracao_html = '<span style="background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;margin-left:8px;">Expira hoje</span>'
                        elif dias_restantes <= 2:
                            alerta_expiracao_html = f'<span style="background:#fef3c7;color:#92400e;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;margin-left:8px;">Expira em {dias_restantes} dia{"s" if dias_restantes > 1 else ""}</span>'
                    except Exception:
                        pass
                
                # Dados de aprovação
                aprovacao_html = ""
                if status == "APROVADA":
                    t_aprov = item.get('transportadora_aprovada', '')
                    v_aprov = item.get('valor_frete_aprovado', 0)
                    if t_aprov:
                        try:
                            d_aprov = datetime.fromisoformat(item.get('approved_at', '')).strftime("%d/%m/%Y %H:%M")
                        except Exception:
                            d_aprov = ""
                        aprovacao_html = f"""
                        <div style="background:#dcfce7; border:1px solid #bbf7d0; border-radius:6px; padding:8px 12px; margin-top:6px; font-size:13px;">
                            <span style="color:#166534; font-weight:700;">Frete aprovado:</span> 
                            <span style="color:#15803d; font-weight:600;">{t_aprov} — {utils.formatar_moeda(v_aprov)}</span>
                            {f'<span style="color:#166534; font-size:12px; margin-left:8px;">| {d_aprov}</span>' if d_aprov else ''}
                        </div>"""
                
                st.html(
                    f"""
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px;">
                        <div style="flex:1;">
                            <div style="font-size:12px; color:#64748b; font-weight:600;">#{item.get('id', '')} &nbsp;|&nbsp; {dh_str} {alerta_expiracao_html}</div>
                            <div translate='no' class='notranslate' style='font-size:14px; color:#0f172a; font-weight:600; margin-top:5px;'>{nome_display}</div>
                            <div style='font-size:13px; color:#475569; margin-top:2px;'>CNPJ: {doc_cli}</div>
                            <div style='font-size:13px; color:#475569; margin-top:2px;'>Destino: {destino_str}  |  Valor NF: {utils.formatar_moeda(valor_nf)}</div>
                            {aprovacao_html}
                        </div>
                        <div>
                            <span style="{cor_badge} padding:4px 10px; border-radius:12px; font-size:12px; font-weight:700;">{status}</span>
                        </div>
                    </div>
                    """
                )
                
                # Retrieve JSON payload to display the best offer if available
                melhor_transp = payload.get("melhor_transportadora", "N/D")
                melhor_valor = payload.get("melhor_valor", 0)
                if melhor_transp != "N/D" and status != "APROVADA":
                    st.html(f"""
                    <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; padding:10px; margin-bottom:10px; font-size:13px;">
                        <span style="color:#64748b;">Melhor Oferta Registrada:</span> <span style="font-weight:700; color:#0f172a;">{melhor_transp}</span> &nbsp;&mdash;&nbsp; <span style="font-weight:700; color:#10b981;">{utils.formatar_moeda(melhor_valor)}</span>
                    </div>
                    """)

                if status != "EXCLUÍDA":
                    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
                    with c1:
                        if st.button("Visualizar", key=f"viz_idx_{i}", use_container_width=True):
                            visualizar_cotacao_dialog(item["id"], item, payload)
                    with c2:
                        if status == "PENDENTE":
                            if st.button("Aprovar", key=f"aprovar_idx_{i}", use_container_width=True):
                                aprovar_cotacao_dialog(item["id"], payload)
                    with c3:
                        btn_label = "Retomar" if status in ("PENDENTE", "APROVADA") else "Refazer Cotação"
                        if st.button(btn_label, key=f"retomar_idx_{i}", use_container_width=True):
                            st.session_state.acao_retomar = item["id"]
                            st.rerun()
                    with c4:
                        col4a, col4b = st.columns(2)
                        with col4a:
                            if st.button("Duplicar", key=f"dup_idx_{i}", use_container_width=True):
                                novo_id = db_historico.duplicar_cotacao(item["id"], new_owner_user_id=u.get("id"), role=u.get("role", "VENDEDOR"))
                                if novo_id:
                                    st.toast(f"Cotação duplicada: #{novo_id}")
                                    st.rerun()
                        with col4b:
                            if st.button("Excluir", key=f"excluir_idx_{i}", use_container_width=True):
                                confirmar_exclusao_dialog(item["id"])

        # Paginação — controles
        if total_paginas > 1:
            st.markdown(f"<div style='text-align:center; font-size:13px; color:#64748b; margin:10px 0 5px 0;'>Página {st.session_state.hist_pagina + 1} de {total_paginas} — {total_cotacoes} cotações</div>", unsafe_allow_html=True)
            cp, cn = st.columns(2)
            with cp:
                if st.button("← Anterior", disabled=st.session_state.hist_pagina == 0, use_container_width=True, key="pag_ant"):
                    st.session_state.hist_pagina -= 1
                    st.rerun()
            with cn:
                if st.button("Próxima →", disabled=st.session_state.hist_pagina >= total_paginas - 1, use_container_width=True, key="pag_prox"):
                    st.session_state.hist_pagina += 1
                    st.rerun()


elif aba == "Painel Admin":
    st.markdown("<div style='font-size:1.5rem;font-weight:800;color:#0f172a;margin-bottom:4px;letter-spacing:-0.03em;'>Painel Administrativo</div>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:0.82rem;color:#64748b;margin-bottom:20px;'>Gerenciamento de usuários e acessos.</div>", unsafe_allow_html=True)
    @st.dialog("Excluir Usuário")
    def excluir_usuario_dialog(u_id, u_nome, u_email):
        st.warning(f"Tem certeza que deseja excluir permanentemente o usuário **{u_nome}** ({u_email})?")
        st.error("Atenção: Esta ação é irreversível. Caso possua histórico, o usuário será apenas inativado.")
        confirm = st.text_input("Para confirmar, digite EXCLUIR", key=f"confirm_excluir_{u_id}")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Sim, Excluir", type="primary", use_container_width=True):
                if confirm.strip() == "EXCLUIR":
                    sucesso = db_historico.excluir_usuario(u_id)
                    if sucesso:
                        st.success("Usuário excluído/inativado com sucesso!")
                        st.rerun()
                else:
                    st.error("Confirmação incorreta. Digite EXCLUIR.")
        with col2:
            if st.button("Cancelar", use_container_width=True):
                st.rerun()

    tab1, tab2 = st.tabs(["Gerenciar Usuários", "Novo Usuário"])
    
    with tab1:
        usuarios = db_historico.get_all_users()
        if usuarios:
            for u in usuarios:
                with st.expander(f"{u['nome']} ({u['email']}) - {u['role']} - {u['status']}"):
                    st.write(f"**ID:** {u['id']}")
                    st.write(f"**Criado em:** {u['created_at']}")
                    
                    c1, c2, c3 = st.columns([1, 1, 1])
                    with c1:
                        novo_status = st.selectbox("Status", ["ATIVO", "BLOQUEADO"], index=0 if u['status'] == "ATIVO" else 1, key=f"status_{u['id']}")
                        if st.button("Atualizar Status", key=f"btn_status_{u['id']}"):
                            db_historico.update_user_status(u['id'], novo_status)
                            st.success("Status atualizado!")
                            st.rerun()
                    
                    with c2:
                        nova_senha = st.text_input("Nova Senha", type="password", key=f"senha_{u['id']}")
                        if st.button("Redefinir Senha", key=f"btn_senha_{u['id']}"):
                            if nova_senha:
                                db_historico.reset_user_password(u['id'], nova_senha)
                                st.success("Senha atualizada!")
                                st.rerun()
                            else:
                                st.error("Digite a nova senha.")
                                
                    with c3:
                        st.write("Ações")
                        if u['id'] != st.session_state.user['id']:
                            if st.button("Excluir Usuário", key=f"btn_excluir_{u['id']}", type="primary", use_container_width=True):
                                excluir_usuario_dialog(u['id'], u['nome'], u['email'])
                        else:
                            st.info("Você não pode excluir a si mesmo.")
        else:
            st.info("Nenhum usuário encontrado.")
            
    with tab2:
        with st.form("novo_usuario_form"):
            st.subheader("Criar Vendedor")
            email = st.text_input("E-mail")
            nome = st.text_input("Nome")
            
            pwd_temp = "123456"
            
            senha = st.text_input("Senha Inicial (modifique ou use a gerada)", value=pwd_temp)
            role = st.selectbox("Perfil", ["VENDEDOR", "ADMIN"])
            
            submit = st.form_submit_button("Criar Usuário", type="primary")
            if submit:
                if email and nome and senha:
                    try:
                        db_historico.create_user(email, nome, senha, role)
                        st.success(f"Usuário criado com sucesso! Senha inicial: {senha}")
                    except Exception as e:
                        st.error(f"Erro ao criar usu�rio (email j� existe?): {e}")
                else:
                    st.error("Preencha todos os campos obrigat�rios.")


