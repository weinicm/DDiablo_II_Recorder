# src/utils/screenshot_utils.py
import os
import cv2
from pathlib import Path
from datetime import datetime
import sys
import traceback

def get_writable_data_path(relative_path: str) -> Path:
    """开发：相对项目根目录；打包后：exe 同级目录"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent / relative_path
    return Path(relative_path)

try:
    import keyboard
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False
    print("[Screenshot] ⚠️  keyboard 库未安装")

class ScreenshotManager:
    def __init__(self, save_dir: str = "./loots"):
        self.save_dir = get_writable_data_path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.hotkey_registered = False
        self._register_hotkey()
    
    def _register_hotkey(self):
        if not HAS_KEYBOARD: return
        try:
            from .config import get_shortcut
            shortcut = get_shortcut("capture_screenshot") or "alt+x"
            keyboard.add_hotkey(shortcut.lower(), self._safe_take_screenshot)
            self.hotkey_registered = True
            print(f"[Screenshot] ✅ 截图快捷键已注册: {shortcut}")
        except Exception as e:
            print(f"[Screenshot] ❌ 快捷键注册失败: {e}")
    
    def _safe_take_screenshot(self):
        try: self._take_screenshot()
        except Exception as e: print(f"[Screenshot] ❌ 截图错误: {e}")

    def _take_screenshot(self):
        try:
            from .window_api import get_best_d2r_window, capture_window
            
            hwnd = get_best_d2r_window()
            if not hwnd: return
            
            image = capture_window(hwnd)
            if image is None or image.size == 0: return

            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"d2r_{timestamp}.png"
            filepath = self.save_dir / filename
            
            # ==========================================
            # 🚀 核心修复：解决 OpenCV 中文路径和 4 通道兼容性问题
            # ==========================================
            
            # 1. 确保目录存在 (防御性编程)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            # 2. 确保图像为 3 通道 (BGR)，去除 Alpha 通道防止 imwrite 报错
            if len(image.shape) == 3 and image.shape[2] == 4:
                image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
            
            # 3. 使用 imencode + tofile 替代 imwrite (完美支持中文路径)
            ret, buf = cv2.imencode('.png', image)
            if ret:
                buf.tofile(str(filepath))
                print(f"[Screenshot] 📸 截图已保存: {filename}")
            else:
                print(f"[Screenshot] ❌ 图像编码失败")
            # ==========================================

        except ImportError as e:
            print(f"[Screenshot] ❌ 无法导入 API: {e}")
        except Exception as e:
            print(f"[Screenshot] ❌ 异常: {e}")

    def manual_screenshot(self):
        try: self._take_screenshot()
        except Exception as e: print(f"[Screenshot] ❌ 手动截图失败: {e}")

    def get_screenshot_count(self) -> int:
        try:
            return len(list(self.save_dir.glob("*.png"))) + len(list(self.save_dir.glob("*.jpg")))
        except Exception: return 0