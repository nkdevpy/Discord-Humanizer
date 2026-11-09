import time
import base64
import hashlib
import re
import os
import json
import uuid
import random
import threading
import importlib
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Optional, Dict, Any, List
from pathlib import Path
from io import BytesIO
from urllib.parse import urlparse, quote

import primp
import websocket

pil_img_module = importlib.import_module("PIL.Image")
resample_filter = getattr(pil_img_module.Resampling, "LANCZOS")

os.system("")

script_dir = Path(__file__).parent
data_dir = script_dir / "data"
input_dir = script_dir / "input"
output_dir = script_dir / "output"
avatars_dir = script_dir / "avatars" if (script_dir / "avatars").exists() else script_dir / "avatar"
banners_dir = script_dir / "banners"

tokens_file = input_dir / "tokens.txt"
proxies_file = input_dir / "proxies.txt"
bios_file = data_dir / "bios.txt"
names_file = data_dir / "names.txt"
pronouns_file = data_dir / "pronouns.txt"
success_file = output_dir / "success.txt"
failed_file = output_dir / "failed.txt"

clr_reset = "\033[0m"
clr_bold = "\033[1m"
clr_dim = "\033[2m"
clr_red = "\033[38;5;196m"
clr_green = "\033[38;5;46m"
clr_yellow = "\033[38;5;226m"
clr_cyan = "\033[38;5;51m"
clr_white = "\033[38;5;255m"
clr_gray = "\033[38;5;244m"
clr_purple = "\033[38;5;141m"
clr_light_blue = "\033[38;5;153m"
clr_light_cyan = "\033[38;5;123m"

default_cooldown = 0.5
discordapi = "https://discord.com/api/v9"
discordgateway = "wss://gateway.discord.gg/?encoding=json&v=9"
discord_avatar_max_bytes = 1000000

build_number = 520031
discord_client_version = "1.0.9186"
electron_version = "34.5.1"
chrome_version = "146.0.0.0"
chrome_ua = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36"

hypesquad_houses = {
    1: "Bravery",
    2: "Brilliance",
    3: "Balance"
}

def set_console_title(title: str):
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleTitleW(title)
        except Exception:
            os.system(f"title {title}")
    else:
        print(f"\033]0;{title}\007", end="", flush=True)

def load_config():
    default_config = {
        "max_threads": 5,
        "avatar_dimension": 256,
        "max_avatar_cache": 100,
        "update_display_name": False,
        "update_bio": True,
        "update_pronouns": True,
        "update_avatar": True,
        "update_hypesquad": True,
        "proxy": True,
        "retry_limit": 1
    }
    config_path = script_dir / "config.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for key, val in data.items():
                    default_config[key] = val
        except Exception as e:
            print(f"{clr_yellow}[WARN] Could not load config.json ({e}). Using defaults.{clr_reset}")
    return default_config

config = load_config()

max_threads = config.get("max_threads", 3)
avatar_dimension = config.get("avatar_dimension", 256)
max_avatar_cache = config.get("max_avatar_cache", 100)
update_display_name = config.get("update_display_name", False)
update_bio = config.get("update_bio", True)
update_pronouns = config.get("update_pronouns", True)
update_avatar = config.get("update_avatar", True)
update_hypesquad = config.get("update_hypesquad", True)
retry_limit = config.get("retry_limit", 1)
use_proxy = config.get("proxy", True)

cf_cookies_cache = None
cf_cookies_cache_time = 0.0
cf_fingerprint_cache = None
cf_cookies_lock = threading.Lock()

