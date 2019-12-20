import sgtk

from sgtk.platform.qt import QtCore, QtGui

import os
import sys
import pyseq
from datetime import datetime
import collections
import glob

class AppDialog(QtGui.QWidget):
    @property
    def hide_tk_title_bar(self):
        """
        Tell the system to not show the std toolbar
        """
        return True

    def __init__(self, parent=None):
        # first, call the base class and let it do its thing.
        QtGui.QWidget.__init__(self, parent)

        self.image_types = ('exr', 'jpg', 'dpx', 'png', 'tiff')

        # most of the useful accessors are available through the Application class instance
        # it is often handy to keep a reference to this. You can get it via the following method:
        self._current_sgtk = sgtk.platform.current_bundle()

        # Get all Managers
        self._column_names = ColumnNames()
        self._cache_manager = CacheManager(self, self._current_sgtk, self._column_names)
        self._icon_manager = IconManager()

        # Setup UI
        self._setup_ui()
        self._fill_shots()
        self._fill_filters()

        # Load async icon loader
        self._icon_loader = LoadIcons(self._tree_widget, self._icon_manager, self._column_names, self.image_types)
        self._icon_thread = QtCore.QThread()
        self._icon_loader.moveToThread(self._icon_thread)

        self._icon_thread.started.connect(self._icon_loader.start_icon_loop)
        
    ############################################################################
    # UI methods

    def _setup_ui(self):
        self.setWindowTitle('Shotgun Explorer')

        # Top lout
        upper_bar = QtGui.QHBoxLayout()
        title_lab = QtGui.QLabel('Project Explorer')
        refresh_but = QtGui.QPushButton()
        refresh_but.setFixedSize(25, 25)
        refresh_but.setIcon(QtGui.QIcon(self._icon_manager.get_pixmap('refresh')))
        refresh_but.clicked.connect(self._refresh)
        
        upper_bar.addWidget(title_lab)
        upper_bar.addWidget(refresh_but)
        
        # Side layout
        main_splitter = QtGui.QSplitter(QtCore.Qt.Horizontal)
        side_bar = QtGui.QVBoxLayout()

        project_label = QtGui.QLabel(self._current_sgtk.context.project['name'])

        self._shot_list_widget = QtGui.QListWidget()
        self._shot_list_widget.itemClicked.connect(self._refresh)

        filter_widget = QtGui.QLabel('Filters')
        
        self._step_list_widget = QtGui.QListWidget()
        self._step_list_widget.itemChanged.connect(self._fill_treewidget)

        filter_buttons = QtGui.QHBoxLayout()

        all_button = QtGui.QPushButton('All')
        all_button.clicked.connect(self._select_all_filters)
        none_button = QtGui.QPushButton('None')
        none_button.clicked.connect(self._select_no_filters)

        filter_buttons.addWidget(all_button)
        filter_buttons.addWidget(none_button)

        self._type_list_widget = QtGui.QListWidget()
        self._type_list_widget.itemChanged.connect(self._fill_treewidget)

        side_bar.addWidget(project_label)
        side_bar.addWidget(self._shot_list_widget)
        side_bar.addWidget(filter_widget)
        side_bar.addWidget(self._step_list_widget)
        side_bar.addLayout(filter_buttons)
        side_bar.addWidget(self._type_list_widget)

        side_bar.setStretchFactor(self._shot_list_widget, 20)

        splitter_side_bar_widget = QtGui.QWidget()
        splitter_side_bar_widget.setLayout(side_bar)

        # Tree layout
        tree_layout = QtGui.QVBoxLayout()
        self._search_bar = QtGui.QLineEdit()
        self._search_bar.setPlaceholderText('Search')
        self._search_bar.returnPressed.connect(self._fill_treewidget)

        self._tree_widget = QtGui.QTreeWidget()

        self._tree_widget.setColumnCount(1)
        self._tree_widget.setHeaderLabels(self._column_names.get_nice_names())
        self._tree_widget.setSelectionMode(QtGui.QAbstractItemView.SelectionMode.SingleSelection)
        self._tree_widget.header().setSectionsMovable(False)
        self._tree_widget.header().resizeSections(QtGui.QHeaderView.ResizeToContents)

        self._tree_widget.setSortingEnabled(True)
        self._tree_widget.header().setSortIndicatorShown(True)
        self._tree_widget.header().setSectionsClickable(True)
        self._tree_widget.header().setSortIndicator(self._column_names.index_name('modif'), QtCore.Qt.DescendingOrder)

        self._tree_widget.itemDoubleClicked.connect(self._tree_item_double_clicked)
        self._tree_widget.itemExpanded.connect(self._item_expanded)
        self._tree_widget.itemClicked.connect(self._item_clicked)

        tree_layout.addWidget(self._search_bar)
        tree_layout.addWidget(self._tree_widget)

        splitter_tree_widget = QtGui.QWidget()
        splitter_tree_widget.setLayout(tree_layout)

        # Detail layout

        splitter_detail_widget = QtGui.QWidget()
        splitter_detail_widget.setMinimumWidth(250)

        detail_layout = QtGui.QVBoxLayout()
        detail_layout.setAlignment(QtCore.Qt.AlignTop)
        self._detail_icon = QtGui.QLabel()
        self._detail_icon.setAlignment(QtCore.Qt.AlignHCenter)

        # Actions
        self._detail_copy_path = QtGui.QPushButton()
        self._detail_copy_path.setFixedSize(25, 25)
        self._detail_copy_path.setIcon(QtGui.QIcon(self._icon_manager.get_pixmap('clipboard')))
        self._detail_copy_path.clicked.connect(self._detail_copy_path_clipboard)
        self._detail_copy_path.setEnabled(False)

        self._detail_open_images = QtGui.QPushButton()
        self._detail_open_images.setFixedSize(25, 25)
        self._detail_open_images.setIcon(QtGui.QIcon(self._icon_manager.get_pixmap('image')))
        self._detail_open_images.clicked.connect(self._detail_open_rv)
        self._detail_open_images.setEnabled(False)

        self._detail_open_video = QtGui.QPushButton()
        self._detail_open_video.setFixedSize(25, 25)
        self._detail_open_video.setIcon(QtGui.QIcon(self._icon_manager.get_pixmap('video')))
        self._detail_open_video.clicked.connect(self._detail_open_rv)
        self._detail_open_video.setEnabled(False)

        self._detail_open_nuke = QtGui.QPushButton()
        self._detail_open_nuke.setFixedSize(25, 25)
        self._detail_open_nuke.setIcon(QtGui.QIcon(self._icon_manager.get_pixmap('nuke')))
        self._detail_open_nuke.setEnabled(False)
        
        self._detail_open_maya = QtGui.QPushButton()
        self._detail_open_maya.setFixedSize(25, 25)
        self._detail_open_maya.setIcon(QtGui.QIcon(self._icon_manager.get_pixmap('maya')))
        self._detail_open_maya.setEnabled(False)

        self._detail_open_hou = QtGui.QPushButton()
        self._detail_open_hou.setFixedSize(25, 25)
        self._detail_open_hou.setIcon(QtGui.QIcon(self._icon_manager.get_pixmap('houdini')))
        self._detail_open_hou.setEnabled(False)

        detail_buttons = QtGui.QHBoxLayout()
        detail_buttons.addWidget(self._detail_copy_path)
        detail_buttons.addWidget(self._detail_open_images)
        detail_buttons.addWidget(self._detail_open_video)
        detail_buttons.addWidget(self._detail_open_nuke)
        detail_buttons.addWidget(self._detail_open_maya)
        detail_buttons.addWidget(self._detail_open_hou)

        self._detail_form_layout = QtGui.QFormLayout()

        self._detail_dict = collections.OrderedDict([
            ('Name', None),
            ('Version', None),
            ('Type', None),
            ('Range', None),
            ('Department', None),
            ('Modified', None),
            ('Path', None)
        ])
        
        for key in self._detail_dict:
            label = QtGui.QLabel()
            label.setWordWrap(True)
            self._detail_dict[key] = label

            self._detail_form_layout.addRow(key, self._detail_dict[key])

        detail_layout.addWidget(self._detail_icon)
        detail_layout.addLayout(detail_buttons)
        detail_layout.addLayout(self._detail_form_layout)
        
        splitter_detail_widget.setLayout(detail_layout)

        main_splitter.addWidget(splitter_side_bar_widget)
        main_splitter.addWidget(splitter_tree_widget)
        main_splitter.addWidget(splitter_detail_widget)
        main_splitter.setStretchFactor(1, 10)

        # Create final layout
        self.setLayout(QtGui.QVBoxLayout())
        self.layout().addLayout(upper_bar)
        self.layout().addWidget(main_splitter)

    def _fill_treewidget(self):
        current_item = self._shot_list_widget.currentItem()

        if current_item:
            # Filters
            steps = {}
            for index in range(self._step_list_widget.count()):
                item = self._step_list_widget.item(index)
                steps[item.text()] = bool(item.checkState())
            
            type_filter = {}
            for index in range(self._type_list_widget.count()):
                item = self._type_list_widget.item(index)
                type_filter[item.text()] = bool(item.checkState())

            # Get caches
            self._cache_manager.get_caches(current_item.text(), steps, type_filter, self._search_bar.text())
            
            if self._icon_thread.isRunning():
                self._icon_thread.terminate()
            self._icon_thread.start()

    def _refresh(self):
        # Reset Detail Tab
        self._detail_icon.setPixmap(None)

        self._detail_copy_path.setEnabled(False)
        self._detail_open_images.setEnabled(False)
        self._detail_open_video.setEnabled(False)
        self._detail_open_nuke.setEnabled(False)
        self._detail_open_maya.setEnabled(False)
        self._detail_open_hou.setEnabled(False)

        for key in self._detail_dict:
            self._detail_dict[key].setText('')

        # Reset Tree Widget
        self._tree_widget.invisibleRootItem().takeChildren()
        self._cache_manager.clear_cache()
        self._fill_treewidget()

    def _select_all_filters(self):
        self._step_list_widget.itemChanged.disconnect()
        for index in range(self._step_list_widget.count()):
            self._step_list_widget.item(index).setCheckState(QtCore.Qt.Checked)
        self._step_list_widget.itemChanged.connect(self._fill_treewidget)
       
        self._fill_treewidget()

    def _select_no_filters(self):
        self._step_list_widget.itemChanged.disconnect()
        for index in range(self._step_list_widget.count()):
            self._step_list_widget.item(index).setCheckState(QtCore.Qt.Unchecked)
        self._step_list_widget.itemChanged.connect(self._fill_treewidget)

        self._fill_treewidget()

    def _tree_item_double_clicked(self, item, column):
        if item.get_type() in self.image_types:
            self._open_rv(item.get_path())

    def _item_expanded(self, item):
        new_items = item.item_expand()

        # Set icons for new items or remove the expand indicator
        if new_items:
            for new_item in new_items:
                self._icon_loader.set_item_icon(new_item)
            self._tree_widget.header().resizeSections(QtGui.QHeaderView.ResizeToContents)
        elif not item.childCount():
            item.setChildIndicatorPolicy(QtGui.QTreeWidgetItem.DontShowIndicator)

    def _item_clicked(self, item, column):
        if not isinstance(item, TreeItem):
            item = item.get_latest_child()

        # Check if it has more info
        self._item_expanded(item)

        # Set detail icon
        current_icon = item.icon(self._column_names.index_name('thumb'))
        if current_icon:
            thumb = self._icon_loader.get_icon_name(item.get_type())
            if thumb:
                self._detail_icon.setPixmap(self._icon_manager.get_pixmap(thumb))

        # Enable correct buttons
        self._detail_copy_path.setEnabled(True)
        self._detail_open_images.setEnabled(False)
        self._detail_open_video.setEnabled(False)
        self._detail_open_nuke.setEnabled(False)
        self._detail_open_maya.setEnabled(False)
        self._detail_open_hou.setEnabled(False)

        items = [item]
        for child_index in range(item.childCount()):
            items.append(item.child(child_index))

        for element in items:
            element_type = element.get_type()

            if element_type in self.image_types:
                self._detail_open_images.setEnabled(True)
            elif element_type == 'mov':
                self._detail_open_video.setEnabled(True)
            elif element_type == 'nk':
                self._detail_open_nuke.setEnabled(True)
            elif element_type == 'ma':
                self._detail_open_maya.setEnabled(True)
            elif element_type == 'hip':
                self._detail_open_hou.setEnabled(True)

        # Set detail Form
        properties = item.get_properties()

        for key in self._detail_dict:
            if key.lower() in properties.keys():
                # Replace path with slashes with slash and spaces for wordwrap to work
                text = properties[key.lower()]
                text_parts = text.split(os.sep)
                text_parts = text_parts[-4:]
                text = os.sep.join(text_parts).replace(os.sep, '%s ' % os.sep)
                text = text.replace('_', ' _')
                self._detail_dict[key].setText(text)

        # Set Range if needed
        # to do check the sequence range
        if '%04d' in item.get_path():
            cache_range = 'Invalid Sequence Object!'
            sequences = pyseq.get_sequences(item.get_path().replace('%04d', '*'))
            if len(sequences):
                sequence = sequences[0]

                if sequence.missing():
                    cache_range = '[%s-%s], missing %s' % (sequence.format('%s'), sequence.format('%e'), sequence.format('%m'))
                else:
                    cache_range = sequence.format('%R')
            self._detail_dict['Range'].setText(cache_range)
        else:
            self._detail_dict['Range'].setText('Single')

    def _detail_copy_path_clipboard(self):
        clip_string = ''
        for item in self._tree_widget.selectedItems():
            clip_string += item.get_path()

        if clip_string:
            QtGui.QGuiApplication.clipboard().setText(clip_string)

    def _detail_open_rv(self):
        items = self._tree_widget.selectedItems()

        if len(items) and items[0].get_type() in self.image_types:
            self._open_rv(items[0].get_path())

    def _open_rv(self, path):
        process = QtCore.QProcess(self)

        # run the app
        system = sys.platform
        if system == "linux2":
            program = 'rv'
        elif system == 'win32':
            program = 'C:/Program Files/Shotgun/RV-7.2.6/bin/rv.exe'
        else:
            msg = "Platform '%s' is not supported." % (system)
            self._current_sgtk.log_error(msg)
            return

        process.startDetached(program, [path])
        process.close()
    
    ############################################################################
    # Public methods

    def add_item_to_tree(self, item):
        self._tree_widget.addTopLevelItem(item)

    ############################################################################
    # Private methods
    
    def _fill_shots(self):
        current_project = self._current_sgtk.context.project['name']
        shotgun_shots = self._current_sgtk.shotgun.find("Shot", [['project.Project.name', 'is', current_project]], ['code'])

        shots = []
        for shot in shotgun_shots:
            shots.append(shot['code'])
        shots.sort()

        self._shot_list_widget.addItems(shots)

    def _fill_filters(self):
        # Step List
        shotgun_list = self._current_sgtk.shotgun.find("Step", [], ['code'])
        step_list = []
        for step in shotgun_list:
            step_list.append(step['code'])
        step_list.sort()

        for step in step_list:
            check_box = QtGui.QListWidgetItem()
            check_box.setText(step)
            check_box.setFlags(check_box.flags() | QtCore.Qt.ItemIsUserCheckable)
            check_box.setCheckState(QtCore.Qt.Checked)

            self._step_list_widget.addItem(check_box)

        # Type List (2D or 3D)
        type_list = ['2D', '3D']

        for filter_item in type_list:
            check_box = QtGui.QListWidgetItem()
            check_box.setText(filter_item)
            check_box.setFlags(check_box.flags() | QtCore.Qt.ItemIsUserCheckable)
            check_box.setCheckState(QtCore.Qt.Checked)

            self._type_list_widget.addItem(check_box)

        self._type_list_widget.setFixedHeight(len(type_list) * 20)
    
