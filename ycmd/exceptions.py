# -*- coding: utf8 -*-

class UnknownExtraConf(Exception):
    def __init__(self, extra_conf_file):
        message = "YcmdCompletion found {0}. Load?".format(extra_conf_file)
        super(UnknownExtraConf, self).__init__(message)
        self.extra_conf_file = extra_conf_file
