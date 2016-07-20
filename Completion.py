# -*- coding: utf8 -*-

from .ycmd import http_client, exceptions
from base64 import b64decode
from json import loads
from threading import Thread
import os
import sublime
import sublime_plugin
import subprocess
from .lang_map import LANG_MAP


PACKAGE_NAME = os.path.splitext(os.path.basename(os.path.dirname(__file__)))[0]
ERROR_MARKER_IMG = 'Packages/{}/marker.png'.format(PACKAGE_NAME)
SETTINGS_NAME = "{}.sublime-settings".format(PACKAGE_NAME)
SETTINGS_PATH = "${packages}/User/" + SETTINGS_NAME

########################
#  MESSAGES TEMPLATES  #
########################
COMPLETION_ERROR_MSG = "[Ycmd][Completion] Error {}"
COMPLETION_NOT_AVAILABLE_MSG = "[Ycmd] No completion available"
ERROR_MESSAGE_TEMPLATE = "[{kind}] {text}"
PANEL_ERROR_MESSAGE_TEMPLATE = "{:<5} {}"
GET_PATH_ERROR_MSG = "[Ycmd][Path] Failed to replace '{}' -> '{}'"
NO_HMAC_MESSAGE = "[Ycmd] You should generate HMAC throug the menu before using plugin"
NOTIFY_ERROR_MSG = "[Ycmd][Notify] Error {}"
PRINT_MODULE_ERROR_MESSAGE_TEMPLATE = "[Ycmd][{}] > Error: {}"
PRINT_MODULE_NOT_AVAILABLE_TEMPLATE = "[Ycmd][{}] Command not available"
PRINT_ERROR_MESSAGE_TEMPLATE = "[Ycmd] > {} ({},{})"
LANGUAGE_NOT_SUPPORTED_MSG = "[Ycmd][ConfigError] Language '{}' specified " \
                             "in settings file is not supported by ycmd"

LOCAL_SERVER = None
USER_LANGUAGES = None


def print_status(msg):
    print(msg)
    sublime.status_message(msg)


def start_server(settings):
    global LOCAL_SERVER
    if LOCAL_SERVER:
        print_status('[Ycmd] Shutdown server: {}'.format(LOCAL_SERVER._server_location))
        LOCAL_SERVER.Shutdown()
    ycmd_path = settings["ycmd_path"]
    default_settings_path = settings["default_settings_path"]
    python_path = settings["python_bin"]
    LOCAL_SERVER = http_client.YcmdClient.StartYcmdAndReturnHandle(python_path, ycmd_path,
                                                                   default_settings_path)
    server_pid = str(LOCAL_SERVER._popen_handle.pid)
    st_pid = str(os.getpid())
    subprocess.Popen([python_path,
                      os.path.join(os.path.dirname(os.path.abspath(__file__)), "ycmd/monitor.py"),
                      st_pid,
                      server_pid])
    if LOCAL_SERVER.IsAlive():
        print_status("[Ycmd] Local Server started at: {}".format(LOCAL_SERVER._server_location))


def get_client(settings=None):
    if not settings:
        settings = read_settings()
    if settings['use_auto']:
        return LOCAL_SERVER
    else:
        return http_client.YcmdClient(0, settings["server"], settings["port"], settings["hmac"])


def plugin_loaded():
    from imp import reload
    reload(http_client)
    settings = read_settings()
    if settings['use_auto']:
        print('[Ycmd] Plugin loaded with autostart. Starting Ycmd.')
        start_server(settings)


def plugin_unloaded():
    print('[Ycmd] Plugin unloaded, so killing server.')
    LOCAL_SERVER.Shutdown()


def open_user_settings():
    sublime.active_window().run_command('open_file', {'file': SETTINGS_PATH})


def active_view():
    return sublime.active_window().active_view()


def load_active_languages(settings):
    languages = set(settings["languages"])
    for missing_lang in languages - set(LANG_MAP.keys()):
        print_status(LANGUAGE_NOT_SUPPORTED_MSG.format(missing_lang))
        languages.discard(missing_lang)
    return languages


