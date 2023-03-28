#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re

class main_config:

    # qb客户端的WEB UI地址+端口
    main_url = "http://xxxxxx:xxxx"


    # 登录qb的账号密码
    param = {
        "username": "xxxx",
        "password": "xxxxx"
    }


    # 用于check_torrents_addtime()方法的种子最大添加时间，超过则删除
    max_addtime = 43200

    # 过滤规则，这里的规则是只选1-6GB的资源下载
    rule = re.compile('(?<=\[)[1-6]{1}\.\d+(?=\sGB\])')

    # rss订阅组名称
    rss_item = 'xxx'

    # 允许同时运行种子的最大值
    max_num = 5

    # 爱语飞飞token
    token = 'xxxxx'
