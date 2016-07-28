import json
import time
import logging
import socket
from threading import Thread
import threading

from magi.util import helpers


BUFF=1024
FALSE=0
TXTIMEOUT=1
PORT = 55343


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG) 

ch = logging.StreamHandler()
log.addHandler(ch)

class ServerCommService:
    
    def __init__(self):
	# The initialization function creates three maps to track the clients 
        self.active = False
        self.transportMap = dict()
        self.threadMap = dict()
	self.activeClientMap = dict() 
        self.sock = None
    
    def initCommServer(self, port, replyHandler):
        functionName = self.initCommServer.__name__
        helpers.entrylog(log, functionName, level=logging.INFO)
       
        self.sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        log.info("Starting a server at port %s" %(port))
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.settimeout(TXTIMEOUT)
        self.sock.bind(('0.0.0.0', port))
        self.sock.listen(5)
        
        self.active = True
        thread = Thread(target=self.commServerThread,args=(replyHandler,))
        thread.start()
        
        helpers.exitlog(log, functionName, level=logging.INFO)
        return thread
    
    #Blocking, never returns
    def commServerThread(self, replyHandler):
        
        log.debug("Running commServerThread on %s" % threading.currentThread().name)
        
        while self.active:
            try:
                log.info('%s: Waiting for clients to connect.....' % threading.currentThread().name) 
                clientsock, addr = self.sock.accept()
            except socket.timeout:
                continue


            log.debug('Client Connected from address %s' % repr(addr))  
            # Set the socket to blocking and receive the clientId information 
            clientsock.setblocking(1) 
            rxdata = clientsock.recv(BUFF)
            if len(rxdata) == 0:
                log.info("Client %s closed connection abruptly" % repr(addr))
                continue 
            else: 
            # Now receive the clientId information 
                jdata = json.loads(rxdata.strip())
                log.info("Received Data from client with Connection Info %s" %(jdata))
                # Setup the server state information for the recent client connection 
                clientId = jdata['src']
                nthread = Thread(name="ServerHandler for " + str(clientId), target=self.ServerHandler, args=(clientId, clientsock, replyHandler))
                self.threadMap[clientId] = nthread
                self.transportMap[clientId] = clientsock
                self.activeClientMap[clientId] = True 
	    
                # Start the client handling thread 
                nthread.start()
            
            
        log.info("Leaving commServerThread %s" % threading.currentThread().name)
        self.sock.close()
        
    #One thread is run per client on the servers's side
    def ServerHandler(self, clientId, clientsock, replyHandler):
        t = threading.currentThread()
        clientsock.settimeout(TXTIMEOUT);
        log.info("\t %s: In ServerHandler Running" % t.name)
        
        textstring = "Hello Client " + str(clientId) + " from the server" 
        data = json.dumps({'src': 'server', 'text': textstring }) 
        self.sendOneData(clientId, data) 

        while self.activeClientMap[clientId]:
            log.info("\t %s: Waiting to get data from client" % t.name)
            try:
                rxdata = clientsock.recv(BUFF)
                log.debug("Data Received: %s" %(repr(rxdata)))
            except socket.timeout:
                continue
            
            try:
                jdata = json.loads(rxdata.strip())
            except :
                if len(rxdata) == 0: 
                    log.info("Exception in commServerThread while trying to parse %s" % repr(rxdata))
                    log.info("Closing connection from client at %s" %(clientId)) 
                    self.activeClientMap[clientId] = False 
                    continue

            log.debug('ServerHandler RX data: %s' % repr(jdata))
            sresponse  = replyHandler(jdata)
            data = json.dumps({'src': 'server', 'text': sresponse }) 
            self.sendOneData(clientId, data) 

        #Cleanup
        clientsock.close()
        log.info("Leaving %s" % t.name)
   

    def sendOneData(self, clientId, data):
        if clientId not in self.transportMap:
            log.error("Client %s not registered" %(clientId))
            raise Exception, "Client %s not registered" %(clientId)
            
        clientsock = self.transportMap[clientId]

        log.debug('Sending data %s' %(data))
        clientsock.sendall(data)

    def onerecv(self, data):
        log.info('Data is from %s' % repr(data))
        sendstring = "Thank you" 
        return sendstring 

    def sendData(self, clientId, data):
        data['dst'] = clientId
        data = json.dumps(data)
        
        if clientId not in self.transportMap:
            log.error("Client %s not registered" %(clientId))
            raise Exception, "Client %s not registered" %(clientId)
            
        clientsock = self.transportMap[clientId]
        
        log.debug('Sending data %s' %(data))
        clientsock.send(data)
                    
    def stop(self):
        self.active = False



if __name__ == "__main__":
    server= ServerCommService()
    server.initCommServer(55353, server.onerecv)
    time.sleep(60)
    server.stop()    
