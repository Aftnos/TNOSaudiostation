import re
import requests
import json
from fuzzywuzzy import fuzz
from tqdm import tqdm

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