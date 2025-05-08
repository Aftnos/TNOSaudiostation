import re
from urllib.parse import urlparse, parse_qs

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