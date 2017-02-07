try:
    import re
except ImportError:
    import ure as re
    
try:
    from io import StringIO
except ImportError:
    from uio import StringIO
    
try:
    from collections import OrderedDict
except ImportError: 
    from ucollections import OrderedDict #micrpython specific
    
DEBUG = False
    
EXPRESSION_TAG_OPEN  = "{{"
EXPRESSION_TAG_CLOSE = "}}"

RE_INDENT = re.compile(r"^(\s*).*$")
RE_EXPRESSION_TAG = re.compile(r"{{\s(\w+)\s}}")

def scan_tag(text, at_pos = 0):
    global DEBUG
    tag_start_pos = text.find(EXPRESSION_TAG_OPEN, at_pos)
    if tag_start_pos == -1: #no tags found
        return (-1,-1, None)
    at_pos  = tag_start_pos + len(EXPRESSION_TAG_OPEN)
    tag_end_pos = text.find(EXPRESSION_TAG_CLOSE, at_pos) + len(EXPRESSION_TAG_CLOSE)
    if tag_end_pos == -1:
        raise SyntaxError("@pos %d: missing EXPRESSION_TAG_CLOSE '%r'" % (at_pos,EXPRESSION_TAG_CLOSE))
    tag = text[tag_start_pos : tag_end_pos]
    at_pos = tag_end_pos
    if DEBUG:
        print("@pos = %d: FOUND TAG: %s" % (at_pos,tag))
    m = RE_EXPRESSION_TAG.match(tag)
    if not m:
        raise SyntaxError("@pos %d: malformed tag '%s' needs to match '%r'" % (at_pos,tag, RE_EXPRESSION_TAG))
    name = m.group(1)
    return (tag_start_pos, tag_end_pos, name)

class BaseTemplate(object):
    def __init__(self, tag_replacements = None):
        if tag_replacements is None:
            tag_replacements = {}
        self._tag_replacements = tag_replacements
        
    def __str__(self):
        return self.render()
        
    def format(self, **kwargs):
        self._tag_replacements = kwargs
        return self
        
    def render(self):
        raise NotImplementedError
        
class Template(BaseTemplate):
    def __init__(self, text, tag_replacements = None):
        BaseTemplate.__init__(self, tag_replacements)
        self._text = text
        self._tag_locs = []
        self._scan_all_tags()
    
    def _scan_all_tags(self):
        #scan through all text and mark tag locations
        at_pos = 0
        while True:
            tag_start_pos, tag_end_pos, tag_name = scan_tag(self._text, at_pos = at_pos)
            if tag_start_pos == -1: #no more tags found
                break
            self._tag_locs.append((tag_start_pos, tag_end_pos, tag_name))
            at_pos = tag_end_pos #start again right after tag
            
    def render(self):
        buff = []
        at_pos = 0
        for tag_start_pos, tag_end_pos, tag_name in self._tag_locs:
            #see if a replacement has been registered for this tag_name
            rep = self._tag_replacements.get(tag_name)
            if not rep is None:
                lead_text = self._text[at_pos:tag_start_pos]
                if DEBUG:
                    print("@pos %d TEXT: %r" % (at_pos,lead_text))
                #put leading text into buffer
                buff.append(lead_text)
                at_pos = tag_start_pos
                if DEBUG:
                    print("@pos %d REPLACING TAG '%s' -> '%s'" % (at_pos,tag_name,rep))
                #splice in replacement
                buff.append(str(rep))
            else:
                #put leading text and tag inclusive into buffer
                buff.append(self._text[at_pos:tag_end_pos])
            at_pos = tag_end_pos
        #put trailing text into buffer
        buff.append(self._text[at_pos:])
        buff = "".join(buff)
        return StringIO(buff)
        
    @classmethod
    def from_file(cls, filename):
        return cls(text = open(filename,'r').read())
    