class ColumnNames():
    def __init__(self):
        self._nice_names = ['Thumbnail', 'Name', 'Version', 'Type', 'Department', 'Last Modified']
        self._prog_names = ['thumb', 'name', 'ver', 'type', 'depart', 'modif']
    def index_name(self, name):
        return self._prog_names.index(name)
    def name_to_nice(self, name):
        return self._nice_names[self._prog_names.index(name)]
    def get_nice_names(self):
        return self._nice_names

class CacheManager():
    def __init__(self, dialog, app, column_names):
        self._dialog = dialog
        self._app = app
        self._column_names = column_names

        self._2d_item_dict = {}
        self._3d_item_dict = {}

        self._2d_templates = []
        self._3d_templates = []
        for output_profile in self._app.get_setting("templates", []):
            cache_template = self._app.get_template_by_name(output_profile['cache_template'])

            work_template = ''
            if output_profile['work_template']:
                work_template = self._app.get_template_by_name(output_profile['work_template'])
            preview_template = ''
            if output_profile['preview_template']:
                preview_template = self._app.get_template_by_name(output_profile['preview_template'])
            
            template_dict = {'cache_template': cache_template, 'work_template': work_template, 'preview_template': preview_template}

            extension = cache_template.definition.split('.')[-1]
            if extension in self._dialog.image_types:
                self._2d_templates.append(template_dict)
            else:
                self._3d_templates.append(template_dict)

    ############################################################################
    # Public methods

    def clear_cache(self):
        self._2d_item_dict.clear()
        self._3d_item_dict.clear()

    def get_caches(self, shot, step_filters, type_filters, search_text):
        for step, enabled in step_filters.items():
            ui_fields = {
                'Shot': shot,
                'Step': step}
            
            if enabled and type_filters['2D']:
                if step in self._2d_item_dict:
                    self._set_hidden(False, self._2d_item_dict[step], search_text)
                elif enabled:
                    self._2d_item_dict[step] = self._caches_from_templates(self._2d_templates, ui_fields, search_text)
            elif step in self._2d_item_dict:
                self._set_hidden(True, self._2d_item_dict[step], search_text)

            if enabled and type_filters['3D']:
                if step in self._3d_item_dict:
                    self._set_hidden(False, self._3d_item_dict[step], search_text)
                elif enabled:
                    self._3d_item_dict[step] = self._caches_from_templates(self._3d_templates, ui_fields, search_text)
            elif step in self._3d_item_dict:
                self._set_hidden(True, self._3d_item_dict[step], search_text)
    
    ############################################################################
    # Private methods

    def _caches_from_templates(self, templates, ui_fields, search_text):
        items = []
        for template_dict in templates:
            template = template_dict['cache_template']

            cache_paths = self._app.sgtk.abstract_paths_from_template(template, ui_fields)
            cache_paths.sort()
            top_level_item = None
            for cache_path in cache_paths:
                fields = template.get_fields(cache_path)
                fields['templates'] = template_dict

                fields_no_ver = fields.copy()
                fields_no_ver.pop('version', None)

                if not top_level_item or top_level_item.get_generic_fields() != fields_no_ver:
                    # Only add top level item if it has children
                    if top_level_item and top_level_item.childCount():
                        top_level_item.post_process()
                        self._dialog.add_item_to_tree(top_level_item)
                        items.append(top_level_item)
                        
                    top_level_item = TopLevelTreeItem(cache_path, fields_no_ver, self._column_names)
                
                # Check if valid cache (remove duplicates when checking with templates that have and don't have {SEQ} key)
                if ('%04d' in cache_path and len(glob.glob(cache_path.replace('%04d', '*')))) or os.path.exists(cache_path):
                    item = TreeItem(cache_path, fields, self._column_names)
                    top_level_item.addChild(item)
        return items
    
    def _set_hidden(self, hidden, cache_dict, search_text):
        for item in cache_dict:
            item.setHidden(hidden)
            
            if search_text and search_text not in item.get_path().lower():
                item.setHidden(True)

