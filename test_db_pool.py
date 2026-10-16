"""
Testes automatizados para verificação do pool de conexões e banco de dados.

Contém:
1. Testes simulados (mocks) do pool PostgreSQL:
   - Uma conexão é devolvida após uma consulta bem-sucedida.
   - Uma conexão é devolvida quando uma consulta produz uma exceção SQL (com rollback).
   - Conexão quebrada/encerrada é descartada com close=True e não vaza no pool.
   - Falha em cursor.close() não impede a devolução da conexão ao pool.
   - Chamadas repetidas a contar_cotacoes() e get_user_by_id() não esgotam o pool.
   - O gerenciamento do pool continua correto e estável em consultas simultâneas (concorrência).
2. Testes com banco real (SQLite):
   - Histórico, filtros (status, busca, período), permissões de vendedor vs admin
     e integridade das cotações.
"""

import threading
import time
import uuid
import os
import pytest
from unittest import mock

import db_historico


# ============================================================================
# CLASSES DE SIMULAÇÃO (MOCKS) DE CONEXÃO E POOL POSTGRESQL
# ============================================================================

class MockCursor:
    def __init__(self, conn, raise_on_execute=None, raise_on_close=False, result_rows=None):
        self.conn = conn
        self.raise_on_execute = raise_on_execute
        self.raise_on_close = raise_on_close
        self.result_rows = result_rows if result_rows is not None else [{"total": 42, "id": "user-1", "nome": "Vendedor 1", "role": "VENDEDOR"}]
        self.closed = False
        self.last_query = None
        self.last_params = None

    def execute(self, query, params=None):
        self.last_query = query
        self.last_params = params
        if self.raise_on_execute:
            raise self.raise_on_execute

    def fetchone(self):
        if self.result_rows:
            return self.result_rows[0]
        return None

    def fetchall(self):
        return list(self.result_rows)

    def close(self):
        self.closed = True
        if self.raise_on_close:
            raise RuntimeError("InterfaceError: cursor already closed")


class MockConnection:
    def __init__(self, conn_id=None, raise_on_cursor=None, raise_on_execute=None, raise_on_close=False):
        self.id = conn_id or str(uuid.uuid4())
        self.closed = 0
        self.commit_count = 0
        self.rollback_count = 0
        self.raise_on_cursor = raise_on_cursor
        self.raise_on_execute = raise_on_execute
        self.raise_on_close = raise_on_close
        self.cursors = []

    def cursor(self, cursor_factory=None):
        if self.closed != 0:
            raise RuntimeError("OperationalError: connection already closed")
        if self.raise_on_cursor:
            raise self.raise_on_cursor
        cur = MockCursor(self, raise_on_execute=self.raise_on_execute, raise_on_close=self.raise_on_close)
        self.cursors.append(cur)
        return cur

    def commit(self):
        if self.closed != 0:
            raise RuntimeError("OperationalError: connection already closed")
        self.commit_count += 1

    def rollback(self):
        if self.closed != 0:
            raise RuntimeError("OperationalError: connection already closed")
        self.rollback_count += 1

    def close(self):
        self.closed = 1


class MockThreadedConnectionPool:
    """
    Simula estritamente o comportamento do ThreadedConnectionPool do psycopg2:
    - minconn=1, maxconn=5.
    - Se len(_used) >= maxconn, getconn() lança Exception("connection pool exhausted").
    - putconn(conn, close=...) remove conn de _used e se close=False e não fechada, adiciona a _pool.
    """
    def __init__(self, minconn=1, maxconn=5, *args, **kwargs):
        self.minconn = minconn
        self.maxconn = maxconn
        self.closed = False
        self._lock = threading.Lock()
        self._used = {}
        self._pool = [MockConnection(f"conn-{i}") for i in range(maxconn)]

    def getconn(self, key=None):
        with self._lock:
            if self.closed:
                raise RuntimeError("PoolError: connection pool is closed")
            if self._pool:
                conn = self._pool.pop()
                self._used[id(conn)] = conn
                return conn
            if len(self._used) >= self.maxconn:
                raise RuntimeError("psycopg2.pool.PoolError: connection pool exhausted")
            conn = MockConnection(f"conn-extra-{len(self._used)}")
            self._used[id(conn)] = conn
            return conn

    def putconn(self, conn, key=None, close=False):
        with self._lock:
            if self.closed:
                raise RuntimeError("PoolError: connection pool is closed")
            conn_id = id(conn)
            if conn_id not in self._used:
                raise RuntimeError("psycopg2.pool.PoolError: connection not in use")
            del self._used[conn_id]
            if close or getattr(conn, "closed", 0) != 0:
                conn.close()
                return
            self._pool.append(conn)

    def closeall(self):
        with self._lock:
            self.closed = True
            for c in list(self._pool):
                c.close()
            self._pool.clear()
            for c in list(self._used.values()):
                c.close()
            self._used.clear()


