import random
import time
import win32gui  # 👈 必须导入：用于 Windows 句柄验活
from PyQt5.QtCore import QObject, pyqtSignal
from src.utils.window_api import get_best_d2r_window, capture_window
from src.ai.detector import D2RSceneDetector
from src.core.session_manager import SceneSessionManager

class MonitorWorker(QObject):
    finished = pyqtSignal()
    stats_updated = pyqtSignal(dict)
    status_message = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, session_name: str, filters: dict, session_manager=None):
        super().__init__()
        self.session_name = session_name
        self.filters = filters
        self._running = False
        self._minimize_counter = 0
        self.session_manager = session_manager

    def run(self):
        self._running = True
        self._minimize_counter = 0
        manager = None
        AUTO_SAVE_INTERVAL = 30.0
        last_save_time = time.time()
        BASE_INTERVAL = 0.5  # 基础检测间隔

        try:
            detector = D2RSceneDetector()

            # ✅ 1. 绑定或创建 SessionManager
            if self.session_manager:
                manager = self.session_manager
                print(f"[Worker] 🤝 使用共享 SessionManager (ID: {id(manager)})")
            else:
                manager = SceneSessionManager()
                print(f"[Worker] 🆕 创建独立 SessionManager (ID: {id(manager)})")

            # ✅ 2. 配置过滤器并激活会话
            print(f"[Worker] ⚙️ 正在应用过滤器并激活会话: '{self.session_name}'")
            manager.configure_filters(**self.filters)
            manager.activate_session(self.session_name)
            print(f"[Worker] ✅ 会话激活完成，初始历史局数: {manager.get_stats()['historical']['total_runs']}")

            # ✅ 3. 初始窗口寻找
            hwnd = None
            while self._running and not hwnd:
                hwnd = get_best_d2r_window()
                if not hwnd:
                    self.status_message.emit("🔍 正在寻找 D2R 游戏窗口...")
                    time.sleep(1.0)
            if not self._running:
                return

            self.status_message.emit("✅ 已锁定游戏窗口，开始运行")

            # ✅ 4. 主监控循环（带自愈重连 + 异常静默降级）
            while self._running:
                # 🔑 修复点 A：每次循环校验句柄，游戏关闭/重启时自动重连
                if not win32gui.IsWindow(hwnd):
                    hwnd = get_best_d2r_window()
                    if not hwnd:
                        self.status_message.emit("🔍 窗口已关闭，正在重新寻找...")
                        time.sleep(BASE_INTERVAL + random.uniform(-0.1, 0.1))
                        continue
                    self._minimize_counter = 0
                    self.status_message.emit("✅ 已重新锁定窗口")

                # 🔑 修复点 B：安全截图，拦截 Win32 1400 等异常，防止误触发 error_occurred 弹窗
                frame = None
                try:
                    frame = capture_window(hwnd)
                except Exception:
                    frame = None  # 窗口瞬间销毁或截图波动，静默降级为 None

                if frame is None:
                    if self._minimize_counter < 3:
                        self._minimize_counter += 1
                    else:
                        evt = manager.update("minimized")
                        self.stats_updated.emit(evt.get("stats", {}))
                        if evt.get("message"):
                            self.status_message.emit(evt["message"])
                    time.sleep(BASE_INTERVAL + random.uniform(-0.1, 0.1))
                    continue
                else:
                    self._minimize_counter = 0

                # 场景识别
                res = detector.predict(hwnd)
                if res["stable"]:
                    evt = manager.update(res["scene"])
                    self.stats_updated.emit(evt.get("stats", {}))
                    if evt.get("message"):
                        self.status_message.emit(evt["message"])

                # 随机间隔控制频率（防反作弊检测）
                time.sleep(BASE_INTERVAL + random.uniform(-0.1, 0.1))

                # 定期保存进度
                if time.time() - last_save_time >= AUTO_SAVE_INTERVAL:
                    manager.save()
                    last_save_time = time.time()

        except Exception as e:
            # 仅对真正的程序逻辑错误发送信号，窗口丢失等已在上方拦截
            print(f"[Worker] ❌ 线程异常: {e}")
            self.error_occurred.emit(str(e))
        finally:
            if manager:
                try:
                    manager.pause_and_save()
                except Exception as e:
                    print(f"[Worker] 保存会话时发生异常: {e}")
            self.finished.emit()

    def stop(self):
        self._running = False
