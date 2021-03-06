from .options import PORT, QUIET
from .ogg import parse_comment, parse_pages
import functools
import http.server
import socketserver
import pathlib
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
    outfile.write(f'{_get_track_string(data)}\n')
    outfile.flush()

class Listener():
    """Listens to Traktor broadcast, given a port."""

    def __init__(self, port=PORT, quiet=QUIET, outfile=None, custom_callback=None):
        self.port = port
        self.quiet = quiet
        self.outfile = outfile
        self.custom_callback = custom_callback

    def _create_outfile(self):
        if not self.outfile:
            return
        outpath = pathlib.Path(self.outfile)
        outpath.parent.mkdir(parents=True, exist_ok=True)
        outpath.touch(exist_ok=True)

        if not outpath.is_file():
            print(f'{self.outfile} is a directory!')
            raise IsADirectoryError

        self.output_file = open(outpath, "a")

    def start(self):
        """Start listening to Traktor broadcast."""

        callbacks = []

        if not self.quiet:
            print(f'Listening on port {self.port}.')
            if self.outfile:
                print(f'Outputting to {self.outfile}')
            callbacks.append(_output_to_console)

        if self.outfile:
            try:
                self._create_outfile()
                callbacks.append(functools.partial(_output_to_file, outfile=self.output_file))
            except:
                print(f'Error encountered while trying to write to {self.outfile}.')
                return

        if self.custom_callback:
            callbacks.append(self.custom_callback)

        # create a request handler with appropriate callback
        handler = create_request_handler(callbacks=callbacks)

        with socketserver.TCPServer(('', self.port), handler) as httpd:
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                httpd.server_close()
