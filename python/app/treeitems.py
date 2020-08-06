import os
from datetime import datetime

from sgtk.platform.qt import QtGui

class TopLevelTreeItem(QtGui.QTreeWidgetItem):
    def __init__(self, path, fields, column_names):
        super(TopLevelTreeItem, self).__init__()
        self._fields = fields
        self._column_names = column_names

    def post_process(self):
        self._find_latest_child()
        child_properties = self.get_properties()
        
        # Set GUI text columns
        self.setText(self._column_names.index_name('name'), child_properties['name'])
        self.setText(self._column_names.index_name('ver'), child_properties['version'])
        self.setText(self._column_names.index_name('type'), child_properties['type'])
        self.setText(self._column_names.index_name('depart'), child_properties['department'])
        self.setText(self._column_names.index_name('modif'), child_properties['modified'])

    def _find_latest_child(self):
        children = []
        for child_index in range(self.childCount()):
            children.append(self.child(child_index))
        children = sorted(children, key=lambda k: k.get_properties()['version'])

        self._latest_child = children[-1]
        return self._latest_child

    def get_latest_child(self):
        if not isinstance(self._latest_child, TreeItem):
            return self._latest_child.get_latest_child()
        return self._latest_child

    def get_fields(self):
        return self._fields

    def item_expand(self):
        for child_index in range(self.childCount()):
            self.child(child_index).item_expand()

    def get_path(self):
        return self._latest_child.get_path()

    def get_type(self):
        return self._latest_child.get_type()

    def get_published(self):
        return self._latest_child.get_published()

    def get_properties(self):
        return self._latest_child.get_properties()

class RenderTopLevelTreeItem(TopLevelTreeItem):
    def __init__(self, path, fields, column_names):
        super(RenderTopLevelTreeItem, self).__init__(path, fields, column_names)

    def _find_latest_child(self):
        if self._fields['isversion']:
            for child_index in range(self.childCount()):
                if self.child(child_index).get_properties()['name'] == 'RGBA':
                    self._latest_child = self.child(child_index)
                    break
        else:
            super(RenderTopLevelTreeItem, self)._find_latest_child()
  
        return self._latest_child

    def get_properties(self):
        properties = self._latest_child.get_properties().copy()
        properties['name'] = '{}_{}_{}_v{}'.format(self._fields['Shot'], self._fields['RenderLayer'], self._fields['Camera'], properties['version'])
        
        return properties

class TreeItem(QtGui.QTreeWidgetItem):
    def __init__(self, path, fields, column_names):
        super(TreeItem, self).__init__()

        self._fields = fields
        self._column_names = column_names
        self._item_expanded = False

        # Check if it can have children through templates
        if 'templates' in self._fields.keys() and len(self._fields['templates'].keys()) > 1:
            self.setChildIndicatorPolicy(QtGui.QTreeWidgetItem.ShowIndicator)

        # Last modified
        time = os.path.getctime(os.path.dirname(path))
        date_time = datetime.utcfromtimestamp(time).strftime('%Y-%m-%d %H:%M:%S')

        # Set item properties
        self._properties = {
            'name': os.path.basename(path).split('.')[0],
            'version': str(fields['version']).zfill(3),
            'type': path.split('.')[-1],
            'published': fields['published'],
            'department': fields['Step'],
            'modified': date_time,
            'path': path
        }

        # Set GUI text columns
        self.setText(self._column_names.index_name('name'), self._properties['name'])
        self.setText(self._column_names.index_name('ver'), self._properties['version'])
        self.setText(self._column_names.index_name('type'), self._properties['type'])
        self.setText(self._column_names.index_name('depart'), self._properties['department'])
        self.setText(self._column_names.index_name('modif'), self._properties['modified'])

    def _create_child_item(self, path, fields):
        item = TreeItem(path, fields, self._column_names)
        self.addChild(item)
        return item

    def item_expand(self):
        if 'templates' in self._fields.keys() and not self._item_expanded:
            work_templates = self._fields['templates']['work_template']
            if work_templates:
                for work_template in work_templates:
                    path = work_template.apply_fields(self._fields)
                    fields = self._fields.copy()
                    fields.pop('templates', None)

                    if os.path.exists(path):
                        self._create_child_item(path, fields)
                        break

            preview_template = self._fields['templates']['preview_template']
            if preview_template:
                path = preview_template.apply_fields(self._fields)
                fields = self._fields.copy()
                fields.pop('templates', None)
                
                if os.path.exists(path):
                    self._create_child_item(path, fields)

            self._item_expanded = True

        # Remove the expand indicator
        if not self.childCount():
            self.setChildIndicatorPolicy(QtGui.QTreeWidgetItem.DontShowIndicator)

    def get_path(self):
        return self._properties['path']

    def get_type(self):
        return self._properties['type']

    def get_published(self):
        return self._properties['published']

    def get_properties(self):
        return self._properties

class AovTreeItem(TreeItem):
    def __init__(self, path, fields, column_names):
        super(AovTreeItem, self).__init__(path, fields, column_names)

        self._properties['name'] = fields['AOV']
        self.setText(self._column_names.index_name('name'), self._properties['name'])
