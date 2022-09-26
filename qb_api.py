#!/usr/bin/env python
# -*- coding: utf-8 -*-
from config import main_config
import requests
import time
import re
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def login(main_url,param):
    """
    登录获取cookie
    :param main_url:
    :param param:
    :return:
    """
    logger.info("===开始登录qBittorrent获取cookie===")
    session = requests.Session() # 空白session对象
    headers = {
        'Referer':main_url,
        'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36',
    }
    url = '/api/v2/auth/login'
    login_url = main_url + url
    response = session.get(url= login_url,headers=headers,params=param) # 获取cookie存储到session
    logger.info(response.text)
    return session


def get_torrents_info(session,main_url):
    """
    获取所有种子信息
    :param session:
    :param main_url:
    :return:
    """
    logger.info("===获取qBittorrent当前所有的种子信息===")
    url = '/api/v2/torrents/info'
    headers = {
        'Referer': main_url,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36',
    }
    #此时的session发请求带有cookies，该cookie包含手动添加和发起url获得的cookie
    response = session.get(url=main_url + url,headers=headers)
    data = response.json()
    # logger.info(data)
    return data


def del_torrents(session,main_url,hashes,name):
    """
    删除单个种子
    :param session:
    :param main_url:
    :return:
    """
    logger.info("===执行删除单个种子，哈希值为：{0}".format(hashes))
    url = '/api/v2/torrents/delete'
    headers = {
        'Referer': main_url,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36',
    }
    data = {
        "hashes": hashes,
        "deleteFiles": True
    }
    response = session.post(url=main_url + url,headers=headers,data=data)
    if response.status_code == 200:
        logger.info("删除 {0} 种子完成".format(name))
    else:
        logger.info(response.status_code)
        logger.info("删除 {0} 种子【失败】！！！".format(name))


def add_torrents(session,main_url,torrents_urls,name):
    """
    通过url添加单个种子
    :param session:
    :param main_url:
    :return:
    """
    logger.info("===执行添加单个种子，种子地址为：{0}".format(torrents_urls))
    url = '/api/v2/torrents/add'
    headers = {
        'Referer': main_url,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36',
    }
    data = {
        "urls": torrents_urls
    }
    response = session.post(url=main_url + url,headers=headers,data=data)
    if response.status_code == 200:
        logger.info("添加新种子完成：{0} ".format(name))
    elif response.status_code == 415:
        logger.info("添加新种子失败，Torrent 文件无效：{0} ".format(name))
    else:
        logger.info("添加新种子【失败】！！！")


def get_rss_matchingArticles(session,main_url,ruleName):
    """
    获取所有符合规则的rss文章(没啥用，只能拿到名字）
    :param session:
    :param main_url:
    :return:
    """
    logger.info("===获取所有符合rss规则的文章===")
    url = '/api/v2/rss/matchingArticles'
    headers = {
        'Referer': main_url,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36',
    }
    param = {
        "ruleName": ruleName
    }
    response = session.get(url=main_url + url,headers=headers,params=param)
    data = response.json()
    logger.info(data)
    return data


def get_rss_items(session,main_url,rss_item):
    """
    获取以 JSON 格式返回所有 RSS 项目数据
    :param session:
    :param main_url:
    :return:
    """
    logger.info("===获取以 JSON 格式返回所有 RSS 项目数据===")
    # 先刷新订阅源，调用刷新接口
    url = '/api/v2/rss/refreshItem'
    headers = {
        'Referer': main_url,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36',
    }
    data = {
        "itemPath": rss_item
    }
    response = session.post(url=main_url + url, headers=headers, data=data)
    if response.status_code == 200:
        logger.info("刷新 {0} 订阅组完成".format(rss_item))
    else:
        logger.info("刷新 {0} 订阅组【失败】！！！".format(rss_item))
    # 刷新完成后获取最新的订阅数据
    url = '/api/v2/rss/items'
    data = {
        "withData": True
    }
    response = session.post(url=main_url + url,headers=headers,data=data)
    data = response.json()
    # logger.info(data)
    return data


