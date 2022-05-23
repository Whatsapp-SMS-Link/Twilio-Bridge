import os
import re
import threading

from datetime import datetime, timedelta
from flask import Flask, request
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

communication_opened = dict()  # todo database


def get_number(s):
    result = re.search('\\d{10}$', s)
    return result.group(0) if result else ''


def simple_send(dest, body, whatsapp=True):
    client = Client(os.getenv('SID'), os.getenv('TOKEN'))
    return client.messages.create(
        to=('whatsapp:' if whatsapp else '') + '+1' + dest,  # We currently only support US
        messaging_service_sid=os.getenv('MESSAGING_SERVICE_SID'),
        body=body
    )


###################################################################################################
# WHATSAPP requires an approved template to be sent if a business is initiating communication.    #
#     Once the client sends anything (whether he initiated or in response to the template), there #
#     is a 24-hour window for communication before the template must be sent again.               #
#     https://www.twilio.com/docs/whatsapp/tutorial/send-whatsapp-notification-messages-templates #
# If this is the first time we are connecting with a client, save the message and send him the    #
#     agreement. On that, send him the message. Otherwise, just send the message, nothing else    #
#     required.                                                                                   #
###################################################################################################
def open_communication(source, dest, body, signature):
    simple_send(dest, f'Hi {dest}, were we able to solve the issue that you were facing?')  # todo custom template
    while dest not in communication_opened.keys():
        pass
    return bridge_services(source, dest, body, signature, True)


def bridge_services(source, dest, body, signature, to_whatsapp):
    sig = (signature + ' (' + source + ')') if signature is not None else source
    return simple_send(dest, body + '\n- ' + sig,
                       to_whatsapp)


@app.route("/reply", methods=['GET', 'POST'])
def sms_reply():
    resp = MessagingResponse()
    source = request.form['From']
    from_whatsapp = source.startswith('w')

    if from_whatsapp:
        communication_opened[get_number(source)] = datetime.now()

    request_body = request.form['Body'].splitlines()  # todo currently only supports single line messages

    if len(request_body) < 2 or len(request_body) > 3:
        resp.message("To send a message, you must write two or three lines:\nThe destination number\nThe message you "
                     "want to send\nAn optional signature (otherwise, only your phone number will be given)")
    else:
        dest = get_number(request_body[0])

        if dest == '':
            resp.message("The destination number was malformed. Please check it and try again.")
        else:
            if not from_whatsapp and (dest not in communication_opened.keys()
                                      or datetime.now() >= communication_opened[dest] + timedelta(hours=24)):
                x = threading.Thread(target=open_communication,
                                     args=(source, dest, request_body[1], request_body[2] if len(request_body) == 3
                                           else None))
                x.start()
            else:
                bridge_services(source, dest, request_body[1], signature=request_body[2] if len(request_body) == 3
                                else None, to_whatsapp=not from_whatsapp)

    return str(resp)


if __name__ == "__main__":
    app.run(debug=True)
