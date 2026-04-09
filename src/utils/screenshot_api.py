import win32gui
import win32ui
import win32con
import win32process
import psutil
import cv2
import numpy as np
import ctypes
import sys
import time
from typing import List, Optional

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

def find_d2r_windows() -> List[int]:
    hwnds = []
    def callback(h, _):
        if win32gui.IsWindowVisible(h) and _is_d2r_window(h):
            l, t, r, b = win32gui.GetWindowRect(h)
            if (r - l) > 300 and (b - t) > 200:
                hwnds.append(h)
        return True
    win32gui.EnumWindows(callback, None)
    hwnds.sort(key=lambda h: (win32gui.GetWindowRect(h)[2]-win32gui.GetWindowRect(h)[0]) *
                         (win32gui.GetWindowRect(h)[3]-win32gui.GetWindowRect(h)[1]), reverse=True)
    return hwnds

def get_best_d2r_window() -> Optional[int]:
    windows = find_d2r_windows()
    return windows[0] if windows else None

def capture_window(hwnd: int) -> Optional[np.ndarray]:
    """直接返回内存 BGR 矩阵，零磁盘 I/O"""
    # ✅ 先检查窗口句柄是否有效
    try:
        # 检查窗口句柄是否有效
        if not hwnd or hwnd == 0:
            return None
        
        # 使用Windows API检查窗口句柄是否有效
        if not ctypes.windll.user32.IsWindow(hwnd):
            return None
        
        # ✅ 检查窗口是否最小化
        if win32gui.IsIconic(hwnd):
            return None

        # ✅ 安全地获取窗口矩形
        l, t, r, b = win32gui.GetWindowRect(hwnd)
        
    except Exception as e:
        # 捕获所有获取窗口信息的异常，避免程序崩溃
        return None
    
    w, h = r - l, b - t
    if w <= 0 or h <= 0: 
        return None

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
        # ✅ 安全清理 GDI 资源（防止创建失败时 NameError）
        try:
            if bmp: win32gui.DeleteObject(bmp.GetHandle())
            if save_dc: save_dc.DeleteDC()
            if mfc_dc: mfc_dc.DeleteDC()
            if hwnd_dc: win32gui.ReleaseDC(hwnd, hwnd_dc)
        except: 
            pass