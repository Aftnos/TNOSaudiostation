import re
import requests
import json
from urllib.parse import urlparse, parse_qs


def extract_playlist_id(link):
    """
    从网易云音乐歌单链接中提取歌单 ID。
    支持多种链接格式，如：
    - https://music.163.com/#/playlist?id=2657399934&creatorId=1756433368
    - https://music.163.com/playlist/2657399934
    - 短链接形式（假设为 https://t.cn/xxxxxx 转换为实际链接）
    """
    # 解析 URL
    parsed_url = urlparse(link)
    query = parse_qs(parsed_url.query)

    # 尝试从查询参数中获取 ID
    if 'id' in query:
        print("从查询参数中提取 ID")
        return query['id'][0]

    # 尝试从片段中提取 ID
    fragment = parsed_url.fragment
    fragment_query = parse_qs(urlparse(fragment).query)
    if 'id' in fragment_query:
        print("从片段查询参数中提取 ID")
        return fragment_query['id'][0]

    # 尝试从片段的路径中提取 ID
    path_match = re.search(r'/playlist/(\d+)', fragment)
    if path_match:
        print("从片段路径中提取 ID")
        return path_match.group(1)

    # 如果是短链接，尝试获取重定向后的实际链接
    if 't.cn' in parsed_url.netloc:
        print("处理短链接，尝试重定向解析")
        try:
            response = requests.head(link, allow_redirects=True, timeout=5)
            print(f"重定向到: {response.url}")
            return extract_playlist_id(response.url)
        except requests.RequestException as e:
            print(f"无法解析短链接: {e}")
            return None

    print("无法提取歌单 ID。")
    return None


def get_playlist_details(playlist_id):
    """
    通过歌单 ID 获取歌单详情，包括歌曲名称和作者。
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
        print(f"HTTP 请求失败: {e}")
        return None

    try:
        playlist_json = response.json()
    except json.JSONDecodeError as e:
        print(f"解析 JSON 失败: {e}")
        return None

    # 检查 API 返回的状态码
    if playlist_json.get("code") != 200:
        print(f"API 返回错误: {playlist_json.get('msg', '未知错误')}")
        return None

    return playlist_json


def extract_songs(playlist_json):
    """
    从歌单详情 JSON 数据中提取歌曲名称和作者信息。
    """
    songs = []
    playlist = playlist_json.get("playlist", {})
    if not playlist:
        print("无效的歌单数据。")
        return songs

    tracks = playlist.get("tracks", [])

    for track in tracks:
        song_name = track.get("name", "未知歌曲")
        artists = track.get("ar", [])
        artist_names = " / ".join([artist.get("name", "未知艺术家") for artist in artists])
        full_song_info = f"{song_name} - {artist_names}"
        songs.append(full_song_info)

    return songs


def main():
    # 示例歌单链接
    playlist_link = input("请输入网易云音乐歌单链接: ").strip()

    # 提取歌单 ID
    playlist_id = extract_playlist_id(playlist_link)
    if not playlist_id:
        print("未能提取到歌单 ID。")
        return

    print(f"提取到歌单 ID: {playlist_id}")

    # 获取歌单详情
    playlist_json = get_playlist_details(playlist_id)
    if not playlist_json:
        print("未能获取歌单详情。")
        return

    # 提取歌曲列表
    songs = extract_songs(playlist_json)
    if not songs:
        print("歌单中没有歌曲。")
        return

    # 输出歌曲列表
    print(f"\n歌单名称: {playlist_json['playlist'].get('name', '未知歌单')}")
    print(f"歌曲总数: {len(songs)}")
    print("歌曲列表:")
    for idx, song in enumerate(songs, 1):
        print(f"{idx}. {song}")


if __name__ == "__main__":
    main()