class LazyTemplate(BaseTemplate):
    """  A templating engine that allows chained lazy evaluation of 
         nested subtemplates.
    """
    # `__iter__` is a generator which evaluates 
    # `_replace_tags` which is itself a recursive generator thats scans 
    # each line replacing tags.  If a tag is encountered, then either the 
    # replacement is a string or it is a subtemplate.  If it is a string we 
    # just splice it inline.  For the subtemplate case we have to 
    # break the line, yield it, and stitch in all the lines that the 
    # subtemplate generates.  Finally we have to continue with the rest of 
    # the line occuring after the tag.  The upshot of all this crazyness is 
    # a very low RAM footprint since the whole document never needs to be in
    # memory.
    class SyntaxError(Exception):
        pass
        
    def __init__(self, textio,
                 tag_replacements = None,
                 newline = '\n',
                 ):
        BaseTemplate.__init__(self, tag_replacements)
        self._newline = newline
        self._line_num = 0
        self._current_indent = "" #should only hold whitespace chars
        self._textio = textio   #this is file-like
        self._gen_next = self._next_generator()
        
    def __del__(self):
        self.close()
        
    def __iter__(self):
        return self
                
    def __next__(self):
        return next(self._gen_next)
        
    def _next_generator(self):
        while True:
            line = self._textio.readline()
            if line == "":
                self.close()
                raise StopIteration
            self._line_num += 1
            #determine the indentation
            m = RE_INDENT.match(line)
            self._current_indent = m.group(1)
            #replace tags recursively, at start set remaining line to the whole
            for rep_line in self._replace_tags(line,line):
                #trim dangling whitespace from right and put back one newline
                yield rep_line.rstrip() + self._newline
    
    def __str__(self):
        return repr(self)
        
    def render(self):
        lines = list(self)
        self.close()
        return "".join(lines)
        
    def _replace_tags(self, line, rline):
        #NOTE this a a generator which yields when a 
        global DEBUG
        if DEBUG:
            print("LINE %d, indent %r: %r" % (self._line_num, self._current_indent, line))
        tag_start_pos, tag_end_pos, tag_name = scan_tag(rline)
        if tag_start_pos == -1: #no tags found
            if line:  #prevent empty lines from being sent
                yield line
            raise StopIteration
        #set up the remainder of the line
        rline = rline[tag_end_pos:]
        rep = self._tag_replacements.get(tag_name)
        if not rep is None:
            if DEBUG:
                print("REPLACING TAG '%s' -> '%s'" % (tag_name,rep))
            # test if we can iterate over rep to produce output text
            # the follow is a hueristic iterablility test that works for generators
            # and other iterable containers on upython
            rep_isiterable = False
            try:
                rep.__next__
                rep is rep.__iter__()
                #tests pass here
                rep_isiterable = True
            except AttributeError:
                pass
            if rep_isiterable:
                if DEBUG:
                    print("SPLICING IN ITERABLE")
                #we must chain in the sub-template
                part_line = line[:tag_start_pos] #text in current line
                #extract all the lines of the sub-template
                first_line = part_line + next(rep) #first line should already have indentation
                yield first_line
                for sub_line in rep:
                    #extend the current indentation to sub lines and strip newlines
                    yield self._current_indent + sub_line
                #reduce the line to the remaining portion
                line = rline.strip() #trim any dangling whitespace
                if DEBUG:
                    print("END SPLICING ITERABLE")
            else:
                rep = str(rep)
                #just a simple string replacement
                line = "".join((line[:tag_start_pos],rep,line[tag_end_pos:]))
        else:
            if DEBUG:
                print("UNRECOGNIZED TAG '%s'" % (tag_name,))
        #continue with the remaining line
        if DEBUG:
            print("RLINE: %r" % rline)
        for rep_line in self._replace_tags(line, rline):
            yield rep_line
    
    def close(self):
        self._textio.close()
        
    @classmethod
    def from_file(cls, filename):
        return cls(textio = open(filename,'r'))
        
    @classmethod
    def from_text(cls, text):
        return cls(textio = StringIO(text))
        
