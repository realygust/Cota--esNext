import secrets
import datetime
import sqlite3
import json
import os
import uuid
import hashlib
from datetime import datetime, timedelta
import streamlit as st

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

DB_PATH = "C:\\Users\\Next\\Desktop\\CotaçõesAutomáticas\\db\\historico.db"
JSON_PATH = "C:\\Users\\Next\\Desktop\\CotaçõesAutomáticas\\historico.json"

def get_db_config():
    url = os.environ.get("DATABASE_URL")
    if not url and "database" in st.secrets and "url" in st.secrets["database"]:
        url = st.secrets["database"]["url"]
        
    if url and url.startswith("postgres"):
        if not HAS_POSTGRES:
            st.error("psycopg2-binary não está instalado, mas um URL do Postgres foi fornecido.")
            st.stop()
        return {"type": "postgres", "url": url}
        
    return {"type": "sqlite", "path": DB_PATH}

def get_connection():
    config = get_db_config()
    if config["type"] == "postgres":
        conn = psycopg2.connect(config["url"])
        return conn
    else:
       diretorio = os.path.dirname(config["path"])
if diretorio:
    os.makedirs(diretorio, exist_ok=True)
        conn = sqlite3.connect(config["path"], check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

def execute_query(query, params=None, fetch=False, fetchone=False, commit=True):
    config = get_db_config()
    conn = get_connection()
    
    if config["type"] == "postgres":
        query = query.replace("?", "%s")
        cursor = conn.cursor(cursor_factory=RealDictCursor)
    else:
        cursor = conn.cursor()
        
    try:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
            
        if commit:
            conn.commit()
            
        if fetchone:
            row = cursor.fetchone()
            return dict(row) if row else None
        if fetch:
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    finally:
        cursor.close()
        conn.close()

def hash_password(password: str, salt: bytes = None):
    if salt is None:
        salt = os.urandom(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt.hex(), pwd_hash.hex()

def verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    salt = bytes.fromhex(salt_hex)
    _, expected_hash = hash_password(password, salt)
    return expected_hash == hash_hex

_db_initialized = False

def init_db():
    global _db_initialized
    if _db_initialized:
        return
        
    config = get_db_config()
    
    if config["type"] == "postgres":
        text_type = "TEXT"
        datetime_type = "TIMESTAMP"
        real_type = "NUMERIC"
        int_type = "INTEGER"
    else:
        text_type = "TEXT"
        datetime_type = "DATETIME"
        real_type = "REAL"
        int_type = "INTEGER"

    execute_query(f"""
        CREATE TABLE IF NOT EXISTS usuarios (
            id {text_type} PRIMARY KEY,
            email {text_type} UNIQUE,
            nome {text_type},
            role {text_type},
            status {text_type},
            password_hash {text_type},
            password_salt {text_type},
            session_token {text_type},
            session_expires_at {datetime_type},
            created_at {datetime_type}
        )
    """)


    
    try:
        execute_query("ALTER TABLE usuarios ADD COLUMN session_token " + text_type)
        execute_query("ALTER TABLE usuarios ADD COLUMN session_expires_at " + datetime_type)
    except Exception:
        pass

    try:
        execute_query("ALTER TABLE cotacoes ADD COLUMN approved_by " + text_type)
    except Exception:
        pass

    execute_query(f"""
        CREATE TABLE IF NOT EXISTS cotacoes (

            id {text_type} PRIMARY KEY,
            created_at {datetime_type},
            expires_at {datetime_type},
            approved_at {datetime_type},
            deleted_at {datetime_type},
            status {text_type},
            cnpj_cliente {text_type},
            nome_cliente {text_type},
            cidade_uf_destino {text_type},
            cep_destino {text_type},
            valor_nf {real_type},
            qtd_volumes {int_type},
            peso_real {real_type},
            peso_cubado {real_type},
            peso_tarifado {real_type},
            transportadora_aprovada {text_type},
            valor_frete_aprovado {real_type},
            approved_by {text_type},
            dados_json {text_type},
            owner_user_id {text_type}
        )
    """)
    
    execute_query(f"""
        CREATE TABLE IF NOT EXISTS entregas_rastreamento (
            id {text_type} PRIMARY KEY,
            nf {text_type},
            pedido {text_type},
            cliente {text_type},
            cidade {text_type},
            estado {text_type},
            transportadora {text_type},
            status {text_type},
            data_atualizacao {datetime_type},
            dados_json {text_type}
        )
    """)

    if config["type"] == "sqlite":
        cols = execute_query("PRAGMA table_info(cotacoes)", fetch=True)
        if not any(c["name"] == "owner_user_id" for c in cols):
            execute_query("ALTER TABLE cotacoes ADD COLUMN owner_user_id TEXT")
    else:
        cols = execute_query("SELECT column_name FROM information_schema.columns WHERE table_name='cotacoes'", fetch=True)
        if not any(c["column_name"] == "owner_user_id" for c in cols):
            execute_query("ALTER TABLE cotacoes ADD COLUMN owner_user_id TEXT")

    # Create default admin if not exists
    users_count = execute_query("SELECT COUNT(*) as c FROM usuarios", fetchone=True)
    if users_count and users_count["c"] == 0:
        salt, pwd_hash = hash_password("admin123")
        execute_query("""
            INSERT INTO usuarios (id, email, nome, role, status, password_hash, password_salt, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), "admin@admin.com", "Administrador", "ADMIN", "ATIVO", pwd_hash, salt, datetime.now().isoformat()))

    # Migrate entregas.xlsx if exists
    import os
    if os.path.exists("entregas.xlsx"):
        try:
            import pandas as pd
            import json
            df_mig = pd.read_excel("entregas.xlsx")
            if not df_mig.empty:
                for _, row in df_mig.iterrows():
                    nf = str(row.get("Nota Fiscal", ""))
                    if not nf or nf == "nan": continue
                    cnpj = str(row.get("CNPJ", ""))
                    status = str(row.get("Status", ""))
                    cidade = str(row.get("Destino", ""))
                    
                    row_dict = {k: ("" if pd.isna(v) else v) for k, v in row.to_dict().items()}
                    dados_json = json.dumps(row_dict, ensure_ascii=False)
                    upsert_entrega(nf, "", cnpj, cidade, "", "", status, dados_json)
            # Backup and remove
            os.rename("entregas.xlsx", "entregas.xlsx.migrated")
            import logging
            logging.info("Migracao do entregas.xlsx concluida com sucesso!")
        except Exception as e:
            import logging
            logging.error(f"Erro ao migrar entregas.xlsx: {e}")

    _db_initialized = True
    
    try:
        migrar_json_antigo()
    except Exception as e:
        print(f"Erro na migração do JSON: {e}")

def migrar_json_antigo():
    if not os.path.exists(JSON_PATH):
        return
        
    count = execute_query("SELECT COUNT(*) as c FROM cotacoes", fetchone=True)
    
    if count and count["c"] == 0:
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            dados = json.load(f)
            
        for item in dados:
            item_id = item.get("id", str(uuid.uuid4()))
            dh_str = item.get("data_hora", "")
            try:
                created_at = datetime.strptime(dh_str, "%d/%m/%Y %H:%M")
            except:
                created_at = datetime.now()
            
            expires_at = created_at + timedelta(days=7)
            status = "EXPIRADA" if datetime.now() > expires_at else "PENDENTE"
                
            execute_query("""
                INSERT INTO cotacoes (
                    id, created_at, expires_at, status, cnpj_cliente, nome_cliente,
                    cidade_uf_destino, cep_destino, valor_nf, peso_real, peso_tarifado,
                    transportadora_aprovada, valor_frete_aprovado, dados_json, owner_user_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item_id,
                created_at.isoformat(),
                expires_at.isoformat(),
                status,
                item.get("doc_destinatario", ""),
                item.get("nome_cliente", ""),
                item.get("destino", ""),
                item.get("cep_destino", ""),
                item.get("valor_nf", 0.0),
                item.get("peso_kg", 0.0),
                item.get("peso_tarifado_kg", 0.0),
                None,
                None,
                json.dumps(item, ensure_ascii=False),
                None
            ))
        
        os.rename(JSON_PATH, f"{JSON_PATH}.bak")

def atualizar_status_expiradas():
    init_db()
    
    now_iso = datetime.now().isoformat()
    execute_query("""
        UPDATE cotacoes 
        SET status = 'EXPIRADA' 
        WHERE status = 'PENDENTE' 
        AND ? > expires_at
    """, (now_iso,))

def salvar_cotacao(dados, owner_user_id=None):
    init_db()
    created_at = datetime.now()
    expires_at = created_at + timedelta(days=7)
    
    # 1. Enforce ID creation to prevent NULL IDs
    cot_id = dados.get("id")
    if not cot_id:
        cot_id = f"COT-{created_at.strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:4]}"
        dados["id"] = cot_id
        
    val_nf = dados.get("valor_nf")
    if val_nf == "": val_nf = None

    dados_copy = dict(dados)
    for k in ["status", "owner_user_id", "approved_at", "approved_by", "transportadora_aprovada", "valor_frete_aprovado", "deleted_at"]:
        dados_copy.pop(k, None)

    execute_query("""
        INSERT INTO cotacoes (
            id, created_at, expires_at, status, cnpj_cliente, nome_cliente,
            cidade_uf_destino, cep_destino, valor_nf, qtd_volumes, peso_real, 
            peso_cubado, peso_tarifado, dados_json, owner_user_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        cot_id,
        created_at.isoformat(),
        expires_at.isoformat(),
        "PENDENTE",
        dados.get("cnpj_cliente", ""),
        dados.get("nome_cliente", ""),
        dados.get("cidade_uf_destino", ""),
        dados.get("cep_destino", ""),
        val_nf,
        dados.get("qtd_volumes", 0),
        dados.get("peso_real", 0.0),
        dados.get("peso_cubado", 0.0),
        dados.get("peso_tarifado", 0.0),
        json.dumps(dados_copy, ensure_ascii=False),
        owner_user_id
    ))

def obter_cotacoes(status=None, search=None, limit=100, offset=0, periodo=None, owner_user_id=None, role="VENDEDOR"):
    init_db()
    if owner_user_id:
        u = get_user_by_id(owner_user_id)
        if u: role = u.get("role", role)
    atualizar_status_expiradas()
    
    query = "SELECT * FROM cotacoes WHERE status != 'EXCLUÍDA'"
    params = []
    
    if role != "ADMIN":
        query += " AND owner_user_id = ?"
        params.append(owner_user_id)
    
    if status and status != "Todas":
        if status == "Excluídas":
            query = query.replace("status != 'EXCLUÍDA'", "status = 'EXCLUÍDA'")
        else:
            query += " AND status = ?"
            params.append(status.upper())
            
    if search:
        query += " AND (cnpj_cliente LIKE ? OR nome_cliente LIKE ? OR cidade_uf_destino LIKE ? OR id LIKE ? OR dados_json LIKE ?)"
        lk = f"%{search}%"
        params.extend([lk, lk, lk, lk, lk])
    
    if periodo:
        now = datetime.now()
        if periodo == "Hoje":
            data_ini = now.replace(hour=0, minute=0, second=0).isoformat()
            query += " AND created_at >= ?"
            params.append(data_ini)
        elif periodo == "Últimos 7 dias":
            data_ini = (now - timedelta(days=7)).isoformat()
            query += " AND created_at >= ?"
            params.append(data_ini)
        elif periodo == "Últimos 30 dias":
            data_ini = (now - timedelta(days=30)).isoformat()
            query += " AND created_at >= ?"
            params.append(data_ini)
        elif periodo == "Últimos 90 dias":
            data_ini = (now - timedelta(days=90)).isoformat()
            query += " AND created_at >= ?"
            params.append(data_ini)
        
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    return execute_query(query, params, fetch=True)

def contar_cotacoes(status=None, search=None, periodo=None, owner_user_id=None, role="VENDEDOR"):
    init_db()
    if owner_user_id:
        u = get_user_by_id(owner_user_id)
        if u: role = u.get("role", role)
    atualizar_status_expiradas()
    
    query = "SELECT COUNT(*) as total FROM cotacoes WHERE status != 'EXCLUÍDA'"
    params = []
    
    if role != "ADMIN" and owner_user_id:
        query += " AND owner_user_id = ?"
        params.append(owner_user_id)
    
    if status and status != "Todas":
        if status == "Excluídas":
            query = query.replace("status != 'EXCLUÍDA'", "status = 'EXCLUÍDA'")
        else:
            query += " AND status = ?"
            params.append(status.upper())
            
    if search:
        query += " AND (cnpj_cliente LIKE ? OR nome_cliente LIKE ? OR cidade_uf_destino LIKE ? OR id LIKE ? OR dados_json LIKE ?)"
        lk = f"%{search}%"
        params.extend([lk, lk, lk, lk, lk])
    
    if periodo:
        now = datetime.now()
        if periodo == "Hoje":
            data_ini = now.replace(hour=0, minute=0, second=0).isoformat()
            query += " AND created_at >= ?"
            params.append(data_ini)
        elif periodo == "Últimos 7 dias":
            data_ini = (now - timedelta(days=7)).isoformat()
            query += " AND created_at >= ?"
            params.append(data_ini)
        elif periodo == "Últimos 30 dias":
            data_ini = (now - timedelta(days=30)).isoformat()
            query += " AND created_at >= ?"
            params.append(data_ini)
        elif periodo == "Últimos 90 dias":
            data_ini = (now - timedelta(days=90)).isoformat()
            query += " AND created_at >= ?"
            params.append(data_ini)
    
    result = execute_query(query, params, fetchone=True)
    return result["total"] if result else 0

def aprovar_cotacao(id_cotacao, transportadora, valor, owner_user_id=None, role="VENDEDOR"):
    init_db()
    if owner_user_id:
        u = get_user_by_id(owner_user_id)
        if u: role = u.get("role", role)
    
    query = """
        UPDATE cotacoes
        SET status = 'APROVADA',
            approved_at = ?,
            transportadora_aprovada = ?,
            valor_frete_aprovado = ?,
            approved_by = ?
        WHERE id = ?
    """
    params = [datetime.now().isoformat(), transportadora, valor, owner_user_id, id_cotacao]
    
    if role != "ADMIN":
        query += " AND owner_user_id = ?"
        params.append(owner_user_id)
        
    execute_query(query, params)

def excluir_cotacao(id_cotacao, owner_user_id=None, role="VENDEDOR"):
    if not id_cotacao:
        print("Warning: excluir_cotacao called with empty or None id_cotacao")
        return
        
    init_db()
    if owner_user_id:
        u = get_user_by_id(owner_user_id)
        if u: role = u.get("role", role)
    query = """
        UPDATE cotacoes 
        SET status = 'EXCLUÍDA', 
            deleted_at = ?
        WHERE id = ?
    """
    params = [datetime.now().isoformat(), id_cotacao]
    
    if role != "ADMIN":
        query += " AND owner_user_id = ?"
        params.append(owner_user_id)
        
    execute_query(query, params)

def obter_cotacao_por_id(id_cotacao, owner_user_id=None, role="VENDEDOR"):
    init_db()
    if owner_user_id:
        u = get_user_by_id(owner_user_id)
        if u: role = u.get("role", role)
    query = "SELECT * FROM cotacoes WHERE id = ?"
    params = [id_cotacao]
    
    if role != "ADMIN":
        query += " AND owner_user_id = ?"
        params.append(owner_user_id)
        
    return execute_query(query, params, fetchone=True)

def duplicar_cotacao(id_cotacao, new_owner_user_id=None, role="VENDEDOR"):
    init_db()
    if new_owner_user_id:
        u = get_user_by_id(new_owner_user_id)
        if u: role = u.get("role", role)
    original = obter_cotacao_por_id(id_cotacao, new_owner_user_id, role)
    if not original:
        return None
    
    novo_id = f"COT-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:4]}"
    created_at = datetime.now()
    expires_at = created_at + timedelta(days=7)
    
    try:
        dados = json.loads(original.get("dados_json", "{}"))
        dados["id"] = novo_id
        for k in ["status", "owner_user_id", "approved_at", "approved_by", "transportadora_aprovada", "valor_frete_aprovado", "deleted_at"]:
            dados.pop(k, None)
        dados_json = json.dumps(dados, ensure_ascii=False)
    except Exception:
        dados_json = original.get("dados_json", "{}")
    
    execute_query("""
        INSERT INTO cotacoes (
            id, created_at, expires_at, status, cnpj_cliente, nome_cliente,
            cidade_uf_destino, cep_destino, valor_nf, qtd_volumes, peso_real, 
            peso_cubado, peso_tarifado, dados_json, owner_user_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        novo_id,
        created_at.isoformat(),
        expires_at.isoformat(),
        "PENDENTE",
        original.get("cnpj_cliente", ""),
        original.get("nome_cliente", ""),
        original.get("cidade_uf_destino", ""),
        original.get("cep_destino", ""),
        original.get("valor_nf"),
        original.get("qtd_volumes", 0),
        original.get("peso_real", 0.0),
        original.get("peso_cubado", 0.0),
        original.get("peso_tarifado", 0.0),
        dados_json,
        new_owner_user_id
    ))
    return novo_id

# ===== USERS API =====

def get_user_by_email(email: str):
    init_db()
    return execute_query("SELECT * FROM usuarios WHERE email = ?", (email,), fetchone=True)

def get_user_by_id(user_id: str):
    init_db()
    return execute_query("SELECT * FROM usuarios WHERE id = ?", (user_id,), fetchone=True)

def create_user(email: str, nome: str, password: str, role: str = "VENDEDOR"):
    init_db()
    salt, pwd_hash = hash_password(password)
    user_id = str(uuid.uuid4())
    execute_query("""
        INSERT INTO usuarios (id, email, nome, role, status, password_hash, password_salt, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, email, nome, role, "ATIVO", pwd_hash, salt, datetime.now().isoformat()))
    return user_id

def authenticate_local_user(email: str, password: str):
    user = get_user_by_email(email)
    if not user:
        return None
    if user["status"] != "ATIVO":
        return None
    
    if verify_password(password, user["password_salt"], user["password_hash"]):
        return user
    return None

def get_all_users():
    init_db()
    return execute_query("SELECT id, email, nome, role, status, created_at FROM usuarios", fetch=True)

def update_user_status(user_id: str, status: str):
    init_db()
    execute_query("UPDATE usuarios SET status = ? WHERE id = ?", (status, user_id))

def reset_user_password(user_id: str, password: str):
    init_db()
    salt, pwd_hash = hash_password(password)
    execute_query("UPDATE usuarios SET password_hash = ?, password_salt = ? WHERE id = ?", (pwd_hash, salt, user_id))

# ===== ENTREGAS API =====

def get_all_entregas():
    init_db()
    return execute_query("SELECT * FROM entregas_rastreamento ORDER BY data_atualizacao DESC", fetch=True)

def upsert_entrega(nf: str, pedido: str, cliente: str, cidade: str, estado: str, transportadora: str, status: str, dados_json: str):
    init_db()
    entrega_id = nf if nf else str(uuid.uuid4())
    now = datetime.now().isoformat()
    
    # Simple upsert using DELETE then INSERT (SQLite compatible)
    if nf:
        execute_query("DELETE FROM entregas_rastreamento WHERE nf = ?", (nf,))
    else:
        execute_query("DELETE FROM entregas_rastreamento WHERE id = ?", (entrega_id,))
    
    query = """
        INSERT INTO entregas_rastreamento (id, nf, pedido, cliente, cidade, estado, transportadora, status, data_atualizacao, dados_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    execute_query(query, (entrega_id, nf, pedido, cliente, cidade, estado, transportadora, status, now, dados_json))

def delete_entrega(nf: str):
    init_db()
    execute_query("DELETE FROM entregas_rastreamento WHERE nf = ?", (nf,))

def create_session_token(user_id: str) -> str:
    token = secrets.token_hex(32)
    expires_at = (datetime.now() + timedelta(days=30)).isoformat()
    query = "UPDATE usuarios SET session_token = ?, session_expires_at = ? WHERE id = ?"
    execute_query(query, (token, expires_at, user_id), commit=True)
    return token

def authenticate_session_token(token: str):
    if not token:
        return None
    query = "SELECT * FROM usuarios WHERE session_token = ?"
    user = execute_query(query, (token,), fetchone=True)
    if user and user.get("session_expires_at"):
        try:
            expires_at = datetime.fromisoformat(user["session_expires_at"])
            if datetime.now() < expires_at:
                return user
        except Exception:
            pass
    return None

def clear_session_token(user_id: str):
    query = "UPDATE usuarios SET session_token = NULL, session_expires_at = NULL WHERE id = ?"
    execute_query(query, (user_id,), commit=True)
