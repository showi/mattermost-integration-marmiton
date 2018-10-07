# -*- coding: utf-8 -*-
import json
import logging
import random
import re

try:
    from urllib.parse import urlsplit
    from urllib.parse import urlunsplit
except ImportError:
    from urlparse import urlsplit
    from urlparse import urlunsplit

import requests
from flask import Flask
from flask import Response
from flask import request

from mattermost_marmiton.settings import USERNAME, ICON_URL, RATING, SCHEME, \
    MARMITON_API_KEY, MATTERMOST_MARMITON_TOKEN


logging.basicConfig(
    level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(message)s')
app = Flask(__name__)


@app.route('/')
def root():
    """
    Home handler
    """

    return "OK"


@app.route('/new_post', methods=['POST'])
def new_post():
    """
    Mattermost new post event handler
    """
    try:
        # NOTE: common stuff
        slash_command = False
        resp_data = {}
        resp_data['username'] = USERNAME
        resp_data['icon_url'] = ICON_URL

        data = request.form

        if 'token' not in data:
            raise Exception('Missing necessary token in the post data')

        if data['token'] not in MATTERMOST_MARMITON_TOKEN:
            raise Exception('Tokens did not match, it is possible that this request came from somewhere other than Mattermost')

        # NOTE: support the slash command
        if 'command' in data:
            slash_command = True
            resp_data['response_type'] = 'in_channel'

        translate_text = data['text']
        if not slash_command:
            translate_text = data['text'][len(data['trigger_word']):]

        if not translate_text:
            raise Exception("No translate text provided, not hitting Marmiton")

        gif_url = translate(translate_text)
        if not gif_url:
            raise Exception('No gif url found for `{}`'.format(translate_text))

        resp_data['text'] = '''`{}` searched for {}
    {}'''.format(data.get('user_name', 'unknown').title(), translate_text, gif_url)
    except Exception as err:
        msg = err.message
        logging.error('unable to handle new post :: {}'.format(msg))
        resp_data['text'] = msg
    finally:
        resp = Response(content_type='application/json')
        resp.set_data(json.dumps(resp_data))
        return resp


def marmiton_translate(text):
    """
    Marmiton translate method, uses the Marmiton API to find an appropriate gif url
    """
    try:
        params = {}
        params['s'] = text
        params['rating'] = RATING
        params['api_key'] = MARMITON_API_KEY

        resp = requests.get('{}://api.marmiton.com/v1/gifs/translate'.format(SCHEME), params=params, verify=True)

        if resp.status_code is not requests.codes.ok:
            logging.error('Encountered error using Marmiton API, text=%s, status=%d, response_body=%s' % (text, resp.status_code, resp.json()))
            return None

        resp_data = resp.json()

        url = list(urlsplit(resp_data['data']['images']['original']['url']))
        url[0] = SCHEME.lower()

        return urlunsplit(url)
    except Exception as err:
        logging.error('unable to translate marmiton :: {}'.format(err))
        return None


def translate(text):
    """
    Search for a #Command with format '#Command <text>'.  If there is one, process the command.  If not, search marmiton
    """
    match = re.match(r'\#(\w+)\s+((?:\w|\s)+)', text, flags=0)
    return marmiton_translate(text) if match is None else process_command(match.group(1),match.group(2))


def process_command(command, text):
    """
    Process a #Command and return the Marmiton Url.  If command is not found, return marmiton URL for command and text.
    """
    transforms = {
      'magic8ball': lambda x: marmiton_translate(random.choice(['Yes',
                                                             'Absolutely',
                                                             'Yep',
                                                             'Hell Yeah',
                                                             'Affirmative',
                                                             'No',
                                                             'Absolutely Not',
                                                             'Nope',
                                                             'Hell No',
                                                             'Negative',
                                                             'Dont Know',
                                                             'Maybe',
                                                             'Dunno',
                                                             'Clueless',
                                                             'Shrug']))
    }
    return transforms[command.lower()](text) if command.lower() in transforms else marmiton_translate("#{} {}".format(command, text))