def get_discord_cf_cookies_and_fingerprint(proxy_arg: Optional[str] = None) -> tuple:
    """
    Fetch live Cloudflare cookies (__dcfduid, __sdcfduid, _cfuvid, locale) and X-Fingerprint
    from Discord API experiments endpoint via primp (Cwelium methodology).
    Cached for 10 minutes to minimize network roundtrips.
    """
    global cf_cookies_cache, cf_cookies_cache_time, cf_fingerprint_cache
    now = time.time()
    with cf_cookies_lock:
        if cf_cookies_cache and (now - cf_cookies_cache_time) < 600:
            return cf_cookies_cache, cf_fingerprint_cache or ""

    fallback_cookies = (
        "__dcfduid=62f9e16000a211ef8089eda5bffbf7f9; "
        "__sdcfduid=62f9e16100a211ef8089eda5bffbf7f98e904ba04346eacdf57ee4af97bdd94e4c16f7df1db5132bea9132dd26b21a2a; "
        "__cfruid=a2ccd7637937e6a41e6888bdb6e8225cd0a6f8e0-1714045775; "
        "_cfuvid=s_CLUzmUvmiXyXPSv91CzlxP00pxRJpqEhuUgJql85Y-1714045775095-0.0.1.1-604800000; locale=en-US"
    )
    fallback_fingerprint = ""

    try:
        exp_client = primp.Client(verify=False, proxy=proxy_arg)
        exp_res = exp_client.get("https://discord.com/api/v9/experiments", timeout=12)
        cookies_list = [f"{k}={v}" for k, v in exp_res.cookies.items()]
        if cookies_list:
            cookie_str = "; ".join(cookies_list) + "; locale=en-US"
        else:
            cookie_str = fallback_cookies

        fp = ""
        try:
            fp = exp_res.json().get("fingerprint", "")
        except Exception:
            fp = fallback_fingerprint

        with cf_cookies_lock:
            cf_cookies_cache = cookie_str
            cf_fingerprint_cache = fp
            cf_cookies_cache_time = now
        return cookie_str, fp
    except Exception:
        return fallback_cookies, fallback_fingerprint

def generate_super_properties(launch_id: str, signature: str, heartbeat_id: str) -> str:
    props = {
        "os": "Windows",
        "browser": "Chrome",
        "device": "",
        "system_locale": "en-US",
        "has_client_mods": False,
        "browser_user_agent": chrome_ua,
        "browser_version": chrome_version,
        "os_version": "10",
        "referrer": "https://discord.com/channels/@me",
        "referring_domain": "discord.com",
        "referrer_current": "",
        "referring_domain_current": "",
        "release_channel": "stable",
        "client_build_number": build_number,
        "client_event_source": None,
        "client_launch_id": launch_id,
        "launch_signature": signature,
        "client_heartbeat_session_id": heartbeat_id,
        "client_app_state": "focused",
    }
    raw = json.dumps(props, separators=(",", ":"))
    return base64.b64encode(raw.encode("utf-8")).decode("utf-8")

stats = {
    "total": 0,
    "success": 0,
    "failed": 0,
    "start_time": time.time()
}
stats_lock = threading.Lock()
file_lock = threading.Lock()
print_lock = threading.Lock()

account_cooldown_lock = threading.Lock()
last_account_start_time = 0.0

def wait_account_cooldown(cooldown_seconds: float = default_cooldown):
    global last_account_start_time
    with account_cooldown_lock:
        now = time.time()
        elapsed = now - last_account_start_time
        if elapsed < cooldown_seconds:
            time.sleep(cooldown_seconds - elapsed)
        last_account_start_time = time.time()

class ProxyManager:
    def __init__(self, proxies: List[str]):
        self.proxies = proxies
        self.lock = threading.Lock()
        self.index = 0
        self.bad_proxies = set()
        self.in_use = set()

    def get_proxy(self) -> Optional[str]:
        with self.lock:
            if not self.proxies:
                return None
            attempts = 0
            while attempts < len(self.proxies):
                proxy = self.proxies[self.index]
                self.index = (self.index + 1) % len(self.proxies)
                if proxy in self.bad_proxies or proxy in self.in_use:
                    attempts += 1
                    continue
                self.in_use.add(proxy)
                return proxy
            for _ in range(len(self.proxies)):
                proxy = self.proxies[self.index]
                self.index = (self.index + 1) % len(self.proxies)
                if proxy not in self.bad_proxies:
                    return proxy
            return None

    def release_proxy(self, proxy: str):
        with self.lock:
            if proxy:
                self.in_use.discard(proxy)

    def mark_bad(self, proxy: str):
        with self.lock:
            if proxy:
                self.bad_proxies.add(proxy)

    def get_stats(self) -> Dict[str, int]:
        with self.lock:
            return {
                "total": len(self.proxies),
                "bad": len(self.bad_proxies),
                "active": len(self.proxies) - len(self.bad_proxies)
            }

proxy_manager: Optional[ProxyManager] = None

def get_timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S")

