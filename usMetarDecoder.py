#!/usr/bin/env python2
#
# Name: usMetarDecoder.py
# Purpose: To decode, in its entirety, the METAR/SPECI traditional alphanumeric codes as
#          described in the OFCM FMH-1 (2005) handbook. This decoder is meant for US observations only,
#          not international ones.
#
# Author: Mark Oberfield
# Organization: NOAA/NWS/OSTI/MDL 
#
import exceptions, logging, re, time, types
import tpg

_CompassDegrees = {'N':(337.5,022.5), 'NE':(022.5,067.5), 'E':(067.5,112.5), 'SE':(112.5,157.5),
                   'S':(157.5,202.5), 'SW':(202.5,247.5), 'W':(247.5,292.5), 'NW':(292.5,337.5)}
###############################################################################
# local exceptions
class Error(exceptions.Exception): pass

##############################################################################
# regular expressions for identifying elements in a METAR/SPECI
#
_SkyCov = 'FEW|SCT|BKN|(0|O)VC|///'
_Cld = '(%s)[\d/]{3}(CB|TCU|///)?' % _SkyCov
_Fract = '[1-9\s]{0,2}[1357]/([248]|16)'
_Obv = 'BR|FG|FU|VA|DU|SA|HZ|PY|PO|SQ|[+]?FC|SS|DS|SN'
_ObvQ = 'MI|PR|BC|DR|BL|FZ'
_Pcp = 'DZ|RA|SN|SG|IC|PE|GR|GS|UP|PL|//\s'
_PcpQ = 'SH|TS|FZ'
_CompassPts = '[NEWS]{1,2}'
_Movement = '(?P<mov>MOV(D|G)?\s+(%s|OHD))' % _CompassPts
_Location = '(OHD|VC|DSNT|ALQD?S|\d{0,2}%s(?=[-\s])|AND|[-\s])+' % _CompassPts
_secondLocation = '\s+(?P<loc>(R(WY)?\s*\d{2}[RCL]?|\S+))'
_complexFraction = '(?P<%s>\d{1,2}(?!/))?(?P<%s>(M|\s+)?\d/\d{1,2})?'

_re_rvr = re.compile(r'R(?P<rwy>\w+)/(?P<oper>[PM]?)(?P<mean>\d{4})(?!V)(?P<tend>[UDN]?)(FT)?')
_re_vrbrvr = re.compile(r'R(?P<rwy>\w+)/(?P<minus>M)?(?P<lo>\d{4})V(?P<plus>P)?(?P<hi>\d{4})(FT)?')
#
# _Location is tough
_re_VC = re.compile(r'VC(ALQD?S|%s|AND|[-\s])+' % _CompassPts )
_re_DSNT = re.compile(r'DSNT(ALQD?S|%s|AND|[-\s])+' % _CompassPts )

_Options = r"""
set lexer = ContextSensitiveLexer 
set lexer_dotall = True
"""

_Separator = r"separator spaces:    '\s+' ;"

_pcptok = '[+-]?(%s)?(%s)+' % (_PcpQ, _Pcp)
_obvtok = '(%s)?(%s)' % (_ObvQ, _Obv)

_TokList = [
    # mandatory part
    ('type', r'METAR|SPECI'),
    ('ident', r'[A-Z][A-Z0-9]{3}'),
    ('itime', r'\d{6}Z'),
    ('autocor', r'AUTO|COR'),
    ('wind', r'(VRB|\d{3})\d{2,3}(G\d{2,3})?KT'),
    ('wind_vrb', r'\d{3}V\d{3}'),
    ('vsby',r'(?P<whole>\d{1,3}(?!/))?(?P<fraction>(M|\s+)?\d/\d{1,2})?SM'),
    ('rvr', r'R\w+/[MP]?\d{4}(V?P?\d{4})?[UDN]?FT'),
    ('funnel', r'[+]?FC'),
    ('pcp', r'%s|TS(\s+%s)?' % (_pcptok, _pcptok)),
    ('obv', r'%s(\s+%s)*' % (_obvtok, _obvtok)),
    ('vcnty', r'VC\w+'),
    ('sky', r'SKC|CLR|VV[/\d]{3}|(%s((\s+)?%s)*)' % (_Cld, _Cld)),
    ('temp', r'((M|-)?\d{2}|MM)/((M|-)?\d{2}|MM)?'),
    ('alt', r'[AQ]\d{3,4}'),
    # US remarks
    ('ostype',r'A(0|O)(1|2)'),
    ('pkwnd',r'PK\s+WND\s+\d{5,6}/\d{2,4}'),
    ('wshft',r'WSHFT\s+\d{2,4}(\s+FROPA)?'),
    ('sfcvis', r'SFC\s+VIS\s+'+_complexFraction % ('whole','fraction')),
    ('twrvis', r'TWR\s+VIS\s+'+_complexFraction % ('whole','fraction')),
    ('vvis', r'(VSBY|VIS)\s+'+_complexFraction % ('vintlo','vfraclo') +'V'+_complexFraction % ('vinthi','vfrachi')),
    ('sctrvis',r'VIS\s+%s\s+' % _CompassPts + _complexFraction % ('whole','fraction')),
    ('vis2loc',r'VIS\s+'+_complexFraction % ('whole','fraction') +_secondLocation),
    ('ltg',r'((OCNL|FRQ|CONS)\s+)?LTG(CG|IC|CC|CA){0,4}%s' % _Location),
    ('tstmvmt',r'(CBMAM|CB|TS)%s%s' % (_Location,_Movement)),
    ('pcpnhist',r'((SH|FZ)?(TS|%s)((B|E)\d{2,4})+)+' % _Pcp),
    ('hail',r'GR\s+'+_complexFraction % ('whole','fraction')),
    ('vcig', r'CIG\s+(\d{3})V(\d{3})'),
    ('obsc',r'(FG|FU|DU|VA|HZ)\s+(%s)\d{3}' % _SkyCov),
    ('vsky', r'(%s)(\d{3})?\s+V\s+(%s)' % (_SkyCov,_SkyCov)),
    ('cig2loc',r'CIG\s+\d{3}' + _secondLocation),
    ('pchgr',r'PRES(R|F)R'),
    ('mslp', r'SLP(\d{3}|///)'),
    ('nospeci',r'NOSPECI'),
    ('aurbo', r'AURBO'),
    ('contrails', r'CONTRAILS'),
    ('snoincr', r'SNINCR\s+\d/[\d/]{1,3}'),
    ('runway',r'WR(\d{3}[RCL]?)|///'),
    ('other',r'(FIRST|LAST)'),
    ('pcp1h', r'P(\d{3,4}|/{3,4})'),
    ('pcp6h',r'6(\d{4}|////)'),
    ('pcp24h',r'7(\d{4}|////)'),    
    ('iceacc',r'I[1,3,6](\d{3}|///)'),
    ('snodpth',r'4/(\d{3}|///)'),
    ('lwe',r'933(\d{3}|///)'),
    ('sunshine',r'98(\d{3}|///)'),
    ('tempdec', r'T[01]\d{3}[01]\d{3}'),
    ('maxt6h',r'1(\d{4}|////)'),
    ('mint6h',r'2(\d{4}|////)'),
    ('xtrmet',r'4[\d/]{8}'),
    ('ptndcy3h',r'5(\d{4}|////)'),
    ('ssindc',r'(RVR|PWI|P|FZRA|TS|SLP)NO|(VISNO|CIGNO)(\s(RWY\d+|(N|NE|E|SE|S|SW|W|NW)\s))?'),
    ('estwind',r'WIND\s+ESTIMATED'),
    ('maintenance',r'\$'),
    ('any', r'\S+'),
    #
    # Consume any unrecognizable tokens, except "RMK'
    ('noRMK',r'(?!RMK)\S+'),
]