# ============================================================================
# 1. TESTES SIMULADOS (MOCK POSTGRESQL POOL)
# ============================================================================

def test_conexao_devolvida_apos_sucesso():
    """Confirma que uma conexão é devolvida ao pool após uma consulta bem-sucedida."""
    pool = MockThreadedConnectionPool(1, 5)
    db_historico.reset_postgres_pool()

    with mock.patch("db_historico.get_db_config", return_value={"type": "postgres", "url": "postgres://mock"}), \
         mock.patch("db_historico.get_postgres_pool", return_value=pool):

        assert len(pool._used) == 0
        assert len(pool._pool) == 5

        res = db_historico.execute_query("SELECT COUNT(*) as c FROM cotacoes", fetchone=True)
        assert res is not None
        assert res.get("total") == 42

        # A conexão DEVE ter sido devolvida ao pool imediatamente
        assert len(pool._used) == 0
        assert len(pool._pool) == 5


def test_conexao_devolvida_quando_consulta_produz_excecao():
    """Confirma que uma conexão é devolvida ao pool e recebe rollback quando a consulta produz exceção SQL."""
    pool = MockThreadedConnectionPool(1, 5)
    db_historico.reset_postgres_pool()

    # Configura a primeira conexão para falhar no execute
    failing_conn = pool._pool[-1]
    failing_conn.raise_on_execute = RuntimeError("psycopg2.errors.SyntaxError: syntax error at or near 'INVALID'")

    with mock.patch("db_historico.get_db_config", return_value={"type": "postgres", "url": "postgres://mock"}), \
         mock.patch("db_historico.get_postgres_pool", return_value=pool):

        with pytest.raises(RuntimeError, match="SyntaxError"):
            db_historico.execute_query("INVALID SQL STATEMENT")

        # Rollback DEVE ter sido executado para limpar o estado da transação
        assert failing_conn.rollback_count >= 1

        # A conexão DEVE ter retornado ao pool mesmo com a exceção
        assert len(pool._used) == 0
        assert len(pool._pool) == 5


def test_conexao_quebrada_descartada_com_close():
    """Confirma que conexões quebradas/fechadas são descartadas com close=True e não vazam em _used."""
    pool = MockThreadedConnectionPool(1, 5)
    db_historico.reset_postgres_pool()

    # Simula falha ao abrir cursor (servidor encerrou a conexão)
    broken_conn = pool._pool[-1]
    broken_conn.raise_on_cursor = RuntimeError("psycopg2.OperationalError: server closed the connection unexpectedly")

    with mock.patch("db_historico.get_db_config", return_value={"type": "postgres", "url": "postgres://mock"}), \
         mock.patch("db_historico.get_postgres_pool", return_value=pool):

        with pytest.raises(RuntimeError, match="server closed the connection"):
            db_historico.execute_query("SELECT 1")

        # A conexão quebrada não deve estar em _used
        assert len(pool._used) == 0
        # A conexão deve ter sido fechada e não devolvida ao _pool reutilizável
        assert broken_conn.closed == 1
        assert len(pool._pool) == 4


def test_falha_no_cursor_close_nao_impede_devolucao():
    """Confirma que se cursor.close() falhar, a conexão ainda é devolvida ao pool."""
    pool = MockThreadedConnectionPool(1, 5)
    db_historico.reset_postgres_pool()

    conn = pool._pool[-1]
    conn.raise_on_close = True  # cursor.close() lança RuntimeError

    with mock.patch("db_historico.get_db_config", return_value={"type": "postgres", "url": "postgres://mock"}), \
         mock.patch("db_historico.get_postgres_pool", return_value=pool):

        res = db_historico.execute_query("SELECT 1", fetchone=True)
        assert res is not None

        # Mesmo com erro em cursor.close(), a conexão foi devolvida
        assert len(pool._used) == 0
        assert len(pool._pool) == 5


