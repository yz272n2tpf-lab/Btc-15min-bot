"""Local TEST transport only: use the workspace's standard HTTPS proxy for GETs.

Serves the candidate's exact assets/guards. No producer or deployment imports.
Production hosting uses its existing direct HTTPS transport, unchanged.
"""
import importlib.util
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen

source=Path(__file__).resolve().parents[2]/'cockpit_candidate/server.py'
spec=importlib.util.spec_from_file_location('candidate_host',source)
host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)


class Reader(host.CandidateHandler):
    def relay(self, route, nonce):
        scalp=route=='/scalp/ladders'
        upstream='https://v81-live-diagnostics-production.up.railway.app/ladders' if scalp else 'https://'+host.MAIN_HOST+route
        headers={'X-BTC15-Information-Nonce':nonce} if route=='/information' and nonce else {}
        try:
            response=urlopen(Request(upstream,headers=headers,method='GET'),timeout=8)
        except HTTPError as e:response=e
        except (URLError,TimeoutError):return self.fail(502,'LOCAL_PROXY_TRANSPORT_UNAVAILABLE')
        with response:
            body=response.read(2*1024*1024+1)
            if len(body)>2*1024*1024:return self.fail(502,'LOCAL_RESPONSE_TOO_LARGE')
            self.reply(response.status,body,[(k,v) for k,v in response.headers.items() if k.lower() in host.RESPONSE_HEADERS])


if __name__=='__main__':
    server=host.CandidateServer(('127.0.0.1',8765));server.RequestHandlerClass=Reader
    print('BTC15 isolated candidate: local proxy-aware TEST transport; GET only',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
