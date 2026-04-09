import os, json, ctypes
import subprocess
from pathlib import Path
import sys
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *


def get_resource_path(relative_path: str) -> Path:
    """单文件/目录模式兼容的资源路径解析"""
    if getattr(sys, 'frozen', False):
        # 单文件模式：资源解压到 sys._MEIPASS 目录
        if hasattr(sys, '_MEIPASS'):
            base_path = Path(sys._MEIPASS)
        else:
            # 目录模式：资源与 exe 同级
            base_path = Path(sys.executable).parent
        return base_path / relative_path
    # 开发环境
    return Path(relative_path)

# 重新导入keyboard库用于全局热键
try:
    import keyboard
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False
    print("[UI] ⚠️ keyboard库未安装，全局热键功能不可用")

from src.core.session_manager import SceneSessionManager
from src.utils.config import load_config, save_config
from src.core.worker import MonitorWorker
from src.ui.interaction import WindowInteractionMixin
from src.ui.settings_page import SettingsPage
from src.ui.monitor_page import MonitorPage
from src.ui.loot_browser import LootBrowser

class D2ROverlay(QWidget, WindowInteractionMixin):
    def __init__(self, session_manager=None, parent=None):
        super().__init__(parent)
        
        # 🔑 1. 核心组件初始化
        self.session_manager = session_manager if session_manager else SceneSessionManager()
        
        # 🔑 2. 线程/任务管理初始化
        self.monitoring = False
        self._worker = None
        self._thread = None
        
        # 🔑 3. 配置加载
        self.config = load_config()
        
        # 🔑 4. UI 与业务初始化
        self._init_ui()
        self._apply_config()
        self._bind_signals()
        self._load_theme_list()
        self._apply_theme()
        
        # 🔑 5. 截图工具初始化
        self.loots_manager = None
        self._init_loots_manager()
        
        # 🔑 6. 全局热键注册
        self._setup_global_hotkeys()
        
        # 🔑 7. 按钮初始状态
        self.btn_start.setProperty("state", "ready")
        self.btn_start.setText("▶")
        self.btn_start.style().unpolish(self.btn_start)
        self.btn_start.style().polish(self.btn_start)
        
        # 🔑 8. 交互逻辑绑定
        self.setup_interaction()
        
        # 🔑 9. 初始化时预加载一次数据
        if self.session_manager:
            print("[D2ROverlay] 📊 初始化预加载统计数据...")
            stats = self.session_manager.get_stats()
            if stats:
                self.monitor_page.update_stats_display(stats)
        
        # 🔑 10. 初始化会话选择框状态
        self._update_session_combo_state()

    def _init_ui(self):
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(340, 500)
        self.move(QApplication.primaryScreen().geometry().right() - 360, 20)

        try:
            hwnd = int(self.winId())
            GWL_EXSTYLE = -20; WS_EX_TOOLWINDOW = 0x00000080
            ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style | WS_EX_TOOLWINDOW)
        except: 
            pass

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.header = QWidget()
        self.header.setObjectName("header")
        self.header.setFixedHeight(36)
        h = QHBoxLayout(self.header)
        h.setContentsMargins(8, 0, 6, 0)
        h.setSpacing(6)
        
        self.lbl_title = QLabel(" D2R 场景监控")
        self.lbl_title.setObjectName("lbl_title")
        self.lbl_title.setCursor(Qt.SizeAllCursor)
        h.addWidget(self.lbl_title)
        h.addStretch()

        self.btn_start = QPushButton("▶")
        self.btn_start.setObjectName("btn_start")
        self.btn_start.setFixedSize(28, 28)
        self.btn_start.setCursor(Qt.PointingHandCursor)
        h.addWidget(self.btn_start)
        
        self.btn_settings = QPushButton("⚙️")
        self.btn_settings.setObjectName("btn_settings")
        self.btn_settings.setFixedSize(28, 28)
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        h.addWidget(self.btn_settings)
        
        self.btn_loot = QPushButton("📁")
        self.btn_loot.setObjectName("btn_loot")
        self.btn_loot.setFixedSize(28, 28)
        self.btn_loot.setCursor(Qt.PointingHandCursor)
        self.btn_loot.setToolTip("打开Loot目录")
        h.addWidget(self.btn_loot)
        
        self.btn_lock = QPushButton("🔓")
        self.btn_lock.setObjectName("btn_lock")
        self.btn_lock.setFixedSize(28, 28)
        self.btn_lock.setCursor(Qt.PointingHandCursor)
        self.btn_lock.setEnabled(False)
        h.addWidget(self.btn_lock)
        
        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("btn_close")
        self.btn_close.setFixedSize(28, 28)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        h.addWidget(self.btn_close)
        
        main_layout.addWidget(self.header)

        self.stacked = QStackedWidget()
        self.monitor_page = MonitorPage(session_manager=self.session_manager)
        self.settings_page = SettingsPage()
        self.stacked.addWidget(self.monitor_page)
        self.stacked.addWidget(self.settings_page)
        main_layout.addWidget(self.stacked)

    def _init_loots_manager(self):
        """初始化Loots截图管理器"""
        try:
            from .loots import LootScreenshot
            self.loots_manager = LootScreenshot(
                session_manager=self.session_manager,
                save_dir="./Loot"
            )
            print(f"[UI] ✅ Loots截图功能已初始化")
        except ImportError as e:
            print(f"[UI] ⚠️  Loots功能不可用: {e}")
        except Exception as e:
            print(f"[UI] ⚠️  Loots功能初始化失败: {e}")

    def _setup_global_hotkeys(self):
        """注册全局热键（使用keyboard库）"""
        if not HAS_KEYBOARD:
            print(f"[UI] ⚠️ keyboard库未安装，无法注册全局热键")
            return
        
        try:
            from src.utils.config import get_shortcut
            
            screenshot_shortcut = get_shortcut("capture_screenshot") or "ctrl+shift+s"
            lock_shortcut = get_shortcut("lock_unlock") or "ctrl+shift+l"
            
            # 清理可能存在的旧热键
            try:
                keyboard.remove_hotkey(screenshot_shortcut.lower())
                keyboard.remove_hotkey(lock_shortcut.lower())
            except:
                pass
            
            # 注册截图热键
            keyboard.add_hotkey(
                screenshot_shortcut.lower(), 
                self._on_screenshot_hotkey,
                suppress=True
            )
            print(f"[UI] ✅ 全局截图热键已注册: {screenshot_shortcut}")
            
            # 注册锁定热键
            keyboard.add_hotkey(
                lock_shortcut.lower(),
                self._on_lock_hotkey,
                suppress=True
            )
            print(f"[UI] ✅ 全局锁定热键已注册: {lock_shortcut}")
            
        except Exception as e:
            print(f"[UI] ❌ 注册全局热键失败: {e}")
    
    def _on_screenshot_hotkey(self):
        """截图热键回调"""
        QTimer.singleShot(0, self._safe_screenshot)
    
    def _safe_screenshot(self):
        """安全的截图方法（在主线程中执行）"""
        if self.loots_manager:
            try:
                print(f"[UI] 📸 截图热键触发")
                import threading
                thread = threading.Thread(target=self.loots_manager.manual_capture, daemon=True)
                thread.start()
            except Exception as e:
                print(f"[UI] ❌ 截图失败: {e}")
        else:
            print(f"[UI] ❌ Loots管理器未初始化")
    
    def _on_lock_hotkey(self):
        """锁定热键回调"""
        QTimer.singleShot(0, self._safe_toggle_lock)
    
    def _safe_toggle_lock(self):
        """安全的锁定切换方法"""
        if self.monitoring:
            self.toggle_lock()
            self._update_lock_ui()

    def _bind_signals(self):
        self.btn_start.clicked.connect(self._toggle_monitor)
        self.btn_settings.clicked.connect(lambda: self.stacked.setCurrentWidget(self.settings_page))
        self.settings_page.btn_back.clicked.connect(lambda: self.stacked.setCurrentWidget(self.monitor_page))
        self.btn_lock.clicked.connect(self._on_lock_clicked)
        self.btn_close.clicked.connect(self.close)
        
        self.btn_loot.clicked.connect(self._open_loot_directory)
        
        # 连接蒙版播放按钮信号
        self.monitor_page.start_requested.connect(self._toggle_monitor)
        
        self.settings_page.btn_add.clicked.connect(self._add_session)
        self.settings_page.btn_del.clicked.connect(self._delete_session)
        
        self.monitor_page.cmb_session.currentTextChanged.connect(self._on_session_changed)
        self.settings_page.cmb_session.currentTextChanged.connect(self._on_session_changed)
        
        self.settings_page.slider_opa.valueChanged.connect(self._update_opacity)
        
        for s in [self.settings_page.spin_wait_max,
                  self.settings_page.spin_ig_min, 
                  self.settings_page.spin_ig_max]:
            s.textChanged.connect(self._save_all_config)
            
        self.settings_page.theme_changed.connect(self._apply_theme)
    

    def _update_session_combo_state(self):
        """根据监控状态和对局状态更新会话选择框的启用状态"""
        # 获取当前的 in_game 状态
        in_game = False
        if (self.monitor_page and self.monitoring and 
            self.session_manager and hasattr(self.session_manager, "_current_round")):
            current_round = getattr(self.session_manager, "_current_round", {})
            in_game = current_round.get("in_game_start", 0.0) > 0.0
        
        # 规则：
        # 1. 如果不在监控状态（monitoring=False），会话选择框可用
        # 2. 如果在监控状态但在对局中（in_game=True），会话选择框禁用
        # 3. 如果在监控状态但不在对局中（in_game=False），会话选择框可用
        enable_combo = not self.monitoring or (self.monitoring and not in_game)
        
        self.monitor_page.cmb_session.setEnabled(enable_combo)
        self.settings_page.cmb_session.setEnabled(enable_combo)
        
        # 如果禁用，设置提示信息
        if not enable_combo:
            self.monitor_page.cmb_session.setToolTip("对局进行中，无法切换会话")
            self.settings_page.cmb_session.setToolTip("对局进行中，无法切换会话")
        else:
            self.monitor_page.cmb_session.setToolTip("")
            self.settings_page.cmb_session.setToolTip("")

    def _handle_stats_update(self, stats: dict):
        """处理统计更新，更新会话选择框状态"""
        self._update_session_combo_state()

    def _open_loot_directory(self):
        """打开Loot文件浏览器（内置）"""
        try:
            if not hasattr(self, '_loot_browser') or not self._loot_browser:
                self._loot_browser = LootBrowser("./Loot", self)
            
            self._loot_browser.setWindowFlags(
                self._loot_browser.windowFlags() | Qt.WindowStaysOnTopHint
            )
            
            self._loot_browser.show()
            self._loot_browser.raise_()
            self._loot_browser.activateWindow()
            
            print(f"[UI] 📁 已打开Loot文件浏览器")
            
        except Exception as e:
            print(f"[UI] ❌ 无法打开Loot浏览器: {e}")
            QMessageBox.warning(self, "错误", f"无法打开Loot浏览器: {e}")

    def _load_theme_list(self):
        theme_dir = os.path.join(os.path.dirname(__file__), "themes")
        if not os.path.isdir(theme_dir): 
            return

        self.settings_page.cmb_theme.blockSignals(True)
        self.settings_page.cmb_theme.clear()
        
        for fname in sorted(os.listdir(theme_dir)):
            if fname.endswith(".json"):
                try:
                    with open(os.path.join(theme_dir, fname), "r", encoding="utf-8") as f:
                        data = json.load(f)
                    display_name = data.get("name", fname.replace(".json", ""))
                    self.settings_page.cmb_theme.addItem(display_name, fname.replace(".json", ""))
                except:
                    self.settings_page.cmb_theme.addItem(fname.replace(".json", ""), fname.replace(".json", ""))
                    
        saved_theme = self.config.get("theme", "dark")
        idx = self.settings_page.cmb_theme.findData(saved_theme)
        if idx >= 0: 
            self.settings_page.cmb_theme.setCurrentIndex(idx)
        self.settings_page.cmb_theme.blockSignals(False)

    def _apply_config(self):
        self.monitor_page.cmb_session.blockSignals(True)
        self.settings_page.cmb_session.blockSignals(True)
        
        self.monitor_page.cmb_session.clear()
        self.settings_page.cmb_session.clear()
        
        for s in self.config.get("sessions", []):
            if s.strip(): 
                self.monitor_page.cmb_session.addItem(s.strip())
                self.settings_page.cmb_session.addItem(s.strip())
                
        saved = self.config.get("session", "")
        idx = self.monitor_page.cmb_session.findText(saved)
        self.monitor_page.cmb_session.setCurrentIndex(idx if idx >= 0 else 0)
        self._sync_session_combos()
        
        f = self.config.get("filters", {})
        self.settings_page.spin_wait_max.setText(str(f.get("wait_max", 0)))
        self.settings_page.spin_ig_min.setText(str(f.get("ig_min", 0)))
        self.settings_page.spin_ig_max.setText(str(f.get("ig_max", 0)))
        self.settings_page.slider_opa.setValue(self.config.get("opacity", 85))
        self._update_opacity()
        
        self.monitor_page.cmb_session.blockSignals(False)
        self.settings_page.cmb_session.blockSignals(False)

        # 🧹 清理：移除冗余的会话切换调用
        # 会话切换现在由 monitor_page.update_stats_display 处理

    def _sync_session_combos(self):
        cur = self.monitor_page.cmb_session.currentText()
        self.settings_page.cmb_session.blockSignals(True)
        self.settings_page.cmb_session.clear()
        for i in range(self.monitor_page.cmb_session.count()): 
            self.settings_page.cmb_session.addItem(self.monitor_page.cmb_session.itemText(i))
        idx = self.settings_page.cmb_session.findText(cur)
        if idx >= 0: 
            self.settings_page.cmb_session.setCurrentIndex(idx)
        self.settings_page.cmb_session.blockSignals(False)

    def _get_filter_int(self, line_edit, default=0):
        """安全获取 QLineEdit 的整数值"""
        try:
            return int(line_edit.text())
        except (ValueError, AttributeError):
            return default

    def _save_all_config(self):
        """保存所有配置，包括快捷键"""
        from src.utils.config import get_all_shortcuts
        
        current_shortcuts = get_all_shortcuts()
        
        save_config({
            "session": self.monitor_page.cmb_session.currentText(),
            "filters": {
                "wait_max": self._get_filter_int(self.settings_page.spin_wait_max),
                "ig_min": self._get_filter_int(self.settings_page.spin_ig_min),
                "ig_max": self._get_filter_int(self.settings_page.spin_ig_max)
            },
            "opacity": self.settings_page.slider_opa.value(),
            "sessions": [self.monitor_page.cmb_session.itemText(i) for i in range(self.monitor_page.cmb_session.count())],
            "theme": self.config.get("theme", "dark"),
            "shortcuts": current_shortcuts
        })

    def _update_opacity(self): 
        self.setWindowOpacity(self.settings_page.slider_opa.value() / 100.0)

    def _on_session_changed(self, new_name: str):
        """会话切换事件"""
        # 检查是否可以切换会话
        if self.monitoring:
            # 检查当前是否在对局中
            in_game = False
            if self.session_manager and hasattr(self.session_manager, "_current_round"):
                current_round = getattr(self.session_manager, "_current_round", {})
                in_game = current_round.get("in_game_start", 0.0) > 0.0
            
            if in_game:
                print("[UI] ⚠️ 对局进行中，禁止切换会话")
                
                # 恢复原会话选择
                self.monitor_page.cmb_session.blockSignals(True)
                self.settings_page.cmb_session.blockSignals(True)
                
                # 恢复为当前会话
                current_session = self.session_manager.get_current_session_name()
                idx = self.monitor_page.cmb_session.findText(current_session)
                if idx >= 0:
                    self.monitor_page.cmb_session.setCurrentIndex(idx)
                
                idx = self.settings_page.cmb_session.findText(current_session)
                if idx >= 0:
                    self.settings_page.cmb_session.setCurrentIndex(idx)
                
                self.monitor_page.cmb_session.blockSignals(False)
                self.settings_page.cmb_session.blockSignals(False)
                
                # 显示提示
                QMessageBox.warning(self, "提示", "对局进行中，无法切换会话")
                return
        
        if not new_name or not self.session_manager: 
            return
        
        if self.sender() == self.monitor_page.cmb_session:
            idx = self.settings_page.cmb_session.findText(new_name)
            if idx >= 0: 
                self.settings_page.cmb_session.setCurrentIndex(idx)
        elif self.sender() == self.settings_page.cmb_session:
            idx = self.monitor_page.cmb_session.findText(new_name)
            if idx >= 0: 
                self.monitor_page.cmb_session.setCurrentIndex(idx)
            
        self._save_all_config()
        res = self.session_manager.switch_session(new_name)
        
        # 🧹 清理：移除直接设置状态文本，由 update_stats_display 处理
        # 刷新监控页面显示
        stats = self.session_manager.get_stats()
        if stats:
            self.monitor_page.update_stats_display(stats)

    def _toggle_monitor(self):
        """
        切换监控状态（开始/停止）
        重构要点：
        1. 连接 stats_updated 到 monitor_page.update_stats_display
        2. 抽取重复的按钮重置逻辑到 _reset_start_button()
        3. 抽取线程清理逻辑到 _cleanup_thread()
        4. 使用更安全的信号断开方式
        """
        if not self.monitoring:
            # ========== 开始监控 ==========
            print("[MainWindow] ▶ 启动监控线程...")
            
            # 检查会话
            session = self.monitor_page.cmb_session.currentText().strip()
            if not session: 
                QMessageBox.warning(self, "提示", "请先添加或选择会话")
                return
            
            # 1. 创建Worker和线程
            filters = {
                "wait_max": self._get_filter_int(self.settings_page.spin_wait_max) or 0,
                "ingame_min": self._get_filter_int(self.settings_page.spin_ig_min),
                "ingame_max": self._get_filter_int(self.settings_page.spin_ig_max) or 0
            }
            
            self._worker = MonitorWorker(session, filters, session_manager=self.session_manager)
            self._thread = QThread()
            self._worker.moveToThread(self._thread)
            
            # 2. 连接信号
            self._thread.started.connect(self._worker.run)
            
            # 🎯 核心修复：连接到 monitor_page.update_stats_display
            self._worker.stats_updated.connect(self.monitor_page.update_stats_display)
            # 添加：连接统计更新信号到会话状态更新
            self._worker.stats_updated.connect(self._handle_stats_update)
            
            # 状态和错误信号
            self._worker.error_occurred.connect(
                lambda msg: print(f"[Worker Error] {msg}")
            )
            
            # 线程生命周期管理
            self._worker.finished.connect(self._thread.quit)
            self._worker.finished.connect(self._worker.deleteLater)
            self._thread.finished.connect(self._thread.deleteLater)
            self._thread.finished.connect(self._cleanup_thread)
            
            # 3. 更新UI状态
            self.monitoring = True
            self.monitor_page.set_running_state(True)
            self._reset_start_button(starting=True)
            self._update_lock_ui()  # 🔧 修复：调用更新锁定UI的方法
            
            # 4. 启动线程
            self._thread.start()
            
            # 5. 立即更新一次会话选择框状态
            self._update_session_combo_state()
            
            print(f"[MainWindow] ✅ 监控已启动")
            
        else:
            # ========== 停止监控 ==========
            print("[MainWindow] ⏸️ 停止监控线程...")
            
            # 1. 重置按钮状态（立即反馈）
            self._reset_start_button(stopping=True)
            
            # 2. 通知Worker停止
            if self._worker:
                self._worker.stop()
            
            # 3. 更新UI状态
            self.monitor_page.set_running_state(False)
            
            print("[MainWindow] ✅ 已发送停止信号")


    def _reset_start_button(self, starting=False, stopping=False):
        """
        重置开始按钮状态（抽取重复逻辑）
        Args:
            starting: 是否正在启动
            stopping: 是否正在停止
        """
        if starting:
            # 启动时的按钮状态
            self.btn_start.setProperty("state", "running")
            self.btn_start.setText("⏹")
            self.btn_start.style().unpolish(self.btn_start)
            self.btn_start.style().polish(self.btn_start)
            
        elif stopping:
            # 停止中的按钮状态
            self.btn_start.setText("停止中...")
            self.btn_start.setEnabled(False)
            
        else:
            # 默认停止状态
            self.btn_start.setProperty("state", "ready")
            self.btn_start.setText("▶")
            self.btn_start.style().unpolish(self.btn_start)
            self.btn_start.style().polish(self.btn_start)
            self.btn_start.setEnabled(True)

    def _cleanup_thread(self):
        """
        清理线程资源（安全的资源回收）
        """
        print("[MainWindow] 🧹 清理线程资源...")
        
        # 1. 安全断开信号连接
        if self._worker:
            try:
                self._worker.stats_updated.disconnect()
                # 🧹 清理：移除已无用的信号断开
                self._worker.error_occurred.disconnect()
                self._worker.finished.disconnect()
            except (TypeError, RuntimeError):
                # TypeError: 信号未连接
                # RuntimeError: C++对象已删除
                pass
        
        # 2. 重置状态
        self.monitoring = False
        
        # 3. 清理线程和Worker引用
        self._worker = None
        self._thread = None
        
        # 4. 更新锁定UI
        self._update_lock_ui()
        
        # 5. 最终重置按钮状态
        self._reset_start_button()
        
        # 6. 更新会话选择框状态
        self._update_session_combo_state()
        
        print("[MainWindow] ✅ 线程资源已清理")

    def _on_lock_clicked(self):
        """锁定按钮点击事件"""
        if not self.monitoring: 
            return
        self.toggle_lock()
        self._update_lock_ui()

    def _update_lock_ui(self):
        """更新锁定按钮UI"""
        self.btn_lock.setEnabled(self.monitoring)
        if self.monitoring: 
            self.btn_lock.setText("🔒" if self._is_locked else "🔓")
            self.btn_lock.setToolTip("已锁定穿透" if self._is_locked else "未锁定")
        else: 
            self.btn_lock.setText("🔓")
            self.btn_lock.setToolTip("未运行时无效")

    def _add_session(self):
        """添加新会话"""
        name = self.settings_page.edit_new.text().strip()
        if not name: 
            QMessageBox.warning(self, "提示", "请输入会话名称")
            return
        if self.monitor_page.cmb_session.findText(name) >= 0: 
            QMessageBox.information(self, "提示", "已存在")
            return
        self.monitor_page.cmb_session.addItem(name)
        self.monitor_page.cmb_session.setCurrentText(name)
        self.settings_page.edit_new.clear()
        self._sync_session_combos()
        self._save_all_config()
        QMessageBox.information(self, "成功", f"已添加: {name}")

    def _delete_session(self):
        """删除当前会话"""
        if self.settings_page.cmb_session.count() <= 1: 
            QMessageBox.warning(self, "提示", "至少保留一个")
            return
        name = self.settings_page.cmb_session.currentText()
        if QMessageBox.question(self, "确认", f"删除 '{name}'?") == QMessageBox.Yes:
            idx = self.monitor_page.cmb_session.findText(name)
            if idx >= 0: 
                self.monitor_page.cmb_session.removeItem(idx)
            self._sync_session_combos()
            self._save_all_config()

    def _apply_theme(self, theme_name: str = None):
        """应用主题样式"""
        if theme_name is None:
            theme_name = self.config.get("theme", "深空灰")

        # 🔧 使用资源路径解析函数，支持打包后从 exe 同级目录加载
        themes_dir = get_resource_path("src/ui/themes")  # 假设主题放在此相对路径下
        base_qss_path = themes_dir / "base_style.qss"
        theme_json_path = themes_dir / f"{theme_name}.json"

        if not base_qss_path.exists() or not theme_json_path.exists():
            print(f"[UI] ⚠️ 主题文件缺失 ({base_qss_path} 或 {theme_json_path})，启用内置兜底样式")
            self.setStyleSheet("""
                QWidget { background: #1A1A1A; color: #C8C8C8; font-family: 'Microsoft YaHei', sans-serif; }
                QLineEdit, QComboBox, QSpinBox { background: #262626; border: 1px solid #333333; border-radius: 6px; padding: 6px 8px; color: #D0D0D0; }
                QPushButton { background: #2A2A2A; border: 1px solid #333333; border-radius: 6px; color: #B0B0B0; }
                QPushButton:hover { background: #333333; border-color: #444444; }
                QPushButton:pressed { background: #222222; }
                QGroupBox { border: 1px solid #333333; border-radius: 8px; margin-top: 12px; padding-top: 14px; }
                QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; color: #888888; font-size: 12px; }
                #header { background: #222222; border-bottom: 1px solid #2F2F2F; }
                QLabel { color: #C0C0C0; }
            """)
            return

        with open(base_qss_path, "r", encoding="utf-8") as f:
            qss_template = f.read()
        with open(theme_json_path, "r", encoding="utf-8") as f:
            colors = json.load(f).get("colors", {})

        for key, value in colors.items():
            qss_template = qss_template.replace(f"{{{{{key}}}}}", value)

        self.setStyleSheet(qss_template)
        self.config["theme"] = theme_name
        save_config(self.config)
        print(f"[UI] ✅ 主题已应用: {theme_name}")

    def closeEvent(self, event):
        """窗口关闭事件"""
        self._save_all_config()
        
        # 停止监控worker
        if self._worker: 
            self._worker.stop()
        
        # 安全停止线程
        if self._thread and self._thread.isRunning():
            try:
                self._thread.quit()
                if not self._thread.wait(1500):
                    try:
                        self._thread.terminate()
                        self._thread.wait()
                    except:
                        pass
            except Exception as e:
                print(f"[UI] 停止线程时发生错误: {e}")
        
        # 清理键盘钩子
        if HAS_KEYBOARD:
            try: 
                keyboard.unhook_all()
                print(f"[UI] ✅ 键盘钩子已清理")
            except: 
                pass
        
        # 清理Loots管理器
        if hasattr(self, 'loots_manager') and self.loots_manager:
            try:
                if hasattr(self.loots_manager, 'cleanup'):
                    self.loots_manager.cleanup()
            except Exception as e:
                print(f"[UI] ❌ 清理Loots管理器失败: {e}")
        
        # 清理浏览器窗口
        if hasattr(self, '_loot_browser') and self._loot_browser:
            try:
                self._loot_browser.close()
            except:
                pass
            self._loot_browser = None
        
        # 接受关闭事件
        event.accept()
