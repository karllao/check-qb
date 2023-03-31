# -*- coding: utf8 -*-

import json
import requests
from email.mime.text import MIMEText
from email.header import Header
import smtplib


test_url_list = [
    {
        'url':'https://www.pttime.org/attendance.php',
        'header' : {
            'accept': '*/*',
            'accept-encoding': 'gzip, deflate, br',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'cookie': '=========你的cookie==============',
            'referer': 'https://www.pttime.org/adults.php',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'
        }
    },
    {
        'url':'https://hdtime.org/attendance.php',
        'header':{
            'accept': '*/*',
            'accept-encoding': 'gzip,deflate,br',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'cache-control': 'no-cache',
            'cookie': '=========你的cookie==============',
            'referer': 'https://hdtime.org/attendance.php',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.84 Safari/537.36'
        }
    }
]


# Third-party SMTP service for sending alert emails. 第三方 SMTP 服务，用于发送告警邮件
mail_host = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxx"       # SMTP server, such as QQ mailbox, need to open SMTP service in the account. SMTP服务器,如QQ邮箱，需要在账户里开启SMTP服务
mail_user = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  # Username 用户名
mail_pass = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  # Password, SMTP service password. 口令，SMTP服务密码
mail_port = 465  # SMTP service port. SMTP服务端口

# The URL address need to dial test. 需要拨测的URL地址


# The notification list of alert emails. 告警邮件通知列表
email_notify_list = {
    "xxxxxxxxxxxxxxx@xxxxxxx.com"
}


def sendEmail(fromAddr, toAddr, subject, content):
    sender = fromAddr
    receivers = [toAddr]
    message = MIMEText(content, 'plain', 'utf-8')
    message['From'] = fromAddr
    message['To'] = toAddr
    message['Subject'] = Header(subject, 'utf-8')
    try:
        smtpObj = smtplib.SMTP_SSL(mail_host, mail_port)
        smtpObj.login(mail_user, mail_pass)
        smtpObj.sendmail(sender, receivers, message.as_string())
        print("send email success")
        return True
    except smtplib.SMTPException as e:
        print(e)
        print("Error: send email fail")
        return False


def test_url(url_list):
    errorinfo = []
    respinfo = []
    # 遍历所有签到任务
    for urldata in url_list:
        resp = None
        try:
            # 请求签到地址
            url = urldata['url']
            header=urldata['header']
            resp = requests.get(url,headers=header, timeout=60)
            # resp.encoding = 'utf-8'
            print (resp)
            print (resp.headers)
            if len(resp.text) != 0 and resp.status_code == 200:
                # body = str(resp)
                respinfo.append("\nAccess : %s success, %s" % (url, str(resp)))
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.ConnectTimeout) as e:
            # 请求超时的失败记录错误信息
            print("request exceptions:" + str(e))
            errorinfo.append("Access " + url + " timeout")
        else:
            # 请求正常相应，检查请求状态码有无异常
            if resp.status_code >= 400:
                # 请求异常，异常状态码记录错误信息
                print("response status code fail:" + str(resp.status_code))
                errorinfo.append("Access " + url + " fail, status code:" + str(resp.status_code))
    if len(errorinfo) != 0:
        body = "\r\n".join(errorinfo + respinfo)
        subject = "Please note: PTCheck Error"
        for toAddr in email_notify_list:
            print ("send message [%s] to [%s]" % (body, toAddr))
            sendEmail(mail_user, toAddr, subject, body)
    else:
        body = "\r\n".join(respinfo)
        subject = "PTCheck success"
        for toAddr in email_notify_list:
            print ("send message to [%s]" % (toAddr))
            sendEmail(mail_user, toAddr, subject, body)



test_url(test_url_list)
