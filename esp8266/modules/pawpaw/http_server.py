import time, socket

try:
    from collections import OrderedDict
except ImportError: 
    from ucollections import OrderedDict #micrpython specific

from .socketserver import TCPServer, StreamRequestHandler
from .template_engine import Template, LazyTemplate

DEBUG = False
#DEBUG = True
################################################################################
# Classes
class HttpRequest(object):
    __slots__ = 'method','path','args','headers'
    
class HttpRequestHandler(StreamRequestHandler):
    handler_registry = OrderedDict()
    newline = "\r\n"
            
    def setup(self):
        StreamRequestHandler.setup(self)
        
    def render_template(self, tmp,
                        status  = "HTTP/1.1 200 OK",
                        headers = None):
        if DEBUG:
            print("INSIDE METHOD name='%s' " % ('render_template'))
        if headers is None:
            headers = OrderedDict()
        headers['Content-Type'] = headers.get('Content-Type', 'text/html')
        # test if we can iterate over tmp to produce output text
        # the follow is a hueristic iterablility test that works for generators
        # and other iterable containers on upython
        tmp_isiterable = False
        try:
            tmp.__next__
            tmp is tmp.__iter__()
            #tests pass here
            tmp_isiterable = True
        except AttributeError:
            pass
        if tmp_isiterable:
            #use chunked transfer coding for an iterable template
            headers['Transfer-Encoding'] = 'chunked'
            #send headers
            self._send_response_headers(status, headers)
            #send in chunks
            for chunk in tmp:
                self._send_chunk(chunk)
            #IMPORTANT terminate chunked transfer
            self._send_line("0")
            self._send_line("")
        else:
            content = tmp.render().read() #read the StringIO or stream interface
            #compute and send using Content-Length
            headers['Content-Length'] = len(content)
            #send headers
            self._send_response_headers(status, headers)
            #send all at once
            self._send(content)
            
    def _send_response_headers(self, status, headers):
        if DEBUG:
            print("INSIDE METHOD name='%s' " % ('_send_response_headers'))
        self._send_line(status)
        for key, val in headers.items():
            line = "%s: %s" % (key,val)
            self._send_line(line)
        #IMPORTANT final blank line
        self._send_line("")
        
    def _send(self, content):
        if DEBUG:
            print("INSIDE METHOD name='%s' " % ('_send'))
        self.wfile.write(bytes(content,'utf8'))
        self.wfile.flush()
        
    def _send_line(self, line):
        if DEBUG:
            print("INSIDE METHOD name='%s'" % ('_send_line'))
        line = line.rstrip()
        line += self.newline
        if DEBUG:
            print("LINE: %r" % line)
        self.wfile.write(bytes("%s" % (line,),'utf8'))
        self.wfile.flush()
        
    def _send_chunk(self, chunk):
        if DEBUG:
            print("INSIDE METHOD name='%s'" % ('_send_chunk'))
        self.wfile.write(bytes("%X%s" % (len(chunk),self.newline),'utf8'))
        self.wfile.write(bytes("%s%s" % (chunk,self.newline),'utf8'))
        self.wfile.flush()
    
    def handle(self):
        global DEBUG
        # self.rfile is a file-like object created by the handler;
        # we can now use e.g. readline() instead of raw recv() calls
        #parse the request header
        request_line = str(self.rfile.readline(),'utf8').strip()
        if DEBUG:
            print("CLIENT: %s" % request_line)
        method, req, protocol = request_line.split()
        #split off any params if they exist
        req = req.split("?")
        req_path = req[0]
        params = {}
        if len(req) == 2:
            items = req[1].split("&")
            for item in items:
                item = item.split("=")
                if len(item) == 1:
                    params[item[0]] = None
                elif len(item) == 2:
                    params[item[0]] = item[1]
        #read the remaining request headers
        headers = OrderedDict()
        while True:
            line = str(self.rfile.readline(),'utf8').strip()
            if DEBUG:
                print("CLIENT: %r" % line)
            if not line or line == b'\r\n':
                break
            key, val = line.split(':',1)
            headers[key] = val
        #construct the request object, similar to Flask names
        self.request = HttpRequest()
        self.request.method  = method
        self.request.path    = req_path
        self.request.args    = params
        self.request.headers = headers
        #dispatch request to registered handler or default
        key = "%s %s" % (method, req_path)
        handler = self.handler_registry.get(key)
        if handler is None:
            handler = self.__class__.handle_default
        if DEBUG:
            print("DISPATCHING REQUEST key='%s' to handler=%r" % (key,handler))
        #call the handler
        handler(self)
        
    def handle_default(self):
        if DEBUG:
            print("INSIDE HANDLER name='%s' " % ('handle_default'))
        tmp = LazyTemplate.from_file("templates/404.html_template")
        self.render_template(tmp)

################################################################################
# TEST  CODE
################################################################################
#if __name__ == "__main__":
#    SERVER_IP   = '0.0.0.0'
#    SERVER_PORT = 9999
#    
#    #---------------------------------------------------------------------------
#    class TestPawpawApp(HttpRequestHandler):
#        @route("/")
#        def index(self):
#            if DEBUG:
#                print("INSIDE HANDLER name='%s' " % ('index'))
#            try:
#                from collections import OrderedDict
#            except ImportError: 
#                from ucollections import OrderedDict #micropython specific
#            import mock_machine as machine
#    
#            #test a complete template
#            pins_tmp   = LazyTemplate.from_file("templates/pins.html_template")
#            ptr_tmp    =     Template.from_file("templates/pins_table_row.html_template")
#            pins_jstmp = LazyTemplate.from_file("templates/pins.js_template")
#            
#            PIN_NUMBERS = (0, 2, 4, 5, 12, 13, 14, 15)
#            PINS = OrderedDict((i,machine.Pin(i, machine.Pin.IN)) for i in PIN_NUMBERS)
#            PINS[0].value = True
#            PINS[5].value = True
#            #we make table content a generator that produces one row per iteration
#            def gen_table_content(pins):
#                for pin_num, pin in pins.items():
#                    ptr_tmp.format(pin_id = str(pin),
#                                   pin_value = 'HIGH' if pin.value() else 'LOW',
#                                  )
#                    for line in ptr_tmp.render():
#                        yield line
#            pins_jstmp.format(server_addr = "0.0.0.0")
#            pins_tmp.format(table_content = gen_table_content(PINS),
#                            comment='This is a test page!',
#                            javascript = pins_jstmp)
#            #finally render the view
#            self.render_template(pins_tmp)
#    #---------------------------------------------------------------------------
#    # Create the server, binding to localhost on port 9999
#    server = TCPServer((SERVER_IP, SERVER_PORT), TestPawpawApp)

#    # Activate the server; this will keep running until you
#    # interrupt the program with Ctrl-C
#    server.serve_forever()
