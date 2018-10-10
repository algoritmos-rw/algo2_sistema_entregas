import base64
import datetime
import json
import logging
import mimetypes
import smtplib
import traceback
from collections import namedtuple
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import urlencode

import httplib2
import oauth2client.client
import urlfetch
from flask import Flask
from flask import render_template
from flask import request
from werkzeug.utils import secure_filename

from config import SENDER_NAME, EMAIL_TO, APP_TITLE, RECAPTCHA_SECRET, RECAPTCHA_SITE_ID, TEST, CLIENT_ID, \
    CLIENT_SECRET, OAUTH_REFRESH_TOKEN, GRUPAL, INDIVIDUAL
from planilla import fetch_planilla

app = Flask(__name__)
File = namedtuple('File', ['content', 'filename'])


EXTENSIONES_ACEPTADAS = {'zip', 'tar', 'gz', 'pdf'}


@app.route('/', methods=['GET'])
def get():
    planilla = fetch_planilla()
    return render('index.html', {
        'entregas': planilla.entregas,
        'entregas_json': json.dumps(planilla.entregas),
        'correctores_json': json.dumps(planilla.correctores),
    })


@app.errorhandler(Exception)
def err(error):
    logging.exception(error)
    return render('result.html', {'error': error})


def render(name, params={}):
    return render_template(name, **dict(params, **{
        'title': APP_TITLE,
        'recaptcha_site_id': RECAPTCHA_SITE_ID,
        'test': TEST,
    }))


def archivo_es_permitido(nombre):
    return '.' in nombre and \
           nombre.rsplit('.', 1)[1].lower() in EXTENSIONES_ACEPTADAS


def get_files():
    files = request.files.getlist('files')
    return [
        File(content=f.read(), filename=secure_filename(f.filename))
        for f in files
        if f and archivo_es_permitido(f.filename)
    ]


def sendmail(emails_alumno, nombres_alumnos,email_docente, tp, padrones, files, body):
    correo = MIMEMultipart()
    correo["From"] = SENDER_NAME
    correo["To"] = EMAIL_TO
    correo["Cc"] = ", ".join(emails_alumno + [email_docente])
    correo["Subject"] = '{} - {} - {}'.format(tp, ' , '.join(padrones), ' , '.join(nombres_alumnos))

    correo.attach(MIMEText('\n'.join([
            tp,
            '\n'.join(emails_alumno),
            '\n{}\n'.format(body) if body else '',
            '-- ',
            '{} - {}'.format(APP_TITLE, request.url),
        ]), 'plain'))

    for f in files:
        # Tomado de: https://docs.python.org/3.5/library/email-examples.html#id2
        # Adivinamos el Content-Type de acuerdo a la extensión del fichero.
        ctype, encoding = mimetypes.guess_type(f.filename)
        if ctype is None or encoding is not None:
            # No pudimos adivinar, así que usamos un Content-Type genérico.
            ctype = 'application/octet-stream'
        maintype, subtype = ctype.split('/', 1)
        if maintype == 'text':
            msg = MIMEText(f.content, _subtype=subtype)
        else:
            msg = MIMEBase(maintype, subtype)
            msg.set_payload(f.content)
            # Codificamos el payload en base 64.
            encoders.encode_base64(msg)
        # Set the filename parameter
        msg.add_header('Content-Disposition', 'attachment', filename=f.filename)
        correo.attach(msg)

    if not TEST:
        creds = get_oauth_credentials()
        xoauth2_tok = "user=%s\1" "auth=Bearer %s\1\1" % (EMAIL_TO,
                                                          creds.access_token)
        xoauth2_b64 = base64.b64encode(xoauth2_tok.encode("ascii")).decode("ascii")

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.ehlo()
        server.starttls()
        server.ehlo()  # Se necesita EHLO de nuevo tras STARTTLS.
        server.docmd("AUTH", "XOAUTH2 " + xoauth2_b64)
        server.send_message(correo)
        server.close()

    return correo