def read_settings():
    s = sublime.load_settings(SETTINGS_NAME)
    settings = dict()
    settings["server"] = s.get("ycmd_server", "http://localhost")
    settings["port"] = s.get("ycmd_port", 8080)
    settings["hmac"] = s.get("HMAC", '')
    settings["use_auto"] = s.get("use_auto_start_localserver", 0) == 1
    settings["ycmd_path"] = s.get("ycmd_path", "")
    settings["python_bin"] = s.get("python_binary_path", "python")
    settings["default_settings_path"] = s.get(
        "default_settings_path", os.path.join(settings["ycmd_path"], "default_settings.json"))
    settings["languages"] = s.get("languages", ["cpp"])

    if not settings['use_auto']:
        if not settings["hmac"] or str(settings['hmac']) == "_some_base64_key_here_==":
            print_status(NO_HMAC_MESSAGE)
        else:
            settings["hmac"] = b64decode(settings["hmac"].encode('utf-8'))

    settings["replace_file_path"] = (None, None)
    replace = s.get("ycmd_filepath_replace", {})

    if replace:
        settings["replace_file_path"] = (replace["from"], replace["to"])
    return settings


def lang(view):
    global USER_LANGUAGES
    if USER_LANGUAGES is None:
        USER_LANGUAGES = load_active_languages(read_settings())
    for language in USER_LANGUAGES:
        if view.match_selector(view.sel()[0].begin(), 'source.%s' % LANG_MAP[language]):
            return language.replace('c++', 'cpp').replace('js', 'javascript')
    return None


def get_selected_pos(view):
    try:
        return view.rowcol(view.sel()[0].end())
    except:
        return None


def get_file_path(filepath=None, reverse=False):
    ''' Turns filepath to its modified variant (replace prefix according to settings).
        If reverse is True, then tries to convert filepath from remote version to local.
        If filepath is None, trying to get current filepath, opened in active view.
    '''
    if not filepath:
        filepath = active_view().file_name()
    if not filepath:
        filepath = 'tmpfile.cpp'
    from_prefix, to_prefix = read_settings()["replace_file_path"]
    if reverse:
        from_prefix, to_prefix = to_prefix, from_prefix
    if from_prefix and to_prefix:
        try:
            filepath = filepath.replace(from_prefix, to_prefix)
        except:
            print_status(GET_PATH_ERROR_MSG.format(from_prefix, to_prefix))
    return filepath


def notify_func(filepath, content, callback, filetype):
    cli = get_client()
    try:
        data = http_client.PrepareForNewFile(cli, filepath, content, filetype)
    except exceptions.UnknownExtraConf as e:
        if sublime.ok_cancel_dialog(str(e)):
            cli.LoadExtraConfFile(e.extra_conf_file)
        else:
            cli.IgnoreExtraConfFile(e.extra_conf_file)
        return
    except Exception as e:
        print(NOTIFY_ERROR_MSG.format(e))
        return
    if callback:
        callback(data)


def complete_func(filepath, row, col, content, error_cb, data_cb, filetype):
    notify_func(filepath, content, error_cb, filetype)
    cli = get_client()
    try:
        data = http_client.SemanticCompletionResults(cli, filepath,
                                                     row + 1, col + 1,
                                                     content, filetype)
    except Exception as e:
        print(COMPLETION_ERROR_MSG.format(e))
        sublime.status_message(COMPLETION_NOT_AVAILABLE_MSG)
        return
    if data_cb:
        data_cb(data)


def completer_cmd_func(command, filepath, row, col, content, completer_cb, filetype):
    cli = get_client()
    try:
        data = cli.SendCompleterCommandRequest(command, filepath, filetype,
                                               row + 1, col + 1, content)
    except Exception as e:
        print(PRINT_MODULE_ERROR_MESSAGE_TEMPLATE.format(command, e))
        sublime.status_message(PRINT_MODULE_NOT_AVAILABLE_TEMPLATE.format(command))
        return
    completer_cb(data, command)


class YcmdRestartServerCommand(sublime_plugin.WindowCommand):
    def run(self):
        settings = read_settings()
        if settings['use_auto']:
            start_server(settings)


class YcmdReloadSettingsCommand(sublime_plugin.WindowCommand):
    def run(self):
        global USER_LANGUAGES
        USER_LANGUAGES = load_active_languages(read_settings())


class YcmdCreateHmacPairCommand(sublime_plugin.WindowCommand):
    def run(self):
        HMAC_b64 = http_client.YcmdClient.GenerateHMAC()[0]
        s = sublime.load_settings(SETTINGS_NAME)
        print("HMAC:", HMAC_b64.decode('utf-8'))
        s.set('HMAC', HMAC_b64.decode('utf-8'))
        sublime.save_settings(SETTINGS_NAME)
        open_user_settings()


