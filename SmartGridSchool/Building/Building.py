# NOTE: building data files must have "Data" subdirectory in the AAL's directory

import logging
import math
#import scipy.io
import sys

from magi.messaging.magimessage import MAGIMessage
from magi.util import helpers, database
from magi.util.agent import DispatchAgent, agentmethod
from magi.util.processAgent import initializeProcessAgent
import yaml

from CommClient import ClientCommService

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG) 

def sind(x):
    return sin((math.pi / 180) * x)

def cosd(x):
    return cos((math.pi / 180) * x)

class Building(DispatchAgent): # difference between DispatchAgent and NonBlockingDispatchAgent?
    def __init__(self):
        DispatchAgent.__init__(self)
        
        #Default arguments for server and clientId:
        self.server = 'server'
        self.port = 55343
        self.clientId = None
    
    # This code for parsing parameters.conf
    def setConfiguration(self, msg, **kwargs):
        DispatchAgent.setConfiguration(self, msg, **kwargs)
        
        '''From simple_client > client.py'''
        from magi.testbed import testbed
        if self.clientId == None: 
            self.hostname = testbed.nodename
            log.info("Hostname: %s", self.hostname)
            self.clientId = self.hostname 

        # The clientId can be set programmatically to append the hostname .
        self.setClientid() 
        self.commClient = None
        
        '''Parsing for Parameters'''
        # create list of strings
        with open("/users/rning/magi-modules/SmartGridSchool/Parameters.conf", "r") as paramFile:
            self.paramList = paramFile.read().splitlines()
        
        # define the global parameters
        self.day = float(self.paramList[0][len("day:"):])
        self.panelEff = float(self.paramList[1][len("panelEff:"):])
        
        # define the parameters unique to the building
        # UNTIL SERVER PARAMS ARE IMPLEMENTED:
        if self.hostname != "server":
            index = self.paramList.index(self.hostname)
            self.area = float(self.paramList[index+1][len("area:"):]) 
            self.volume = float(self.paramList[index+2][len("volume:"):])
            self.panelArea = float(self.paramList[index+3][len("panelArea:"):])
            # set panelTracking to false as default, if true, then set
            self.panelTracking = False
            if self.paramList[index+4][len("panelTracking:"):] == "True":
                self.panelTracking = True
            self.pAZA = float(self.paramList[index+5][len("pAZA:"):])
            self.pELA = float(self.paramList[index+6][len("pELA:"):])
            self.lightDraw = float(self.paramList[index+7][len("lightDraw:"):])
            self.baselineCe = float(self.paramList[index+8][len("baselineCe:"):])
            self.outlets = float(self.paramList[index+9][len("outlets:"):])
            self.applianceDraw = float(self.paramList[index+10][len("applianceDraw:"):])
            self.tempAC = float(self.paramList[index+11][len("tempAC:"):])
            self.timeAC = self.paramList[index+12][len("timeAC:"):]
            # convert string from param file to list
            self.timeAC = [] # list: [ day start, day end, time of day start, time of day end ]
            ACList = self.paramList[index+12][len("timeAC:"):]
            timeACIndex = 0
            endIndex = 0
            for letter in ACList:
                if letter == "," or letter == "[":
                    endIndex = timeACIndex + 1
                    while ACList[endIndex] != "," and ACList[endIndex] != "]":
                        endIndex += 1
                    self.timeAC.append(float(ACList[timeACIndex + 1: endIndex]))
                    timeACIndex = endIndex
            self.thermalLeakCe = float(self.paramList[index+13][len("thermalLeak:"):])
            self.thermalPower = float(self.paramList[index+14][len("thermalPower:"):])
    
    def iterateDay(self, msg):
        # run newDay to generate day-unique values
        self.newDay(self.day)
        
        dataPath = "/users/rning/magi-modules/SmartGridSchool/Data/" + self.hostname + "data.txt"
        with open(dataPath, "a") as dataFile:
            for i in range(0, 1440):
                print >>dataFile, "%d,%d" % (self.generation(), self.consumption())
    
    def newDay(self, day):
        # constants and parsed values
        self.day = day
        self.LT = 0
        self.OLI = 23.44
        self.LAT = 33.77984
        self.panelEff = 0.21
        self.preDawn = True
        self.dusk = False

        # calculated daily
        self.B = (360.0 / 365.0) * (self.day - 81)
        self.EoT = 9.87 * sind(2 * self.B) - 7.53 * cosd(self.B) - 1.5 * sind(self.B)
        self.delta = self.OLI * sind(self.B)

        # dew point in % as a float 0-1, by mass; base-lined for room temp
        self.dewPt = 0.025
        # % humidity as a float 0-1
        self.humidity = 0.6

        # atmospheric pressure in kpa
        self.ATM = 101.325

        # gas coefficents
        self.airGC = 0.287
        self.waterGC = 0.4615

        # specific heat capacities KJ / Kg
        self.airCp = 1.005
        self.waterCp = 1.8723

        # air density, Kilograms / meter^3, baseline
        self.P = 1

        # A/C calculation
        # max and min temperatures for the day
        self.maxT = (5.0 / 9.0) * (6.5 * sin(.0172 * self.day - 2.25) + 72.8 - 32)
        self.minT = (5.0 / 9.0) * (6.5 * sin(.0172 * self.day - 2.25) + 56.5 - 32)

        self.ran = self.maxT - self.minT
        self.ave = (self.maxT + self.minT) / 2
        
        self.insideTemperature = self.tempAC + self.thermalLeakCe * 60 * (24 - self.timeAC[1] + self.timeAC[0]) * (ave - tempAC)
        self.outsideTemperature = 23

        # the amount of energy in Kw, the air conditioner can remove from the air per hour
        # 1.057 Kilojoules per Btu / h
        self.thermalCapacity = self.thermalPower * 1.057

        # A / C power use when on in Watts
        self.acPowerUse = 5000 * 7   # need data for this

        # Lights calculation
        self.activeWattage = 0  # % active wattage 0.0 - 1.0
        self.baselineCe = 0.15

        # Outlets
        self.activeOutlets = 0
        
        # a conservative baseline estimate
        self.outletDraw = 75
        
        return true

    def generation(self):
        
        self.LST = (self.LT + (4.0 * (-13.361) + self.EoT)) / 60
        self.HRA = 15.0 * (self.LST - 12)

        self.SELA = asin(sind(self.delta) * sind(self.LAT) + cosd(self.delta) * cosd(self.LAT) * cosd(self.HRA))
        self.SAZA = acos(sind(self.delta) * cosd(self.LAT) - cosd(self.delta) * sind(self.LAT) * cosd(self.HRA)) / cos(self.SELA)

        if self.preDawn and self.SELA > 0: self.preDawn = False
        if not self.preDawn and self.SELA < 0: self.dusk = True

        if not self.preDawn and not self.dusk:
            #self.declination = 90 - (self.SELA) * (180 / math.pi)
            self.declination = 90 - self.SELA * (180 / math.pi)
            self.am = 1 / (cosd(self.declination) + 0.50572 * pow(96.07995 - self.declination, -1.6364))

            self.diffuseIrradience = 0.2 * pow(0.7, pow(1 / self.am, 0.678))
            self.solarIrradience = 1.353 * (1 + self.diffuseIrradience) * pow(0.7, pow(self.am, 0.678))

            self.moduleCe = cos(self.SELA) * sind(self.ELA) * cosd(self.AZA - self.SAZA * (180 / math.pi)) + sin(self.SELA) * cosd(self.ELA)

            if self.moduleCe < 0:
                self.moduleCe = 0

            self.eTotal = self.solarIrradience * self.moduleCe

            self.gen = self.eTotal * self.panelArea * self.panelEff

        else:
            self.gen = 0

        return self.gen

    def consumption(self):

        self.cons = 0
        # temperature calculation
        tempEq1 = 2.0 * pow(sin(math.pi * (self.LT / 60.0 - 9) / 12), 3)
        tempEq2 = 7.0 * pow(sin(math.pi * (self.LT / 60.0 - 9) / 19), 2)
        tempEq3 = 4.5 * pow(sin(math.pi * (self.LT / 60.0 - 19) / 40), 19)

        temp = (1.0 / 7.8789) * (tempEq1 + tempEq2 + tempEq3)

        self.outsideTemperature = (self.ran / 2) * temp + self.ave

        # thermal leak
        self.thermalLeak = self.thermalLeakCe * (self.outsideTemperature - self.insideTemperature)
        self.insideTemperature += self.thermalLeak

        # if air conditioning meets input time parameters
        if self.LT / 60 > self.timeAC[0] and self.LT / 60 < self.timeAC[1] and self.day >= self.timeAC[2] and self.day <= self.timeAC[3]:
            if self.insideTemperature > self.tempAC:

                # the amount of thermal energy vented by the A/C, in kilojoules per minute
                self.thermalVent = self.thermalCapacity / 60

                # % water vapor by mass
                self.waterVaporCe = self.dewPt * self.humidity

                # gas volume calculation * temperature in kelvin
                self.volCe_t = (self.waterVaporCe * self.waterGC + (1 - self.waterVaporCe) * self.airGC) * (self.insideTemperature + 273)

                # density in Kg / m^3
                self.P = self.ATM / self.volCe_t

                # average specific heat of the air solution
                self.cAve = self.waterVaporCe * self.waterCp + (1 - self.waterVaporCe) * self.airCp

                # temperature change
                self.deltaT = (self.thermalCapacity / 60) / (self.P * self.volume * self.cAve)

                # if deltaT is greater than the difference between the temperature and target
                # change inside temperature to target and reduce energy consumption as necessary
                if self.insideTemperature - self.deltaT < self.tempAC:
                    self.cons += self.acPowerUse * ((self.insideTemperature - self.tempAC) / self.deltaT)
                    self.insideTemperature = self.tempAC
                else:
                    self.insideTemperature -= self.deltaT
                    self.cons += self.acPowerUse

        if self.LT > (5.0 / 24.0) * 1440.0 and self.LT < (21.0 / 24.0) * 1440.0:
            # Outlet use
            if self.LT < 475:
                self.activeOutlets = (1.0 / randint(8, 10) * self.outlets)
            elif self.LT < 795:
                if (self.LT - 475) % 45 == 0:
                    self.activeOutlets = (1.0 / randint(1, 10) * self.outlets)
            elif self.LT < 945:
                if (self.LT - 795) % 5 == 0:
                    self.activeOutlets = (1.0 / randint(int(10 * (1 - 0.32)), 10) * self.outlets)
            elif self.LT < 1020:
                if (self.LT - 795) % 15 == 0:
                    self.activeOutlets = (1.0 / randint(int(10 * (1 - 2 * 0.32)), 10) * self.outlets)
            else:
                if self.LT % 5 == 0 and randint(0, 10) <= 10 * 0.24:
                    self.activeOutlets = (1 / randint(int(10 * (1 - 2.5 * 0.32)), 10) * self.outlets)
                else:
                    self.activeOutlets = 0
            self.activeOutlets = round(self.activeOutlets, 0)
            self.cons += self.activeOutlets * self.outletDraw

            # light use
            base = round((10 - 10 * self.baselineCe) * 10, 0)
            #self.baselineCe = round(self.baselineCe * 100, 0)

            if self.LT < 475:
                if self.LT % 10 == 0:
                    self.activeWattage = 1.0 / (0.1 * randint(round(base / 2, 0), base))
            elif self.LT < 795:
                if (self.LT - 475) % 45 == 0:
                    self.activeWattage = 1.0 / (0.1 * randint(1, base - (100 - base)))
            elif self.LT < 1020:
                if (self.LT - 795) % 15 == 0:
                    self.activeWattage = 1.0 / (0.1 * randint(1, base))
            else:
                if (self.LT - 1020) % 20 == 0 and randint(0, 10) <= 10 * self.baselineCe:
                    self.activeWattage = (1.0 / randint(int(10 * (1 - 3 * self.baselineCe)), base))
                else:
                    self.activeWattage = self.baselineCe

            self.cons += self.activeWattage * self.lightDraw
        return self.cons

    
    # From simple_client > client.py
    def setClientid(self):
    # The method is called in the setConfiguration to set a unique clientID  for the client in a group 
    # If there is only one client per host, then the clientId can be the hostname 
    # but if there are more than one clients per host, we will need to add a random int to it... 
        return
    
    # From simple_client > client.py
    @agentmethod()
    def startclient(self, msg):
        self.commClient = ClientCommService(self.clientId)
        self.commClient.initCommClient(self.server, self.port, self.requestHandler)
    
    # From simple_client > client.py
    @agentmethod()
    def stopclient(self, msg):
        DispatchAgent.stop(self, msg)
        if self.commClient:
            self.commClient.stop()
    
    # From simple_client > client.py
    def requestHandler(self, msgData):
        log.info("RequestHandler: %s", msgData)
        
        src= msgData['src']
        string = msgData['text']

        log.info("src and string: %s %s", src, string) 
        return "Hello there" 

    # From simple_client > client.py
    def setClientid(self):
    # The method is called in the setConfiguration to set a unique clientID  for the client in a group 
    # If there is only one client per host, then the clientId can be the hostname 
    # but if there are more than one clients per host, we will need to add a random int to it... 
        return 

# getAgent() method must be defined somewhere for all agents.
# Magi daemon invokes method to get reference to agent. Uses reference to run and interact with agent instance.
def getAgent(**kwargs):
    agent = Building()
    agent.setConfiguration(None, **kwargs)
    return agent

# In case agent run as separate process, need to create instance of agent, initialize required
# parameters based on received arguments, and call run method defined in DispatchAgent.
if __name__ == "__main__":
    agent = Building()
    kwargs = initializeProcessAgent(agent, sys.argv)
    agent.setConfiguration(None, **kwargs)
    agent.run()
