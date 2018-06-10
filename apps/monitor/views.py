# coding:utf-8
from django.http import JsonResponse
from django.shortcuts import render
from django.views.generic.base import View
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from users.models import RedisConf
from conf import logs
import time
from dss.Serializer import serializer

from conf.conf import scan_batch
from public.menu import Menu
from public.redis_api import get_cl, get_redis_conf, redis_conf_save, check_redis_connect
from utils.utils import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from forms import RedisForm


# from public.user_premission import object_user_premission
# Create your views here.


class GetRedisInfo(LoginRequiredMixin, View):
    """
    首页获取redis info信息
    """

    def get(self, request):
        # print request.META["HTTP_REFERER"]
        servers = get_redis_conf(name=None, user=request.user)
        data = []
        for ser in servers:
            try:
                redis_obj = RedisConf.objects.get(id=ser.redis)
            except ObjectDoesNotExist:
                continue
            status = check_redis_connect(name=redis_obj.name)
            if status is True:
                client, cur_server_index, cur_db_index = get_cl(redis_name=redis_obj.name)
                info_dict = client.info()
                time_local = time.localtime(info_dict['rdb_last_save_time'])
                dt = time.strftime("%Y-%m-%d %H:%M:%S", time_local)
                info_dict['rdb_last_save_time'] = dt
                info_dict['socket'] = redis_obj.socket
                # info_dict.update(host=client.connection_pool.connection_kwargs['host'])
                info_dict.update(redis_id=ser.redis)
                data.append(info_dict)
        return render(request, 'index.html', {
            'data': data,
            'console': 'console',
        })


class RedisErrorHtmlView(LoginRequiredMixin, View):
    """
    错误页视图
    """

    def get(self, request):
        return render(request, 'redis_error.html', {
            'error': 'error',
        })


class CheckRedisContent(LoginRequiredMixin, View):
    """
    获取连接错误信息
    """

    def get(self, request):
        servers = get_redis_conf(name=None, user=request.user)
        list = []
        for ser in servers:
            try:
                redis_obj = RedisConf.objects.get(id=ser.redis)
            except ObjectDoesNotExist:
                continue
            status = check_redis_connect(name=redis_obj.name)
            if status is not True:
                info_dict = {'name': status["redis"].name, 'host': status["redis"].host, 'port': status["redis"].port,
                             'error': status["message"].message, 'socket': status['redis'].socket}
                list.append(info_dict)
        if len(list) != 0:
            data = {'code': 0, 'msg': '', 'data': list}
        else:
            data = {'code': 1, 'msg': '无连接错误', 'data': ''}

        return JsonResponse(data)


class GetKeyView(LoginRequiredMixin, View):
    """
    获取key
    """

    def get(self, request, redis_name, db_id):
        from public.redis_api import get_cl, get_all_keys_tree

        values = []
        "搜索"
        search_name = request.GET.get('key[id]', None)
        "分页"
        limit = int(request.GET.get('limit', 30))
        page = int(request.GET.get('page', 1))
        max_num = limit * page
        min_num = max_num - limit

        cl, redis_name, cur_db_index = get_cl(redis_name, int(db_id))
        if search_name is not None:
            keys = get_all_keys_tree(client=cl, key=search_name, cursor=0, min_num=min_num, max_num=max_num)
        else:
            keys = get_all_keys_tree(client=cl, cursor=0, min_num=min_num, max_num=max_num)
        for key in keys:
            values.append({'key': key})

        db_key_num = cl.dbsize()
        batch_key_num = scan_batch
        if batch_key_num > db_key_num:
            key_num = db_key_num
        else:
            key_num = batch_key_num
        key_value_dict = {'code': 0, 'msg': '', 'count': key_num, 'data': values}

        return JsonResponse(key_value_dict, safe=False)


class GetValueView(LoginRequiredMixin, View):
    """
    获取key对应value
    """

    def get(self, request, redis_name, value_db_id, key):
        from public.redis_api import get_cl
        from public.data_view import get_value
        cl, cur_server_index, cur_db_index = get_cl(redis_name, int(value_db_id))
        value_dict = {'code': 0, 'msg': '', 'data': ''}
        if cl.exists(key):
            value = ''
            if request.GET.get("type", None) == 'ttl':
                value = cl.ttl(key)
                if value is None:
                    value = -1
            else:
                try:
                    value = get_value(key, cur_server_index, cur_db_index, cl)
                except Exception as e:
                    logs.error(e)
                    value_dict['code'] = 1
            value_dict['data'] = value
        else:
            value_dict['code'] = 1

        return JsonResponse(value_dict, safe=False)

    def post(self, request, redis_name, value_db_id, key):
        """
        修改TTL
        """
        from public.redis_api import get_cl
        cl, cur_server_index, cur_db_index = get_cl(redis_name, int(value_db_id))
        value_dict = {'code': 0, 'msg': '', 'data': ''}
        ttl = request.POST.get("ttl", None)
        if cl.exists(key) and ttl:
            try:
                cl.expire(key, ttl)
                value_dict['msg'] = "修改成功"
            except Exception as e:
                logs.error(e)
                value_dict['msg'] = '修改失败，请联系管理员'
        return JsonResponse(value_dict)


