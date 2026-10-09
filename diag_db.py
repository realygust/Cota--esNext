
import db_historico
import json

user_a = 'test_owner_a'
user_b = 'test_owner_b'

db_historico.execute_query('DELETE FROM cotacoes WHERE owner_user_id IN (?, ?)', (user_a, user_b))

dados = {
    'id': 'COT-TEST-A',
    'cnpj_cliente': '123',
    'nome_cliente': 'Test Client',
    'cidade_uf_destino': 'Sao Paulo/SP',
    'cep_destino': '01000-000',
    'valor_nf': None,
    'qtd_volumes': 1,
    'peso_real': 10.0,
    'peso_cubado': 10.0,
    'peso_tarifado': 10.0,
    'resultados': [{'Transportadora': 'Trans A', 'Valor Frete (R$)': 100}]
}
db_historico.salvar_cotacao(dados, owner_user_id=user_a)

db_historico.aprovar_cotacao('COT-TEST-A', 'Trans A', 100, owner_user_id=user_a)

row_a = db_historico.obter_cotacao_por_id('COT-TEST-A', owner_user_id=user_a, role='VENDEDOR')
print('COT-A status:', row_a['status'])
print('COT-A approved_by:', row_a['approved_by'])
print('COT-A nf:', row_a['valor_nf'])
parsed_json_a = json.loads(row_a['dados_json'])
print('COT-A JSON has status?', 'status' in parsed_json_a)
print('COT-A JSON has owner?', 'owner_user_id' in parsed_json_a)

novo_id = db_historico.duplicar_cotacao('COT-TEST-A', new_owner_user_id=user_b)
row_b = db_historico.obter_cotacao_por_id(novo_id, owner_user_id=user_b, role='VENDEDOR')
print('COT-B status:', row_b['status'])
print('COT-B approved_by:', row_b['approved_by'])
print('COT-B owner:', row_b['owner_user_id'])
parsed_json_b = json.loads(row_b['dados_json'])
print('COT-B JSON has status?', 'status' in parsed_json_b)
print('COT-B JSON has owner?', 'owner_user_id' in parsed_json_b)