def log(log_type: str, token: str, message: str):
    timestamp = get_timestamp()
    masked = mask_token(token)
    with print_lock:
        ts = f"{clr_gray}[{timestamp}]{clr_reset}"
        tok = f"{clr_gray}[{clr_reset}Token : {clr_cyan}{masked}{clr_reset}{clr_gray}]{clr_reset}"
        type_upper = log_type.upper()
        if type_upper == "SUCCESS":
            status = f"{clr_green}[SUCCESS]{clr_reset}"
        elif type_upper == "FAILED":
            status = f"{clr_red}[FAILED]{clr_reset}"
        elif type_upper == "WARN":
            status = f"{clr_yellow}[WARN]{clr_reset}"
        elif type_upper == "INFO":
            status = f"{clr_cyan}[INFO]{clr_reset}"
        else:
            status = f"[{type_upper}]"

        if " : " in message and message.startswith("[") and message.endswith("]"):
            inner = message[1:-1]
            parts = inner.split(" : ", 1)
            if len(parts) == 2:
                desc, value = parts
                msg = f"{clr_gray}[{clr_reset}{clr_white}{desc}{clr_reset} : {clr_cyan}{value}{clr_reset}{clr_gray}]{clr_reset}"
            else:
                msg = f"{clr_gray}[{clr_reset}{clr_white}{inner}{clr_reset}{clr_gray}]{clr_reset}"
        else:
            msg = message
        print(f"{ts} - {status} - {tok} → {msg}")

def log_simple(log_type: str, message: str):
    timestamp = get_timestamp()
    ts = f"{clr_gray}[{timestamp}]{clr_reset}"
    type_upper = log_type.upper()
    with print_lock:
        if type_upper == "FAILED":
            print(f"{ts} - {clr_red}[FAILED]{clr_reset} - {clr_red}{message}{clr_reset}")
        elif type_upper == "INFO":
            print(f"{ts} - {clr_cyan}[INFO]{clr_reset} - {clr_white}{message}{clr_reset}")
        elif type_upper == "WARN":
            print(f"{ts} - {clr_yellow}[WARN]{clr_reset} - {clr_yellow}{message}{clr_reset}")
        elif type_upper == "SUCCESS":
            print(f"{ts} - {clr_green}[SUCCESS]{clr_reset} - {clr_green}{message}{clr_reset}")
        else:
            print(f"{ts} - [{type_upper}] - {message}")

def display_banner():
    set_console_title("NKDev - Discord Humanizer")
    os.system("cls" if os.name == "nt" else "clear")
    c1 = "\033[38;5;51m"
    c2 = "\033[38;5;45m"
    c3 = "\033[38;5;39m"
    c4 = "\033[38;5;75m"
    c5 = "\033[38;5;111m"
    c6 = "\033[38;5;147m"
    banner_lines = [
        "",
        f"{c1}  ███╗   ██╗██╗  ██╗██████╗ ███████╗██╗   ██╗{clr_reset}",
        f"{c2}  ████╗  ██║██║ ██╔╝██╔══██╗██╔════╝██║   ██║{clr_reset}",
        f"{c3}  ██╔██╗ ██║█████╔╝ ██║  ██║█████╗  ██║   ██║{clr_reset}",
        f"{c4}  ██║╚██╗██║██╔═██╗ ██║  ██║██╔══╝  ╚██╗ ██╔╝{clr_reset}",
        f"{c5}  ██║ ╚████║██║  ██╗██████╔╝███████╗ ╚████╔╝ {clr_reset}",
        f"{c6}  ╚═╝  ╚═══╝╚═╝  ╚═╝╚═════╝ ╚══════╝  ╚═══╝  {clr_reset}",
        ""
    ]
    print("\n".join(banner_lines))

def mask_token(token: str) -> str:
    if len(token) <= 20:
        return token[:10] + "****"
    return token[:10] + "****" + token[-10:]

def load_file_lines(file_path: Path) -> List[str]:
    if not file_path.exists():
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

def append_to_file(file_path: Path, content: str):
    with file_lock:
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(content + "\n")

def remove_token_from_file(file_path: Path, token: str):
    with file_lock:
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
            new_lines = [l for l in lines if extract_token(l) != token.strip()]
            file_path.write_text("\n".join(new_lines) + ("\n" if new_lines else ""), encoding="utf-8")
        except Exception:
            pass

