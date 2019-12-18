import sgtk

from sgtk.platform.qt import QtCore, QtGui

import os
import sys
from datetime import datetime

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

        # most of the useful accessors are available through the Application class instance
        # it is often handy to keep a reference to this. You can get it via the following method:
        self._current_sgtk = sgtk.platform.current_bundle()

        # Get all Managers
        self._column_names = ColumnNames()
        self._cache_manager = CacheManager(self, self._current_sgtk)
        self._project_manager = ProjectManager(self._current_sgtk)
        self._icon_manager = IconManager()

        # Setup UI
        self._setup_ui()
        self._fill_projects()
        self._fill_filters()

    ############################################################################
    # UI methods

    def _setup_ui(self):
        self.setWindowTitle('Shotgun Explorer')

        # Top lout
        upper_bar = QtGui.QHBoxLayout()
        title_lab = QtGui.QLabel('Project Explorer')
        refresh_but = QtGui.QPushButton()
        refresh_but.setFixedSize(25, 25)
        icon = QtGui.QIcon(self._icon_manager.get_pixmap('refresh.png'))
        refresh_but.setIcon(icon)
        refresh_but.clicked.connect(self._refresh)
        
        upper_bar.addWidget(title_lab)
        upper_bar.addWidget(refresh_but)
        
        # Side layout
        main_splitter = QtGui.QSplitter(QtCore.Qt.Horizontal)
        side_bar = QtGui.QVBoxLayout()

        self._project_combo = QtGui.QComboBox()
        self._project_combo.currentIndexChanged.connect(self._change_project)

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

        side_bar.addWidget(self._project_combo)
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
        self._tree_widget.header().setMinimumSectionSize(100)

        self._tree_widget.setSortingEnabled(True)
        self._tree_widget.header().setSortIndicatorShown(True)
        self._tree_widget.header().setSectionsClickable(True)
        self._tree_widget.header().setSortIndicator(self._column_names.index_name('modif'), QtCore.Qt.DescendingOrder)

        self._tree_widget.itemDoubleClicked.connect(self._tree_item_double_clicked)
        self._tree_widget.itemExpanded.connect(self._item_expanded)

        tree_layout.addWidget(self._search_bar)
        tree_layout.addWidget(self._tree_widget)

        splitter_tree_widget = QtGui.QWidget()
        splitter_tree_widget.setLayout(tree_layout)

        # Detail layout

        splitter_detail_widget = QtGui.QWidget()
        # splitter_detail_widget.setLayout(detail_layout)

        main_splitter.addWidget(splitter_side_bar_widget)
        main_splitter.addWidget(splitter_tree_widget)
        main_splitter.addWidget(splitter_detail_widget)
        main_splitter.setStretchFactor(1, 10)

        # Create final layout
        self.setLayout(QtGui.QVBoxLayout())
        self.layout().addLayout(upper_bar)
        self.layout().addWidget(main_splitter)

    def _change_project(self):
        self._shot_list_widget.clear()
        current_project = self._project_combo.currentText()
        
        shots = self._project_manager.get_new_project(current_project)
        shots.sort()
        self._shot_list_widget.addItems(shots)

    def _fill_treewidget(self):
        self._tree_widget.invisibleRootItem().takeChildren()

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
        self._cache_manager.get_caches(self._shot_list_widget.currentItem().text(), steps, type_filter, self._search_bar.text())

        self._tree_widget.header().resizeSections(QtGui.QHeaderView.ResizeToContents)

    def _refresh(self):
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
        path = item.get_path()

        if path[-3:] == 'exr' or path[-3:] == 'jpg':
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

    def _item_expanded(self, item):
        new_items = item.item_expand()

        if new_items:
            for new_item in new_items:
                self._set_item_icon(new_item)
        elif not item.childCount():
            item.setChildIndicatorPolicy(QtGui.QTreeWidgetItem.DontShowIndicator)

    ############################################################################
    # Public methods

    def add_item_to_tree(self, cache_dict):
        item = TreeItem(cache_dict['path'], cache_dict['fields'], self._column_names)
        self._tree_widget.addTopLevelItem(item)
        self._set_item_icon(item)

    ############################################################################
    # Private methods
    
    def _set_item_icon(self, item):
        ext = item.get_path().split('.')[-1]
        thumb = None
        if ext == 'abc':
            thumb = 'alembic.png'
        elif ext == 'sc':
            thumb = 'geometry.png'
        elif ext == 'hip':
            thumb = 'houdini.png'
        elif ext == 'exr':
            thumb = 'image.png'
        elif ext == 'ma':
            thumb = 'maya.png'
        elif ext == 'nk':
            thumb = 'nuke.png'
        elif ext == 'obj':
            thumb = 'obj.png'
        elif ext == 'vdb':
            thumb = 'openvdb.png'
        elif ext == 'mov':
            thumb = 'video.png'

        if thumb:
            pixmap = self._icon_manager.get_pixmap(thumb)

            thumbnail = QtGui.QLabel("", self._tree_widget)
            thumbnail.setAlignment(QtCore.Qt.AlignHCenter)
            thumbnail.setPixmap(pixmap)
            self._tree_widget.setItemWidget(item, self._column_names.index_name('thumb'), thumbnail)
            self._tree_widget.header().resizeSections(QtGui.QHeaderView.ResizeToContents)

    def _fill_projects(self):
        self._project_combo.clear()

        projects = self._project_manager.get_projects()
        projects.sort()

        self._project_combo.addItems(projects)
        self._project_combo.setCurrentText(self._project_manager.get_current_project())

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

        self._type_list_widget.setFixedHeight(35)
    
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