################################################################################
# TEST CODE
################################################################################
#if __name__ == "__main__":
#    try:
#        from collections import OrderedDict
#    except ImportError: 
#        from ucollections import OrderedDict #micropython specific
#    
#    import mock_machine as machine
#    
#    DEBUG = True
#    #test a complete template
#    pins_tmp   = LazyTemplate.from_file("templates/pins.html_template")
#    ptr_tmp    =     Template.from_file("templates/pins_table_row.html_template")
#    pins_jstmp = LazyTemplate.from_file("templates/pins.js_template")
#    
#    PIN_NUMBERS = (0, 2, 4, 5, 12, 13, 14, 15)
#    PINS = OrderedDict((i,machine.Pin(i, machine.Pin.IN)) for i in PIN_NUMBERS)
#    PINS[0].value = True
#    PINS[5].value = True
#    #we make table content a generator that produces one row per iteration
#    def gen_table_content(pins):
#        for pin_num, pin in pins.items():
#            ptr_tmp.format(pin_id = str(pin),
#                           pin_value = 'HIGH' if pin.value() else 'LOW',
#                          )
#            for line in ptr_tmp.render():
#                yield line
#   
#    pins_jstmp.format(server_addr = "0.0.0.0")
#    pins_tmp.format(table_content = gen_table_content(PINS),
#                    comment='This is a test page!',
#                    javascript = pins_jstmp)
#    #print(repr(pins_tmp.render()))
#    with open("doc.html",'w') as rnd:
#        for line in pins_tmp:
#            rnd.write(line)
################################################################################
# TEST OUTPUT
################################################################################
#    @pos = 23: FOUND TAG: {{ pin_id }}
#    @pos = 50: FOUND TAG: {{ pin_value }}
#    @pos = 103: FOUND TAG: {{ pin_id }}
#    LINE 1, indent '': '<!DOCTYPE html>\n'
#    LINE 2, indent '': '<html>\n'
#    LINE 3, indent '  ': '  <head> <title>ESP8266 Pins</title>\n'
#    LINE 4, indent '  ': '  </head>\n'
#    LINE 5, indent '  ': '  <body> <h1>ESP8266 Pins</h1>\n'
#    LINE 6, indent '    ': '    <table border="1"> \n'
#    LINE 7, indent '      ': '      <tr><th>Pin</th><th>Value</th></tr>\n'
#    LINE 8, indent '      ': '      {{ table_content }}\n'
#    @pos = 25: FOUND TAG: {{ table_content }}
#    REPLACING TAG 'table_content' -> '<generator object gen_table_content at 0x7fada6c4c870>'
#    SPLICING IN ITERABLE
#    @pos 0 TEXT: '<tr>\n  <td>'
#    @pos 11 REPLACING TAG 'pin_id' -> '0'
#    @pos 23 TEXT: '</td>\n  <td>'
#    @pos 35 REPLACING TAG 'pin_value' -> 'HIGH'
#    @pos 50 TEXT: '</td>\n  <td><button type="button" id="btn'
#    @pos 91 REPLACING TAG 'pin_id' -> '0'
#    @pos 0 TEXT: '<tr>\n  <td>'
#    @pos 11 REPLACING TAG 'pin_id' -> '2'
#    @pos 23 TEXT: '</td>\n  <td>'
#    @pos 35 REPLACING TAG 'pin_value' -> 'LOW'
#    @pos 50 TEXT: '</td>\n  <td><button type="button" id="btn'
#    @pos 91 REPLACING TAG 'pin_id' -> '2'
#    @pos 0 TEXT: '<tr>\n  <td>'
#    @pos 11 REPLACING TAG 'pin_id' -> '4'
#    @pos 23 TEXT: '</td>\n  <td>'
#    @pos 35 REPLACING TAG 'pin_value' -> 'LOW'
#    @pos 50 TEXT: '</td>\n  <td><button type="button" id="btn'
#    @pos 91 REPLACING TAG 'pin_id' -> '4'
#    @pos 0 TEXT: '<tr>\n  <td>'
#    @pos 11 REPLACING TAG 'pin_id' -> '5'
#    @pos 23 TEXT: '</td>\n  <td>'
#    @pos 35 REPLACING TAG 'pin_value' -> 'HIGH'
#    @pos 50 TEXT: '</td>\n  <td><button type="button" id="btn'
#    @pos 91 REPLACING TAG 'pin_id' -> '5'
#    @pos 0 TEXT: '<tr>\n  <td>'
#    @pos 11 REPLACING TAG 'pin_id' -> '12'
#    @pos 23 TEXT: '</td>\n  <td>'
#    @pos 35 REPLACING TAG 'pin_value' -> 'LOW'
#    @pos 50 TEXT: '</td>\n  <td><button type="button" id="btn'
#    @pos 91 REPLACING TAG 'pin_id' -> '12'
#    @pos 0 TEXT: '<tr>\n  <td>'
#    @pos 11 REPLACING TAG 'pin_id' -> '13'
#    @pos 23 TEXT: '</td>\n  <td>'
#    @pos 35 REPLACING TAG 'pin_value' -> 'LOW'
#    @pos 50 TEXT: '</td>\n  <td><button type="button" id="btn'
#    @pos 91 REPLACING TAG 'pin_id' -> '13'
#    @pos 0 TEXT: '<tr>\n  <td>'
#    @pos 11 REPLACING TAG 'pin_id' -> '14'
#    @pos 23 TEXT: '</td>\n  <td>'
#    @pos 35 REPLACING TAG 'pin_value' -> 'LOW'
#    @pos 50 TEXT: '</td>\n  <td><button type="button" id="btn'
#    @pos 91 REPLACING TAG 'pin_id' -> '14'
#    @pos 0 TEXT: '<tr>\n  <td>'
#    @pos 11 REPLACING TAG 'pin_id' -> '15'
#    @pos 23 TEXT: '</td>\n  <td>'
#    @pos 35 REPLACING TAG 'pin_value' -> 'LOW'
#    @pos 50 TEXT: '</td>\n  <td><button type="button" id="btn'
#    @pos 91 REPLACING TAG 'pin_id' -> '15'
#    END SPLICING ITERABLE
#    RLINE: '\n'
#    LINE 8, indent '      ': ''
#    LINE 9, indent '    ': '    </table>\n'
#    LINE 10, indent '    ': '    <div>{{ comment }}</div>\n'
#    @pos = 22: FOUND TAG: {{ comment }}
#    REPLACING TAG 'comment' -> ''
#    RLINE: '</div>\n'
#    LINE 10, indent '    ': '    <div></div>\n'
#    LINE 11, indent '  ': '  </body>\n'
#    LINE 12, indent '  ': '  <script>\n'
#    LINE 13, indent '    ': '    {{ javascript }}\n'
#    @pos = 20: FOUND TAG: {{ javascript }}
#    REPLACING TAG 'javascript' -> '<__main__.LazyTemplate object at 0x7fada657a240>'
#    SPLICING IN ITERABLE
#    LINE 1, indent '': 'document.body.addEventListener("click", function(event) {\n'
#    LINE 2, indent '  ': '  if (event.target.nodeName == "BUTTON"){\n'
#    LINE 3, indent '    ': '    var btn_id = event.target.getAttribute("id")\n'
#    LINE 4, indent '    ': '    console.log("Clicked", btn_id);\n'
#    LINE 5, indent '    ': '    postToggle(btn_id);\n'
#    LINE 6, indent '  ': '  }\n'
#    LINE 7, indent '': '});\n'
#    LINE 8, indent '  \n': '  \n'
#    LINE 9, indent '': 'function postToggle (btn_id) {\n'
#    LINE 10, indent '  ': "  var form = document.createElement('form');\n"
#    LINE 11, indent '  ': "  form.setAttribute('method', 'post');\n"
#    LINE 12, indent '  ': "  form.setAttribute('action', 'http://{{ server_addr }}?btn_id='+btn_id);\n"
#    @pos = 55: FOUND TAG: {{ server_addr }}
#    REPLACING TAG 'server_addr' -> '0.0.0.0'
#    RLINE: "?btn_id='+btn_id);\n"
#    LINE 12, indent '  ': "  form.setAttribute('action', 'http://0.0.0.0?btn_id='+btn_id);\n"
#    LINE 13, indent '  ': "  form.style.display = 'hidden';\n"
#    LINE 14, indent '  ': '  document.body.appendChild(form)\n'
#    LINE 15, indent '  ': '  form.submit();\n'
#    LINE 16, indent '': '}\n'
#    END SPLICING ITERABLE
#    RLINE: '\n'
#    LINE 13, indent '    ': ''
#    LINE 14, indent '  ': '  </script>\n'
#    LINE 15, indent '': '</html>\n'
