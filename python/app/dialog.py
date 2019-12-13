import sgtk

from sgtk.platform.qt import QtCore, QtGui

import os
import hou
import sys

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

        template_name = self._app.get_setting("output_flipbook_template")
        self._output_template = self._app.get_template_by_name(template_name)

        self._setup_ui()
        self._fill_projects()
        self._fill_treewidget()
    
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
        main_layout = QtGui.QHBoxLayout()
        side_bar = QtGui.QVBoxLayout()

        self._project_combo = QtGui.QComboBox()
        self._project_combo.currentIndexChanged.connect(self._fill_shots)

        self._shot_list_widget = QtGui.QListWidget()
        
        side_bar.addWidget(self._project_combo)
        side_bar.addWidget(self._shot_list_widget)

        # Tree layout
        self._tree_widget = QtGui.QTreeWidget()

        self._tree_widget.setColumnCount(1)
        self._tree_widget.setHeaderLabels(['hello'])
        self._tree_widget.setSelectionMode(QtGui.QAbstractItemView.SelectionMode.ExtendedSelection)
        self._tree_widget.header().setSectionsMovable(False)
        self._tree_widget.header().resizeSections(QtGui.QHeaderView.ResizeToContents)

        main_layout.addLayout(side_bar)
        main_layout.addWidget(self._tree_widget)

        # Create final layout
        self.setLayout(QtGui.QVBoxLayout())
        self.layout().addLayout(upper_bar)
        self.layout().addLayout(main_layout)

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
        print 'Fill treewidget not functional yet!'
