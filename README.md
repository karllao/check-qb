# check-qb
适用小磁盘的机器使用qBittorrent，定时检查做种时间，并检查rss是否存在文件大小适用的种子下载

## 支持qb客户端v4.1+的webui接口

- 按规则筛选种子title的大小信息
- 按添加时间删除做种种子
- 支持win下crontab表达式运行，感谢[micromys/winCron](https://github.com/micromys/winCron)
- 支持添加爱语飞飞接口调用通知

## 使用

先编辑好congfig.py文件里的配置

### windows:

第一种，支持crontab表达式可以自定义时间： 编辑crontab.txt定义定时执行，已存在默认命令，每天8点-23点每2分钟执行一次 命令行运行：start_crontab.bat

第二种方法，运行start_check.bat 60秒执行一次

### linux:

写个crontab，运行run_check.py文件，例如*/2 8-23 * * * python run_check.py

