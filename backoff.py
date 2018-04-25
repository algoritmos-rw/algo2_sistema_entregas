import os.path
from datetime import datetime, timedelta

SIN_PENALIDAD = 2
ULTIMAS_ENTREGAS = 10
# Por si acaso que algun error nuestro cause errores, permitimos desactivar el backoff,
# aunque sea momentaneamente
BACKOFF_ACTIVADO = True

def get_id_cursada():
  """Devuelve el identificador de la cursada según año y cuatrimestre.

  El identificador es del tipo ‘2015_2’ o ‘2016_1’, donde el segundo elemento
  indica el cuatrimestre.

  El cuatrimestre es:

    - 1 si la fecha es antes del 1 de agosto;
    - 2 si es igual o posterior.
  """
  today = datetime.today()
  cutoff = today.replace(month=8, day=1)
  return "{}_{}".format(today.year, 1 if today < cutoff else 2)


def get_id_estudiante(planilla, padron_o_grupo):
    """
    Los grupos se registran como Gxx en la planilla, pero en el repositorio se
    guardan como padrón1_padrón2 (con padrón1 < padrón2).
    Esta función devuelve el indentificador correspondiente de acuerdo al grupo
    o padrón.
    """
    # Si es un grupo formado por dos personas.
    if padron_o_grupo in planilla.grupos and len(planilla.grupos[padron_o_grupo]) == 2:
        padrones = planilla.grupos[padron_o_grupo]
        return "{}_{}".format(min(padrones), max(padrones))

    # Si es un grupo formado por una persona.
    if padron_o_grupo in planilla.grupos and len(planilla.grupos[padron_o_grupo]) == 1:
        return planilla.grupos[padron_o_grupo][0]

    # En otro caso es un padrón.
    return padron_o_grupo


def obtener_entregas(repo, tp, id_cursada, id_grupo):
    """
    Devuelve una lista con los
    """
    rel_dir = os.path.join(tp, id_cursada, id_grupo)

    # Si el path no existe, entonces no hubo entregas hasta ahora.
    if not os.path.exists(os.path.join(repo.working_dir, rel_dir)):
        return []

    log = repo.git.log("--format=%at", "--date=iso", rel_dir)
    return [datetime.fromtimestamp(int(date)) for date in log.split("\n")]

def backoff(x):
    """
    Calcula el backoff (en horas) correspondiente a una cantidad de entregas
    La funcion tiene la forma: 
                        0                                   si x <= SIN_PENALIDAD
        backoff(x) =    x - SIN_PENALIDAD                   si SIN_PEALIDAD < x < ULTIMAS_ENTREGAS
                        ULTIMAS_ENTREGAS - SIN_PENALIDAD    en otro caso
    
    Siendo SIN_PENALIDAD = 2 y ULTIMAS_ENTREGAS = 10, 
    Es la función lineal que empieza en x = 2, y termina en x = 10 con valor 8.
    """
    return 0 if x <= SIN_PENALIDAD else x - SIN_PENALIDAD

def tiempo_siguiente_entrega(entregas):
    """
    Calcula el momento a partir del cual el alumno puede volver a hacer la entrega, 
    teniendo en cuenta el backoff que tiene que cumplir el alumno respecto de la 
    ultima entrega que hizo.
    """
    # Le sumo el delta a la ultima entrega
    return entregas[-1] + timedelta(hours = backoff(len(entregas)))

def _validar_backoff_entregas(entregas, tiempo_actual):
    """
    Logica de la validacion. Recibe el tiempo actual para poder hacerlo 
    testeable
    """
    # Si aun no hizo entregas, entonces cumple
    if len(entregas) == 0:
        return

    # Me quedo con las ultimas entregas, para poner un máximo de tiempo
    entregas = entregas[-ULTIMAS_ENTREGAS:]  
    siguiente = tiempo_siguiente_entrega(entregas)

    if  siguiente > datetime.today():
        raise BackoffException("No puede hacer esta entrega hasta: " + str(siguiente))

def validar_backoff(repo, planilla, tp, padron_o_grupo):
    """
    Levanta una excepción de tipo BackoffException cuando un alumno o grupo
    hace demasiados intentos en muy poco tiempo para realizar una entrega.
    """
    if not BACKOFF_ACTIVADO:
        return

    tp = tp.lower()
    id_cursada = get_id_cursada()
    id_grupo = get_id_estudiante(planilla, padron_o_grupo)

    entregas = obtener_entregas(repo, tp, id_cursada, id_grupo)
    _validar_backoff_entregas(entregas, datetime.today())


class BackoffException(Exception):
    """
    Excepcion que se lanza cuando no se cumplen los tiempos de espera del corrector,
    luego de sucesivos intentos
    """
    pass
