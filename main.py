import base64
import collections
import datetime
import io
import logging
import mimetypes
import smtplib
import zipfile

from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import urlencode

import httplib2
import oauth2client.client
import urlfetch

from flask import Flask, render_template, request
from werkzeug.exceptions import FailedDependency, HTTPException
from werkzeug.utils import secure_filename

from config import load_config, Modalidad, Settings
from planilla import fetch_planilla

app = Flask(__name__)
cfg: Settings = load_config()

File = collections.namedtuple('File', ['content', 'filename'])
EXTENSIONES_ACEPTADAS = {'zip', 'tar', 'gz', 'pdf'}


class InvalidForm(Exception):
    """Excepción para cualquier error en el form.
    """


@app.route("/", methods=["GET"])
def get():
    planilla = fetch_planilla()
    return render("index.html",
                  entregas=cfg.entregas,
                  correctores=planilla.correctores)


@app.errorhandler(Exception)
def err(error):
    if isinstance(error, HTTPException):
        code = error.code
        message = error.description
    else:
        code = 500
        message = f"{error.__class__.__name__}: {error}"
    logging.exception(error)
    return render("result.html", error=message), code


@app.errorhandler(InvalidForm)
def warn_and_render(ex):
    """Error menos verboso que err(), apropiado para excepciones de usuario.
    """
    logging.warn(f"InvalidForm: {ex}")
    return render("result.html", error=ex), 422  # Unprocessable Entity


def render(name, **params):
    return render_template(name, cfg=cfg, **params)


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


def sendmail(emails_alumno, nombres_alumnos, email_docente, tp, padrones, files, body):
    correo = MIMEMultipart()
    correo["From"] = str(cfg.sender)
    correo["To"] = ", ".join(emails_alumno)
    correo["Cc"] = email_docente
    correo["Bcc"] = cfg.sender.email
    correo["Reply-To"] = correo["To"]  # Responder a los alumnos
    subject_text = '{} - {} - {}'.format(tp, ', '.join(padrones), ', '.join(nombres_alumnos))

    if not files:
        # Se asume que es una ausencia, se escribe la justificación dentro
        # de un archivo ZIP para que el corrector automático acepte el mail
        # como una entrega, y registre la justificación en el repositorio.
        rawzip = io.BytesIO()
        with zipfile.ZipFile(rawzip, "w") as zf:
            zf.writestr("ausencia.txt", body + "\n")
        files = [File(rawzip.getvalue(), f"{tp.lower()}_ausencia.zip")]
        subject_text += " (ausencia)"  # Permite al corrector omitir las pruebas.

    correo["Subject"] = subject_text
    correo.attach(MIMEText('\n'.join([tp,
                                      '\n'.join(emails_alumno),
                                      f'\n{body}\n' if body else '',
                                      f'-- \n{cfg.title} - {request.url}',
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

    if not cfg.test:
        creds = get_oauth_credentials()
        xoauth2_tok = "user=%s\1" "auth=Bearer %s\1\1" % (cfg.sender.email,
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
        "",
        cfg.oauth_client_id,
        cfg.oauth_client_secret.get_secret_value(),
        cfg.oauth_refresh_token.get_secret_value(),
        datetime.datetime(2015, 1, 1),
        "https://accounts.google.com/o/oauth2/token", "corrector/1.0")

    creds.refresh(httplib2.Http())
    return creds


def get_padrones(planilla, padron_o_grupo):
    if padron_o_grupo not in planilla.correctores:
        raise InvalidForm(f"No se encuentra el alumno o grupo {padron_o_grupo}")

    # Es un grupo.
    if padron_o_grupo in planilla.grupos:
        return [padron for padron in planilla.grupos[padron_o_grupo]]

    # Es un padrón.
    return [padron_o_grupo]


def validate_grupo(planilla, padron_o_grupo, tp):
    if padron_o_grupo in planilla.grupos and cfg.entregas[tp] == Modalidad.INDIVIDUAL:
        raise InvalidForm(f"La entrega {tp} debe ser entregada de forma individual")


def get_emails_alumno(planilla, padrones):
    return [planilla.emails_alumnos[p] for p in padrones]


def get_nombres_alumnos(planilla, padrones):
    return [planilla.nombres_alumnos[p].split(',')[0].title() for p in padrones]


@app.route('/', methods=['POST'])
def post():
    planilla = fetch_planilla()
    try:
        validate_captcha()
        tp = request.form['tp']
        if tp not in cfg.entregas:
            raise InvalidForm(f"La entrega {tp!r} es inválida")

        files = get_files()
        body = request.form['body'] or ''
        tipo = request.form['tipo']

        if tipo == 'entrega' and not files:
            raise InvalidForm('No se ha adjuntado ningún archivo con extensión válida.')
        elif tipo == 'ausencia' and not body:
            raise InvalidForm('No se ha adjuntado una justificación para la ausencia.')

        padron_o_grupo = request.form['identificador']
    except KeyError as ex:
        raise InvalidForm(f"Formulario inválido sin campo {ex.args[0]!r}") from ex

    # Valida si la entrega es individual o grupal de acuerdo a lo ingresado.
    validate_grupo(planilla, padron_o_grupo, tp)

    docente = get_docente(planilla.correctores, padron_o_grupo, planilla, tp)
    email_docente = planilla.emails_docentes[docente]
    padrones = get_padrones(planilla, padron_o_grupo)
    emails_alumno = get_emails_alumno(planilla, padrones)
    nombres_alumnos = get_nombres_alumnos(planilla, padrones)

    email = sendmail(emails_alumno, nombres_alumnos, email_docente, tp.upper(), padrones, files, body)

    return render("result.html",
                  tp=tp,
                  email='\n'.join(f"{k}: {v}"
                                  for k, v in email.items()) if cfg.test else None)


def validate_captcha():
    response = urlfetch.fetch(
        url='https://www.google.com/recaptcha/api/siteverify',
        params=urlencode({
            "secret": cfg.recaptcha_secret.get_secret_value(),
            "remoteip": request.remote_addr,
            "response": request.form["g-recaptcha-response"],
        }),
        method="POST",
    )

    if not response.json['success']:
        raise InvalidForm('Falló la validación del captcha')


def get_docente(correctores, padron_o_grupo, planilla, tp):
    if cfg.entregas[tp] == Modalidad.PARCIALITO:
        return ""  # XXX "Funciona" porque parse_datos_docentes() suele encontrar celdas vacías.
    if padron_o_grupo not in correctores:
        raise FailedDependency(f"No hay un corrector asignado para el padrón o grupo {padron_o_grupo}")

    if padron_o_grupo in planilla.grupos or cfg.entregas[tp] != Modalidad.GRUPAL:
        return correctores[padron_o_grupo]

    # Es un alumno entregando de forma individual una entrega grupal,
    # por el motivo que fuere.
    # Buscamos su corrector de trabajos grupales.
    padron = padron_o_grupo
    for grupo in planilla.grupos:
        if padron in planilla.grupos[grupo]:
            return correctores[grupo]
