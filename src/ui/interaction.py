# import sys
# import ctypes
# import ctypes.wintypes
# from PyQt5.QtCore import QTimer, QPoint, Qt, QEvent, QRect
# from PyQt5.QtGui import QCursor
# from PyQt5.QtWidgets import QApplication, QWidget

# # 重新启用keyboard库
# try:
#     import keyboard
#     HAS_KEYBOARD = True
# except ImportError:
#     HAS_KEYBOARD = False
#     print("[Debug] keyboard库未安装，无法使用全局热键")

# # Windows API 常量
# WS_EX_LAYERED = 0x00080000
# GWL_EXSTYLE = -20

# user32 = ctypes.windll.user32

# class WindowInteractionMixin:
#     """提供窗口穿透、热键切换、临时悬浮解锁及拖动功能"""
    
#     def setup_interaction(self):
#         # 状态标志
#         self._is_locked = False          # 用户主动锁定（穿透）
#         self._temp_unlock = False        # 临时解锁（鼠标悬浮）
#         self._drag_pos = QPoint()        # 拖动起始点
#         self._drag_active = False        # 是否正在拖动
#         self._hwnd = None                # 窗口句柄，延迟获取

#         # 1. 悬停检测定时器（替代不可靠的 QEvent.Enter/Leave）
#         self._hover_timer = QTimer(self)
#         self._hover_timer.setInterval(100)  # 100ms 检测一次，性能开销极低
#         self._hover_timer.timeout.connect(self._check_hover_state)

#         # 2. 延迟重新锁定定时器
#         self._relock_timer = QTimer(self)
#         self._relock_timer.setSingleShot(True)
#         self._relock_timer.setInterval(300)
#         self._relock_timer.timeout.connect(self._on_relock_timeout)

#         # 注意：热键现在由主窗口通过keyboard库全局注册
#         # 这里不再注册热键，避免重复注册
#         print(f"[Debug] 窗口交互功能已初始化，热键由主窗口统一管理")

#         # 安装事件过滤器（仅用于拖动，不再依赖 Enter/Leave）
#         self.installEventFilter(self)

#         # 延迟获取窗口句柄
#         QTimer.singleShot(0, self._init_hwnd)
    
#     def _init_hwnd(self):
#         """获取窗口句柄并应用初始状态"""
#         self._hwnd = int(self.winId())
#         print(f"[Debug] 获取窗口句柄: {self._hwnd:#x}")
#         self._apply_lock_state()

#     def _check_hover_state(self):
#         """轮询检测鼠标是否在【标题栏】范围内（避免窗口主体误触解锁）"""
#         if not self._is_locked or self._hwnd is None:
#             return

#         # 安全获取标题栏控件
#         if not hasattr(self, 'header') or self.header is None or not self.header.isVisible():
#             return

#         # 将标题栏局部坐标转换为屏幕全局坐标
#         header_global_pos = self.header.mapToGlobal(QPoint(0, 0))
#         header_global_rect = QRect(header_global_pos, self.header.size())
#         cursor_pos = QCursor.pos()

#         # 判断光标是否在标题栏矩形内
#         is_over_header = header_global_rect.contains(cursor_pos)

#         if is_over_header:
#             # 悬浮在标题栏 -> 临时解锁
#             if not self._temp_unlock:
#                 self._temp_unlock = True
#                 self._relock_timer.stop()
#                 self._apply_lock_state()
#                 print("[Debug] 鼠标悬浮标题栏 -> 临时解锁")
#         else:
#             # 离开标题栏（无论鼠标是否仍在窗口主体上）-> 延迟恢复穿透
#             if self._temp_unlock and not self._relock_timer.isActive():
#                 self._relock_timer.start()
#                 print("[Debug] 鼠标离开标题栏 -> 启动重新锁定定时器(300ms)")

#     def _on_relock_timeout(self):
#         """延迟结束后，恢复穿透状态"""
#         self._temp_unlock = False
#         self._apply_lock_state()
#         print("[Debug] 延迟结束 -> 恢复穿透锁定")

