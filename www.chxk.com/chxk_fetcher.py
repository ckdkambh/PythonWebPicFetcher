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

class OptCounter():
    def __init__(self, name, total):
        self.name = name
        self.total = total
        self.count = 0

    def increase(self):
        self.count = self.count + 1

    def __str__(self):
        return '{%s, %d/%d}' % (self.name, self.count, self.total)


class ImgDownloader():
    def __init__(self, basePath, start, end):
        self.basePath = basePath
        self.start = start
        self.end = end
        self.count = 0
        self.headers = {'user-agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.101 Safari/537.36'}

    async def get_current_img(self, name, url):
        while True:
            try:
                async with self.session.get(url, headers=self.headers, ssl=False) as response:
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")
                    imgs = soup.find_all("img")
                    ret = ["https:" + x.attrs["src"] for x in imgs if "title" in x.attrs]
                    self.get_current_img_count[name].increase()
                    print(self.get_current_img_count[name])
                    return ret
            except:
                await asyncio.sleep(2)
                pass

    async def download_img(self, filePath, imgUrl):
        async with self.session.get(imgUrl, headers=self.headers, ssl=False) as response:
            content = await response.content.read()
            fileName = imgUrl.split('/')[5]
            open(filePath + '\\' + fileName, 'wb').write(content)
            self.download_img_count[filePath].increase()
            print(self.download_img_count[filePath])

    async def get_imgs(self, url):
        async with self.session.get(url, headers=self.headers, ssl=False) as response:
            html = await response.text()
            soup = BeautifulSoup(html, "html.parser")
            imgLinks = soup.find_all("a", target="_self")
            maxIdx = max([int(x.string) for x in imgLinks if x.string.isdigit()])
            ret = [url.replace('.html', '_%d.html' % x) for x in range(1, maxIdx + 1)]
            self.img_count.increase()
            print(self.img_count)
            return ret
        
    def get_album_list(self, url):
        get_url = requests.get(url, headers=self.headers)
        soup = BeautifulSoup(get_url.text, "html.parser")
        aList = soup.find_all("a")
        return [{'name' : x.attrs['title'], "url" : 'https://www.chxk.com' + x.attrs['href']} for x in aList if "title" in x.attrs and x.attrs['href'].find('guonei') != -1]

    async def get_imgs_in_albums(self, urlMap):
        async with aiohttp.ClientSession() as session:
            self.session = session
            self.img_count = OptCounter("ImgCount", len(urlMap))
            albumTasks = [{'name' : x['name'], 'task' : asyncio.create_task(self.get_imgs(x['url']))} for x in urlMap]

            imgTasks = []
            self.get_current_img_count = {}
            for i in albumTasks:
                await i['task']
                self.get_current_img_count[i['name']] = OptCounter(i['name'], len(i['task'].result()))
                imgTasks.append({ 'name' : i['name'], 'tasks' : [asyncio.create_task(self.get_current_img(i['name'], x)) for x in i['task'].result()]})

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
                downloadTasks.extend([asyncio.create_task(self.download_img(currentPath, x)) for x in imgList])

            for i in downloadTasks:
                await i

    def run(self):
        start = datetime.now()
        baseUrl = "https://www.chxk.com/guonei/list_1957_%d.html"
        dbase = shelve.open("chxk_recorder")
        albumList = set()
        if 'album_list' in dbase:
            albumList = set(dbase['album_list'])
        dbase.close()

        loop = asyncio.get_event_loop()
        for i in range(self.start, self.end + 1):
            print('start page %d' % i)
            currentList = [x for x in self.get_album_list(baseUrl % i) if x['url'] not in albumList]
            albumList.update([x['url'] for x in currentList])
            loop.run_until_complete(self.get_imgs_in_albums(currentList))
            dbase = shelve.open("chxk_recorder")
            dbase['album_list'] = albumList
            dbase.close()
        print('cost %s' % (datetime.now() - start))

if __name__ == "__main__":
    obj = ImgDownloader(r'D:\down\imgs\chxk', 1, 6)
    obj.run()
