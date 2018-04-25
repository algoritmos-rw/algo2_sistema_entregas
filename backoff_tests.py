from backoff import _validar_backoff_entregas as validar
from backoff import BackoffException
from datetime import datetime, timedelta
import unittest

HOY = datetime.today()

class TestValidacionBackoff(unittest.TestCase):

    def test_sin_entregas(self):
        validar([], HOY)

    def test_entrega_pocas_veces(self):
        # Entrego hace 1 segundo
        validar([HOY - timedelta(seconds = 1)], HOY)

    def test_entrega_hace_mucho(self):
        # Entrego hace 5 dias
        validar([HOY - timedelta(5)], HOY)

    def test_entrega_pasa_backoff(self):
        # Entrego hace 5 dias
        validar([HOY - timedelta(hours = 6), HOY - timedelta(hours = 5), HOY - timedelta(hours = 4), HOY - timedelta(hours = 3)], HOY)

    def test_entrega_no_pasa_backoff(self):
        with self.assertRaises(BackoffException):
            validar([HOY, HOY, HOY, HOY], HOY)

    def test_muchas_entregas_hace_tiempo(self):
        tiempos = [HOY - timedelta(10, seconds = 10 - i) for i in range(10)]
        validar(tiempos, HOY)

    def test_muchas_entregas_hace_poco_tiempo(self):
        tiempos = [HOY - timedelta(hours = 10 - i) for i in range(8)]
        with self.assertRaises(BackoffException):
            validar(tiempos, HOY)

    def test_algunas_entregas_poco_tiempo(self):
        tiempos = [HOY - timedelta(minutes = 7, hours = 3), HOY - timedelta(minutes = 5, hours = 3), HOY - timedelta(minutes = 3)]
        with self.assertRaises(BackoffException):
            validar(tiempos, HOY)

if __name__ == "__main__":
    unittest.main()