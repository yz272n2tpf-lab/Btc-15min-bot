#!/usr/bin/env python3
"""Serve the qualified recovered dashboard from its actual generated directory."""
import http.server,os,socketserver
from pathlib import Path
import BTC15_RECOVERED_V11_FINAL_PROBABILITY_V1 as candidate

html=candidate.build_dashboard().resolve()
root=html.parent
if not html.exists():
    raise SystemExit("PREVIEW REJECTED: generated dashboard missing")
if html.name!="BTC_Kalshi_App_Live_v13.html":
    raise SystemExit("PREVIEW REJECTED: unexpected artifact identity")
os.chdir(root)
port=int(os.environ.get("PORT","8080"))
print(f"BTC15 QUALIFIED PREVIEW ROOT | {root} | ARTIFACT {html.name}",flush=True)
class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?",1)[0]=="/":
            self.path="/"+html.name
        return super().do_GET()
with socketserver.TCPServer(("0.0.0.0",port),Handler) as server:
    print(f"BTC15 QUALIFIED PREVIEW SERVING | port={port}",flush=True)
    server.serve_forever()
