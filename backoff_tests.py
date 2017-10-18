from backoff import _validar_backoff_entregas as validar
from backoff import TIEMPO_BASE, BackoffException
from datetime import datetime, timedelta
import unittest

HOY = datetime.today()

class TestValidacionBackoff(unittest.TestCase):

    def test_sin_entregas(self):
        validar([], HOY)

    def test_entrega_hace_mucho(self):
        # Entrego hace 5 dias
        validar([HOY - timedelta(5)], HOY)

    def test_entrega_pasa_backoff(self):
        # Entrego hace 5 dias
        validar([HOY - timedelta(seconds = TIEMPO_BASE + 10)], HOY)

    def test_entrega_no_pasa_backoff(self):
        with self.assertRaises(BackoffException):
            validar([HOY], HOY)

    def test_muchas_entregas_hace_tiempo(self):
        tiempos = [HOY - timedelta(10, seconds = 10 - i) for i in range(10)]
        validar(tiempos, HOY)

    def test_muchas_entregas_hace_poco_tiempo(self):
        tiempos = [HOY - timedelta(seconds = 10 - i) for i in range(10)]
        with self.assertRaises(BackoffException):
            validar(tiempos, HOY)

    def test_algunas_entregas_poco_tiempo(self):
        tiempos = [HOY - timedelta(minutes = 7), HOY - timedelta(minutes = 3)]
        with self.assertRaises(BackoffException):
            validar(tiempos, HOY)

    def test_algunas_entregas_pasa_tiempo(self):
        tiempos = [HOY - timedelta(minutes = 15), HOY - timedelta(minutes = 10)]
        validar(tiempos, HOY)

if __name__ == "__main__":
    unittest.main()