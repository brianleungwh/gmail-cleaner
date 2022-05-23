import re
import logging

import requests

from caseconverter import snakecase
from gmail_cleaner.utils import create_message, send_message


class Sender(object):
    """
    Represents a sender
    """

    def __init__(self, thread_id=None, headers=None):
        self.name = headers.get_sender_name(),
        self.email = headers.get_sender_email(),
        self.unsub_links = headers.get_list_of_unsub_links()
        self.thread_ids = [thread_id]

    def has_mailto_link(self):
        """
        Returns True if unsub_links contain a mailto
        """
        for link in self.unsub_links:
            if link.is_mailto():
                return True
        return False

    def get_mailto_unsub_link(self):
        """

        """
        for link in self.unsub_links:
            if link.is_mailto():
                return link.action_link()
        return None

    def do_unsubscribe(self, user_email, gmail_service):
        """
        Makes request to unsub from sender.
        Prefers mailto method. If mailto method not available, try http method with both GET and POST
        """
        logging.info('Processing unsubscribe from {}'.format(self.email))
        if self.has_mailto_link():
            print('A')
            mailto_unsub_link = self.get_mailto_unsub_link()
            message = create_message(
                user_email,
                mailto_unsub_link,
                'unsubscribe',
                'This message was automatically generated by Gmail with my custom python script'
            )
            send_message(gmail_service, 'me', message)
        else:
            print('B')
            # make both http GET and POST to list of unsub links
            try:
                for link in self.unsub_links:
                    print(link.action_link())
                    requests.get(link.action_link())
                    requests.post(link.action_link())
            except (Exception, ConnectionRefusedError) as e:
                print('C')
                logging.error('Connection error unsubscribing from {}'.format(link.action_link()))


class UnsubscribeLink(object):
    """
    Represents an unsubscribe link
    """

    def __init__(self, link):
        """
        Parses and clean raw link
        <mailto:GVSDM53CMRRVI5BTKIWVUTLZKB3G442UK53T2PI=.5225.6819.9@unsub-ab.mktomail.com>
        """
        pattern = '<(.*?)>'
        if not re.search(pattern, link):
            # link not enclosed within brackets
            self.link = link
        else:
            self.link = re.search(pattern, link).group(1)

    def method(self):
        """
        Returns whether the link is mailto method or http method
        """
        protocal = self.link[0:self.link.find(':')]
        return protocal        

    def is_mailto(self):
        return self.method() == 'mailto'

    def is_http(self):
        return self.method() == 'http'

    def action_link(self):
        """
        Returns link to operate the unsubscribe operation
        """
        if self.is_mailto():
            if self.link[-1] == '>':
                return self.link[self.link.find(':')+1:-1]
            else:
                return self.link[self.link.find(':')+1:]
        else:
            return self.link


class Headers(object):
    """
    Handles a collection of headers
    """

    def __init__(self, headers):
        """
        headers: list of header objects
        """
        self.data = {}
        for header in headers:
            k = snakecase(header['name'])
            v = header['value']
            self.data[k] = v

    def __contains__(self, item):
        return item in self.data

    def __getitem__(self, item):
        if type(item) is not str:
            raise TypeError
        elif item not in self.data:
            raise KeyError('{} not in headers'.format(item))
        else:
            return self.data[item]

    def unsubscribable(self):
        """
        Returns True if 'list_unsubscribe' is in header
        """
        if 'list_unsubscribe' in self:
            return True
        return False

    def get_sender_name(self):
        """
        method to retrieve the sender name by parsing the FROM field
        """
        unparsed_name = self.data['from']
        return unparsed_name[0:unparsed_name.find('<') - 1]

    def get_sender_email(self):
        """
        Returns sender's email as string
        """
        try:
            pattern = '<(.*?)>'
            return re.search(pattern, self.data['from']).group(1)
        except AttributeError as e:
            msg ='cannot parse sender email with conventional pattern - guessing it is {}'.format(self.data['from'])
            logging.warning(msg)
            # Some FROM header only has the following format
            # {'from': 'autotrader-messages@blinker.com'}
            return self.data['from']

    def get_list_of_unsub_links(self):
        """
        parses the value of List-Unsubscibe and returns
        a list of links
        """
        unparsed_list = self.data['list_unsubscribe']
        links = unparsed_list.split(', ')
        return [UnsubscribeLink(link) for link in links]