class YcmdCompletionEventListener(sublime_plugin.EventListener):

    completions = []
    ready_from_defer = False
    view_cache = dict()
    view_line = dict()

    def on_selection_modified_async(self, view):
        if view.id() == ERROR_PANEL.id():
            ERROR_PANEL.show_code_for_error()
            return
        if lang(view) is None or view.is_scratch():
            return
        self.update_statusbar(view)

    def on_load_async(self, view):
        '''Called when the file is finished loading'''
        filetype = lang(view)
        if filetype is '' or view.is_scratch():
            return
        filepath = get_file_path()
        content = view.substr(sublime.Region(0, view.size()))
        t = Thread(None, notify_func, 'NotifyAsync', [filepath, content, self._on_errors, filetype])
        t.daemon = True
        t.start()

    def on_post_save_async(self, view):
        if lang(view) is None or view.is_scratch():
            return
        self.on_load_async(view)

    def on_pre_close(self, view):
        view_id = view.id()
        if view_id in self.view_line:
            del self.view_line[view_id]
        if view_id in self.view_cache:
            del self.view_cache[view_id]

    def on_activated_async(self, view):
        if lang(view) is None or view.is_scratch():
            return
        ERROR_PANEL.update(self.view_cache)

    def on_query_completions(self, view, prefix, locations):
        '''Sublime Text autocompletion event handler'''
        filetype = lang(view)
        if filetype is None or view.is_scratch():
            return

        print("[YCMD] #### START COMPLETION ####")

        if self.ready_from_defer is True:
            cpl = self.completions
            self.completions = []
            self.ready_from_defer = False
            return (cpl, sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)

        filepath = get_file_path()
        row, col = view.rowcol(locations[0])
        content = view.substr(sublime.Region(0, view.size()))
        t = Thread(None, complete_func, 'CompleteAsync',
                   [filepath, row, col, content, self._on_errors, self._complete, filetype])
        t.daemon = True
        t.start()

    def _complete(self, data):
        try:
            jsonResp = loads(data)
        except:
            print(NOTIFY_ERROR_MSG.format("json '{}'".format(data)))
            return
        proposals = list(self.generate_completion_items(jsonResp['completions']))

        if proposals:
            active_view().run_command("hide_auto_complete")
            self.completions = proposals
            self.ready_from_defer = True
            self._run_auto_complete()
        else:
            sublime.status_message("[Ycmd] No completion available")

    def _run_auto_complete(self):
        active_view().run_command("auto_complete", {
            'disable_auto_insert': True,
            'next_completion_if_showing': False,
            'auto_complete_commit_on_tab': True,
        })

    def _on_errors(self, data):
        try:
            data = loads(data)
        except:
            print(NOTIFY_ERROR_MSG.format("json '{}'".format(data)))
            return
        filepath = get_file_path()
        self.highlight_problems(active_view(),
                                [_ for _ in data
                                    if get_file_path(_['location']['filepath']) == filepath])
        self.update_statusbar(active_view(), force=True)
        ERROR_PANEL.update(self.view_cache)

    def update_statusbar(self, view, force=False):
        row, col = get_selected_pos(view)
        view_id = view.id()
        text_point = view.text_point(row, col)

        if not force:
            beg, end = self.view_line.get(view_id, (None, None))
            if beg and end and sublime.Region(beg, end).contains(text_point):
                return

        errors_regions = self.view_cache.get(view_id, {}).get(row, {})
        for region, msg in errors_regions.items():
            if sublime.Region(*region).contains(text_point) and msg:
                view.set_status('clang-code-errors', msg)
                self.view_line[view_id] = region
                return
        if view_id in self.view_line:
            del self.view_line[view_id]
        view.erase_status('clang-code-errors')

    def highlight_problems(self, view, problems):
        view.erase_regions('clang-code-errors')
        view_id = view.id()
        view_cache = {}
        regions = []
        for problem in problems:
            lineno = problem['location']['line_num']
            colno = problem['location']['column_num']
            line_regions = view_cache.setdefault(lineno - 1, {})
            message = ERROR_MESSAGE_TEMPLATE.format(**problem)
            print(PRINT_ERROR_MESSAGE_TEMPLATE.format(message, lineno, colno))
            region = view.word(view.text_point(lineno - 1, colno - 1))
            regions.append(region)
            line_regions[(region.a, region.b)] = message
        self.view_cache[view_id] = view_cache
        style = (sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE |
                 sublime.DRAW_SQUIGGLY_UNDERLINE)
        view.add_regions(
            'clang-code-errors', regions, 'invalid', ERROR_MARKER_IMG, style)

    def generate_completion_items(self, completions):
        for completion in completions:
            if 'insertion_text' not in completion:
                continue
            insertion = completion['insertion_text']
            if 'extra_menu_info' in completion:
                yield ["{0}\t{1}".format(insertion, completion['extra_menu_info']), insertion]
            else:
                yield [insertion, insertion]


