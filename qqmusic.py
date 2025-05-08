import re
import time
import requests
import json
from urllib.parse import urlparse, parse_qs

def extract_qqmusic_playlist_id(link):
    """
    从 QQ 音乐歌单链接中提取歌单 ID。
    支持多种链接格式，如：
    - https://y.qq.com/n/yqq/playlist/1234567890.html
    - https://c.y.qq.com/qzone/fcg-bin/fcg_ucc_getcdinfo_byids_cp.fcg?disstid=1234567890
    - 短链接形式（如 https://t.qq.com/xxxxxx 转换为实际链接）
    """
    parsed_url = urlparse(link)
    query = parse_qs(parsed_url.query)

    if 'disstid' in query:
        print("从查询参数中提取 QQMusic 歌单 ID")
        return query['disstid'][0]

    path_match = re.search(r'/playlist/(\d+)', parsed_url.path)
    if path_match:
        print("从路径中提取 QQMusic 歌单 ID")
        return path_match.group(1)

    if 't.qq.com' in parsed_url.netloc:
        print("处理 QQMusic 短链接，尝试重定向解析")
        try:
            response = requests.head(link, allow_redirects=True, timeout=5)
            print(f"重定向到: {response.url}")
            return extract_qqmusic_playlist_id(response.url)
        except requests.RequestException as e:
            print(f"无法解析 QQMusic 短链接: {e}")
            return None

    print("无法提取 QQMusic 歌单 ID。")
    return None

class QQMusicList():
    def __init__(self, id):
        self.id = id
        self.headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": f"https://y.qq.com/w/taoge.html?ADTAG=profile_h5&id={self.id}",
            "Origin": "https://y.qq.com",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
        }
        self.session = requests.Session()
        retries = requests.adapters.Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        adapter = requests.adapters.HTTPAdapter(max_retries=retries)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

    def total_song_num(self):
        """
        获取 QQ 音乐歌单的总歌曲数。
        """
        url = f"https://y.qq.com/n/m/detail/taoge/index.html"
        params = {
            "ADTAG": "profile_h5",
            "id": self.id
        }
        method = "GET"
        try:
            resp = self.session.request(method, url, params=params, headers=self.headers, timeout=10)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"QQMusic 获取总歌曲数请求失败: {e}")
            return 0
        match = re.search(r"共(\d+)首", resp.text)
        if match:
            try:
                total_song_num = int(match.group(1))
                print(f"QQMusic 总歌曲数: {total_song_num}")
                return total_song_num
            except ValueError:
                print("QQMusic 无法将总歌曲数转换为整数。")
                return 0
        else:
            print("QQMusic 未能找到总歌曲数。")
            return 0

    def get_list(self):
        """
        获取 QQ 音乐歌单的歌曲列表。
        """
        song_list = []
        url = "https://c.y.qq.com/qzone/fcg-bin/fcg_ucc_getcdinfo_byids_cp.fcg"
        total_song_num = self.total_song_num()
        if total_song_num == 0:
            print("QQMusic 总歌曲数为0，无法获取歌曲列表。")
            return song_list
        for song_begin in range(0, total_song_num, 15):
            params = {
                "_": int(time.time() * 1000)
            }
            postdata = {
                "format": "json",
                "inCharset": "utf-8",
                "outCharset": "utf-8",
                "notice": "0",
                "platform": "h5",
                "needNewCode": "1",
                "new_format": "1",
                "pic": "500",
                "disstid": self.id,
                "type": "1",
                "json": "1",
                "utf8": "1",
                "onlysong": "0",
                "nosign": "1",
                "song_begin": song_begin,
                "song_num": "15",
            }
            try:
                resp = self.session.post(url, headers=self.headers, params=params, data=postdata, timeout=10)
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"QQMusic {song_begin} 页数获取失败: {e}")
                continue
            try:
                data = resp.json()
            except json.JSONDecodeError as e:
                print(f"QQMusic JSON 解析失败: {e}")
                print(f"QQMusic 响应内容: {resp.text}")
                continue
            cdlist = data.get("cdlist")
            if not cdlist:
                print(f"QQMusic 缺少 'cdlist' 键，响应内容: {data}")
                continue
            cd = cdlist[0]
            songlist = cd.get("songlist")
            if not songlist:
                print(f"QQMusic 缺少 'songlist' 键，响应内容: {cd}")
                continue
            for song in songlist:
                name = song.get("name", "未知歌曲")
                singer_info = song.get("singer")
                if not singer_info:
                    singer = "未知歌手"
                else:
                    singer = singer_info[0].get("name", "未知歌手")
                sony_name = f"{name} - {singer}"
                print(sony_name)
                song_list.append(sony_name)
        return song_list