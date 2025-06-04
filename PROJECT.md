# 项目说明

TNOS AudioStation是一个用于向群晖 AudioStation 导入歌单的图形化工具。用户可以登录自己的群晖服务器，从网易云音乐或 QQ 音乐获取歌单并导入，也可以从本地文本文件导入。项目基于 Python 3 开发，界面由 `ttkbootstrap` 构建，主要功能代码在 `audiostation.py` 与 `gui.py` 中实现。

## 功能
- 账号登录并缓存群晖中的歌曲信息
- 管理已有歌单：查看及删除
- 从网易云音乐、QQ 音乐或本地文件导入歌单
- 模糊匹配已有歌曲并创建新的播放列表

## 运行方式
```bash
python main.py
```

更多使用说明见 `README.md`。
