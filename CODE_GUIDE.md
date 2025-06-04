# 代码结构说明

- **main.py** 入口文件，创建 `Application` 实例并启动 GUI。
- **gui.py** 用户界面逻辑，包含登录窗口和主窗口的实现。
- **audiostation.py** 与群晖 AudioStation 的交互封装，包括登录、歌曲缓存、歌单管理与导入等。
- **netease_music.py** 处理网易云音乐歌单链接的解析与歌曲列表获取。
- **qqmusic.py** 解析 QQ 音乐歌单并获取歌曲列表。
- **playlist_service.py** 根据链接判断平台并统一返回歌单信息。
- **utils.py** 提供辅助方法，目前包含 `detect_platform` 用于识别链接来源。

代码中通过 `log_func` 回调向 GUI 传递日志信息，便于在界面中显示执行过程。
