import re

from caseconverter import snakecase


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

    def type(self):
        """
        Returns whether the link is mailto type or http type
        """
        protocal = self.link[0:self.link.find(':')]
        return protocal        

    def is_mailto(self):
        return True if self.type == 'mailto' else False

    def is_http(self):
        return True if self.type == 'http' else False

    def action_link(self):
        """
        Returns link to operate the unsubscribe operation
        """
        if self.is_mailto():
            pattern = '/:([\s\S]*)$/'
            return re.match(pattern, self.link)
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
        pattern = '<(.*?)>'
        return re.search(pattern, self.data['from']).group(1)

    def get_list_of_unsub_links(self):
        """
        parses the value of List-Unsubscibe and returns
        a list of links
        """
        unparsed_list = self.data['list_unsubscribe']
        links = unparsed_list.split(', ')
        return [UnsubscribeLink(link) for link in links]

