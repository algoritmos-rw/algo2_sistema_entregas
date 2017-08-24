import gspread
from oauth2client.service_account import ServiceAccountCredentials
from collections import namedtuple, defaultdict
from config import SPREADSHEET_ID, ENTREGAS, SERVICE_ACCOUNT_CREDENTIALS, GRUPAL, INDIVIDUAL

SCOPE = ['https://spreadsheets.google.com/feeds']
SHEET_NOTAS = 'Notas'
SHEET_DATOS_ALUMNOS = 'DatosAlumnos'


def fetch_sheet(ranges):
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(SERVICE_ACCOUNT_CREDENTIALS, SCOPE)
    gc = gspread.authorize(credentials)
    sheet = gc.open_by_key(SPREADSHEET_ID)
    return [sheet.worksheet(worksheet) for worksheet in ranges]


def parse_datos_alumnos(datos_alumnos):
    # emails_alumnos = { <padron> => <email> }
    emails_alumnos = {}
    NOMBRE = 0
    celdas = datos_alumnos.get_all_values()
    PADRON = celdas[0].index(u'Padrón')
    EMAIL = celdas[0].index(u'Email')
    for row in celdas[1:]:
        if EMAIL < len(row) and row[PADRON] and '@' in row[EMAIL]:
            emails_alumnos[row[PADRON]] = u'{} <{}>'.format(row[NOMBRE], row[EMAIL])
    return emails_alumnos


def safely_get_column(row, col_number):
    return row[col_number] if col_number < len(row) else ""


def parse_notas(notas):
    celdas = notas.get_all_values()
    headers = celdas[0]
    
    PADRON = headers.index(u'Padrón')
    DOCENTE_INDIV = headers.index(u'Ayudante')
    DOCENTE_MAIL_INDIV = headers.index(u'Email')
    DOCENTE_GRUP = headers.index(u'Ayudante grupo')
    DOCENTE_MAIL_GRUP = headers.index(u'Mail ayudante grupo')
    NRO_GRUPO = headers.index(u'Nro Grupo')
    COMPA = headers.index(u'Nombre compañero')
    PADRON_COMPA = headers.index(u'Padrón compañero')
    MAIL_COMPA = headers.index(u'Mail compañero grupo')

    # correctores = { <padron o grupo> => { <tp> => <nombre docente> } }
    correctores = defaultdict(dict)
    # grupos = { <grupo> => set(<padron>, ...) }
    grupos = defaultdict(set)
    # emails_docentes = { <nombre docente> => <email> }
    emails_docentes = {}

    for row in celdas[1:]:
        if PADRON >= len(row) or not row[PADRON]:
            break
        # TODO: optimizar esto. No hace falta hacer iteraciones de más en
        # algoritmos II porque todos los alumnos tienen un corrector
        # individual y uno grupal (es decir: no varía según entrega).
        padron = row[PADRON]
        for tp, tipo in ENTREGAS.iteritems():
            email_docente = safely_get_column(row, DOCENTE_MAIL_INDIV)
            docente = safely_get_column(row, DOCENTE_INDIV)
            if not '@' in email_docente:
                continue
            emails_docentes[docente] = u'{} <{}>'.format(docente, email_docente)
            if tipo == INDIVIDUAL:
                correctores[padron][tp] = docente
            else:
                grupo = safely_get_column(row, NRO_GRUPO)
                padron_compa = safely_get_column(row, PADRON_COMPA)
                email_compa = safely_get_column(row, MAIL_COMPA)
                correctores[grupo][tp] = docente
                grupos[grupo].add(padron)
                if email_compa and '@' in email_compa:
                    grupos[grupo].add(padron_compa)
    return correctores, grupos, emails_docentes

Planilla = namedtuple('Planilla', [
    'correctores',
    'grupos',
    'emails_alumnos',
    'emails_docentes',
    'entregas',
])


def fetch_planilla():
    notas, datos_alumnos = fetch_sheet([SHEET_NOTAS, SHEET_DATOS_ALUMNOS])
    emails_alumnos = parse_datos_alumnos(datos_alumnos)
    correctores, grupos, emails_docentes = parse_notas(notas)
    return Planilla(
        correctores,
        grupos,
        emails_alumnos,
        emails_docentes,
        ENTREGAS,
    )
