"""Original isolated information service plus ephemeral read-only revalidation."""

def main():
    # The original CPU/memory/credential isolation remains in force.
    from btc15_information_worker_v1 import configure
    configure()
    import json
    import os
    from pathlib import Path
    import threading
    import time
    from urllib.request import urlopen
    import btc15_information_service_v1 as service
    from btc15_v2_product.revalidation import Revalidator
    from btc15_information_v1 import pack
    revalidator=Revalidator()
    changed=threading.Condition()
    root=Path(os.environ['BTC15_LADDER_DATA_ROOT'])
    original_server=service.server_for
    def server_for(*args,**kwargs):
        server=original_server(*args,**kwargs)
        original_get=server.RequestHandlerClass.do_GET
        def do_GET(handler):
            from urllib.parse import urlparse,parse_qs
            requested=urlparse(handler.path)
            if requested.path!='/revalidation':return original_get(handler)
            desired=parse_qs(requested.query).get('binding',[None])[0]
            if desired:
                # A new native commit with only milliseconds on its old source
                # lease must not race the independent sampler. Wait for its
                # already-running read-only work; HTTP cannot trigger inference.
                def matching():
                    return revalidator.latest and json.loads(revalidator.latest).get('binding')==desired
                with changed:changed.wait_for(matching,timeout=.2)
            raw=revalidator.latest or pack(dict(status='PENDING',reason='REVALIDATION_STARTING'))
            handler.send_response(200);handler.send_header('Content-Type','application/json')
            handler.send_header('Cache-Control','no-store');handler.send_header('Content-Length',str(len(raw)))
            handler.end_headers()
            try:handler.wfile.write(raw)
            except (BrokenPipeError,ConnectionResetError):pass
        server.RequestHandlerClass.do_GET=do_GET
        return server
    service.server_for=server_for
    def sample():
        from btc15_v2_product.revalidation import binding
        while True:
            started=time.monotonic();v=None
            try:
                raw=(root/'main.json').read_bytes()
                if len(raw)>524288:raise ValueError('OVERSIZE_NATIVE_VIEW')
                v=json.loads(raw)
                with urlopen('http://127.0.0.1:8766/revalidation-input',timeout=.4) as response:
                    data=response.read(524289)
                if len(data)>524288:raise ValueError('OVERSIZE_REVALIDATION_INPUT')
                source=json.loads(data)
                revalidator.step(v,source)
            except Exception:
                if v is not None:revalidator.unavailable(v,'REVALIDATION_INPUT_UNAVAILABLE')
            with changed:changed.notify_all()
            time.sleep(max(.01,.1-(time.monotonic()-started)))
    threading.Thread(target=sample,daemon=True,name='read-only-confirmation').start()
    service.main()


if __name__=='__main__':main()
