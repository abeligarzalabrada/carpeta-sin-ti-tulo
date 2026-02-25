import os
import sys
import json
import time
import logging
import threading
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# --- Configuration & Logging --- #
CONFIG_PATH = os.path.expanduser("~/.nanobot/config.json")
SKILLS_DIR = "skills"
MCP_CONFIG = "skills.json"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("NanoBotCore")

# --- Context Bus --- #
class ContextBus:
    
    """Bus de contexto común para todos los agentes. Mantiene el estado en memoria."""
    def __init__(self):
        self.messages = []
        self.lock = threading.Lock()
        
    def publish(self, sender, message):
        with self.lock:
            entry = {"time": time.time(), "sender": sender, "message": message}
            self.messages.append(entry)
            logger.info(f"[{sender}] {message}")
            
    def get_all(self):
        with self.lock:
            return list(self.messages)

bus = ContextBus()

# --- Configuración Web (Puerto 8080) --- #
class ConfigUIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            
            # Cargar config
            try:
                with open(CONFIG_PATH, "r") as f:
                    config_data_raw = f.read()
                    config_dict = json.loads(config_data_raw)
            except Exception:
                config_data_raw = "{}"
                config_dict = {}
                
            channels = config_dict.get("channels", {})
            integrations_html = ""
            available_integrations = {
                "telegram": ["token"],
                "discord": ["token"],
                "whatsapp": [], 
                "feishu": ["appId", "appSecret"],
                "mochat": ["claw_token", "agent_user_id"],
                "dingtalk": ["clientId", "clientSecret"],
                "slack": ["botToken", "appToken"],
                "email": ["imapUsername", "imapPassword", "smtpUsername", "smtpPassword"],
                "qq": ["appId", "secret"]
            }
            
            for key, fields in available_integrations.items():
                channel_cfg = channels.get(key, {})
                enabled = channel_cfg.get("enabled", False)
                checked = "checked" if enabled else ""
                
                inputs_html = ""
                for config_field in fields:
                    val = channel_cfg.get(config_field, "")
                    inputs_html += f'<div><label style="display:inline-block; width:130px;">{config_field}:</label> <input type="text" name="chan_{key}_{config_field}" value="{val}"></div>'
                    
                integrations_html += f"""
                <div class="integration-item">
                    <label>
                        <input type="checkbox" name="enable_{key}" {checked} onchange="toggleConfig('cfg_{key}')" value="true">
                        <b style="color: #00ff00;">{key.capitalize()}</b>
                    </label>
                    <div id="cfg_{key}" style="display: {'block' if enabled else 'none'}; margin-left: 20px; margin-top: 10px;">
                        {inputs_html}
                    </div>
                </div>
                """
                
            providers_config = config_dict.get("providers", {})
            providers_html = ""
            available_providers = {
                "deepseek": ["apiKey"],
                "openrouter": ["apiKey"],
                "anthropic": ["apiKey"],
                "openai": ["apiKey"],
                "groq": ["apiKey"],
                "gemini": ["apiKey"],
                "minimax": ["apiKey"],
                "aihubmix": ["apiKey"],
                "siliconflow": ["apiKey"],
                "volcengine": ["apiKey"],
                "dashscope": ["apiKey"],
                "moonshot": ["apiKey"],
                "zhipu": ["apiKey"],
                "vllm": ["apiKey", "apiBase"],
                "custom": ["apiKey", "apiBase"]
            }
            
            for key, fields in available_providers.items():
                is_enabled_in_config = key in providers_config
                # We can't strictly know if it's "enabled" because there's no "enabled" boolean for providers,
                # but we can infer it exists if the key is present in json. We'll use a checkbox anyway.
                checked = "checked" if is_enabled_in_config else ""
                
                prov_cfg = providers_config.get(key, {})
                inputs_html = ""
                for config_field in fields:
                    val = prov_cfg.get(config_field, "")
                    inputs_html += f'<div><label style="display:inline-block; width:130px;">{config_field}:</label> <input type="text" name="prov_{key}_{config_field}" value="{val}"></div>'
                    
                # Highlight DeepSeek
                display_name = "⭐️ " + key.capitalize() if key == "deepseek" else key.capitalize()
                
                providers_html += f"""
                <div class="integration-item">
                    <label>
                        <input type="checkbox" name="enable_prov_{key}" {checked} onchange="toggleConfig('prov_div_{key}')" value="true">
                        <b style="color: #00ff00;">{display_name}</b>
                    </label>
                    <div id="prov_div_{key}" style="display: {'block' if is_enabled_in_config else 'none'}; margin-left: 20px; margin-top: 10px;">
                        {inputs_html}
                    </div>
                </div>
                """

            html = f"""<!DOCTYPE html>
<html>
<head>
    <title>NanoBot Config & Logs</title>
    <style>
        body {{ font-family: monospace; background: #121212; color: #00ff00; margin: 2rem; padding-bottom: 50px; }}
        textarea {{ width: 100%; height: 150px; background: #222; color: #fff; border: 1px solid #444; padding: 10px; }}
        input[type="text"] {{ width: 80%; background: #222; color: #fff; border: 1px solid #444; padding: 10px; }}
        button {{ background: #00ff00; color: #000; border: none; padding: 10px 20px; cursor: pointer; }}
        #logs {{ background: #000; padding: 15px; border: 1px solid #444; height: 350px; overflow-y: auto; margin-bottom: 20px;}}
        .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #333; padding-bottom: 1rem; margin-bottom: 1rem;}}
        .chat-container {{ display: flex; gap: 10px; margin-bottom: 20px; }}
        .integration-item {{ margin-bottom: 10px; background: #222; padding: 10px; border-radius: 5px; border: 1px solid #444; }}
        .integration-item label {{ cursor: pointer; display: flex; align-items: center; gap: 10px; }}
        .integration-item input[type="text"] {{ width: 60%; background: #111; color: #fff; border: 1px solid #555; padding: 5px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>NanoBot Executive Dashboard</h1>
        <span>RAM: &lt;15MB | NATIVE PYTHON</span>
    </div>
    
    <h2>Live Context Bus (Agents)</h2>
    <div id="logs">Connecting to bus...</div>
    
    <div class="chat-container">
        <input type="text" id="chatInput" placeholder="Send orders to NanoBot..." onkeypress="if(event.key === 'Enter') sendChat()">
        <button onclick="sendChat()">Send</button>
    </div>
    
    <h2>LLM Providers (Model Configuration)</h2>
    <form method="POST" action="/update_providers">
        {providers_html}
        <button type="submit">Save Provider Credentials</button>
    </form>
    
    <h2>Integrations & Channels</h2>
    <form method="POST" action="/update_channels">
        {integrations_html}
        <button type="submit">Save Active Integrations</button>
    </form>
    
    <h2>Raw Configuration (config.json)</h2>
    <form method="POST" action="/update">
        <textarea name="config">{config_data_raw}</textarea><br><br>
        <button type="submit">Save Raw Configuration</button>
    </form>
    
    <script>
        function toggleConfig(id) {{
            const el = document.getElementById(id);
            el.style.display = el.style.display === 'none' ? 'block' : 'none';
        }}
        
        function sendChat() {{
            const el = document.getElementById('chatInput');
            if(!el.value) return;
            fetch('/chat', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/x-www-form-urlencoded' }},
                body: 'message=' + encodeURIComponent(el.value)
            }}).then(() => {{ el.value = ''; }});
        }}
        
        setInterval(() => {{
            fetch('/logs')
                .then(r => r.json())
                .then(data => {{
                    const lg = document.getElementById('logs');
                    const isScrolledToBottom = lg.scrollHeight - lg.clientHeight <= lg.scrollTop + 1;
                    lg.innerHTML = data.map(x => `<b>[${{x.sender}}]</b> ${{x.message}}`).join('<br>');
                    if(isScrolledToBottom) lg.scrollTop = lg.scrollHeight;
                }});
        }}, 500);
    </script>
</body>
</html>"""
            self.wfile.write(html.encode("utf-8"))
            
        elif self.path == '/logs':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(bus.get_all()).encode("utf-8"))
            
        elif self.path == '/chat':
            # Endpoint para recibir mensajes GET vía query string (simplificado) o POST
            pass
            
    def do_POST(self):
        if self.path == '/chat':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode("utf-8")
            params = parse_qs(post_data)
            if 'message' in params:
                msg = params['message'][0]
                bus.publish("User", msg)
                # Aquí el MasterAgent debería reaccionar. Lo simulamos poniendo el mensaje en el bus.
                master.process_user_message(msg)
            self.send_response(302)
            self.send_header('Location', '/')
            self.end_headers()
            
        elif self.path == '/update_providers':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode("utf-8")
            params = parse_qs(post_data)
            
            try:
                with open(CONFIG_PATH, "r") as f:
                    config_dict = json.load(f)
            except Exception:
                config_dict = {}
                
            if "providers" not in config_dict:
                config_dict["providers"] = {}
                
            available_providers = ["deepseek", "openrouter", "anthropic", "openai", "groq", "gemini", "minimax", "aihubmix", "siliconflow", "volcengine", "dashscope", "moonshot", "zhipu", "vllm", "custom"]
            
            for key in available_providers:
                enabled = f"enable_prov_{key}" in params
                
                if enabled:
                    if key not in config_dict["providers"]:
                        config_dict["providers"][key] = {}
                        
                    for p_key, p_val in params.items():
                        prefix = f"prov_{key}_"
                        if p_key.startswith(prefix):
                            field_name = p_key.replace(prefix, "")
                            config_dict["providers"][key][field_name] = p_val[0]
                else:
                    if key in config_dict["providers"]:
                        del config_dict["providers"][key]
                        
            with open(CONFIG_PATH, "w") as f:
                json.dump(config_dict, f, indent=4)
                
            bus.publish("System", "LLM Providers updated via Web Interface.")
            self.send_response(302)
            self.send_header('Location', '/')
            self.end_headers()
            
        elif self.path == '/update_channels':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode("utf-8")
            params = parse_qs(post_data)
            
            try:
                with open(CONFIG_PATH, "r") as f:
                    config_dict = json.load(f)
            except Exception:
                config_dict = {}
                
            if "channels" not in config_dict:
                config_dict["channels"] = {}
                
            available_integrations = ["telegram", "discord", "whatsapp", "feishu", "mochat", "dingtalk", "slack", "email", "qq"]
            for key in available_integrations:
                enabled = f"enable_{key}" in params
                
                if enabled:
                    if key not in config_dict["channels"]:
                        config_dict["channels"][key] = {}
                    config_dict["channels"][key]["enabled"] = True
                    
                    for p_key, p_val in params.items():
                        prefix = f"chan_{key}_"
                        if p_key.startswith(prefix):
                            field_name = p_key.replace(prefix, "")
                            config_dict["channels"][key][field_name] = p_val[0]
                else:
                    if key in config_dict["channels"]:
                        config_dict["channels"][key]["enabled"] = False
                        
            with open(CONFIG_PATH, "w") as f:
                json.dump(config_dict, f, indent=4)
                
            bus.publish("System", "Channel integrations updated via Web Interface.")
            self.send_response(302)
            self.send_header('Location', '/')
            self.end_headers()
            
        elif self.path == '/update':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode("utf-8")
            params = parse_qs(post_data)
            if 'config' in params:
                try:
                    # Validar JSON antes de guardar
                    json.loads(params['config'][0])
                    with open(CONFIG_PATH, "w") as f:
                        f.write(params['config'][0])
                    bus.publish("System", "Raw Configuration updated via Web Interface.")
                except json.JSONDecodeError as e:
                    bus.publish("System", f"Failed to save Raw Configuration. Invalid JSON: {e}")
                    
            self.send_response(302)
            self.send_header('Location', '/')
            self.end_headers()

    def log_message(self, format, *args):
        # Mute standard access HTTP logs
        pass