_Tokens = '\n'.join([r"token %s: '%s' ;" % tok for tok in _TokList])
#
# For main body of METAR there are two types of common errors identified so far:
#
#   Permutation error -- wrong order of elements. A solution is to repeat main body search twice, hence {1,2}.
#   Another is a typo of some sort. Repeated search, e.g.{1,2}, will not fix a typo. The noRMK expression
#   will consume a typo, then rescan to finish any remaining elements in main body of METAR.
#
#   This is not exhaustive search or parsing strategy; some errors will not be caught. The intent here is to
#   decode a majority of the US METAR/SPECI. Badly malformed reports will not have all elements decoded.
#
_Rules = r"""
START/e -> METAR/e $ e=self.unparsed() $ ;
METAR -> Type Ident ('NIL' any* | ITime Autocor? Body) ;
Body -> Mandatory{1,2} noRMK? Mandatory Remarks? ;
Mandatory -> (Wind? Wind_Vrb? Vsby? Rvr* WWGroup* Sky? Temp? Alt?) ;
WWGroup -> (Pcp|Obv|Vcnty|Funnel) ;
Remarks -> 'RMK' (Ostype|PkWnd|Wshft|SfcVis|TwrVis|VVis|SctrVis|Vis2Loc|Ltg|PcpnHist|TstmMvmt|Hail|VCig|Obsc|VSky|Cig2Loc|Pchgr|Slp|Nospeci|Aurbo|Contrails|Snoincr|Other|Pcp1h|Pcp6h|Pcp24h|Iceacc|Snodpth|Lwe|Sunshine|TempDec|MaxT6h|MinT6h|XtrmeT|Ptndcy3h|Ssindc|Maintenance|Estwind|any)* ;

Type -> type/x $ self.obtype(x) $ ;
Ident -> ident/x $ self.ident(x) $ ;
ITime -> itime/x $ self.itime(x) $ ;
Autocor -> autocor/x $ self.autocor(x) $ ;
Wind -> wind/x $ self.wind(x) $ ;
Wind_Vrb -> wind_vrb/x $ self.wind(x) $ ;
Vsby -> vsby/x $ self.vsby(x) $ ;
Rvr -> rvr/x $ self.rvr(x) $ ;
Pcp -> pcp/x $ self.pcp(x) $ ;
Obv -> obv/x $ self.obv(x) $ ;
Vcnty -> vcnty/x $ self.vcnty(x) $ ;
Funnel -> funnel/x $ self.obv(x) $ ;
Sky -> sky/x $ self.sky(x) $ ;
Temp -> temp/x $ self.temp(x) $ ;
Alt -> alt/x $ self.alt(x) $ ;

Ostype -> ostype/x $ self.ostype(x) $ ;
PkWnd -> pkwnd/x $ self.pkwnd(x) $ ;
Wshft -> wshft/x $ self.wshft(x) $ ;
SfcVis -> sfcvis/x $ self.sfcvsby(x) $ ;
TwrVis -> twrvis/x $ self.twrvsby(x) $ ;
VVis -> vvis/x $ self.vvis(x) $ ;
SctrVis -> sctrvis/x $ self.sctrvis(x) $ ;
Vis2Loc -> vis2loc/x $ self.vis2loc(x) $ ;
Ltg -> ltg/x $ self.ltg(x) $ ;
PcpnHist -> pcpnhist/x $ self.pcpnhist(x) $ ;
TstmMvmt -> tstmvmt/x $ self.tstmvmt(x) $ ;
Hail -> hail/x $ self.hail(x) $ ;
VCig -> vcig/x $ self.vcig(x) $ ;
Obsc -> obsc/x $ self.obsc(x) $ ;
VSky -> vsky/x $ self.vsky(x) $ ;
Cig2Loc -> cig2loc/x $ self.cig2loc(x) $ ;
Pchgr -> pchgr/x $ self.pressureChgRapidly(x) $ ;
Slp -> mslp/x $ self.mslp(x) $ ;
Nospeci -> nospeci/x $ self.nospeci(x) $ ;
Aurbo -> aurbo/x $ self.aurbo(x) $;
Contrails -> contrails/x $ self.contrails(x) $;
Snoincr -> snoincr/x $ self.snoincr(x) $ ;
Other -> other/x $ self.other(x) $ ;
Pcp1h -> pcp1h/x $ self.pcp1h(x) $ ;
Pcp6h -> pcp6h/x $ self.pcp6h(x) $ ;
Pcp24h -> pcp24h/x $ self.pcp24h(x) $ ;
Iceacc -> iceacc/x $ self.iceacc(x) $ ;
Snodpth -> snodpth/x $ self.snodpth(x) $ ;
Lwe -> lwe/x $ self.lwe(x) $ ;
Sunshine -> sunshine/x $ self.sunshine(x) $ ;
TempDec -> tempdec/x $ self.tempdec(x) $ ;
MaxT6h -> maxt6h/x $ self.maxt6h(x) $ ;
MinT6h -> mint6h/x $ self.mint6h(x) $ ;
XtrmeT -> xtrmet/x $ self.xtrmet(x) $ ;
Ptndcy3h -> ptndcy3h/x $ self.prestendency(x) $ ;
Ssindc -> ssindc/x $ self.ssindc(x) $ ;
Estwind -> estwind/x $ self.estwind(x) $ ;
Maintenance -> maintenance/x $ self.maintenance(x) $ ;
"""