class YcmdExecuteCompleterFuncCommand(sublime_plugin.TextCommand):

    def run(self, edit, command):
        filepath = get_file_path()
        row, col = self.view.rowcol(self.view.sel()[0].begin())
        content = self.view.substr(sublime.Region(0, self.view.size()))
        filetype = lang(self.view)
        if filetype is None:
            return
        t = Thread(None, completer_cmd_func, 'ExecuteCompleterFuncAsync',
                   [command, filepath, row, col, content, self._completer_cb, filetype])
        t.daemon = True
        t.start()

    def is_enabled(self):
        return lang(self.view) is not None

    def _completer_cb(self, data, command):
        try:
            jsonResp = loads(data)
        except:
            print(NOTIFY_ERROR_MSG.format("json '{}'".format(data)))
            return
        if command == 'GoTo':
            row = jsonResp.get('line_num', 1)
            col = jsonResp.get('column_num', 1)
            filepath = get_file_path(jsonResp.get('filepath', self.view.file_name()), reverse=True)
            print("[Ycmd][GoTo] file: {}, row: {}, col: {}".format(filepath, row, col))
            sublime.active_window().open_file('{}:{}:{}'.format(filepath, row, col),
                                              sublime.ENCODED_POSITION)
        else:
            print_status("[Ycmd][{}]: {}".format(command, jsonResp.get('message', '')))


class YcmdErrorPanelRefresh(sublime_plugin.TextCommand):
    def run(self, edit, data):
        self.view.erase(edit, sublime.Region(0, self.view.size()))
        self.view.insert(edit, 0, data)


class YcmdErrorPanel(object):
    # view of this error panel
    view = None
    # text currently in panel
    text = ""
    # view with code, for with panel show errors
    code_view = None
    lines_to_errors = []

    def id(self):
        if self.view is not None:
            return self.view.id()
        else:
            return None

    def update_async(self, view_cache, view=None):
        t = Thread(None, self.update, 'PanelUpdateAsync', [view_cache, view])
        t.daemon = True
        t.start()

    def update(self, view_cache, view=None):
        if view is None:
            view = active_view()

        messages = []
        self.lines_to_errors = []
        lines = view_cache.get(view.id(), {})
        for line_num, line_regions in sorted(lines.items()):
            for region, msg in line_regions.items():
                messages.append(PANEL_ERROR_MESSAGE_TEMPLATE.format(str(line_num) + ':', msg))
                self.lines_to_errors.append(region)
        self.text = '\n'.join(messages)
        self.code_view = view
        if self.is_visible():
            self._refresh()

    def is_visible(self):
        return self.view is not None and self.view.window() is not None

    def _refresh(self):
        self.view.set_read_only(False)
        self.view.set_scratch(True)
        self.view.run_command("ycmd_error_panel_refresh", {"data": self.text})
        self.view.set_read_only(True)

    def show_code_for_error(self):
        if not self.is_visible() or self.code_view is None:
            return

        # get rid of false positive (non-user interaction)
        last_command_name, _, _ = self.view.command_history(0, False)
        if last_command_name == 'ycmd_error_panel_refresh':
            return

        row, _ = get_selected_pos(self.view)
        if row < len(self.lines_to_errors):
            region = self.lines_to_errors[row]
            # we must create sublime region, because cached region is just tuple
            sublime_region = sublime.Region(region[0], region[1])
            self.code_view.show_at_center(sublime_region)

    def open(self):
        window = sublime.active_window()
        if not self.is_visible():
            self.view = window.create_output_panel("clang-errors")
            syntax_file = "Packages/YcmdCompletion/ErrorPanel.tmLanguage"
            self.view.set_syntax_file(syntax_file)
        self._refresh()
        window.run_command("show_panel", {"panel": "output.clang-errors"})

    def close(self):
        sublime.active_window().run_command("hide_panel", {"panel": "output.clang-errors"})

ERROR_PANEL = YcmdErrorPanel()


class YcmdErrorPanelShow(sublime_plugin.WindowCommand):
    def run(self):
        ERROR_PANEL.open()


class YcmdErrorPanelHide(sublime_plugin.WindowCommand):
    def run(self):
        ERROR_PANEL.close()
