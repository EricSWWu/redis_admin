﻿# coding=utf-8
import redis
import socket
import sys

from conf import logs
from conf.conf import base, socket_timeout, scan_batch
from redis.exceptions import (
    RedisError,
    ConnectionError,
    TimeoutError,
    BusyLoadingError,
    ResponseError,
    InvalidResponse,
    AuthenticationError,
    NoScriptError,
    ExecAbortError,
    ReadOnlyError
)
from redis._compat import nativestr
from users.models import RedisConf
from monitor.forms import RedisForm

client = None
server_ip = None
db_index = None
unix_socket = None


def get_redis_conf(name=None, user=None):
    if name is None and user is not None:
        return user.auths.all()
    else:
        try:
            return RedisConf.objects.get(name=name)
        except Exception as e:
            logs.error(e)
    return False


def connect(*args, **kwargs):
    """ 连接Redis数据库，参数和redis-py的Redis类一样 """
    global client
    client = redis.Redis(*args, **kwargs)
    return client


def get_client(*args, **kwargs):
    global server_ip
    global db_index
    global unix_socket
    if args or kwargs:
        if (server_ip is not None and db_index is not None) or (unix_socket is not None):
            if (kwargs['host'] == server_ip and kwargs['db'] == db_index) \
                    or unix_socket == kwargs['unix_socket_path'] is not None:
                pass
            else:
                if kwargs['unix_socket_path'] is not None:
                    unix_socket = kwargs['unix_socket_path']
                elif kwargs['host'] is not None and kwargs['port'] is not None:
                    server_ip = kwargs['host']
                    db_index = kwargs['db']
                connect(*args, **kwargs)
        else:
            connect(*args, **kwargs)
            try:
                server_ip = kwargs['host']
                db_index = kwargs['db']
                unix_socket = kwargs['unix_socket_path']
            except Exception as e:
                logs.error(e)

    global client
    if client:
        return client
    else:
        # connect(host='127.0.0.1', port=6379)
        connect(args, kwargs)
        return client


def get_tmp_client(*args, **kwargs):
    from redis import Redis
    return Redis(*args, **kwargs)


def get_all_keys_dict(client=None):
    if client:
        m_all = client.keys()
    else:
        m_all = get_client().keys()
    m_all.sort()
    me = {}
    for key in m_all:
        if len(key) > 100:
            continue
        key_levels = key.split(base['seperator'])
        cur = me
        for lev in key_levels:
            if cur.has_key(lev):
                if cur.keys() == 0:
                    cur[lev] = {lev: {}}  # append(lev)
            else:
                cur[lev] = {}
            cur = cur[lev]
    return me


def get_all_keys_tree(client=None, key='*', cursor=0, min_num=None, max_num=None):
    client = client or get_client()
    key = key or '*'
    if key == '*':
        next_cursor, key_all = client.scan(cursor=cursor, match=key, count=scan_batch)
    else:
        # key = '*%s*' % key
        # next_cursor, key_all = 0, client.keys(key) # keys online will deny all thread execute, so disabled it
        next_cursor, key_all = 0, []
        if client.exists(key):
            key_all = [key]
    key_all = key_all[min_num:max_num]
    key_all.sort()
    return key_all


def check_connect(host, port, password=None, unix_socket_path=None, socket_timeout=30):
    # from redis import Connection
    try:
        redisconn = redis.Redis(host=host, port=port, password=password, socket_timeout=socket_timeout)
        return redisconn.ping()
    except Exception as e:
        logs.error(e)
        return e


def check_redis_connect(name):
    redis_conf = get_redis_conf(name)
    try:
        logs.info("host:{0},port:{1},password:{2},timeout:{3}, socket: {4}".format(
            redis_conf.host, redis_conf.port, redis_conf.password, socket_timeout, redis_conf.socket))
        if redis_conf.socket is not None and redis_conf.socket != "":
            redisconn = redis.Redis(host=redis_conf.host, port=redis_conf.port, password=redis_conf.password,
                                    unix_socket_path=redis_conf.socket)
        else:
            redisconn = redis.Redis(host=redis_conf.host, port=redis_conf.port, password=redis_conf.password)
        return redisconn.ping()
    except Exception as e:
        logs.error(e)
        error = dict(
            redis=redis_conf,
            message=e,
        )
        return error


def get_cl(redis_name, db_id=0):
    cur_db_index = int(db_id)
    server = get_redis_conf(name=redis_name)
    if server is not False:
        if server.socket is not None and server.socket != "":
            cl = get_client(host=server.host, port=server.port, db=cur_db_index, password=None,
                            unix_socket_path=server.socket)
        else:
            cl = get_client(host=server.host, port=server.port, db=cur_db_index, password=server.password)
        return cl, redis_name, cur_db_index
    else:
        return False


def redis_conf_save(request):
    redis_id = request.POST.get("id", None)
    if redis_id is not None:
        try:
            redis_obj = RedisConf.objects.get(id=redis_id)
            redis_form = RedisForm(request.POST, instance=redis_obj)
            if redis_form.is_valid():
                redis_form.save()
                return True
            return False
        except Exception as e:
            logs.error(e)
            return False
    else:
        name = request.POST.get('name', None)
        if RedisConf.objects.filter(name__iexact=name).count() == 0:
            redis_form = RedisForm(request.POST)
            if redis_form.is_valid():
                redis_form.save()
                return True
            logs.error(redis_form.errors)
        return False
