#
# Name: MetarXMLEncoder.py
# Purpose: To encode METAR/SPECI information to a METAR/SPECI XML schema. This encoder will
#          properly encode the entire contents of a US METAR/SPECI observation to the IWXXM-US
#          schema. It can encode US and International METAR/SPECI observations to the IWXXM
#          schema.
#
# Author: Mark Oberfield
# Organization: NOAA/NWS/OSTI/Meteorological Development Laboratory
# Contact Info: Mark.Oberfield@noaa.gov
# Date: 10 July 2015
#
import difflib, os, re, sys, tempfile, time, uuid
import xml.etree.ElementTree as ET
import xmlpp
#
NameSpaces = { 'gco':'http://www.isotc211.org/2005/gco',
               'gmd':'http://www.isotc211.org/2005/gmd',
               'gml':'http://www.opengis.net/gml/3.2',
               'iwxxm':'http://icao.int/iwxxm/1.1',
               'iwxxm-us':'http://nws.weather.gov/schemas/IWXXM-US/1.0/Release',
               'om':'http://www.opengis.net/om/2.0',
               'saf':'http://icao.int/saf/1.1',
               'sams':'http://www.opengis.net/samplingSpatial/2.0',
               'sf':'http://www.opengis.net/sampling/2.0',
               'xlink':'http://www.w3.org/1999/xlink',
               'xsi':'http://www.w3.org/2001/XMLSchema-instance' }

FMH1URL = 'http://nws.weather.gov/codes/FMH-1/2005'
SSCLURL = '%s/SensorStatus' % FMH1URL
_Pcp = 'TS|DZ|RA|SN|SG|IC|PE|GR|GS|UP|PL|//'
_PcpQ = 'SH|FZ'

_re_cloudLyr = re.compile(r'(VV|SKC|CLR|FEW|SCT|BKN|(0|O)VC|///)([/\d]{3})(CB|TCU|///)?')
_re_pcpnhist = re.compile(r'(?P<PCP>(%s)?(%s))(?P<TIME>((B|E)\d{2,4})+)' % (_PcpQ,_Pcp))
_re_event = re.compile(r'(?P<EVENT>B|E)(?P<TIME>\d{2,4})')
#
# From stackoverflow 'nbolton'
textnode_re = re.compile('>\n\s+([^<>\s].*?)\n\s+</', re.DOTALL)
#
_CldCvr = {'CLR':(0,'Clear'),'SKC':(0,'Clear'),'FEW':(1,'Few'),'SCT':(2,'Scattered'),'BKN':(3,'Broken'),
           'OVC':(4,'Overcast'),'0VC':(4,'Overcast')}

_BeginEnd = {'B':'BEGIN','E':'END'}

_OSType = {'AO1':'AUTOMATED_NO_PRESENT_WEATHER', 'AO2':'AUTOMATED_WITH_PRESENT_WEATHER',
           'A01':'AUTOMATED_NO_PRESENT_WEATHER', 'A02':'AUTOMATED_WITH_PRESENT_WEATHER'}

_Distance = {'DSNT': { 'title':'DISTANT',
                       'href':'%s/ConvectionDistance/DISTANT/' % FMH1URL },
             'OHD': { 'title':'OVERHEAD',
                      'href':'%s/ConvectionDistance/OVERHEAD/' % FMH1URL },
             'VC': { 'title':'VICINITY',
                     'href':'%s/ConvectionDistance/VICINITY/' % FMH1URL },
             'ATSTN' : { 'title':'' }
             }

_Frequency = { 'OCNL': { 'title': 'OCCASIONAL',
                         'href' : '%s/LightningFrequency/OCCASIONAL/' % FMH1URL },
               'FRQ': { 'title': 'FREQUENT',
                        'href' : '%s/LightningFrequency/FREQUENT/' % FMH1URL },
               'CONS': { 'title': 'CONTINUOUS',
                         'href' : '%s/LightningFrequency/CONTINUOUS/' % FMH1URL }}

_SensorStatus = { 'RVRNO':'RUNWAY_VISUAL_RANGE',
                  'PWINO':'PRESENT_WEATHER',
                  'PNO':'PRECIPITATION',
                  'FZRANO':'FREEZING_RAIN',
                  'TSNO':'THUNDERSTORM',
                  'VISNO':'VISIBILITY',
                  'CHINO':'CEILING_HEIGHT',
                  'SLPNO':'PRESSURE_MEASURED',
                  'WINDNO':'WIND_MEASURED',
                  }

_CompassPts = { 'N' :'360','NE':'45', 'E' :'90', 'SE':'135',
                'S' :'180','SW':'225','W' :'270','NW':'315'}

def parseAndGetNameSpaces(fname,References={}):
    #
    events = 'start','start-ns'
    root = None
    ns = {}
    requiredNS = References.keys()
    allLocations = [x[0] for x in References.values()] 
    #
    for event, elem in ET.iterparse(fname,events):
        if event == 'start' and root == None:
            root = elem
            for prefix, uri in ns.items():
                if prefix not in ['','xs']:
                    try:
                        elem.set("xmlns:"+prefix,"http://%s" % difflib.get_close_matches(uri,allLocations,1)[0])
                    except IndexError:
                        elem.set("xmlns:"+prefix,uri)
                try:
                    requiredNS.pop(requiredNS.index(prefix))
                except ValueError:
                    pass
        #
        elif event == 'start-ns':
            if elem[0] in ns and ns[elem[0]] != elem[1]:
                #
                # NOTE: It is perfectly valid to have the same prefix refer
                #       to different URI namespaces in different parts of the
                #       document. This exception servers as a reminder that
                #       this solution is not robust.
                raise KeyError("Duplicate prefix with different URI found.")
            ns[elem[0]] = elem[1]
    #
    while True:
        try:
            key = requiredNS.pop()
            root.set("xmlns:%s" % key,"http://%s" % References[key][0])
        except IndexError:
            break
    #    
    return ET.ElementTree(root),ns

def getGeography(file):

    fh = open(file,'r')
    d = {}
    
    for lne in fh:
        if lne.startswith('#'):
            continue
        uuid,key,lat,lon,elev,name,junk,junk=lne.split('|')
        d[key.strip()] = ('%s %s %s' % (lat.strip(),lon.strip(),elev.strip()),name.strip(),uuid)
        
    return d

def fix_date(tms):
    """Tries to determine month and year from report timestamp.
    tms contains day, hour, min of the report, current year and month"""
    
    now = time.time()
    t = time.mktime(tms)    
    if t > now + 86400.0:       # previous month
        if tms[1] > 1:
            tms[1] -= 1
        else:
            tms[1] = 12
            tms[0] -= 1
    elif t < now - 25*86400.0:  # next month
        if tms[1] < 12:
            tms[1] += 1
        else:
            tms[1] = 1
            tms[0] += 1

def _getAllMatches(re,inputstr):

    curpos = 0
    matches = []
    while len(inputstr[curpos:]):
        try:
            m = re.search(inputstr[curpos:])
            matches.append(m.groupdict())
            curpos += m.end()
        except AttributeError:
            break
            
    return matches
    
