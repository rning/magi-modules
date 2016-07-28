import sys
import json
import logging
import random
import socket
from threading import Thread
import threading
import time

from magi.util import helpers


PORT=55343
BUFF=1024
FALSE=0
TXTIMEOUT=1

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


ch = logging.StreamHandler()
log.addHandler(ch) 


class ClientCommService:
    
    def __init__(self, clientId):
        log.info("In ClientCommService Init")

        self.active = False
        self.clientId = clientId
        self.connected = False
        self.sock = None

        functionName = self.initCommClient.__name__ + str(self.clientId)
        helpers.exitlog(log, functionName, level=logging.INFO)
    
    def initCommClient(self, address, port, replyHandler):
        functionName = self.initCommClient.__name__
        helpers.entrylog(log, functionName, level=logging.INFO)
        
        self.sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.settimeout(TXTIMEOUT)
        
        retries = 0        
        while not self.connected:
            log.info("Trying to connect to server, attempt #%d..." % (retries+1))
            try:
                log.info("Trying to connect to server %s..." % (address))
                self.sock.connect((address, port))
                self.connected = True
                log.info("Connected to server")
            except socket.error as e:
                retries += 1
                log.info("Socket timed out, exception: %s" % repr(e))
                time.sleep(0.1 + (random.random()*0.3))
                if retries == 10:
                    log.info("Failed to connect after ten retires...  %s" % repr(e))
                    return 
        
        # Now that a connection is established with the server start the 
        # server management thread so that client and asynchronously send and recv 
        self.active = True
        thread = Thread(name="ClientHandler for " + str(self.clientId), target=self.ClientHandler, args=(replyHandler,))
        thread.start()
        
        helpers.exitlog(log, functionName, level=logging.INFO)
        return thread
    
    def ClientHandler(self, replyHandler):
        
        t = threading.currentThread()
        log.info("Running %s"  % t.name)

        data = json.dumps({'src': self.clientId, 'text': 'hello server'})
        log.debug("sending string %s" %(data))
        self.sock.sendall(data) 
        
        # Waiting for the server hello 
        while self.active:
            log.debug("%s: Wating for data from server..." % t.name )
            #blocks on recv, but may timeout
            try:
                rxdata = self.sock.recv(BUFF)
                self.processRecvData(rxdata)
                log.debug("Data Received: %s" %(repr(rxdata)))
            except socket.timeout:
                continue
        #cleanup
        log.info("Leaving %s" % threading.currentThread().name)
    

    def processRecvData(self,string):
        if len(string) == 0:
            log.info("Server closed connection. Exiting....")
            self.stop()
            return 
        if len(string) > 0:
          jdata = json.loads(string.strip())
          log.debug("Data Received: %s" %(repr(jdata)))
          return 

    def onesend(self,string):
       # neoed to process what is received from the server 

       str = "hi again" 
       return str 


    def sendData(self, data):
        data['src'] = self.clientId
        data = json.dumps(data)
        log.debug('Sending data %s' %(data))
        self.sock.send(data)
                
    def stop(self):
        self.active = False
        self.sock.close()
        return 


if __name__ == "__main__":
    client = ClientCommService(sys.argv[1])
    client.initCommClient("localhost",55353,client.onesend)
