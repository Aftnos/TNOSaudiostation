import threading
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import messagebox, filedialog
from tkinter.scrolledtext import ScrolledText

from audiostation import AudioStationClient
from playlist_service import fetch_song_list_from_link

class LoginWindow(ttk.Toplevel):
    def __init__(self, app, parent):
        super().__init__(parent)
        self.title("登录群晖AudioStation-艾拉与方块")
        self.geometry("500x450")  # 调整窗口尺寸
        self.resizable(False, False)
        self.app = app
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # 设置窗口图标
        self.set_icon()

        self.host_var = ttk.StringVar()
        self.username_var = ttk.StringVar()
        self.password_var = ttk.StringVar()

        self.create_widgets()

    def set_icon(self):
        try:
            self.iconbitmap("1.ico")
        except Exception as e:
            print(f"无法设置图标: {e}")


    def create_widgets(self):
        padding = {'padx': 10, 'pady': 10}

        # 使用 grid 布局管理器
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)

        # Host
        ttk.Label(self, text="群晖主机地址:\n(管理界面地址)").grid(column=0, row=0, sticky='W', **padding)
        ttk.Entry(self, textvariable=self.host_var, width=30).grid(column=1, row=0, sticky='EW', **padding)

        # Username
        ttk.Label(self, text="用户名:").grid(column=0, row=1, sticky='W', **padding)
        ttk.Entry(self, textvariable=self.username_var, width=30).grid(column=1, row=1, sticky='EW', **padding)

        # Password
        ttk.Label(self, text="密码:").grid(column=0, row=2, sticky='W', **padding)
        ttk.Entry(self, textvariable=self.password_var, show="*", width=30).grid(column=1, row=2, sticky='EW', **padding)

        # Login Button
        self.login_button = ttk.Button(self, text="登录", bootstyle=SUCCESS, command=self.login)
        self.login_button.grid(column=0, row=3, columnspan=2, sticky='EW', pady=20, padx=50)

        # Log Status
        ttk.Label(self, text="状态:").grid(column=0, row=4, sticky='NW', **padding)
        self.status_text = ScrolledText(self, height=5, width=35, state='disabled')
        self.status_text.grid(column=0, row=5, columnspan=2, sticky='EW', **padding)

    def login(self):
        host = self.host_var.get().strip()
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()

        if not host or not username or not password:
            messagebox.showwarning("错误", "你输入完了吗你！")
            return

        self.login_button.configure(state='disabled')
        self.log_status("开始登录群晖AudioStation...")

        def perform_login():
            self.app.audio_client = AudioStationClient(host, username, password)
            if not self.app.audio_client.get_available_endpoints():
                self.show_login_failure("乐，链接失败检查主机地址！\n要不就是你群晖有点毛病！")
                return
            if not self.app.audio_client.login():
                self.show_login_failure("乐，登录失败。")
                return
            if not self.app.audio_client.fetch_all_songs(log_func=self.log_status):
                self.show_login_failure("乐，获取歌曲缓存失败。")
                return
            self.log_status("登录并缓存歌曲成功。")
            self.show_login_success()

        threading.Thread(target=perform_login, daemon=True).start()

    def show_login_failure(self, message):
        self.log_status(message)
        self.login_button.configure(state='normal')
        messagebox.showerror("登录失败", message)

    def show_login_success(self):
        self.login_button.configure(state='normal')
        messagebox.showinfo("登录成功", "成功登录进去了")
        self.destroy()
        self.app.create_main_window()

    def log_status(self, message):
        def append_message():
            self.status_text.configure(state='normal')
            self.status_text.insert('end', f"{message}\n")
            self.status_text.see('end')
            self.status_text.configure(state='disabled')
        self.after(0, append_message)

    def on_close(self):
        if messagebox.askokcancel("离开", "真的要退出程序吗？QWQ"):
            self.app.root.destroy()