class XMLEncoder:
    
    def __init__(self,wwCodesFile='../data/ww.xml',metarStationInfoFile='../data/metarStationInfo.txt'):
        #
        # Populate METAR metadata dictionary
        self.metarMetaData = getGeography(metarStationInfoFile)
        #
        # Populate the dictionary with precipitation/obstruction and other phenomenon
        root,wwCodeSpaces = parseAndGetNameSpaces(wwCodesFile)
        self.wwCodes = {}
        for concept in root.iter('{%s}Concept' % wwCodeSpaces.get('skos')):
            try:
                uri = concept.get('{%s}about' % wwCodeSpaces.get('rdf'))
                for elem in concept:
                    title = elem.text
                    
                key = uri[uri.rfind('/')+1:]
                self.wwCodes[key] = dict([('uri',uri),('title',title)])
                
            except KeyError:
                pass            
        #
        # map several encoder tokens to a single function
        setattr(self,'obv',self.pcp)
        setattr(self,'vcnty', self.pcp)
        
        setattr(self,'iceacc1',self.iceAccretion)
        setattr(self,'iceacc3',self.iceAccretion)
        setattr(self,'iceacc6',self.iceAccretion)
        
        setattr(self,'pcp1h', self.precipitationAmounts)
        setattr(self,'pcpamt',self.precipitationAmounts)
        setattr(self,'pcpamt24h',self.precipitationAmounts)
        setattr(self,'lwe',   self.precipitationAmounts)

        setattr(self,'maxT6h', self.maxTemperature)
        setattr(self,'maxT24h',self.maxTemperature)
        setattr(self,'minT6h', self.minTemperature)
        setattr(self,'minT24h',self.minTemperature)
        
    def __call__(self,decodedMetar,report=None,allowUSExtensions=False,nameSpaceDeclarations=False,debugComment=False):
        #
        # decodedMetar is a dictionary
        if decodedMetar.has_key('fatal'):
            print 'Fatal error at %s %s in report.' % (decodedMetar['index'],decodedMetar['fatal'])
            return
        #
        # see if we have the metadata for the observation
        self.ident(decodedMetar['ident'])
        self.ICAOLatLonElev, self.ICAOName, self.stationUUID = self.metarMetaData[self.ICAOId]
        #
        self.rawReport = report.strip()
        self.decodedMetar = decodedMetar
        self.nameSpacesDeclared = nameSpaceDeclarations
        self.debugComment = debugComment
        self.defaultNSPrefix = 'iwxxm'
        #
        # If an 'international' METAR/SPECI is passed in, the value of the variable below 
        # should be determined by presence of 'CAVOK' in the TAC itself.
        #
        try:
            self.cavokPresent = decodedMetar['cavok']
        except KeyError:
            self.cavokPresent = 'false'
            
        self.doingUSMetarSpeci = False
        #
        # Determine if US METAR/SPECI. if so, cavok cannot be present in observation.
        if self.ICAOId[0] in ['K','P'] or self.ICAOId[:2] == 'TJ':
            
            self.doingUSMetarSpeci = True
            self.cavokPresent = 'false'
            if allowUSExtensions:
                self.defaultNSPrefix = 'iwxxm-us'
        #
        # Minimal set of elements that can appear in the document
        self.ObservationResults = ['temp','alt','wind']
        #
        # If CAVOK is not present, add to the list . . .
        if self.cavokPresent == 'false':
            self.ObservationResults += ['vsby','rvr','pcp','obv','vcnty','sky']
        #
        # If US extension to the IWXXM standard is allowed, then the elements to process is much larger
        if allowUSExtensions:
            self.ObservationResults += ['additive','mslp','pchgr','ptndcy','snodpth','hail',
                                        'ssmins','auro','contrail','nospeci','event','maintenance',
                                        'snoincr','pcp1h','pcpamt','pcpamt24h','iceacc1','iceacc3',
                                        'iceacc6','lwe','maxT6h','minT6h','maxT24h','minT24h']
        #
        # These elements will not appear in the US observation
        else:
            self.ObservationResults += ['rewx','ws','sea','rwystate']
        
        self._issueTime = list(time.gmtime(self.decodedMetar['itime']['value']))
        #
        # The root element created here
        self.XMLDocument = ET.Element('%s:%s' % (self.defaultNSPrefix,self.decodedMetar['type']['str']))
        #
        # Namespace declarations are optional
        if self.nameSpacesDeclared:
            for prefix,uri in NameSpaces.items():
                if prefix == 'iwxxm-us' and self.defaultNSPrefix == 'iwxxm':
                    continue
                
                self.XMLDocument.set('xmlns:%s' % prefix,uri)
        
        if self.defaultNSPrefix == 'iwxxm-us':
            self.XMLDocument.set('xsi:schemaLocation','http://nws.weather.gov/schemas/IWXXM-US/1.0/Release http://nws.weather.gov/schemas/IWXXM-US/1.0/Release/schemas/usMetarSpeci.xsd')
        else:
            self.XMLDocument.set('xsi:schemaLocation','http://icao.int/iwxxm/1.1 http://schemas.wmo.int/iwxxm/1.1/metarSpeci.xsd')
                    
        status = 'NORMAL'
        try:
            if 'COR' in self.decodedMetar['autocor']['str']:
                status = 'CORRECTED'
        except KeyError:
            pass
            
        auto = 'false'
        try:
            if 'AUTO' in self.decodedMetar['autocor']['str']:
                auto = 'true'
        except KeyError:
            pass
            
        self.XMLDocument.set('status',status)
        self.XMLDocument.set('automatedStation',auto)

        self.doIt()
                
    def printXML(self,f,readable=False):
        #
        # Make a file object
        if type(f) == str:
            f = open(f,'w')
        #
        # If the user wants a readable document, a little more prep work is
        # required
        #
        if readable:
            #
            # Create a workfile and dump the contents of element tree
            _fd,_fname = tempfile.mkstemp()
            ET.ElementTree(self.XMLDocument).write(_fname,xml_declaration='Yes, please.',encoding="utf-8",method="xml")
            os.close(_fd)
            #
            _fobj = open(_fname,'r')
            xmltext = _fobj.read()
            _fobj.close()
            #
            # Indent for readablity 
            _fobj = open(_fname,'w')
            xmlpp.pprint(xmltext,output=_fobj,indent=2,width=160)        
            _fobj.close()
            xmltext = open(_fname,'r').read()  
            os.unlink(_fname)
            #
            # Create neater text elements and write to designated file
            prettyXml = textnode_re.sub('>\g<1></',xmltext)
            f.write(prettyXml)
            f.write('\n')
        else:
            
            ET.ElementTree(self.XMLDocument).write(f,xml_declaration='Yes, please.',encoding="utf-8",method="xml")
            
            
        if f not in [sys.stdout,sys.stderr]:
            f.close()
            
    def itime(self,parent,itime):
        self.XMLDocument.set('gml:id','%s-%s' % (self.decodedMetar['type']['str'],uuid.uuid4()))
        indent = ET.SubElement(parent,'om:type')
        indent.set('xlink:href','http://codes.wmo.int/49-2/observation-type/IWXXM/1.0/MeterologicalAerodromeObservation')
        indent = ET.SubElement(parent,'om:phenomenonTime')
        indent1 = ET.SubElement(indent,'gml:TimeInstant')
        indent1.set('gml:id','%s-%s-%s' % (self.decodedMetar['type']['str'].lower(),
                                           self.ICAOId,time.strftime('%Y%m%d%H%MZ',
                                                                     self._issueTime)))
        indent2 = ET.SubElement(indent1,'gml:timePosition')
        indent2.text = time.strftime('%Y-%m-%dT%H:%M:%SZ',self._issueTime)
        
        indent = ET.SubElement(parent,'om:resultTime')
        indent.set('xlink:href','#%s' % indent1.get('gml:id'))

    def ident(self,ident):
        self.ICAOId = ident['str']

    def doIt(self):
        #
        # The appearance of the corresponding TAC is explicitly forbidden in the IWXXM XML document.
        # However, if you pass in the optional argument, the TAC will appear in the document as a
        # comment. I find this useful as a debugging aid.
        #
        message = []
        try:
            message=['%s%s%s' % ('UNPARSED_TAC=\'',self.decodedMetar['unparsed']['str'],'\'\n')]
            message.insert(0,'%s%s%s' % ('\nORIG_TAC=\'',self.rawReport,'\'\n'))
                     
        except KeyError:
            if self.debugComment:
                message = ['%s%s%s' % ('\nORIG_TAC=\'',self.rawReport,'\'\n')]

        if len(message):
            self.XMLDocument.append(ET.Comment(''.join(message)))

        #
        # It begins...
        indent = ET.SubElement(self.XMLDocument,'iwxxm:observation')
        indent1 = ET.SubElement(indent,'om:OM_Observation')
        indent1.set('gml:id','obs-%s-%s' % (self.ICAOId,time.strftime('%Y%m%dT%H%M%SZ',self._issueTime)))
            
        self.itime(indent1,self.decodedMetar['itime'])
        self.procedureAndGIS(indent1)
        #
        # Current status and capability of the observing system
        try:
            self.resultQuality(indent1,self.decodedMetar['ssistatus'])
        except KeyError:
            pass
        #
        # If wind information is estimated
        try:
            self.decodedMetar['estwind']
            self.resultQuality(indent1,{'str':'WINDNO'})
        except KeyError:
            pass
        #
        # Finally the observation itself
        self.result(indent1)

    def resultQuality(self,parent,token):
        #
        for no in token['str'].split():
            #
            # Bypass compass directions
            if no in ['N','NE','E','SE','S','SW','W','NW']:
                continue
            
            indent  = ET.SubElement(parent,'om:resultQuality')
            indent1 = ET.SubElement(indent,'gmd:DQ_CompletenessOmission')
            indent2 = ET.SubElement(indent1,'gmd:result')
            indent3 = ET.SubElement(indent2,'gmd:DQ_ConformanceResult')
            
            indent4 = ET.SubElement(indent3,'gmd:specification')
            indent4.set('xlink:href','%s/%s' % (SSCLURL,_SensorStatus.get(no)))
            
            indent4 = ET.SubElement(indent3,'gmd:explanation')
            indent4.set('gco:nilReason','missing')

            indent4 = ET.SubElement(indent3,'gmd:pass')
            indent5 = ET.SubElement(indent4,'gco:Boolean')
            indent5.text = 'false'        
    
    def procedureAndGIS(self,parent):
        #
        indent = ET.SubElement(parent,'om:procedure')
        
        if self.doingUSMetarSpeci:
            indent.set('xlink:href','http://nws.weather.gov/schemas/IWXXM-US/1.0/Release/FMH1-METAR-SPECI.xml')
        else:
            indent1 = ET.SubElement(indent,'metce:Process')
            indent1.set('xmlns:metce','http://def.wmo.int/metce/2013')
            indent1.set('gml:id','p-49-2-metar')
            indent2 = ET.SubElement(indent1,'gml:description')
            indent2.text = """WMO No. 49 Volume 2 Meteorological Service for International Air Navigation
            APPENDIX 3 TECHNICAL SPECIFICATIONS RELATED TO METEOROLOGICAL OBSERVATIONS AND REPORTS"""
            
        indent = ET.SubElement(parent, 'om:observedProperty')
        
        if self.doingUSMetarSpeci:
            indent.set('xlink:href','http://www.ofcm.gov/fmh-1/fmh1.htm')
            indent.set('xlink:title','Federal Meteorological Handbook No.1 - Surface Weather Observations and Reports')
        else:
            indent.set('xlink:href','http://codes.wmo.int/49-2/observable-property/MeteorologicalAerodromeObservation')
            indent.set('xlink:title','Observed properties for Meteorological Aerodrome Observation Reports (METAR and SPECI)')
            
        indent = ET.SubElement(parent, 'om:featureOfInterest')
        indent1 = ET.SubElement(indent,'sams:SF_SpatialSamplingFeature')
        indent1.set('gml:id','samplePt-%s' % self.ICAOId)
        
        indent2 = ET.SubElement(indent1,'sf:type')
        indent2.set('xlink:href','http://www.opengis.net/def/samplingFeatureType/OGC-OM/2.0/SF_SamplingPoint')
        indent2.set('xlink:title','SF_SamplingPoint')
        
        indent2 = ET.SubElement(indent1,'sf:sampledFeature')

        indent3 = ET.SubElement(indent2,'saf:Aerodrome')
        indent3.set('gml:id','uuid.%s' % self.stationUUID)
        
        indent4 = ET.SubElement(indent3,'gml:identifier')
        indent4.set('codeSpace','urn:uuid:')
        indent4.text = self.stationUUID
        
        indent4 = ET.SubElement(indent3,'saf:designator')
        indent4.text = self.ICAOId
        
        indent4 = ET.SubElement(indent3,'saf:name')
        indent4.text = self.ICAOName
        
        indent4 = ET.SubElement(indent3,'saf:locationIndicatorICAO')
        indent4.text = self.ICAOId
        
        indent4 = ET.SubElement(indent3,'saf:ARP')
        indent5 = ET.SubElement(indent4,'gml:Point')
        indent5.set('gml:id','reference-Pt-%s' % self.ICAOId)
        indent5.set('uomLabels','degree degree m')
        indent5.set('axisLabels','Latitude Longitude Altitude')
        indent5.set('srsName','urn:ogc:def:crs:EPSG::4979')

        indent6 = ET.SubElement(indent5,'gml:pos')
        indent6.text = self.ICAOLatLonElev
        
        indent2 = ET.SubElement(indent1,'sams:shape')
        indent2.set('xlink:href','#reference-Pt-%s' % self.ICAOId)
    #
    # Beginning of IWXXM Base, in order
    #
    def temp(self,parent,token):
        
        if token == None:
            return
        
        indent = ET.Element('iwxxm:airTemperature')
        try:
            indent.text = str(self.decodedMetar['tempdec']['tt'])
            indent.set('uom','Cel')
            parent.append(indent)
            
        except KeyError:
            try:
                indent.text = str(token['tt'])
                indent.set('uom','Cel')
                parent.append(indent)
                
            except KeyError:
                pass

        indent = ET.Element('iwxxm:dewpointTemperature')
        try:
            indent.text = str(self.decodedMetar['tempdec']['td'])
            indent.set('uom','Cel')
            parent.append(indent)
            
        except KeyError:
            try:
                indent.text = str(token['td'])
                indent.set('uom','Cel')
                parent.append(indent)
                
            except KeyError:
                pass

    def alt(self,parent,token):
        
        if token == None:
            return
        
        indent = ET.Element('iwxxm:qnh')
        #
        # Always report pressure in hPa
        factor = 1.0
        try:
            if token['uom'] == "[in_i'Hg]":
                factor = 33.86
                
        except KeyError:
            pass
            
        try:
            indent.text = '%.1f' % (token['value'] * factor)
            indent.set('uom','hPa')
            parent.append(indent)
            
        except KeyError:
            pass
    
    def wind(self,parent,token):        

        if token == None:
            return
        
        indent = ET.SubElement(parent,'iwxxm:surfaceWind')        
        indent1 = ET.Element('iwxxm:AerodromeSurfaceWind')
        #
        # Wind direction and speed are mandatory
        if token['str'].startswith('VRB') or token.has_key('ccw'):
            indent1.set('variableDirection','true')
        else:
            indent1.set('variableDirection','false')
            indent2 = ET.Element('iwxxm:meanWindDirection')
            try:
                indent2.text = token['dd']                
                indent2.set('uom','deg')
                indent1.append(indent2)
                
            except KeyError:
                pass
        #
        # Always report speeds in kilometers per hour
        factor = 1.0
        if token['uom'] == '[kn_i]':
            factor = 1.85184
            
        try:
            indent2 = ET.Element('iwxxm:meanWindSpeed')
            indent2.text = '%.1f' % (token['ff']*factor)
            indent2.set('uom','km/h')
            indent1.append(indent2)
            
        except KeyError:
            pass
        #
        # Gusts are optional
        try:
            indent2 = ET.Element('iwxxm:windGust')
            indent2.text = '%.1f' % (token['gg']*factor)
            indent2.set('uom','km/h')
            indent1.append(indent2)
            
        except KeyError:
            pass
        #
        # Variable direction is optional
        try:
            indent2 = ET.Element('iwxxm:extremeClockwiseWindDirection')
            indent2.text = token['cw']
            indent2.set('uom','deg')
            indent1.append(indent2)
            
            indent2 = ET.Element('iwxxm:extremeCounterClockwiseWindDirection')
            indent2.set('uom','deg')
            indent2.text = token['ccw']
            indent1.append(indent2)

        except KeyError:
            pass

        indent.append(indent1)

    def vsby(self,parent,token):

        if token == None:
            return
        
        indent = ET.SubElement(parent,'iwxxm:visibility')
        indent1 = ET.SubElement(indent,'iwxxm:AerodromeHorizontalVisibility')
        #
        # Always report visibility in meters
        factor = 1.0
        if token['uom'] == '[mi_i]':
            factor = 1609.34

        try:
            indent2 = ET.Element('iwxxm:prevailingVisibility')
            try:
                indent2.text = '%.1f' % (self.decodedMetar['sfcvsby']['value']*factor)
            except KeyError:
                indent2.text = '%.1f' % (token['value']*factor)
                
            indent2.set('uom','m')
            indent1.append(indent2)
            
            try:
                indent2 = ET.Element('iwxxm:prevailingVisibilityOperator')
                indent2.text = {'M':'BELOW','P':'ABOVE'}.get(token['oper'])
                indent1.append(indent2)
                
            except KeyError:
                pass
        #
        # No prevailing visibility
        except KeyError:
            pass
        
        try:    
            indent2 = ET.Element('iwxxm:minimumVisibility')
            indent2.text = '%.0f' % token['minimum']['value']            
            indent2.set('uom','m')
            indent1.append(indent2)
            
            indent2 = ET.Element('iwxxm:minimumVisibilityDirection')
            indent2.text = _CompassPts.get(token['minimum']['direction'],'360.0')
            indent2.set('uom','deg')
            indent1.append(indent2)
            
        except KeyError:
            pass        
            
    def rvr(self,parent,token):

        for rwy,mean,tend,oper in zip(token['rwy'].split(),token['mean'].split(),
                                      list(token['tend']),list(token['oper'])):
            
            indent = ET.SubElement(parent,'iwxxm:rvr')
            indent1 = ET.SubElement(indent,'iwxxm:AerodromeRunwayVisualRange')
            if tend in ['U','D','N']:
                ident1.set('pastTendency',{'U':'UPWARD','D':'DOWNWARD','N':'NO_CHANGE'}.get(tend))
            
            indent2 = ET.SubElement(indent1,'iwxxm:runway')
            indent3 = ET.SubElement(indent2,'saf:RunwayDirection')
            indent3.set('gml:id','RVRRWY_%s' % rwy)
            indent4 = ET.SubElement(indent3,'saf:designator')
            indent4.text = rwy
        
            indent2 = ET.SubElement(indent1,'iwxxm:meanRVR')
            indent2.set('uom','m')
            
            if token['uom'] == 'm':
                indent2.text = mean
            elif token['uom'] == '[ft_i]':
                indent2.text = '%.1f' % (float(mean)*0.3048)

            if oper in ['M','P']:
                indent2 = ET.SubElement(indent1,'iwxxm:meanRVROperator')
                indent2.text = {'M':'BELOW','P':'ABOVE'}.get(oper)

    def pcp(self,parent,token):
        
        for ww in token['str'].split():
            #
            if ww == '//':
                indent = ET.SubElement(parent,'iwxxm:presentWeather')
                indent.set('nilReason','http://codes.wmo.int/common/nil/notObservable')
                indent.set('xsi:nil','true')
                continue
            #
            # Search BUFR table
            try:
                codes = self.wwCodes[ww]
                indent = ET.SubElement(parent,'iwxxm:presentWeather')
                indent.set('xlink:href',codes['uri'])
                indent.set('xlink:title',codes['title'])
            #
            # Initial weather phenomenon token not matched
            except KeyError:
                self.wxrPhenomenonSearch(parent,ww)
                
    def wxrPhenomenonSearch(self,parent,ww):
        #
        # Split the weather string into two; both pieces must be found
        pos=-2
        ww1 = ww[:pos]
        ww2 = ww[pos:]
        
        while len(ww1) > 1:
            try:
                codes1 = self.wwCodes[ww1]
                codes2 = self.wwCodes[ww2]
                
                indent = ET.SubElement(parent,'iwxxm:presentWeather')
                indent.set('xlink:href',codes1['uri'])
                indent.set('xlink:title',codes1['title'])
                
                indent = ET.SubElement(parent,'iwxxm:presentWeather')
                indent.set('xlink:href',codes2['uri'])
                indent.set('xlink:title',codes2['title'])
                break
            
            except KeyError:
                
                pos -= 2
                ww1 = ww[:pos]
                ww2 = ww[pos:]
        
    def sky(self,parent,token):

        if token == None:
            return

        indent = ET.Element('iwxxm:cloud')
        indent1 = ET.SubElement(indent,'iwxxm:AerodromeObservedClouds')
        for amount,ignored,hgt,typ in _re_cloudLyr.findall(token['str']):
            self.doCloudLayer(indent1,amount,hgt,typ)
            
        if len(indent1):
            parent.append(indent)
        

    def doCloudLayer(self,parent,amount,hgt,typ):
        #
        # Vertical visibility
        if amount == 'VV':    
            indent = ET.SubElement(parent,'iwxxm:verticalVisibility')
            indent.set('uom','[ft_i]')
            if hgt == '///':
                indent.set('missing','http://codes.wmo.int/common/nil/notObservable')
                indent.set('xsi:nil','true')
            else:
                indent.text = str(int(hgt)*100)
            return
            
        indent  = ET.SubElement(parent,'iwxxm:layer')
        indent1 = ET.SubElement(indent,'iwxxm:CloudLayer')
        indent2 = ET.SubElement(indent1,'iwxxm:amount')
        try:
            indent2.set('xlink:href','http://codes.wmo.int/bufr4/codeflag/0-20-008/%d' % _CldCvr[amount][0])
            indent2.set('xlink:title', _CldCvr[amount][1])            

        except KeyError:
            indent2.set('xsi:nil','true')
            indent2.set('nilReason','http://codes.wmo.int/common/nil/notObservable')                

        indent2 = ET.SubElement(indent1,'iwxxm:base')
        indent2.set('uom','[ft_i]')
        
        try:
            indent2.text = str(int(hgt)*100)

        except (TypeError,ValueError):
            indent2.set('uom','N/A')
            indent2.set('xsi:nil','true')
            try:
                if _CldCvr[amount][0] == 0:
                    indent2.set('nilReason','inapplicable')

            except KeyError:
                indent2.set('nilReason','http://codes.wmo.int/common/nil/notObservable')                
        #
        # Annex 3 and FMH-1 specifies only two cloud type in METARs, 'CB' and 'TCU'
        if typ == 'CB':
            indent2 = ET.SubElement(indent1,'iwxxm:cloudType')
            indent2.set('xlink:href','http://codes.wmo.int/bufr4/codeflag/0-20-012/9')
            indent2.set('xlink:title','Cumulonimbus')

        if typ == 'TCU':
            indent2 = ET.SubElement(indent1,'iwxxm:cloudType')
            indent2.set('xlink:href','http://codes.wmo.int/bufr4/codeflag/0-20-012/32')
            indent2.set('xlink:title','Cumulus congestus')

        if typ == '///' and hgt != '///':
            indent2 = ET.SubElement(indent1,'iwxxm:cloudType')            
            indent2.set('nilReason','http://codes.wmo.int/common/nil/notObservable')

    def rewx(self,parent,token):

        indent = ET.SubElement(parent,'iwxxm:recentWeather')
        indent.set('xlink:href',wwCodes[token['str']]['uri'])
        indent.set('xlink:title',wwCodes[token['str']]['title'])
    
    def ws(self,parent,token):

        rwy = token['str']
        indent = ET.SubElement(parent,'iwxxm:windShear')
        indent1 = ET.SubElement(indent,'iwxxm:AerodromeWindShear')
        indent2 = ET.SubElement(indent1,'iwxxm:runway')
        indent3 = ET.SubElement(indent2,'saf:RunwayDirection')
        indent3.set('gml:id','WSRWY_%s' % rwy)
        indent4 = ET.SubElement(indent3,'saf:designator')
        indent4.text = rwy
    
    def sea(self,parent,token):
        
        indent1 = ET.Element('iwxxm:AerodromeSeaState')
        try:
            indent2= ET.Element('iwxxm:seaSurfaceTemperature')
            indent2.text = token['tt']
            indent2.set('uom','Cel')
            indent1.append(indent2)
            
        except KeyError:
            pass

        try:
            indent2= ET.Element('iwxxm:seaState')
            indent2.set('xlink:href',self.wwCodes[token['str']]['uri'])
            indent2.set('xlink:title',self.wwCodes[token['str']]['uri'])
            indent1.append(indent2)
                
        except KeyError:
            pass
        
        indent = ET.SubElement(parent,'iwxxm:seaState')
        indent.append(indent1)
    #
    # Argh!
    def rwystate(self,parent,token):
        pass
    
    def trend(self,parent,token):
        pass
    #
    # End of IWXXM Base
    #
    #
    # Beginning of IWXXM-US extension. Information supplied after the TAC's RMK keyword
    #
    def additive(self,parent,token):
        
        indent = ET.SubElement(parent,'iwxxm-us:humanReadableText')
        indent.text = token['str']

    def mslp(self,parent,token):

        indent = ET.Element('iwxxm-us:seaLevelPressure')
        indent.set('uom','hPa')
        try:
            indent.text = str(token['value'])
            parent.append(indent)
            
        except KeyError:
            pass

    def pchgr(self,parent,token):

        indent = ET.SubElement(parent,'iwxxm-us:pressureChangeIndicator')
        indent.set('xlink:href','%s/PressureChangingRapidly/PRESSURE_%s_RAPIDLY' % \
                   (FMH1URL,token['value']))

    def ptndcy(self,parent,token):

        try:
            url = 'http://codes.wmo.int/common/bufr4/codeflag/0-10-063/%c' % token['character']
            indent = ET.Element('iwxxm-us:pressureTendency3hr')
            indent.set('uom','hPa')
            indent.text = str(token['pchg'])
            parent.append(indent)
            indent = ET.SubElement(parent,'iwxxm-us:pressureTendencyCharacteristic3hr')
            indent.set('xlink:href',url)

        except KeyError:
            pass

    def snodpth(self,parent,token):
        
        indent = ET.Element('iwxxm-us:snowDepth')
        indent.set('uom','m')
        try:
            indent.text = '%.2e' % (float(token['depth'])*0.0254)
            parent.append(indent)
            
        except KeyError:
            pass

    def hail(self,parent,token):
        
        indent = ET.SubElement(parent,'iwxxm-us:maxHailstoneDiameter')
        indent.set('uom','m')
        indent.text = '%.2e' % (token['value']*0.0254)
    
    def ssmins(self,parent,token):

        try:
            sunshineMinutes = token['value']
            indent = ET.SubElement(parent,'iwxxm-us:durationOfSunshine')
            indent.text = 'PT%dH%dM0S' % (sunshineMinutes/60,sunshineMinutes%60)
            
        except KeyError:
            pass
        
    def auro(self,parent,token):

        indent = ET.SubElement(parent,'iwxxm-us:aurora')
        indent.text='true'

    def contrail(self,parent,token):

        indent = ET.SubElement(parent,'iwxxm-us:aurora')
        indent.text='true'

    def nospeci(self,parent,token):

        indent = ET.SubElement(parent,'iwxxm-us:noSPECI')
        indent.text='true'
    
    def event(self,parent,token):

        indent = ET.SubElement(parent,'iwxxm-us:%sObservation' % token['str'].lower())
        indent.text='true'
        
    def snoincr(self,parent,token):

        indent = ET.SubElement(parent,'iwxxm-us:snowIncrease')
        indent1 = ET.SubElement(indent,'iwxxm-us:snowDepth')
        indent1.set('uom','m')
        indent1.text = '%.2e' % (token['depth']*0.0254)
        indent1 = ET.SubElement(indent,'iwxxm-us:snowDepthIncrease')
        
        indent2 = ET.SubElement(indent1,'iwxxm-us:extremeValuePeriod')
        indent2.set('unit','hour')
        indent2.text = token['period']
        indent2 = ET.SubElement(indent1,'iwxxm-us:extremeValueType')
        indent2.set('xlink:href','http://codes.wmo.int/grib2/codeflag/4.10/1')
        indent2.set('xlink:title','Accumulation')
        indent2 = ET.SubElement(indent1,'iwxxm-us:processedValue')
        indent2.set('uom','m/s')
        indent2.text = '%.2e' % (token['value']*7.06e-6)
        indent2 = ET.SubElement(indent1,'iwxxm-us:processedWeatherElement')
        indent2.set('xlink:href','http://codes.wmo.int/grib2/codeflag/4.2/0-1-57')
        indent2.set('xlink:title','Total snowfall rate')
    #
    # Statistically Processed Properties routines
    def precipitationRate(self,parent,token,code):

        try:
            indent = ET.Element('iwxxm-us:extremeValuePeriod')
            indent.set('unit','hour')
            indent.text = token['period']
            parent.append(indent)
            
        except KeyError:
            raise
        
        indent = ET.SubElement(parent,'iwxxm-us:extremeValueType')
        indent.set('xlink:href','http://codes.wmo.int/grib2/codeflag/4.10/1')
        indent.set('xlink:title','Accumulation')
        indent = ET.SubElement(parent,'iwxxm-us:processedValue')
        indent.set('uom','kg/(s-m^2)')
        indent.text = '%.2e' % (token['value']*7.06e-3)
        indent = ET.SubElement(parent,'iwxxm-us:processedWeatherElement')
        indent.set('xlink:href','%s/StatisticallyProcessedWeatherElements/%s/' % (FMH1URL,code))

    def precipitationAmounts(self,parent,token):
        
        indent = ET.Element('iwxxm-us:statisticallyProcessedQuantity')
        try:
            self.precipitationRate(indent,token,'PrecipitationRate')
            parent.append(indent)
            
        except KeyError:
            pass
        
    def iceAccretion(self,parent,token):
        
        indent = ET.Element('iwxxm-us:statisticallyProcessedQuantity')
        try:
            self.precipitationRate(indent,token,'IceAccretionRate')
            parent.append(indent)
            
        except KeyError:
            pass

    def temperatureExtrema(self,parent,token,xlink):
        
        try:
            indent = ET.Element('iwxxm-us:extremeValuePeriod')
            indent.set('unit','hour')
            indent.text = token['period']
            parent.append(indent)
            
        except KeyError:
            raise
        
        indent = ET.SubElement(parent,'iwxxm-us:extremeValueType')
        indent.set('xlink:href',xlink['href'])
        indent.set('xlink:title',xlink['title'])
        indent = ET.SubElement(parent,'iwxxm-us:processedValue')
        indent.set('uom','Cel')
        indent.text = '%.1f' % token['value']
        indent = ET.SubElement(parent,'iwxxm-us:processedWeatherElement')
        indent.set('xlink:href','%s/StatisticallyProcessedWeatherElements/Temperature/' % FMH1URL)

    def minTemperature(self,parent,token):
        
        xlink = {'href':'http://codes.wmo.int/grib2/codeflag/4.10/3',
                 'title':'Minimum'}
        
        indent = ET.Element('iwxxm-us:statisticallyProcessedQuantity')
        try:
            self.temperatureExtrema(indent,token,xlink)
            parent.append(indent)

        except KeyError:
            pass
        
    def maxTemperature(self,parent,token):
        
        xlink = {'href':'http://codes.wmo.int/grib2/codeflag/4.10/2',
                 'title':'Maximum'}
        
        indent = ET.Element('iwxxm-us:statisticallyProcessedQuantity')
        try:
            self.temperatureExtrema(indent,token,xlink)
            parent.append(indent)

        except KeyError:
            pass
    #
    # Variations in Observed Properties section
    # 
    def twrvsby(self,parent,token):

        indent = ET.SubElement(parent,'iwxxm-us:towerVisibility')
        indent.set('uom','m')
        factor = 1.0
        if token['uom'] == '[mi_i]':
            factor = 1609.34
        indent.text = '%.1f' % (token['value']*factor)

    def vrbrvr(self,parent,token):

        for rwy,lo,hi,oper in zip(token['rwy'].split(),token['lo'].split(),token['hi'].split(),
                                  list(token['oper'])):
            
            indent = ET.SubElement(parent,'iwxxm-us:variableRVR')            
            indent1 = ET.SubElement(indent,'iwxxm-us:runway')
            indent2 = ET.SubElement(indent1,'saf:RunwayDirection')
            indent2.set('gml:id','VRBRVRRWY_%s' % rwy)
            indent3 = ET.SubElement(indent2,'saf:designator')
            indent3.text = rwy
        
            indent1 = ET.SubElement(indent,'iwxxm-us:maximumRVR')
            indent1.set('uom','m')
            if token['uom'] == 'm':
                indent1.text = hi
            elif token['uom'] == '[ft_i]':
                indent1.text = '%.1f' % (float(hi)*0.3048)

            indent1 = ET.SubElement(indent,'iwxxm-us:minimumRVR')
            indent1.set('uom','m')
            if token['uom'] == 'm':
                indent1.text = lo
            elif token['uom'] == '[ft_i]':
                indent1.text = '%.1f' % (float(lo)*0.3048)

            if oper in ['M','P']:
                indent1 = ET.SubElement(indent,'iwxxm-us:rvrOperator')
                indent1.text = {'M':'BELOW','P':'ABOVE'}.get(oper)
        
    def vcig(self,parent,token):

        indent = ET.SubElement(parent,'iwxxm-us:variableCeilingHeight')
        indent1 = ET.SubElement(indent,'iwxxm-us:maximumCeilingHeight')
        indent1.set('uom','[ft_i]')
        indent1.text = str(token['hi'])
        indent1 = ET.SubElement(indent,'iwxxm-us:minimumCeilingHeight')
        indent1.set('uom','[ft_i]')
        indent1.text = str(token['lo'])
        
    def vvis(self,parent,token):

        indent = ET.SubElement(parent,'iwxxm-us:variableVisibility')
        indent1 = ET.SubElement(indent,'iwxxm-us:maximumVisibility')
        indent2 = ET.SubElement(indent1,'iwxxm-us:extremeValuePeriod')
        indent2.set('unit','minute')
        indent2.text = '10'
        indent2 = ET.SubElement(indent1,'iwxxm-us:extremeValueType')
        indent2.set('xlink:href','http://codes.wmo.int/grib2/codeflag/4.10/2')
        indent2.set('xlink:title','Maximum')
        indent2 = ET.SubElement(indent1,'iwxxm-us:processedValue')
        indent2.set('uom','m')
        indent2.text = '%.1f' % (token['hi']*1609.34)

        indent2 = ET.SubElement(indent1,'iwxxm-us:processedWeatherElement')
        indent2.set('xlink:href','http://codes.wmo.int/common/quantity-kind/aeronauticalVisibility')

        indent1 = ET.SubElement(indent,'iwxxm-us:minimumVisibility')
        indent2 = ET.SubElement(indent1,'iwxxm-us:extremeValuePeriod')
        indent2.set('unit','minute')
        indent2.text = '10'
        indent2 = ET.SubElement(indent1,'iwxxm-us:extremeValueType')
        indent2.set('xlink:href','http://codes.wmo.int/grib2/codeflag/4.10/3')
        indent2.set('xlink:title','Minimum')
        indent2 = ET.SubElement(indent1,'iwxxm-us:processedValue')
        indent2.set('uom','m')
        indent2.text = '%.1f' % (token['lo']*1609.34)

        indent2 = ET.SubElement(indent1,'iwxxm-us:processedWeatherElement')
        indent2.set('xlink:href','http://codes.wmo.int/common/quantity-kind/aeronauticalVisibility')

        indent1 = ET.SubElement(indent,'iwxxm-us:belowMinimumReportable')
        indent1.text = 'false'
        if token.has_key('oper'):
            indent1.text = 'true'
        
    def vsky(self,parent,token):
        
        indent = ET.SubElement(parent,'iwxxm-us:variableSkyCondition')
        indent1 = ET.SubElement(indent,'iwxxm-us:heightOfVariableLayer')
        indent1.set('uom','[ft_i]')
        indent1.text = str(token['hgt'])
        indent1 = ET.SubElement(indent,'iwxxm-us:firstSkyCoverValue')
        indent1.set('xlink:href','http://codes.wmo.int/bufr4/codeflag/0-20-008/%d' % _CldCvr[token['cvr1']][0])
        indent1.set('xlink:title',_CldCvr[token['cvr1']][1])
        indent1 = ET.SubElement(indent,'iwxxm-us:secondSkyCoverValue')
        indent1.set('xlink:href','http://codes.wmo.int/bufr4/codeflag/0-20-008/%d' % _CldCvr[token['cvr2']][0])
        indent1.set('xlink:title',_CldCvr[token['cvr2']][1])

    def pcpnhist(self,parent,token):
        
        inputstr = token['str']
        issueTime = time.gmtime(self.decodedMetar['itime']['value'])
        pcphistory = {}
            
        for match in _getAllMatches(_re_pcpnhist,inputstr):
            
            ww = match.get('PCP')
            timeHistory = match.get('TIME')
            events = []
            
            for event in _getAllMatches(_re_event,timeHistory):
                
                issueTimeList = list(issueTime)
                e = event.get('EVENT')
                hhmm = event.get('TIME')
                
                if len(hhmm) == 2:
                    issueTimeList[4] = int(hhmm)
                elif len(hhmm) == 4:
                    issueTimeList[3:5] = int(hhmm[:2]),int(hhmm[2:])
                    fix_date(issueTimeList)
                else:
                    continue
                
                events.append((e,issueTimeList))

            pcphistory[ww] = events
        #
        # Okay have broken down the history into individual weather types and times
        for ww in pcphistory.keys():
            for event,tms in pcphistory[ww]:
                
                url = '%s/BeginOrEnd/%s' % (FMH1URL,_BeginEnd.get(event))
                indent = ET.Element('iwxxm-us:beginEndWeather')

                indent1 = ET.SubElement(indent,'iwxxm-us:weatherBeginEndTime')
                indent1.set('gml:id','%s-%c%s' % (ww,event,time.strftime('%H%MZ',tms)))
                
                indent2 = ET.SubElement(indent1,'gml:timePosition')
                indent2.text = time.strftime('%Y-%m-%dT%H:%M:%SZ',tms)
                
                indent1 = ET.SubElement(indent,'iwxxm-us:weatherBeginOrEnd')
                indent1.set('xlink:href',url)
                
                codes = self.wwCodes[ww]
                indent1 = ET.SubElement(indent,'iwxxm-us:weatherType')
                indent1.set('xlink:href',codes['uri'])
                indent1.set('xlink:title',codes['title'])

                parent.append(indent)

    def wshft(self,parent,token):

        indent = ET.SubElement(parent,'iwxxm-us:windShift')
        indent1 = ET.SubElement(indent,'iwxxm-us:timeOfWindShift')
        indent1.set('gml:id','wndshft-%s' % time.strftime('%H%MZ',time.gmtime(token['itime'])))
        indent2 = ET.SubElement(indent1,'gml:timePosition')
        indent2.text = time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(token['itime']))
        
        try:
            token['fropa']
            indent1 = ET.SubElement(indent,'iwxxm-us:frontalPassageIndicator')
            indent1.text = 'true'

        except KeyError:
            pass

    def pkwnd(self,parent,token):
        
        indent = ET.SubElement(parent,'iwxxm-us:aerodromePeakWind')
        indent1 = ET.SubElement(indent,'iwxxm-us:peakWindDirection')
        indent1.set('uom','deg')
        indent1.text = str(token['dd'])
        
        indent1 = ET.SubElement(indent,'iwxxm-us:peakWindSpeed')
        indent1.set('uom','km/h')
        factor = 1.0
        try:
            if self.decodedMetar['wind']['str'][-2:] == 'KT':
                factor = 1.85184
        except KeyError:
            pass
        
        indent1.text = '%.1f' % (token['ff']*factor)
        
        indent1 = ET.SubElement(indent,'iwxxm-us:timeOfPeakWind')
        indent1.set('gml:id','peakWind-%s' % time.strftime('%H%MZ',time.gmtime(token['itime'])))
        indent2 = ET.SubElement(indent1,'gml:timePosition')
        indent2.text = time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(token['itime']))

    def ostype(self,parent,token):

        url = '%s/ObservingSystemType/%s' % (FMH1URL,_OSType[token['str']])
        indent = ET.SubElement(parent,'iwxxm-us:observingSystemType')
        indent.set('xlink:href',url)

    def ssistatus(self,parent,token):
        pass
    
    def maintenance(self,parent,token):

        indent = ET.SubElement(parent,'iwxxm-us:maintenanceIndicator')
        indent.text='true'
        
    def tstmvmt(self,parent,token):
        #
        # One movement in parsed string.
        mov = token['movement']['ATSTN']['sector0']
        if mov['ccw'] > mov['cw']:
            mov['ccw'] -= 360.0
        
        for distance in token['locations'].keys():
            
            distanceInfo = _Distance[distance]
            
            for spans in token['locations'][distance].keys():
                indent = ET.SubElement(parent,'iwxxm-us:significantWeatherAndCloudLocation')
                if distanceInfo['title'] == 'OVERHEAD':
                    indent1 = ET.SubElement(indent,'iwxxm-us:convectionOverhead')
                    indent1.text = 'true'
                    
                indent1 = ET.SubElement(indent,'iwxxm-us:convectionExtremeCounterClockwiseDirection')
                indent1.set('uom','deg')
                indent1.text = '%.1f' % token['locations'][distance][spans]['ccw']
                indent1 = ET.SubElement(indent,'iwxxm-us:convectionExtremeClockwiseDirection')
                indent1.set('uom','deg')
                indent1.text = '%.1f' % token['locations'][distance][spans]['cw']
                indent1 = ET.SubElement(indent,'iwxxm-us:convectionDirectionOfMotion')
                indent1.set('uom','deg')
                indent1.text = '%d' % (sum(mov.values())/2)
                
                if distanceInfo['title'] not in ['OVERHEAD','']:
                    indent1 = ET.SubElement(indent,'iwxxm-us:convectionDistance')
                    indent1.set('xlink:href', distanceInfo['href'])
                    indent1.set('xlink:title', distanceInfo['title'])
                
    def lightning(self,parent,token):

        try:
            frequencyInfo = _Frequency[token['frequency']]
        except KeyError:
            pass

        for distance in token['locations'].keys():
            
            distanceInfo = _Distance[distance]
            
            for spans in token['locations'][distance].keys():
                indent = ET.SubElement(parent,'iwxxm-us:lightning')
                if distanceInfo['title'] == 'OVERHEAD':
                    indent1 = ET.SubElement(indent,'iwxxm-us:lightningOverhead')
                    indent1.text = 'true'
                    
                indent1 = ET.SubElement(indent,'iwxxm-us:lightningExtremeCounterClockwiseDirection')
                indent1.set('uom','deg')
                indent1.text = '%.1f' % token['locations'][distance][spans]['ccw']

                indent1 = ET.SubElement(indent,'iwxxm-us:lightningExtremeClockwiseDirection')
                indent1.set('uom','deg')
                indent1.text = '%.1f' % token['locations'][distance][spans]['cw']
                
                try:
                    indent1 = ET.Element('iwxxm-us:lightningFrequency')
                    indent1.set('xlink:href', frequencyInfo['href'])
                    indent1.set('xlink:title', frequencyInfo['title'])
                    indent.append(indent1)
                    
                except NameError:
                    pass

                try:
                    indent1 = ET.Element('iwxxm-us:lightningType')
                    indent1.set('xlink:href','http://nws.weather.gov/codes/FHM-1/LightningType/%s' % token['types'])
                    indent1.set('xlink:title',token['types'])
                    indent.append(indent1)
                    
                except KeyError:
                    pass
                
                if distanceInfo['title'] not in ['OVERHEAD','']:
                    indent1 = ET.SubElement(indent,'iwxxm-us:lightningDistance')
                    indent1.set('xlink:href', distanceInfo['href'])
                    indent1.set('xlink:title', distanceInfo['title'])
    
    def obsc(self,parent,token):

        codes,cvr,hgt = self.wwCodes[token['pcp']],token['sky'][:-3],token['sky'][-3:]

        indent = ET.SubElement(parent,'iwxxm-us:obscuration')
        indent1 = ET.SubElement(indent,'iwxxm-us:heightOfWeatherPhenomenon')
        indent1.set('uom','[ft_i]')
        indent1.text = str(int(hgt)*100)

        indent1 = ET.SubElement(indent,'iwxxm-us:obscurationAmount')
        indent1.set('xlink:href','http://codes.wmo.int/bufr4/codeflag/0-20-008/%d' % _CldCvr[cvr][0])
        indent1.set('xlink:title', _CldCvr[cvr][1])

        indent1 = ET.SubElement(indent,'iwxxm-us:weatherCausingObscuration')
        indent1.set('xlink:href',codes['uri'])
        indent1.set('xlink:title',codes['title'])
    
    def sectorvis(self,parent,token):

        factor = 1.0
        if token['uom'] == '[mi_i]':
            factor = 1609.34
            
        indent = ET.SubElement(parent,'iwxxm-us:sectorVisibility')
        indent1= ET.SubElement(indent,'iwxxm-us:compassDirection')
        indent1.set('uom','deg')
        if token['direction'][0] > token['direction'][1]:
            indent1.text = '360'
        else:
            indent1.text = '%d' % (sum(token['direction'])/2)

        indent1= ET.SubElement(indent,'iwxxm-us:visibilityMeasuredDistance')
        indent1.set('uom','m')
        indent1.text = '%.1f' % (token['value']*factor)

        indent1= ET.SubElement(indent,'iwxxm-us:belowMinimumReportable')
        indent1.text = 'false'
        if token.has_key('oper'):
            indent1.text = 'true'
        
    def vis2ndlocation(self,parent,token):

        factor = 1.0
        if token['uom'] == '[mi_i]':
            factor = 1609.34

        indent = ET.SubElement(parent, 'iwxxm-us:location')
        indent.set('gml:id','vis2ndloc')
        indent1 = ET.SubElement(indent,'saf:designator')
        indent1.text = token['location']
        
        indent = ET.SubElement(parent, 'iwxxm-us:visibility')
        indent.set('uom','m')
        indent.text = '%.1f' % (token['value']*factor)
        
        indent = ET.SubElement(parent, 'iwxxm-us:visibilityBelowSensorMinimum')
        indent.text = 'false'
        if token.has_key('oper'):
            indent.text = 'true'
        
    def cig2ndlocation(self,parent,token):

        indent = ET.SubElement(parent, 'iwxxm-us:ceilingHeight')
        indent.set('uom','[ft_i]')
        indent.text = '%.1f' % token['value']

        indent = ET.SubElement(parent, 'iwxxm-us:location')
        indent.set('gml:id','cig2ndloc')
        indent1 = ET.SubElement(indent,'saf:designator')
        indent1.text = token['location']
    
    def result(self,parent):

        indent = ET.SubElement(parent,'om:result')
        metObRecord = ET.SubElement(indent,'%s:MeteorologicalAerodromeObservationRecord' % self.defaultNSPrefix)
        metObRecord.set('gml:id','%s-maor' % self.ICAOId)
        metObRecord.set('cloudAndVisibilityOK',self.cavokPresent)
        #
        for element in self.ObservationResults:
            
            function = getattr(self,element)
            try:
                function(metObRecord,self.decodedMetar[element])
            #    
            # Some elements generate a nilReason if missing from the observation because they are
            # considered mandatory, but for whatever reason, the observation system does not report
            # it.
            #
            except KeyError:
                pass
            
