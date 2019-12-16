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
        self._app = sgtk.platform.current_bundle()
        
        # Get all templates
        self._output_templates = []
        for output_profile in self._app.get_setting("templates", []):
            self._output_templates.append(output_profile)

        self._column_names = ColumnNames()

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
        icon = QtGui.QIcon(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "resources", "refresh.png")))
        refresh_but.setIcon(icon)
        refresh_but.clicked.connect(self._fill_treewidget)

        upper_bar.addWidget(title_lab)
        upper_bar.addWidget(refresh_but)
        
        # Side layout
        main_splitter = QtGui.QSplitter(QtCore.Qt.Horizontal)
        side_bar = QtGui.QVBoxLayout()

        self._project_combo = QtGui.QComboBox()
        self._project_combo.currentIndexChanged.connect(self._fill_shots)

        self._shot_list_widget = QtGui.QListWidget()
        self._shot_list_widget.itemClicked.connect(self._fill_treewidget)

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

        self._tree_widget = QtGui.QTreeWidget()

        self._tree_widget.setColumnCount(1)
        self._tree_widget.setHeaderLabels(self._column_names.get_nice_names())
        self._tree_widget.setSelectionMode(QtGui.QAbstractItemView.SelectionMode.ExtendedSelection)
        self._tree_widget.header().setSectionsMovable(False)
        self._tree_widget.header().resizeSections(QtGui.QHeaderView.ResizeToContents)
        self._tree_widget.header().setMinimumSectionSize(100)

        self._tree_widget.setSortingEnabled(True)
        self._tree_widget.header().setSortIndicatorShown(True)
        self._tree_widget.header().setSectionsClickable(True)
        self._tree_widget.header().setSortIndicator(self._column_names.index_name('modif'), QtCore.Qt.DescendingOrder)

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

    def _fill_shots(self):
        self._shot_list_widget.clear()

        current_project = self._project_combo.currentText()
        shotgun_shots = self._app.shotgun.find("Shot", [['project.Project.name', 'is', current_project]], ['code'])
        shots = []
        for shot in shotgun_shots:
            shots.append(shot['code'])
        shots.sort()
        self._shot_list_widget.addItems(shots)

    def _fill_treewidget(self):
        self._tree_widget.invisibleRootItem().takeChildren()
        step_selected = self._get_step_filter_selected()

        if self._shot_list_widget.currentItem() and len(step_selected) != 0:
            caches = []
            
            for step in step_selected:
                ui_fields = {
                'Shot': self._shot_list_widget.currentItem().text(),
                'Step': step}

                for template_dict in self._output_templates:
                    template = self._app.get_template_by_name(template_dict['cache_template'])

                    if self._type_filter(template):
                        cache_paths = self._app.sgtk.abstract_paths_from_template(template, ui_fields)
                        for cache_path in cache_paths:
                            fields = template.get_fields(cache_path)

                            caches.append({'path': cache_path, 'fields': fields})

            for cache in caches:
                item = TopLevelTreeItem(cache['path'], cache['fields'], self._column_names)
                self._tree_widget.addTopLevelItem(item)
                item.set_image()

            self._tree_widget.header().resizeSections(QtGui.QHeaderView.ResizeToContents)

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

    ############################################################################
    # Private methods

    def _fill_projects(self):
        self._project_combo.clear()

        current_project = self._app.context.project['name']
        shotgun_projects = self._app.shotgun.find('Project', [], ['name'])
        projects = []
        for project in shotgun_projects:
            projects.append(project['name'])
        projects.sort()
        self._project_combo.addItems(projects)
        self._project_combo.setCurrentText(current_project)

    def _fill_filters(self):
        # Step List
        shotgun_list = self._app.shotgun.find("Step", [], ['code'])
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
    
    def _get_step_filter_selected(self):
        steps = []
        for index in range(self._step_list_widget.count()):
            item = self._step_list_widget.item(index)
            if item.checkState() == QtCore.Qt.Checked:
                steps.append(item.text())
        return steps

    def _type_filter(self, template):
        if template.definition[-3:] == 'exr':
            # 2D
            if self._type_list_widget.item(0).checkState() == QtCore.Qt.Unchecked:
                return False
        else:
            # 3D
            if self._type_list_widget.item(1).checkState() == QtCore.Qt.Unchecked:
                return False
        
        return True

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
    def __init__(self, app, templates):
        self._app = app
        self._templates = templates

class TopLevelTreeItem(QtGui.QTreeWidgetItem):
    def __init__(self, path, fields, column_names):
        super(TopLevelTreeItem, self).__init__()
        self._fields = fields
        self._path = path
        self._column_names = column_names

        self.setText(self._column_names.index_name('name'), os.path.basename(self._path).split('.')[0])
        self.setText(self._column_names.index_name('ver'), str(fields['version']))
        self.setText(self._column_names.index_name('type'), self._path.split('.')[-1])
        self.setText(self._column_names.index_name('depart'), str(fields['Step']))

        # Last modified
        time = os.path.getctime(os.path.dirname(self._path))
        date_time = datetime.utcfromtimestamp(time).strftime('%Y-%m-%d %H:%M:%S')
        self.setText(self._column_names.index_name('modif'), date_time)

    def set_image(self):
        # For demo
        dir_path = os.path.dirname(os.path.dirname(self._path))
        thumb_name = '%s.jpg' % os.path.basename(self._path).split('.')[0]
        thumb_path = os.path.join(dir_path, 'flipbook_panel', thumb_name)

        if os.path.exists(thumb_path):
            image = QtGui.QPixmap(thumb_path)

            thumbnail = QtGui.QLabel("", self.treeWidget())
            thumbnail.setAlignment(QtCore.Qt.AlignHCenter)
            thumbnail.setPixmap(image)
            self.treeWidget().setItemWidget(self, self._column_names.index_name('thumb'), thumbnail)
            self.treeWidget().header().resizeSections(QtGui.QHeaderView.ResizeToContents)

