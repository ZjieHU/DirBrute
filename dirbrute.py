#!/usr/bin/env python
# encoding: utf-8
# email: i@cdxy.me
# github: http://github.com/Xyntax

'''
	多线程并行计算，Queue.get_nowait()非阻塞
		* 生成线程数组
		* 启动线程组
		* 线程组遍历，使每个独立的线程join()，等待主线程退出后，再进入主进程
'''

import libs.requests as requests2
from libs.output import *
from libs.utils.FileUtils import FileUtils
from libs.checkWAF import checkWaf
import threading
import Queue
import optparse
import re
import requests
import sys

sys.getdefaultencoding()
sys.setdefaultencoding('utf8')

# 全局配置
domain_filename = '' #要爆破的域名文件
using_dic = ''  # 使用的字典文件
threads_count = 1  # 线程数
timeout = 3  # 超时时间
allow_redirects = True  # 是否允许URL重定向
headers = {  # HTTP 头设置
             'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_3) AppleWebKit/535.20 (KHTML, like Gecko) Chrome/19.0.1036.7 Safari/535.20',
             'Referer': 'http://www.google.com',
             'Cookie': 'whoami=wyscan_dirfuzz',
             }
proxies = {  # 代理配置
    # "http": "http://user:pass@10.10.1.10:3128/",
    # "https": "http://10.10.1.10:1080",
    # "http": "http://127.0.0.1:8118", # TOR 洋葱路由器
}


def outFile(filename, content):
    fp = open(filename, 'a')
    content = content.replace('\r', '').replace('\n', '')
    fp.write(content+'\n')
    fp.close()


def dir_check(url):
    return requests2.get(url, stream=True, headers=headers, timeout=timeout, proxies=proxies,
                        allow_redirects=allow_redirects)


class WyWorker(threading.Thread):
    # 线程初始化，使用OOP传递参数
    def __init__(self, queue):
        threading.Thread.__init__(self)
        self.queue = queue
        self.output = CLIOutput()

    def run(self):
        while True:
            if self.queue.empty():
                break
            # 用hack方法，no_timeout读取Queue队列，直接异常退出线程避免阻塞
            try:
                url = self.queue.get_nowait()
                results = dir_check(url)
                if results.status_code == requests2.codes.ok:
                    dir_exists.append(url)
                    title = ''
                    regx = '<title>(.*?)</title>'
                    objs = re.findall(regx, results.text)
                    for obj in objs:
                        title = title +','+ obj
                    title = title[0:-1]
                    # print results.status_code
                    msg = "[%s]:%s:%s \n" % (results.status_code, results.url, title)
                    outFile('result.txt', msg)
                    self.output.printInLine(msg)
            except Exception, e:
                print e  # 队列阻塞
                break


def check_https(url):
    global headers
    try:
        res = requests.head(url=url, timeout=30, headers=headers)
        return True
    except Exception, e:
        print e
        return False


def fuzz_start(siteurl, file_ext):
    output = CLIOutput()

    urls = []
    if not siteurl.startswith('http://'):
        tmp_url = 'http://%s' % siteurl
        if check_https(tmp_url):
            urls.append(tmp_url)

    if not siteurl.startswith('https://'):
        tmp_url = 'https://%s' % siteurl
        if check_https(tmp_url):
            urls.append(tmp_url)
    print urls

    for siteurl in urls:

        # 检查waf是否存在
        #checkWaf(url=siteurl, header=headers, proxy=proxies, timeout=timeout, allow_redirects=allow_redirects)

        global dir_exists
        dir_exists = []

        # 生成队列堆栈
        queue = Queue.Queue()

        for line in FileUtils.getLines(using_dic):
            line = '%s/%s' % (siteurl.rstrip('/'), line.replace('%EXT%', file_ext))
            queue.put(line)


        output.printHeader('-' * 60)
        output.printTarget(siteurl)
        output.printConfig(file_ext, str(threads_count), str(queue.qsize()))
        output.printHeader('-' * 60)

        # 初始化线程组
        threads = []
        for i in xrange(threads_count):
            threads.append(WyWorker(queue))
        # 启动线程
        for t in threads:
            t.start()
        # 等待线程执行结束后，回到主线程中
        for t in threads:
            t.join()

        output.printHeader('-' * 60)
        for url in dir_exists:
            output.printWarning(url)
        output.printHeader('-' * 60)


if __name__ == "__main__":
    parser = optparse.OptionParser('usage: %prog target [options] \n'
                                   'Example: python %prog www.cdxy.me -e php -t 10\n'
                                   '         python %prog www.cdxy.me -t 10 -d ./dics/ASP/uniq')
    parser.add_option('-e', '--ext', dest='ext',
                      default='html', type='string',
                      help='Choose the extension: php asp aspx jsp...')
    parser.add_option('-f', '--file', dest='file',
                      default='', type='string',
                      help='Choose the domain filename')
    parser.add_option('-t', '--threads', dest='threads_num',
                      default=10, type='int',
                      help='Number of threads. default = 10')
    parser.add_option('-d', '--dic', dest='dic_path', default='./dics/dirs.txt',
                      type='string', help='Default dictionaty: ./dics/dirs.txt')
    (options, args) = parser.parse_args()

    if options.dic_path:
        using_dic = options.dic_path
    if options.threads_num:
        threads_count = options.threads_num
    if options.file:
        domain_filename = options.file
    if len(sys.argv) > 1:
        if domain_filename != '':
            domains = []
            fp = open(domain_filename, 'rb')
            for line in fp:
                line = line.replace('\r', '').replace('\n', '')
                if len(line) > 0 and domains.count(line) == 0:
                    domains.append(line)
                    fuzz_start(line, options.ext)
            fp.close()
        else:
            fuzz_start(sys.argv[1], options.ext)
    else:
        parser.print_help()
        sys.exit(0)