##############################################################################
# local functions
def valid_day(tms):
    """Checks if day of month is valid"""
    year, month, day = tms[:3]
    if day > 31:
        return 0
    if month in [4, 6, 9, 11] and day > 30:
        return 0
    if month == 2 and (year%4 == 0 and day > 29 or day > 28):
        return 0
    return 1

def getAllMatches(re,inputstr):

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

def processLocationString(locationString,locations):
    #
    # overhead is the simplest
    pos = locationString.find('OHD')
    if pos >= 0:
        locations['OHD'] = { 'sector0': { 'ccw':0.0,'cw':360.0 }}
        locationString = '%s%s' % (locationString[:pos],locationString[pos+4:])
    #
    # Parse out language "in the vicinity" (VC); shouldn't be mixed up with DSNT
    vcLocation = _re_VC.search(locationString)
    if vcLocation:
        vcString = locationString[(vcLocation.start()+2):vcLocation.end()]
        locations['VC'] = parseLocationString(vcString)
        locationString = '%s%s' % (locationString[:vcLocation.start()],locationString[vcLocation.end():])
            
    dsntLocation = _re_DSNT.search(locationString)
    if dsntLocation:
        dsntString = locationString[(dsntLocation.start()+4):dsntLocation.end()]
        locations['DSNT'] = parseLocationString(dsntString)
        locationString = '%s%s' % (locationString[:dsntLocation.start()],locationString[dsntLocation.end():])
    #
    # locationString now has what is left over....
    if locationString.strip():
        locations['ATSTN'] = parseLocationString(locationString)

    return

def parseLocationString(strng):

    spans = {}
    sector = -1

    for token in strng.split():        
        #
        # AND suggests a discontinuity
        if token == 'AND':
            continue        
        sector += 1        
        #
        # If a range of compass points are indicated, combine the spans if possible
        if token.find('-') > 0:
            for sectr in token.split('-'):
                try:
                    if spans['sector%d' % sector]['cw'] == _CompassDegrees[sectr][0]:
                        spans['sector%d' % sector]['cw'] = _CompassDegrees[sectr][1]
                    else:
                        raise KeyError

                except KeyError:
                    if spans.has_key('sector%d' % sector):
                        sector += 1
                        
                    spans['sector%d' % sector] = {'ccw': _CompassDegrees[sectr][0],
                                                  'cw' : _CompassDegrees[sectr][1]}
        #
        # No compass point span given
        else:
            try:
                spans['sector%d' % sector] = {'ccw': _CompassDegrees[token][0],
                                              'cw' : _CompassDegrees[token][1]}
            except KeyError:
                print 'Unexpected token in location string', strng
    #
    # Final pass to see if directions can be combined
    discontinuities = len(spans.keys())
    markedForDeletion = []
    
    for discnt in range(0,discontinuities):
        for target in range(discnt+1,discontinuities):
            try:
               markedForDeletion.index(target)
            except ValueError:
                if spans['sector%d' % discnt]['cw'] == spans['sector%d' % target]['ccw']:
                    spans['sector%d' % discnt]['cw'] = spans['sector%d' % target]['cw']
                    markedForDeletion.append(target)
        
    while markedForDeletion:
        try:
            del spans['sector%d' % markedForDeletion.pop()]
        except KeyError:
            pass
        
    return spans

