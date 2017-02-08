import socket

try:
    import sys
    from sys import print_exception #micropython specific
except ImportError:
    import traceback
    print_exception = lambda exc: traceback.print_exc()
    

from time import monotonic as time

DEBUG = True

__all__ = ["TCPServer","StreamRequestHandler"]

class TCPServer(object):
    timeout = None
    address_family = socket.AF_INET
    socket_type = socket.SOCK_STREAM
    request_queue_size = 5
    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass, bind_and_activate=True):
        #BaseServer.__init__(self, server_address, RequestHandlerClass)
        self.server_address = server_address
        self.RequestHandlerClass = RequestHandlerClass
        self.__is_shut_down = None #FIXME threading.Event()
        self.__shutdown_request = False
        
        self.socket = socket.socket(self.address_family,
                                    self.socket_type)
        if bind_and_activate:
            try:
                self.server_bind()
                self.server_activate()
            except:
                self.server_close()
                raise

    #inserted from old BaseServer
    def __enter__(self):
        return self

    #inserted from old BaseServer
    def __exit__(self, *args):
        self.server_close()
        
    #inserted from old BaseServer
    def serve_forever(self, poll_interval=0.5):
        #FIXME self.__is_shut_down.clear()
        try:
            while not self.__shutdown_request:
                self._handle_request_noblock()
                self.service_actions()
        finally:
            self.__shutdown_request = False
            #FIXME self.__is_shut_down.set()
    
    #inserted from old BaseServer
    def shutdown(self):
        self.__shutdown_request = True
        #FIXME self.__is_shut_down.wait()

    #inserted from old BaseServer
    def service_actions(self):
        pass
    
    #inserted from old BaseServer
    def verify_request(self, request, client_address):
        return True
        
    #inserted from old BaseServer
#    def handle_request(self):
#        #FIXME timeout = self.socket.gettimeout()
#        if timeout is None:
#            timeout = self.timeout
#        elif self.timeout is not None:
#            timeout = min(timeout, self.timeout)
#        if timeout is not None:
#            deadline = time() + timeout

#        while True:
#            ready = selector.select(timeout)
#            if ready:
#                return self._handle_request_noblock()
#            else:
#                if timeout is not None:
#                    timeout = deadline - time()
#                    if timeout < 0:
#                        return self.handle_timeout()
    
    #inserted from old BaseServer
    def _handle_request_noblock(self):
        if DEBUG:
            print("INSIDE TCPServer._handle_request_noblock")
            try:
                from micropython import mem_info
                mem_info()
            except ImportError:
                pass
        try:
            request, client_address = self.get_request()
        except OSError:
            return
        if self.verify_request(request, client_address):
            try:
                self.process_request(request, client_address)
            except Exception as exc:
                self._exc = exc
                self.handle_error(request, client_address)
                self.shutdown_request(request)
        else:
            self.shutdown_request(request)
    
    #inserted from old BaseServer
    def process_request(self, request, client_address):
        self.finish_request(request, client_address)
        self.shutdown_request(request)
    
    def handle_timeout(self):
        pass
    
    #inserted from old BaseServer
    def handle_error(self, request, client_address):
        print('-'*40, file=sys.stderr)
        print('Exception happened during processing of request from',
            client_address, file=sys.stderr)
        print_exception(self._exc,sys.stderr)
        print('-'*40, file=sys.stderr)
    
    #inserted from old BaseServer
    def finish_request(self, request, client_address):
        self.RequestHandlerClass(request, client_address, self)

    #inserted from old BaseServer
    def shutdown_request(self, request):
        self.close_request(request)

    def server_bind(self):
        if self.allow_reuse_address:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        host, port = self.server_address
        addr = socket.getaddrinfo(host,port)[0][-1]
        self.socket.bind(addr)
        self.server_address = addr

    def server_activate(self):
        self.socket.listen(self.request_queue_size)

    def server_close(self):
        self.socket.close()

    def get_request(self):
        return self.socket.accept()

    def shutdown_request(self, request):
        try:
            #explicitly shutdown.  socket.close() merely releases
            #the socket and waits for GC to perform the actual close.
            request.shutdown(socket.SHUT_WR)
        except OSError:
            pass #some platforms may raise ENOTCONN here
        self.close_request(request)

    def close_request(self, request):
        request.close()

class StreamRequestHandler(object):
    rbufsize = -1
    wbufsize = -1

    timeout = None
    
    def __init__(self, request, client_address, server):
        self.request = request
        self.client_address = client_address
        self.server = server
        self.setup()
        try:
            self.handle()
        finally:
            self.finish()

    def setup(self):
        self.connection = self.request
        if self.timeout is not None:
            self.connection.settimeout(self.timeout)
        self.rfile = self.connection.makefile('rb', self.rbufsize)
        if self.wbufsize == 0:
            #FIXME self.wfile = _SocketWriter(self.connection)
            raise NotImplementedError
        else:
            self.wfile = self.connection.makefile('wb', self.wbufsize)

    def finish(self):
        if not self.wfile.closed:
            try:
                self.wfile.flush()
            except socket.error:
                # A final socket error may have occurred here, such as
                # the local error ECONNABORTED.
                pass
        self.wfile.close()
        self.rfile.close()

################################################################################
# TEST CODE
################################################################################
#if __name__ == "__main__":
#    #configure an HTTP server
#    SERVER_IP = '0.0.0.0'
#    SERVER_PORT = 80
#    class HTTPHandler(StreamRequestHandler):
#        def handle(self):
#            # self.rfile is a file-like object created by the handler;
#            # we can now use e.g. readline() instead of raw recv() calls
#            self.data = self.rfile.readline().strip()
#            print("{} wrote:".format(self.client_address[0]))
#            print(self.data)
#            # Likewise, self.wfile is a file-like object used to write back
#            # to the client
#            self.wfile.write(self.data.upper())
#    # Create the server, binding to localhost on port 9999
#    server = TCPServer((SERVER_IP, SERVER_PORT), HTTPHandler)
#    
#    # Activate the server; this will keep running until you
#    # interrupt the program with Ctrl-C
#    server.serve_forever()