class Application:
    def __init__(self):
        self.audio_client = None
        self.root = ttk.Window(themename="cosmo")
        self.root.title("群晖AudioStation歌单导入工具-艾拉与方块")
        self.root.geometry("900x700")
        self.root.resizable(False, False)
        self.root.withdraw()  # 隐藏主窗口，直到登录成功

        # 设置图标
        self.set_icon(self.root)

        self.login_window = LoginWindow(self, self.root)

        # 创建主窗口的控件
        self.playlist_link_var = ttk.StringVar()
        self.new_playlist_name_var = ttk.StringVar()
        self.threshold_var = ttk.StringVar(value="70")
        self.import_mode = ttk.StringVar(value='link')
        self.selected_file_path = ''

        self.create_main_widgets()

        self.root.mainloop()

    def set_icon(self, window):
        # 设置 .ico 图标文件
        try:
            window.iconbitmap("1.ico")
        except Exception as e:
            print(f"无法设置图标: {e}")

    def create_main_window(self):
        self.root.deiconify()  # 显示主窗口
        # 更新主窗口的内容
        self.notebook.pack(expand=True, fill='both')
        self.load_playlists()

    def create_main_widgets(self):
        self.notebook = ttk.Notebook(self.root, bootstyle=PRIMARY)
        self.notebook.pack(expand=True, fill='both')

        self.manage_frame = ttk.Frame(self.notebook)
        self.import_frame = ttk.Frame(self.notebook)

        self.notebook.add(self.manage_frame, text='管理歌单')
        self.notebook.add(self.import_frame, text='导入歌单')

        self.create_manage_tab()
        self.create_import_tab()

    def create_manage_tab(self):
        padding = {'padx': 10, 'pady': 10}

        # 仅显示"名称"列，去掉"ID"列
        ttk.Label(self.manage_frame, text="现有歌单:").pack(anchor='w', **padding)

        # 修改Treeview，移除ID列
        self.playlist_tree = ttk.Treeview(self.manage_frame, columns=("Name",), show='headings', selectmode='browse')

        # 仅显示名称列
        self.playlist_tree.heading("Name", text="名称")
        self.playlist_tree.column("Name", width=700, anchor='w')
        self.playlist_tree.pack(fill='both', expand=True, **padding)

        # 删除按钮
        self.delete_button = ttk.Button(self.manage_frame, text="删除选中的歌单", bootstyle=DANGER,
                                        command=self.delete_selected_playlist)
        self.delete_button.pack(anchor='e', **padding)

    def create_import_tab(self):
        padding = {'padx': 10, 'pady': 10}

        # Import mode selection
        ttk.Label(self.import_frame, text="导入方式:").grid(column=0, row=0, sticky='W', **padding)
        self.link_radio = ttk.Radiobutton(self.import_frame, text='从链接导入', variable=self.import_mode, value='link', command=self.update_import_mode)
        self.link_radio.grid(column=1, row=0, sticky='W', **padding)
        self.file_radio = ttk.Radiobutton(self.import_frame, text='从文件导入', variable=self.import_mode, value='file', command=self.update_import_mode)
        self.file_radio.grid(column=2, row=0, sticky='W', **padding)

        # Playlist Link
        self.playlist_link_label = ttk.Label(self.import_frame, text="歌单链接 (网易云音乐或 QQ 音乐):")
        self.playlist_link_entry = ttk.Entry(self.import_frame, textvariable=self.playlist_link_var, width=80)
        self.playlist_link_label.grid(column=0, row=1, sticky='W', **padding)
        self.playlist_link_entry.grid(column=1, row=1, columnspan=2, sticky='EW', **padding)

        # File selection
        self.file_select_button = ttk.Button(self.import_frame, text="选择歌单文件 (txt)", command=self.select_file)
        self.selected_file_label = ttk.Label(self.import_frame, text="未选择文件")
        self.file_select_button.grid(column=0, row=2, sticky='W', **padding)
        self.selected_file_label.grid(column=1, row=2, columnspan=2, sticky='W', **padding)
        self.file_select_button.grid_remove()
        self.selected_file_label.grid_remove()

        # New Playlist Name
        ttk.Label(self.import_frame, text="新歌单名称:").grid(column=0, row=3, sticky='W', **padding)
        ttk.Entry(self.import_frame, textvariable=self.new_playlist_name_var, width=50).grid(column=1, row=3, columnspan=2, sticky='EW', **padding)

        # Matching Threshold
        ttk.Label(self.import_frame, text="匹配阈值 (默认70，范围0-100)\n匹配不好就低一点:").grid(column=0, row=4, sticky='W', **padding)
        ttk.Entry(self.import_frame, textvariable=self.threshold_var, width=10).grid(column=1, row=4, sticky='W', **padding)

        # Import Button
        self.import_button = ttk.Button(self.import_frame, text="导入歌单", bootstyle=SUCCESS, command=self.import_playlist)
        self.import_button.grid(column=1, row=5, sticky='E', **padding)

        # Status Text
        ttk.Label(self.import_frame, text="导入状态:").grid(column=0, row=6, sticky='NW', **padding)
        self.status_text = ScrolledText(self.import_frame, height=20, width=100, state='disabled')
        self.status_text.grid(column=0, row=7, columnspan=3, sticky='EW', **padding)

    def update_import_mode(self):
        mode = self.import_mode.get()
        if mode == 'link':
            self.playlist_link_label.grid()
            self.playlist_link_entry.grid()
            self.file_select_button.grid_remove()
            self.selected_file_label.grid_remove()
        elif mode == 'file':
            self.playlist_link_label.grid_remove()
            self.playlist_link_entry.grid_remove()
            self.file_select_button.grid()
            self.selected_file_label.grid()
        else:
            self.playlist_link_label.grid_remove()
            self.playlist_link_entry.grid_remove()
            self.file_select_button.grid_remove()
            self.selected_file_label.grid_remove()

    def select_file(self):
        file_path = filedialog.askopenfilename(title="选择歌单文件", filetypes=[("Text Files", "*.txt")])
        if file_path:
            self.selected_file_path = file_path
            self.selected_file_label.config(text=file_path)
        else:
            self.selected_file_path = ''
            self.selected_file_label.config(text="未选择文件")

    def load_playlists(self):
        playlists = self.audio_client.get_playlist_list()
        for item in self.playlist_tree.get_children():
            self.playlist_tree.delete(item)
        for pl in playlists:
            self.playlist_tree.insert('', 'end', values=(pl['id'], pl['name']))

    def delete_selected_playlist(self):
        selected = self.playlist_tree.selection()
        if not selected:
            messagebox.showwarning("选择错误", "请先选择一个歌单。")
            return
        playlist_id, playlist_name = self.playlist_tree.item(selected[0], 'values')
        confirm = messagebox.askyesno("确认删除", f"确定要删除歌单 '{playlist_name}' 吗？")
        if not confirm:
            return

        self.delete_button.configure(state='disabled')

        def perform_delete():
            self.log_status(f"正在删除歌单: {playlist_name} (ID: {playlist_id})...")
            success = self.audio_client.delete_playlist(playlist_id, log_func=self.log_status)
            if success:
                self.log_status(f"成功删除歌单: {playlist_name} (ID: {playlist_id})")
                self.playlist_tree.delete(selected[0])
                messagebox.showinfo("删除成功", f"成功删除歌单 '{playlist_name}'。")
            else:
                self.log_status(f"删除歌单失败: {playlist_name} (ID: {playlist_id})")
                messagebox.showerror("删除失败", f"无法删除歌单 '{playlist_name}'。")
            self.delete_button.configure(state='normal')

        threading.Thread(target=perform_delete, daemon=True).start()

    def import_playlist(self):
        new_playlist_name = self.new_playlist_name_var.get().strip()
        threshold_input = self.threshold_var.get().strip()

        if not new_playlist_name:
            messagebox.showwarning("输入错误", "请填写歌单名称。")
            return

        try:
            threshold = int(threshold_input) if threshold_input else 70
            if threshold < 0 or threshold > 100:
                messagebox.showwarning("输入错误", "匹配阈值必须在0到100之间，使用默认值70分。")
                threshold = 70
        except ValueError:
            messagebox.showwarning("输入错误", "匹配阈值必须是一个整数，使用默认值70分。")
            threshold = 70

        import_mode = self.import_mode.get()

        if import_mode == 'link':
            link = self.playlist_link_var.get().strip()
            if not link:
                messagebox.showwarning("输入错误", "请填写歌单链接。")
                return
        elif import_mode == 'file':
            if not self.selected_file_path:
                messagebox.showwarning("输入错误", "请先选择歌单文件。")
                return
        else:
            messagebox.showwarning("输入错误", "请选择导入方式。")
            return

        self.import_button.configure(state='disabled')

        def perform_import():
            if import_mode == 'link':
                self.log_status(f"开始从链接导入歌单: {new_playlist_name}")
                playlist_name, songs = fetch_song_list_from_link(link)
                if not songs:
                    self.log_status("未能获取到有效的歌曲列表，导入终止。")
                    messagebox.showerror("导入失败", "未能获取到有效的歌曲列表。")
                    self.enable_import_widgets()
                    return
                self.log_status(f"歌单名称: {playlist_name}")
                self.log_status(f"歌曲总数: {len(songs)}")
                if new_playlist_name != playlist_name:
                    self.log_status(f"自定义歌单名称: {new_playlist_name}")
                success = self.audio_client.import_playlist_from_song_list(songs, new_playlist_name, threshold, log_func=self.log_status)
            elif import_mode == 'file':
                self.log_status(f"开始从文件导入歌单: {new_playlist_name}")
                file_path = self.selected_file_path
                success = self.audio_client.import_playlist_from_file(file_path, new_playlist_name, threshold, log_func=self.log_status)
            else:
                self.log_status("未知的导入方式，导入终止。")
                success = False

            if success:
                self.log_status("歌单导入成功！")
                messagebox.showinfo("导入成功", f"歌单 '{new_playlist_name}' 导入成功。")
                self.load_playlists()
            else:
                self.log_status("歌单导入失败。")
                messagebox.showerror("导入失败", "歌单导入失败。")
            self.enable_import_widgets()

        threading.Thread(target=perform_import, daemon=True).start()

    def enable_import_widgets(self):
        self.import_button.configure(state='normal')

    def log_status(self, message):
        def append_message():
            self.status_text.configure(state='normal')
            self.status_text.insert('end', f"{message}\n")
            self.status_text.see('end')
            self.status_text.configure(state='disabled')
        self.root.after(0, append_message)