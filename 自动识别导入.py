import re
import time
import requests
import json
from urllib.parse import urlparse, parse_qs
from fuzzywuzzy import fuzz
from tqdm import tqdm
import sys

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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://music.163.com/",
        "Origin": "https://music.163.com",
        "Cookie": "os=pc"  # 添加 Cookie 来模拟 PC 客户端
    }
    data = {
        "id": playlist_id,
        "n": "1000"  # 假设最大获取1000首歌曲
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

    # 检查 API 返回的状态码
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
            "User-Agent": "Mozilla/5.0 (Linux; Android 8.0.0; Pixel 2 XL Build/OPD1.170816.004) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Mobile Safari/537.36",
            "Referer": f"https://y.qq.com/w/taoge.html?ADTAG=profile_h5&id={self.id}",
            "Origin": "https://y.qq.com",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
        }
        self.session = requests.Session()
        # 设置重试机制
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
        # 使用正则表达式提取总歌曲数
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
                # Debug: Uncomment to see the response JSON
                # print(f"QQMusic 响应 JSON: {json.dumps(data, ensure_ascii=False, indent=2)}")
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

    # 尝试从查询参数中获取 disstid
    if 'disstid' in query:
        print("从查询参数中提取 QQMusic 歌单 ID")
        return query['disstid'][0]

    # 尝试从路径中提取 ID
    path_match = re.search(r'/playlist/(\d+)', parsed_url.path)
    if path_match:
        print("从路径中提取 QQMusic 歌单 ID")
        return path_match.group(1)

    # 如果是短链接，尝试获取重定向后的实际链接
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
        self.all_songs_cache = []  # 用于缓存所有歌曲信息

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
            print("需要 OTP 验证。请输入 OTP 码：")
            otp_code = input("OTP Code: ")
            payload['otp_code'] = otp_code
            try:
                response = self.session.post(url, data=payload, verify=False, timeout=10)
                response.raise_for_status()
                data = response.json()
            except requests.RequestException as e:
                print(f"OTP 登录请求失败: {e}")
                return False
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
                try:
                    response = self.session.get(url, params=params, verify=False, timeout=10)
                    response.raise_for_status()
                    data = response.json()
                except requests.RequestException as e:
                    print(f"获取歌曲列表请求失败: {e}")
                    return False
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
        try:
            response = self.session.post(url, data=payload, verify=False, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            print(f"创建歌单请求失败: {e}")
            return None
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
        try:
            response = self.session.post(url, data=payload, verify=False, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            print(f"添加歌曲到歌单请求失败: {e}")
            return False
        except json.JSONDecodeError:
            print("无法解析 JSON 响应")
            return False
        if data.get('success'):
            print(f"成功添加 {len(song_ids)} 首歌曲到歌单 (ID: {playlist_id})")
            return True
        else:
            print(f"添加歌曲到歌单失败 (ID: {playlist_id})")
            return False

    def import_playlist_from_song_list(self, song_list, playlist_name, threshold=70):
        """
        从歌曲列表导入歌单并创建新的播放列表
        song_list: list of "歌曲名 - 艺术家名" 格式的字符串
        threshold: 匹配阈值，默认70分
        """
        # 搜索并收集歌曲 ID
        song_ids = []
        print("正在匹配歌曲...")
        for song in tqdm(song_list, desc="Matching songs", unit="song"):
            match = re.match(r'^(.*?)\s*-\s*(.*)$', song)
            if not match:
                print(f"无效的歌曲格式: {song}")
                continue
            title = match.group(1).strip()
            artist = match.group(2).strip()
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

# --------------------- Main Function ---------------------

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

        # 获取歌单详情
        playlist_json = get_netease_playlist_details(playlist_id)
        if not playlist_json:
            print("未能获取网易云音乐歌单详情。")
            return None, []

        # 提取歌曲列表
        songs = extract_netease_songs(playlist_json)
        if not songs:
            print("网易云音乐歌单中没有歌曲。")
            return None, []

        # 获取歌单名称
        playlist_name = playlist_json['playlist'].get('name', '未知歌单')

    elif platform == 'qqmusic':
        # 提取 QQ 音乐歌单 ID
        playlist_id = extract_qqmusic_playlist_id(link)
        if not playlist_id:
            print("未能提取到 QQ 音乐歌单 ID。")
            return None, []
        print(f"提取到 QQ 音乐歌单 ID: {playlist_id}")

        # 使用 QQMusicList 类获取歌曲列表
        qqmusic = QQMusicList(playlist_id)
        songs = qqmusic.get_list()
        if not songs:
            print("QQ 音乐歌单中没有歌曲。")
            return None, []

        # 获取歌单名称（QQMusicList 类中未实现获取歌单名称，这里使用默认名称）
        playlist_name = "QQMusic 导入歌单"

    return playlist_name, songs

def main():
    """
    主函数：接收用户输入的歌单链接，自动识别平台，获取歌单歌曲列表，并导入到 Synology AudioStation。
    """
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

    # 用户输入歌单链接
    print("\n=== 歌单导入功能 ===")
    playlist_link = input("请输入网易云音乐或 QQ 音乐歌单链接: ").strip()

    # 获取歌单名称和歌曲列表
    playlist_name, songs = fetch_song_list_from_link(playlist_link)
    if not songs:
        print("未能获取到有效的歌曲列表，导入终止。")
        sys.exit(1)

    print(f"\n歌单名称: {playlist_name}")
    print(f"歌曲总数: {len(songs)}")

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

    # 导入歌单
    if client.import_playlist_from_song_list(songs, playlist_name, threshold):
        print("歌单导入成功！")
    else:
        print("歌单导入失败。")

if __name__ == "__main__":
    # 禁用 InsecureRequestWarning
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
    main()
