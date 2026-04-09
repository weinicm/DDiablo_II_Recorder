import win32gui
import win32ui
import win32con
import win32process
import psutil
import cv2
import numpy as np
import ctypes
import time
from typing import List, Optional

# ✅ 确保导出 capture_window
__all__ = ["enable_dpi_awareness", "find_d2r_windows", "get_best_d2r_window", "capture_window"]

_D2R_PROCESS_NAME = "D2R.exe"
_D2R_TITLE_KEYWORDS = ["diablo ii: resurrected", "diablo® ii: resurrected™", "diablo ii"]

def enable_dpi_awareness() -> None:
    try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception: ctypes.windll.user32.SetProcessDPIAware()

def _is_d2r_window(hwnd: int) -> bool:
    title = win32gui.GetWindowText(hwnd).lower()
    if not any(kw in title for kw in _D2R_TITLE_KEYWORDS): return False
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return psutil.Process(pid).name().lower() == _D2R_PROCESS_NAME.lower()
    except Exception: return False

import win32gui
from typing import List, Tuple

def find_d2r_windows() -> List[int]:
    # 缓存 (hwnd, 面积)，避免二次查询
    hwnds_with_area: List[Tuple[int, int]] = []

    def callback(h, _):
        try:
            # 1. 先验证句柄是否依然有效
            if not win32gui.IsWindow(h):
                return True
            # 2. 过滤不可见窗口
            if not win32gui.IsWindowVisible(h):
                return True
            # 3. 业务过滤
            if not _is_d2r_window(h):
                return True

            # 4. 安全获取尺寸并计算面积
            l, t, r, b = win32gui.GetWindowRect(h)
            w, h_size = r - l, b - t
            if w > 300 and h_size > 200:
                hwnds_with_area.append((h, w * h_size))
        except Exception:
            # 窗口可能在枚举过程中瞬间关闭，静默跳过即可
            pass
        return True

    win32gui.EnumWindows(callback, None)
    
    # 5. 使用缓存的面积排序，彻底避免重复调用 Win32 API
    hwnds_with_area.sort(key=lambda x: x[1], reverse=True)
    return [h for h, _ in hwnds_with_area]


def get_best_d2r_window() -> Optional[int]:
    windows = find_d2r_windows()
    return windows[0] if windows else None

def capture_window(hwnd: int) -> Optional[np.ndarray]:
    """直接返回内存 BGR 矩阵，零磁盘 I/O。最小化时返回 None"""
    if win32gui.IsIconic(hwnd):
        return None  # ✅ 关键：不强制恢复窗口，直接返回 None 触发暂停逻辑

    l, t, r, b = win32gui.GetWindowRect(hwnd)
    w, h = r - l, b - t
    if w <= 0 or h <= 0: return None

    hwnd_dc = mfc_dc = save_dc = bmp = None
    try:
        hwnd_dc = win32gui.GetWindowDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(mfc_dc, w, h)
        save_dc.SelectObject(bmp)

        if ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2) == 0:
            return None

        img = np.frombuffer(bmp.GetBitmapBits(True), dtype=np.uint8).reshape((h, w, 4))
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    except Exception:
        return None
    finally:
        try:
            if bmp: win32gui.DeleteObject(bmp.GetHandle())
            if save_dc: save_dc.DeleteDC()
            if mfc_dc: mfc_dc.DeleteDC()
            if hwnd_dc: win32gui.ReleaseDC(hwnd, hwnd_dc)
        except: pass
