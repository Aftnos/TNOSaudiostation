import re
import time
import requests
import json
from urllib.parse import urlparse, parse_qs
from fuzzywuzzy import fuzz
from tqdm import tqdm
import sys
import threading
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import messagebox, filedialog
from tkinter.scrolledtext import ScrolledText  # 使用标准 ScrolledText

# --------------------- NetEase Music Handling ---------------------

def extract_netease_playlist_id(link):
    """
    从网易云音乐歌单链接中提取歌单 ID。
    支持多种链接格式，如：
    - https://music.163.com/#/playlist?id=2657399934&creatorId=1756433368
    - https://music.163.com/playlist/2657399934
    - 短链接形式（如 https://t.cn/xxxxxx 转换为实际链接）
    """
    parsed_url = urlparse(link)
    query = parse_qs(parsed_url.query)

    # 尝试从查询参数中获取 ID
    if 'id' in query:
        print("从查询参数中提取 NetEase 歌单 ID")
        return query['id'][0]

    # 尝试从片段中提取 ID
    fragment = parsed_url.fragment
    fragment_query = parse_qs(urlparse(fragment).query)
    if 'id' in fragment_query:
        print("从片段查询参数中提取 NetEase 歌单 ID")
        return fragment_query['id'][0]

    # 尝试从片段的路径中提取 ID
    path_match = re.search(r'/playlist/(\d+)', fragment)
    if path_match:
        print("从片段路径中提取 NetEase 歌单 ID")
        return path_match.group(1)

    # 如果是短链接，尝试获取重定向后的实际链接
    if 't.cn' in parsed_url.netloc:
        print("处理 NetEase 短链接，尝试重定向解析")
        try:
            response = requests.head(link, allow_redirects=True, timeout=5)
            print(f"重定向到: {response.url}")
            return extract_netease_playlist_id(response.url)
        except requests.RequestException as e:
            print(f"无法解析 NetEase 短链接: {e}")
            return None

    print("无法提取 NetEase 歌单 ID。")
    return None

def get_netease_playlist_details(playlist_id):
    """
    通过网易云音乐歌单 ID 获取歌单详情，包括歌曲名称和作者。
    """
    url = "https://music.163.com/api/v6/playlist/detail"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://music.163.com/",
        "Origin": "https://music.163.com",
        "Cookie": "os=pc"
    }
    data = {
        "id": playlist_id,
        "n": "1000"
    }

    try:
        response = requests.post(url, headers=headers, data=data, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"NetEase HTTP 请求失败: {e}")
        return None

    try:
        playlist_json = response.json()
    except json.JSONDecodeError as e:
        print(f"NetEase 解析 JSON 失败: {e}")
        return None

    if playlist_json.get("code") != 200:
        print(f"NetEase API 返回错误: {playlist_json.get('msg', '未知错误')}")
        return None

    return playlist_json

def extract_netease_songs(playlist_json):
    """
    从网易云音乐歌单详情 JSON 数据中提取歌曲名称和作者信息。
    """
    songs = []
    playlist = playlist_json.get("playlist", {})
    if not playlist:
        print("NetEase 无效的歌单数据。")
        return songs

    tracks = playlist.get("tracks", [])

    for track in tracks:
        song_name = track.get("name", "未知歌曲")
        artists = track.get("ar", [])
        artist_names = " / ".join([artist.get("name", "未知艺术家") for artist in artists])
        full_song_info = f"{song_name} - {artist_names}"
        songs.append(full_song_info)

    return songs

# --------------------- QQ Music Handling ---------------------

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

# --------------------- Synology AudioStation Import Handling ---------------------

