# src/ui/loots.py
"""
独立的Loots截图模块
功能：截图时添加当前对局信息
"""
import os
import sys  # 🔑 新增：用于检测打包状态
import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
import traceback
import threading
import atexit
import time

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("[Loots] ⚠️  PIL库未安装，无法添加文字水印")

# 尝试导入keyboard库
try:
    import keyboard
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False
    print("[Loots] ⚠️  keyboard库未安装，截图快捷键功能不可用")

class LootScreenshot:
    """Loots截图工具，只在游戏中对局时添加对局信息"""
    
    def __init__(self, session_manager=None, save_dir: str = "./Loot"):
        """
        初始化Loots截图工具
        
        Args:
            session_manager: SceneSessionManager实例，用于获取对局信息
            save_dir: 截图保存目录
        """
        self.session_manager = session_manager
        
        # 🔑 核心修复：动态解析保存目录。打包后强制指向 exe 同级目录，彻底解决 WinError 5
        if getattr(sys, 'frozen', False):
            # 打包后：指向 exe 所在目录下的 Loot 文件夹（用户完全可读写）
            self.save_dir = Path(sys.executable).parent / "Loot"
        else:
            # 开发环境：保持原有相对路径
            self.save_dir = Path(save_dir)
            
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.hotkey_registered = False
        
        # 初始化字体
        self.title_font = None
        self.info_font = None
        self._init_font()
        
        # 注册退出清理
        atexit.register(self.cleanup)
        
        print(f"[Loots] ✅ 初始化完成，保存目录: {self.save_dir}")
        if self.session_manager:
            print(f"[Loots] ✅ SessionManager已注入")
        else:
            print(f"[Loots] ⚠️  未注入SessionManager，截图将不包含对局信息")
    
    def _init_font(self):
        """初始化字体"""
        if not HAS_PIL:
            return
        
        try:
            # 尝试加载中文字体
            font_paths = [
                "C:/Windows/Fonts/msyhbd.ttc",  # 微软雅黑 Bold
                "C:/Windows/Fonts/msyh.ttc",    # 微软雅黑
                "C:/Windows/Fonts/simhei.ttf",  # 黑体
                "/System/Library/Fonts/PingFang.ttc",  # macOS
                "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",  # Linux
            ]
            
            for font_path in font_paths:
                if os.path.exists(font_path):
                    self.title_font = ImageFont.truetype(font_path, 45)
                    self.info_font = ImageFont.truetype(font_path, 35)
                    print(f"[Loots] ✅ 字体加载成功: {font_path}")
                    return
            
            self.title_font = ImageFont.load_default()
            self.info_font = ImageFont.load_default()
            print(f"[Loots] ⚠️  使用默认字体，中文可能显示异常")
            
        except Exception as e:
            print(f"[Loots] ❌ 字体加载失败: {e}")
            self.title_font = ImageFont.load_default()
            self.info_font = ImageFont.load_default()
    
    def register_hotkey(self, hotkey: str = None):
        """注册截图快捷键"""
        if not HAS_KEYBOARD:
            print(f"[Loots] ❌ keyboard库未安装，无法注册全局热键")
            return False
        
        try:
            if not hotkey:
                try:
                    from ..utils.config import get_shortcut
                    shortcut = get_shortcut("capture_screenshot")
                    if not shortcut:
                        shortcut = "ctrl+shift+s"
                except ImportError:
                    shortcut = "ctrl+shift+s"
            else:
                shortcut = hotkey
            
            self.unregister_hotkey(shortcut)
            keyboard_shortcut = shortcut.lower()
            
            def safe_capture():
                try:
                    thread = threading.Thread(target=self.capture_with_info, daemon=True)
                    thread.start()
                except Exception as e:
                    print(f"[Loots] ❌ 截图线程启动失败: {e}")
            
            keyboard.add_hotkey(keyboard_shortcut, safe_capture, suppress=True)
            self.hotkey_registered = True
            print(f"[Loots] ✅ 全局截图快捷键已注册: {shortcut}")
            return True
            
        except Exception as e:
            print(f"[Loots] ❌ 注册快捷键失败: {e}")
            traceback.print_exc()
            return False
    
    def unregister_hotkey(self, hotkey: str = None):
        """取消注册快捷键"""
        if not HAS_KEYBOARD:
            return
        
        try:
            if hotkey:
                keyboard.remove_hotkey(hotkey.lower())
            else:
                keyboard.unhook_all_hotkeys()
            self.hotkey_registered = False
            print(f"[Loots] ✅ 已取消快捷键注册: {hotkey if hotkey else '所有'}")
        except Exception as e:
            print(f"[Loots] ❌ 取消快捷键注册失败: {e}")
    
    def _get_game_info(self) -> Dict[str, Any]:
        """获取当前对局信息"""
        if not self.session_manager:
            return {}
        
        try:
            stats = self.session_manager.get_stats()
            if not stats:
                return {}
            
            historical = stats.get("historical", {})
            current_round = getattr(self.session_manager, '_current_round', {})
            total_runs = historical.get("total_runs", 0)
            in_game_start = current_round.get("in_game_start", 0)
            is_in_game = in_game_start > 0
            
            if not is_in_game:
                return {}
            
            current_round_number = total_runs + 1
            return {
                "session_name": stats.get("session_name", "未知场景"),
                "total_runs": total_runs,
                "current_round_number": current_round_number,
                "is_in_game": is_in_game,
            }
        except Exception as e:
            print(f"[Loots] ❌ 获取对局信息失败: {e}")
            return {}
    
    def _add_text_to_image(self, image: np.ndarray, info: Dict[str, Any]) -> np.ndarray:
        """将对局信息添加到图片上"""
        if not HAS_PIL or self.title_font is None or not info.get("is_in_game", False):
            return image
        
        try:
            if len(image.shape) == 3 and image.shape[2] == 3:
                pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            else:
                pil_image = Image.fromarray(image)
            
            draw = ImageDraw.Draw(pil_image)
            img_width, img_height = pil_image.size
            text_color = (255, 255, 0)
            bg_color = (0, 0, 0, 200)
            
            lines = []
            lines.append("🎉 恭喜出货！")
            lines.append(f"场景: {info.get('session_name', '未知')}")
            lines.append(f"对局: 第{info.get('current_round_number', 0)}局")
            
            margin_top = 30
            margin_right = 30
            line_spacing = 15
            bg_padding = 15
            
            line_heights = []
            line_widths = []
            for i, line in enumerate(lines):
                font = self.title_font if i == 0 else self.info_font
                bbox = draw.textbbox((0, 0), line, font=font)
                line_widths.append(bbox[2] - bbox[0])
                line_heights.append(bbox[3] - bbox[1])
            
            total_text_height = sum(line_heights) + (len(lines) - 1) * line_spacing
            max_text_width = max(line_widths)
            
            bg_left = img_width - max_text_width - margin_right - bg_padding * 2
            bg_top = margin_top - bg_padding
            bg_right = img_width - margin_right + bg_padding
            bg_bottom = margin_top + total_text_height + bg_padding
            
            draw.rectangle([(bg_left, bg_top), (bg_right, bg_bottom)], fill=bg_color)
            
            y_current = margin_top
            for i, line in enumerate(lines):
                font = self.title_font if i == 0 else self.info_font
                text_width = line_widths[i]
                x = img_width - margin_right - text_width
                
                shadow_offset = 2
                shadow_color = (0, 0, 0)
                for dx, dy in [(-shadow_offset, 0), (shadow_offset, 0),
                               (0, -shadow_offset), (0, shadow_offset),
                               (-shadow_offset, -shadow_offset), (shadow_offset, shadow_offset),
                               (-shadow_offset, shadow_offset), (shadow_offset, -shadow_offset)]:
                    draw.text((x + dx, y_current + dy), line, font=font, fill=shadow_color)
                
                draw.text((x, y_current), line, font=font, fill=text_color)
                y_current += line_heights[i] + line_spacing
            
            return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        except Exception as e:
            print(f"[Loots] ❌ 添加文字失败: {e}")
            return image
    
    def capture_with_info(self) -> Optional[str]:
        """截图并添加对局信息"""
        try:
            from ..utils.window_api import get_best_d2r_window, capture_window
            import win32gui
            
            hwnd = get_best_d2r_window()
            if not hwnd:
                print("[Loots] ❌ 未找到游戏窗口")
                return None
                
            if not win32gui.IsWindow(hwnd):
                print("[Loots] ⚠️ 窗口已关闭/句柄失效，跳过截图")
                return None
                
            image = capture_window(hwnd)
            if image is None or image.size == 0:
                print("[Loots] ❌ 截图失败：无法捕获画面")
                return None
            
            game_info = self._get_game_info()
            is_in_game = game_info.get("is_in_game", False)
            
            if is_in_game and HAS_PIL and self.title_font:
                image = self._add_text_to_image(image, game_info)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if is_in_game:
                round_number = game_info.get("current_round_number", 0)
                filename = f"loot_第{round_number}局_{timestamp}.png"
            else:
                filename = f"capture_{timestamp}.png"
            
            filepath = self.save_dir / filename
            
            # ==========================================
            # 🚀 核心修复：解决 OpenCV 中文路径和 4 通道兼容性问题
            # ==========================================
            # 1. 确保目录存在（防御性编程）
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            # 2. 确保图像为 3 通道 (BGR)，去除 Alpha 通道防止编码报错
            if len(image.shape) == 3 and image.shape[2] == 4:
                image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
            
            # 3. 使用 imencode + tofile 替代 imwrite (完美支持中文路径/特殊字符)
            ret, buf = cv2.imencode('.png', image)
            if ret:
                buf.tofile(str(filepath))
                if is_in_game:
                    print(f"[Loots] 📸 战利品截图已保存: {filename}")
                else:
                    print(f"[Loots] 📸 普通截图已保存: {filename}")
                time.sleep(0.3)
                return str(filepath)
            else:
                print(f"[Loots] ❌ 图像编码失败")
                return None
            # ==========================================
                
        except ImportError as e:
            print(f"[Loots] ❌ 无法导入窗口API: {e}")
        except Exception as e:
            print(f"[Loots] ❌ 截图过程中发生错误: {e}")
            traceback.print_exc()
        return None
    
    def manual_capture(self) -> Optional[str]:
        """手动触发截图"""
        return self.capture_with_info()
    
    def get_screenshot_count(self) -> int:
        """获取已保存的截图数量"""
        try:
            return len(list(self.save_dir.glob("*.png"))) + len(list(self.save_dir.glob("*.jpg")))
        except Exception:
            return 0
    
    def cleanup(self):
        """清理资源"""
        if HAS_KEYBOARD and self.hotkey_registered:
            try:
                self.unregister_hotkey()
            except Exception as e:
                print(f"[Loots] ❌ 清理键盘钩子失败: {e}")