##############################################################################
# decoder class
class Decoder(tpg.VerboseParser):
    """METAR decoder class"""

    __doc__ = '\n'.join([_Options, _Separator, _Tokens, _Rules])
    verbose = 3

    def __call__(self, metar):
        
        self._metar = {}
        self._first = 0
        if type(metar) == types.ListType:
            metar = '\n'.join(metar)
        #
        # Remove the EOT marker
        eot = metar.find('=')
        if eot > 0:
            metar = metar[:eot]+' '
        try:
            return super(Decoder, self).__call__(metar)

        except tpg.SyntacticError, e:
            logging.warning('Decoder fault: %s; METAR: %s' % (str(e),metar))
            return self._metar

        except Exception, e:
            logging.error('Unhandled exception in decoder: %s; METAR: %s' % (str(e),metar))
            return self._metar

    def index(self):
        
        ti = self.lexer.cur_token
        return ('%d.%d' % (ti.line+self._first, ti.column-1),
                '%d.%d' % (ti.end_line+self._first, ti.end_column-1))

    def eatCSL(self, name):
        """Overrides super definition"""
        try:
            value = super(Decoder, self).eatCSL(name)
            return value
        except tpg.WrongToken:
            raise

    def fix_date(self,tms):
        """Tries to determine month and year from report timestamp.
tms contains day, hour, min of the report, current year and month
"""
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

    #######################################################################
    # Methods called by the parser
    def alt(self, s):
        
        d = self._metar['alt'] = {'str': s, 'index': self.index(), 'uom':"[in_i'Hg]",
                                  'value':int(s[1:])/100.0}
        
    def ident(self, s):
        
        self._metar['ident'] = {'str': s, 'index': self.index()}

    def itime(self, s):
        
        d = self._metar['itime'] = {'str': s, 'index': self.index()}
        mday, hour, min = int(s[:2]), int(s[2:4]), int(s[4:6])
        try:
            if mday > 31 or hour > 23 or min > 59:
                raise Error('Invalid time')
            tms = list(time.gmtime())
            tms[2:6] = mday, hour, min, 0
            self.fix_date(tms)
            if not valid_day(tms):
                raise Error('Invalid day')
            d['value'] = time.mktime(tms)
        except Error, e:
            d['value'] = time.time()
            d['error'] = str(e)

    def obtype(self, s):
        
        self._metar['type'] = {'str': s, 'index': self.index()}

    def vvis(self, s):
        
        d = self._metar['vvis'] = {'str': s, 'index': self.index(), 'uom':'[mi_i]'}
        v = self.lexer.tokens[self.lexer.cur_token.name][0].search(s)
        vis = 0.0
        
        try:
            vis += float(v.group('vintlo').strip())
        except (AttributeError, ValueError):
            pass
            
        try:
            num, den = v.group('vfraclo').split('/', 1)
            if num[0] == 'M':
                if num != 'M1':
                    vis += float(num[1:])/float(den)
                d['oper']='M'
                
            else:
                vis += float(num)/float(den)
                
        except (AttributeError, ValueError):
            pass

        d['lo'] = vis
        
        vis = 0.0
        try:
            vis += float(v.group('vinthi').strip())
        except (AttributeError, ValueError):
            pass
            
        try:
            num, den = v.group('vfrachi').split('/', 1)
            vis += float(num)/float(den)
            metric = False
            
        except (AttributeError, ValueError):

            pass
        
        d['hi'] = vis
        d['uom'] = self._metar['vsby']['uom']
        #
        # Bad token processed
        if d['hi'] < d['lo']:
            del self._metar['vvsby']
            raise tpg.WrongToken
    #
    # SFC VIS found in comments
    def sfcvsby(self, s):
        
        v = self.lexer.tokens[self.lexer.cur_token.name][0].search(s)
        vis = 0.0
            
        try:
            vis += float(v.group('whole').strip())
        except (AttributeError, ValueError):
            pass
            
        try:
            num, den = v.group('fraction').split('/', 1)
            if num[0] == 'M':
                if num != 'M1':
                    vis += float(num[1:])/float(den)
                oper = 'M'
            else:
                vis += float(num)/float(den)
                
        except (AttributeError, ValueError):
            pass
        #
        # What is in the prevailing group is tower visibility
        self._metar['twrvsby'] = self._metar['vsby'].copy()
        self._metar['vsby'] = {'str': s,
                               'index': self.index(),
                               'value': vis,
                               'uom':self._metar['twrvsby']['uom']}
        try:
            self._metar['vsby']['oper'] = oper
        except NameError:
            pass
        
    def vsby(self, s):

        v = self.lexer.tokens[self.lexer.cur_token.name][0].search(s)
        vis = 0.0
        uom = 'm'
        if s[-2:] == 'SM':         # miles            
            uom = '[mi_i]'
            
        try:
            vis += float(v.group('whole').strip())
        except (AttributeError, ValueError):
            pass
            
        try:
            num, den = v.group('fraction').split('/', 1)
            if num[0] == 'M':
                if num != 'M1':
                    vis += float(num[1:])/float(den)
                oper = 'M'
            else:
                vis += float(num)/float(den)
                
        except (AttributeError, ValueError):
            pass
                
        d = self._metar['vsby'] = {'str': s, 'index': self.index(),
                                   'value': vis, 'uom': uom}
        try:
            d['oper'] = oper
        except NameError:
            pass

    def wind(self, s):
        #
        # Handle variable wind direction > 6kts which always comes after the wind group
        try:            
            d = self._metar['wind']
            d['index'] = (d['index'][0],self.index()[1])
            d['str'] = "%s %s" % (d['str'],s)
            ccw,cw = s.split('V')
            d.update({'ccw': ccw, 'cw': cw})
            return
        
        except KeyError:
            pass
        
        d = self._metar['wind'] = {'str': s, 'index': self.index()}
        if s.startswith('VRB'):
            dd = 'VRB'
        else:
            dd = s[:3]
            
        tok = s[3:-2].split('G', 1)
                
        ff = int(tok[0])
        d.update({'dd': dd, 'ff': ff, 'uom':'[kn_i]'})
            
        try:
            d['gg'] = int(tok[1])
        except IndexError:
            pass

    def obv(self, s):

        if 'obv' in self._metar:
            return
        
        self._metar['obv'] = {'str': s, 'index': self.index()}

    def pcp(self, s):

        self._metar['pcp'] = {'str': s, 'index': self.index()}

    def vcnty(self, s):

        d = self._metar['vcnty'] = {'str': s, 'index': self.index()}

    def sky(self, s):

        self._metar['sky'] = {'str': s, 'index': self.index()}

    def vsky(self,s):

        d = self._metar['vsky'] = {'str': s, 'index': self.index(), 'uom':'[ft_i]'}
        v = self.lexer.tokens[self.lexer.cur_token.name][0].search(s)
        try:
            d['hgt'] = int(v.group(3))*100
        except (TypeError,ValueError):
            pos = self._metar['sky']['str'].find(v.group(1))
            try:
                d['hgt'] = int(self._metar['sky']['str'][pos+3:pos+6])*100
            except ValueError:
                pos = self._metar['sky']['str'].find(v.group(4))
                d['hgt'] = int(self._metar['sky']['str'][pos+3:pos+6])*100
        
        d['cvr1'] = v.group(1)
        d['cvr2'] = v.group(4)
        
    def vcig(self,s):

        d = self._metar['vcig'] = {'str': s, 'index': self.index(), 'uom':'[ft_i]'}
        v = self.lexer.tokens[self.lexer.cur_token.name][0].search(s)
        d['lo']=int(v.group(1))*100
        d['hi']=int(v.group(2))*100
        
    def temp(self, s):

        d = self._metar['temp'] = {'str': s, 'index': self.index(), 'uom':'Cel'}
        tok = s.split('/')
        
        if tok[0][0] == 'M':
            try:
                tt = -int(tok[0][1:])
                d.update({'tt': tt})
                
            except ValueError:
                pass
        else:
            tt = int(tok[0])
            d.update({'tt': tt})
            
        try:
            if tok[1][0] == 'M':
                try:
                    td = -int(tok[1][1:])
                    d.update({'td': td})
                    
                except ValueError:
                    pass
            else:
                td = int(tok[1])
                d.update({'td': td})
                
        except (TypeError,IndexError):    
            pass
                    
    def tempdec(self, s):
        
        d = self._metar['tempdec'] = {'str': s, 'index': self.index()}
        tt = float(s[2:5])/10.0
        if s[1] == '1':
            tt = -tt
            
        td = float(s[6:9])/10.0
        if s[5] == '1':
            td = -td
            
        d.update({'tt': tt, 'td': td})

    def pcp1h(self, s):

        try:
            self._metar['pcp1h'] = {'str': s, 'index': self.index(), 'uom':'[in_i]',
                                    'value': float(s[1:])/100.0, 'period': '1'}
        except ValueError:
            self._metar['pcp1h'] = {'str': s, 'index': self.index()}

    def mslp(self, s):
        
        try:
            p = float(s[3:])/10.0

        except ValueError:
            self._metar['mslp'] =  {'str': s, 'index': self.index()}
            return
        
        if p >= 60.0:
            p += 900.0
        else:
            p += 1000.0
            
        d = self._metar['mslp'] =  {'str': s, 'index': self.index(), 'uom':'hPa', 'value':p }

    def autocor(self,s):
        self._metar['autocor'] = {'str': s, 'index': self.index()}
        
    def vrb_rvr(self,s,r):
        #
        # Multiple RVRs are possible
        try:
            d = self._metar['vrbrvr']
            d['index'] = (d['index'][0],self.index()[1])
            d['str'] += ' %s' % s
            d['lo'] += ' %s' % r.group('lo')
            d['hi'] += ' %s' % r.group('hi')    
            #
            # Optional items are kludgy...
            if r.group('plus'):
                d['oper'] += r.group('plus')
            else:
                d['oper'] += ' '
                
            if r.group('minus'):
                d['oper'] += r.group('minus')
            else:
                d['oper'] += ' '
            
        except KeyError:
            uom = 'm'
            if s[-2:] == 'FT':
                uom = '[ft_i]'
                
            self._metar['vrbrvr'] = {'str': s, 'index': self.index(), 'uom': uom }
            self._metar['vrbrvr'].update(r.groupdict())
            del self._metar['vrbrvr']['minus']
            del self._metar['vrbrvr']['plus']
            if r.group('minus'):
                self._metar['vrbrvr']['oper'] = 'M'
            elif r.group('plus'):
                self._metar['vrbrvr']['oper'] = 'P'
            else:
                self._metar['vrbrvr']['oper'] = ' '
                
    def rvr(self,s):
        
        r = _re_rvr.search(s)
        #
        # Variable RVR information is handled differently
        if r == None:
            r = _re_vrbrvr.search(s)
            if r:
                self.vrb_rvr(s,r)
            return
        #
        # Multiple RVRs are possible
        try:            
            d = self._metar['rvr']
            d['index'] = (d['index'][0],self.index()[1])
            d['str'] += ' %s' % s
            d['mean'] += ' %s' % r.group('mean')
            d['rwy'] += ' %s' % r.group('rwy')
            #
            # Optional items are kludgy...
            if r.group('oper'):
                d['oper'] += r.group('oper')
            else:
                d['oper'] += ' '
                
            if r.group('tend'):
                d['tend'] += r.group('tend')
            else:
                d['tend'] += ' '
            
        except KeyError:
            uom = 'm'
            if s[-2:] == 'FT':
                uom = '[ft_i]'
                
            self._metar['rvr'] = {'str': s, 'index': self.index(), 'uom': uom }
            self._metar['rvr'].update(r.groupdict())            
            if r.group('tend') == '':
                self._metar['rvr']['tend'] = ' '
            if r.group('oper') == '':
                self._metar['rvr']['oper'] = ' '
            
    def ostype(self,s):
        
        self._metar['ostype'] = {'str': s, 'index': self.index()}

    def pkwnd(self,s):
        
        d = self._metar['pkwnd'] = {'str': s, 'index': self.index()}
        wind,hhmm = s.split(' ')[-1].split('/')
        
        d['dd'] = int(wind[:3])
        d['ff'] = int(wind[3:])
            
        tms = list(time.gmtime(self._metar['itime']['value']))
        if len(hhmm) == 2:
            tms[4] = int(hhmm)
            d['itime'] = time.mktime(tms)
        
        elif len(hhmm) == 4:
            tms[3:5] = int(hhmm[:2]),int(hhmm[2:])
            self.fix_date(tms)
            d['itime'] = time.mktime(tms)
            
    def wshft(self,s):
        
        d = self._metar['wshft'] = {'str': s, 'index': self.index()}
        tokens = s.split()
        hhmm = tokens[1]
        tms = list(time.gmtime(self._metar['itime']['value']))

        if len(hhmm) == 2:
            tms[4] = int(hhmm)
            d['itime'] = time.mktime(tms)
        
        elif len(hhmm) == 4:
            if tms[3] != int(hhmm[:2]):
                tms[3:5] = int(hhmm[:2]),int(hhmm[2:])
                self.fix_date(tms)
            else:
                tms[4] = int(hhmm[2:])
                
            d['itime'] = time.mktime(tms)
            
        try: 
            tokens[2]
            d['fropa'] = 'yup'
        except IndexError:
            pass
            
    def twrvsby(self,s):
        
        v = self.lexer.tokens[self.lexer.cur_token.name][0].search(s)
        vis = 0.0
        
        try:
            vis += float(v.group('whole').strip())
        except (AttributeError, ValueError):
            pass
            
        try:
            num, den = v.group('fraction').split('/', 1)
            if num[0] == 'M':
                if num != 'M1':
                    vis += float(num[1:])/float(den)
                oper = 'M'
            else:
                vis += float(num)/float(den)
                
        except (AttributeError, ValueError):
            pass

        d = self._metar['twrvsby'] = {'str': s,
                                      'index': self.index(),
                                      'value': vis,
                                      'uom': self._metar['vsby']['uom']}
        try:
            d['oper'] = oper
            
        except NameError:
            pass
        
    def sctrvis(self,s):

        v = self.lexer.tokens[self.lexer.cur_token.name][0].search(s)            
        vis = 0.0
        
        try:
            vis += float(v.group('whole').strip())
        except (AttributeError, ValueError):
            pass
            
        try:
            num, den = v.group('fraction').split('/', 1)
            if num[0] == 'M':
                if num != 'M1':
                    vis += float(num[1:])/float(den)
                oper = 'M'
            else:
                vis += float(num)/float(den)
                
        except (AttributeError, ValueError):
            pass

        compassPt = s.split()[1]
        self._metar['sectorvis'] = {'str': s,
                                    'index': self.index(),
                                    'value': vis,
                                    'direction': _CompassDegrees[compassPt],
                                    'uom': self._metar['vsby']['uom']}
        try:
            self._metar['sectorvis']['oper'] = oper

        except NameError:
            pass
            

    def vis2loc(self,s):

        v = self.lexer.tokens[self.lexer.cur_token.name][0].search(s)            
        vis = 0.0
        try:
            vis += float(v.group('whole').strip())
        except (AttributeError, ValueError):
            pass
            
        try:
            num, den = v.group('fraction').split('/', 1)
            if num[0] == 'M':
                if num != 'M1':
                    vis += float(num[1:])/float(den)
                oper = 'M'
            else:
                vis += float(num)/float(den)
                
        except (AttributeError, ValueError):
            pass
        
        self._metar['vis2ndlocation'] = {'str': s,
                                         'index': self.index(),
                                         'value': vis,
                                         'location': v.group('loc'),
                                         'uom': self._metar['vsby']['uom'],
                                         }
        try:
            self._metar['vis2ndlocation']['oper'] = oper
        except NameError:
            pass
        
    def ltg(self,s):
        
        d = self._metar['lightning'] = {'str': s, 'index': self.index()}        
        lxr = self.lexer.tokens[self.lexer.cur_token.name][0].search(s)
        locations = {}
        #
        # Lightning flash frequency is optional
        frequency = lxr.group(2)
        if frequency:
            d['frequency'] = frequency
        #
        # Sorted lightning characteristics, if any
        bpos = s.find('LTG')+3
        epos = lxr.end(3)
        if epos > 0:
            ltgtypes = s[bpos:epos]
            sortedTypes = [ltgtypes[n:n+2] for n in range(0,len(ltgtypes),2)]
            sortedTypes.sort()
            d['types'] = ''.join(sortedTypes)            
        else:
            epos = bpos
        #
        # Location/Distance are present.        
        locationString = s[epos+1:].strip()
        processLocationString(locationString,locations)
        d['locations'] = locations.copy()
        
    def tstmvmt(self,s):

        d = self._metar['tstmvmt'] = {'str': s, 'index': self.index()}        
        
        mspos = s.find('MOV')
        locations = {}
        locationString = s[2:mspos]
        
        processLocationString(locationString,locations)
        
        d['locations'] = locations.copy()
        del locations
        
        locations = {}
        processLocationString(s[mspos+3:],locations)
        d['movement'] = locations.copy()
        
    def pcpnhist(self,s):
        
        try:
            d = self._metar['pcpnhist']
            d['str'] = '%s%s' % (d['str'],s)
            d['index'] = (d['index'][0],self.index()[1])
            
        except KeyError:
            self._metar['pcpnhist'] = {'str': s, 'index': self.index()}

    def hail(self,s):
        
        v = self.lexer.tokens[self.lexer.cur_token.name][0].search(s)            
        siz = 0.0
        try:
            siz += float(v.group('whole').strip())
        except (AttributeError, ValueError):
            pass
            
        try:
            num, den = v.group('fraction').split('/', 1)
            if num[0] == 'M':
                siz += float(num[1:])/float(den)
            else:
                siz += float(num)/float(den)
                
        except (AttributeError, ValueError):
            pass
                            
        self._metar['hail'] = {'str': s, 'value':siz, 'index': self.index(), 'uom':'[in_i]'}

    def obsc(self,s):

        pcp,sky = s.split()        
        self._metar['obsc'] = {'str': s,
                               'index': self.index(),
                               'pcp': pcp,
                               'sky': sky}

    def pressureChgRapidly(self,s):
        
        self._metar['pchgr'] = {'str': s, 'index': self.index(),
                                'value': {'R':'RISING','F':'FALLING'}.get(s[-2])}
        
    def cig2loc(self,s):
        
        c = self.lexer.tokens[self.lexer.cur_token.name][0].search(s)            
        value = int(s.split()[1])*100
        self._metar['cig2ndlocation'] = {'str': s, 'index': self.index(),
                                         'value': value, 'uom': '[ft_i]',
                                         'location':c.group('loc')}

    def nospeci(self,s):
        
        self._metar['nospeci'] = {'str': s, 'index': self.index()}
        
    def aurbo(self,s):
        
        self._metar['aurbo'] = {'str': s, 'index': self.index()}
        
    def contrails(self,s):
        
        self._metar['contrails'] = {'str': s, 'index': self.index()}
        
    def snoincr(self,s):
        
        d = self._metar['snoincr'] = {'str': s, 'index': self.index(), 'period': '1', 'uom':'[in_i]'}
        try:
            d['value'],d['depth'] = map(int,s.split(' ')[1].split('/'))
            
        except ValueError:
            pass
        
    def other(self,s):
        
        self._metar['event'] = {'str': s, 'index': self.index()}
        
    def pcp6h(self,s):
        
        try:
            d = self._metar['pcpamt'] = {'str': s, 'index': self.index(), 'uom':'[in_i]',
                                         'value': float(s[1:])/100.0}
        except ValueError:
            
            self._metar['pcpamt'] = {'str': s, 'index': self.index()}
            return
        
        if self._metar['type']['str'] == 'METAR':
            hm = self._metar['itime']['str'][2:5]
            if hm in ['025','085','145','205']:
                d['period'] = '3'
            elif hm in ['055','115','175','235']:
                d['period'] = '6'

    def pcp24h(self,s):
        
        try:
            self._metar['pcpamt24h'] = {'str': s, 'index': self.index(), 'uom':'[in_i]',
                                        'value': float(s[1:])/100.0,
                                        'period':'24'}
        except ValueError:
            self._metar['pcpamt24h'] = {'str': s, 'index': self.index()}
            

    def iceacc(self,s):
        
        try:
            self._metar['iceacc%c' % s[1]] = {'str': s, 'index': self.index(), 'uom':'[in_i]',
                                              'value': float(s[2:])/100.0,
                                              'period':'%d' % int(s[1])}
        except ValueError:
            self._metar['iceacc%c' % s[1]] = {'str': s, 'index': self.index()}
            
        
    def snodpth(self,s):
        
        try:
            self._metar['snodpth'] = {'str': s, 'index': self.index(), 'uom':'[in_i]',
                                      'period':'1',
                                      'value':float(s[3:])}
        except ValueError:
            self._metar['snodpth'] = {'str': s, 'index': self.index()}

    def lwe(self,s):
        
        try:
            self._metar['lwe'] = {'str': s, 'index': self.index(), 'uom':'[in_i]',
                                  'value':float(s[4:])/10.0}
        except ValueError:
            self._metar['lwe'] = {'str': s, 'index': self.index()}
            

    def sunshine(self,s):

        try:
            self._metar['ssmins'] = {'str': s, 'index': self.index(),
                                     'value':int(s[3:])}
        except ValueError:
            self._metar['ssmins'] = {'str': s, 'index': self.index()}

    def maxt6h(self,s):
        
        try:
            self._metar['maxT6h'] = {'str': s, 'index': self.index(),
                                     'value':float(s[3:])/10.0,
                                     'period':'6'}
            if s[2] == '1':
                self._metar['maxT6h']['value'] = -(self._metar['maxT6h']['value'])
                
        except ValueError:
            self._metar['maxT6h'] = {'str': s, 'index': self.index()}

    def mint6h(self,s):
        
        try:
            self._metar['minT6h'] = {'str': s, 'index': self.index(),
                                     'value':float(s[3:])/10.0,
                                     'period':'6'}
            if s[2] == '1':
                self._metar['minT6h']['value'] = -(self._metar['minT6h']['value'])

        except ValueError:
            self._metar['minT6h'] = {'str': s, 'index': self.index()}

    def xtrmet(self,s):
        
        try:
            self._metar['maxT24h'] = {'str': s, 'index': self.index(),
                                      'value':float(s[3:6])/10.0,
                                      'period':'24'}
        except ValueError:
            self._metar['maxT24h'] = {'str': s, 'index': self.index()}

        try:
            self._metar['minT24h'] = {'str': s, 'index': self.index(),
                                      'value':float(s[7:10])/10.0,
                                      'period':'24'}
        except ValueError:
            self._metar['minT24h'] = {'str': s, 'index': self.index()}
        
        try:
            if s[2] == '1':
                self._metar['maxT24h']['value'] *= -1.0

        except KeyError:
            pass
        
        try:
            if s[6] == '1':
                self._metar['minT24h']['value'] *= -1.0

        except KeyError:
            pass

    def prestendency(self,s):
        
        try:
            self._metar['ptndcy'] = {'str': s, 'index': self.index(),
                                     'character':s[1],
                                     'pchg':float(s[2:])/10.0}
        except ValueError:
            self._metar['ptndcy'] = {'str': s, 'index': self.index()}

    def estwind(self,s):

        self._metar['estwind'] = {'index': self.index()}
        
    def ssindc(self,s):

        try:
            d = self._metar['ssistatus']
            d['str'] = '%s %s' % (d['str'], s)
            d['index'] = (d['index'][0],self.index()[1])
            
        except KeyError:
            self._metar['ssistatus'] = {'str': s.strip(), 'index': self.index()}

    def maintenance(self,s):
        
        self._metar['maintenance'] = {'index': self.index()}
        
    def whiteOut(self,key):
        #
        # Starting, ending line and character positions
        index = self._metar[key]['index']
        slpos,scpos = map(int,index[0].split('.'))
        elpos,ecpos = map(int,index[1].split('.'))

        if slpos == elpos:
            self.unparsedText[slpos][scpos:ecpos] = ' ' * (ecpos-scpos)
        else:
            self.unparsedText[slpos][scpos:] = ' ' * len(self.unparsedText[slpos][scpos:])
            self.unparsedText[elpos][:ecpos+1] = ' ' * (ecpos+1)

        #print 'removed',key
        #print '\n'.join([''.join(x) for x in self.unparsedText])
        
    def unparsed(self):

        self.unparsedText = [list(x) for x in self.lexer.input.split('\n')]
        self.unparsedText.insert(0,[])
        #
        # Remove all tokens from input string that were successfully parsed.
        map(self.whiteOut,self._metar.keys())
        self.unparsedText.pop(0)
        #
        # Before the RMK token, if there is one, should be considered an error
        # After the RMK token, it is considered text added by the observer
        #
        rmk_pos = -1
        additiveText = []
        unrecognized = []
        
        for lne in self.unparsedText:
            try:
                pos = lne.index('R')
                if pos > -1 and lne[pos:pos+3] == ['R','M','K']:
                    rmk_pos = pos
                    unrecognized.append(''.join(lne[:pos]))
                    additiveText.append(''.join(lne[pos+3:]))
                    break
                
            except ValueError:
                pass
            #
            # RMK not found yet
            if rmk_pos == -1:
                unrecognized.append(''.join(lne))
            else:
                additiveText.append(''.join(lne))                        
        #
        # Reassemble and remove superfluous whitespaces
        try:
            text = ' '.join(additiveText).strip()
            if len(text):
                self._metar['additive'] = {'str':text}
                
        except IndexError:
            pass
            
        try:
            text = ' '.join(unrecognized).strip()
            if len(text):
                self._metar['unparsed'] = {'str':text}
                
        except IndexError:
            pass
        
        return self._metar
    
##############################################################################
# public part
##############################################################################
# test
def main(reports):
    import pprint
    pp = pprint.PrettyPrinter(indent=2)
    #
    # Create a US METAR decoder
    decoder = Decoder()
    #
    # Pass observations to it.
    for report in reports:
        logging.debug('BEGIN decoding %s '%report)
        d = decoder(report)
        print report
        pp.pprint(d)

    
if __name__ == '__main__':
    #
    # To perform unit testing, run this file with a single argument: a file name containing
    # observations. Each observation requires the key word METAR or SPECI as appropriate.
    #
    # To that end, provided a sample set of METAR/SPECI records under /data directory
    #
    import logging, sys

    #logging.basicConfig(filename='example.log',level=logging.DEBUG)
    #
    # The decoder is depending on the presence of the EOT '=' character, so we need to
    # append to the observations read in.
    #
    allobs = ['%s=' % x for x in open(sys.argv[1]).read().split('=')]
    #
    # Last item in the list is empty, so remove it.
    allobs.pop()
    main(allobs)
