import sys
import requests
import pyaudio
import subprocess
import threading
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QPushButton, QLabel,
                             QLineEdit, QVBoxLayout, QHBoxLayout, QListWidget, QMessageBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

# 禁用 InsecureRequestWarning
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

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

    def get_available_endpoints(self):
        url = f"{self.host}/webapi/query.cgi"
        params = {
            "version": 1,
            "api.py": "SYNO.API.Info",
            "method": "query",
            "query": "all"
        }
        try:
            response = self.session.get(url, params=params, verify=False)
            response.raise_for_status()
            data = response.json()
            if data.get('success'):
                self.endpoints = data['data']
                return True
            else:
                print("无法获取可用端点")
                return False
        except requests.RequestException as e:
            print(f"请求错误: {e}")
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
            "api.py": "SYNO.API.Auth",
            "method": "login",
            "session": "AudioStation",
            "device_name": self.device_name,
            "account": self.username,
            "passwd": self.password,
            "enable_device_token": "yes"
        }
        try:
            response = self.session.post(url, data=payload, verify=False)
            response.raise_for_status()
            data = response.json()
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
                response.raise_for_status()
                data = response.json()
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
        except requests.RequestException as e:
            print(f"请求错误: {e}")
            return False

    def logout(self):
        auth_info = self.endpoints.get("SYNO.API.Auth")
        if not auth_info:
            print("Auth 端点未找到")
            return False
        path = auth_info['path']
        url = f"{self.host}/webapi/{path}"
        payload = {
            "version": 6,
            "api.py": "SYNO.API.Auth",
            "method": "logout",
            "session": "AudioStation",
            "_sid": self.sid
        }
        try:
            response = self.session.post(url, data=payload, verify=False)
            response.raise_for_status()
            data = response.json()
            if data.get('success'):
                print("注销成功")
                return True
            else:
                print("注销失败")
                return False
        except requests.RequestException as e:
            print(f"请求错误: {e}")
            return False

    def get_playlist_list(self):
        playlist_info = self.endpoints.get("SYNO.AudioStation.Playlist")
        if not playlist_info:
            print("Playlist 端点未找到")
            return []
        path = playlist_info['path']
        url = f"{self.host}/webapi/{path}"
        params = {
            "version": 2,
            "api.py": "SYNO.AudioStation.Playlist",
            "method": "list",
            "library": "all",
            "additional": "songs_song_tag",
            "_sid": self.sid
        }
        try:
            response = self.session.get(url, params=params, verify=False)
            response.raise_for_status()
            data = response.json()
            if data.get('success'):
                return data['data']['playlists']
            else:
                print("获取播放列表失败")
                return []
        except requests.RequestException as e:
            print(f"请求错误: {e}")
            return []

    def get_songs_in_playlist(self, playlist_id):
        playlist_info = self.endpoints.get("SYNO.AudioStation.Playlist")
        if not playlist_info:
            print("Playlist 端点未找到")
            return []
        path = playlist_info['path']
        url = f"{self.host}/webapi/{path}"
        params = {
            "version": 2,
            "api.py": "SYNO.AudioStation.Playlist",
            "method": "getinfo",
            "id": playlist_id,
            "additional": "songs_song_tag,songs_song_audio,songs_song_rating",
            "library": "personal",
            "_sid": self.sid
        }
        try:
            response = self.session.get(url, params=params, verify=False)
            response.raise_for_status()
            data = response.json()
            if data.get('success'):
                playlists = data['data'].get('playlists', [])
                if not playlists:
                    print("未找到指定的播放列表")
                    return []
                selected_playlist = playlists[0]
                songs = selected_playlist.get('additional', {}).get('songs', [])
                if not songs:
                    print("播放列表中没有歌曲")
                return songs
            else:
                error_code = data.get('error', {}).get('code', '未知')
                error_message = data.get('error', {}).get('message', '未知错误')
                print(f"获取播放列表中的歌曲失败，错误代码: {error_code}, 错误信息: {error_message}")
                return []
        except requests.RequestException as e:
            print(f"请求错误: {e}")
            return []

    def get_stream_url(self, song_id, method='transcode', format='mp3'):
        stream_info = self.endpoints.get("SYNO.AudioStation.Stream")
        if not stream_info:
            print("Stream 端点未找到")
            return None
        path = stream_info['path']
        if method == 'transcode':
            url = f"{self.host}/webapi/{path}/0.{format}"
            params = {
                "version": 2,
                "api.py": "SYNO.AudioStation.Stream",
                "method": "transcode",
                "id": song_id,
                "format": format,
                "_sid": self.sid
            }
            stream_url = f"{url}?{requests.compat.urlencode(params)}"
            return stream_url
        else:
            print("未知的流媒体方法")
            return None

