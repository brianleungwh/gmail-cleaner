from __future__ import print_function

import os.path
import base64

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from gmail_cleaner.objects import Headers, Sender

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://mail.google.com/']


def add_to_senders(senders, thread_id, headers):
    """
    Add to the dictionary of senders, avoiding duplicates while appending new thread id
    """
    sender_email = headers.get_sender_email()
    if sender_email in senders:
        # append thread id to sender instance
        sender = senders[sender_email]
        sender.thread_ids.append(thread_id)
    else:
        # instantiate a new sender obj and add to dict of senders
        sender = Sender(thread_id=thread_id, headers=headers)
        senders[sender_email] = sender


def main():
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080, open_browser=False)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    # Main logic begins
    try:
        # Call the Gmail API
        gmail_service = build('gmail', 'v1', credentials=creds)

        # pageToken = ''
        results = gmail_service.users().threads().list(
            userId='me', 
            maxResults=100,
        ).execute()

        # pageToken = results['nextPageToken']

        threads = results.get('threads', [])

        if not threads:
            print('No threads found.')
            return

        senders = {}
        # where sender email is used as a uid as a key and sender obj as the value in the dict

        for t in threads:
            thread = gmail_service.users().threads().get(userId='me', id=t['id']).execute()
            msg = thread['messages'][0]

            headers = Headers(msg['payload']['headers'])
            if headers.unsubscribable:
                add_to_senders(senders, thread_id, headers)

        print("Found {num} marketing emails".format(num=len(marketers)))

        # eliminate duplicate entries in list
        unique_senders = set()
        to_unsub = []
        for marketer in marketers:
           if marketer['sender_email'] in unique_senders:
               print('Duplicate sender {}'.format(marketer['sender_email']))
               continue
           else:
               to_unsub.append(marketer)
               unique_senders.add(marketer['sender_email'])

        for m in to_unsub:
            print('{} {}'.format(m['sender_name'], m['sender_email']))
            for link in m['unsub_links']:
                print('{} {}'.format(link.method(), link.action_link()))

        respond = input("y or n")
        print(respond)
        print(type(respond))

            
        # result = gmail_service.users().getProfile(userId='me').execute()
        # print(result)

    except HttpError as error:
        # TODO(developer) - Handle errors from gmail API.
        print(f'An error occurred: {error}')


if __name__ == '__main__':
    main()
    

# snippet to decoce base64url to plain string in utf-8
# message = gmail_service.users().messages().get(userId='me', id=msg['id'], format='raw').execute()
# raw_message_str = str(base64.urlsafe_b64decode(message['raw']), 'utf-8')
