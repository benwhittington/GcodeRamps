import re
import sys


class ZFinder():
    def __init__(self, startTagValue):
        linePattern = f'G00 Z{startTagValue:.4f}'
        self.lineRegex = re.compile(linePattern)

    def __call__(self, lineString):
        return self.lineRegex.search(lineString) is not None    


class RampWriter():
    def __init__(self, zCutDepth, zCutFeedRate, zTravelHeight):
        if zCutFeedRate is None:
            self.zCutCode = f'G01 Z{zCutDepth:.4f}'
        else:
            self.zCutCode = f'G01 Z{zCutDepth:.4f} F{zCutFeedRate:d}'
        self.zTravelHeightCode = f'G00 Z{zTravelHeight:.4f}'
        self.gcodeRegex = re.compile(r'G0[1-3]')
        self.xRegex = re.compile(r'(?<=X)\-?\d+\.\d{4}')
        self.yRegex = re.compile(r'(?<=Y)\-?\d+\.\d{4}')
        self.iRegex = re.compile(r'(?<=I)\-?\d+\.\d{4}')
        self.jRegex = re.compile(r'(?<=J)\-?\d+\.\d{4}')

        self.gcodeMap = {
            'G01': 'G01',
            'G02': 'G03',
            'G03': 'G02'
        }

    def __call__(self, file, lineA='', lineB='', lineRampEnd=''):
        file.write('(RAMP ADDED)\n')
        file.write('(goto top of ramp, point B)\n')
        file.write(self.makeProcessedLineB(lineB, lineRampEnd))
        file.write('(goto cutting depth)\n')
        file.write(self.zCutCode + '\n')
        file.write('(goto start of tab, point A)\n')
        file.write(self.makeReturnToPointALine(lineA, lineB))

    def makeProcessedLineB(self, lineB, lineRampEnd):
        lineBSplit = lineB.split()
        gcode = self.gcodeRegex.findall(lineBSplit[0])[0]

        if gcode in ('G02', 'G03') and len(lineBSplit) == 5:
            lineBSplit.insert(3, lineRampEnd.split()[1])
            return ' '.join(lineBSplit) + '\n'
        elif gcode == 'G01' and len(lineBSplit) in (1, 2, 3):
            return ' '.join(lineBSplit) + lineRampEnd.split()[1] + '\n'
        else:
            raise ValueError(f'Unexpected gcode in "{lineB}"')

    def makeReturnToPointALine(self, lineA, lineB):
        lineASplit = lineA.split()
        lineBSplit = lineB.split()
        numFields = len(lineASplit)

        if numFields in (2, 3):
            return lineA
        elif numFields == 5:
            rawGcodeA, rawXA, rawYA, rawIA, rawJA = lineASplit
            rawGcodeB, rawXB, rawYB, rawIB, rawJB = lineBSplit

            gcodeA = self.gcodeRegex.findall(rawGcodeA)[0]
            xA = float(self.xRegex.findall(rawXA)[0])
            yA = float(self.yRegex.findall(rawYA)[0])
            iA = float(self.iRegex.findall(rawIA)[0])
            jA = float(self.jRegex.findall(rawJA)[0])

            gcodeB = self.gcodeRegex.findall(rawGcodeB)[0]
            xB = float(self.xRegex.findall(rawXB)[0])
            yB = float(self.yRegex.findall(rawYB)[0])
            iB = float(self.iRegex.findall(rawIB)[0])
            jB = float(self.jRegex.findall(rawJB)[0])

            newGcode = self.gcodeMap[gcodeA]
            newI = xA + iB - xB
            newJ = yA + jB - yB
            newLine = f'{newGcode} X{xA:.4f} Y{yA:.4f} I{newI:.4f} J{newJ:.4f}\n'

            assert(gcodeA == gcodeB)

            return newLine
        else:
            raise ValueError(f'Unexpected number of fields ({numFields}) in "{lineA}"')


def makeOutFileName(inFileName):
    temp = inFileName.split('.')
    temp.insert(-1, '_out.')
    return ''.join(temp)


def main():
    startTagValue = 2.5
    zCutDepth = -0.5
    zCutFeedRate = None  # can be an integer or None
    zTravelHeight = 19.3

    isStartTag = ZFinder(startTagValue)
    writeRamp = RampWriter(zCutDepth=zCutDepth, zCutFeedRate=zCutFeedRate, zTravelHeight=zTravelHeight)

    inFileName = sys.argv[1]
    outFileName = makeOutFileName(inFileName)

    with open(inFileName, 'r') as r, open(outFileName, 'w') as w:
        line = ' '
        linePrev = ' '
        c = 0
        while line:
            line = r.readline()
            
            if not isStartTag(line):
                linePrev = line
                w.write(line)
                continue

            lineNext = r.readline()
            writeRamp(w, lineA=linePrev, lineB=lineNext, lineRampEnd=line)
            c += 1

    print(f'Modified {c} lines')
    print(f'Written to {outFileName}')


if __name__ == '__main__':
    main()