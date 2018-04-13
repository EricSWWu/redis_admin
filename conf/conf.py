#!/usr/bin/env python
# coding:utf-8
__author__ = 'carey'
__date__ = '2017/12/25'

DEBUG = True

LOG_LEVEL = 'INFO'

# redis
base = {
    'seperator': ':',
    'maxkeylen': 100
}
socket_timeout = 5
scan_batch = 10000  # scan 限制获取数据量
show_key_self_count = False
