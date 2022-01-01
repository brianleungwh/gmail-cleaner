class Headers(object):

    def __init__(self, headers):
        """
        headers: list of header objects
        """
        # set attrs to self
        self._data = {}
        for header in headers:
            k = header['name']
            v = header['value']

            self._data[k] = v

    def has_list_unsubscribe(self):
        if 'List-Unsubscribe' in self._data:
            return True
        return False

    def __setitem__(self, header_name, header_value):
        pass

    @property
    def get_from(self):
        try:
            return self._data['From']
        except KeyError as e:
            return self._data['from']

    @property
    def get_unsub_link(self):
        return self._data['List-Unsubscribe']
