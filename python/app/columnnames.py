class ColumnNames():
    def __init__(self):
        self._nice_names = ('Thumbnail', 'Published', 'Name', 'Version', 'Type', 'Department', 'Last Modified')
        self._prog_names = ('thumb', 'pub', 'name', 'ver', 'type', 'depart', 'modif')
    def index_name(self, name):
        return self._prog_names.index(name)
    def name_to_nice(self, name):
        return self._nice_names[self._prog_names.index(name)]
    def get_nice_names(self):
        return self._nice_names
