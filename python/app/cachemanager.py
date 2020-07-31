
import os
import glob

from sgtk.platform.qt import QtCore, QtGui
import sgtk

import treeitems

class CacheManager(QtCore.QObject):
    add_item_sig = QtCore.Signal(treeitems.TopLevelTreeItem)

    def __init__(self, app, column_names, image_types):
        super(CacheManager, self).__init__()

        self._app = app
        self._column_names = column_names
        self._abort = False

        self._2d_item_dict = {}
        self._3d_item_dict = {}

        self._2d_templates = []
        self._3d_templates = []
        self._comp_templates = []

        # Get shot templates in from shot or asset context
        shotgun_shots = self._app.shotgun.find("Shot", [['project.Project.name', 'is', self._app.context.project['name']]], ['code'])
        
        search_dict = shotgun_shots[0]
        search_dict['project'] = self._app.context.project

        entity_context = self._app.sgtk.context_from_entity_dictionary(search_dict)

        # Statically add the tk-houdini engine as I could not get this to work with the tk-desktop engine
        # Still contacting support about it :(
        settings = sgtk.platform.find_app_settings('tk-houdini', self._app.name, self._app.sgtk, entity_context)
        self._app.log_debug(settings)

        if settings:
            for output_profile in settings[0]["settings"]["templates"]:
                cache_template = self._app.get_template_by_name(output_profile['cache_template'])

                work_template = ''
                if output_profile['work_template']:
                    work_template = self._app.get_template_by_name(output_profile['work_template'])
                preview_template = ''
                if output_profile['preview_template']:
                    preview_template = self._app.get_template_by_name(output_profile['preview_template'])

                template_dict = {'cache_template': cache_template, 'work_template': work_template, 'preview_template': preview_template}

                extension = cache_template.definition.split('.')[-1]
                if extension in image_types:
                    if 'Compositing' in cache_template.definition:
                        self._comp_templates.append(template_dict)
                    else:
                        self._2d_templates.append(template_dict)
                else:
                    self._3d_templates.append(template_dict)
        else:
            self._app.log_error("Could not find settings for the cachemanager. App will not work!")

    ############################################################################
    # Public methods

    def clear_cache(self):
        self._2d_item_dict.clear()
        self._3d_item_dict.clear()

    def set_thread_variables(self, shot, step_filters, type_filters, search_text):
        self._thread_var = {
            'shot': shot,
            'step_filters': step_filters,
            'type_filters': type_filters,
            'search_text': search_text
        }

    def get_caches(self):
        # get all published paths for shot
        self._publishes = []
        base_project_path = os.path.dirname(self._app.tank.project_path)

        for publish_file in self._app.shotgun.find('PublishedFile', [['project.Project.name', 'is', self._app.context.project['name']]], ['path_cache']):
            self._publishes.append(os.path.join(base_project_path, publish_file['path_cache'].replace('/', os.sep)))

        for step, enabled in self._thread_var['step_filters'].items():
            ui_fields = {
                'Shot': self._thread_var['shot'],
                'Step': step}

            if enabled and self._thread_var['type_filters']['2D']:
                if step in self._2d_item_dict:
                    self._set_hidden(False, self._2d_item_dict[step], self._thread_var['search_text'])
                else:
                    self._2d_item_dict[step] = self._caches_from_templates(self._2d_templates, ui_fields, self._thread_var['search_text'])

                    # Add compositing (exeption, in time shoud be removed)
                    if step == 'Compositing':
                        self._2d_item_dict[step] += self._caches_from_templates(self._comp_templates, ui_fields, self._thread_var['search_text'])

            elif step in self._2d_item_dict:
                self._set_hidden(True, self._2d_item_dict[step], self._thread_var['search_text'])

            if enabled and self._thread_var['type_filters']['3D']:
                if step in self._3d_item_dict:
                    self._set_hidden(False, self._3d_item_dict[step], self._thread_var['search_text'])
                else:
                    self._3d_item_dict[step] = self._caches_from_templates(self._3d_templates, ui_fields, self._thread_var['search_text'])
            elif step in self._3d_item_dict:
                self._set_hidden(True, self._3d_item_dict[step], self._thread_var['search_text'])

        self.thread().terminate()

    ############################################################################
    # Private methods

    def _caches_from_templates(self, templates, ui_fields, search_text):
        items = []
        for template_dict in templates:
            template = template_dict['cache_template']
            cache_paths = self._app.sgtk.abstract_paths_from_template(template, ui_fields)
            
            # different logic for renders
            if 'AOV' in template.keys and 'RenderLayer' in template.keys:
                # sort paths
                cache_paths.sort()

                # Add caches to tree
                top_level_item = None
                renderlayer_item = None
                aov_item = None

                for cache_path in cache_paths:
                    fields = template.get_fields(cache_path)
                    fields['templates'] = template_dict
                    # Copy over step for comp (should be removed)
                    fields['Step'] = ui_fields['Step']
                    # Fields for toplevel items
                    fields['isrendertoplevel'] = False
                    fields['isrenderlayer'] = False
                    fields['published'] = self._check_published(cache_path)

                    if not top_level_item or top_level_item.get_fields()['version'] != fields['version']:
                        if top_level_item and top_level_item.childCount():
                            for index in range(top_level_item.childCount()):
                                top_level_item.child(index).post_process()
                            top_level_item.post_process()

                            self.add_item_sig.emit(top_level_item)
                            items.append(top_level_item)

                        top_level_fields = fields.copy()
                        top_level_fields['isrendertoplevel'] = True
                        top_level_item = treeitems.RenderTopLevelTreeItem(cache_path, top_level_fields, self._column_names)
                        renderlayer_item = None

                    if not renderlayer_item or renderlayer_item.get_fields()['RenderLayer'] != fields['RenderLayer']:
                        render_layer_fields = fields.copy()
                        render_layer_fields['isrenderlayer'] = True
                        renderlayer_item = treeitems.RenderTopLevelTreeItem(cache_path, render_layer_fields, self._column_names)

                        top_level_item.addChild(renderlayer_item)
                        
                    aov_item = treeitems.AovTreeItem(cache_path, fields, self._column_names)
                    renderlayer_item.addChild(aov_item)

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
                    # Copy over step for comp (should be removed)
                    fields['Step'] = ui_fields['Step']
                    fields['published'] = self._check_published(cache_path)

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

    def _check_published(self, path):
        for publish in self._publishes:
            if publish == path:
                return True
        return False