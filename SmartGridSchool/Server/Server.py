import logging
import sys
import threading

from magi.util import helpers, database
from magi.util.agent import SharedServer, agentmethod
from magi.util.processAgent import initializeProcessAgent

from CommServer import ServerCommService

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

#ch = logging.StreamHandler()
#log.addHandler(ch)

class Server(SharedServer):
    def __init__(self):
        SharedServer.__init__(self)
        # Default port when port not specified in AAL 
        self.port = 55286 
    
    # This function should start the server 
    def runserver(self):
        functionName = self.runserver.__name__ + "on port " + str(self.port) 
        helpers.entrylog(log, functionName, level=logging.INFO)

        self.commServer = ServerCommService()
        self.commServer.initCommServer(self.port, self.responseHandler)
            
        helpers.exitlog(log, functionName, level=logging.INFO)

        return True 
    
    # This function should stop the server 
    def terminateserver(self): 
        functionName = self.terminateserver.__name__
        helpers.entrylog(log, functionName, level=logging.INFO)
   
        self.commServer.stop() 
        helpers.exitlog(log, functionName, level=logging.INFO)
        return True 
    
    # Dummy response handler 
    def responseHandler(self,recvdata):
        log.info("Got info %s" %(rcvdata)) 
        sendstring = "Thank you" 	
        return sendstring  

def getAgent(**kwargs):
    agent = Server()
    agent.setConfiguration(None, **kwargs)
    return agent

if __name__ == "__main__":
    agent = Server()
    kwargs = initializeProcessAgent(agent, sys.argv)
    agent.setConfiguration(None, **kwargs)
    agent.run()
