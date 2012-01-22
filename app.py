# -*- coding: utf-8 -
"""Tornado handler for Server-Sent Events"""

import tornado.web

import tornado.web
import tornado.ioloop
import tornado.iostream
import tornado.escape
import tornado.template
import tornado.options

from tornado.options import define, options

define("port", default=8888, help="run on the given port", type=int)

import logging
import os
import time

import redis.client

import simplejson as json

# Max number of timeout events for the handler
MAX_TIMEOUTS = 15

# Set of SSEHandlers that will respond when new logs are entered
listeners = set()

class SSEHandler(tornado.web.RequestHandler):
    def initialize(self):
        self.set_header('Content-Type', 'text/event-stream')
        self.set_header('Cache-Control', 'no-cache')
            
    def emit(self, data, event=None):
        """
        Actually emits the data to the waiting JS
        """
        response = u''
        encoded_data = json.dumps(data)
        if event != None:
            response += u'event: ' + unicode(event).strip() + u'\n'
                
        response += u'data: ' + encoded_data.strip() + u'\n\n'

        self.write(response)
        self.flush()

class LogHandler(SSEHandler):
    """
    JS requests to be pushed updates
    """
    @tornado.web.asynchronous
    def get(self):
        listeners.add(self)
        
    def _on_timeout(self, i):
        if self.request.connection.stream.closed():
            return
        
        if i < MAX_TIMEOUTS:
            tornado.ioloop.IOLoop.instance().add_timeout(time.time() + 1, lambda: self._on_timeout(i + 1))
        else:
            self.finish()
        
    @tornado.web.asynchronous
    def post(self):
        listeners.add(self)
        tornado.ioloop.IOLoop.instance().add_timeout(time.time() + 1, lambda: self._on_timeout(1))

class MainHander(tornado.web.RequestHandler):
    """
    Renders the html with JS to connect to the logger.
    """
    def get(self):
        return self.render("base.html")

class TornadoPubSub(redis.client.PubSub):
    """
    PubSub handler that uses the IOLoop from tornado to read published messages
    """
    _stream = None
    def listen(self):
        """
        Listen for messages by telling IOLoop what to call when data is there.
        """
        if not self._stream:
            socket = self.connection._sock
            self._stream = tornado.iostream.IOStream(socket)
            self._stream.read_until('\r\n', self.process_response)

    def process_response(self, data):
        """
        Called by IOLoop when data is read.
        """
        # Pretty fragile here. @TODO: figure out how to turn socket into
        # blocking until the mulk-bulk message is completely read.
        if data[0] == 'm':
            self._stream.read_bytes(2, lambda x: self._stream.read_until('}\r\n', self.read_json_message))
        else:
            self._stream.read_until('\r\n', self.process_response)

    def read_json_message(self, data):
        """
        Reads redis protocol and gets the json message
        """
        message = json.loads(data.split('\n')[-2])
        for listener in listeners:
            listener.emit(message)

        self._stream.read_until('\r\n', self.process_response)

class RealtimeLogApplication(tornado.web.Application):
    """
    Tornado Application for powering Elva RealtimeLog
    """
    def __init__(self):
        routes = [
            (r'/', MainHander),
            (r'/events', LogHandler)
            ]

        settings = dict(
            static_path=os.path.join(os.path.dirname(__file__), 'static'),
            template_path=os.path.join(os.path.dirname(__file__), 'templates'))
        logging_config = {
            'format': "%(asctime)s %(name)s <%(levelname)s>: %(message)s",
            'level': logging.INFO
            }
        logging.basicConfig(**logging_config)

        tornado.web.Application.__init__(self, routes, **settings)


routes = [
    (r'/', MainHander),
    (r'/events', LogHandler)
]

if __name__ in ('main', '__main__'):
    tornado.options.parse_command_line()
    app = RealtimeLogApplication()
    
    app.listen(options.port)

    # Redis connection
    connection = redis.client.Redis()

    # register PubSub
    pubsub_client = TornadoPubSub(connection.connection_pool)
    pubsub_client.subscribe(['my:channel'])
    pubsub_client.listen()

    tornado.ioloop.IOLoop.instance().start()
