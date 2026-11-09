# -*- coding: utf-8 -*-
"""
火车站广播调度系统 - 后端 TCP 通信客户端
对应易语言工程中的"后端通信.e"
协议：JSON over TCP(127.0.0.1:8888)，请求 UTF-8 发送，响应按 GBK 解码，以 \\n 定界
"""
import json
import socket

HOST = "127.0.0.1"
PORT = 8888
RECV_TIMEOUT = 6.0


class BackendClient:
    def __init__(self, host=HOST, port=PORT):
        self.host = host
        self.port = port
        self.sock = None
        self.connected = False

    # ---------- 连接管理 ----------
    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(RECV_TIMEOUT)
            self.sock.connect((self.host, self.port))
            self.connected = True
            return True, "连接成功"
        except Exception as e:
            self.connected = False
            return False, f"连接后端失败: {e}"

    def close(self):
        self.connected = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    # ---------- 底层收发 ----------
    def send_request(self, payload) -> dict:
        """发送请求对象（dict 或 str），返回解析后的响应 dict。失败返回 {Error:{message}}"""
        if not self.connected or not self.sock:
            return {"Error": {"message": "未连接到后端服务，请先启动后端程序"}}
        try:
            if isinstance(payload, str):
                text = payload
            else:
                text = json.dumps(payload, ensure_ascii=False)
            # 后端支持 UTF-8 与 GBK，Python 统一发 UTF-8
            self.sock.sendall(text.encode("utf-8"))
            # 接收直到 \n
            buf = b""
            while b"\n" not in buf:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
            if not buf:
                return {"Error": {"message": "服务器无响应"}}
            raw = buf.rstrip(b"\n").decode("gbk", errors="replace")
            return json.loads(raw)
        except socket.timeout:
            self.connected = False
            return {"Error": {"message": "请求超时，服务器无响应"}}
        except Exception as e:
            self.connected = False
            return {"Error": {"message": f"通信错误: {e}"}}

    # ---------- 响应解析辅助 ----------
    @staticmethod
    def _get_message(resp: dict) -> str:
        """从任意响应类型里取 message 字段"""
        for v in resp.values():
            if isinstance(v, dict):
                if "message" in v:
                    return v["message"]
        return ""

    @staticmethod
    def _is_success(resp: dict) -> bool:
        if "Error" in resp or "error" in resp:
            return False
        # LoginResult/RegisterResult 有 success 字段
        for v in resp.values():
            if isinstance(v, dict) and "success" in v:
                return bool(v["success"])
        # Success 响应
        if "Success" in resp:
            return True
        return True

    # ---------- 业务接口 ----------
    def login(self, username: str, password: str):
        """返回 (成功与否, 消息文本)"""
        resp = self.send_request({"Login": {"username": username, "password": password}})
        msg = self._get_message(resp)
        ok = False
        for v in resp.values():
            if isinstance(v, dict) and "success" in v:
                ok = bool(v["success"])
        return ok, msg or "登录响应解析失败"

    def register(self, username: str, password: str):
        resp = self.send_request({"Register": {"username": username, "password": password}})
        msg = self._get_message(resp)
        ok = False
        for v in resp.values():
            if isinstance(v, dict) and "success" in v:
                ok = bool(v["success"])
        return ok, msg or "注册响应解析失败"

    def add_train(self, train_number, dep, arr, dep_time, platform, status):
        resp = self.send_request({"AddTrain": {
            "train_number": train_number,
            "departure_station": dep,
            "arrival_station": arr,
            "departure_time": dep_time,
            "platform": platform,
            "status": status,
        }})
        return self._is_success(resp), self._get_message(resp)

    def get_trains(self):
        """返回 (成功, 车次列表[dict])"""
        resp = self.send_request("\"GetActiveTrains\"")
        for v in resp.values():
            if isinstance(v, dict) and "trains" in v:
                return True, v["trains"]
        return False, self._get_message(resp)

    def update_train_status(self, train_number, status):
        resp = self.send_request({"UpdateTrainStatus": {
            "train_number": train_number, "status": status}})
        return self._is_success(resp), self._get_message(resp)

    def remove_train(self, train_number):
        resp = self.send_request({"RemoveTrain": {"train_number": train_number}})
        return self._is_success(resp), self._get_message(resp)

    def get_queue_status(self):
        """返回 (size, next_broadcast_str)"""
        resp = self.send_request("\"GetQueueStatus\"")
        for v in resp.values():
            if isinstance(v, dict) and "size" in v:
                return v["size"], v.get("next_broadcast") or ""
        return 0, self._get_message(resp)

    def add_manual_broadcast(self, btype, message, priority=5, audio_file=None):
        resp = self.send_request({"AddManualBroadcast": {
            "broadcast_type": btype,
            "train_info": None,
            "message": message,
            "audio_file": audio_file,
            "priority": priority,
        }})
        return self._is_success(resp), self._get_message(resp)

    def set_auto_mode(self, enabled: bool):
        resp = self.send_request({"SetAutoMode": {"enabled": enabled}})
        return self._is_success(resp), self._get_message(resp)

    def get_system_status(self):
        """返回 (is_running, auto_mode, account_count, queue_size)"""
        resp = self.send_request("\"GetSystemStatus\"")
        for v in resp.values():
            if isinstance(v, dict) and "account_count" in v:
                return (bool(v.get("is_running")),
                        bool(v.get("auto_mode")),
                        v.get("account_count", 0),
                        v.get("queue_size", 0))
        return False, False, 0, 0

    # ---------- 音频 ----------
    def play_audio(self, path):
        resp = self.send_request({"PlayAudio": {"path": path}})
        return self._is_success(resp), self._get_message(resp)

    def stop_audio(self):
        resp = self.send_request("\"StopAudio\"")
        return self._is_success(resp), self._get_message(resp)

    def pause_audio(self):
        resp = self.send_request("\"PauseAudio\"")
        return self._is_success(resp), self._get_message(resp)

    def resume_audio(self):
        resp = self.send_request("\"ResumeAudio\"")
        return self._is_success(resp), self._get_message(resp)

    def set_volume(self, volume):
        resp = self.send_request({"SetVolume": {"volume": float(volume)}})
        return self._is_success(resp), self._get_message(resp)

    def get_audio_status(self):
        """返回 (status_str, current_str)"""
        resp = self.send_request("\"GetAudioStatus\"")
        for v in resp.values():
            if isinstance(v, dict) and "status" in v:
                return v["status"], v.get("current") or ""
        return "unknown", ""

    # ---------- 系统 ----------
    def shutdown(self):
        resp = self.send_request("\"Shutdown\"")
        # 关闭系统后断开连接
        self.close()
        return self._is_success(resp), self._get_message(resp)
