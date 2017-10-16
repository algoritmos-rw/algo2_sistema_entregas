import os.path
from datetime import datetime


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


def validar_backoff(repo, planilla, tp, padron_o_grupo):
    """
    Levanta una excepción de tipo BackoffException cuando un alumno o grupo
    hacen demasiados intentos en muy poco tiempo para realizar una entrega.
    """
    tp = tp.lower()
    id_cursada = get_id_cursada()
    id_grupo = get_id_estudiante(planilla, padron_o_grupo)

    entregas = obtener_entregas(repo, tp, id_cursada, id_grupo)
    # Usar "entregas" para implementar el backoff.
