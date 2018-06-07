#!/usr/bin/env python
# coding:utf-8
__author__ = 'carey'
__date__ = '2017/10/12'

from public.redis_api import get_tmp_client, check_redis_connect, get_redis_conf, get_cl
from users.models import RedisConf
from django.core.exceptions import ObjectDoesNotExist


def Menu(user):
    """
    菜单导航
    :return:
    """
    servers = get_redis_conf(name=None, user=user)
    data = []
    m_index = 0
    for ser in servers:
        try:
            redis_obj = RedisConf.objects.get(id=ser.redis)
        except ObjectDoesNotExist:
            continue
        data_is = {'name': redis_obj.name, 'db': ''}
        status = check_redis_connect(name=redis_obj.name)
        if isinstance(status, bool) and status:
            me = []
            for i in range(redis_obj.database):
                me.append('db{0}'.format(i))
            data_is['db'] = me
            data.append(data_is)
            m_index += 1
    return data
