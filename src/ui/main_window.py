import os
import json
import ctypes
import ctypes.wintypes
from pathlib import Path
import sys
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

def get_resource_path(relative_path: str) -> Path:
    if getattr(sys, 'frozen', False):
        base_path = Path(sys.executable).parent
        # --onedir 默认释放到 exe 同级目录，直接拼接即可
        target = base_path / relative_path
        if target.exists():
            return target
        # 兼容 --onefile 或旧版 PyInstaller
        if hasattr(sys, '_MEIPASS'):
            return Path(sys._MEIPASS) / relative_path
    return Path(relative_path)

try:
    import keyboard
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False
    print("[UI] ⚠️ keyboard库未安装，全局热键功能不可用")

from src.core.session_manager import SceneSessionManager
from src.utils.config import load_config, save_config, get_shortcut
from src.core.worker import MonitorWorker
# 不再使用旧的 interaction，我们用自己实现的 mixin
# from src.ui.interaction import WindowInteractionMixin
from src.ui.settings_page import SettingsPage
from src.ui.monitor_page import MonitorPage
from src.ui.loot_browser import LootBrowser


# ========== 自定义交互 Mixin（基于定时器轮询 + WS_EX_TRANSPARENT）==========
class WindowInteractionMixin:
    """提供基于轮询的局部穿透（标题栏可交互，其他区域穿透）"""

    def setup_interaction(self):
        self._is_locked = False          # 用户主动锁定（穿透）
        self._temp_unlock = False        # 临时解锁（鼠标悬浮在标题栏）
        self._drag_pos = QPoint()
        self._drag_active = False
        self._hwnd = None

        # 悬停检测定时器（每100ms检测一次鼠标是否在标题栏）
        self._hover_timer = QTimer(self)
        self._hover_timer.setInterval(100)
        self._hover_timer.timeout.connect(self._check_hover_state)

        # 延迟重新锁定定时器（离开标题栏后300ms恢复穿透）
        self._relock_timer = QTimer(self)
        self._relock_timer.setSingleShot(True)
        self._relock_timer.setInterval(300)
        self._relock_timer.timeout.connect(self._on_relock_timeout)

        self.installEventFilter(self)
        QTimer.singleShot(0, self._init_hwnd)   # 延迟获取窗口句柄

    def _init_hwnd(self):
        self._hwnd = int(self.winId())
        self._apply_lock_state()

    def _check_hover_state(self):
        if not self._is_locked or self._hwnd is None:
            return
        # 确保 header 存在（由主窗口提供）
        if not hasattr(self, 'header') or self.header is None:
            return
        # 计算标题栏的全局矩形
        header_global_rect = QRect(self.header.mapToGlobal(QPoint(0, 0)), self.header.size())
        cursor_pos = QCursor.pos()
        is_over_header = header_global_rect.contains(cursor_pos)

        if is_over_header:
            if not self._temp_unlock:
                self._temp_unlock = True
                self._relock_timer.stop()
                self._apply_lock_state()
        else:
            if self._temp_unlock and not self._relock_timer.isActive():
                self._relock_timer.start()

    def _on_relock_timeout(self):
        self._temp_unlock = False
        self._apply_lock_state()

    def _apply_lock_state(self):
        if self._hwnd is None:
            return
        should_transparent = self._is_locked and not self._temp_unlock
        self._set_clickthrough(should_transparent)
        # 更新按钮图标（如果主窗口提供了 btn_lock）
        if hasattr(self, 'btn_lock'):
            self.btn_lock.setText("🔒" if self._is_locked else "🔓")
            self.btn_lock.setToolTip("已锁定（穿透）" if self._is_locked else "未锁定")

    def _set_clickthrough(self, enable):
        if self._hwnd is None:
            return
        try:
            WS_EX_TRANSPARENT = 0x00000020
            GWL_EXSTYLE = -20
            user32 = ctypes.windll.user32
            ex_style = user32.GetWindowLongW(self._hwnd, GWL_EXSTYLE)
            if enable:
                new_style = ex_style | WS_EX_TRANSPARENT
            else:
                new_style = ex_style & ~WS_EX_TRANSPARENT
            if new_style != ex_style:
                user32.SetWindowLongW(self._hwnd, GWL_EXSTYLE, new_style)
                # 0x0037 = SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED | SWP_NOACTIVATE
                user32.SetWindowPos(self._hwnd, 0, 0, 0, 0, 0, 0x0037)
        except Exception as e:
            print(f"[UI] 设置穿透样式失败: {e}")

    def toggle_lock(self):
        """用户主动切换锁定状态（按钮或热键调用）"""
        self._is_locked = not self._is_locked
        self._temp_unlock = False
        self._relock_timer.stop()
        if self._is_locked:
            self._hover_timer.start()
        else:
            self._hover_timer.stop()
        self._apply_lock_state()

    def eventFilter(self, obj, event):
        """处理标题栏拖动（仅当鼠标按下时在标题栏内）"""
        if obj is self:
            et = event.type()
            if et == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                if hasattr(self, 'header') and self.header.geometry().contains(event.pos()):
                    self._drag_active = True
                    self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
                    event.accept()
                    return True
            elif et == QEvent.MouseMove and self._drag_active:
                self.move(event.globalPos() - self._drag_pos)
                event.accept()
                return True
            elif et == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                self._drag_active = False
                event.accept()
                return True
        return False

    def _update_lock_ui(self):
        """更新锁定按钮的图标和提示（始终可用）"""
        if hasattr(self, 'btn_lock'):
            self.btn_lock.setEnabled(True)   # 始终启用
            self.btn_lock.setText("🔒" if self._is_locked else "🔓")
            self.btn_lock.setToolTip("已锁定（穿透）" if self._is_locked else "未锁定")


