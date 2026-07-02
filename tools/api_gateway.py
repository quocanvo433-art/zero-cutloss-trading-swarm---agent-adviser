"""
🧬 DNA: v16.7
🏢 UNIT: API_GATEWAY
🛠️ ROLE: SOVEREIGN_PROXY
📖 DESC: HTTPS/HTTP Proxy lifeline filtering connections out of the Sandbox
"""
import socket
import select
import threading
import os
import requests
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ALLOWED_DOMAINS = [
    "openrouter.ai", 
    "api.groq.com", 
    "host.docker.internal",
    "172.18.0.1",
    "172.19.0.1",
    "172.17.0.1",
    "127.0.0.1",
    "localhost",
    "zcl_ollama",
    "zcl_api_gateway",
    "zcl_claw_coder",
    "zcl_redis"
]

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

def send_telegram_alert(blocked_host):
    msg = f"🚨 [API GATEWAY ALERT]\nCLAW Sandbox attempted to bypass firewall to unauthorized domain: {blocked_host}\nPacket has been blocked!"
    print(msg, flush=True)
    if TELEGRAM_TOKEN and TELEGRAM_CHAT:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT, "text": msg},
                timeout=5
            )
        except:
            pass

class APIFilterProxy(BaseHTTPRequestHandler):
    def do_CONNECT(self):
        host, port = self.path.split(":")
        
        # Allow only domains in the filter
        allowed = False
        for d in ALLOWED_DOMAINS:
            if host == d or host.endswith("." + d):
                allowed = True
                break
                
        if not allowed:
            print(f"❌ [BLOCKED] Connection to {host}:{port} was rejected!", flush=True)
            self.send_error(403, f"Domain {host} is strictly blocked by Zero-Cutloss Sovereign Gateway.")
            threading.Thread(target=send_telegram_alert, args=(host,)).start()
            return

        print(f"✅ [ALLOWED] API connection to {host}:{port}", flush=True)

        target_sock = None
        try:
            # Establish tunnel (Tunneling) with API provider
            target_sock = socket.create_connection((host, int(port)))
            
            self.send_response(200, "Connection Established")
            self.end_headers()

            self.connection.setblocking(False)
            target_sock.setblocking(False)

            sockets = [self.connection, target_sock]
            while True:
                # Wait for data from either side
                r, _, _ = select.select(sockets, [], [], 10)
                if not r: 
                    break # Timeout
                
                if self.connection in r:
                    data = self.connection.recv(8192)
                    if not data: break
                    target_sock.sendall(data)
                
                if target_sock in r:
                    data = target_sock.recv(8192)
                    if not data: break
                    self.connection.sendall(data)
                    
        except Exception as e:
            pass
        finally:
            try: target_sock.close()
            except: pass
            try: self.connection.close()
            except: pass

    def do_POST(self):
        self._handle_http_request()
        
    def do_GET(self):
        self._handle_http_request()
        
    def _handle_http_request(self):
        url = self.path
        
        # [REVERSE PROXY MODE] If request is completion, automatically forward to TQ3 host
        if url == "/completion":
            host_name = "host.docker.internal"
            url = f"http://172.18.0.1:8085{self.path}"
        else:
            # Retrieve host from headers for FORWARD PROXY MODE
            host = self.headers.get('Host', '')
            if ':' in host:
                host_name, port = host.split(':', 1)
            else:
                host_name = host
                
            allowed = False
            for d in ALLOWED_DOMAINS:
                if host_name == d or host_name.endswith("." + d):
                    allowed = True
                    break
                    
            if not allowed:
                print(f"❌ [BLOCKED] HTTP connection to {host_name} was rejected!", flush=True)
                self.send_error(403, f"Domain {host_name} is strictly blocked by Zero-Cutloss Sovereign Gateway.")
                threading.Thread(target=send_telegram_alert, args=(host_name,)).start()
                return

        content_length = self.headers.get('Content-Length')
        if content_length:
            body = self.rfile.read(int(content_length))
        elif self.headers.get('Transfer-Encoding', '').lower() == 'chunked' or self.command in ('POST', 'PUT'):
            body = self.rfile.read()
        else:
            body = None
        
        headers = {k: v for k, v in self.headers.items() if k.lower() not in ('host', 'connection')}
        
        try:
            with requests.request(
                method=self.command,
                url=url,
                headers=headers,
                data=body,
                stream=True,
                timeout=120
            ) as resp:
                self.send_response(resp.status_code)
                for k, v in resp.headers.items():
                    if k.lower() not in ('transfer-encoding', 'connection', 'content-encoding'):
                        self.send_header(k, v)
                self.end_headers()
                
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        self.wfile.write(chunk)
                        self.wfile.flush()
        except Exception as e:
            print(f"❌ [PROXY_ERROR] Error calling {url}: {e}", flush=True)
            self.send_error(502, f"Bad Gateway: {e}")

if __name__ == "__main__":
    PORT = 8080
    print(f"🛡️ Starting Intermediate API Gateway on port {PORT}", flush=True)
    print(f"🔒 Filter network: Allowing {ALLOWED_DOMAINS}, cutting off all other connections.", flush=True)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), APIFilterProxy)
    server.serve_forever()
