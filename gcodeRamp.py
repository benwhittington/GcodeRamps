import regex as re
import sys


class ZFinder():
    def __init__(self, startTagValue):
        linePattern = f'G00 Z{startTagValue:.4f}'
        self.lineRegex = re.compile(linePattern)

    def __call__(self, lineString):
        return self.lineRegex.search(lineString) is not None    


class RampWriter():
    def __init__(self, zCutDepth):
        self.zCutCode = f'G01 Z{zCutDepth:.4f}'
        self.gcodeRegex = re.compile(r'G0[1-3]')
        self.xRegex = re.compile(r'(?<=X)\-?\d+\.\d{4}')
        self.yRegex = re.compile(r'(?<=Y)\-?\d+\.\d{4}')
        self.iRegex = re.compile(r'(?<=I)\-?\d+\.\d{4}')
        self.jRegex = re.compile(r'(?<=J)\-?\d+\.\d{4}')
        self.zFeedRateRegex = re.compile(r'(?<=G0[1-3]\sZ\d+\.\d{4}\sF)\d+')
        self.xyFeedRateRegex = re.compile(r'(?<=G0[1-3]\sX\d+\.\d{4}.*F)\d+')

        self.zFeedRate = None
        self.xyFeedRate = None

        self.gcodeMap = {
            'G01': 'G01',
            'G02': 'G03',
            'G03': 'G02'
        }

    def checkLineForFeedRates(self, line):
        if self.zFeedRate is None:
            match = self.zFeedRateRegex.findall(line)
            if len(match) == 1:
                self.zFeedRate = int(match[0])
                print(f'Found Z feed rate F{self.zFeedRate}')
        if self.xyFeedRate is None:
            match = self.xyFeedRateRegex.findall(line)
            if len(match) == 1:
                self.xyFeedRate = int(match[0])
                print(f'Found XY feed rate F{self.xyFeedRate}')

    def writeRamp(self, file, lineA='', lineB='', lineRampEnd='', tabHeight=None):
        if self.xyFeedRate is None:
            raise ValueError(f'Failed to find XY feed rate before it was needed to write ramp')

        if self.zFeedRate is None:
            raise ValueError(f'Failed to find Z feed rate before it was needed to write ramp')

        file.write('(RAMP ADDED)\n')
        file.write('(goto top of ramp, point B)\n')
        file.write(self.makeProcessedLineB(lineB, lineRampEnd, self.zFeedRate))
        file.write('(goto cutting depth)\n')
        file.write(self.zCutCode + '\n')
        file.write('(goto start of tab, point A at Z feed rate)\n')
        file.write(self.makeReturnToPointALine(lineA, lineB, self.xyFeedRate))

    def writeTab(self, file, lineA='', lineB='', lineRampEnd='', tabHeight=None):
        if self.xyFeedRate is None:
            raise ValueError(f'Failed to find XY feed rate before it was needed to write tab')

        file.write('(TAB ADDED)\n')
        file.write('(goto to tab height)\n')
        file.write(f'G00 Z{tabHeight:.4f}\n')
        file.write('(goto point B at tab height, unmodified)\n')
        file.write(lineB)
        file.write('(goto cutting depth)\n')
        file.write(self.zCutCode + '\n')
        file.write('(goto start of tab, point A at Z feed rate)\n')
        file.write(self.makeReturnToPointALine(lineA, lineB, self.zFeedRate))

    def makeProcessedLineB(self, lineB, lineRampEnd, feedRate):
        lineBSplit = lineB.split()
        gcode = self.gcodeRegex.findall(lineBSplit[0])[0]

        if gcode in ('G02', 'G03') and len(lineBSplit) == 5:
            lineBSplit.insert(3, lineRampEnd.split()[1])
            return  f'{" ".join(lineBSplit)} F{self.zFeedRate}\n'
        elif gcode == 'G01' and len(lineBSplit) in (1, 2, 3):
            return f'{" ".join(lineBSplit)} {lineRampEnd.split()[1]} F{feedRate}\n'
        else:
            raise ValueError(f'Unexpected gcode in "{lineB}"')

    def makeReturnToPointALine(self, lineA, lineB, feedRate):
        """
            For future Ben: line A gcode is irrelevant, only coordinates.
        """
        lineASplit = lineA.split()
        lineBSplit = lineB.split()
        numFields = len(lineBSplit) # here

        if numFields in (2, 3):
            return lineA
        elif numFields == 5:
            # don't know how many values in lineA so slice of first 3
            rawGcodeA, rawXA, rawYA = lineASplit[:3]
            rawGcodeB, rawXB, rawYB, rawIB, rawJB = lineBSplit

            # gcodeA = self.gcodeRegex.findall(rawGcodeA)[0]
            xA = float(self.xRegex.findall(rawXA)[0])
            yA = float(self.yRegex.findall(rawYA)[0])
            # iA = float(self.iRegex.findall(rawIA)[0])
            # jA = float(self.jRegex.findall(rawJA)[0])

            gcodeB = self.gcodeRegex.findall(rawGcodeB)[0]
            xB = float(self.xRegex.findall(rawXB)[0])
            yB = float(self.yRegex.findall(rawYB)[0])
            iB = float(self.iRegex.findall(rawIB)[0])
            jB = float(self.jRegex.findall(rawJB)[0])

            newGcode = self.gcodeMap[gcodeB]
            newI = xA + iB - xB
            newJ = yA + jB - yB
            newLine = f'{newGcode} X{xA:.4f} Y{yA:.4f} I{newI:.4f} J{newJ:.4f} F{feedRate}\n'

            return newLine
        else:
            raise ValueError(f'Unexpected number of fields ({numFields}) in "{lineA}"')


def makeOutFileName(inFileName):
    temp = inFileName.split('.')
    temp.insert(-1, '_out.')
    return ''.join(temp)


def main():
    startTagValue = 2.5  # also tab height
    zCutDepth = -0.5

    isStartTag = ZFinder(startTagValue)
    writer = RampWriter(zCutDepth=zCutDepth)

    inFileName = sys.argv[1]
    outFileName = makeOutFileName(inFileName)

    with open(inFileName, 'r') as r, open(outFileName, 'w') as w:
        line = ' '
        linePrev = ' '
        c = 0
        while line:
            line = r.readline()
            writer.checkLineForFeedRates(line)
            if not isStartTag(line):
                linePrev = line
                w.write(line)
                continue

            lineNext = r.readline()
            # writer.writeRamp(w, lineA=linePrev, lineB=lineNext, lineRampEnd=line, tabHeight=startTagValue)
            writer.writeTab(w, lineA=linePrev, lineB=lineNext, lineRampEnd=line, tabHeight=startTagValue)
            c += 1

    print(f'Replaced {c} tabs')
    print(f'Written to {outFileName}')


if __name__ == '__main__':
    main()