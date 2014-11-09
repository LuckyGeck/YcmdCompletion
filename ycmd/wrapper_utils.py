#!/usr/bin/env python
# -*- coding: utf8 -*-

import collections
import json


# Recurses through the object if it's a dict/iterable and converts all the
# unicode objects to utf-8 strings.
def RecursiveEncodeUnicodeToUtf8(value):
    # if isinstance(value, unicode):
    #     return value.encode('utf8')
    if isinstance(value, str):
        return value
    elif isinstance(value, collections.Mapping):
        return dict(map(RecursiveEncodeUnicodeToUtf8, value.items()))
    elif isinstance(value, collections.Iterable):
        return type(value)(map(RecursiveEncodeUnicodeToUtf8, value))
    else:
        return value


def ToUtf8Json(data):
    return json.dumps(RecursiveEncodeUnicodeToUtf8(data),
                      ensure_ascii=False)