def get_oauth_credentials():
    """Refresca y devuelve nuestras credenciales OAuth.
    """
    # N.B.: siempre re-generamos el token de acceso porque este script es
    # stateless y no guarda las credenciales en ningún sitio. Todo bien con eso
    # mientras no alcancemos el límite de refresh() de Google (pero no publican
    # cuál es).
    creds = oauth2client.client.OAuth2Credentials(
        "", CLIENT_ID, CLIENT_SECRET, OAUTH_REFRESH_TOKEN,
        datetime.datetime(2015, 1, 1),
        "https://accounts.google.com/o/oauth2/token", "corrector/1.0")

    creds.refresh(httplib2.Http())
    return creds


def get_padrones(planilla, padron_o_grupo):
    if padron_o_grupo not in planilla.correctores:
        raise Exception('No se encuentra el alumno o grupo {}'.format(padron_o_grupo))

    # Es un grupo.
    if padron_o_grupo in planilla.grupos:
        return [padron for padron in planilla.grupos[padron_o_grupo]]

    # Es un padrón.
    return [padron_o_grupo]


def validate_grupo(planilla, padron_o_grupo, tp):
    if padron_o_grupo in planilla.grupos and planilla.entregas[tp] == INDIVIDUAL:
        raise Exception("La entrega {} debe ser entregada de forma individual".format(tp))


def get_emails_alumno(planilla, padron_o_grupo):
    if padron_o_grupo in planilla.grupos:
        return [planilla.emails_alumnos[alumno] for alumno in planilla.grupos[padron_o_grupo]]

    return [planilla.emails_alumnos[padron_o_grupo]]

def get_nombres_alumnos(planilla, padron_o_grupo):
    if padron_o_grupo in planilla.grupos:
        return [planilla.nombres_alumnos[alumno] for alumno in planilla.grupos[padron_o_grupo]]

    return [planilla.nombres_alumnos[padron_o_grupo]]


@app.route('/', methods=['POST'])
def post():
    try:
        validate_captcha()
        planilla = fetch_planilla()
        tp = request.form['tp']
        if tp not in planilla.entregas:
            raise Exception('La entrega {} es inválida'.format(tp))

        files = get_files()
        if not files:
            raise Exception('No se ha adjuntado ningún archivo con extensión válida.')

        padron_o_grupo = request.form['identificador']

        # Valida si la entrega es individual o grupal de acuerdo a lo ingresado.
        validate_grupo(planilla, padron_o_grupo, tp)

        docente = get_docente(planilla.correctores, padron_o_grupo, planilla, tp)
        body = request.form['body'] or ''
        email_docente = planilla.emails_docentes[docente]
        emails_alumno = get_emails_alumno(planilla, padron_o_grupo)
        nombres_alumnos = get_nombres_alumnos(planilla, padron_o_grupo)
        padrones = get_padrones(planilla, padron_o_grupo)

        email = sendmail(emails_alumno,nombres_alumnos, email_docente, tp.upper(), padrones, files, body)

        return render('result.html', {
            'sent': {
                'tp': tp,
                'email': '\n'.join('[[{}]]: {}'.format(k, str(v)) for k, v in email) if TEST else None,
            },
        })
    except Exception as e:
        print(traceback.format_exc())
        raise e


def validate_captcha():
    response = urlfetch.fetch(
        url='https://www.google.com/recaptcha/api/siteverify',
        params=urlencode({
            "secret": RECAPTCHA_SECRET,
            "remoteip": request.remote_addr,
            "response": request.form["g-recaptcha-response"],
        }),
        method="POST",
    )

    if not response.json['success']:
        raise Exception('Falló la validación del captcha')


def get_docente(correctores, padron_o_grupo, planilla, tp):
    if padron_o_grupo not in correctores:
        raise Exception('No hay un corrector asignado para el padrón o grupo {}'.format(padron_o_grupo))

    if padron_o_grupo in planilla.grupos or planilla.entregas[tp] != GRUPAL:
        return correctores[padron_o_grupo]

    # Es un alumno entregando de forma individual una entrega grupal,
    # por el motivo que fuere.
    # Buscamos su corrector de trabajos grupales. 
    padron = padron_o_grupo
    for grupo in planilla.grupos:
        if padron in planilla.grupos[grupo]:
            return correctores[grupo]
        
