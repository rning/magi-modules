class ProcessData():
  if __name__ == "__main__":
    
    netElectricity = []
    for i in range(0, 1440):
      netElectricity.append(0)
    
    for i in range(0, 21):
      fileName = "b-" + str(i) + "data.txt"
      with open(fileName, "r") as dataFile:
        listIndex = 0
        for line in dataFile:
          generation = float(line[:line.find(",")])
          consumption = float(line[line.find(",") + 1:])
          
          #find net surplus (positive) or deficit (negative) and add to netElectricity list
          netElectricity[listIndex] += generation - consumption
          
          listIndex += 1
    
    with open("netData.txt", "a") as netDataFile:
      for netData in netElectricity:
        print >>netDataFile, str(netData)