# ========== 主窗口类 ==========
class D2ROverlay(QWidget, WindowInteractionMixin):
    def __init__(self, session_manager=None, parent=None):
        super().__init__(parent)
        
        self.session_manager = session_manager or SceneSessionManager()
        self.monitoring = False
        self._worker = None
        self._thread = None
        self.config = load_config()
        
        self._init_ui()
        self._apply_config()
        self._bind_signals()
        self._load_theme_list()
        self._apply_theme()
        
        self.loots_manager = None
        self._init_loots_manager()
        
        self._setup_global_hotkeys()
        
        # 初始化交互（必须在 UI 创建后调用，因为需要访问 self.header）
        self.setup_interaction()
        self._update_lock_ui()   # 初始禁用按钮（monitoring=False）
        
        self.btn_start.setProperty("state", "ready")
        self.btn_start.setText("▶")
        self.btn_start.style().unpolish(self.btn_start)
        self.btn_start.style().polish(self.btn_start)
        
        if self.session_manager:
            print("[D2ROverlay] 📊 初始化预加载统计数据...")
            stats = self.session_manager.get_stats()
            if stats:
                self.monitor_page.update_stats_display(stats)
            
        self._update_session_combo_state()

    def _init_ui(self):
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(340, 500)
        self.move(QApplication.primaryScreen().geometry().right() - 360, 20)

        # 基础窗口样式：仅 WS_EX_LAYERED + WS_EX_TOOLWINDOW（不设置 TRANSPARENT）
        try:
            hwnd = int(self.winId())
            GWL_EXSTYLE = -20
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_LAYERED = 0x00080000
            ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style | WS_EX_TOOLWINDOW | WS_EX_LAYERED)
        except Exception as e:
            print(f"[UI] ⚠️ 设置窗口样式失败: {e}")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.header = QWidget()
        self.header.setObjectName("header")
        self.header.setFixedHeight(36)
        h = QHBoxLayout(self.header)
        h.setContentsMargins(8, 0, 6, 0)
        h.setSpacing(6)
        
        self.lbl_title = QLabel(" D2R暗黑小记")
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
        
        for btn in [self.btn_start, self.btn_settings, self.btn_loot, self.btn_lock, self.btn_close]:
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setAutoDefault(False)
            btn.setDefault(False)

        for widget in self.findChildren(QWidget):
            if isinstance(widget, (QComboBox, QPushButton, QLineEdit, QSpinBox, QStackedWidget)):
                widget.setFocusPolicy(Qt.NoFocus)
        
        self.installEventFilter(self)

    def _init_loots_manager(self):
        try:
            from .loots import LootScreenshot
            self.loots_manager = LootScreenshot(session_manager=self.session_manager, save_dir="./Loot")
            print("[UI] ✅ Loots截图功能已初始化")
        except Exception as e:
            print(f"[UI] ⚠️ Loots功能初始化失败: {e}")

    def _setup_global_hotkeys(self):
        if not HAS_KEYBOARD:
            return
        try:
            sc = get_shortcut("capture_screenshot") or "alt+c"
            lk = get_shortcut("lock_unlock") or "alt+z"
            try:
                keyboard.remove_hotkey(sc.lower())
                keyboard.remove_hotkey(lk.lower())
            except:
                pass
            keyboard.add_hotkey(sc.lower(), self._on_screenshot_hotkey, suppress=True)
            keyboard.add_hotkey(lk.lower(), self._on_lock_hotkey, suppress=True)
            print(f"[UI] ✅ 全局热键已注册: 截图={sc}, 锁定={lk}")
        except Exception as e:
            print(f"[UI] ❌ 热键注册失败: {e}")
    
    def _on_screenshot_hotkey(self):
        QTimer.singleShot(0, self._safe_screenshot)

    def _safe_screenshot(self):
        if self.loots_manager:
            import threading
            threading.Thread(target=self.loots_manager.manual_capture, daemon=True).start()
    
    def _on_lock_hotkey(self):
        QTimer.singleShot(0, self._safe_toggle_lock)

    def _safe_toggle_lock(self):
        self.toggle_lock()   # 调用 mixin 的方法

    def _bind_signals(self):
        self.btn_start.clicked.connect(self._toggle_monitor)
        self.btn_settings.clicked.connect(lambda: self.stacked.setCurrentWidget(self.settings_page))
        self.settings_page.btn_back.clicked.connect(lambda: self.stacked.setCurrentWidget(self.monitor_page))
        self.btn_lock.clicked.connect(self._on_lock_clicked)
        self.btn_close.clicked.connect(self.close)
        self.btn_loot.clicked.connect(self._open_loot_directory)
        self.monitor_page.start_requested.connect(self._toggle_monitor)
        self.settings_page.btn_add.clicked.connect(self._add_session)
        self.settings_page.btn_del.clicked.connect(self._delete_session)
        self.monitor_page.cmb_session.currentTextChanged.connect(self._on_session_changed)
        self.settings_page.cmb_session.currentTextChanged.connect(self._on_session_changed)
        self.settings_page.slider_opa.valueChanged.connect(self._update_opacity)
        for s in [self.settings_page.spin_wait_max, self.settings_page.spin_ig_min, self.settings_page.spin_ig_max]:
            s.textChanged.connect(self._save_all_config)
        self.settings_page.theme_changed.connect(self._apply_theme)

    def _update_session_combo_state(self):
        in_game = False
        if self.monitoring and self.session_manager and hasattr(self.session_manager, "_current_round"):
            in_game = getattr(self.session_manager, "_current_round", {}).get("in_game_start", 0.0) > 0.0
        enable = not self.monitoring or not in_game
        self.monitor_page.cmb_session.setEnabled(enable)
        self.settings_page.cmb_session.setEnabled(enable)
        tip = "对局进行中，无法切换会话" if not enable else ""
        self.monitor_page.cmb_session.setToolTip(tip)
        self.settings_page.cmb_session.setToolTip(tip)

    def _handle_stats_update(self, stats: dict):
        self._update_session_combo_state()

    def _open_loot_directory(self):
        try:
            if not hasattr(self, '_loot_browser') or not self._loot_browser:
                self._loot_browser = LootBrowser("./Loot", self)
            self._loot_browser.setWindowFlags(self._loot_browser.windowFlags() | Qt.WindowStaysOnTopHint)
            self._loot_browser.show()
            self._loot_browser.raise_()
        except Exception as e:
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
                        name = json.load(f).get("name", fname.replace(".json", ""))
                    self.settings_page.cmb_theme.addItem(name, fname.replace(".json", ""))
                except:
                    pass
        idx = self.settings_page.cmb_theme.findData(self.config.get("theme", "dark"))
        if idx >= 0:
            self.settings_page.cmb_theme.setCurrentIndex(idx)
        self.settings_page.cmb_theme.blockSignals(False)

    def _apply_config(self):
        for cb in [self.monitor_page.cmb_session, self.settings_page.cmb_session]:
            cb.blockSignals(True)
            cb.clear()
        for s in self.config.get("sessions", []):
            if s.strip():
                self.monitor_page.cmb_session.addItem(s.strip())
                self.settings_page.cmb_session.addItem(s.strip())
        saved = self.config.get("session", "")
        idx = self.monitor_page.cmb_session.findText(saved)
        self.monitor_page.cmb_session.setCurrentIndex(idx if idx >= 0 else 0)
        self._sync_session_combos()
        for cb in [self.monitor_page.cmb_session, self.settings_page.cmb_session]:
            cb.blockSignals(False)
        
        f = self.config.get("filters", {})
        self.settings_page.spin_wait_max.setText(str(f.get("wait_max", 0)))
        self.settings_page.spin_ig_min.setText(str(f.get("ig_min", 0)))
        self.settings_page.spin_ig_max.setText(str(f.get("ig_max", 0)))
        self.settings_page.slider_opa.setValue(self.config.get("opacity", 85))
        self._update_opacity()

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

    def _get_filter_int(self, le, default=0):
        try:
            return int(le.text())
        except:
            return default

    def _save_all_config(self):
        from src.utils.config import get_all_shortcuts
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
            "shortcuts": get_all_shortcuts()
        })

    def _update_opacity(self):
        self.setWindowOpacity(self.settings_page.slider_opa.value() / 100.0)

    def _on_session_changed(self, new_name: str):
        if self.monitoring and self.session_manager:
            in_game = getattr(self.session_manager, "_current_round", {}).get("in_game_start", 0.0) > 0.0
            if in_game:
                for cb in [self.monitor_page.cmb_session, self.settings_page.cmb_session]:
                    cb.blockSignals(True)
                    cb.setCurrentText(self.session_manager.get_current_session_name())
                    cb.blockSignals(False)
                QMessageBox.warning(self, "提示", "对局进行中，无法切换会话")
                return
        if not new_name or not self.session_manager:
            return
        sender = self.sender()
        if sender == self.monitor_page.cmb_session:
            self.settings_page.cmb_session.blockSignals(True)
            self.settings_page.cmb_session.setCurrentText(new_name)
            self.settings_page.cmb_session.blockSignals(False)
        elif sender == self.settings_page.cmb_session:
            self.monitor_page.cmb_session.blockSignals(True)
            self.monitor_page.cmb_session.setCurrentText(new_name)
            self.monitor_page.cmb_session.blockSignals(False)
        self._save_all_config()
        self.session_manager.switch_session(new_name)
        stats = self.session_manager.get_stats()
        if stats:
            self.monitor_page.update_stats_display(stats)

    def _toggle_monitor(self):
        if not self.monitoring:
            session = self.monitor_page.cmb_session.currentText().strip()
            if not session:
                return QMessageBox.warning(self, "提示", "请先添加或选择会话")
            self._reset_start_button("stopping")
            filters = {
                "wait_max": self._get_filter_int(self.settings_page.spin_wait_max) or 0,
                "ingame_min": self._get_filter_int(self.settings_page.spin_ig_min),
                "ingame_max": self._get_filter_int(self.settings_page.spin_ig_max) or 0
            }
            self._worker = MonitorWorker(session, filters, session_manager=self.session_manager)
            self._thread = QThread()
            self._worker.moveToThread(self._thread)
            self._thread.started.connect(self._worker.run)
            self._worker.stats_updated.connect(self.monitor_page.update_stats_display)
            self._worker.stats_updated.connect(self._handle_stats_update)
            self._worker.finished.connect(self._thread.quit)
            self._thread.finished.connect(self._cleanup_thread)
            self.monitoring = True
            self.monitor_page.set_running_state(True)
            self._reset_start_button("running")
            self._update_session_combo_state()
            # 启动监控后，启用锁定按钮并刷新状态
            self._update_lock_ui()
            self._thread.start()
        else:
            self.monitoring = False
            self.monitor_page.set_running_state(False)
            self._reset_start_button("stopping")
            if self._worker:
                self._worker.stop()
            # 停止监控后，禁用锁定按钮，并强制退出穿透模式
            self._update_lock_ui()
            # if self._is_locked:
            #     self.toggle_lock()   # 确保退出锁定状态

    def _reset_start_button(self, state="ready"):
        self.btn_start.style().unpolish(self.btn_start)
        if state == "running":
            self.btn_start.setProperty("state", "running")
            self.btn_start.setText("⏹")
            self.btn_start.setEnabled(True)
        elif state == "stopping":
            self.btn_start.setText("⏸ 停止中...")
            self.btn_start.setEnabled(False)
        else:
            self.btn_start.setProperty("state", "ready")
            self.btn_start.setText("▶")
            self.btn_start.setEnabled(True)
        self.btn_start.style().polish(self.btn_start)

    def _cleanup_thread(self):
        self._worker = None
        self._thread = None
        self.monitoring = False
        self._reset_start_button("ready")
        self._update_session_combo_state()

    def _on_lock_clicked(self):
        self.toggle_lock()

    def _add_session(self):
        name = self.settings_page.edit_new.text().strip()
        if not name:
            return QMessageBox.warning(self, "提示", "请输入会话名称")
        if self.monitor_page.cmb_session.findText(name) >= 0:
            return QMessageBox.information(self, "提示", "已存在")
        self.monitor_page.cmb_session.addItem(name)
        self.monitor_page.cmb_session.setCurrentText(name)
        self.settings_page.edit_new.clear()
        self._sync_session_combos()
        self._save_all_config()
        QMessageBox.information(self, "成功", f"已添加: {name}")

    def _delete_session(self):
        if self.settings_page.cmb_session.count() <= 1:
            return QMessageBox.warning(self, "提示", "至少保留一个")
        name = self.settings_page.cmb_session.currentText()
        if QMessageBox.question(self, "确认", f"删除 '{name}'?") == QMessageBox.Yes:
            idx = self.monitor_page.cmb_session.findText(name)
            if idx >= 0:
                self.monitor_page.cmb_session.removeItem(idx)
            self._sync_session_combos()
            self._save_all_config()

    def _apply_theme(self, theme_name=None):
        if theme_name is None:
            theme_name = self.config.get("theme", "dark")
        themes_dir = get_resource_path("src/ui/themes")
        print(f"[DEBUG] 查找主题目录: {themes_dir}")
        print(f"[DEBUG] base_style.qss 存在: {(themes_dir / 'base_style.qss').exists()}")
        print(f"[DEBUG] 深空灰.json 存在: {(themes_dir / f'{theme_name}.json').exists()}")
        base = themes_dir / "base_style.qss"
        theme_file = themes_dir / f"{theme_name}.json"
        if not base.exists() or not theme_file.exists():
            self.setStyleSheet("QWidget { background: #1A1A1A; color: #C8C8C8; font-family: 'Microsoft YaHei'; } QPushButton { background: #2A2A2A; border-radius: 6px; }")
            return
        with open(base, "r", encoding="utf-8") as f:
            qss = f.read()
        with open(theme_file, "r", encoding="utf-8") as f:
            colors = json.load(f).get("colors", {})
        for k, v in colors.items():
            qss = qss.replace(f"{{{{{k}}}}}", v)
        self.setStyleSheet(qss)
        self.config["theme"] = theme_name
        save_config(self.config)

    def closeEvent(self, event):
        self._save_all_config()
        if self._worker:
            self._worker.stop()
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            if not self._thread.wait(1500):
                try:
                    self._thread.terminate()
                    self._thread.wait()
                except:
                    pass
        if HAS_KEYBOARD:
            try:
                keyboard.unhook_all()
            except:
                pass
        # 清理穿透样式
        if self._hwnd:
            try:
                user32 = ctypes.windll.user32
                WS_EX_TRANSPARENT = 0x00000020
                ex_style = user32.GetWindowLongW(self._hwnd, -20)
                user32.SetWindowLongW(self._hwnd, -20, ex_style & ~WS_EX_TRANSPARENT)
                user32.SetWindowPos(self._hwnd, 0, 0, 0, 0, 0, 0x0037)
            except:
                pass
        event.accept()

    # def eventFilter(self, obj, event):
    #     # 为了避免和 mixin 的 eventFilter 冲突，这里直接调用父类（mixin 的 event r
    #     # 但为了简单，直接将拖动逻辑放在这里（但 mixin 也有，可能会重复）。为避免冲突，这里只处理其他事件
    #     # 实际 mixin 的 eventFilter 会处理拖动，我们不需要重复。
    #     # 但为了安全，我们不覆盖，让 mixin 处理。所以这里直接返回 False。
    #     return False