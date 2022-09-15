import math
import os
import re
from copy import deepcopy


class ERPEntry:
    def __init__(self, data):
        nSize = int.from_bytes(data[0x4:0x6], 'little')
        self.Name = data[0x6:0x6 + nSize]
        self.Count = data[0x6 + nSize + 0x14]
        self.Data = data
        self.Type = data[0x6 + nSize:0x6 + nSize + 0x10]

    def stringName(self):
        return self.Name[:-1].decode('UTF-8')

    def rename(self):
        nNew = bytes(input('New name/path (blank to cancel): '), 'UTF-8')
        if not nNew:
            return False
        fExI = re.search(r'\.', self.stringName())

        if fExI:
            fEx = self.Name[fExI.start():-1]
            if re.search(r'\b[y]\b', input('Remove existing extension %s? [y/*]: ' % fEx.decode('UTF-8')),
                         flags=re.IGNORECASE):
                fEx = bytes()
                print(fEx)
            nNew = nNew + fEx

        oSize = len(self.Name)
        self.Name = self.Name[:0x7] + (nNew if nNew else self.Name[0x7:-1]) + self.Name[-1:]
        self.rebuildEntry(oSize)
        return True

    def mipCheck(self):
        isRes = re.search(r'GfxSurfaceRes', self.Type.decode('UTF-8'), flags=re.IGNORECASE)
        return True if isRes and self.Count == 3 else False

    def removeMip(self):
        for count in range(self.Count):
            if count == 2:
                base = len(self.Name) + 0x1B + (0x21 * count)
                self.Data = self.Data[:base-1] + self.Data[base+0x20:]
        self.rebuildEntry()
        print('MIPs entry removed!')

    def rebuildEntry(self, size=None):
        nSize = size if size else len(self.Name)
        self.Count = math.floor(len(self.Data[0x6 + nSize + 0x14:]) / 0x21)
        result = len(self.Name).to_bytes(2, 'little')
        result = result + self.Name + self.Data[0x6+nSize:0x6+nSize+0x14] + self.Count.to_bytes(1, 'little')
        result = result + self.Data[0x6+nSize+0x15:]
        result = len(result).to_bytes(4, 'little') + result
        self.Data = result


class ERPFile:
    def __init__(self, data=None):
        headBytes = b'ERPK\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x000\x00\x00\x00\x00\x00\x00\x00'
        if data and data[:0x18] != headBytes:
            raise ValueError('Invalid ERP file')
        self.count = int.from_bytes(data[0x30:0x34], 'little') if data else 0
        self.subCount = int.from_bytes(data[0x34:0x38], 'little') if data else 0
        self.entries = []
        self.size = 0

        for entry in range(self.count):
            start, end = 0x38 + self.size, 0x3B + self.size
            chunkSize = int.from_bytes(data[start:end], 'little') + 4
            self.entries.append(ERPEntry(data[start:start + chunkSize]))
            self.size = self.size + chunkSize

        self.size = self.size + 8
        self.header = self.getHeader()

    def getHeader(self):
        result = b'ERPK\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x000\x00\x00\x00\x00\x00\x00\x00'
        result = result + self.size.to_bytes(8, 'little') + (self.size + 0x30).to_bytes(8, 'little')
        result = result + bytes(8)
        result = result + self.count.to_bytes(4, 'little') + self.subCount.to_bytes(4, 'little')
        return result

    def getWriteData(self):
        result = b''
        self.count = len(self.entries)
        self.subCount = 0
        self.size = 8
        for entry in self.entries:
            self.size = self.size + len(entry.Data)
            self.subCount = self.subCount + entry.Count
            result = result + entry.Data

        self.header = self.getHeader()
        return self.header + result

    def addEntry(self, entry):
        matches = [item for item in self.entries if item.Name == entry.Name]
        if matches:
            if re.search(r'\b[y]\b', input('%s already exists!\nOverwrite ? [y/*]: ' % entry.stringName()),
                         flags=re.IGNORECASE):
                for match in matches:
                    self.entries.remove(match)
            else:
                return
        self.entries.append(entry)
        print('Entry added!')

    def removeEntry(self, entry):
        try:
            self.entries.remove(entry)
            print('Entry removed!')
            return True
        except ValueError:
            print("Couldn't remove entry!")
            return False


class ListHandler:
    def __init__(self, dlist, listtype):
        CLS()
        entryData, self.ListName = dlist
        self.ListToDisplay = entryData.entries
        per = input('%s Total entries. Display per page: ' % len(self.ListToDisplay))
        self.perPage = int(per) if per.isnumeric() and int(per) > 0 else 25
        self.maxPage = math.ceil(len(self.ListToDisplay)/self.perPage) - 1
        self.Page = 0
        self.Type = listtype

    def printList(self):
        print('Viewing %s ' % self.ListName + ('Input\n' if self.Type else 'Output\n'))
        for enum, item in [(enum, item) for enum, item in enumerate(self.ListToDisplay)
                           if self.perPage + self.perPage * self.Page > enum >= self.perPage * self.Page]:
            print('{:^3} - {}'.format(1 + enum-self.perPage*self.Page, item.stringName()))
        print('\nPage %i of %i' % (self.Page + 1, self.maxPage + 1))

    def isFirstPage(self):
        return self.Page == 0

    def isLastPage(self):
        return self.maxPage <= self.Page

    def FirstPage(self):
        self.Page = 0

    def LastPage(self):
        self.Page = self.maxPage

    def NextPage(self):
        self.Page = self.Page + 1 if not self.isLastPage() else self.Page

    def PrevPage(self):
        self.Page = self.Page - 1 if not self.isFirstPage() else self.Page

    def getSelected(self, selected):
        if 0 < selected <= self.perPage and selected + self.perPage * self.Page <= len(self.ListToDisplay):
            return self.ListToDisplay[selected-1 + self.perPage * self.Page]
        return None

    def Filter(self, fstring):
        self.ListToDisplay = [item for item in self.ListToDisplay
                              if re.search(fstring, item.stringName(), flags=re.IGNORECASE)]
        self.ListName = 'Filtered[%s] ' % fstring + self.ListName
        self.maxPage = math.ceil(len(self.ListToDisplay)/self.perPage) - 1
        self.Page = 0


