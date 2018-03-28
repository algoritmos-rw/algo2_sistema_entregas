# -*- coding: utf8 -*-
import os
from collections import OrderedDict

GRUPAL = "g"
INDIVIDUAL = "i"

SPREADSHEET_ID = os.environ['spreadsheet_id']
ENTREGAS = OrderedDict([('TP0', INDIVIDUAL), ('VD', INDIVIDUAL), ('Pila', INDIVIDUAL) ])
SENDER_NAME = 'Entregas Algoritmos 2'
EMAIL_TO = 'tps.7541rw@gmail.com'
APP_TITLE = 'Algoritmos y Programación 2 - Entrega de TPs'

SERVICE_ACCOUNT_CREDENTIALS = {
    "type":                           "service_account",
    "project_id": os.environ          ['project_id'],
    "private_key_id": os.environ      ['private_key_id'],
    "private_key":                    "-----BEGIN PRIVATE KEY-----" +
                                      os.environ['private_key'].replace("\\n", "\n") +
                                      "-----END PRIVATE KEY-----\n",
    "client_email": os.environ        ['client_email'],
    "client_id": os.environ           ['client_id'],
    "auth_uri":                       "https://accounts.google.com/o/oauth2/auth",
    "token_uri":                      "https://accounts.google.com/o/oauth2/token",
    "auth_provider_x509_cert_url":    "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": os.environ['client_x509_cert_url']
}

RECAPTCHA_SITE_ID = os.environ['RECAPTCHA_SITE_ID']
RECAPTCHA_SECRET = os.environ['RECAPTCHA_SECRET']

TEST = False

CLIENT_ID = os.environ['OAUTH_CLIENT_ID']
CLIENT_SECRET = os.environ['OAUTH_CLIENT_SECRET']
OAUTH_REFRESH_TOKEN = os.environ['OAUTH_REFRESH_TOKEN']
