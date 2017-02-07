import time
try:
    from collections import OrderedDict
except ImportError: 
    from ucollections import OrderedDict #micrpython specific

from .socketserver    import TCPServer, StreamRequestHandler
from .http_server     import HttpRequestHandler
from .template_engine import Template, LazyTemplate

DEBUG = True
################################################################################
# DECORATORS
#-------------------------------------------------------------------------------
class route(object):
    #a method decorator to automate handling of HTTP route dispatching
    def __init__(self, path, methods = None):
        #this runs upon decoration
        self.path = path
        if methods is None:
            methods = ["GET"]
        self.req_methods = methods
        
    def __call__(self, m):
        #this runs upon decoration immediately after __init__
        def wrapped_m(*args): #pull in request object
            return m(*args)
        #add the wrapped method to the handler_registry with path as key
        wrapped_m.route_handles = []
        for req_method in self.req_methods:
            key = "%s %s" % (req_method, self.path)
            wrapped_m.route_handles.append(key)
        return wrapped_m

################################################################################
# Classes
class WebApp(object):
    class RoutingRequestHandler(HttpRequestHandler):
            pass

    def __init__(self, server_addr, server_port):
        # Create the server, binding to localhost on port 9999
        self.server_addr = server_addr
        self.server_port = server_port
        self._register_routes()
        self.server = TCPServer((self.server_addr, self.server_port), self.RoutingRequestHandler)
        
    def _register_routes(self):
        if DEBUG:
            print("@PawpawApp.register_routes")
        #a class decorator to automate handling of HTTP route dispatching
        for name, method in type(self).__dict__.items():
            if hasattr(method, "route_handles"):
                # transform the method into a handler
                # (behaves like method of RoutingRequestHandler)
                def route_handler(context,app=self):
                    return method(app,context)
                if DEBUG:
                    print("@PawpawApp.register_routes REGISTERING HANDLER METHOD '%s'" % (name,))
                for key in method.route_handles:
                    self.RoutingRequestHandler.handler_registry[key] = route_handler

    def serve_forever(self):
        # Activate the server; this will keep running until you
        # interrupt the program with Ctrl-C
        self.server.serve_forever()

################################################################################
# TEST  CODE
################################################################################
#if __name__ == "__main__":
#    try:
#        from collections import OrderedDict
#    except ImportError: 
#        from ucollections import OrderedDict #micropython specific
#    
#    import mock_machine as machine
#    
#    SERVER_IP   = '0.0.0.0'
#    SERVER_PORT = 9999
#    PIN_NUMBERS = (0, 2, 4, 5, 12, 13, 14, 15)
#    PINS = OrderedDict((i,machine.Pin(i, machine.Pin.IN)) for i in PIN_NUMBERS)
#    
#    #---------------------------------------------------------------------------
#    class PinServer(PawpawApp):
#        @route("/", methods=['GET','POST'])
#        def pins(self, context):
#            if DEBUG:
#                print("INSIDE ROUTE HANDLER name='%s' " % ('pins'))
#            
#    
#            #open the template files
#            pins_tmp   = LazyTemplate.from_file("templates/pins.html_template")
#            ptr_tmp    =     Template.from_file("templates/pins_table_row.html_template")
#            pins_jstmp = LazyTemplate.from_file("templates/pins.js_template")
#            comment = ""
#           
#            if context.request.method == 'POST':
#                if DEBUG:
#                    print("HANDLING POST REQUEST: args = %r" % context.request.args)
#                #get the button id from the params and pull out the corresponding pin object
#                btn_id = context.request.args['btn_id']
#                pin_id = int(btn_id[3:])#pattern is "btn\d\d"
#                pin = PINS[pin_id]
#                pin.value = not pin.value() #invert the pin state
#                comment = "Toggled pin %d" % pin_id
#                
#            #we make table content a generator that produces one row per iteration
#            def gen_table_content(pins):
#                for pin_num, pin in pins.items():
#                    ptr_tmp.format(pin_id = str(pin),
#                                   pin_value = 'HIGH' if pin.value() else 'LOW',
#                                  )
#                    for line in ptr_tmp.render():
#                        yield line
#            server_base_url = "%s:%s" % (self.server_addr,self.server_port)
#            pins_jstmp.format(server_base_url = server_base_url)
#            pins_tmp.format(table_content = gen_table_content(PINS),
#                            comment=comment,
#                            javascript = pins_jstmp)
#            #finally render the view
#            context.render_template(pins_tmp)
#    #---------------------------------------------------------------------------
#    # Create application instance binding to localhost on port 9999
#    app = PinServer(server_addr = '0.0.0.0',
#                    server_port = 9999,
#                   )

#    # Activate the server; this will keep running until you
#    # interrupt the program with Ctrl-C
#    app.serve_forever()
