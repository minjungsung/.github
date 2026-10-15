import io
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from scripts.model_gateway_relay import serve, validate_endpoint


class RelayTests(unittest.TestCase):
    def test_insecure_and_embedded_credentials_are_rejected(self):
        for endpoint in ['http://example.invalid/responses', 'https://secret@example.invalid/responses']:
            with self.assertRaises(ValueError):
                validate_endpoint(endpoint)

    def test_authenticated_forwarding_and_anonymous_rejection(self):
        servers = []
        requests = []

        def server(address, handler):
            instance = ThreadingHTTPServer(('127.0.0.1', 0), handler)
            servers.append(instance)
            return instance

        class Response(io.BytesIO):
            status = 200
            headers = {'Content-Type': 'text/event-stream'}

        def upstream(request, **kwargs):
            requests.append(request)
            return Response(b'data: {"status":"completed"}\n\n')

        with patch('scripts.model_gateway_relay.ThreadingHTTPServer', server), patch('scripts.model_gateway_relay.urlopen', upstream):
            thread = threading.Thread(target=serve, args=('https://example.invalid/responses', 'enterprise.token', 'local-key', 0), daemon=True)
            thread.start()
            import time
            for attempt in range(100):
                if servers:
                    break
                time.sleep(.01)
            self.assertTrue(servers)
            instance = servers[0]
            endpoint = 'http://127.0.0.1:' + str(instance.server_port) + '/responses'
            try:
                with self.assertRaises(HTTPError) as rejected:
                    urlopen(Request(endpoint, data=b'{}'), timeout=2)
                self.assertEqual(rejected.exception.code, 403)
                self.assertEqual(requests, [])
                request = Request(endpoint, data=b'{"stream":true}', headers={'Authorization': 'Bearer local-key'})
                with urlopen(request, timeout=2) as response:
                    self.assertIn(b'completed', response.read())
                self.assertEqual(requests[0].get_header('Authorization'), 'Bearer enterprise.token')
                self.assertEqual(requests[0].data, b'{"stream":true}')
                self.assertEqual(instance.server_address[0], '127.0.0.1')
            finally:
                instance.shutdown()
                instance.server_close()
                thread.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
