import cv2
import numpy as np
import os
from typing import Dict, Tuple, Optional
from src.utils.screenshot_api import capture_window

__all__ = ["match_interface", "verify_d2r_screen"]

_template_cache = {}

def _load_template(path: str) -> Optional[np.ndarray]:
    if path not in _template_cache:
        tpl = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if tpl is None: return None
        if tpl.shape[2] == 4:  # 处理透明通道
            tpl = cv2.cvtColor(tpl, cv2.COLOR_BGRA2BGR)
        _template_cache[path] = tpl
    return _template_cache[path]

def match_interface(screenshot: np.ndarray, template_path: str,
                    threshold: float = 0.75, scale_range: Tuple[float, float] = None,
                    debug: bool = False) -> Dict:
    tpl = _load_template(template_path)
    if screenshot is None or tpl is None:
        return {"found": False, "error": "图像加载失败"}

    # 🌑 预处理：转灰度 + 高斯模糊（消除抗锯齿/动态光影噪点）
    img_gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
    img_gray = cv2.GaussianBlur(img_gray, (3, 3), 0)
    
    tpl_gray = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
    tpl_gray = cv2.GaussianBlur(tpl_gray, (3, 3), 0)
    
    h_tpl, w_tpl = tpl_gray.shape
    h_img, w_img = img_gray.shape

    # 📐 智能缩放基准（取短边比例防止越界）
    if scale_range is None:
        base = min(h_img / h_tpl, w_img / w_tpl)
        scale_range = (max(0.2, base * 0.85), min(2.5, base * 1.15))

    best_val, best_loc, best_size = 0.0, None, (w_tpl, h_tpl)
    scales = np.linspace(scale_range[0], scale_range[1], num=12)

    for scale in scales:
        tw, th = int(w_tpl * scale), int(h_tpl * scale)
        if tw < 15 or th < 15 or tw > w_img or th > h_img: continue

        resized = cv2.resize(tpl_gray, (tw, th), interpolation=cv2.INTER_AREA)
        res = cv2.matchTemplate(img_gray, resized, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val > best_val:
            best_val, best_loc, best_size = max_val, max_loc, (tw, th)

    if debug:
        print(f"🔍 匹配日志 | 模板尺寸: {w_tpl}x{h_tpl} | 最佳缩放: {best_size[0]/w_tpl:.2f}x | 最高置信度: {best_val:.3f}")

    if best_val >= threshold:
        x, y = best_loc
        return {
            "found": True, "confidence": round(float(best_val), 4),
            "center": (x + best_size[0]//2, y + best_size[1]//2),
            "bbox": (x, y, x + best_size[0], y + best_size[1])
        }
    return {"found": False, "confidence": round(float(best_val), 4)}

def verify_d2r_screen(hwnd: int, template_path: str, threshold: float = 0.75) -> Dict:
    img = capture_window(hwnd)
    if img is None: return {"found": False, "error": "截图失败"}
    return match_interface(img, template_path, threshold, debug=True)
