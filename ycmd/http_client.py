# -*- coding: utf8 -*-
#!/usr/bin/env python

from base64 import b64encode
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from .wrapper_utils import ToUtf8Json
from .ycmd_events import EventEnum
from .exceptions import UnknownExtraConf
import collections
import hmac
import hashlib
import json
import os
import socket
import subprocess
import tempfile
import threading


HMAC_HEADER = 'X-Ycm-Hmac'
HMAC_SECRET_LENGTH = 16

DEFINED_SUBCOMMANDS_HANDLER = '/defined_subcommands'
CODE_COMPLETIONS_HANDLER = '/completions'
COMPLETER_COMMANDS_HANDLER = '/run_completer_command'
EVENT_HANDLER = '/event_notification'
EXTRA_CONF_HANDLER = '/load_extra_conf_file'
IGNORE_EXTRA_CONF_HANDLER = '/ignore_extra_conf_file'
DIR_OF_THIS_SCRIPT = os.path.dirname(os.path.abspath(__file__))


class YcmdClient(object):

    def __init__(self, popen, server, port, hmac_secret):
        self._popen_handle = popen
        self._port = port
        self._hmac_secret = hmac_secret
        self._server_location = "{}:{}".format(server, port)

    @classmethod
    def StartYcmdAndReturnHandle(cls, python_path, ycmd_path, default_settings_path):
        prepared_options = json.load(open(default_settings_path))
        hmac_secret = os.urandom(16)
        prepared_options['hmac_secret'] = b64encode(
            hmac_secret).decode('utf-8')
        server_port = GetUnusedLocalhostPort()
        with tempfile.NamedTemporaryFile(delete=False, mode='w') as options_file:
            json.dump(prepared_options, options_file)
            options_file.flush()
            ycmd_args = [python_path,
                         ycmd_path,
                         '--port={0}'.format(server_port),
                         '--options_file={0}'.format(options_file.name),
                         '--idle_suicide_seconds={0}'.format(3600)]
            child_handle = subprocess.Popen(ycmd_args,
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT)
            t = threading.Thread(target=LogServerOutput, args=[child_handle.stdout])
            t.daemon = True
            t.start()
            return cls(child_handle, "http://localhost", server_port, hmac_secret)

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

    def SendCompleterCommandRequest(self, command, filepath, filetype, line_num, column_num, contents):
        request_json = BuildRequestData(filepath=filepath,
                                        command_arguments=[command],
                                        filetype=filetype,
                                        line_num=line_num,
                                        column_num=column_num,
                                        contents=contents)
        return self.PostToHandler(COMPLETER_COMMANDS_HANDLER, request_json)

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

    def IgnoreExtraConfFile(self, extra_conf_filename):
        request_json = {'filepath': extra_conf_filename}
        self.PostToHandler(IGNORE_EXTRA_CONF_HANDLER, request_json)

    def _HmacForRequest(self, method, path, body):
        return b64encode(CreateRequestHmac(method, path, body,
                                           self._hmac_secret))

    def _BuildUri(self, handler):
        return self._server_location + handler

    def _CallHttp(self, method, handler, data=None):
        method = method.upper()
        req = Request(self._BuildUri(handler), method=method)
        if isinstance(data, collections.Mapping):
            req.add_header('content-type', 'application/json')
            data = ToUtf8Json(data)
        req.add_header(
            HMAC_HEADER, self._HmacForRequest(method, handler, data))
        req.data = bytes(data, 'utf-8')
        try:
            readData = urlopen(req).read().decode('utf-8')
            return readData
        except HTTPError as err:
            if err.code == 500:
                responseAsJson = json.loads(err.read().decode('utf-8'))
                if responseAsJson['exception']['TYPE'] == "UnknownExtraConf":
                    raise UnknownExtraConf(responseAsJson['exception']['extra_conf_file'])
            raise err

    def IsAlive(self):
        returncode = self._popen_handle.poll()
        # When the process hasn't finished yet, poll() returns None.
        return returncode is None

    def Shutdown(self):
        if self.IsAlive():
            self._popen_handle.terminate()


def CreateRequestHmac(method, path, body, hmac_secret):
    method = bytes(method, 'utf-8')
    path = bytes(path, 'utf-8')
    body = bytes(body, 'utf-8')
    method_hmac = CreateHmac(method, hmac_secret)
    path_hmac = CreateHmac(path, hmac_secret)
    body_hmac = CreateHmac(body, hmac_secret)

    joined_hmac_input = b''.join((method_hmac, path_hmac, body_hmac))
    return CreateHmac(joined_hmac_input, hmac_secret)


def CreateHmac(content, hmac_secret):
    # Must ensure that hmac_secret is str and not unicode
    return hmac.new(hmac_secret,
                    msg=content,
                    digestmod=hashlib.sha256).digest()


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


def PrepareForNewFile(server, path, contents, filetype):
    print("[Ycmd][Notify] {}".format(path))
    return server.SendEventNotification(EventEnum.FileReadyToParse,
                                        filepath=path,
                                        filetype=filetype,
                                        contents=contents)


def SemanticCompletionResults(server, path, row, col, contents, filetype):
    print("[Ycmd][Completion] for {}:{}:{}".format(path, row, col))
    return server.SendCodeCompletionRequest(filepath=path,
                                            filetype=filetype,
                                            line_num=row,
                                            column_num=col,
                                            contents=contents)

def LogServerOutput(stdout):
    for line in iter(stdout.readline, b''):
        s = line.decode('utf-8').rstrip()
        print('[Ycmd][Server] {}'.format(s))
    stdout.close()


def GetUnusedLocalhostPort():
    sock = socket.socket()
    # This tells the OS to give us any free port in the range [1024 - 65535]
    sock.bind(('', 0))
    port = sock.getsockname()[1]
    sock.close()
    return port
