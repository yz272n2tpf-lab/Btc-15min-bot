"""Fixed source routing preserves source bytes and clocks; never orders."""
import http.client
import threading
import unittest
from unittest.mock import patch
import server


class ProductionRelay(unittest.TestCase):
    def test_fixed_sources_preserve_original_publication(self):
        body=b'{"status":"AVAILABLE","published_ts":123,"expires_at":124,"orders":false}'
        calls=[]
        class Upstream:
            status=200
            def __init__(self,host,**kwargs):self.host=host
            def request(self,method,path,headers):calls.append((self.host,method,path,headers))
            def getresponse(self):return self
            def read(self):return body
            def getheaders(self):return [('Content-Type','application/json'),('Date','Thu, 08 Oct 2026 23:00:00 GMT')]
            def close(self):pass
        host=server.CandidateServer(('127.0.0.1',0))
        thread=threading.Thread(target=host.serve_forever,daemon=True);thread.start()
        try:
            with patch.object(server.http.client,'HTTPSConnection',Upstream):
                for route,target in [('/ladders',server.MAIN_HOST),('/scalp/ladders','v81-live-diagnostics-production.up.railway.app')]:
                    conn=http.client.HTTPConnection('127.0.0.1',host.server_port)
                    conn.request('GET',route);response=conn.getresponse()
                    self.assertEqual(response.status,200);self.assertEqual(response.read(),body)
                    self.assertIn('no-store',response.getheader('Cache-Control'))
                    self.assertEqual(calls[-1][:3],(target,'GET','/ladders'))
                    self.assertNotIn('Authorization',calls[-1][3]);conn.close()
                before=len(calls)
                conn=http.client.HTTPConnection('127.0.0.1',host.server_port)
                conn.request('GET','/scalp/ladders?url=https://example.com')
                response=conn.getresponse();self.assertEqual(response.status,404);response.read();conn.close()
                self.assertEqual(len(calls),before)
        finally:host.shutdown();host.server_close();thread.join()


if __name__=='__main__':unittest.main()
