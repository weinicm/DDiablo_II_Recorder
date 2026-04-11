import os
import json
import re
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional
from enum import Enum


def get_writable_data_path(relative_path: str) -> Path:
    """打包后指向 exe 同级目录，开发环境保持相对路径"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent / relative_path
    return Path(relative_path)


# 定义状态枚举
class SessionPhase(Enum):
    UNKNOWN = "unknown"      # 初始状态
    LOBBY = "lobby"         # 在登录/匹配界面 (login/dating)
    IN_GAME = "in_game"     # 在游戏中
    MINIMIZED = "minimized" # 游戏最小化（暂停计时）

class SceneSessionManager:
    def __init__(self, storage_dir: str = "./data/sessions"):
        self._uid = id(self)
        print(f"[Manager #{self._uid}] 🏗️ 初始化 SessionManager")
        # 🔑 核心修复：调用自适应路径函数，彻底解决打包后临时目录拒绝访问问题
        self.storage_dir = get_writable_data_path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # 注意：已移除 wait_min，只保留 wait_max
        self._filters = {"wait_max": 0, "ingame_min": 0, "ingame_max": 0}
        self._session: Optional[Dict] = None
        self._last_tick: float = time.time()
        
        # 🔑 固定结构模板
        self._round_template = {
            "round_id": 0,
            "wait_time": 0.0,
            "in_game_start": 0.0,
            "wait_start": time.time(),
            "valid": True,
            "paused_duration": 0.0
        }
        self._current_round = self._round_template.copy()
        
        # 🔑 运行时缓存池
        self._runtime_cache: Dict[str, Dict[str, Any]] = {}
        
        # 🔍 严格的状态机
        self._phase: SessionPhase = SessionPhase.UNKNOWN
        self._pause_start_time: float = 0.0
        self._game_pause_start: float = 0.0
        
        # 🔍 场景确认机制
        self._last_stable_scene = None
        self._scene_buffer = []
        self._scene_buffer_size = 3
        self._require_stable_count = 2

    def configure_filters(self, wait_max: float, ingame_min: float, ingame_max: float) -> Dict[str, Any]:
        print(f"[Manager #{self._uid}] ⚙️ 配置过滤器")
        if ingame_min > 0 and ingame_max > 0 and ingame_min >= ingame_max:
            raise ValueError("❌ ingame_min 必须严格小于 ingame_max")
        self._filters = {"wait_max": wait_max, "ingame_min": ingame_min, "ingame_max": ingame_max}
        return {"status": "ok", "message": "📏 过滤阈值已更新"}

    def _sanitize_name(self, name: str) -> str:
        safe = re.sub(r"[^\w\u4e00-\u9fa5\s.\-_]", "", name.strip())
        if not safe: raise ValueError("会话名称格式非法或包含非法字符")
        return safe

    def _sync_runtime_cache(self):
        if self._session:
            name = self._session["name"]
            self._runtime_cache[name] = {
                "runs": self._session["current"]["runs"],
                "wait_time_accum": self._session["current"].get("wait_time_accum", 0.0),
                "saved_duration": self._session["current"]["saved_duration"]
            }

    def _pause_game_timer(self):
        if self._phase == SessionPhase.IN_GAME and self._current_round.get("in_game_start", 0) > 0:
            self._game_pause_start = time.time()
            print(f"[Manager #{self._uid}] ⏸️ 游戏计时已暂停")

    def _resume_game_timer(self):
        if self._game_pause_start > 0:
            pause_duration = time.time() - self._game_pause_start
            self._current_round["paused_duration"] += pause_duration
            self._game_pause_start = 0.0
            print(f"[Manager #{self._uid}] ▶️ 游戏计时已恢复 | 暂停时长: {pause_duration:.1f}s")

    def activate_session(self, session_name: str) -> Dict[str, Any]:
        safe_name = self._sanitize_name(session_name)
        
        if self._session:
            if self._session["name"] == safe_name:
                current_scene = self._session.get("last_scene")
                is_lobby = current_scene in ("login", "dating")
                is_ingame = current_scene == "in_game"
                
                if is_lobby:
                    self._phase = SessionPhase.LOBBY
                    self._current_round["wait_start"] = time.time()
                elif is_ingame:
                    self._phase = SessionPhase.IN_GAME
                    if self._current_round.get("in_game_start", 0) <= 0:
                        self._current_round["in_game_start"] = 0.0
                else:
                    self._phase = SessionPhase.UNKNOWN
                
                self._session["status"] = "active"
                self._session["current"]["resume_time"] = time.time()
                self._last_tick = time.time()
                print(f"[Manager #{self._uid}] 🔄 监控已恢复")
                return {"status": "active", "message": "✅ 监控已恢复", "stats": self.get_stats()}
                
            print(f"[Manager #{self._uid}] ⚠️ 已有活跃会话，建议调用 switch_session()")
            return self.switch_session(safe_name)
            
        return self._setup_session(safe_name, is_switch=False)

    def switch_session(self, session_name: str) -> Dict[str, Any]:
        safe_name = self._sanitize_name(session_name)
        
        if not self._session:
            return self.activate_session(safe_name)
        if self._session["name"] == safe_name:
            return {"status": "already_active", "message": "✅ 当前已是该会话", "stats": self.get_stats()}

        print(f"[Manager #{self._uid}] 🔀 正在切换会话: '{self._session['name']}' -> '{safe_name}'")
        self._sync_runtime_cache()
        self._pause_and_save()
        self._session = None
        self._current_round = self._round_template.copy()
        self._phase = SessionPhase.UNKNOWN
        
        return self._setup_session(safe_name, is_switch=True)

    def _setup_session(self, safe_name: str, is_switch: bool = False) -> Dict[str, Any]:
        file_path = self.storage_dir / f"{safe_name}.json"
        self._session = self._load_or_create(safe_name, file_path)
        
        if safe_name in self._runtime_cache:
            cache = self._runtime_cache[safe_name]
            self._session["current"]["runs"] = cache["runs"]
            self._session["current"]["wait_time_accum"] = cache["wait_time_accum"]
            self._session["current"]["saved_duration"] = cache.get("saved_duration", 0.0)
        else:
            self._runtime_cache[safe_name] = {"runs": 0, "wait_time_accum": 0.0, "saved_duration": 0.0}
            self._session["current"]["runs"] = 0
            self._session["current"]["wait_time_accum"] = 0.0
            self._session["current"]["saved_duration"] = 0.0

        self._session["status"] = "active"
        self._session["current"]["resume_time"] = time.time()
        self._last_tick = time.time()
        
        last_scene = self._session.get("last_scene")
        if last_scene in ("login", "dating"):
            self._phase = SessionPhase.LOBBY
            self._current_round["wait_start"] = time.time()
        elif last_scene == "in_game":
            self._phase = SessionPhase.IN_GAME
            if self._current_round.get("in_game_start", 0) <= 0:
                self._current_round["in_game_start"] = 0.0
        else:
            self._phase = SessionPhase.UNKNOWN
            self._current_round["wait_start"] = time.time()

        msg = f"🔄 已切换至会话 '{safe_name}'" if is_switch else f"✅ 会话 '{safe_name}' 已成功激活"
        print(f"[Manager #{self._uid}] 🚀 {msg}")
        return {"status": "switched" if is_switch else "activated", "message": msg, "stats": self.get_stats()}
    
    def _get_stable_scene(self, detected_scene: str) -> str:
        if detected_scene == "minimized":
            return detected_scene
            
        self._scene_buffer.append(detected_scene)
        if len(self._scene_buffer) > self._scene_buffer_size:
            self._scene_buffer.pop(0)
        
        if len(self._scene_buffer) < self._scene_buffer_size:
            return detected_scene
        
        from collections import Counter
        scene_counter = Counter(self._scene_buffer)
        most_common_scene, count = scene_counter.most_common(1)[0]
        
        if count >= self._require_stable_count:
            if most_common_scene != self._last_stable_scene:
                self._last_stable_scene = most_common_scene
            return most_common_scene
        
        if self._last_stable_scene:
            return self._last_stable_scene
        
        return detected_scene

    def update(self, scene: str) -> Dict[str, Any]:
        if not self._session:
            return {"status": "no_session", "message": "❌ 未激活会话，请先初始化", "stats": self.get_stats()}
        
        stable_scene = self._get_stable_scene(scene)
        last_scene = self._session.get("last_scene")
        now = time.time()
        
        if stable_scene == last_scene and self._phase not in [SessionPhase.UNKNOWN, SessionPhase.MINIMIZED]:
            return {"status": "stable", "message": "", "stats": self.get_stats()}
            
        is_lobby = stable_scene in ("login", "dating")
        is_ingame = stable_scene == "in_game"
        
        result = {"status": "ignored", "message": "🔄 场景切换中", "stats": self.get_stats()}
        
        if stable_scene == "minimized":
            if self._phase == SessionPhase.IN_GAME:
                self._pause_game_timer()
            elif self._phase == SessionPhase.LOBBY:
                pass
            
            if self._session.get("status") == "active": 
                self._pause_and_save()
            
            self._session["last_scene"] = stable_scene
            self._phase = SessionPhase.MINIMIZED
            return {"status": "minimized", "message": "📉 游戏最小化，计时已暂停", "stats": self.get_stats()}
            
        if self._phase == SessionPhase.MINIMIZED:
            pause_duration = now - self._pause_start_time if self._pause_start_time > 0 else 0.0
            self._session["status"] = "active"
            self._session["current"]["resume_time"] = now
            
            if is_ingame:
                if self._current_round.get("in_game_start", 0) > 0:
                    self._resume_game_timer()
                    self._phase = SessionPhase.IN_GAME
                    result["status"] = "resumed_in_game"
                    result["message"] = "▶️ 游戏计时已恢复"
                else:
                    self._phase = SessionPhase.IN_GAME
                    self._current_round["in_game_start"] = 0.0
                    result["status"] = "incomplete_resumed"
                    result["message"] = "⚠️ 恢复游戏，但本局为残缺对局"
                    
            elif is_lobby:
                self._phase = SessionPhase.LOBBY
                self._current_round["wait_start"] = now
                
                if self._current_round.get("in_game_start", 0) > 0:
                    self._settle_round(now)
                    result["status"] = "round_completed_minimized"
                    result["message"] = "🏁 对局已结束（最小化期间）"
                else:
                    result["status"] = "resumed_lobby"
                    result["message"] = "✅ 已恢复至大厅"
                    
            print(f"[Manager #{self._uid}] ▶️ 恢复激活 | 空白期: {pause_duration:.1f}s")
            self._session["last_scene"] = stable_scene
            result["stats"] = self.get_stats()
            return result
            
        if self._session["status"] != "active":
            self._session["last_scene"] = stable_scene
            return {"status": "paused", "message": "⏸️ 会话处于暂停状态", "stats": self.get_stats()}
        
        if is_lobby:
            if self._phase == SessionPhase.IN_GAME and self._current_round.get("in_game_start", 0) > 0:
                self._settle_round(now)
                self._phase = SessionPhase.LOBBY
                self._current_round["wait_start"] = now
                result["status"] = "round_completed"
                result["message"] = "🏁 对局已结束，等待中"
            elif self._phase == SessionPhase.LOBBY:
                self._current_round["wait_start"] = now
                result["status"] = "ready"
                result["message"] = "✅ 已就绪，等待游戏开始"
            elif self._phase == SessionPhase.UNKNOWN:
                self._phase = SessionPhase.LOBBY
                self._current_round["wait_start"] = now
                if not self._session.get("initialized"):
                    self._session["initialized"] = True
                    print(f"[Manager #{self._uid}] ✅ 会话初始化完成，基准场景: {stable_scene}")
                result["status"] = "ready"
                result["message"] = "✅ 已就绪，等待游戏开始"
            else:
                self._phase = SessionPhase.LOBBY
                self._current_round["wait_start"] = now
                result["status"] = "ready"
                result["message"] = "✅ 已就绪，等待游戏开始"
                
        elif is_ingame:
            if self._phase == SessionPhase.LOBBY:
                self._phase = SessionPhase.IN_GAME
                self._start_round(now)
                result["status"] = "round_started"
                result["message"] = "🎮 游戏中，正在计时"
            elif self._phase == SessionPhase.IN_GAME:
                result["status"] = "in_game"
                result["message"] = "🎮 游戏中"
            else:
                self._phase = SessionPhase.IN_GAME
                self._current_round["in_game_start"] = 0.0
                result["status"] = "incomplete"
                result["message"] = "⚠️ 未从大厅进入，本局为残缺对局，已跳过"
                print(f"[Manager #{self._uid}] ⚠️ 跳过残缺对局 | 未从大厅进入游戏")
                
        else:
            result["status"] = "unknown_scene"
            result["message"] = f"❓ 未知场景: {stable_scene}"
        
        self._session["last_scene"] = stable_scene
        result["stats"] = self.get_stats()
        return result

    def _start_round(self, now: float):
        wait_time = now - self._current_round["wait_start"]
        # 🔑 修复：0 表示不限制等待时间
        is_wait_valid = (self._filters["wait_max"] == 0) or (wait_time <= self._filters["wait_max"])

        self._current_round.update({
            "round_id": 0,
            "wait_time": round(wait_time, 2),
            "in_game_start": now,
            "valid": is_wait_valid,
            "paused_duration": 0.0
        })

        if is_wait_valid:
            self._session["current"]["wait_time_accum"] = round(
                self._session["current"]["wait_time_accum"] + wait_time, 2
            )

        self._sync_runtime_cache()
        print(f"[Manager #{self._uid}] 🚀 进入战局 | 等待:{wait_time:.1f}s | 有效:{is_wait_valid}")

    def _settle_round(self, now: float):
        in_game_start = self._current_round.get("in_game_start", 0.0)
        if in_game_start <= 0:
            print(f"[Manager #{self._uid}] ⚠️ 丢弃残缺对局 | 无效的in_game_start")
            self._current_round = self._round_template.copy()
            return
            
        paused_duration = self._current_round.get("paused_duration", 0.0)
        actual_game_time = now - in_game_start - paused_duration
        
        # 🔑 修复：0 表示不限制对应边界
        min_val = self._filters["ingame_min"]
        max_val = self._filters["ingame_max"]
        min_ok = (min_val == 0) or (actual_game_time >= min_val)
        max_ok = (max_val == 0) or (actual_game_time <= max_val)
        is_ig_valid = min_ok and max_ok
        
        round_valid = self._current_round.get("valid", False) and is_ig_valid

        if round_valid:
            new_run_id = int(self._session["historical"]["total_runs"] + 1)
            self._session["historical"]["total_runs"] = new_run_id
            self._session["current"]["runs"] += 1

            total_time = round(self._current_round["wait_time"] + actual_game_time, 2)
            new_round = {
                "round_id": new_run_id,
                "total_time": total_time,
                "in_game_time": round(actual_game_time, 2),
                "wait_time": self._current_round["wait_time"],
                "paused_duration": round(paused_duration, 2)
            }
            self._session["recent_5"].append(new_round)
            if len(self._session["recent_5"]) > 5:
                self._session["recent_5"].pop(0)

            self._session["historical"]["total_duration"] = round(
                self._session["historical"]["total_duration"] + total_time, 2
            )
            self._sync_runtime_cache()
            print(f"[Manager #{self._uid}] 🏁 对局 #{new_run_id} 结算 | 总:{total_time}s | 实际游戏:{actual_game_time:.1f}s | 暂停:{paused_duration:.1f}s")
        else:
            print(f"[Manager #{self._uid}] ⚠️ 对局丢弃 | 等待有效:{self._current_round.get('valid')} | 局内有效:{is_ig_valid}")

        self._current_round = self._round_template.copy()

    def get_stats(self) -> Dict[str, Any]:
        if not self._session:
            return {"error": "未激活会话", "historical": {"total_runs": 0, "total_duration": 0.0},
                    "current_session": {"runs": 0, "duration": 0.0, "wait_time_accum": 0.0},
                    "recent_5_rounds": [], "average_duration": 0.0}
        
        now = time.time()
        base_dur = self._session["current"]["saved_duration"]
        active_dur = now - self._session["current"]["resume_time"] if self._session["status"] == "active" else 0
        current_dur = round(base_dur + active_dur, 2)

        recent = self._session.get("recent_5", [])
        avg_time = round(sum(r.get("total_time", 0) for r in recent) / len(recent), 2) if recent else 0.0
        
        current_round_info = None
        if self._phase == SessionPhase.IN_GAME and self._current_round.get("in_game_start", 0) > 0:
            in_game_start = self._current_round["in_game_start"]
            paused_duration = self._current_round.get("paused_duration", 0.0)
            game_time = now - in_game_start - paused_duration
            current_round_info = {
                "wait_time": self._current_round.get("wait_time", 0),
                "game_time": round(game_time, 2),
                "paused_duration": round(paused_duration, 2),
                "valid": self._current_round.get("valid", False)
            }
        
        return {
            "session_name": self._session["name"],
            "status": self._session["status"],
            "phase": self._phase.value,
            "historical": self._session["historical"].copy(),
            "current_session": {
                "runs": self._session["current"]["runs"],
                "duration": current_dur,
                "wait_time_accum": round(self._session["current"]["wait_time_accum"], 2)
            },
            "recent_5_rounds": [r.copy() for r in recent],
            "average_duration": avg_time,
            "current_round": current_round_info
        }

    def delete_round(self, round_id: int) -> Dict[str, Any]:
        print(f"[Manager #{self._uid}] 🗑️ delete_round 请求: ID={round_id}")
        if not self._session:
            return {"status": "error", "message": "无活跃会话"}
        
        target_idx = -1
        found_id = None
        for i, r in enumerate(self._session["recent_5"]):
            if int(r.get("round_id", -1)) == int(round_id):
                target_idx = i
                found_id = r.get("round_id")
                break

        if target_idx == -1:
            return {"status": "error", "message": f"未找到对局 #{round_id}"}

        target = self._session["recent_5"].pop(target_idx)
        self._session["historical"]["total_runs"] = max(0, self._session["historical"]["total_runs"] - 1)
        self._session["historical"]["total_duration"] = max(0.0, round(self._session["historical"]["total_duration"] - target["total_time"], 2))
        self._session["current"]["runs"] = max(0, self._session["current"]["runs"] - 1)
        self._session["current"]["wait_time_accum"] = max(0.0, round(self._session["current"]["wait_time_accum"] - target["wait_time"], 2))
        
        self._sync_runtime_cache()
        self.save()
        return {"status": "ok", "message": f"✅ 已删除对局 #{found_id} 并同步统计", "stats": self.get_stats()}

    def save(self):
        if not self._session: return
        if self._session["status"] == "active":
            now = time.time()
            base = self._session["current"]["saved_duration"]
            active = now - self._session["current"]["resume_time"]
            self._session["current"]["saved_duration"] = round(base + active, 2)
            self._session["current"]["resume_time"] = now

        file_path = self.storage_dir / f"{self._session['name']}.json"
        export_current = {
            "runs": 0,
            "saved_duration": self._session["current"]["saved_duration"],
            "resume_time": self._session["current"]["resume_time"],
            "wait_time_accum": 0.0,
            "duration": self._session["current"]["duration"]
        }
        export_data = {
            "name": self._session["name"], "created_at": self._session.get("created_at"),
            "filters": self._filters, "historical": self._session["historical"],
            "current": export_current, "initialized": self._session.get("initialized"),
            "last_scene": self._session.get("last_scene")
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

    def pause_and_save(self): self._pause_and_save()
    def _pause_and_save(self):
        if not self._session or self._session.get("status") == "paused": return
        base_dur = self._session["current"]["saved_duration"]
        active_dur = time.time() - self._session["current"]["resume_time"]
        self._session["current"]["saved_duration"] = round(base_dur + active_dur, 2)
        self._session["status"] = "paused"
        self._pause_start_time = time.time()
        self.save()

    def get_recent_rounds(self, limit: int = 5):
        if not self._session: return []
        recent = self._session.get("recent_5", [])
        return recent[-limit:] if len(recent) > limit else recent

    def _load_or_create(self, name: str, file_path: Path) -> Dict:
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["recent_5"] = []
            if "filters" in data: 
                filters = data["filters"]
                if "wait_min" in filters:
                    del filters["wait_min"]
                self._filters = filters
            data["current"].setdefault("duration", 0.0)
            return data
        return self._create_template(name)

    def _create_template(self, name: str) -> Dict:
        return {
            "name": name, "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "active", "initialized": False, "last_scene": None,
            "filters": self._filters.copy(),
            "historical": {"total_runs": 0, "total_duration": 0.0},
            "current": {"runs": 0, "saved_duration": 0.0, "resume_time": time.time(), 
                        "wait_time_accum": 0.0, "duration": 0.0},
            "recent_5": []
        }