class IconManager(QtGui.QPixmapCache):
    def __init__(self):
        super(IconManager, self).__init__()
        self._label_height = 25
        self._thumb_dict = {}

        thumb_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "resources"))
        thumb_files = ['alembic', 'clipboard', 'geometry', 'houdini', 'image', 'maya', 'nuke', 'obj', 'openvdb', 'refresh', 'video']

        for thumb in thumb_files:
            image = QtGui.QPixmap(os.path.join(thumb_path, '%s.png' % thumb))
            key = self.insert(image.scaledToHeight(self._label_height, QtCore.Qt.SmoothTransformation))

            self._thumb_dict[thumb] = key

    def get_pixmap(self, name):
        if name in self._thumb_dict.keys():
            return self.find(self._thumb_dict[name])
        return None

class TopLevelTreeItem(QtGui.QTreeWidgetItem):
    def __init__(self, path, fields, column_names):
        super(TopLevelTreeItem, self).__init__()
        self._fields = fields
        self._column_names = column_names

    def post_process(self):
        children = []
        for child_index in range(self.childCount()):
            children.append(self.child(child_index))
        children = sorted(children, key=lambda k: k.get_properties()['version']) 

        self._latest_child = children[-1]
        child_properties = self._latest_child.get_properties()

        # Set GUI text columns
        self.setText(self._column_names.index_name('name'), child_properties['name'][:-5])
        self.setText(self._column_names.index_name('ver'), child_properties['version'])
        self.setText(self._column_names.index_name('type'), child_properties['type'])
        self.setText(self._column_names.index_name('depart'), child_properties['department'])
        self.setText(self._column_names.index_name('modif'), child_properties['modified'])

    def get_latest_child(self):
        return self._latest_child

    def get_generic_fields(self):
        return self._fields

    def item_expand(self):
        pass

    def get_path(self):
        return self._latest_child.get_path()

    def get_type(self):
        return self._latest_child.get_type()

    def get_properties(self):
        return self._latest_child.get_properties()