def mark_Read(session,main_url,rss_item):
    """
    将订阅组所有数据标记成已读状态
    :param session:
    :param main_url:
    :param rss_item:
    :return:
    """
    logger.info("===将订阅组所有数据标记成已读状态===")
    # 先刷新订阅源，调用刷新接口
    url = '/api/v2/rss/markAsRead'
    headers = {
        'Referer': main_url,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36',
    }
    data = {
        "itemPath": rss_item
    }
    response = session.post(url=main_url + url, headers=headers, data=data)
    if response.status_code == 200:
        logger.info("标记 {0} 订阅组已读完成".format(rss_item))
    else:
        logger.info("标记 {0} 订阅组已读【失败】！！！".format(rss_item))


def filter_rss(rss_data,rss_item,rule):
    """
    处理rss，按正则规则过滤
    :param rss_data: get_rss_items()方法获取的数据
    :param rss_item: qB里的RSS订阅的站点
    :param rule: 过滤用的判断文件大小正则规则
    :return:
    """
    torrents_data = rss_data[rss_item]['articles']
    filter_torrents = []
    for torrent in torrents_data:
        title = torrent['title']
        match = re.search(rule,title)
        if match is not None:
            logger.info(match.group())
            torrent['size'] = float(match.group())
            if "isRead" in torrent:
                if torrent['isRead'] == True:
                    logger.info("已读文件被过滤：{0}".format(title))
                else:
                    logger.info("未知文件无法处理，先被过滤：{0}".format(title))
            else:
                filter_torrents.append(torrent)
                logger.info("匹配规则成功，添加种子到返回数据：{0}".format(title))
        else:
            logger.info("种子不符合规则被过滤：{0}".format(title))
    # logger.info(filter_torrents)
    return filter_torrents



def check_torrents_addtime(session,main_url,max_addtime):
    """
    检查种子添加时间，超过指定时间删除
    :param session:
    :param main_url:
    :return:
    """
    logger.info("===开始检查种子添加时间，超过{0}秒将删除===".format(max_addtime))
    headers = {
        'Referer': main_url,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36',
    }
    torrents_info  = get_torrents_info(session, main_url)
    now_time = time.time()
    check_del_torrent = []
    for torrent in torrents_info:
        add_time = torrent['added_on']
        hash = torrent['hash']
        name = torrent['name']
        torrent_size = torrent['total_size']/1024/1024/1024
        if now_time - add_time > max_addtime:
            check_del_torrent.append(torrent)
            del_torrents(session,main_url,hash,name)
            logger.info("删除种子：{0},大小：{1} GB".format(name,round(torrent_size, 2)))
        else:
            logger.info("未过期：{0},大小：{1} GB".format(name,round(torrent_size, 2)))
    # logger.info(check_del_torrent)
    return check_del_torrent


def send_msg(token,text,desp='来自check_qb的通知'):
    """
    调用爱语飞飞接口发送微信通知
    :param token:
    :param text:
    :param desp:
    :return:
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36',
    }
    param = {
        "text": text,
        "desp": desp
    }
    url = "https://iyuu.cn/{0}.send".format(token)
    response = requests.post(url=url, headers=headers, params=param)
    if response.status_code == 200:
        logger.info("发送微信通知成功")
    else:
        logger.info("发送微信通知【失败】！！！")




if __name__=="__main__":
    # qb客户端的WEB UI地址+端口
    main_url = main_config.main_url
    # 登录qb的账号密码
    login_param = main_config.param
    # 用于check_torrents_addtime()方法的种子最大添加时间，超过则删除
    max_addtime = main_config.max_addtime
    # 登录qb
    session = login(main_url,login_param)
    # 获取所有种子信息
    #get_torrents_info(session,main_url)
    # 获取所有符合rss规则的种子文章(没啥用，只能拿到名字）
    #get_rss_matchingArticles(session, main_url,"hdtime")
    # 检查种子添加时间是否超过最大时间
    #check_torrents_addtime(session, main_url, max_addtime)
    # 获取所有rss项目
    rss_item = main_config.rss_item
    rss_data = get_rss_items(session,main_url,rss_item)
    # 获取rss并过滤整理
    rule = main_config.rule
    filter_rss(rss_data, rss_item, rule)
    # 批量已读订阅源
    # mark_Read(session,main_url,rss_item)
    # 新增种子推送
    add_torrents(session,main_url,'xxxxxxxxxxx','Handy Manny S03 1080p DSNP WEB-DL DDP5.1 H.264-playWEB[77.28 GB]')