#                if self.cavokPresent == 'true':                    
#                    if element in ['temp','alt','wind']:
#                        function(metObRecord,None)
#                else:
#                    if element in ['temp','alt','wind','vsby','sky']:
#                        function(metObRecord,None)
        #
        # If iwxxm document, quit early
        if self.defaultNSPrefix == 'iwxxm':
            return
        
        visuallyObservedTypes = ET.Element('iwxxm-us:visuallyObservablePhenomena')
        # 
        for element in ['tstmvmt','obsc','lightning']:
            
            function = getattr(self,element)
            try:
                function(visuallyObservedTypes,self.decodedMetar[element])
            except KeyError, e:
                pass
        #
        if len(visuallyObservedTypes):
            metObRecord.append(visuallyObservedTypes)
        #
        observedPropertySecondLocation = ET.Element('iwxxm-us:observedPropertyAtSecondLocation')
        for element in ['cig2ndlocation','vis2ndlocation']:
            
            function = getattr(self,element)
            try:
                function(observedPropertySecondLocation,self.decodedMetar[element])
            except KeyError, e:
                pass

        if len(observedPropertySecondLocation):
            metObRecord.append(observedPropertySecondLocation)            
        #
        variationsInObservedPropertiesTypes = ET.Element('iwxxm-us:variationsInObservedProperties')
        for element in ['twrvsby','vcig','vvis','sectorvis','vsky','pcpnhist','wshft','pkwnd','vrbrvr']:
            
            function = getattr(self,element)
            try:
                function(variationsInObservedPropertiesTypes,self.decodedMetar[element])
            except KeyError, e:
                pass
        #
        if len(variationsInObservedPropertiesTypes):
            metObRecord.append(variationsInObservedPropertiesTypes)
        #
        # Last element in a iwxxm-us document
        try:
            self.ostype(self.XMLDocument,self.decodedMetar['ostype'])
        except KeyError, e:
            pass
        