def CLS():
    os.system('cls')


def getData(fn):
    fnERP = fn + '.erp'
    try:
        file = open(fnERP, 'rb')
        fileData = file.read()
        file.close()
        try:
            fileData = ERPFile(fileData)
            print('%s loaded!' % fnERP)
        except ValueError:
            print('Invalid ERP File')
            return None
        return fileData, fnERP
    except IOError:
        print('Failed to fetch data! %s' % fnERP)
        return None


def writeData(data, fn):
    if not fn:
        print('Missing filename, ERP not written')
        return
    try:
        file = open(fn, 'wb')
        file.write(data.getWriteData())
        file.close()
        print('%s created!' % fn)
        return
    except IOError:
        print("Write Failed!")
        return


def makeERP(fn):
    fnERP = fn + '.erp'
    return ERPFile(), fnERP


def iFilename(fn):
    if not fn:
        print('Selection file cleared!')
        return None, None
    loaded = getData(fn) if fn else None
    if loaded:
        return loaded, None
    return None, fn


def EntryOption(entry, move):
    hasMip = entry.mipCheck()
    mOption = '\n\nM - ' + ('Move to output' if move else 'Remove from output')
    rOption = '\nR - Remove MIPS entry ' + ('and move to output' if move else '') if hasMip else ''
    pOption = '\nP - Rename/Change path'
    cOption = '\nB - Back'
    while True:
        CLS()
        print('Selected: ' + entry.stringName() + mOption + rOption + pOption + cOption)
        match input('Input: '):
            case 'M' | 'm':
                return True
            case 'R' | 'r':
                if hasMip:
                    entry.removeMip()
                    return True and move
            case 'P' | 'p':
                entry.rename()
            case 'B' | 'b':
                return False


def CopySelect(ifile, ofile):
    outputTable, *_ = ofile
    theList = ListHandler(ifile, True) if ifile else ListHandler(ofile, False)
    while True:
        CLS()
        theList.printList()

        ShownFile = ifile if theList.Type else ofile
        pPage = '<<< First < Prev' if not theList.isFirstPage() else ''
        nPage = 'Next > Last >>>' if not theList.isLastPage() else ''
        sPage = ' | ' if nPage and pPage else ''
        print(pPage + sPage + nPage)
        print('S - Save | R - Return | F - Filter | C - Clear | V - View')
        cInput = input('Input: ')
        match int(cInput) if cInput.isnumeric() else cInput:
            case int():
                copyMode = theList.Type
                entry = deepcopy(theList.getSelected(int(cInput))) if copyMode else theList.getSelected(int(cInput))
                if entry:
                    entryState = EntryOption(entry, copyMode)
                    if entryState and copyMode:
                        outputTable.addEntry(entry)
                        input('Press Enter to continue...')
                    if entryState and not copyMode:
                        outputTable.removeEntry(entry)
                        input('Press Enter to continue...')
            case '<':
                theList.PrevPage()
            case '<<<':
                theList.FirstPage()
            case '>':
                theList.NextPage()
            case '>>>':
                theList.LastPage()
            case 'S' | 's':
                CLS()
                if re.search(r'\b[y]\b', input('Save changes ? [y/*]: '), flags=re.IGNORECASE):
                    writeData(*ofile)
                    input('Press Enter to continue...')
                else:
                    input('Changes not saved, Press Enter to continue...')
            case 'F' | 'f':
                theList.Filter(input('String to Filter: '))
            case 'C' | 'c':
                theList = ListHandler(ShownFile, theList.Type)
            case 'V' | 'v':
                theList.Type = not theList.Type
                ShownFile = ifile if theList.Type else ofile
                print('Changing view to ' + ('Input list.' if theList.Type else 'Output list.'))
                theList = ListHandler(ShownFile, theList.Type)
            case 'R' | 'r':
                return


inFile = None
outFile = None
while True:
    CLS()
    print('1 - Select Input file [Read Only] (%s)\n'
          '2 - Select Output file [Read/Write] (%s)\n3 - Continue...\n\n0 - Exit\n'
          % (inFile[-1] if inFile else inFile, outFile[-1] if outFile else outFile))

    match (input('Input: ')):
        case '1':
            CLS()
            inFile, _ = iFilename(input('Input Filename: '))
            input('Press Enter to continue...')
        case '2':
            CLS()
            outFile, iName = iFilename(input('Output Filename: '))
            if not outFile and iName:
                if re.search(r'\b[y]\b', input('Create a blank %s ERP? [y/*]: ' % iName), flags=re.IGNORECASE):
                    outFile = makeERP(iName)
                    writeData(*outFile)
                input('Press Enter to continue...')
            else:
                input('Press Enter to continue...')
        case '3':
            CLS()
            if not outFile:
                input('Missing Output file!\nPress Enter to continue')
            else:
                CopySelect(inFile, outFile)
                inFile, outFile = None, None
        case '0':
            break
