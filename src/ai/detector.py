# d2r_scene_detector.py
import sys
import cv2
import numpy as np
import onnxruntime as ort
from collections import Counter
import threading
from pathlib import Path
from src.utils.screenshot_api import capture_window

# ⚠️ 类别名称必须与训练时数据集文件夹顺序严格一致
CLASS_NAMES = ["dating", "in_game", "login"]

def get_resource_path(relative_path: str) -> str:
    """兼容 PyInstaller -F 单文件模式的资源路径解析"""
    if getattr(sys, 'frozen', False):
        # -F 模式打包后，文件会解压到系统临时目录，通过 _MEIPASS 访问
        return str(Path(sys._MEIPASS) / relative_path)
    return relative_path

class D2RSceneDetector:
    def __init__(self, model_path: str = "best.onnx"):
        resolved_path = get_resource_path(model_path)
        print(f"[Detector] Loading ONNX model from: {resolved_path}")

        # 初始化 ONNX Runtime 会话（纯 CPU，兼容所有 Windows）
        self.session = ort.InferenceSession(
            resolved_path,
            providers=["CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name
        # 自动获取模型输入尺寸（通常为 640）
        input_shape = self.session.get_inputs()[0].shape
        self.imgsz = input_shape[2] if input_shape[2] else 640

        self._buffer = []
        self._buffer_size = 3
        self._min_conf = 0.45
        self._min_gap = 0.12
        self._lock = threading.Lock()

    def _preprocess(self, img: np.ndarray) -> np.ndarray:
        """YOLOv8 分类模型标准预处理（与训练时完全一致）"""
        # 1. Resize
        img_resized = cv2.resize(img, (self.imgsz, self.imgsz), interpolation=cv2.INTER_LINEAR)
        # 2. BGR -> RGB (OpenCV 默认 BGR，YOLO 默认 RGB)
        img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
        # 3. 归一化到 [0, 1]
        img_norm = img_rgb.astype(np.float32) / 255.0
        # 4. HWC -> CHW -> 1, C, H, W
        return img_norm.transpose(2, 0, 1)[np.newaxis, ...]

    def predict(self, hwnd: int) -> dict:
        with self._lock:
            if not hwnd:
                self._buffer.clear()
                return {"scene": "waiting", "stable": False}

            try:
                img = capture_window(hwnd)
                if img is None:
                    self._buffer.clear()
                    return {"scene": "waiting", "stable": False}

                # ONNX 推理
                input_tensor = self._preprocess(img)
                outputs = self.session.run(None, {self.input_name: input_tensor})
                probs = outputs[0][0]  # 概率分布数组，形状: (num_classes,)

                # 获取 Top1
                top1_idx = int(np.argmax(probs))
                conf = float(probs[top1_idx])

                # 获取 Top2 (完全等效于 ultralytics 的 probs.top5conf[1])
                temp_probs = probs.copy()
                temp_probs[top1_idx] = -1.0
                top2_conf = float(np.max(temp_probs))
                gap = conf - top2_conf

                # 映射类别名
                top1_name = CLASS_NAMES[top1_idx] if top1_idx < len(CLASS_NAMES) else f"unknown_{top1_idx}"

                # 缓冲与投票逻辑（与你原版完全一致）
                if conf < self._min_conf or gap < self._min_gap:
                    self._buffer.append("noise")
                else:
                    self._buffer.append(top1_name)

                if len(self._buffer) > self._buffer_size:
                    self._buffer.pop(0)

                if len(self._buffer) == self._buffer_size:
                    vote = Counter(self._buffer)
                    most_common_scene, count = vote.most_common(1)[0]
                    if count == self._buffer_size and most_common_scene != "noise":
                        return {"scene": most_common_scene, "stable": True, "confidence": conf}

                return {"scene": "waiting", "stable": False}

            except Exception as e:
                self._buffer.clear()
                print(f"[SceneDetector] Inference error: {e}")
                return {"scene": "waiting", "stable": False}