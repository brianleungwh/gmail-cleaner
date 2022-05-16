import base64
import logging


from email.mime.text import MIMEText

from googleapiclient import errors


def create_message(sender, to, subject, message_text):
    """Create a message for an email.

    Args:
        sender: Email address of the sender.
        to: Email address of the receiver.
        subject: The subject of the email message.
        message_text: The text of the email message.

    Returns:
        An object containing a base64url encoded email object.
    """
    message = MIMEText(message_text)
    logging.info('TO: {}'.format(to))

    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    raw_msg = base64.urlsafe_b64encode(message.as_string().encode('utf-8'))
    return {'raw': raw_msg.decode('utf-8')}

def send_message(service, user_id, message):
    """Send an email message.

    Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me"
    can be used to indicate the authenticated user.
    message: Message to be sent.

    Returns:
    Sent Message.
    """
    try:
        message = service.users().messages().send(userId=user_id, body=message).execute()
        logging.info('Message Id: %s' % message['id'])
        return message
    except errors.HttpError as e:
        logging.error('An error occurred: %s' % e)
