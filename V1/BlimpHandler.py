from Input import Input
from Blimp import Blimp
from Connection import Connection
import pygame
from pygame.locals import *

import serial

#from SerialHelper import SerialHelper
from UDPMulticast import UDPHelper
import time
import easygui


class BlimpHandler:
    # Init =================================================================================
    def __init__(self):
        self.comms = UDPHelper()  # SerialHelper() # UDPHelper()
        self.display = None
        self.comms.open()
        self.parameterMessages = []
        self.pCodes = {  # Parameter message codes
            "toggleABG": "e",    # toggle Active Ball Grabber
            "autoOn":    "A1",   # turn autonomous on
            "autoOff":   "A0"    # turn autonomous off
        }

        self.blimps = []
        """
        for i in range(50,60):
            self.addFakeBlimp(i,"Fake"+str(i))
        """

        self.blimpIPIDMap = {"192.168.0.101": 1,
                             "192.168.0.102": 2,
                             "192.168.0.103": 3,
                             "192.168.0.104": 4,
                             "192.168.0.105": 5,
                             "192.168.0.106": 6,
                             "192.168.0.107": 7,
                             "192,168.0.100": 8,

                             "192.168.0.80": 10,
                             "192.168.0.20": 11,
                             "192.168.0.89": 12,
                             "192.168.0.62": 13,
                             "192.168.0.86": 14,
                             "192.168.0.14": 15,

                             "192.168.0.38": 20}
        self.blimpIDNameMap = {1: "Spicy Hot Dog",
                               2: "Waffle",
                               3: "Apple",
                               4: "Milk",
                               5: "Pasta",
                               6: "Duck",
                               7: "Eggs",
                               8: "Silly ahh",

                               10: "Big Cup of Eggs",
                               11: "Leg in a Cup",
                               12: "I'm in a Cup",
                               13: "My Cup of Eggs",
                               14: "Pint of Eggs",
                               15: "Stealthy Steve",

                               20: "Barometer"}
        self.blimpNewID = 30

        self.lastBlimpAdded = 0
        self.blimpAddDelay = 5  # seconds

        self.initInputs()

        self.connections = []

        self.blimpStateStrings = {-1: "None",
                                  0: "searching",
                                  1: "approach",
                                  2: "catching",
                                  3: "caught",
                                  4: "goalSearch",
                                  5: "approachGoal",
                                  6: "scoringStart",
                                  7: "shooting",
                                  8: "scored"}

        self.baseHeight = 0
        self.baroPrioritizeUDP = False
        self.baroTimeout = 3  # seconds

        self.baroType = None
        self.lastBaroPrint = 0
        self.baroUDPLastReceivedTime = 0
        self.baroUDPLastReceivedValue = None
        self.baroSerialLastReceivedTime = 0
        self.baroSerialLastReceivedValue = None
        self.baroSerial = None
        try:
            self.baroSerial = serial.Serial('/dev/baro_0', 115200)
        except serial.SerialException:
            print("Serial error!")

        self.plotData = {}

        self.numMessages = 0
        self.lastCheckedNumMessages = 0

        self.lastUpdateLoop = 0

        self.globalTargets = False

        self.pingDelay = 1  # second
        self.lastPing = 0

    def close(self):
        print("Closing BlimpHandler")
        self.comms.close()
        print("Comms closed.")

    def initInputs(self):
        self.inputs = []

        # Init WASD Input
        input_WASD = Input("Keyboard", "WASD", (K_d, K_a, K_w, K_s, K_UP, K_DOWN, K_c, K_e, K_q))
        self.inputs.append(input_WASD)
        """
        #Init IJKL Input
        input_IJKL = Input("Keyboard", "IJKL", (K_l, K_j, K_i, K_k, K_LEFTBRACKET, K_QUOTE, K_RETURN))
        self.inputs.append(input_IJKL)
        """

        #Check for joysticks
        self.joystickInstanceIDs = []
        self.joystickCount = pygame.joystick.get_count()
        for i in range(0,self.joystickCount):
            controller = pygame.joystick.Joystick(i)
            controller.init()
            self.printControllerData(controller)
            self.joystickInstanceIDs.append(controller.get_instance_id())
            controllerName = "Contrl " + str(controller.get_instance_id())
            input_Controller = Input("Controller",controllerName,controller)
            self.inputs.append(input_Controller)
        self.tempActiveController = len(self.inputs)-1
        if(self.display != None): self.display.activeController = self.tempActiveController

    def setDisplay(self,display):
        self.display = display
        display.activeController = self.tempActiveController

    #Loop ==================================================================================
    def update(self):
        currentTime = time.time()
        if currentTime - self.lastPing > self.pingDelay:
            self.lastPing = currentTime
            self.comms.send(69,"L","MAO")
        self.updateBaroHeight()
        self.checkJoystickCount()
        self.updateInputs()
        self.checkForDeadBlimps()
        self.listen()
        self.sendDataToBlimps()
        waitTime = time.time() - self.lastUpdateLoop
        if(waitTime > 0.01):
            print(waitTime)
        self.lastUpdateLoop = time.time()

    #Make UI element that shows if baro data is available and what type such as serial or udp
    def updateBaroHeight(self):
        #Handle serial connection
        #If barometer is disconnected, try to reconnect
        if(self.baroSerial == None):
            #Try to reconnect
            try:
                self.baroSerial = serial.Serial('/dev/baro_0', 115200)
                self.baroSerial.open()
            #If reconnect fails
            except(serial.SerialException):
                pass

        if(self.baroSerial != None):
            # get baro data from teensy
            try:
                while self.baroSerial.in_waiting:
                    receivedString = self.baroSerial.readline().decode('utf-8')
                    if(self.isFloat(receivedString)):
                        self.baroSerialLastReceivedValue = float(receivedString)
                        self.baroSerialLastReceivedTime = time.time()
                if(time.time() - self.lastBaroPrint > 0.01):
                    self.lastBaroPrint = time.time()
                    #print(self.baseHeight)
            #if port crashes, assume teensy has disconnected
            except(OSError):
                self.baroSerial = None

        #Check which data has been received recently
        currentTime = time.time()
        baroValidUDP = currentTime-self.baroUDPLastReceivedTime < self.baroTimeout
        baroValidSerial = currentTime-self.baroSerialLastReceivedTime < self.baroTimeout and self.baroSerial != None

        if(baroValidUDP and (self.baroPrioritizeUDP or not baroValidSerial)):
            self.baseHeight = self.baroUDPLastReceivedValue
            self.baroType = "UDP"
        elif(baroValidSerial and (not self.baroPrioritizeUDP or not baroValidUDP)):
            self.baseHeight = self.baroSerialLastReceivedValue
            self.baroType = "Serial"
        else:
            self.baseHeight = None
            self.baroType = None

    def checkJoystickCount(self):
        if (pygame.joystick.get_count() != self.joystickCount):
            print("Updating joysticks")
            self.initInputs()
            self.fixConnections()

    def updateInputs(self):
        for input in self.inputs:
            input.update()

    def checkForDeadBlimps(self):
        blimpsCorrect = False
        while not blimpsCorrect:
            blimpsCorrect = True
            for i in range(0, len(self.blimps)):
                blimp = self.blimps[i]
                blimp.lastHeartbeatDiff = time.time() - blimp.lastHeartbeatDetected
                #print(amount,";  ",blimp.heartbeatDisconnectDelay)
                if (blimp.lastHeartbeatDiff > blimp.heartbeatDisconnectDelay):
                    # Blimp heartbeat not received for too long; Remove it
                    print(blimp.name, "heartbeat not received; Removing...")
                    self.blimps.pop(i)
                    self.display.removeBlimp(blimp.ID)
                    blimpsCorrect = False
                    self.fixConnections()
                    break

    def listen(self):
        if(time.time() - self.lastCheckedNumMessages > 1):
            self.lastCheckedNumMessages = time.time()
            print("NumMessages:",self.numMessages)
            self.numMessages = 0

        readStrings = self.comms.getInputMessages()
        #readStrings = []
        while(len(readStrings)>0):
            self.numMessages += 1
            message = readStrings[0]
            readStrings.pop(0)
            self.checkForNewBlimps(message)
            self.useMessage(message) #includes heartbeat

    def sendDataToBlimps(self):
        currentTime = time.time()
        #Send parameter messages
        if(len(self.parameterMessages) > 0):
            #print("Messages:",len(self.parameterMessages))
            while(len(self.parameterMessages)>0):
                message = self.parameterMessages[0]
                self.parameterMessages.pop(0)

                blimpID = message[0]
                data = message[1]
                self.comms.send(blimpID,"P",data)
                #print(blimpID,",0:P:",data,sep='')currentTime = time.time()

        #Iterate through blimps, input, barometer data, target goal
        for blimpInd in range(0,len(self.blimps)):
            blimp = self.blimps[blimpInd]
            blimpID = blimp.ID
            connection = self.getConnectionFromBlimpIndex(blimpInd)
            #Send inputs
            if(connection != None):
                input = self.inputs[connection.inputIndex]
                inputData = input.grabInput()
            else:
                inputData = [0,0,0,0]
            if(currentTime - blimp.lastTimeInputDataSent > blimp.timeInputDelay):
                blimp.lastTimeInputDataSent = currentTime
                if (blimp.auto == 1):
                    message = str(self.baseHeight) + ";" + blimp.targetGoal + ";" + blimp.targetEnemy
                    self.comms.send(blimpID, "A", message)
                else:
                    blimpData = inputData.copy()
                    blimpData.append(blimp.grabbing)
                    blimpData.append(blimp.shooting)
                    message = ""
                    for data in blimpData:
                        message += str(data) + ","
                    message += ";" + str(self.baseHeight) + ";" + blimp.targetGoal + ";" + blimp.targetEnemy
                    self.comms.send(blimpID, "M", message)

        #Iterate through inputs and actions
        for inputIndex in range(0,len(self.inputs)):
            input = self.inputs[inputIndex]
            #Blimp-centered actions
            #Iterate through blimps
            blimpIndices = self.getConnectedBlimpIndicesFromInput(input)
            for blimpIndex in blimpIndices:
                blimp = self.blimps[blimpIndex]
                blimpID = blimp.ID

                if(input.grabAction("grab")):
                    blimp.grabbing = 1 - blimp.grabbing
                    print("Toggled grabber for blimp ID",blimpID)

                if(input.grabAction("shoot")):
                    blimp.shooting = 1 - blimp.shooting
                    print("Toggled shooting for blimp ID",blimpID)

                if(input.grabAction("auto")):
                    blimp.auto = 1 - blimp.auto
                    print("Toggled auto for blimp ID",blimpID)
                    input.notify(0.5)

                if(input.grabAction("kill")):
                    print("Killing blimp", blimpID)
                    self.comms.send(blimpID, "K", "")
                    input.notify(3)

                if(input.grabAction("record")):
                    self.requestRecording(blimpID)

            #Non-blimp-centered actions
            if(input.grabAction("panicAuto")):
                for blimp in self.blimps:
                    blimp.auto = 1
                    print("PANIC AUTO")
                    input.notify(1)
                    self.connections.clear()

            if(input.grabAction("connectUp")):
                blimpIndices = self.getConnectedBlimpIndicesFromInput(input)
                if(len(blimpIndices) < 2):
                    prevIndex = len(self.blimps)
                    if(len(blimpIndices) == 1):
                        prevIndex = blimpIndices[0]
                        self.updateConnection(inputIndex, blimpIndices[0])
                    while(prevIndex > 0):
                        nextIndex = prevIndex - 1
                        connection = self.getConnectionFromBlimpIndex(nextIndex)
                        if(connection == None):
                            self.updateConnection(inputIndex, nextIndex)
                            break
                        prevIndex = nextIndex

            if(input.grabAction("connectDown")):
                blimpIndices = self.getConnectedBlimpIndicesFromInput(input)
                if(len(blimpIndices) < 2):
                    prevIndex = -1
                    if(len(blimpIndices) == 1):
                        prevIndex = blimpIndices[0]
                        self.updateConnection(inputIndex, blimpIndices[0])
                    while(prevIndex < len(self.blimps)-1):
                        nextIndex = prevIndex + 1
                        connection = self.getConnectionFromBlimpIndex(nextIndex)
                        if(connection == None):
                            self.updateConnection(inputIndex, nextIndex)
                            break
                        prevIndex = nextIndex

            if (input.grabAction("vibeRight")):
                input.notify(0.1)
                print("STOP Vibe")

            if (input.grabAction("vibeLeft")):
                input.notify(100000)
                print("STOP Vibe")

    def requestRecording(self, blimpIDs):
        if (type(blimpIDs) != list):
            blimpIDs = [blimpIDs]
        for blimpID in blimpIDs:
            self.comms.send(blimpID, "P", "C300")

    #Helper functions ======================================================================
    def fixConnections(self):
        correctConnections = False
        while not correctConnections:
            correctConnections = True  # Assume true until proven incorrect
            for i in range(0, len(self.connections)):
                connection = self.connections[i]
                inputExist = self.inputExists(connection.inputName)
                blimpExist = self.blimpNameExists(connection.blimpName)
                if inputExist[0] and blimpExist[0]:
                    # Input and blimp exists; Update index
                    connection.inputIndex = inputExist[1]
                    connection.blimpIndex = blimpExist[1]
                else:
                    # Input or blimp doesn't exist; Remove it
                    self.connections.pop(i)
                    correctConnections = False
                    break

    def inputExists(self,inputName):
        for i in range(0,len(self.inputs)):
            if(inputName == self.inputs[i].name):
                return (True,i)
        return (False,0)

    def blimpNameExists(self,blimpName):
        for i in range(0,len(self.blimps)):
            if(blimpName == self.blimps[i].name):
                return (True,i)
        return (False,0)

    def blimpIDExists(self,blimpID):
        for blimp in self.blimps:
            if(blimpID == blimp.ID):
                return True
        return False

    def checkForNewBlimps(self, message):
        msgContent = message[0]
        msgAddress = message[1]
        if (msgContent == "0,N:N:N"):  # New Blimp
            currentTime = time.time()
            if(currentTime - self.lastBlimpAdded > self.blimpAddDelay):
                self.lastBlimpAdded = currentTime
                #Add new blimp!

                #Check if IP matches known blimp
                newID = self.blimpIPIDMap.get(msgAddress)
                if(newID != None):
                    print("Recognized Blimp",newID)
                else:
                    #IP doesn't match, assign new ID
                    newID = self.blimpNewID
                    self.blimpNewID += 1
                    print("Unrecognized Blimp",newID)

                if(newID != -1):
                    self.comms.send("N","N",str(newID))
                    newBlimp = Blimp(newID,self.getBlimpName(newID))
                    newBlimp.lastHeartbeatDetected = time.time()
                    self.blimps.append(newBlimp)
        else:
            comma = msgContent.find(",")
            colon = msgContent.find(":")
            if(comma == -1 or colon == -1): return
            checkID = msgContent[comma+1:colon]
            if(self.isInt(checkID)):
                checkID = int(checkID)
                if not self.blimpIDExists(checkID):
                    newBlimp = Blimp(checkID,self.getBlimpName(checkID))
                    newBlimp.lastHeartbeatDetected = time.time()
                    self.blimps.append(newBlimp)
                    print("Blimp heard with ID:",checkID)

    def useMessage(self, message):
        msgContent = message[0]
        msgAddress = message[1]
        comma = msgContent.find(",")
        colon = msgContent.find(":")
        ID = msgContent[comma+1:colon]
        if(self.isInt(ID)):
            currentTime = time.time()
            ID = int(ID)
            blimp = self.findBlimp(ID)
            blimp.lastHeartbeatDetected = currentTime

            secondColon = msgContent.find(":", colon+1)
            flag = msgContent[colon+1:secondColon]
            if(flag == "P"):
                equal = msgContent.find("=", secondColon+1)
                numFeedbackData = int(msgContent[secondColon+1:equal])
                currentDataLength = len(blimp.data)
                for i in range(currentDataLength, numFeedbackData):
                    blimp.data.append(0.0)
                lastComma = equal
                for i in range(0,numFeedbackData):
                    nextComma = msgContent.find(",",lastComma+1)
                    blimp.data[i] = float(msgContent[lastComma+1:nextComma])
                    lastComma = nextComma
            if(flag == "S"): #State
                blimp.receivedState = int(msgContent[secondColon+1:])
                #print("Received State:",blimp.receivedState)
            if(flag == "BB"): #BarometerBaseline
                baroMsg = msgContent[secondColon+1:]
                if(self.isFloat(baroMsg)):
                    self.baroUDPLastReceivedTime = currentTime
                    self.baroUDPLastReceivedValue = float(baroMsg)
            if(flag == "T"): #Telemetry
                pass
                """
                msg = msgContent[secondColon+1:]
                msgEqual = msg.find("=")
                varName = msg[0:msgEqual]
                varValue = msg[msgEqual+1:]
                if(self.isFloat(varValue)):
                    varValue = float(varValue)
                    key = str(blimp.ID) + ":" + varName
                    if(self.plotData.get(key) == None):
                        #New variable
                        self.plotData[key] = [[],varValue,varValue] #[Data points, min, max]

                    varPlotData = self.plotData.get(key)
                    currentData = (time.time(), varValue)
                    varPlotData[0].append(currentData)
                    varPlotData[1] = min(varPlotData[1],varValue)
                    varPlotData[2] = max(varPlotData[2],varValue)
                    #print(len(varPlotData[0]))
                """

            for blimp in self.blimps:
                if(blimp.ID == ID):
                    blimp.lastHeartbeatDetected = time.time()

    def updateConnection(self, inputIndex, blimpIndex):
        if(inputIndex >= len(self.inputs)): return
        if(blimpIndex >= len(self.blimps)): return
        inputName = self.inputs[inputIndex].name
        blimpName = self.blimps[blimpIndex].name
        newConnection = Connection(inputName,blimpName,inputIndex,blimpIndex)
        for i in range(0,len(self.connections)):
            connection = self.connections[i]
            if(newConnection.names==connection.names): #Connection exists; Remove it
                self.connections.pop(i)
                return
            elif(newConnection.blimpName==connection.blimpName): #Blimp already connected; Overwrite it
                self.connections.pop(i)
                self.connections.append(newConnection)
                return
        self.connections.append(newConnection)

    def pushMPB(self, blimpIDs):
        if(type(blimpIDs)!=list):
            blimpIDs = (blimpIDs)
        #Update parameter
        data = easygui.enterbox(msg="Enter parameter data",title="Parameter Update")
        if(data == None): return
        if(data[0] == "E"):
            if(data[1:]=="1"):
                self.display.exclusiveConnections = True
                print("Exclusive connections: TRUE")
            else:
                self.display.exclusiveConnections = False
                print("Exclusive connections: FALSE")
            return
        for blimpID in blimpIDs:
            self.parameterMessages.append((blimpID,data))
            blimp = self.findBlimp(blimpID)
            if(data == self.pCodes["autoOn"]):
                blimp.auto = 1
            elif(data == self.pCodes["autoOff"]):
                blimp.auto = 0
    #TG = TargetGoal
    def pushTGButton(self,blimpID):
        targetGoal = None
        for blimp in self.blimps:
            if(blimp.ID == blimpID):
                if(blimp.targetGoal == "O"):
                    blimp.targetGoal = "Y"
                elif(blimp.targetGoal == "Y"):
                    blimp.targetGoal = "O"
                targetGoal = blimp.targetGoal
        if(self.globalTargets and targetGoal != None):
            for altBLimp in self.blimps:
                altBLimp.targetGoal = targetGoal

    #TE = TargetEnemy
    def pushTEButton(self,blimpID):
        targetEnemy = None
        for blimp in self.blimps:
            if(blimp.ID == blimpID):
                if(blimp.targetEnemy == "R"):
                    blimp.targetEnemy = "B"
                elif(blimp.targetEnemy == "B"):
                    blimp.targetEnemy = "G"
                elif(blimp.targetEnemy == "G"):
                    blimp.targetEnemy = "R"
                targetEnemy = blimp.targetEnemy
        if(self.globalTargets and targetEnemy != None):
            for altBLimp in self.blimps:
                altBLimp.targetEnemy = targetEnemy

        def toggleAuto(self, blimpIDs):
            if(type(blimpIDs)!=list):
                blimpIDs = (blimpIDs)
            for blimpID in blimpIDs:
                blimp = self.findBlimp(blimpID)
                if(blimp.auto == 0):
                    self.parameterMessages.append((blimpID,self.pCodes["autoOn"]))
                    blimp.auto = 1
                else:
                    self.parameterMessages.append((blimpID,self.pCodes["autoOff"]))
                    blimp.auto = 0

    def updateGrabber(self, blimpIDs):
        if (type(blimpIDs) != list):
            blimpIDs = (blimpIDs)
        for blimpID in blimpIDs:
            self.parameterMessages.append((blimpID,self.pCodes["toggleABG"]))

    def findBlimp(self, blimpID):
        for blimp in self.blimps:
            if(blimp.ID == blimpID):
                return blimp

    def getConnectionFromBlimpIndex(self, blimpInd):
        for connection in self.connections:
            if(connection.blimpIndex == blimpInd):
                return connection
        return None

    def getConnectedBlimpIndicesFromInput(self, input):
        blimpIndices = []
        for connection in self.connections:
            if(self.inputs[connection.inputIndex] == input):
                blimpIndices.append(connection.blimpIndex)
        return blimpIndices

    def printControllerData(self, controller):
        print("Input")
        print("Name:", controller.get_name())
        print("Axes:", controller.get_numaxes())
        print("Trackballs:", controller.get_numballs())
        print("Buttons:", controller.get_numbuttons())
        print("Hats:", controller.get_numhats())

    def isInt(self, inputString):
        try:
            int(inputString)
            return True
        except ValueError:
            return False

    def isFloat(self, inputString):
        try:
            float(inputString)
            return True
        except ValueError:
            return False

    def getBlimpName(self, ID):
        name = self.blimpIDNameMap.get(ID)
        if(name == None):
            name = "Blimp " + str(ID)
        return name

    def addFakeBlimp(self, ID, name):
        tempBlimp = Blimp(ID,name)
        tempBlimp.lastHeartbeatDetected = 99999999999999
        self.blimps.append(tempBlimp)
        return tempBlimp

