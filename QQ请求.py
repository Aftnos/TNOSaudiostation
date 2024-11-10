import re
import time
import requests
import json
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

class QQMusicList():
    def __init__(self, id):
        self.id = id
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 8.0.0; Pixel 2 XL Build/OPD1.170816.004) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Mobile Safari/537.36",
            "Referer": f"https://y.qq.com/w/taoge.html?ADTAG=profile_h5&id={self.id}",
            "Origin": "https://y.qq.com",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
        }
        self.session = requests.Session()
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

    def total_song_num(self):
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
            print(f"获取总歌曲数请求失败: {e}")
            return 0
        match = re.search(r"共(\d+)首", resp.text)
        if match:
            try:
                total_song_num = int(match.group(1))
                print(f"总歌曲数: {total_song_num}")
                return total_song_num
            except ValueError:
                print("无法将总歌曲数转换为整数。")
                return 0
        else:
            print("未能找到总歌曲数。")
            return 0

    def get_list(self):
        song_list = []
        url = "https://c.y.qq.com/qzone/fcg-bin/fcg_ucc_getcdinfo_byids_cp.fcg"
        total_song_num = self.total_song_num()
        if total_song_num == 0:
            print("总歌曲数为0，无法获取歌曲列表。")
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
                print(f"{song_begin} 页数获取失败: {e}")
                continue
            try:
                data = resp.json()
                print(f"响应 JSON: {json.dumps(data, ensure_ascii=False, indent=2)}")  # 调试输出
            except json.JSONDecodeError as e:
                print(f"JSON 解析失败: {e}")
                print(f"响应内容: {resp.text}")
                continue
            cdlist = data.get("cdlist")
            if not cdlist:
                print(f"缺少 'cdlist' 键，响应内容: {data}")
                continue
            cd = cdlist[0]
            songlist = cd.get("songlist")
            if not songlist:
                print(f"缺少 'songlist' 键，响应内容: {cd}")
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

    def start(self):
        datas = self.get_list()
        if not datas:
            print("未获取到任何歌曲。")
            return
        to_file_data = "\n".join(datas)
        file_name = f"{self.id} QQ音乐歌单.txt"
        try:
            with open(file_name, "w", encoding="utf-8") as file:
                file.write(to_file_data)
            print(f"文件成功保存到:{file_name},"
                  f"歌曲数量:{len(datas)}")
        except IOError as e:
            print(f"写入文件失败: {e}")

if __name__ == '__main__':
    playlist_link = input("请输入 QQ 音乐歌单链接: ").strip()
    # 从链接中提取 ID
    match = re.search(r'/playlist/(\d+)', playlist_link)
    if match:
        playlist_id = match.group(1)
    else:
        print("无法提取歌单 ID。请检查链接格式。")
        exit(1)
    print(f"提取到歌单 ID: {playlist_id}")
    wang_qq_list = QQMusicList(playlist_id)
    wang_qq_list.start()