#     def _apply_lock_state(self):
#         """根据状态更新窗口穿透样式"""
#         if self._hwnd is None:
#             return
#         should_transparent = self._is_locked and not self._temp_unlock
#         self._set_clickthrough(should_transparent)
        
#         # 更新锁按钮 UI
#         if hasattr(self, 'btn_lock'):
#             self.btn_lock.setText("🔒" if self._is_locked else "🔓")
#             self.btn_lock.setToolTip("已锁定（穿透）" if self._is_locked else "未锁定")
#         print(f"[Debug] 穿透状态: locked={self._is_locked}, temp={self._temp_unlock} -> 实际穿透={should_transparent}")

#     def _set_clickthrough(self, enable):
#         """通过 Win32 API 设置窗口是否穿透鼠标点击"""
#         if self._hwnd is None:
#             return
#         try:
#             ex_style = user32.GetWindowLongW(self._hwnd, GWL_EXSTYLE)
#             if enable:
#                 new_style = ex_style | WS_EX_TRANSPARENT | WS_EX_LAYERED
#             else:
#                 new_style = ex_style & ~WS_EX_TRANSPARENT
                
#             if new_style != ex_style:
#                 user32.SetWindowLongW(self._hwnd, GWL_EXSTYLE, new_style)
#                 # 0x0037 = SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED | SWP_NOACTIVATE
#                 user32.SetWindowPos(self._hwnd, 0, 0, 0, 0, 0, 0x0037)
#                 print(f"[Debug] 设置穿透: {enable} (样式 {new_style:#x})")
#         except Exception as e:
#             print(f"[Debug] 设置穿透失败: {e}")

#     def toggle_lock(self):
#         """切换锁定状态：点击即视为明确意图，直接翻转并清除临时状态"""
#         if not hasattr(self, 'monitoring') or not self.monitoring:
#             print("[Debug] 未在监控中，忽略切换锁定")
#             return

#         # 1. 直接翻转主锁定状态
#         self._is_locked = not self._is_locked

#         # 2. 强制清除临时悬浮状态，避免与新的主状态冲突
#         self._temp_unlock = False
#         self._relock_timer.stop()

#         # 3. 根据新状态启停悬停检测定时器
#         if self._is_locked:
#             self._hover_timer.start()
#         else:
#             self._hover_timer.stop()

#         # 4. 立即应用状态并刷新UI
#         self._apply_lock_state()
#         print(f"[Debug] 手动切换: locked={self._is_locked}, temp={self._temp_unlock}")
        
#     def eventFilter(self, obj, event):
#         """事件过滤器：仅处理拖动逻辑（穿透模式下收不到鼠标事件，符合预期）"""
#         if obj is self:
#             et = event.type()
#             if et == QEvent.MouseButtonPress:
#                 if event.button() == Qt.LeftButton:
#                     if hasattr(self, 'header') and self.header.geometry().contains(event.pos()):
#                         self._drag_active = True
#                         self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
#                         event.accept()
#                         return True
#             elif et == QEvent.MouseMove:
#                 if self._drag_active:
#                     self.move(event.globalPos() - self._drag_pos)
#                     event.accept()
#                     return True
#             elif et == QEvent.MouseButtonRelease:
#                 if event.button() == Qt.LeftButton and self._drag_active:
#                     self._drag_active = False
#                     event.accept()
#                     return True
#         return False

#     def _update_lock_ui(self):
#         """辅助方法：由主窗口调用更新按钮状态"""
#         if hasattr(self, 'btn_lock'):
#             self.btn_lock.setEnabled(getattr(self, 'monitoring', False))
#             if getattr(self, 'monitoring', False):
#                 self.btn_lock.setText("🔒" if self._is_locked else "🔓")
#                 self.btn_lock.setToolTip("已锁定（穿透）" if self._is_locked else "未锁定")
#             else:
#                 self.btn_lock.setText("🔓")
#                 self.btn_lock.setToolTip("未监控时无效")