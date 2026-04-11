# d2r_scene_detector.py
import sys
import cv2
import numpy as np
import onnxruntime as ort
from collections import Counter
import threading
from pathlib import Path
import ast
from src.utils.screenshot_api import capture_window

def get_resource_path(relative_path: str) -> str:
    """兼容 PyInstaller -F 单文件模式的资源路径解析"""
    if getattr(sys, 'frozen', False):
        return str(Path(sys._MEIPASS) / relative_path)
    return relative_path

class D2RSceneDetector:
    def __init__(self, model_path: str = "best.onnx"):
        resolved_path = get_resource_path(model_path)
        print(f"[Detector] Loading ONNX model from: {resolved_path}")

        # 初始化 ONNX Runtime 会话（纯 CPU）
        self.session = ort.InferenceSession(
            resolved_path,
            providers=["CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name
        input_shape = self.session.get_inputs()[0].shape
        self.imgsz = input_shape[2] if input_shape[2] else 640

        # 🌟 自动从 ONNX 元数据读取类别名称（无需手动维护）
        meta = self.session.get_modelmeta().custom_metadata_map
        names_raw = meta.get('names', '[]')
        try:
            names_parsed = ast.literal_eval(names_raw)
            if isinstance(names_parsed, dict):
                # 兼容 dict 格式 {0: 'dating', 1: 'in_game'}
                self.class_names = [
                    names_parsed.get(i, names_parsed.get(str(i), f"cls_{i}")) 
                    for i in range(len(names_parsed))
                ]
            else:
                # 兼容 list 格式 ['dating', 'in_game']
                self.class_names = list(names_parsed)
        except Exception as e:
            print(f"[⚠️] 自动解析类别失败，使用默认兜底: {e}")
            self.class_names = ["dating", "in_game", "login"]
            
        print(f"[Detector] ✅ 已加载 {len(self.class_names)} 个场景类别: {self.class_names}")

        self._buffer = []
        self._buffer_size = 3
        self._min_conf = 0.45
        self._min_gap = 0.12
        self._lock = threading.Lock()

    def _preprocess(self, img: np.ndarray) -> np.ndarray:
        """YOLOv8 分类模型标准预处理"""
        img_resized = cv2.resize(img, (self.imgsz, self.imgsz), interpolation=cv2.INTER_LINEAR)
        img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
        img_norm = img_rgb.astype(np.float32) / 255.0
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
                probs = outputs[0][0]  # 概率分布数组

                # 获取 Top1
                top1_idx = int(np.argmax(probs))
                conf = float(probs[top1_idx])

                # 获取 Top2 置信度
                temp_probs = probs.copy()
                temp_probs[top1_idx] = -1.0
                top2_conf = float(np.max(temp_probs))
                gap = conf - top2_conf

                # 安全映射类别名
                top1_name = self.class_names[top1_idx] if top1_idx < len(self.class_names) else f"unknown_{top1_idx}"

                # 缓冲与投票逻辑（保持原版逻辑）
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