if __name__ == '__main__':
    
    import argparse, sys
    import usMetarDecoder
    
    cmdlneParser = argparse.ArgumentParser()
    cmdlneParser.add_argument('tacFile', help='File containing one or more METAR TACs separated by "="')
    cmdlneParser.add_argument('-g','--debug', action='store_true', default=False,
                              help='Add TAC as a comment in the XML document')
    cmdlneParser.add_argument('-E','--allowUSExtensions', action='store_true', default=False,
                              help='Generate IWXXM-US XML documents when appropriate')
    cmdlneParser.add_argument('-N','--doNameSpaceDeclarations', action='store_true', default=False,
                              help='Define namespaces and their prefixes in root element')
    
    args = cmdlneParser.parse_args()
    decoder = usMetarDecoder.Decoder()
    encoder = XMLEncoder()
    
    allobs = ['%s=' % x for x in open(args.tacFile).read().split('=')]
    allobs.pop()
    #
    # Convert TAC to python dictionary
    for report in allobs:
        result = decoder(report)
        #
        # Pass results to encoder. The first argument, the python dictionary,
        # is required. The other two show the optional named arguments and
        # their default values. They don't need to be present.
        #
        try:
            encoder(result,report=report,
                    allowUSExtensions=args.allowUSExtensions,
                    nameSpaceDeclarations=args.doNameSpaceDeclarations,
                    debugComment=args.debug)
            encoder.printXML(sys.stdout)
        except KeyError:
            print 'Unknown location:',result['ident']['str']
