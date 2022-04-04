from __future__ import print_function

import os.path
import base64
import logging

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from gmail_cleaner.objects import Headers, Sender


logging.basicConfig(level=logging.INFO)

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


def prompt_user(question):
    """
    Helper to get yes / no answer from user.
    """
    yes = {'yes', 'y'}
    no = {'no', 'n'}

    print(question)
    while True:
        choice = input().lower()
        if choice in yes:
            return True
        elif choice in no:
            return False
        else:
            print("Please respond by yes or no.")


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
        user_email = gmail_service.users().getProfile(userId='me').execute().get('emailAddress')

        # max_results = 500
        results = gmail_service.users().threads().list(
            userId='me',
            # maxResults=max_results,
            includeSpamTrash=False,
        ).execute()

        next_page_token = results.get('nextPageToken')
        threads = []
        while next_page_token:
            print('looping')
            print(next_page_token)
            print(len(threads))

            threads.extend(results.get('threads', []))

            results = gmail_service.users().threads().list(
                userId='me',
                pageToken=next_page_token,
                # maxResults=max_results,
                includeSpamTrash=False,
            ).execute()
            next_page_token = results.get('nextPageToken')


        threads.extend(results.get('threads', []))

        if not threads:
            print('No threads found.')
            return

        print("Processing {} total number of threads".format(len(threads)))


        senders = {}
        # where sender email is used as a uid as a key and sender obj as the value in the dict

        # builds master dictionary of senders
        for t in threads:
            thread = gmail_service.users().threads().get(userId='me', id=t['id']).execute()
            msg = thread['messages'][0]

            headers = Headers(msg['payload']['headers'])
            if headers.unsubscribable():
                add_to_senders(senders, t['id'], headers)

        print("Found {num} unique senders".format(num=len(senders)))


        # builds truth table from user input
        # user_response = {}
        # for sender_email, sender_obj in senders.items():
        #     question = "Unsubscribe and trash all emails from sender: {} {}".format(sender_obj.name, sender_email)
        #     to_remove = prompt_user(question)
        #     if to_remove:
        #         user_response[sender_email] = True
        #     else:
        #         user_response[sender_email] = False


        # execute trashing threads and unsubscibe from senders
        # # based on truth table
        # for sender_email, sender_obj in senders.items():
        #     if user_response[sender_email]:
        #         # unsubscribe from sender
        #         sender_obj.do_unsubscribe(user_email, gmail_service)

        #         # move all threads associated with sender to trash
        #         for t_id in sender_obj.thread_ids:
        #             gmail_service.users().threads().trash(userId='me', id=t_id)

        #     else:
        #         print("skipping {} as user instructed".format(sender_email))


        # result = gmail_service.users().getProfile(userId='me').execute()
        # print(result)

    except HttpError as error:
        # TODO(developer) - Handle errors from gmail API.
        print(f'An error occurred: {error}')


if __name__ == '__main__':
    main()
