from caseconverter import snakecase


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