def format_time(seconds: float) -> str:
    minutes = int(seconds // 60)
    hours = minutes // 60
    if hours > 0:
        return f"{hours}h {minutes % 60}m"
    if minutes > 0:
        secs = seconds % 60
        return f"{minutes}m {secs:.2f}s"
    return f"{seconds:.2f}s"

def is_valid_token(s: str) -> bool:
    if not s or len(s) < 50:
        return False
    parts = s.split(".")
    if len(parts) != 3:
        return False
    return all(re.match(r"^[A-Za-z0-9_-]+$", part) and len(part) > 0 for part in parts)

def extract_token(line: str) -> Optional[str]:
    line = line.strip()
    if not line:
        return None
    if is_valid_token(line):
        return line
    for delimiter in [":", "|", "\t", " "]:
        if delimiter in line:
            parts = line.split(delimiter)
            for part in reversed(parts):
                part = part.strip()
                if is_valid_token(part):
                    return part
    return None

def load_tokens(file_path: Path) -> List[tuple]:
    lines = load_file_lines(file_path)
    tokens_data = []
    seen = set()
    for line in lines:
        token = extract_token(line)
        if token and token not in seen:
            seen.add(token)
            tokens_data.append((token, line))
    return tokens_data

def load_avatar_files() -> List[Path]:
    if not avatars_dir.exists():
        return []
    valid_extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
    return [f for f in avatars_dir.iterdir() if f.suffix.lower() in valid_extensions]

def load_avatar_as_base64(image_path: Path) -> Optional[str]:
    try:
        with pil_img_module.open(image_path) as img:
            is_png = image_path.suffix.lower() == ".png"
            if is_png:
                if img.mode == "P":
                    img = img.convert("RGBA")
            else:
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
            img = img.resize((avatar_dimension, avatar_dimension), resample_filter)
            img_copy = img.copy()

            def encode_img(pil_img, fmt, quality=75) -> str:
                buf = BytesIO()
                kw = {"format": fmt}
                if fmt == "JPEG":
                    kw["quality"] = quality
                    kw["optimize"] = True
                pil_img.save(buf, **kw)
                buf.seek(0)
                return base64.b64encode(buf.read()).decode("utf-8")

            img_format = "PNG" if is_png else "JPEG"
            b64 = encode_img(img_copy, img_format)
            mime = "image/png" if img_format == "PNG" else "image/jpeg"

            if len(b64) > discord_avatar_max_bytes:
                work_img = img_copy.convert("RGB") if img_copy.mode in ("RGBA", "P", "LA") else img_copy
                mime = "image/jpeg"
                for quality in (75, 55, 35, 20):
                    b64 = encode_img(work_img, "JPEG", quality)
                    if len(b64) <= discord_avatar_max_bytes:
                        break
                else:
                    half = max(64, avatar_dimension // 2)
                    work_img = work_img.resize((half, half), resample_filter)
                    for quality in (75, 55, 35):
                        b64 = encode_img(work_img, "JPEG", quality)
                        if len(b64) <= discord_avatar_max_bytes:
                            break
                    else:
                        return None
            return f"data:{mime};base64,{b64}"
    except Exception:
        return None

def parse_proxy(proxy_string: str) -> Optional[str]:
    proxy = proxy_string.strip()
    if proxy.startswith("#"):
        return None
    if "://" in proxy:
        parsed = urlparse(proxy)
        if parsed.hostname and parsed.port:
            return proxy
        return None
    if "@" in proxy:
        at_idx = proxy.rfind("@")
        auth = proxy[:at_idx]
        hostport = proxy[at_idx + 1:]
        colon_idx = auth.find(":")
        if colon_idx == -1:
            return None
        user = auth[:colon_idx]
        password = auth[colon_idx + 1:]
        host_parts = hostport.rsplit(":", 1)
        if len(host_parts) != 2:
            return None
        host, port = host_parts
        return f"http://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}"
    parts = proxy.split(":")
    if len(parts) == 4:
        host, port, user, password = parts
        return f"http://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}"
    elif len(parts) == 2:
        return f"http://{parts[0]}:{parts[1]}"
    return None

def sync_gateway_connect(tok: str, proxy_str: Optional[str], native_build: int):
    kwargs = {"timeout": 15}
    if proxy_str:
        try:
            pstr = proxy_str
            if not pstr.startswith("http"):
                parts = pstr.split(":")
                if len(parts) == 4:
                    pstr = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
                else:
                    pstr = f"http://{pstr}"
            p = urlparse(pstr)
            kwargs["http_proxy_host"] = p.hostname
            kwargs["http_proxy_port"] = p.port
            if p.username and p.password:
                kwargs["http_proxy_auth"] = (p.username, p.password)
        except Exception:
            pass
    try:
        ws = websocket.create_connection(discordgateway, **kwargs)
        hello = json.loads(ws.recv())
        if hello.get("op") != 10:
            return ws, None
        identify = {
            "op": 2,
            "d": {
                "token": tok,
                "capabilities": 16381,
                "properties": {
                    "os": "Windows",
                    "browser": "Discord Client",
                    "release_channel": "stable",
                    "client_version": discord_client_version,
                    "os_version": "10.0.26100",
                    "os_arch": "x64",
                    "app_arch": "x64",
                    "system_locale": "en-US",
                    "browser_user_agent": chrome_ua,
                    "browser_version": electron_version,
                    "os_sdk_version": "26100",
                    "client_build_number": build_number,
                    "native_build_number": native_build,
                    "client_event_source": None,
                    "design_id": 0,
                },
                "presence": {"status": "online", "since": 0, "activities": [], "afk": False},
                "compress": False,
                "client_state": {
                    "guild_versions": {},
                    "highest_last_message_id": "0",
                    "read_state_version": 0,
                    "user_guild_settings_version": -1,
                    "user_settings_version": -1,
                    "private_channels_version": "0",
                    "api_code_version": 0,
                },
            },
        }
        ws.send(json.dumps(identify))
        session_id = None
        for _ in range(5):
            msg = json.loads(ws.recv())
            if msg.get("t") == "READY":
                session_id = msg.get("d", {}).get("session_id")
                break
        return ws, session_id
    except Exception:
        return None, None

class Humanizer:
    def __init__(self, token: str, original_line: str, proxy: Optional[str] = None):
        self.token = token
        self.original_line = original_line
        self.proxy = proxy
        self.proxy_arg = parse_proxy(proxy) if proxy else None
        self.client = primp.Client(
            verify=False,
            proxy=self.proxy_arg
        )
        self.session_id = None
        self.proxy_failed = False
        self.is_locked = False
        self.native_build = random.randint(65600, 65800)

        self.installation_id = (
            f"{random.randint(10**18, 10**19 - 1)}."
            + "".join(random.choices("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_", k=22))
        )
        self.launch_id = str(uuid.uuid4())
        self.signature = str(uuid.uuid4())
        self.heartbeat_id = str(uuid.uuid4())

    def build_headers(self, real_sid: Optional[str]) -> Dict[str, str]:
        heartbeat = real_sid if real_sid else self.heartbeat_id
        super_props = generate_super_properties(self.launch_id, self.signature, heartbeat)
        cf_cookies, fp = get_discord_cf_cookies_and_fingerprint(self.proxy_arg)
        h = {
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en-US,en;q=0.9",
            "authorization": self.token,
            "content-type": "application/json",
            "cookie": cf_cookies,
            "origin": "https://discord.com",
            "referer": "https://discord.com/channels/@me",
            "sec-ch-ua": '"Chromium";v="146", "Google Chrome";v="146", "Not/A)Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": chrome_ua,
            "x-debug-options": "bugReporterEnabled",
            "x-discord-locale": "en-US",
            "x-discord-timezone": "Asia/Calcutta",
            "x-installation-id": self.installation_id,
            "x-super-properties": super_props,
        }
        if fp:
            h["x-fingerprint"] = fp
        return h

    def clean_error(self, error) -> str:
        error = str(error)
        if "rate limit" in error.lower() or "too often" in error.lower() or "rate_limit" in error.lower():
            return "Rate Limited"
        if "Unauthorized" in error or "401" in error:
            return "Unauthorized"
        if "captcha" in error.lower():
            return "Captcha"
        if "Unknown Session" in error:
            return "Bad session"
        if "message" in error and "code" in error:
            match = re.search(r"'message': '([^']+)'", error)
            if match:
                msg = match.group(1)
                if len(msg) > 25:
                    return msg[:22] + "..."
                return msg
        if len(error) > 80:
            return error[:77] + "..."
        return error

    def api_call_with_retry(self, method: str, url: str, data: Optional[Dict[str, Any]] = None,
                            headers: Optional[Dict[str, str]] = None, max_retries: int = 2) -> Dict[str, Any]:
        if getattr(self, "is_locked", False):
            return {"success": False, "error": "Token Locked"}
        last_result = None
        for attempt in range(max_retries):
            if getattr(self, "is_locked", False):
                return {"success": False, "error": "Token Locked"}
            try:
                h = headers if headers else self.build_headers(self.session_id)
                if method.upper() == "POST":
                    resp = self.client.post(url, headers=h, json=data, timeout=30)
                elif method.upper() == "PATCH":
                    resp = self.client.patch(url, headers=h, json=data, timeout=30)
                else:
                    resp = self.client.get(url, headers=h, timeout=30)

                if resp.status_code in (200, 204):
                    try:
                        resp_data = resp.json() if resp.text and resp.status_code == 200 else {}
                    except Exception:
                        resp_data = {}
                    return {"success": True, "data": resp_data, "status": resp.status_code}

                try:
                    error_data = resp.json() if resp.text and resp.text.strip() else {}
                except Exception:
                    error_data = {}

                if error_data.get("captcha_key") or error_data.get("captcha_sitekey"):
                    return {"success": False, "captcha": True, "error": "Captcha required", "status": resp.status_code}

                if resp.status_code == 429:
                    try:
                        ra_header = resp.headers.get("retry-after") or resp.headers.get("Retry-After")
                        ra_body = error_data.get("retry_after", 0) if isinstance(error_data, dict) else 0
                        retry_after = float(ra_header) if ra_header else float(ra_body or 0)
                    except (TypeError, ValueError):
                        retry_after = 0
                    wait_time = max(retry_after, 1.0)
                    time.sleep(wait_time)
                    continue

                if resp.status_code in (401, 403):
                    self.is_locked = True
                    return {"success": False, "unauthorized": True, "error": "Unauthorized", "status": resp.status_code}

                last_result = {"success": False, "error": error_data.get("message", resp.text[:100]), "status": resp.status_code}
            except Exception as e:
                error_str = str(e)
                last_result = {"success": False, "error": error_str, "status": 0}
                if attempt >= max_retries - 1:
                    return last_result
        return last_result or {"success": False, "error": "Max retries reached"}

    def set_hypesquad(self, house_id: int, headers: Dict[str, str]) -> Dict[str, Any]:
        house_name = hypesquad_houses.get(house_id, "Unknown")
        try:
            check = self.client.get(f"{discordapi}/users/@me", headers=headers, timeout=20)
            if check.status_code == 200:
                data = check.json()
                flags = data.get("flags", 0)
                if flags & 0xE:
                    existing_house = None
                    for hid, hname in hypesquad_houses.items():
                        if flags & (1 << hid):
                            existing_house = hname
                            break
                    if existing_house:
                        log("INFO", self.token, f"[HypeSquad Already Set : {existing_house}]")
                        return {"success": True, "house_name": existing_house, "already_set": True}
        except Exception:
            pass

        res = self.api_call_with_retry(
            "post",
            f"{discordapi}/hypesquad/online",
            {"house_id": house_id},
            headers,
            max_retries=2
        )
        if res.get("success") or res.get("status") in (200, 204):
            return {"success": True, "house_name": house_name}
        return {"success": False, "error": f"HypeSquad {house_name} not applied", "house_name": house_name}

    def process(self, names: List[str], bios: List[str], pronouns_list: List[str],
                avatar_files: List[Path], avatar_loader) -> bool:
        ws, real_sid = sync_gateway_connect(self.token, self.proxy, self.native_build)
        self.session_id = real_sid
        headers = self.build_headers(real_sid)

        try:
            check_resp = self.client.get(f"{discordapi}/users/@me", headers=headers, timeout=15)
            if check_resp.status_code != 200:
                self.is_locked = True
                log("FAILED", self.token, f"[Token Status : Already Invalid / Dead ({check_resp.status_code})]")
            else:
                user_info = check_resp.json()
                user_name = user_info.get("username", "Unknown")
                user_id = user_info.get("id")
                log("INFO", self.token, f"[Account Verified : {user_name} | Session : {real_sid[:8] if real_sid else 'none'}]")

                if user_id:
                    try:
                        self.client.get(f"{discordapi}/users/{user_id}/profile?type=modal&with_mutual_guilds=true&with_mutual_friends=false&with_mutual_friends_count=true", headers=headers, timeout=10)
                        self.client.get(f"{discordapi}/users/@me/avatars", headers=headers, timeout=10)
                    except Exception:
                        pass

                time.sleep(0.5)

            if update_avatar and avatar_files and not self.is_locked:
                avatar_path = random.choice(avatar_files)
                avatar_b64 = avatar_loader(avatar_path)
                if avatar_b64:
                    account_payload = {
                        "avatar": avatar_b64
                    }
                    res = self.api_call_with_retry("patch", f"{discordapi}/users/@me", account_payload, headers)
                    if res.get("success"):
                        log("SUCCESS", self.token, f"[Avatar Updated : {avatar_path.name}]")
                    elif res.get("captcha"):
                        log("FAILED", self.token, "[Avatar Failed : Captcha]")
                        self.is_locked = True
                    else:
                        error_msg = self.clean_error(res.get("error", "Unknown"))
                        log("FAILED", self.token, f"[Avatar Failed : {error_msg}]")
                        self.is_locked = True
                    time.sleep(random.uniform(0.6, 1.0))

            if update_display_name and names and not self.is_locked:
                display_name = random.choice(names)
                res = self.api_call_with_retry("patch", f"{discordapi}/users/@me", {"global_name": display_name}, headers)
                if res.get("success"):
                    log("SUCCESS", self.token, f"[Name Updated : {display_name}]")
                elif res.get("captcha"):
                    log("FAILED", self.token, "[Name Failed : Captcha]")
                    self.is_locked = True
                else:
                    error_msg = self.clean_error(res.get("error", "Unknown"))
                    log("FAILED", self.token, f"[Name Failed : {error_msg}]")
                    self.is_locked = True
                time.sleep(random.uniform(0.5, 0.9))

            if (update_bio or update_pronouns) and not self.is_locked:
                prof_payload = {}
                bio_val = None
                pronouns_val = None
                if update_bio and bios:
                    bio_val = random.choice(bios)
                    prof_payload["bio"] = bio_val
                if update_pronouns and pronouns_list:
                    pronouns_val = random.choice(pronouns_list)
                    prof_payload["pronouns"] = pronouns_val

                if prof_payload:
                    res = self.api_call_with_retry("patch", f"{discordapi}/users/%40me/profile", prof_payload, headers)
                    if res.get("success"):
                        if bio_val:
                            log("SUCCESS", self.token, f"[Bio Updated : {bio_val[:40]}{'...' if len(bio_val) > 40 else ''}]")
                        if pronouns_val:
                            log("SUCCESS", self.token, f"[Pronouns Updated : {pronouns_val}]")
                    elif res.get("captcha"):
                        log("FAILED", self.token, "[Profile Failed : Captcha]")
                        self.is_locked = True
                    else:
                        error_msg = self.clean_error(res.get("error", "Unknown"))
                        log("FAILED", self.token, f"[Profile Failed : {error_msg}]")
                        self.is_locked = True
                    time.sleep(random.uniform(0.5, 0.9))

            if update_hypesquad and not self.is_locked:
                house_id = random.choice([1, 2, 3])
                house_name = hypesquad_houses[house_id]
                res = self.set_hypesquad(house_id, headers)
                if res.get("success"):
                    if not res.get("already_set"):
                        log("SUCCESS", self.token, f"[HypeSquad Updated : {house_name}]")
                elif res.get("captcha"):
                    log("FAILED", self.token, "[HypeSquad Failed : Captcha]")
                    self.is_locked = True
                else:
                    error_msg = self.clean_error(res.get("error", "Unknown"))
                    log("FAILED", self.token, f"[HypeSquad Failed : {error_msg}]")
                    self.is_locked = True

        finally:
            if ws:
                try:
                    ws.close()
                except Exception:
                    pass

        if not self.is_locked:
            with stats_lock:
                append_to_file(success_file, self.original_line)
                remove_token_from_file(tokens_file, self.token)
                stats["success"] += 1
            return True
        else:
            with stats_lock:
                append_to_file(failed_file, self.original_line)
                remove_token_from_file(tokens_file, self.token)
                stats["failed"] += 1
            return False

def process_token(token: str, original_line: str, names: List[str], bios: List[str], pronouns_list: List[str],
                  avatar_files: List[Path], avatar_loader) -> bool:
    wait_account_cooldown(default_cooldown)
    proxy = proxy_manager.get_proxy() if proxy_manager else None
    humanizer = Humanizer(token, original_line, proxy)
    try:
        result = humanizer.process(names, bios, pronouns_list, avatar_files, avatar_loader)
        time.sleep(0.2)
        return result
    finally:
        if proxy_manager and proxy:
            proxy_manager.release_proxy(proxy)

def main():
    global proxy_manager, max_threads

    set_console_title("Discord Humanizer")
    display_banner()

    log_simple("INFO", f"Fetched Discord Build: {build_number} | Client: {discord_client_version} | Electron: {electron_version}")
    log_simple("INFO", f"Network Engine: primp-rust | Proxy Mode: {'Enabled' if use_proxy else 'Direct Connection'}")

    try:
        threads_input = input(f"\n  {clr_purple}›{clr_reset} {clr_white}Threads{clr_reset} {clr_gray}(default: {max_threads}){clr_reset}: ").strip()
        print("")
        if threads_input:
            max_threads = int(threads_input)
    except ValueError:
        log_simple("WARN", f"Invalid thread count entered. Using default: {max_threads}")

    data_dir.mkdir(parents=True, exist_ok=True)
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    avatars_dir.mkdir(parents=True, exist_ok=True)
    banners_dir.mkdir(parents=True, exist_ok=True)

    tokens = load_tokens(tokens_file)
    if not tokens:
        log_simple("FAILED", f"No valid tokens found in {tokens_file}")
        return

    with stats_lock:
        stats["total"] = len(tokens)

    if use_proxy:
        proxy_lines = load_file_lines(proxies_file)
        proxies = [p for p in (parse_proxy(line) for line in proxy_lines) if p]
        if proxies:
            proxy_manager = ProxyManager(proxies)
            log_simple("INFO", f"Loaded {len(proxies)} proxies from {proxies_file}")
        else:
            log_simple("WARN", f"No valid proxies found in {proxies_file}. Running on direct connection.")
    else:
        proxy_manager = None

    names = load_file_lines(names_file)
    bios = load_file_lines(bios_file)
    pronouns_list = load_file_lines(pronouns_file)
    avatar_files = load_avatar_files()

    avatar_lock = threading.Lock()
    avatar_cache: Dict[Path, str] = {}

    def lazy_get_avatar(path: Path) -> Optional[str]:
        with avatar_lock:
            if path in avatar_cache:
                return avatar_cache[path]
        b64 = load_avatar_as_base64(path)
        if b64:
            with avatar_lock:
                avatar_cache[path] = b64
        return b64

    if avatar_files:
        log_simple("INFO", f"Loaded {len(avatar_files)} avatars")
    log_simple("INFO", f"Loaded {len(tokens)} accounts | Staggered Cooldown: {default_cooldown}s\n")

    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        token_iter = iter(tokens)
        active_futures = set()

        while True:
            while len(active_futures) < max_threads:
                try:
                    token, original_line = next(token_iter)
                    future = executor.submit(process_token, token, original_line, names, bios, pronouns_list, avatar_files, lazy_get_avatar)
                    future.token_item = token
                    active_futures.add(future)
                except StopIteration:
                    break

            if not active_futures:
                break

            done, _ = wait(active_futures, return_when="FIRST_COMPLETED")

            for future in done:
                active_futures.remove(future)
                try:
                    future.result()
                except Exception as e:
                    token = getattr(future, "token_item", "Unknown")
                    log("FAILED", token, f"Unexpected error: {str(e)[:50]}")

    elapsed = time.time() - stats["start_time"]
    success_rate = (stats["success"] / stats["total"] * 100) if stats["total"] > 0 else 0

    print("")
    log_simple("INFO", f"Finished Humanizer Run in {format_time(elapsed)}")
    log_simple("INFO", f"Total Accounts Processed : {stats['total']}")
    log_simple("SUCCESS", f"Successfully Humanized   : {stats['success']} ({success_rate:.1f}%)")
    if stats["failed"] > 0:
        log_simple("FAILED", f"Failed Accounts          : {stats['failed']}")
    if proxy_manager:
        ps = proxy_manager.get_stats()
        log_simple("INFO", f"Proxy Pool Status        : {ps['active']} Active / {ps['bad']} Dead")
    else:
        log_simple("INFO", "Connection Mode          : Direct (No Proxy)")
    print("")

    if proxy_manager and proxy_manager.bad_proxies:
        proxy_lines = load_file_lines(proxies_file)
        cleaned = [p for p in proxy_lines if parse_proxy(p) not in proxy_manager.bad_proxies]
        proxies_file.write_text("\n".join(cleaned) + "\n")
        log_simple("INFO", f"Removed {len(proxy_lines) - len(cleaned)} bad proxies from proxies.txt")

if __name__ == "__main__":
    main()
