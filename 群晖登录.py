import requests
import sys
import json
import re
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
        self.all_songs_cache = []  # 用于缓存所有歌曲信息

    def get_available_endpoints(self):
        url = f"{self.host}/webapi/query.cgi"
        params = {
            "version": 1,
            "api": "SYNO.API.Info",
            "method": "query",
            "query": "all"
        }
        response = self.session.get(url, params=params, verify=False)
        try:
            data = response.json()
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
        response = self.session.post(url, data=payload, verify=False)
        try:
            data = response.json()
        except json.JSONDecodeError:
            print("无法解析 JSON 响应")
            return False
        if data.get('success'):
            self.sid = data['data']['sid']
            self.did = data['data'].get('did')
            print("登录成功")
            return True
        elif data.get('error', {}).get('code') == 403:
            print("需要 OTP 验证。请输入 OTP 码：")
            otp_code = input("OTP Code: ")
            payload['otp_code'] = otp_code
            response = self.session.post(url, data=payload, verify=False)
            try:
                data = response.json()
            except json.JSONDecodeError:
                print("无法解析 JSON 响应")
                return False
            if data.get('success'):
                self.sid = data['data']['sid']
                self.did = data['data'].get('did')
                print("使用 OTP 登录成功")
                return True
            else:
                print("使用 OTP 登录失败")
                return False
        else:
            print("登录失败")
            return False

    def fetch_all_songs(self):
        """
        获取服务器上所有歌曲并缓存到 self.all_songs_cache
        """
        song_info = self.endpoints.get("SYNO.AudioStation.Song")
        if not song_info:
            print("Song 端点未找到")
            return False
        path = song_info['path']
        url = f"{self.host}/webapi/{path}"
        offset = 0
        limit = 500  # 每次请求获取500首歌曲，根据服务器支持调整
        total = None
        print("正在获取所有歌曲并缓存...")
        with tqdm(total=total, desc="Fetching songs", unit="song") as pbar:
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
                response = self.session.get(url, params=params, verify=False)
                try:
                    data = response.json()
                except json.JSONDecodeError:
                    print("无法解析 JSON 响应")
                    return False
                if data.get('success'):
                    songs = data['data'].get('songs', [])
                    if total is None:
                        total = data['data'].get('total', 0)
                        pbar.total = total
                    if not songs:
                        break
                    self.all_songs_cache.extend(songs)
                    offset += len(songs)
                    pbar.update(len(songs))
                    if offset >= total:
                        break
                else:
                    print("获取歌曲列表失败")
                    return False
        print(f"成功缓存 {len(self.all_songs_cache)} 首歌曲。")
        return True

    def match_song(self, title, artist, threshold=70):
        """
        使用模糊匹配在缓存中搜索歌曲，返回最佳匹配的歌曲 ID
        threshold: 匹配阈值，默认70分
        """
        if not self.all_songs_cache:
            print("歌曲缓存为空，无法进行匹配。")
            return None

        # 创建一个候选列表，包含所有歌曲的标题和艺术家
        candidates = [
            {
                "id": song['id'],
                "title": song.get('title', '').lower(),
                "artist": song.get('additional', {}).get('song_tag', {}).get('artist', '').lower()
            }
            for song in self.all_songs_cache
        ]

        # 预处理输入
        input_title = title.strip().lower()
        input_artists = re.split(r'[、/，,]', artist.lower())

        best_match = None
        highest_score = 0

        for song in candidates:
            # 计算标题匹配得分
            title_score = fuzz.token_set_ratio(input_title, song['title'])
            # 计算艺术家匹配得分
            artist_score = max(fuzz.token_set_ratio(a.strip(), song['artist']) for a in input_artists)

            # 综合得分
            combined_score = (title_score * 0.7) + (artist_score * 0.3)

            if combined_score > highest_score:
                highest_score = combined_score
                best_match = song

        # 设置一个阈值，只有当得分超过阈值时认为匹配成功
        if best_match and highest_score >= threshold:
            return best_match['id']
        else:
            print(f"未找到匹配的歌曲: {title} - {artist} (最佳得分: {highest_score:.2f})")
            return None

    def create_playlist(self, name):
        """
        创建一个新的播放列表，返回其 ID
        """
        playlist_info = self.endpoints.get("SYNO.AudioStation.Playlist")
        if not playlist_info:
            print("Playlist 端点未找到")
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
        response = self.session.post(url, data=payload, verify=False)
        try:
            data = response.json()
        except json.JSONDecodeError:
            print("无法解析 JSON 响应")
            return None
        if data.get('success'):
            playlist_id = data['data']['id']
            print(f"创建歌单成功: {name} (ID: {playlist_id})")
            return playlist_id
        else:
            print(f"创建歌单失败: {name}")
            return None

    def add_songs_to_playlist(self, playlist_id, song_ids):
        """
        将歌曲添加到指定的播放列表
        """
        playlist_info = self.endpoints.get("SYNO.AudioStation.Playlist")
        if not playlist_info:
            print("Playlist 端点未找到")
            return False
        path = playlist_info['path']
        url = f"{self.host}/webapi/{path}"
        payload = {
            "version": 2,
            "api": "SYNO.AudioStation.Playlist",
            "method": "updatesongs",
            "id": playlist_id,
            "offset": -1,  # -1 表示添加到末尾
            "limit": 0,     # 0 表示不移除任何歌曲
            "songs": ",".join(song_ids),
            "_sid": self.sid
        }
        response = self.session.post(url, data=payload, verify=False)
        try:
            data = response.json()
        except json.JSONDecodeError:
            print("无法解析 JSON 响应")
            return False
        if data.get('success'):
            print(f"成功添加 {len(song_ids)} 首歌曲到歌单 (ID: {playlist_id})")
            return True
        else:
            print(f"添加歌曲到歌单失败 (ID: {playlist_id})")
            return False

    def import_playlist_from_file(self, file_path, playlist_name, threshold=70):
        """
        从指定的文本文件导入歌单并创建新的播放列表
        threshold: 匹配阈值，默认70分
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            print(f"无法读取文件: {e}")
            return False

        song_entries = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 使用正则表达式分割歌曲名和艺术家名
            match = re.match(r'^(.*?)\s*-\s*(.*)$', line)
            if match:
                title = match.group(1).strip()
                artist = match.group(2).strip()
                song_entries.append((title, artist))
            else:
                print(f"无效的格式: {line}")

        if not song_entries:
            print("没有有效的歌曲条目")
            return False

        # 搜索并收集歌曲 ID
        song_ids = []
        print("正在匹配歌曲...")
        for title, artist in tqdm(song_entries, desc="Matching songs", unit="song"):
            # 尝试按 (title, artist) 顺序匹配
            song_id = self.match_song(title, artist, threshold)
            if song_id:
                song_ids.append(song_id)
                continue
            # 如果未匹配成功，尝试按 (artist, title) 顺序匹配
            song_id = self.match_song(artist, title, threshold)
            if song_id:
                song_ids.append(song_id)
                continue
            # 如果两种顺序都未匹配成功，报告未找到
            print(f"未匹配到歌曲: {title} - {artist}")

        if not song_ids:
            print("没有找到任何匹配的歌曲")
            return False

        # 创建新的播放列表
        new_playlist_id = self.create_playlist(playlist_name)
        if not new_playlist_id:
            print("无法创建新的播放列表")
            return False

        # 添加歌曲到新的播放列表
        if self.add_songs_to_playlist(new_playlist_id, song_ids):
            print(f"歌单 '{playlist_name}' 导入完成，共添加 {len(song_ids)} 首歌曲。")
            return True
        else:
            print("添加歌曲到歌单时发生错误")
            return False

def main():
    # 用户配置
    host = "https://192.168.2.2:5001/"  # 替换为您的 DSM 主机地址
    username = "tnos"  # 替换为您的用户名
    password = "Sph040627@"  # 替换为您的密码

    client = AudioStationClient(host, username, password)

    # 获取可用端点
    if not client.get_available_endpoints():
        print("无法获取可用端点")
        sys.exit(1)

    # 登录
    if not client.login():
        print("登录失败")
        sys.exit(1)

    # 获取并缓存所有歌曲
    if not client.fetch_all_songs():
        print("无法缓存所有歌曲")
        sys.exit(1)

    # 导入歌单功能
    print("\n=== 歌单导入功能 ===")
    file_path = input("请输入歌单文件的路径 (txt 文件): ").strip()
    playlist_name = input("请输入新歌单的名称: ").strip()

    # 询问用户是否要设置自定义匹配阈值
    try:
        threshold_input = input("请输入匹配阈值（默认70分，范围0-100）: ").strip()
        if threshold_input:
            threshold = int(threshold_input)
            if threshold < 0 or threshold > 100:
                print("匹配阈值必须在0到100之间，使用默认值70分。")
                threshold = 70
        else:
            threshold = 70
    except ValueError:
        print("无效的输入，使用默认匹配阈值70分。")
        threshold = 70

    if client.import_playlist_from_file(file_path, playlist_name, threshold):
        print("歌单导入成功！")
    else:
        print("歌单导入失败。")

if __name__ == "__main__":
    # 禁用 InsecureRequestWarning
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
    main()
