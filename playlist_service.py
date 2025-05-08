from utils import detect_platform
from netease_music import extract_netease_playlist_id, get_netease_playlist_details, extract_netease_songs
from qqmusic import extract_qqmusic_playlist_id, QQMusicList

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