class AudioPlayerThread(threading.Thread):
    def __init__(self, stream_url):
        super().__init__()
        self.stream_url = stream_url
        self.stop_event = threading.Event()

    def run(self):
        CHUNK = 1024
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', self.stream_url,
            '-f', 's16le',
            '-acodec', 'pcm_s16le',
            '-ar', '44100',
            '-ac', '2',
            'pipe:1'
        ]

        try:
            process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            print("FFmpeg 未安装或未在 PATH 中")
            return

        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16,
                        channels=2,
                        rate=44100,
                        output=True)

        try:
            while not self.stop_event.is_set():
                data = process.stdout.read(CHUNK)
                if not data:
                    break
                stream.write(data)
        except Exception as e:
            print(f"播放错误: {e}")
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()
            process.terminate()
            print("播放已停止")

    def stop(self):
        self.stop_event.set()

class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('AudioStation 登录')
        self.client = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        self.host_label = QLabel('DSM 地址:')
        self.host_input = QLineEdit()
        self.host_input.setText('https://192.168.2.2:5001/')  # 默认值，请修改为您的 DSM 地址

        self.username_label = QLabel('用户名:')
        self.username_input = QLineEdit()
        self.username_input.setText('tnos')  # 默认值，请修改为您的用户名

        self.password_label = QLabel('密码:')
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setText('Sph040627@')  # 默认值，请修改为您的密码

        self.login_button = QPushButton('登录')
        self.login_button.clicked.connect(self.login)

        layout.addWidget(self.host_label)
        layout.addWidget(self.host_input)
        layout.addWidget(self.username_label)
        layout.addWidget(self.username_input)
        layout.addWidget(self.password_label)
        layout.addWidget(self.password_input)
        layout.addWidget(self.login_button)

        self.setLayout(layout)

    def login(self):
        host = self.host_input.text()
        username = self.username_input.text()
        password = self.password_input.text()

        self.client = AudioStationClient(host, username, password)
        if not self.client.get_available_endpoints():
            QMessageBox.critical(self, '错误', '无法获取可用端点')
            return

        if not self.client.login():
            QMessageBox.critical(self, '错误', '登录失败，请检查用户名和密码')
            return

        QMessageBox.information(self, '成功', '登录成功！')
        self.main_window = MainWindow(self.client)
        self.main_window.show()
        self.close()

class MainWindow(QMainWindow):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.setWindowTitle('AudioStation 音乐播放器')
        self.player_thread = None
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QHBoxLayout()

        # 左侧：播放列表
        playlist_layout = QVBoxLayout()
        self.playlist_label = QLabel('播放列表')
        self.playlist_list = QListWidget()
        self.playlist_list.itemClicked.connect(self.load_songs)
        playlist_layout.addWidget(self.playlist_label)
        playlist_layout.addWidget(self.playlist_list)

        # 右侧：歌曲列表
        song_layout = QVBoxLayout()
        self.song_label = QLabel('歌曲列表')
        self.song_list = QListWidget()
        self.song_list.itemDoubleClicked.connect(self.play_song)
        song_layout.addWidget(self.song_label)
        song_layout.addWidget(self.song_list)

        # 底部：控制按钮
        control_layout = QHBoxLayout()
        self.play_button = QPushButton('播放')
        self.play_button.clicked.connect(self.play_selected_song)
        self.stop_button = QPushButton('停止')
        self.stop_button.clicked.connect(self.stop_playback)
        control_layout.addWidget(self.play_button)
        control_layout.addWidget(self.stop_button)

        # 组装布局
        layout.addLayout(playlist_layout)
        layout.addLayout(song_layout)

        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(control_layout)

        central_widget.setLayout(main_layout)

        self.load_playlists()

    def load_playlists(self):
        playlists = self.client.get_playlist_list()
        self.playlist_list.clear()
        self.playlists = playlists
        for pl in playlists:
            self.playlist_list.addItem(pl['name'])

    def load_songs(self, item):
        index = self.playlist_list.currentRow()
        selected_playlist = self.playlists[index]
        playlist_id = selected_playlist['id']
        songs = self.client.get_songs_in_playlist(playlist_id)
        self.song_list.clear()
        self.songs = songs
        for song in songs:
            title = song.get('title', '未知标题')
            artist = song.get('additional', {}).get('song_tag', {}).get('artist', '未知艺术家')
            display_text = f"{title} - {artist}"
            self.song_list.addItem(display_text)

    def play_song(self, item):
        self.stop_playback()
        index = self.song_list.currentRow()
        selected_song = self.songs[index]
        song_id = selected_song['id']
        stream_url = self.client.get_stream_url(song_id, method='transcode', format='mp3')
        if not stream_url:
            QMessageBox.critical(self, '错误', '无法获取流媒体链接')
            return
        self.player_thread = AudioPlayerThread(stream_url)
        self.player_thread.start()
        QMessageBox.information(self, '播放', f"正在播放：{item.text()}")

    def play_selected_song(self):
        selected_items = self.song_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, '提示', '请先选择一首歌曲')
            return
        self.play_song(selected_items[0])

    def stop_playback(self):
        if self.player_thread and self.player_thread.is_alive():
            self.player_thread.stop()
            self.player_thread.join()
            self.player_thread = None
            QMessageBox.information(self, '停止', '播放已停止')

    def closeEvent(self, event):
        self.stop_playback()
        self.client.logout()
        event.accept()

def main():
    app = QApplication(sys.argv)
    login_window = LoginWindow()
    login_window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
