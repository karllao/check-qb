#!/usr/bin/env python
# -*- coding: utf-8 -*-

from qb_api import *
from config import main_config
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_qb(main_url,login_param,max_num,max_addtime,rss_item,rule):

    # 登录qb
    session = login(main_url, login_param)
    # 获取qb所有种子信息
    torrents_info = get_torrents_info(session, main_url)
    #  logger.info(torrents_info)
    if len(torrents_info) >= max_num:
        logger.warning("【节点：已满种子最大值】")
        # 检查种子添加时间是否超过最大时间，执行删除操作
        check_del_torrent = check_torrents_addtime(session, main_url, max_addtime)
        if check_del_torrent == []:
            logger.warning("【节点：暂无可删除的超时种子】")
            # 刷新并获取所有rss项目数据
            get_rss_items(session, main_url, rss_item)
            # 批量已读订阅源
            mark_Read(session, main_url, rss_item)
            # send_msg(token, '暂无可删除的超时种子')
        else:
            logger.warning("【节点：存在超时添加种子，删除部分种子】")
            for del_torrents in check_del_torrent:
                # 打印已移除的种子
                logger.info("已移除种子：{0}".format(del_torrents['name']))
                send_msg(token, '删除种子',del_torrents['name'])
    else:
        logger.warning("【节点：未达到种子数做种最大值，开始拉取rss尝试添加】")
        # 计算与最大值的差值
        missing_num = max_num - len(torrents_info)
        # 刷新并获取所有rss项目数据
        rss_data = get_rss_items(session, main_url, rss_item)
        # 根据规则过滤有效的种子
        valid_rss = filter_rss(rss_data, rss_item, rule)
        if valid_rss == []:
            logger.warning("【节点：暂无符合规则的种子添加填充】")
            # 批量已读订阅源
            mark_Read(session, main_url, rss_item)
            # logger.info("暂无符合规则的种子添加。。。")
            # send_msg(token, '无可用种子新增')
        else:
            logger.warning("【节点：找到可用种子，执行新增】")
            # 有效种子的数量
            valid_num = len(valid_rss)
            # 批量添加种子
            for count in range(0,min(valid_num,missing_num)): #有效种子数和差值比较，取小的值，防止发送过多种子或数组越界报错
                torrent = valid_rss[count]
                torrent_url = torrent['torrentURL']
                torrent_title = torrent['title']
                add_torrents(session, main_url, torrent_url,torrent_title)
                send_msg(token, '新增推送种子',torrent_title + torrent_url)
            mark_Read(session, main_url, rss_item)





if __name__=="__main__":
    # 获取qb客户端的WEB UI地址+端口
    main_url = main_config.main_url
    # 获取登录qb的账号密码
    login_param = main_config.param
    # 获取允许同时运行种子的最大值
    max_num = main_config.max_num
    # 获取用于check_torrents_addtime()方法的种子最大添加时间，超过则删除
    max_addtime = main_config.max_addtime
    # 获取订阅源组名
    rss_item = main_config.rss_item
    # 获取rss并过滤整理
    rule = main_config.rule
    # 获取爱语飞飞 token
    token = main_config.token

    # 主函数
    check_qb(main_url, login_param, max_num, max_addtime, rss_item, rule)