def test_chamadas_repetidas_contar_cotacoes_e_get_user_nao_esgotam_pool():
    """Confirma que chamadas repetidas a contar_cotacoes() e get_user_by_id() não esgotam o pool de 5 conexões."""
    pool = MockThreadedConnectionPool(1, 5)
    db_historico.reset_postgres_pool()

    with mock.patch("db_historico.get_db_config", return_value={"type": "postgres", "url": "postgres://mock"}), \
         mock.patch("db_historico.get_postgres_pool", return_value=pool), \
         mock.patch.object(db_historico, "_db_initialized", True):

        for i in range(50):
            # No código anterior, se cada chamada retivesse uma conexão,
            # o pool de 5 estouraria na 6ª iteração com PoolError: connection pool exhausted.
            total = db_historico.contar_cotacoes(owner_user_id="user-1", role="VENDEDOR")
            assert total == 42
            u = db_historico.get_user_by_id("user-1")
            assert u is not None

        # Ao final de 50 repetições, todas as conexões devem estar livres
        assert len(pool._used) == 0
        assert len(pool._pool) == 5


def test_concorrencia_pool_consultas_simultaneas():
    """Confirma que o gerenciamento do pool continua correto em consultas concorrentes superiores a maxconn."""
    pool = MockThreadedConnectionPool(1, 5)
    db_historico.reset_postgres_pool()

    with mock.patch("db_historico.get_db_config", return_value={"type": "postgres", "url": "postgres://mock"}), \
         mock.patch("db_historico.get_postgres_pool", return_value=pool), \
         mock.patch.object(db_historico, "_db_initialized", True):

        erros = []
        num_threads = 15

        def worker(idx):
            try:
                for _ in range(5):
                    # Pequeno jitter para intercalar acessos simultâneos
                    time.sleep(0.005)
                    cnt = db_historico.contar_cotacoes(owner_user_id="user-1", role="VENDEDOR")
                    assert cnt == 42
                    u = db_historico.get_user_by_id("user-1")
                    assert u["role"] == "VENDEDOR"
            except Exception as e:
                erros.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Nenhuma thread pode ter falhado por esgotamento do pool
        assert len(erros) == 0, f"Erros durante execução concorrente: {erros}"
        assert len(pool._used) == 0
        assert len(pool._pool) == 5


# ============================================================================
# 2. TESTES COM BANCO REAL (SQLITE)
# ============================================================================