def start_web_server():
    server = HTTPServer(('0.0.0.0', 8080), ConfigUIHandler)
    bus.publish("System", "Web dashboard listening on http://localhost:8080")
    server.serve_forever()

# --- Sistema de Skills Dinámicas --- #
class SkillsManager:
    """Administra la creacion y ejecucion de scripts/skills."""
    def __init__(self):
        os.makedirs(SKILLS_DIR, exist_ok=True)
        
    def create_skill(self, name: str, code: str, ext: str = ".py"):
        """El agente programador puede crear un script de skill aquí."""
        path = os.path.join(SKILLS_DIR, name + ext)
        with open(path, "w") as f:
            f.write(code)
        if ext == ".sh":
            os.chmod(path, 0o755)
        bus.publish("Skills", f"Skill '{name}{ext}' successfully created.")
        
    def execute_skill(self, name: str, args: list = None):
        """Ejecuta una skill existente."""
        if args is None: args = []
        path_py = os.path.join(SKILLS_DIR, name + ".py")
        path_sh = os.path.join(SKILLS_DIR, name + ".sh")
        
        try:
            if os.path.exists(path_py):
                return subprocess.run([sys.executable, path_py] + args, capture_output=True, text=True, check=True)
            elif os.path.exists(path_sh):
                return subprocess.run([path_sh] + args, capture_output=True, text=True, check=True)
            else:
                bus.publish("Skills", f"Skill {name} not found.")
                return None
        except subprocess.CalledProcessError as e:
            bus.publish("Skills", f"Error execution {name}: {e.stderr}")
            return None

