import re
import time
import requests
import json
from urllib.parse import urlparse, parse_qs

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

def main():
    """
    主函数：接收用户输入的歌单链接，自动识别平台，获取歌单歌曲列表，并输出到控制台。
    """
    # 用户输入歌单链接
    playlist_link = input("请输入网易云音乐或 QQ 音乐歌单链接: ").strip()

    # 判断平台
    platform = detect_platform(playlist_link)
    if not platform:
        print("无法识别链接所属平台。请确保链接来自网易云音乐或 QQ 音乐。")
        return

    # 根据平台提取歌单 ID
    if platform == 'netease':
        playlist_id = extract_netease_playlist_id(playlist_link)
        if not playlist_id:
            print("未能提取到网易云音乐歌单 ID。")
            return
        print(f"提取到网易云音乐歌单 ID: {playlist_id}")

        # 获取歌单详情
        playlist_json = get_netease_playlist_details(playlist_id)
        if not playlist_json:
            print("未能获取网易云音乐歌单详情。")
            return

        # 提取歌曲列表
        songs = extract_netease_songs(playlist_json)
        if not songs:
            print("网易云音乐歌单中没有歌曲。")
            return

    elif platform == 'qqmusic':
        # 提取 QQ 音乐歌单 ID
        playlist_id = extract_qqmusic_playlist_id(playlist_link)
        if not playlist_id:
            print("未能提取到 QQ 音乐歌单 ID。")
            return
        print(f"提取到 QQ 音乐歌单 ID: {playlist_id}")

        # 使用 QQMusicList 类获取歌曲列表
        qqmusic = QQMusicList(playlist_id)
        songs = qqmusic.get_list()
        if not songs:
            print("QQ 音乐歌单中没有歌曲。")
            return

    # 输出歌曲列表
    if platform == 'netease':
        print(f"\n歌单名称: {playlist_json['playlist'].get('name', '未知歌单')}")
        print(f"歌曲总数: {len(songs)}")
    elif platform == 'qqmusic':
        # 假设 QQMusicList 类已经打印了歌曲名称
        print(f"\n歌曲总数: {len(songs)}")

    print("\n歌曲列表:")
    for idx, song in enumerate(songs, 1):
        print(f"{idx}. {song}")

if __name__ == "__main__":
    main()