def test_historico_filtros_e_vendedor_real_sqlite(tmp_path):
    """
    Testa contra o banco real SQLite:
    - Salvar cotações
    - Isolamento de cotações entre vendedores
    - Visibilidade de ADMIN
    - Filtros por status, busca e período
    - Aprovação e exclusão
    - Duplicação
    - Contagem
    """
    db_test_path = str(tmp_path / "test_hist.db")
    db_historico._db_initialized = False

    with mock.patch("db_historico.get_db_config", return_value={"type": "sqlite", "path": db_test_path}), \
         mock.patch("db_historico.migrar_json_antigo", lambda: None):
        db_historico.init_db()

        # 1. Cria usuários: Admin e dois vendedores
        admin_id = db_historico.create_user("admin@real.com", "Admin Real", "pass123", role="ADMIN")
        vend_a_id = db_historico.create_user("venda@real.com", "Vendedor A", "pass123", role="VENDEDOR")
        vend_b_id = db_historico.create_user("vendb@real.com", "Vendedor B", "pass123", role="VENDEDOR")

        # 2. Salva cotação para Vendedor A
        cot_a = {
            "id": "COT-REAL-A1",
            "cnpj_cliente": "11222333000181",
            "nome_cliente": "Cliente Real Alpha",
            "cidade_uf_destino": "Campinas/SP",
            "cep_destino": "13000-000",
            "valor_nf": 1500.0,
            "qtd_volumes": 2,
            "peso_real": 25.0,
            "peso_cubado": 30.0,
            "peso_tarifado": 30.0,
            "dados_json": '{"itens": []}'
        }
        db_historico.salvar_cotacao(cot_a, owner_user_id=vend_a_id)

        # 3. Salva cotação para Vendedor B
        cot_b = {
            "id": "COT-REAL-B1",
            "cnpj_cliente": "99888777000166",
            "nome_cliente": "Cliente Real Beta",
            "cidade_uf_destino": "Curitiba/PR",
            "cep_destino": "80000-000",
            "valor_nf": 800.0,
            "qtd_volumes": 1,
            "peso_real": 10.0,
            "peso_cubado": 12.0,
            "peso_tarifado": 12.0,
            "dados_json": '{"itens": []}'
        }
        db_historico.salvar_cotacao(cot_b, owner_user_id=vend_b_id)

        # 4. Verifica isolamento:
        # Vendedor A só vê sua cotação
        cotacoes_a = db_historico.obter_cotacoes(owner_user_id=vend_a_id, role="VENDEDOR")
        assert len(cotacoes_a) == 1
        assert cotacoes_a[0]["id"] == "COT-REAL-A1"
        assert cotacoes_a[0]["vendedor_nome"] == "Vendedor A"

        # Vendedor B só vê sua cotação
        cotacoes_b = db_historico.obter_cotacoes(owner_user_id=vend_b_id, role="VENDEDOR")
        assert len(cotacoes_b) == 1
        assert cotacoes_b[0]["id"] == "COT-REAL-B1"

        # Admin vê todas as cotações
        cotacoes_admin = db_historico.obter_cotacoes(owner_user_id=admin_id, role="ADMIN")
        assert len(cotacoes_admin) == 2

        # 5. Contagem de cotações
        assert db_historico.contar_cotacoes(owner_user_id=vend_a_id, role="VENDEDOR") == 1
        assert db_historico.contar_cotacoes(owner_user_id=admin_id, role="ADMIN") == 2

        # 6. Filtro por status
        pendentes_a = db_historico.obter_cotacoes(status="Pendente", owner_user_id=vend_a_id, role="VENDEDOR")
        assert len(pendentes_a) == 1
        aprovadas_a = db_historico.obter_cotacoes(status="Aprovada", owner_user_id=vend_a_id, role="VENDEDOR")
        assert len(aprovadas_a) == 0

        # 7. Aprovação de cotação
        db_historico.aprovar_cotacao("COT-REAL-A1", "Braspress", 185.50, owner_user_id=vend_a_id, role="VENDEDOR")
        item_aprovado = db_historico.obter_cotacao_por_id("COT-REAL-A1", owner_user_id=vend_a_id, role="VENDEDOR")
        assert item_aprovado["status"] == "APROVADA"
        assert item_aprovado["transportadora_aprovada"] == "Braspress"
        assert item_aprovado["valor_frete_aprovado"] == 185.50
        assert item_aprovado["approved_by"] == vend_a_id

        # 8. Filtro por busca
        busca_alpha = db_historico.obter_cotacoes(search="Alpha", owner_user_id=admin_id, role="ADMIN")
        assert len(busca_alpha) == 1
        assert busca_alpha[0]["id"] == "COT-REAL-A1"

        busca_cnpj = db_historico.obter_cotacoes(search="99888777", owner_user_id=admin_id, role="ADMIN")
        assert len(busca_cnpj) == 1
        assert busca_cnpj[0]["id"] == "COT-REAL-B1"

        # 9. Duplicação de cotação
        novo_id = db_historico.duplicar_cotacao("COT-REAL-A1", new_owner_user_id=vend_a_id, role="VENDEDOR")
        assert novo_id is not None
        assert novo_id != "COT-REAL-A1"
        item_duplicado = db_historico.obter_cotacao_por_id(novo_id, owner_user_id=vend_a_id, role="VENDEDOR")
        assert item_duplicado["status"] == "PENDENTE"
        assert item_duplicado["cnpj_cliente"] == "11222333000181"

        # 10. Exclusão de cotação
        db_historico.excluir_cotacao(novo_id, owner_user_id=vend_a_id, role="VENDEDOR")
        ativas = db_historico.obter_cotacoes(owner_user_id=vend_a_id, role="VENDEDOR")
        assert not any(c["id"] == novo_id for c in ativas)
        excluidas = db_historico.obter_cotacoes(status="Excluídas", owner_user_id=vend_a_id, role="VENDEDOR")
        assert any(c["id"] == novo_id for c in excluidas)
