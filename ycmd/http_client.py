# -*- coding: utf8 -*-
#!/usr/bin/env python

from base64 import b64encode
from urllib.request import Request, urlopen
from .wrapper_utils import ToUtf8Json
from .ycmd_events import EventEnum
import collections
import hmac
import hashlib
import os


HMAC_HEADER = 'X-Ycm-Hmac'
HMAC_SECRET_LENGTH = 16

DEFINED_SUBCOMMANDS_HANDLER = '/defined_subcommands'
CODE_COMPLETIONS_HANDLER = '/completions'
COMPLETER_COMMANDS_HANDLER = '/run_completer_command'
EVENT_HANDLER = '/event_notification'
EXTRA_CONF_HANDLER = '/load_extra_conf_file'


class YcmdClient(object):
    def __init__(self, server, port, hmac_secret):
        self._port = port
        self._hmac_secret = hmac_secret
        self._server_location = "{}:{}".format(server, port)

    @classmethod
    def GenerateHMAC(cls):
        hmac_secret = os.urandom(HMAC_SECRET_LENGTH)
        return b64encode(hmac_secret), hmac_secret

    def PostToHandler(self, handler, data):
        return self._CallHttp('post', handler, data)

    def GetFromHandler(self, handler):
        return self._CallHttp('get', handler)

    def SendDefinedSubcommandsRequest(self, completer_target):
        request_json = BuildRequestData(completer_target=completer_target)
        self.PostToHandler(DEFINED_SUBCOMMANDS_HANDLER, request_json)

    def SendCodeCompletionRequest(self, filepath, filetype, line_num, column_num, contents):
        request_json = BuildRequestData(filepath=filepath,
                                        filetype=filetype,
                                        line_num=line_num,
                                        column_num=column_num,
                                        contents=contents)
        return self.PostToHandler(CODE_COMPLETIONS_HANDLER, request_json)

    def SendGoToRequest(self, filepath, filetype, line_num, column_num, contents):
        request_json = BuildRequestData(filepath=filepath,
                                        command_arguments=['GoTo'],
                                        filetype=filetype,
                                        line_num=line_num,
                                        column_num=column_num,
                                        contents=contents)
        self.PostToHandler(COMPLETER_COMMANDS_HANDLER, request_json)

    def SendEventNotification(self,
                              event_enum,
                              filepath,
                              filetype,
                              line_num=1,  # just placeholder values
                              column_num=1,
                              extra_data=None,
                              contents=''):
        request_json = BuildRequestData(filepath=filepath,
                                        filetype=filetype,
                                        line_num=line_num,
                                        column_num=column_num,
                                        contents=contents)
        if extra_data:
            request_json.update(extra_data)
        request_json['event_name'] = event_enum
        return self.PostToHandler(EVENT_HANDLER, request_json)

    def LoadExtraConfFile(self, extra_conf_filename):
        request_json = {'filepath': extra_conf_filename}
        self.PostToHandler(EXTRA_CONF_HANDLER, request_json)

    def _ExtraHeaders(self, request_body=None):
        return {HMAC_HEADER: self._HmacForBody(request_body)}

    def _HmacForBody(self, request_body=None):
        if not request_body:
            request_body = ''
        hexhmac = CreateHexHmac(request_body, self._hmac_secret)
        return b64encode(bytes(hexhmac, 'utf-8'))

    def _BuildUri(self, handler):
        return self._server_location + handler

    def _CallHttp(self, method, handler, data=None):
        method = method.upper()
        req = Request(self._BuildUri(handler), method=method)
        if isinstance(data, collections.Mapping):
            req.add_header('content-type', 'application/json')
            data = ToUtf8Json(data)
        data = bytes(data, 'utf-8')
        req.add_header(HMAC_HEADER, self._HmacForBody(data))
        req.data = data
        readData = urlopen(req).read().decode('utf-8')
        return readData


def CreateHexHmac(content, hmac_secret):
    # Must ensure that hmac_secret is str and not unicode
    return hmac.new(hmac_secret,
                    msg=content,
                    digestmod=hashlib.sha256).hexdigest()


def BuildRequestData(filepath='',
                     filetype=None,
                     line_num=None,
                     column_num=None,
                     command_arguments=None,
                     completer_target=None,
                     contents=''):
    data = {
        'line_num': line_num,
        'column_num': column_num,
        'filepath': filepath,
        'file_data': {
            filepath: {
                'filetypes': [filetype],
                'contents': contents
            }
        }
    }

    if command_arguments:
        data['command_arguments'] = command_arguments
    if completer_target:
        data['completer_target'] = completer_target

    return data


def CppGotoDeclaration(server, path, row, col):
    print("[Ycmd][GoTo] {}:{}:{}".format(path, row, col))
    return server.SendGoToRequest(test_filename=path,
                                  filetype='cpp',
                                  line_num=row,
                                  column_num=col)


def PrepareForNewFile(server, path, contents, filetype='cpp'):
    print("[Ycmd][Notify] {}".format(path))
    return server.SendEventNotification(EventEnum.FileReadyToParse,
                                        filepath=path,
                                        filetype=filetype,
                                        contents=contents)


def CppSemanticCompletionResults(server, path, row, col, contents, filetype='cpp'):
    print("[Ycmd][Completion] for {}:{}:{}".format(path, row, col))
    return server.SendCodeCompletionRequest(filepath=path,
                                            filetype=filetype,
                                            line_num=row,
                                            column_num=col,
                                            contents=contents)
