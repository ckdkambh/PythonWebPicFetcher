import requests,re,json,html2text,sys,time,urllib.parse
from bs4 import BeautifulSoup
from array import array
import time 
from urllib.request import urlretrieve
import os
import shelve
import aiohttp
import asyncio
from datetime import datetime
from functools import wraps
import random

def asyn_auto_retry(func):
    @wraps(func)
    async def inner(*args):
        while True:
            try:
                print('%s start, %s' % (func.__name__, args[1:]))
                return await func(*args)
            except:
                # print('retry...')
                await asyncio.sleep(random.randint(1,20))
                pass
    return inner

class OptCounter():
    def __init__(self, name, total):
        self.name = name
        self.total = total
        self.count = 0

    def increase(self):
        self.count = self.count + 1

    def isDone(self):
        return self.count == self.total

    def __str__(self):
        return '{%s, %d/%d}' % (self.name, self.count, self.total)


class ImgDownloader():
    def __init__(self, basePath, start, end):
        self.basePath = basePath
        self.start = start
        self.end = end
        self.count = 0
        self.headers = {'user-agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.101 Safari/537.36'}
        self.timeout = 60
        self.parallelism = 5
        self.dbname = "xrmn5_recorder"

    @asyn_auto_retry
    async def get_current_img(self, name, url):
        start = datetime.now()
        Timeout = aiohttp.ClientTimeout(total = self.timeout)
        async with self.session.get(url, headers=self.headers, ssl=False, timeout=Timeout) as response:
            html = await response.text()
            soup = BeautifulSoup(html, "html.parser")
            imgs = soup.find_all("img")
            ret = ["https://pic.xrmn5.com" + x.attrs["src"] for x in imgs if "title" in x.attrs]
            self.get_current_img_count[name].increase()
            print('get_current_img end, %s, %s, time %s' % (url, self.get_current_img_count[name], datetime.now() - start))
            return ret

    @asyn_auto_retry
    async def download_img(self, filePath, baseUrl, imgUrl):
        start = datetime.now()
        Timeout = aiohttp.ClientTimeout(total = self.timeout)

        fileName = filePath + '\\' + imgUrl.split('/')[6]
        if fileName.exists():
            pass
        else:
            async with self.session.get(imgUrl, headers=self.headers, ssl=False, timeout=Timeout) as response:
                content = await response.content.read()
                with open(fileName, 'wb') as f:
                    f.write(content)
        self.download_img_count[filePath].increase()
        print('download_img end, %s, %s, time %s' % (imgUrl, self.download_img_count[filePath], datetime.now() - start))
        if self.download_img_count[filePath].isDone():
            print('%s is done' % filePath)
            self.persist(baseUrl)

    # 获取所有页码的链接
    @asyn_auto_retry
    async def get_imgs(self, url):
        start = datetime.now()
        Timeout = aiohttp.ClientTimeout(total = self.timeout)
        async with self.session.get(url, headers=self.headers, ssl=False, timeout=Timeout) as response:
            html = await response.text()
            # codingTypr = response.encoding
            # html = html.text.encode(codingTypr, errors='ignore').decode('utf-8', errors='ignore')
            soup = BeautifulSoup(html, "html.parser")
            imgLinks = [x for x in soup.find_all("a") if 'target' not in x.attrs and 'alt' not in x.attrs and x.string != None]
            maxIdx = max([int(x.string) for x in imgLinks if x.string.isdigit()])
            ret = [url]
            ret.extend([url.replace('.html', '_%d.html' % x) for x in range(1, maxIdx)])
            self.img_count.increase()
            print('get_imgs end, %s, %s, time %s' % (url, self.img_count, datetime.now() - start))
            return ret
        
    def get_album_list(self, url):
        start = datetime.now()
        get_url = requests.get(url, headers=self.headers)
        codingTypr = get_url.encoding
        text = get_url.text.encode(codingTypr, errors='ignore').decode('utf-8', errors='ignore')
        soup = BeautifulSoup(text, "html.parser")
        aList = soup.find_all("a")
        print('get_album_list, time %s' % (datetime.now() - start))
        return [{'name' : x.attrs['title'], "url" : 'https://www.xrmn5.com/' + x.attrs['href']} for x in aList if "title" in x.attrs and 'target' not in x.attrs and len(x.contents) > 1]

    async def get_imgs_in_albums(self, urlMap):
        async with aiohttp.ClientSession() as session:
            self.session = session
            self.img_count = OptCounter("ImgCount", len(urlMap))
            albumTasks = [{'name' : x['name'], 'baseUrl' : x['url'], 'task' : asyncio.create_task(self.get_imgs(x['url']))} for x in urlMap]

            imgTasks = []
            self.get_current_img_count = {}
            for i in albumTasks:
                await i['task']
                self.get_current_img_count[i['name']] = OptCounter(i['name'], len(i['task'].result()))
                imgTasks.append({ 'name' : i['name'], 'baseUrl' : i['baseUrl'], 'tasks' : [asyncio.create_task(self.get_current_img(i['name'], x)) for x in i['task'].result()]})

            downloadTasks = []
            self.download_img_count = {}
            for i in imgTasks:
                imgList = []
                for j in i['tasks']:
                    await j
                    imgList.extend(j.result())
                currentPath = os.path.join(self.basePath, i['name'].replace('|', '').replace(':', '').replace('?', ''))
                try:
                    os.makedirs(currentPath)
                except:
                    pass
                self.download_img_count[currentPath] = OptCounter(currentPath, len(imgList))
                downloadTasks.extend([asyncio.create_task(self.download_img(currentPath, i['baseUrl'], x)) for x in imgList])

            for i in downloadTasks:
                await i

    def run(self):
        start = datetime.now()
        baseUrl = "https://www.xrmn5.com/XiuRen/"
        dbase = shelve.open(self.dbname)
        self.albumList = set()
        if 'album_list' in dbase:
            self.albumList = set(dbase['album_list'])
        dbase.close()

        loop = asyncio.get_event_loop()
        for i in range(self.start, self.end + 1):
            print('start page %d' % i)
            if i == 1:
                currentList = [x for x in self.get_album_list(baseUrl) if x['url'] not in self.albumList]
            else:
                currentList = [x for x in self.get_album_list(baseUrl + 'index%d.html' % i) if x['url'] not in self.albumList]
            for j in range(0, len(currentList), self.parallelism):
                loop.run_until_complete(self.get_imgs_in_albums(currentList[j : j + self.parallelism]))
        print('cost %s' % (datetime.now() - start))

    def persist(self, url):
        self.albumList.add(url)
        dbase = shelve.open(self.dbname)
        dbase['album_list'] = self.albumList
        dbase.close()



if __name__ == "__main__":
    obj = ImgDownloader(r'D:\down\imgs\xrmn5', 1, 1)
    obj.run()
