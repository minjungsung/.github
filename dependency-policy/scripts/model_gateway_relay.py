"""Root-owned, loopback-only Responses relay for enterprise bearer tokens.

The pinned Codex proxy accepts a restricted key alphabet. This relay holds the
real gateway credential outside the unprivileged application's process tree.
"""
import argparse
import json
import ssl
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def validate_endpoint(endpoint):
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("Gateway endpoint must be an HTTPS URL without embedded credentials")
    return endpoint


def serve(endpoint, credential, local_key, port, ca_pem=None):
    validate_endpoint(endpoint)
    if not credential or not local_key:
        raise ValueError("Both gateway and relay credentials are required")
    context = ssl.create_default_context()
    if ca_pem:
        context.load_verify_locations(cadata=ca_pem)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass  # Never log prompts, headers, endpoint identifiers or credentials.

        def do_POST(self):
            if self.path != "/responses" or self.headers.get("Authorization") != "Bearer " + local_key:
                self.send_error(403)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 32 * 1024 * 1024:
                    self.send_error(413)
                    return
                body = self.rfile.read(length)
                request = Request(endpoint, data=body, headers={
                    "Authorization": "Bearer " + credential,
                    "Content-Type": "application/json",
                    "Accept": self.headers.get("Accept", "application/json"),
                }, method="POST")
                upstream = urlopen(request, timeout=180, context=context)
            except HTTPError as error:
                self.send_error(error.code, "Gateway rejected the request")
                return
            except (ValueError, URLError, TimeoutError) as error:
                reason = error.reason if isinstance(error, URLError) else error
                category = "TLS verification failed" if isinstance(reason, ssl.SSLCertVerificationError) else type(reason).__name__
                print("Gateway connection category: " + category, flush=True)
                self.send_error(502, "Gateway connection failed: " + category)
                return
            with upstream:
                self.send_response(upstream.status)
                self.send_header("Content-Type", upstream.headers.get("Content-Type", "application/json"))
                self.send_header("Connection", "close")
                self.end_headers()
                try:
                    while chunk := upstream.read1(65536):
                        self.wfile.write(chunk)
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                self.close_connection = True

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    config = json.load(sys.stdin)
    serve(config["endpoint"], config["credential"], config["local-key"], args.port, config.get("ca-pem"))


if __name__ == "__main__":
    main()