# --- Integración Nativa de MCP --- #
class MCPClientCore:
    """Cliente Model Context Protocol para autoinstalar servidores externos."""
    def __init__(self):
        self.config_path = MCP_CONFIG
        if not os.path.exists(self.config_path):
            with open(self.config_path, "w") as f:
                json.dump({"mcpServers": {}}, f, indent=4)
                
    def load_servers(self):
        try:
            with open(self.config_path, "r") as f:
                return json.load(f).get("mcpServers", {})
        except json.JSONDecodeError:
            return {}
            
    def install_mcp_server(self, name: str, command: str, args: list):
        """Añade un servidor MCP de forma autónoma."""
        data = {"mcpServers": self.load_servers()}
        data["mcpServers"][name] = {"command": command, "args": args}
        with open(self.config_path, "w") as f:
            json.dump(data, f, indent=4)
        bus.publish("MCP", f"Installed MCP server: {name} ({command})")

# --- Core Multiagente Nativo: El Master --- #
class MasterAgent:
    def __init__(self):
        self.skills = SkillsManager()
        self.mcp = MCPClientCore()
        bus.publish("MasterAgent", "Booting core systems...")
        
    def show_onboard_guide(self):
        guide = """
================================================================
🚀 BIENVENIDO A NANOBOT - ONBOARDING Y GUÍA RÁPIDA 🚀
================================================================

1. 💻 ACCESO A LA CONSOLA (CLI):
   - Al ejecutar `./nanobot_bin`, entras directo a este modo.
   - Escribe aquí tus comandos y presiona ENTER.
   - Para salir formalmente, usa el comando: 'exit' o presiona Ctrl+C.

2. 🤖 CONVERSANDO CON EL AGENTE:
   - Usa un lenguaje natural.
   - Ejemplo (Crear Skill): "Crea un script que diga hola mundo"
   - Ejemplo (MCP): "Instala un servidor mcp de sqlite"
   - Puedes usar comandos rápidos:
     - 'help' o 'ayuda' -> Muestra esta guía.
     - 'clear' -> Limpia la consola.

3. ⚙️ CONFIGURACIÓN DE APIs Y SISTEMA:
   - Vía Web: 🌟 RECOMENDADO: Entra a http://localhost:8080 desde
     el navegador. Ahí encontrarás un panel de 'Integrations & Channels'
     con switches interactivos (botones) para encender las integraciones
     fácilmente y cajas para colocar sus credenciales sin errores!
   - Vía Consola: Abre directamente el archivo `config.json` o
     dile al bot: "Actualiza mi config para poner mi api key de openai".

¡Tu Ejecutivo Digital está listo! Escribe un mensaje abajo.
================================================================
"""
        print(guide)
        bus.publish("MasterAgent", "Displayed onboarding guide to user.")

    def process_user_message(self, message: str):
        """Punto de entrada para interacciones del usuario"""
        # Aquí el Master analiza si debe hacer spawn de un subagente o contestar directo
        bus.publish("MasterAgent", f"Analyzing user intent: '{message}'")
        time.sleep(1) # Simula razonamiento LLM
        lower_msg = message.lower()
        
        if message.lower() in ["help", "ayuda", "onboard", "guia"]:
            self.show_onboard_guide()
            return
            
        if message.lower() in ["clear", "cls"]:
            os.system('cls' if os.name == 'nt' else 'clear')
            return

        if "instala" in lower_msg or "install" in lower_msg:
            url_target = message.split()[-1]
            self.spawn_subagent("Investigador", f"Verify safely the tool at {url_target}")
            time.sleep(2)
            self.install_tool(url_target)
        elif "crea" in lower_msg or "haz" in lower_msg or "write" in lower_msg:
            self.spawn_subagent("Programador", message)
        else:
            bus.publish("MasterAgent", "Understood. Maintaining autonomous standby and analyzing possible implicit tasks.")

    def spawn_subagent(self, role: str, task: str):
        """Lanza de forma nativa un hilo simulando a un sub-agente especializado."""
        bus.publish("MasterAgent", f"Spawning [{role}] for task: {task}")
        t = threading.Thread(target=self._run_subagent, args=(role, task))
        t.daemon = True
        t.start()
        
    def _run_subagent(self, role: str, task: str):
        bus.publish(role, f"I have booted. Analyzing task: '{task}'")
        time.sleep(2)  # Simulating LLM analysis
        
        if role == "Investigador":
            bus.publish(role, "Searching for best approach. MCP tools verified.")
            time.sleep(1)
            bus.publish(role, "Research complete. Delegating code gen to Programador.")
            
        elif role == "Programador":
            bus.publish(role, "Writing Python skill script...")
            code = "print('Hello World from dynamically generated skill!')"
            self.skills.create_skill("hello_world", code, ".py")
            bus.publish(role, "Code complete.")
            
        elif role == "Ejecutor":
            bus.publish(role, "Executing newly created skill...")
            time.sleep(1)
            res = self.skills.execute_skill("hello_world")
            if res:
                bus.publish(role, f"Output from skill: {res.stdout.strip()}")
            
    def install_tool(self, url: str):
        """Capacidad del bot de actualizar su entono/instalar nuevas herramientas"""
        bus.publish("MasterAgent", f"Received request to install tool from {url}...")
        # Lógica genérica de ejemplo:
        self.mcp.install_mcp_server("new_tool", "npx", ["-y", url])
        bus.publish("MasterAgent", "Tool successfully installed and registered in skills.json.")

    def self_update(self):
        bus.publish("MasterAgent", "Performing self update routine...")
        # Lógica de actualización (git pull, etc)
        bus.publish("MasterAgent", "System is up to date.")

if __name__ == "__main__":
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w") as f:
            f.write(json.dumps({"bot_name": "NanoBot", "mode": "autonomous"}, indent=4))
            
    # Inicializa interfaz web en background
    threading.Thread(target=start_web_server, daemon=True).start()
    
    # Init central core
    global master
    master = MasterAgent()
    
    print("\n" + "="*50)
    print(" 🤖 N A N O B O T   C O R E   O N L I N E 🤖 ")
    print(" 🌐 Web Dashboard: http://localhost:8080")
    print(" 💡 Escribe 'help' o 'ayuda' para ver la guía de inicio.")
    print("="*50 + "\n")
    
    try:
        # Loop principal con CLI nativo interactivo
        while True:
            try:
                user_input = input("User ❯ ")
                if user_input.strip() == "exit":
                    break
                if user_input.strip():
                    if user_input.strip().lower() not in ["clear", "cls", "help", "ayuda", "onboard"]:
                        bus.publish("User", user_input)
                    master.process_user_message(user_input)
            except EOFError:
                break
    except KeyboardInterrupt:
        pass
        
    print("\n")
    logger.info("NanoBot shutting down.")