class ProjectManager():
    def __init__(self, app):
        self._current_sgtk = app
        
        # Only works when a context is available!
        self._current_project = self._current_sgtk.context.project['name']

        # Toolkit Manager
        # sa = sgtk.authentication.ShotgunAuthenticator()
        # current_user = sa.get_user()
        # self._tk_manager = sgtk.bootstrap.ToolkitManager(current_user)

        # Get all Projects
        self._projects = {}
        for project in self._current_sgtk.shotgun.find('Project', [], ['name']):
            project_name = project['name']
            project.pop('name', None)
            
            self._projects[project_name] = project

    def get_new_project(self, current_project):
        # Just find the new shots (this should be changed by changing the toolkit object, sent mail to support)
        shotgun_shots = self._current_sgtk.shotgun.find("Shot", [['project.Project.name', 'is', current_project]], ['code'])

        shots = []
        for shot in shotgun_shots:
            shots.append(shot['code'])

        return shots

        # config = self._tk_manager.get_pipeline_configurations(self._projects[current_project])
        # if len(config) and 'descriptor' in config[0].keys():
        #     descriptor = config[0]['descriptor']

        #     self._current_sgtk = sgtk.sgtk_from_path(descriptor.get_path())

        #     shotgun_shots = self._current_sgtk.shotgun.find("Shot", [['project.Project.name', 'is', current_project]], ['code'])

        #     shots = []
        #     for shot in shotgun_shots:
        #         shots.append(shot['code'])

        #     self._current_project = current_project
        #     return shots
        # else:
        #     self._current_sgtk.log_error('Could not find sgtk config for %s' % self._projects[current_project])
        #     return None
    
    def get_current_project(self):
        return self._current_project

    def get_projects(self):
        return self._projects.keys()

class CacheManager():
    def __init__(self, dialog, app):
        self._dialog = dialog
        self._app = app

        self._2d_cache_dict = {}
        self._3d_cache_dict = {}

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
            if extension == 'exr' or extension == 'jpg':
                self._2d_templates.append(template_dict)
            else:
                self._3d_templates.append(template_dict)

    def clear_cache(self):
        self._2d_cache_dict.clear()
        self._3d_cache_dict.clear()

    def get_caches(self, shot, step_filters, type_filters, search_text):
        for step, enabled in step_filters.items():
            if enabled:
                ui_fields = {
                'Shot': shot,
                'Step': step}
                
                if type_filters['2D']:
                    if step in self._2d_cache_dict:
                        self._add_cached_cache_to_gui(self._2d_cache_dict[step], search_text)
                    else:
                        self._2d_cache_dict[step] = self._caches_from_templates(self._2d_templates, ui_fields, search_text)
                if type_filters['3D']:
                    if step in self._3d_cache_dict:
                        self._add_cached_cache_to_gui(self._3d_cache_dict[step], search_text)
                    else:
                        self._3d_cache_dict[step] = self._caches_from_templates(self._3d_templates, ui_fields, search_text)
                    
    def _caches_from_templates(self, templates, ui_fields, search_text):
        caches = []
        for template_dict in templates:
            template = template_dict['cache_template']
            cache_paths = self._app.sgtk.abstract_paths_from_template(template, ui_fields)
            for cache_path in cache_paths:
                fields = template.get_fields(cache_path)
                fields['templates'] = template_dict

                new_cache_dict = {'path': cache_path, 'fields': fields}
                caches.append(new_cache_dict)
                if not search_text or (search_text and search_text in cache_path):
                    self._dialog.add_item_to_tree(new_cache_dict)
        return caches
    
    def _add_cached_cache_to_gui(self, cache_dict, search_text):
        for cache in cache_dict:
            if not search_text or (search_text and search_text in cache['path']):
                self._dialog.add_item_to_tree(cache)

class IconManager(QtGui.QPixmapCache):
    def __init__(self):
        super(IconManager, self).__init__()
        self._label_height = 25
        self._thumb_dict = {}

        thumb_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "resources"))
        thumb_files = ['alembic.png', 'geometry.png', 'houdini.png', 'image.png', 'maya.png', 'nuke.png', 'obj.png', 'openvdb.png', 'refresh.png', 'video.png']

        for thumb in thumb_files:
            image = QtGui.QPixmap(os.path.join(thumb_path, thumb))
            key = self.insert(image.scaledToHeight(self._label_height, QtCore.Qt.SmoothTransformation))

            self._thumb_dict[thumb] = key

    def get_pixmap(self, name):
        if name in self._thumb_dict.keys():
            return self.find(self._thumb_dict[name])
        return None

class TreeItem(QtGui.QTreeWidgetItem):
    def __init__(self, path, fields, column_names):
        super(TreeItem, self).__init__()
        self._fields = fields
        self._path = path
        self._column_names = column_names
        self._item_expanded = False
        
        if 'templates' in self._fields.keys():
            self.setChildIndicatorPolicy(QtGui.QTreeWidgetItem.ShowIndicator)

        self.setText(self._column_names.index_name('name'), os.path.basename(self._path).split('.')[0])
        self.setText(self._column_names.index_name('ver'), str(fields['version']).zfill(3))
        self.setText(self._column_names.index_name('type'), self._path.split('.')[-1])
        self.setText(self._column_names.index_name('depart'), str(fields['Step']))

        # Last modified
        time = os.path.getctime(os.path.dirname(self._path))
        date_time = datetime.utcfromtimestamp(time).strftime('%Y-%m-%d %H:%M:%S')
        self.setText(self._column_names.index_name('modif'), date_time)

    def _create_child_item(self, path, fields):
        item = TreeItem(path, fields, self._column_names)
        self.addChild(item)
        return item

    def get_path(self):
        return self._path

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