class GetIdView(LoginRequiredMixin, View):
    """
    key列表
    """

    def get(self, request, redis_name, id):
        return render(request, 'keyvalue.html', {
            'db_id': id,
            'redis_name': redis_name,
            'db_num': 'db' + str(id),
        })


class ClientListView(LoginRequiredMixin, View):
    """
    获取客户端主机
    """

    def get(self, request):
        client_id = request.GET.get('client_id', None)
        if client_id is not None:
            redis_obj = RedisConf.objects.get(id=client_id)
            status = check_redis_connect(name=redis_obj.name)
            if status is True:
                client, cur_server_index, cur_db_index = get_cl(redis_name=redis_obj.name)
                client_list = client.client_list()
                "分页"
                limit = int(request.GET.get('limit', 30))
                page = int(request.GET.get('page', 1))
                max_num = limit * page
                min_num = max_num - limit

                data = {'code': 0, 'msg': '', 'count': len(client_list), 'data': client_list[min_num:max_num]}
        else:
            data = {'code': 1, 'msg': 'Error, 请联系系统管理员！', 'data': ''}

        return JsonResponse(data, safe=False)


class ClientHtmlView(LoginRequiredMixin, View):
    def get(self, request, client_id):
        return render(request, 'client_list.html', {
            'client_id': client_id,
        })


class DelKeyView(LoginRequiredMixin, View):
    """
    删除key
    """

    def post(self, request):
        from public.data_change import ChangeData
        from loginfo.models import OperationInfo
        from public.redis_api import get_cl
        from public.data_view import get_value

        redis_name = request.POST.get('redis_name', None)
        db_id = request.POST.get('db_id', None)
        key = request.POST.get('key', None)

        cl, redis_name, cur_db_index = get_cl(redis_name, int(db_id))
        old_data = get_value(key, redis_name, cur_db_index, cl)
        db = OperationInfo(
            username=request.user.username,
            server=redis_name,
            db=db_id,
            key=key,
            old_value=old_data,
            type='del',
        )
        db.save()

        if key:
            ch_data = ChangeData(redis_name=redis_name, db_id=db_id)

            if ch_data.delete_key(key=key):
                data = {'code': 0, 'msg': 'KEY: ' + key + ' is Success', 'data': ''}
                return JsonResponse(data)

        data = {'code': 1, 'msg': 'KEY: ' + key + ' is Failed', 'data': ''}

        return JsonResponse(data)


class EditValueTableView(LoginRequiredMixin, View):
    """
    编辑value
    """

    def get(self, request, redis_name, edit_db_id):
        from public.redis_api import get_cl
        from public.data_view import get_value
        cl, redis_name, cur_db_index = get_cl(redis_name, int(edit_db_id))
        key = request.GET.get('key', None)
        if cl.exists(key):
            value = get_value(key, redis_name, cur_db_index, cl)
            if cl.type(key) == 'list':
                value_list = []
                num = 0
                for i in value['value']:
                    value_dict = {str(num): i}
                    num += 1
                    value_list.append(value_dict)
                value['value'] = value_list

        return render(request, 'edit.html', {
            'db_num': 'db' + str(edit_db_id),
            'redis_name': redis_name,
            'data': value,
        })

    def post(self, request, redis_name, edit_db_id):
        from public.data_change import ChangeData
        from public.redis_api import get_cl
        from public.data_view import get_value
        from loginfo.models import OperationInfo

        cl, cur_server_index, cur_db_index = get_cl(redis_name, int(edit_db_id))
        ch_data = ChangeData(redis_name=redis_name, db_id=edit_db_id)

        key = request.GET.get('key', None)
        post_key_type = request.POST.get('Type', None)
        old_data = get_value(key, cur_server_index, cur_db_index, cl)

        if post_key_type == 'string':
            post_value = request.POST.get('value', None)
            ch_data.edit_value(key=key, value=None, new=post_value, score=None)
        elif post_key_type == 'zset':
            score = request.POST.get('Score', None)
            value = request.POST.get('Value', None)
            old_value = request.POST.get('Old_Value', None)
            ch_data.edit_value(key=key, value=old_value, new=value, score=score)
        elif post_key_type == 'set':
            value = request.POST.get('Value', None)
            old_value = request.POST.get('Old_Value', None)
            ch_data.edit_value(key=key, value=old_value, new=value, score=None)
        elif post_key_type == 'hash':
            value_key = request.POST.get('Key', None)
            value = request.POST.get('Value', None)
            ch_data.edit_value(key=key, value=value_key, new=value, score=None)
        elif post_key_type == 'list':
            index = request.POST.get('Index', None)
            value = request.POST.get('Value', None)
            ch_data.edit_value(key=key, value=index, new=value, score=None)

        data = get_value(key, cur_server_index, cur_db_index, cl)
        if cl.type(key) == 'list':
            value_list = []
            num = 0
            for i in data['value']:
                value_dict = {str(num): i}
                num += 1
                value_list.append(value_dict)
            data['value'] = value_list

        db = OperationInfo(
            username=request.user.username,
            server=redis_name,
            db='db' + edit_db_id,
            key=key,
            old_value=old_data,
            value=data,
            type='edit',
        )
        db.save()

        return render(request, 'edit.html', {
            'db_num': 'db' + str(edit_db_id),
            'redis_name': redis_name,
            'data': data
        })


