from .options import PORT, QUIET
from .ogg import parse_comment, parse_pages
import functools
import http.server
import socketserver
import types
import io
import os


def create_request_handler(callbacks):
    """Creates an HTTP request handler with a custom callback"""

    class TraktorHandler(http.server.BaseHTTPRequestHandler):
        """Simpler handler for Traktor requests."""

        def do_SOURCE(self):
            """
            Implement handler for SOURCE requests which Traktor and older
            icecast source cilents send data via a special SOURCE verb.
            """
            # we send response
            self.send_response(200)
            # and headers
            self.end_headers()

            # and now the streaming begins
            for packet in parse_pages(self.rfile):
                walker = io.BytesIO(packet)
                if packet[:7] == b"\x03vorbis":
                    walker.seek(7, os.SEEK_CUR)  # jump over header name
                    metadata = parse_comment(walker)

                    for callback in callbacks:
                        callback(metadata)

        def log_request(self, code='-', size='-'):
            """Do not log messages about HTTP requests."""
            pass

        def log_error(self, format, *args):
            """Do not log messages about HTTP requests."""
            pass

    return TraktorHandler

def _get_track_string(data):
    info = dict(data)
    track_string = f'{info.get("artist", "")} - {info.get("title", "")}'
    return track_string if len(track_string) > 3 else ''

def _output_to_console(data):
    track_string = _get_track_string(data)
    if track_string:
        print(track_string)

def _output_to_file(data, outfile):
    with open(outfile, 'w') as f:
        f.write(f'{_get_track_string(data)}\n')

class Listener():
    """Listens to Traktor broadcast, given a port."""

    def __init__(self, port=PORT, quiet=QUIET, outfile=None, custom_callback=None):
        self.port = port
        self.quiet = quiet
        self.outfile = outfile
        self.custom_callback = custom_callback

    def start(self):
        """Start listening to Traktor broadcast."""

        callbacks = []

        if not self.quiet:
            print(f'Listening on port {self.port}.')
            if self.outfile:
                print(f'Outputting to {self.outfile}')
            callbacks.append(_output_to_console)

        if self.outfile:
            callbacks.append(functools.partial(_output_to_file, outfile=self.outfile))

        if self.custom_callback:
            callbacks.append(self.custom_callback)

        # create a request handler with appropriate callback
        handler = create_request_handler(callbacks=callbacks)

        with socketserver.TCPServer(('', self.port), handler) as httpd:
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                httpd.server_close()
