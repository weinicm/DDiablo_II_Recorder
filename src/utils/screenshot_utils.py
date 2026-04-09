# src/utils/screenshot_utils.py
"""
独立的截图工具
功能：注册快捷键，截图保存到指定目录
"""
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

# 尝试导入keyboard库
try:
    import keyboard
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False
    print("[Screenshot] ⚠️  keyboard库未安装，截图快捷键功能不可用")

class ScreenshotManager:
    """最简单的截图管理器"""
    
    def __init__(self, save_dir: str = "./loots"):
        """
        初始化截图管理器
        
        Args:
            save_dir: 截图保存目录
        """
        self.save_dir = get_writable_data_path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.hotkey_registered = False
        
        # 尝试注册快捷键
        self._register_hotkey()
    
    def _register_hotkey(self):
        """注册截图快捷键"""
        if not HAS_KEYBOARD:
            return
        
        try:
            # 导入配置
            from .config import get_shortcut
            
            # 获取快捷键配置
            shortcut = get_shortcut("capture_screenshot")
            if not shortcut:
                shortcut = "ctrl+shift+s"  # 默认值
            
            # 转换为keyboard库需要的格式
            keyboard_shortcut = shortcut.lower()
            
            # 注册快捷键
            keyboard.add_hotkey(keyboard_shortcut, self._safe_take_screenshot)
            self.hotkey_registered = True
            
            print(f"[Screenshot] ✅ 截图快捷键已注册: {shortcut}")
            
        except ImportError as e:
            print(f"[Screenshot] ❌ 无法导入配置模块: {e}")
        except Exception as e:
            print(f"[Screenshot] ❌ 注册截图快捷键失败: {e}")
            traceback.print_exc()
    
    def _safe_take_screenshot(self):
        """安全的截图回调函数，捕获所有异常"""
        try:
            self._take_screenshot()
        except Exception as e:
            error_msg = str(e)
            # 如果是窗口句柄无效的错误，不打印错误信息
            if "GetWindowRect" not in error_msg or "无效的窗口句柄" not in error_msg:
                print(f"[Screenshot] ❌ 截图过程中发生错误: {e}")
    
    def _take_screenshot(self):
        """截图回调函数"""
        try:
            # 动态导入窗口API
            from .window_api import get_best_d2r_window, capture_window
            
            # 获取窗口
            hwnd = get_best_d2r_window()
            if not hwnd:
                # 这是正常情况，游戏窗口没找到
                return
            
            # 截图
            image = capture_window(hwnd)
            if image is None or image.size == 0:
                # 这是正常情况，截图失败
                return
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"d2r_{timestamp}.png"
            filepath = self.save_dir / filename
            
            # 保存图片
            success = cv2.imwrite(str(filepath), image)
            if success:
                print(f"[Screenshot] 📸 截图已保存: {filename}")
            else:
                print(f"[Screenshot] ❌ 保存截图失败")
                
        except ImportError as e:
            print(f"[Screenshot] ❌ 无法导入窗口API: {e}")
        except Exception as e:
            # 重新抛出异常，由调用者处理
            raise
    
    def manual_screenshot(self):
        """手动触发截图（可以绑定到UI按钮）"""
        try:
            self._take_screenshot()
        except Exception as e:
            error_msg = str(e)
            # 如果是窗口句柄无效的错误，不打印错误信息
            if "GetWindowRect" not in error_msg or "无效的窗口句柄" not in error_msg:
                print(f"[Screenshot] ❌ 截图过程中发生错误: {e}")
    
    def get_screenshot_count(self) -> int:
        """获取已保存的截图数量"""
        try:
            png_files = list(self.save_dir.glob("*.png"))
            jpg_files = list(self.save_dir.glob("*.jpg"))
            return len(png_files) + len(jpg_files)
        except Exception:
            return 0