class BgSaveView(LoginRequiredMixin, View):
    """
    保存数据 bgsave
    """

    def get(self, request, redis_id):
        redis_obj = RedisConf.objects.get(id=redis_id)
        cl, cur_server_index, cur_db_index = get_cl(redis_name=redis_obj.name, db_id=0)
        cl.bgsave()

        return HttpResponseRedirect(reverse("index"))


class AddKeyView(LoginRequiredMixin, View):
    """
    添加数据
    """

    def get(self, request, redis_name):
        this_tab = 'string'
        db_id = request.GET.get('db', None)

        return render(request, 'add_key.html', {
            'this_tab': this_tab,
            'db': db_id,
        })

    def post(self, request, redis_name):
        from public.data_change import ChangeData
        db_id = request.POST.get('db_id', None)
        type = request.POST.get('type', None)
        key = request.POST.get('key', None)
        value = request.POST.get('value', None)
        ttl = request.POST.get('ttl', None)

        ch_data = ChangeData(redis_name=redis_name, db_id=db_id)
        if type == 'string':
            ch_data.add_key(key=key, value=value, type=type, ttl=ttl)
        elif type == 'zset':
            score = request.POST.get('score', None)
            print("add data:", key, value, score, type, ttl, "---------------------")
            ch_data.add_key(key=key, value=value, type=type, score=int(score), ttl=ttl)
        elif type == 'set':
            ch_data.add_key(key=key, value=value, type=type, ttl=ttl)
        elif type == 'hash':
            vkey = request.POST.get('vkey', None)
            ch_data.add_key(key=key, value=value, type=type, vkey=vkey, ttl=ttl)
        elif type == 'list':
            ch_data.add_key(key=key, value=value, type=type, ttl=ttl)

        return HttpResponseRedirect('/' + redis_name + '/db' + db_id + '/')


class ClearDbView(LoginRequiredMixin, View):
    """
    清空DB
    """

    def post(self, request):
        return JsonResponse({"code": 1, "msg": "this operation not allow!", "data": ""})
        data = {"code": 0, "msg": "successful", "data": ""}
        redis_name = request.POST.get("redis_name", None)
        db_id = request.POST.get("db_id", None)
        try:
            cl, cur_server_index, cur_db_index = get_cl(redis_name=redis_name, db_id=db_id)
            cl.flushdb()
        except Exception as e:
            logs.error(e)
            data["code"] = 1
            data["msg"] = "failed"
        return JsonResponse(data=data, safe=False)


class RedisListView(LoginRequiredMixin, View):
    def get(self, request):
        if request.is_ajax():
            data = {"code": 0, "msg": "", "data": ""}
            redis_objs = RedisConf.objects.all()
            data["data"] = serializer(redis_objs)
            return JsonResponse(data=data)
        return render(request, 'redis_list.html', {
        })


class RedisEditView(LoginRequiredMixin, View):
    def post(self, request):
        data = {"code": 0, "data": "", "msg": "成功"}
        status = redis_conf_save(request)
        if not status:
            data["code"] = 1
            data["msg"] = "失败"
        return JsonResponse(data=data, safe=False)


class RedisAddView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, 'redis_add.html', {})

    def post(self, request):
        data = {"code": 0, "data": "", "msg": "成功"}
        status = redis_conf_save(request)
        if not status:
            data["code"] = 1
            data["msg"] = "失败"
        return JsonResponse(data=data, safe=False)


class RedisDelView(LoginRequiredMixin, View):
    def post(self, request):
        redis_id = request.POST.get('id', None)
        data = {'code': 0, 'data': '', 'msg': '成功'}
        try:
            RedisConf.objects.get(id=redis_id).delete()
        except Exception as e:
            logs.error(e)
            data['code'] = 1
            data['msg'] = '失败，请查看日志'
        return JsonResponse(data=data)
