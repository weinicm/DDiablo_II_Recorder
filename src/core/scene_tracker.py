# scene_tracker.py
import time

class SceneDurationTracker:
    def __init__(self):
        self.current_scene = None
        self.enter_time = None

    def update(self, scene: str) -> dict | None:
        now = time.time()
        if self.current_scene is None:
            self.current_scene = scene
            self.enter_time = now
            return None
        if scene == self.current_scene:
            return None
            
        duration = now - self.enter_time
        event = {
            "from": self.current_scene,
            "to": scene,
            "duration": round(duration, 2)
        }
        self.current_scene = scene
        self.enter_time = now
        return event
