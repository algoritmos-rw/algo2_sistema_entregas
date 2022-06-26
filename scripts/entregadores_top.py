import sys
import heapq
import subprocess

"""
Ejecutar este script parado en la ruta del repo de algo2_entregas
"""

def mes_inicio_fin(semestre):
	inicio = "03" if semestre == 1 else "08"
	fin = "07" if semestre == 1 else "12"
	return inicio, fin


def main(anio, semestre, top):
	entregadores = {}
	ini, fin = mes_inicio_fin(semestre)
	fecha_inicio = f'''{anio}-{ini}-01'''
	fecha_fin = f'''{anio}-{fin}-28'''
	commits = str(subprocess.check_output(['git', 'log', '--pretty=format:"%ad - %an: %s"', f'''--after="{fecha_inicio}"''', f'''--until="{fecha_fin}"'''])).split("\\n")
	for line in commits:
		entregador = line.strip()[1:-1].split(" from ")[1]
		if "_" in entregador:
			e1, e2 = entregador.split("_")
			entregadores[e1] = entregadores.get(e1, 0) + 1
			entregadores[e2] = entregadores.get(e2, 0) + 1
		else:
			entregadores[entregador] = entregadores.get(entregador, 0) + 1

	for top in heapq.nlargest(top, entregadores, key=lambda e: entregadores[e]):
		print(top, entregadores[top])


if __name__ == "__main__":
	cuatrimestre = sys.argv[1]
	top = int(sys.argv[2]) if len(sys.argv) > 2 else 5
	anio, semestre = cuatrimestre.split("_")
	main(anio, int(semestre), top)
