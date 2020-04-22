import os

from sgtk.platform.qt import QtCore, QtGui

class IconManager(QtGui.QPixmapCache):
    def __init__(self, column_names, image_types, movie_types):
        super(IconManager, self).__init__()
        self._column_names = column_names
        self._image_types = image_types
        self._movie_types = movie_types

        self._label_height = 25
        self._thumb_dict = {}

        thumb_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "resources"))
        thumb_files = ['alembic', 'clipboard', 'geometry', 'houdini', 'image', 'maya', 'nuke', 'obj', 'openvdb', 'refresh', 'video']

        for thumb in thumb_files:
            image = QtGui.QPixmap(os.path.join(thumb_path, '{}.png'.format(thumb)))
            key = self.insert(image.scaledToHeight(self._label_height, QtCore.Qt.SmoothTransformation))

            self._thumb_dict[thumb] = key

    def get_pixmap(self, name):
        if name in self._thumb_dict.keys():
            return self.find(self._thumb_dict[name])
        return None

    def get_icon_name(self, ext):
        thumb = None
        if ext == 'abc':
            thumb = 'alembic'
        elif ext == 'sc':
            thumb = 'geometry'
        elif ext == 'hip':
            thumb = 'houdini'
        elif ext in self._image_types:
            thumb = 'image'
        elif ext == 'ma':
            thumb = 'maya'
        elif ext == 'nk':
            thumb = 'nuke'
        elif ext == 'obj':
            thumb = 'obj'
        elif ext == 'vdb':
            thumb = 'openvdb'
        elif ext in self._movie_types:
            thumb = 'video'

        return thumb

    def set_icon(self, item):
        current_icon = item.icon(self._column_names.index_name('thumb'))
        if not current_icon:
            thumb = self.get_icon_name(item.get_type())
            if thumb:
                item.setIcon(self._column_names.index_name('thumb'), QtGui.QIcon(self.get_pixmap(thumb)))
    def set_icons(self, item):
        for child_index in range(item.childCount()):
            child = item.child(child_index)

            self.set_icon(child)