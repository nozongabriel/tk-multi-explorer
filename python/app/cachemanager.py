
import os
import glob

from sgtk.platform.qt import QtCore, QtGui
import sgtk

import treeitems

class CacheManager(QtCore.QObject):
    add_item_sig = QtCore.Signal(treeitems.TopLevelTreeItem)

    def __init__(self, app, column_names, image_types, tab_types):
        super(CacheManager, self).__init__()

        self._app = app
        self._column_names = column_names
        self._abort = False

        self._2d_item_dict = {}
        self._3d_item_dict = {}

        self._2d_templates = {}
        self._3d_templates = {}

        for item_type in tab_types:
            self._2d_templates[item_type] = []
            self._3d_templates[item_type] = []

            # Get templates in from shot and asset context
            search_dict = self._app.shotgun.find_one(item_type, [['project.Project.name', 'is', self._app.context.project['name']]], ['code'])
            search_dict['project'] = self._app.context.project

            entity_context = self._app.sgtk.context_from_entity_dictionary(search_dict)

            # Statically add the tk-houdini engine as I could not get this to work with the tk-desktop engine
            # Still contacting support about it :(
            settings = sgtk.platform.find_app_settings('tk-houdini', self._app.name, self._app.sgtk, entity_context)
            self._app.log_debug('Cache Manager Settings {}'.format(settings))

            if settings:
                for output_profile in settings[0]["settings"]["templates"]:
                    cache_template = self._app.get_template_by_name(output_profile['cache_template'])

                    work_template = []
                    if output_profile['work_template']:
                        for template_name in output_profile['work_template']:
                            work_template.append(self._app.get_template_by_name(template_name))
                    
                    preview_template = ''
                    if output_profile['preview_template']:
                        preview_template = self._app.get_template_by_name(output_profile['preview_template'])

                    template_dict = {'cache_template': cache_template, 'work_template': work_template, 'preview_template': preview_template}

                    extension = cache_template.definition.split('.')[-1]
                    if extension in image_types:
                        self._2d_templates[item_type].append(template_dict)
                    else:
                        self._3d_templates[item_type].append(template_dict)
            else:
                self._app.log_error("Could not find settings for the cachemanager. App will not work!")

        self._app.log_debug('2D Templates {}'.format(self._2d_templates))
        self._app.log_debug('3D Templates {}'.format(self._3d_templates))

    ############################################################################
    # Public methods

    def clear_cache(self):
        self._2d_item_dict.clear()
        self._3d_item_dict.clear()

    def set_thread_variables(self, shot_asset, item_type, step_filters, type_filters, search_text):
        self._thread_var = {
            'item_name': shot_asset,
            'item_type': item_type,
            'step_filters': step_filters,
            'type_filters': type_filters,
            'search_text': search_text
        }

    def get_caches(self):
        # get all published paths for item
        self._publishes = []

        for publish_file in self._app.shotgun.find('PublishedFile', [['project.Project.name', 'is', self._app.context.project['name']]], ['path']):
            self._publishes.append(publish_file['path']['local_path'].replace('/', os.sep))

        # start main loop
        for step, enabled in self._thread_var['step_filters'].items():
            ui_fields = {
                self._thread_var['item_type']: self._thread_var['item_name'],
                'Step': step}

            if enabled and self._thread_var['type_filters']['2D']:
                if step in self._2d_item_dict:
                    self._set_hidden(False, self._2d_item_dict[step], self._thread_var['search_text'])
                else:
                    self._2d_item_dict[step] = self._caches_from_templates(self._2d_templates[self._thread_var['item_type']], ui_fields, self._thread_var['search_text'])
            elif step in self._2d_item_dict:
                self._set_hidden(True, self._2d_item_dict[step], self._thread_var['search_text'])

            if enabled and self._thread_var['type_filters']['3D']:
                if step in self._3d_item_dict:
                    self._set_hidden(False, self._3d_item_dict[step], self._thread_var['search_text'])
                else:
                    self._3d_item_dict[step] = self._caches_from_templates(self._3d_templates[self._thread_var['item_type']], ui_fields, self._thread_var['search_text'])
            elif step in self._3d_item_dict:
                self._set_hidden(True, self._3d_item_dict[step], self._thread_var['search_text'])

        self.thread().terminate()

    ############################################################################
    # Private methods

    def _caches_from_templates(self, templates, ui_fields, search_text):
        items = []
        for template_dict in templates:
            template = template_dict['cache_template']
            self._app.log_debug('Searching Template {}'.format(template))
            self._app.log_debug('With Fields {}'.format(ui_fields))
            
            cache_paths = self._app.sgtk.abstract_paths_from_template(template, ui_fields)
            self._app.log_debug('Found caches {}'.format(cache_paths))
            
            # different logic for renders
            if 'AOV' in template.keys and 'RenderLayer' in template.keys:
                # sort paths
                cache_paths.sort()

                # Add caches to tree
                top_level_item = None
                version_item = None
                aov_item = None

                for cache_path in cache_paths:
                    fields = template.get_fields(cache_path)
                    fields['templates'] = template_dict
                    
                    # Fields for toplevel items
                    fields['isrendertoplevel'] = False
                    fields['isversion'] = False
                    fields['published'] = cache_path in self._publishes
                    
                    # Create copy of fields to compare against, remove keys that can not be the same
                    fields_no_ver = fields.copy()
                    fields_no_ver.pop('version', None)
                    fields_no_ver.pop('published', None)
                    fields_no_ver.pop('AOV', None)
                    fields_no_ver['isrendertoplevel'] = True

                    if not top_level_item or top_level_item.get_fields() != fields_no_ver:
                        if top_level_item and top_level_item.childCount():
                            for index in range(top_level_item.childCount()):
                                top_level_item.child(index).post_process()
                            top_level_item.post_process()

                            self.add_item_sig.emit(top_level_item)
                            items.append(top_level_item)

                        top_level_item = treeitems.RenderTopLevelTreeItem(cache_path, fields_no_ver, self._column_names)
                        version_item = None

                    if not version_item or version_item.get_fields()['version'] != fields['version']:
                        render_layer_fields = fields.copy()
                        render_layer_fields['isversion'] = True
                        version_item = treeitems.RenderTopLevelTreeItem(cache_path, render_layer_fields, self._column_names)

                        top_level_item.addChild(version_item)
                        
                    aov_item = treeitems.AovTreeItem(cache_path, fields, self._column_names)
                    version_item.addChild(aov_item)

                # Add the last element
                if top_level_item and top_level_item.childCount():
                    for index in range(top_level_item.childCount()):
                        top_level_item.child(index).post_process()
                    top_level_item.post_process()

                    self.add_item_sig.emit(top_level_item)
                    items.append(top_level_item)

            # regular tree adding logic
            else:
                # Sort based on basename of path instead of complete path
                # This fixes some elements not being merged in the treeview
                sort_list = []
                for path in cache_paths:
                    sort_list.append({'basename': os.path.basename(path), 'path': path})

                sorted_list = sorted(sort_list, key=lambda k: k['basename'])

                cache_paths = []
                for item in sorted_list:
                    cache_paths.append(item['path'])

                # Add caches to tree
                top_level_item = None
                for cache_path in cache_paths:
                    fields = template.get_fields(cache_path)
                    fields['templates'] = template_dict
                    fields['published'] = cache_path in self._publishes

                    # Create copy of fields to compare against, remove keys that can not be the same
                    fields_no_ver = fields.copy()
                    fields_no_ver.pop('version', None)
                    fields_no_ver.pop('published', None)

                    if not top_level_item or top_level_item.get_fields() != fields_no_ver:
                        # Only add top level item if it has children
                        if top_level_item and top_level_item.childCount():
                            top_level_item.post_process()
                            self.add_item_sig.emit(top_level_item)
                            items.append(top_level_item)

                        top_level_item = treeitems.TopLevelTreeItem(cache_path, fields_no_ver, self._column_names)

                    # Check if valid cache (remove duplicates when checking with templates that have and don't have {SEQ} key)
                    if ('%04d' in cache_path and len(glob.glob(cache_path.replace('%04d', '*')))) or os.path.exists(cache_path):
                        item = treeitems.TreeItem(cache_path, fields, self._column_names)
                        top_level_item.addChild(item)

                # Add the last element
                if top_level_item and top_level_item.childCount():
                    top_level_item.post_process()
                    self.add_item_sig.emit(top_level_item)
                    items.append(top_level_item)
        return items

    def _set_hidden(self, hidden, cache_dict, search_text):
        for item in cache_dict:
            current_hidden_var = item.isHidden()

            new_hidden_var = hidden
            if search_text and search_text.lower() not in item.get_path().lower():
                new_hidden_var = True

            if current_hidden_var != new_hidden_var:
                item.setHidden(new_hidden_var)
                item.treeWidget().header().resizeSections(QtGui.QHeaderView.ResizeToContents)