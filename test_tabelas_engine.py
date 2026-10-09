import unittest
import tabelas_engine as te

class TestTabelasEngine(unittest.TestCase):
    def test_verificar_cobertura_estrita(self):
        # Testa se a Braspress cobre SC
        ok, msg = te.verificar_cobertura_estrita("BRASPRESS", "SC", "qualquer", "89000000")
        self.assertTrue(ok)
        
        # Testa se a Princesa cobre SP
        ok, msg = te.verificar_cobertura_estrita("PRINCESA", "SP", "sao paulo", "01000000")
        self.assertTrue(ok)
        
        # Testa se Princesa cobre PR fora de Curitiba (agora cobre todo o estado)
        ok, msg = te.verificar_cobertura_estrita("PRINCESA", "PR", "londrina", "86000000")
        self.assertTrue(ok)
        self.assertIn("Cobertura confirmada", msg)
        
        # Testa se Princesa cobre PR Curitiba
        ok, msg = te.verificar_cobertura_estrita("PRINCESA", "PR", "curitiba", "80000000")
        self.assertTrue(ok)

    def test_calcular_frete_estrito_garcia(self):
        res = te.calcular_frete_estrito("GARCIA", 10, 10, 1000, "SP", "sao paulo", "01000000")
        self.assertTrue(res.get("Atendida") or res.get("Sucesso", False))
        self.assertGreater(res.get("Valor Frete (R$)", 0), 0)

    def test_calcular_frete_estrito_brasul(self):
        # A Transportadora configurada é BRASUL, mas na tabelas_engine não tem BRASUL explicitamente no cfg
        # O cfg para ela pode não existir.
        res = te.calcular_frete_estrito("TW", 10, 10, 1000, "SC", "blumenau", "89000000")
        self.assertTrue(res.get("Atendida"))

    def test_calcular_frete_estrito_alfa(self):
        res = te.calcular_frete_estrito("ALFA", 10, 10, 1000, "GO", "goiania", "74000000")
        self.assertTrue(res.get("Atendida"))

if __name__ == '__main__':
    unittest.main()