class TreeItem(TopLevelTreeItem):
    def __init__(self, path, fields, column_names):
        super(TreeItem, self).__init__(path, fields, column_names)
        self._item_expanded = False
        
        # Check if it can have children through templates
        if 'templates' in self._fields.keys():
            self.setChildIndicatorPolicy(QtGui.QTreeWidgetItem.ShowIndicator)
        
        # Last modified
        time = os.path.getctime(os.path.dirname(path))
        date_time = datetime.utcfromtimestamp(time).strftime('%Y-%m-%d %H:%M:%S')

        # Set item properties
        self._properties = {
            'name': os.path.basename(path).split('.')[0],
            'version': str(fields['version']).zfill(3),
            'type': path.split('.')[-1],
            'department': str(fields['Step']),
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
            added_items = []

            work_template = self._fields['templates']['work_template']
            if work_template:
                path = work_template.apply_fields(self._fields)
                fields = self._fields.copy()
                fields.pop('templates', None)

                added_items.append(self._create_child_item(path, fields))
        
            preview_template = self._fields['templates']['preview_template']
            if preview_template:
                path = preview_template.apply_fields(self._fields)
                fields = self._fields.copy()
                fields.pop('templates', None)

                added_items.append(self._create_child_item(path, fields))

            self._item_expanded = True
            return added_items

    def get_path(self):
        return self._properties['path']

    def get_type(self):
        return self._properties['type']

    def get_properties(self):
        return self._properties

class LoadIcons(QtCore.QObject):
    def __init__(self, tree_widget, icon_manager, column_names, image_types):
        super(LoadIcons, self).__init__()

        self._tree_widget = tree_widget
        self._icon_manager = icon_manager
        self._column_names = column_names
        self._image_types = image_types

    def start_icon_loop(self):
        self._set_icons(self._tree_widget.invisibleRootItem())
        self._tree_widget.header().resizeSections(QtGui.QHeaderView.ResizeToContents)
        self.thread().terminate()

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
        elif ext == 'mov':
            thumb = 'video'

        return thumb

    def set_item_icon(self, item):
        current_icon = item.icon(self._column_names.index_name('thumb'))
        if not current_icon:
            thumb = self.get_icon_name(item.get_type())
            if thumb:
                item.setIcon(self._column_names.index_name('thumb'), QtGui.QIcon(self._icon_manager.get_pixmap(thumb)))

    def _set_icons(self, item):
        for child_index in range(item.childCount()):
            child = item.child(child_index)

            self.set_item_icon(child)
            if child.childCount():
                self._set_icons(child)