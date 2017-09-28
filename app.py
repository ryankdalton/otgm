#!/usr/bin/env python

# This file may be used instead of Apache mod_wsgi to run your python
# web application in a different framework.  A few examples are
# provided (cherrypi, gevent), but this file may be altered to run
# whatever framework is desired - or a completely customized service.
#
import imp
import os
import sys
import errno

virtenv = os.path.join(os.environ.get('OPENSHIFT_PYTHON_DIR','.'), 'virtenv')
python_version = "python"+str(sys.version_info[0])+"."+str(sys.version_info[1])
os.environ['PYTHON_EGG_CACHE'] = os.path.join(virtenv, 'lib', python_version, 'site-packages')
virtualenv = os.path.join(virtenv, 'bin','activate_this.py')
##execfile(virtualenv, dict(__file__=virtualenv))


#
# IMPORTANT: Put any additional includes below this line.  If placed above this
# line, it's possible required libraries won't be in your searchable path
#


#
#  main():
#
if __name__ == '__main__':
##   try:
       map = imp.load_source('app', 'map.py')
       port = map.app.config['PORT']
       ip = map.app.config['IP']
       app_name = map.app.config['APP_NAME']
       host_name = map.app.config['HOST_NAME']

       fwtype="wsgiref"
       for fw in ("gevent", "gunicorn", "cherrypy", "flask"):
          try:
             imp.find_module(fw)
             fwtype = fw
          except ImportError,e:
             print e
             pass

       print('Starting WSGIServer type %s on %s:%d ... ' % (fwtype, ip, port))

       if fwtype == "gevent":
          from gevent.pywsgi import WSGIServer
          WSGIServer((ip, port), map.app).serve_forever()

       elif fwtype == "gunicorn":
          workers = int(os.environ.get('GUNICORN_PROCESSES', '3'))
          threads = int(os.environ.get('GUNICORN_THREADS', '1'))
          forwarded_allow_ips = '*'
          secure_scheme_headers = { 'X-Forwarded-Proto': 'https' }


       elif fwtype == "cherrypy":
          from cherrypy import wsgiserver
          server = wsgiserver.CherryPyWSGIServer(
             (ip, port), map.app, server_name=host_name)
          server.start()

       elif fwtype == "flask":
              from flask import Flask
              server = Flask(__name__)
              server.wsgi_app = map.app
              try:
                server.run(host=ip, port=port)

              except IOError, e:
                if e.errno == errno.EPIPE:
                   # remote peer disconnected
                   print "Detected remote disconnect", e
                   pass
                else:
                   # determine and handle different error
                   print e
                   pass

              except Exception, e:
                print e


       else:
          from wsgiref.simple_server import make_server
          make_server(ip, port, map.app).serve_forever()

##   except Exception, e:
##      print "Error: ", e