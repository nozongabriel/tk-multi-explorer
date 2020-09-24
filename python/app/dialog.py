import os
import sys
import collections
import glob

sys.path.append(r'\\server01\shared\sharedPython\modules\pyseq')
import pyseq

import sgtk
from sgtk.platform.qt import QtCore, QtGui

import cachemanager
import columnnames
import iconmanager
import treeitems

###########################################################################
###########################################################################
# Problem with comp scripts due to 'comp' being used as step instead of 'compositing' 
# that Shotgun gives us (see with Donat for solution)
###########################################################################
###########################################################################

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

        self.image_types = ('exr', 'jpg', 'dpx', 'png', 'tiff', 'tif', 'tga')
        self.movie_types = ('mov', 'mp4')

        # most of the useful accessors are available through the Application class instance
        # it is often handy to keep a reference to this. You can get it via the following method:
        self._current_sgtk = sgtk.platform.current_bundle()

        # Get Managers
        self._column_names = columnnames.ColumnNames()
        self._icon_manager = iconmanager.IconManager(self._column_names, self.image_types, self.movie_types)

        self._cache_manager = cachemanager.CacheManager(self._current_sgtk, self._column_names, self.image_types)

        self._cache_thread = QtCore.QThread()
        self._cache_manager.moveToThread(self._cache_thread)

        self._cache_thread.started.connect(self._cache_manager.get_caches)
        self._cache_thread.finished.connect(self._set_done_gui)

        self._cache_manager.add_item_sig.connect(self.add_item_to_tree)

        # Setup UI
        self._setup_ui()
        self._fill_shots_assets()
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
        refresh_but.setIcon(QtGui.QIcon(self._icon_manager.get_pixmap('refresh')))
        refresh_but.clicked.connect(self._refresh)

        upper_bar.addWidget(title_lab)
        upper_bar.addWidget(refresh_but)

        # Side layout
        main_splitter = QtGui.QSplitter(QtCore.Qt.Horizontal)
        side_bar = QtGui.QVBoxLayout()

        project_label = QtGui.QLabel(self._current_sgtk.context.project['name'])

        self._shot_list_widget = QtGui.QListWidget()
        self._shot_list_widget.currentItemChanged.connect(self._shot_asset_selected)

        self._asset_list_widget = QtGui.QListWidget()
        self._asset_list_widget.currentItemChanged.connect(self._shot_asset_selected)

        self._tab_list_widgets = [self._shot_list_widget, self._asset_list_widget]

        self._tab_widget = QtGui.QTabWidget()
        self._tab_widget.addTab(self._shot_list_widget, 'Shots')
        self._tab_widget.addTab(self._asset_list_widget, 'Assets')
        self._tab_widget.tabBarClicked.connect(self._refresh)

        self._current_state_label = QtGui.QLabel('Done')

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
        side_bar.addWidget(self._tab_widget)
        side_bar.addWidget(self._current_state_label)
        side_bar.addWidget(filter_widget)
        side_bar.addWidget(self._step_list_widget)
        side_bar.addLayout(filter_buttons)
        side_bar.addWidget(self._type_list_widget)

        side_bar.setStretchFactor(self._tab_widget, 20)

        splitter_side_bar_widget = QtGui.QWidget()
        splitter_side_bar_widget.setLayout(side_bar)

        # Tree layout
        tree_layout = QtGui.QVBoxLayout()
        self._search_bar = QtGui.QLineEdit()
        self._search_bar.setPlaceholderText('Search')
        if self._current_sgtk.engine.has_qt5:
            self._search_bar.setClearButtonEnabled(True)
        self._search_bar.returnPressed.connect(self._fill_treewidget)
        self._search_bar.textEdited.connect(self._fill_treewidget)

        self._tree_widget = QtGui.QTreeWidget()

        self._tree_widget.setColumnCount(1)
        self._tree_widget.setHeaderLabels(self._column_names.get_nice_names())
        self._tree_widget.setSelectionMode(QtGui.QAbstractItemView.SelectionMode.SingleSelection)
        if self._current_sgtk.engine.has_qt5:
            self._tree_widget.header().setSectionsMovable(False)
        self._tree_widget.header().resizeSections(QtGui.QHeaderView.ResizeToContents)
        if self._current_sgtk.engine.has_qt5:
            self._tree_widget.header().setSectionResizeMode(self._column_names.index_name('thumb'), QtGui.QHeaderView.Fixed)

        self._tree_widget.setSortingEnabled(True)
        self._tree_widget.header().setSortIndicatorShown(True)
        if self._current_sgtk.engine.has_qt5:
            self._tree_widget.header().setSectionsClickable(True)
        self._tree_widget.header().setSortIndicator(self._column_names.index_name('modif'), QtCore.Qt.DescendingOrder)

        self._tree_widget.itemDoubleClicked.connect(self._tree_item_double_clicked)
        self._tree_widget.itemExpanded.connect(self._item_expanded)
        self._tree_widget.itemCollapsed.connect(self._item_collapsed)
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
        self._detail_open_images.clicked.connect(self._detail_click_open_images)
        self._detail_open_images.setEnabled(False)

        self._detail_open_video = QtGui.QPushButton()
        self._detail_open_video.setFixedSize(25, 25)
        self._detail_open_video.setIcon(QtGui.QIcon(self._icon_manager.get_pixmap('video')))
        self._detail_open_video.clicked.connect(self._detail_click_open_movie)
        self._detail_open_video.setEnabled(False)

        self._detail_open_nuke = QtGui.QPushButton()
        self._detail_open_nuke.setFixedSize(25, 25)
        self._detail_open_nuke.setIcon(QtGui.QIcon(self._icon_manager.get_pixmap('nuke')))
        self._detail_open_nuke.clicked.connect(self._detail_click_open_nuke)
        self._detail_open_nuke.setEnabled(False)

        self._detail_open_maya = QtGui.QPushButton()
        self._detail_open_maya.setFixedSize(25, 25)
        self._detail_open_maya.setIcon(QtGui.QIcon(self._icon_manager.get_pixmap('maya')))
        self._detail_open_maya.clicked.connect(self._detail_click_open_maya)
        self._detail_open_maya.setEnabled(False)

        self._detail_open_hou = QtGui.QPushButton()
        self._detail_open_hou.setFixedSize(25, 25)
        self._detail_open_hou.setIcon(QtGui.QIcon(self._icon_manager.get_pixmap('houdini')))
        self._detail_open_hou.clicked.connect(self._detail_click_open_hou)
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
            label.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
            
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

    def _fill_treewidget(self, tab_selection = -1):
        if tab_selection == -1:
            tab_selection = self._tab_widget.currentIndex()
        
        current_item = self._tab_list_widgets[tab_selection].currentItem()

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
            self._cache_manager.set_thread_variables(current_item.text(), steps, type_filter, self._search_bar.text())
            
            # Run get caches async
            if True:
                if not self._cache_thread.isRunning():
                    self._set_processing_gui()
                    self._cache_thread.start()
            else:
                self._cache_manager.get_caches()

    def _set_done_gui(self):
        self._current_state_label.setText('Done')
    
    def _set_processing_gui(self):
        self._current_state_label.setText('Processing...')

    def _shot_asset_selected(self):
        if self._cache_thread.isRunning():
            self._cache_thread.terminate()

        self._refresh()

    def _refresh(self, tab_selection = -1):
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
        self._fill_treewidget(tab_selection)

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
        if item.get_type() in self.image_types or item.get_type() in self.movie_types:
            self._open_rv(item.get_preview_path())

    def _item_expanded(self, item):
        item.item_expand()

        # Set icons for new items
        self._icon_manager.set_icons(item)

        self._tree_widget.header().resizeSections(QtGui.QHeaderView.ResizeToContents)

    def _item_collapsed(self, item):
        self._tree_widget.header().resizeSections(QtGui.QHeaderView.ResizeToContents)

    def _item_clicked(self, item, column):
        if not isinstance(item, treeitems.TreeItem):
            item = item.get_latest_child()

        # Check if it has more info
        self._item_expanded(item)

        # Set detail icon
        thumb = self._icon_manager.get_icon_name(item.get_type())
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
            elif element_type in self.movie_types:
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
                text = properties[key.lower()]

                # Add spcaes for wordwrap (should remove this with newer qt)
                amount_char = 25
                if len(text) > amount_char:
                    split_text = [text[i:i+amount_char] for i in range(0, len(text), amount_char)]
                    text = ' '.join(split_text)

                self._detail_dict[key].setText(text)

        # Set Range if needed
        # to do check the sequence range
        if '%04d' in item.get_path():
            cache_range = 'Invalid Sequence Object!'
            sequences = pyseq.get_sequences(item.get_path().replace('%04d', '*'))
            if len(sequences):
                sequence = sequences[0]

                if sequence.missing():
                    cache_range = '[{}-{}], missing {}'.format(sequence.format('%s'), sequence.format('%e'), sequence.format('%M'))
                else:
                    if len(sequence) == 1:
                        cache_range = str(sequence[0].digits[-1])
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

    def _detail_click_open_nuke(self):
        self._current_sgtk.log_info('Not yet implemented opening {}'.format(self._get_selected_path_by_type(['nk'])))

    def _detail_click_open_hou(self):
        self._current_sgtk.log_info('Not yet implemented opening {}'.format(self._get_selected_path_by_type(['hip'])))

    def _detail_click_open_maya(self):
        self._current_sgtk.log_info('Not yet implemented opening {}'.format(self._get_selected_path_by_type(['ma'])))

    def _detail_click_open_images(self):
        self._open_rv(self._get_selected_path_by_type(self.image_types))

    def _detail_click_open_movie(self):
        self._open_rv(self._get_selected_path_by_type(self.movie_types))

    def _open_rv(self, path):
        process = QtCore.QProcess(self)

        # run the app
        system = sys.platform
        if system == "linux2":
            program = 'rv'
        elif system == 'win32':
            possible_rv_s = glob.glob('C:/Program Files/Shotgun/RV-*/bin/rv.exe')
            possible_rv_s.sort()

            if len(possible_rv_s):
                program = possible_rv_s[-1]
            else:
                self._current_sgtk.log_error('Could not find rv!')
                return
        else:
            msg = "Platform '{}' is not supported.".format(system)
            self._current_sgtk.log_error(msg)
            return

        process.startDetached(program, [path])
        process.close()

    ############################################################################
    # Public methods

    def add_item_to_tree(self, item):
        self._tree_widget.addTopLevelItem(item)
        self._icon_manager.set_icon(item)
        
        # Sort items
        self._tree_widget.sortItems(self._tree_widget.header().sortIndicatorSection(), self._tree_widget.header().sortIndicatorOrder())

        # Resize header
        self._tree_widget.header().resizeSections(QtGui.QHeaderView.ResizeToContents)

    def closeEvent(self, event):
        self._cache_thread.quit()
        self._cache_thread.wait()

        event.accept()

    ############################################################################
    # Private methods

    def _get_selected_path_by_type(self, types):
        items = self._tree_widget.selectedItems()

        if len(items):
            item = items[0]

            if not isinstance(item, treeitems.TreeItem):
                item = item.get_latest_child()
            
            # Check itself first
            if item.get_type() in types:
                return item.get_path()

            # Then check children
            if item.childCount():
                type_dict = {}
                for child_index in range(item.childCount()):
                    child = item.child(child_index)

                    type_dict[child.get_type()] = child.get_path()
                
                for type_click in types:
                    if type_click in type_dict.keys():
                        return type_dict[type_click]

    def _fill_shots_assets(self):
        current_project = self._current_sgtk.context.project['name']
        
        # Shots
        shotgun_shots = self._current_sgtk.shotgun.find("Shot", [['project.Project.name', 'is', current_project]], ['code'])

        shots = []
        for shot in shotgun_shots:
            # If the shot code contains a space it means there is probably a '-', replace all spaces with this
            # Fix for Shotgun doing weird things
            shots.append(shot['code'].replace(' ', '-'))
        shots.sort()
        self._shot_list_widget.addItems(shots)

        # Assets
        shotgun_assets = self._current_sgtk.shotgun.find("Asset", [['project.Project.name', 'is', current_project]], ['code'])
        
        assets = []
        for asset in shotgun_assets:
            # If the asset code contains a space it means there is probably a '-', replace all spaces with this
            # Fix for Shotgun doing weird things
            assets.append(asset['code'].replace(' ', '-'))
        assets.sort()
        self._asset_list_widget.addItems(assets)

    def _fill_filters(self):
        # Step List
        # Filter for shot as explorer currently does not support assets type
        shotgun_list = self._current_sgtk.shotgun.find("Step", [], ['code', 'short_name', 'entity_type'])
        step_list = []
        for step in shotgun_list:
            step_list.append(step['short_name'])
        step_list = list(dict.fromkeys(step_list))
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