class AudioStationClient:
    def __init__(self, host, username, password, device_name='PythonPlayer'):
        self.host = host.rstrip('/')
        self.username = username
        self.password = password
        self.device_name = device_name
        self.session = requests.Session()
        self.endpoints = {}
        self.sid = None
        self.did = None
        self.all_songs_cache = []

    def get_available_endpoints(self):
        url = f"{self.host}/webapi/query.cgi"
        params = {
            "version": 1,
            "api": "SYNO.API.Info",
            "method": "query",
            "query": "all"
        }
        try:
            response = self.session.get(url, params=params, verify=False, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            print(f"获取可用端点请求失败: {e}")
            return False
        except json.JSONDecodeError:
            print("无法解析 JSON 响应")
            return False
        if data.get('success'):
            self.endpoints = data['data']
            return True
        else:
            print("无法获取可用端点")
            return False

    def login(self):
        auth_info = self.endpoints.get("SYNO.API.Auth")
        if not auth_info:
            print("Auth 端点未找到")
            return False
        path = auth_info['path']
        url = f"{self.host}/webapi/{path}"
        payload = {
            "version": 6,
            "api": "SYNO.API.Auth",
            "method": "login",
            "session": "AudioStation",
            "device_name": self.device_name,
            "account": self.username,
            "passwd": self.password,
            "enable_device_token": "yes"
        }
        try:
            response = self.session.post(url, data=payload, verify=False, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            print(f"登录请求失败: {e}")
            return False
        except json.JSONDecodeError:
            print("无法解析 JSON 响应")
            return False
        if data.get('success'):
            self.sid = data['data']['sid']
            self.did = data['data'].get('did')
            print("登录成功")
            return True
        elif data.get('error', {}).get('code') == 403:
            print("需要 OTP 验证。")
            return False
        else:
            print("登录失败")
            return False

    def fetch_all_songs(self, log_func=None):
        """
        获取服务器上所有歌曲并缓存到 self.all_songs_cache
        """
        song_info = self.endpoints.get("SYNO.AudioStation.Song")
        if not song_info:
            print("Song 端点未找到")
            if log_func:
                log_func("Song 端点未找到")
            return False
        path = song_info['path']
        url = f"{self.host}/webapi/{path}"
        offset = 0
        limit = 500
        total = None
        if log_func:
            log_func("正在获取所有歌曲并缓存...")
        while True:
            params = {
                "version": 3,
                "api": "SYNO.AudioStation.Song",
                "method": "list",
                "library": "all",
                "offset": offset,
                "limit": limit,
                "additional": "song_tag,song_audio,song_rating",
                "_sid": self.sid
            }
            try:
                response = self.session.get(url, params=params, verify=False, timeout=10)
                response.raise_for_status()
                data = response.json()
            except requests.RequestException as e:
                print(f"获取歌曲列表请求失败: {e}")
                if log_func:
                    log_func(f"获取歌曲列表请求失败: {e}")
                return False
            except json.JSONDecodeError:
                print("无法解析 JSON 响应")
                if log_func:
                    log_func("无法解析 JSON 响应")
                return False
            if data.get('success'):
                songs = data['data'].get('songs', [])
                if total is None:
                    total = data['data'].get('total', 0)
                    if log_func:
                        log_func(f"总歌曲数: {total}")
                if not songs:
                    break
                self.all_songs_cache.extend(songs)
                offset += len(songs)
                if log_func:
                    log_func(f"已缓存 {len(self.all_songs_cache)}/{total} 首歌曲。")
                if offset >= total:
                    break
            else:
                print("获取歌曲列表失败")
                if log_func:
                    log_func("获取歌曲列表失败")
                return False
        print(f"成功缓存 {len(self.all_songs_cache)} 首歌曲。")
        if log_func:
            log_func(f"成功缓存 {len(self.all_songs_cache)} 首歌曲。")
        return True

    def match_song(self, title, artist, threshold=70, log_func=None):
        """
        使用模糊匹配在缓存中搜索歌曲，返回最佳匹配的歌曲 ID
        threshold: 匹配阈值，默认70分
        """
        if not self.all_songs_cache:
            print("歌曲缓存为空，无法进行匹配。")
            if log_func:
                log_func("歌曲缓存为空，无法进行匹配。")
            return None, 0

        candidates = [
            {
                "id": song['id'],
                "title": song.get('title', '').lower(),
                "artist": song.get('additional', {}).get('song_tag', {}).get('artist', '').lower()
            }
            for song in self.all_songs_cache
        ]

        input_title = title.strip().lower()
        input_artists = re.split(r'[、/，,]', artist.lower())

        best_match = None
        highest_score = 0

        for song in candidates:
            title_score = fuzz.token_set_ratio(input_title, song['title'])
            artist_score = max(fuzz.token_set_ratio(a.strip(), song['artist']) for a in input_artists)
            combined_score = (title_score * 0.7) + (artist_score * 0.3)

            if combined_score > highest_score:
                highest_score = combined_score
                best_match = song

        if best_match and highest_score >= threshold:
            if log_func:
                log_func(f"匹配成功: {title} - {artist} (得分: {highest_score:.2f})")
            return best_match['id'], highest_score
        else:
            if log_func:
                log_func(f"匹配失败: {title} - {artist} (最佳得分: {highest_score:.2f})")
            return None, highest_score

    def create_playlist(self, name, log_func=None):
        """
        创建一个新的播放列表，返回其 ID
        """
        playlist_info = self.endpoints.get("SYNO.AudioStation.Playlist")
        if not playlist_info:
            print("Playlist 端点未找到")
            if log_func:
                log_func("Playlist 端点未找到")
            return None
        path = playlist_info['path']
        url = f"{self.host}/webapi/{path}"
        payload = {
            "version": 2,
            "api": "SYNO.AudioStation.Playlist",
            "method": "create",
            "library": "personal",
            "name": name,
            "_sid": self.sid
        }
        try:
            response = self.session.post(url, data=payload, verify=False, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            print(f"创建歌单请求失败: {e}")
            if log_func:
                log_func(f"创建歌单请求失败: {e}")
            return None
        except json.JSONDecodeError:
            print("无法解析 JSON 响应")
            if log_func:
                log_func("无法解析 JSON 响应")
            return None
        if data.get('success'):
            playlist_id = data['data']['id']
            print(f"创建歌单成功: {name} (ID: {playlist_id})")
            if log_func:
                log_func(f"创建歌单成功: {name} (ID: {playlist_id})")
            return playlist_id
        else:
            print(f"创建歌单失败: {name}")
            if log_func:
                log_func(f"创建歌单失败: {name}")
            return None

    def add_songs_to_playlist(self, playlist_id, song_ids, log_func=None):
        """
        将歌曲添加到指定的播放列表
        """
        playlist_info = self.endpoints.get("SYNO.AudioStation.Playlist")
        if not playlist_info:
            print("Playlist 端点未找到")
            if log_func:
                log_func("Playlist 端点未找到")
            return False
        path = playlist_info['path']
        url = f"{self.host}/webapi/{path}"
        payload = {
            "version": 2,
            "api": "SYNO.AudioStation.Playlist",
            "method": "updatesongs",
            "id": playlist_id,
            "offset": -1,
            "limit": 0,
            "songs": ",".join(song_ids),
            "_sid": self.sid
        }
        try:
            response = self.session.post(url, data=payload, verify=False, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            print(f"添加歌曲到歌单请求失败: {e}")
            if log_func:
                log_func(f"添加歌曲到歌单请求失败: {e}")
            return False
        except json.JSONDecodeError:
            print("无法解析 JSON 响应")
            if log_func:
                log_func("无法解析 JSON 响应")
            return False
        if data.get('success'):
            print(f"成功添加 {len(song_ids)} 首歌曲到歌单 (ID: {playlist_id})")
            if log_func:
                log_func(f"成功添加 {len(song_ids)} 首歌曲到歌单 (ID: {playlist_id})")
            return True
        else:
            print(f"添加歌曲到歌单失败 (ID: {playlist_id})")
            if log_func:
                log_func(f"添加歌曲到歌单失败 (ID: {playlist_id})")
            return False

    def import_playlist_from_song_list(self, song_list, playlist_name, threshold=70, log_func=None):
        """
        从歌曲列表导入歌单并创建新的播放列表
        """
        song_ids = []
        if log_func:
            log_func("正在匹配歌曲...")
        for song in tqdm(song_list, desc="Matching songs", unit="song"):
            match = re.match(r'^(.*?)\s*-\s*(.*)$', song)
            if not match:
                if log_func:
                    log_func(f"无效的歌曲格式: {song}")
                continue
            title = match.group(1).strip()
            artist = match.group(2).strip()
            song_id, score = self.match_song(title, artist, threshold, log_func)
            if song_id:
                song_ids.append(song_id)
                continue
            song_id, score = self.match_song(artist, title, threshold, log_func)
            if song_id:
                song_ids.append(song_id)
                continue
            if log_func:
                log_func(f"未匹配到歌曲: {title} - {artist}")

        if not song_ids:
            if log_func:
                log_func("没有找到任何匹配的歌曲")
            return False

        new_playlist_id = self.create_playlist(playlist_name, log_func)
        if not new_playlist_id:
            if log_func:
                log_func("无法创建新的播放列表")
            return False

        if self.add_songs_to_playlist(new_playlist_id, song_ids, log_func):
            if log_func:
                log_func(f"歌单 '{playlist_name}' 导入完成，共添加 {len(song_ids)} 首歌曲。")
            return True
        else:
            if log_func:
                log_func("添加歌曲到歌单时发生错误")
            return False

    def import_playlist_from_file(self, file_path, playlist_name, threshold=70, log_func=None):
        """
        从指定的文本文件导入歌单并创建新的播放列表
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            print(f"无法读取文件: {e}")
            if log_func:
                log_func(f"无法读取文件: {e}")
            return False

        song_entries = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            match = re.match(r'^(.*?)\s*-\s*(.*)$', line)
            if match:
                title = match.group(1).strip()
                artist = match.group(2).strip()
                song_entries.append((title, artist))
            else:
                if log_func:
                    log_func(f"无效的格式: {line}")

        if not song_entries:
            if log_func:
                log_func("没有有效的歌曲条目")
            return False

        song_ids = []
        if log_func:
            log_func("正在匹配歌曲...")
        for title, artist in tqdm(song_entries, desc="Matching songs", unit="song"):
            song_id, score = self.match_song(title, artist, threshold, log_func)
            if song_id:
                song_ids.append(song_id)
                continue
            song_id, score = self.match_song(artist, title, threshold, log_func)
            if song_id:
                song_ids.append(song_id)
                continue
            if log_func:
                log_func(f"未匹配到歌曲: {title} - {artist}")

        if not song_ids:
            if log_func:
                log_func("没有找到任何匹配的歌曲")
            return False

        new_playlist_id = self.create_playlist(playlist_name, log_func)
        if not new_playlist_id:
            if log_func:
                log_func("无法创建新的播放列表")
            return False

        if self.add_songs_to_playlist(new_playlist_id, song_ids, log_func):
            if log_func:
                log_func(f"歌单 '{playlist_name}' 导入完成，共添加 {len(song_ids)} 首歌曲。")
            return True
        else:
            if log_func:
                log_func("添加歌曲到歌单时发生错误")
            return False

    def get_playlist_list(self):
        """
        获取当前所有播放列表。
        """
        playlist_info = self.endpoints.get("SYNO.AudioStation.Playlist")
        if not playlist_info:
            print("Playlist 端点未找到")
            return []
        path = playlist_info['path']
        url = f"{self.host}/webapi/{path}"
        payload = {
            "version": 2,
            "api": "SYNO.AudioStation.Playlist",
            "method": "list",
            "library": "personal",
            "_sid": self.sid
        }
        try:
            response = self.session.post(url, data=payload, verify=False, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            print(f"获取播放列表请求失败: {e}")
            return []
        except json.JSONDecodeError:
            print("无法解析 JSON 响应")
            return []
        if data.get('success'):
            playlists = data['data'].get('playlists', [])
            return playlists
        else:
            print("获取播放列表失败")
            return []

    def delete_playlist(self, playlist_id, log_func=None):
        """
        删除指定的播放列表。
        """
        playlist_info = self.endpoints.get("SYNO.AudioStation.Playlist")
        if not playlist_info:
            print("Playlist 端点未找到")
            if log_func:
                log_func("Playlist 端点未找到")
            return False
        path = playlist_info['path']
        url = f"{self.host}/webapi/{path}"
        payload = {
            "version": 2,
            "api": "SYNO.AudioStation.Playlist",
            "method": "delete",
            "id": playlist_id,
            "_sid": self.sid
        }
        try:
            response = self.session.post(url, data=payload, verify=False, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            print(f"删除播放列表请求失败: {e}")
            if log_func:
                log_func(f"删除播放列表请求失败: {e}")
            return False
        except json.JSONDecodeError:
            print("无法解析 JSON 响应")
            if log_func:
                log_func("无法解析 JSON 响应")
            return False
        if data.get('success'):
            print(f"成功删除歌单 ID: {playlist_id}")
            if log_func:
                log_func(f"成功删除歌单 ID: {playlist_id}")
            return True
        else:
            print(f"删除歌单失败 (ID: {playlist_id})")
            if log_func:
                log_func(f"删除歌单失败 (ID: {playlist_id})")
            return False

# --------------------- GUI Implementation ---------------------

class LoginWindow(ttk.Toplevel):
    def __init__(self, app, parent):
        super().__init__(parent)
        self.title("登录群晖AudioStation-艾拉与方块")
        self.geometry("500x450")  # 调整窗口尺寸
        self.resizable(False, False)
        self.app = app
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # 设置窗口图标
        self.set_icon()

        self.host_var = ttk.StringVar()
        self.username_var = ttk.StringVar()
        self.password_var = ttk.StringVar()

        self.create_widgets()

    def set_icon(self):
        try:
            self.iconbitmap("1.ico")
        except Exception as e:
            print(f"无法设置图标: {e}")


    def create_widgets(self):
        padding = {'padx': 10, 'pady': 10}

        # 使用 grid 布局管理器
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)

        # Host
        ttk.Label(self, text="群晖主机地址:\n(管理界面地址)").grid(column=0, row=0, sticky='W', **padding)
        ttk.Entry(self, textvariable=self.host_var, width=30).grid(column=1, row=0, sticky='EW', **padding)

        # Username
        ttk.Label(self, text="用户名:").grid(column=0, row=1, sticky='W', **padding)
        ttk.Entry(self, textvariable=self.username_var, width=30).grid(column=1, row=1, sticky='EW', **padding)

        # Password
        ttk.Label(self, text="密码:").grid(column=0, row=2, sticky='W', **padding)
        ttk.Entry(self, textvariable=self.password_var, show="*", width=30).grid(column=1, row=2, sticky='EW', **padding)

        # Login Button
        self.login_button = ttk.Button(self, text="登录", bootstyle=SUCCESS, command=self.login)
        self.login_button.grid(column=0, row=3, columnspan=2, sticky='EW', pady=20, padx=50)

        # Log Status
        ttk.Label(self, text="状态:").grid(column=0, row=4, sticky='NW', **padding)
        self.status_text = ScrolledText(self, height=5, width=35, state='disabled')
        self.status_text.grid(column=0, row=5, columnspan=2, sticky='EW', **padding)

    def login(self):
        host = self.host_var.get().strip()
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()

        if not host or not username or not password:
            messagebox.showwarning("错误", "你输入完了吗你！")
            return

        self.login_button.configure(state='disabled')
        self.log_status("开始登录群晖AudioStation...")

        def perform_login():
            self.app.audio_client = AudioStationClient(host, username, password)
            if not self.app.audio_client.get_available_endpoints():
                self.show_login_failure("乐，链接失败检查主机地址！\n要不就是你群晖有点毛病！")
                return
            if not self.app.audio_client.login():
                self.show_login_failure("乐，登录失败。")
                return
            if not self.app.audio_client.fetch_all_songs(log_func=self.log_status):
                self.show_login_failure("乐，获取歌曲缓存失败。")
                return
            self.log_status("登录并缓存歌曲成功。")
            self.show_login_success()

        threading.Thread(target=perform_login, daemon=True).start()

    def show_login_failure(self, message):
        self.log_status(message)
        self.login_button.configure(state='normal')
        messagebox.showerror("登录失败", message)

    def show_login_success(self):
        self.login_button.configure(state='normal')
        messagebox.showinfo("登录成功", "成功登录进去了")
        self.destroy()
        self.app.create_main_window()

    def log_status(self, message):
        def append_message():
            self.status_text.configure(state='normal')
            self.status_text.insert('end', f"{message}\n")
            self.status_text.see('end')
            self.status_text.configure(state='disabled')
        self.after(0, append_message)

    def on_close(self):
        if messagebox.askokcancel("离开", "真的要退出程序吗？QWQ"):
            self.app.root.destroy()


class Application:
    def __init__(self):
        self.audio_client = None
        self.root = ttk.Window(themename="cosmo")
        self.root.title("群晖AudioStation歌单导入工具-艾拉与方块")
        self.root.geometry("900x700")
        self.root.resizable(False, False)
        self.root.withdraw()  # 隐藏主窗口，直到登录成功

        # 设置图标
        self.set_icon(self.root)

        self.login_window = LoginWindow(self, self.root)

        # 创建主窗口的控件
        self.playlist_link_var = ttk.StringVar()
        self.new_playlist_name_var = ttk.StringVar()
        self.threshold_var = ttk.StringVar(value="70")
        self.import_mode = ttk.StringVar(value='link')
        self.selected_file_path = ''

        self.create_main_widgets()

        self.root.mainloop()

    def set_icon(self, window):
        # 设置 .ico 图标文件
        try:
            window.iconbitmap("1.ico")
        except Exception as e:
            print(f"无法设置图标: {e}")

    def create_main_window(self):
        self.root.deiconify()  # 显示主窗口
        # 更新主窗口的内容
        self.notebook.pack(expand=True, fill='both')
        self.load_playlists()

    def create_main_widgets(self):
        self.notebook = ttk.Notebook(self.root, bootstyle=PRIMARY)
        self.notebook.pack(expand=True, fill='both')

        self.manage_frame = ttk.Frame(self.notebook)
        self.import_frame = ttk.Frame(self.notebook)

        self.notebook.add(self.manage_frame, text='管理歌单')
        self.notebook.add(self.import_frame, text='导入歌单')

        self.create_manage_tab()
        self.create_import_tab()

    def create_manage_tab(self):
        padding = {'padx': 10, 'pady': 10}

        # 仅显示"名称"列，去掉"ID"列
        ttk.Label(self.manage_frame, text="现有歌单:").pack(anchor='w', **padding)

        # 修改Treeview，移除ID列
        self.playlist_tree = ttk.Treeview(self.manage_frame, columns=("Name",), show='headings', selectmode='browse')

        # 仅显示名称列
        self.playlist_tree.heading("Name", text="名称")
        self.playlist_tree.column("Name", width=700, anchor='w')
        self.playlist_tree.pack(fill='both', expand=True, **padding)

        # 删除按钮
        self.delete_button = ttk.Button(self.manage_frame, text="删除选中的歌单", bootstyle=DANGER,
                                        command=self.delete_selected_playlist)
        self.delete_button.pack(anchor='e', **padding)

    def create_import_tab(self):
        padding = {'padx': 10, 'pady': 10}

        # Import mode selection
        ttk.Label(self.import_frame, text="导入方式:").grid(column=0, row=0, sticky='W', **padding)
        self.link_radio = ttk.Radiobutton(self.import_frame, text='从链接导入', variable=self.import_mode, value='link', command=self.update_import_mode)
        self.link_radio.grid(column=1, row=0, sticky='W', **padding)
        self.file_radio = ttk.Radiobutton(self.import_frame, text='从文件导入', variable=self.import_mode, value='file', command=self.update_import_mode)
        self.file_radio.grid(column=2, row=0, sticky='W', **padding)

        # Playlist Link
        self.playlist_link_label = ttk.Label(self.import_frame, text="歌单链接 (网易云音乐或 QQ 音乐):")
        self.playlist_link_entry = ttk.Entry(self.import_frame, textvariable=self.playlist_link_var, width=80)
        self.playlist_link_label.grid(column=0, row=1, sticky='W', **padding)
        self.playlist_link_entry.grid(column=1, row=1, columnspan=2, sticky='EW', **padding)

        # File selection
        self.file_select_button = ttk.Button(self.import_frame, text="选择歌单文件 (txt)", command=self.select_file)
        self.selected_file_label = ttk.Label(self.import_frame, text="未选择文件")
        self.file_select_button.grid(column=0, row=2, sticky='W', **padding)
        self.selected_file_label.grid(column=1, row=2, columnspan=2, sticky='W', **padding)
        self.file_select_button.grid_remove()
        self.selected_file_label.grid_remove()

        # New Playlist Name
        ttk.Label(self.import_frame, text="新歌单名称:").grid(column=0, row=3, sticky='W', **padding)
        ttk.Entry(self.import_frame, textvariable=self.new_playlist_name_var, width=50).grid(column=1, row=3, columnspan=2, sticky='EW', **padding)

        # Matching Threshold
        ttk.Label(self.import_frame, text="匹配阈值 (默认70，范围0-100)\n匹配不好就低一点:").grid(column=0, row=4, sticky='W', **padding)
        ttk.Entry(self.import_frame, textvariable=self.threshold_var, width=10).grid(column=1, row=4, sticky='W', **padding)

        # Import Button
        self.import_button = ttk.Button(self.import_frame, text="导入歌单", bootstyle=SUCCESS, command=self.import_playlist)
        self.import_button.grid(column=1, row=5, sticky='E', **padding)

        # Status Text
        ttk.Label(self.import_frame, text="导入状态:").grid(column=0, row=6, sticky='NW', **padding)
        self.status_text = ScrolledText(self.import_frame, height=20, width=100, state='disabled')
        self.status_text.grid(column=0, row=7, columnspan=3, sticky='EW', **padding)

    def update_import_mode(self):
        mode = self.import_mode.get()
        if mode == 'link':
            self.playlist_link_label.grid()
            self.playlist_link_entry.grid()
            self.file_select_button.grid_remove()
            self.selected_file_label.grid_remove()
        elif mode == 'file':
            self.playlist_link_label.grid_remove()
            self.playlist_link_entry.grid_remove()
            self.file_select_button.grid()
            self.selected_file_label.grid()
        else:
            self.playlist_link_label.grid_remove()
            self.playlist_link_entry.grid_remove()
            self.file_select_button.grid_remove()
            self.selected_file_label.grid_remove()

    def select_file(self):
        file_path = filedialog.askopenfilename(title="选择歌单文件", filetypes=[("Text Files", "*.txt")])
        if file_path:
            self.selected_file_path = file_path
            self.selected_file_label.config(text=file_path)
        else:
            self.selected_file_path = ''
            self.selected_file_label.config(text="未选择文件")

    def load_playlists(self):
        playlists = self.audio_client.get_playlist_list()
        for item in self.playlist_tree.get_children():
            self.playlist_tree.delete(item)
        for pl in playlists:
            self.playlist_tree.insert('', 'end', values=(pl['id'], pl['name']))

    def delete_selected_playlist(self):
        selected = self.playlist_tree.selection()
        if not selected:
            messagebox.showwarning("选择错误", "请先选择一个歌单。")
            return
        playlist_id, playlist_name = self.playlist_tree.item(selected[0], 'values')
        confirm = messagebox.askyesno("确认删除", f"确定要删除歌单 '{playlist_name}' 吗？")
        if not confirm:
            return

        self.delete_button.configure(state='disabled')

        def perform_delete():
            self.log_status(f"正在删除歌单: {playlist_name} (ID: {playlist_id})...")
            success = self.audio_client.delete_playlist(playlist_id, log_func=self.log_status)
            if success:
                self.log_status(f"成功删除歌单: {playlist_name} (ID: {playlist_id})")
                self.playlist_tree.delete(selected[0])
                messagebox.showinfo("删除成功", f"成功删除歌单 '{playlist_name}'。")
            else:
                self.log_status(f"删除歌单失败: {playlist_name} (ID: {playlist_id})")
                messagebox.showerror("删除失败", f"无法删除歌单 '{playlist_name}'。")
            self.delete_button.configure(state='normal')

        threading.Thread(target=perform_delete, daemon=True).start()

    def import_playlist(self):
        new_playlist_name = self.new_playlist_name_var.get().strip()
        threshold_input = self.threshold_var.get().strip()

        if not new_playlist_name:
            messagebox.showwarning("输入错误", "请填写歌单名称。")
            return

        try:
            threshold = int(threshold_input) if threshold_input else 70
            if threshold < 0 or threshold > 100:
                messagebox.showwarning("输入错误", "匹配阈值必须在0到100之间，使用默认值70分。")
                threshold = 70
        except ValueError:
            messagebox.showwarning("输入错误", "匹配阈值必须是一个整数，使用默认值70分。")
            threshold = 70

        import_mode = self.import_mode.get()

        if import_mode == 'link':
            link = self.playlist_link_var.get().strip()
            if not link:
                messagebox.showwarning("输入错误", "请填写歌单链接。")
                return
        elif import_mode == 'file':
            if not self.selected_file_path:
                messagebox.showwarning("输入错误", "请先选择歌单文件。")
                return
        else:
            messagebox.showwarning("输入错误", "请选择导入方式。")
            return

        self.import_button.configure(state='disabled')

        def perform_import():
            if import_mode == 'link':
                self.log_status(f"开始从链接导入歌单: {new_playlist_name}")
                playlist_name, songs = fetch_song_list_from_link(link)
                if not songs:
                    self.log_status("未能获取到有效的歌曲列表，导入终止。")
                    messagebox.showerror("导入失败", "未能获取到有效的歌曲列表。")
                    self.enable_import_widgets()
                    return
                self.log_status(f"歌单名称: {playlist_name}")
                self.log_status(f"歌曲总数: {len(songs)}")
                if new_playlist_name != playlist_name:
                    self.log_status(f"自定义歌单名称: {new_playlist_name}")
                success = self.audio_client.import_playlist_from_song_list(songs, new_playlist_name, threshold, log_func=self.log_status)
            elif import_mode == 'file':
                self.log_status(f"开始从文件导入歌单: {new_playlist_name}")
                file_path = self.selected_file_path
                success = self.audio_client.import_playlist_from_file(file_path, new_playlist_name, threshold, log_func=self.log_status)
            else:
                self.log_status("未知的导入方式，导入终止。")
                success = False

            if success:
                self.log_status("歌单导入成功！")
                messagebox.showinfo("导入成功", f"歌单 '{new_playlist_name}' 导入成功。")
                self.load_playlists()
            else:
                self.log_status("歌单导入失败。")
                messagebox.showerror("导入失败", "歌单导入失败。")
            self.enable_import_widgets()

        threading.Thread(target=perform_import, daemon=True).start()

    def enable_import_widgets(self):
        self.import_button.configure(state='normal')

    def log_status(self, message):
        def append_message():
            self.status_text.configure(state='normal')
            self.status_text.insert('end', f"{message}\n")
            self.status_text.see('end')
            self.status_text.configure(state='disabled')
        self.root.after(0, append_message)

# --------------------- Helper Functions ---------------------

def detect_platform(link):
    """
    根据链接的域名判断平台是网易云音乐还是 QQ 音乐。
    返回 'netease', 'qqmusic', 或 None。
    """
    parsed_url = urlparse(link)
    netloc = parsed_url.netloc.lower()
    if 'music.163.com' in netloc:
        return 'netease'
    elif 'y.qq.com' in netloc or 'c.y.qq.com' in netloc or 't.qq.com' in netloc:
        return 'qqmusic'
    else:
        return None

def fetch_song_list_from_link(link):
    """
    根据链接自动提取歌曲列表。
    支持网易云音乐和 QQ 音乐。
    返回歌单名称和歌曲列表。
    """
    platform = detect_platform(link)
    if not platform:
        print("无法识别链接所属平台。请确保链接来自网易云音乐或 QQ 音乐。")
        return None, []

    if platform == 'netease':
        playlist_id = extract_netease_playlist_id(link)
        if not playlist_id:
            print("未能提取到网易云音乐歌单 ID。")
            return None, []
        print(f"提取到网易云音乐歌单 ID: {playlist_id}")

        playlist_json = get_netease_playlist_details(playlist_id)
        if not playlist_json:
            print("未能获取网易云音乐歌单详情。")
            return None, []

        songs = extract_netease_songs(playlist_json)
        if not songs:
            print("网易云音乐歌单中没有歌曲。")
            return None, []

        playlist_name = playlist_json['playlist'].get('name', '未知歌单')

    elif platform == 'qqmusic':
        playlist_id = extract_qqmusic_playlist_id(link)
        if not playlist_id:
            print("未能提取到 QQ 音乐歌单 ID。")
            return None, []
        print(f"提取到 QQ 音乐歌单 ID: {playlist_id}")

        qqmusic = QQMusicList(playlist_id)
        songs = qqmusic.get_list()
        if not songs:
            print("QQ 音乐歌单中没有歌曲。")
            return None, []

        playlist_name = "QQMusic 导入歌单"

    return playlist_name, songs

# --------------------- Main Function ---------------------

def main():
    app = Application()

if __name__ == "__main__":
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
    main()
