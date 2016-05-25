#!/usr/bin/env python2
# -*- coding: utf-8 -*-
#
# Copyright (c) 2016, University Corporation for Atmospheric Research (UCAR)
#
import os,sys,traceback
import optparse
import datetime
import pytz
import re
import logging
import station_util

import usMetarDecoder as usMD
import METARXMLEncoder as MXE

bulletin = re.compile(r'(\x01.*?\x03)',re.DOTALL)

wmo_hdr = re.compile(r"""(
^(?P<prefix>.*?)\s*
(?P<seq>[0-9]{3})?\s*
(?P<wmo>
 (?P<ttaaii>[A-Z0-9]{6})\s
 (?P<cccc>[A-Z][A-Z0-9]{3})\s
 (?P<dd>[0-3][0-9])(?P<hh>[0-2][0-9])(?P<mm>[0-5][0-9])\s
 (?P<bbb>((RR|CC|AA)[A-Z])|P[A-Z]{2})?
)\s*
)""", re.VERBOSE|re.DOTALL)

metar_type = re.compile(r"""(
\s*(MTR[A-Z]{3}\s*)?
(?P<type>METAR|SPECI)\s*
)""", re.VERBOSE|re.DOTALL)

nill = re.compile(r"""(
(?P<type>(METAR|SPECI)\s(?P<icao>[A-Z]{4})\s[0-9]{6}Z\sNIL)
)""", re.VERBOSE|re.DOTALL)

us_metars =re.compile(r"""(
[K][0-9A-Z]{3}|P[AH][0-9A-Z]{2}
)""", re.VERBOSE|re.DOTALL)

usage = ("Usage: %prog [options] [filename]\n\n"
        "If no filename is specified, reads from STDIN")
parseopts = optparse.OptionParser(usage=usage)
parseopts.add_option('-v', action='count', dest='verbosity', default=0,
                         help='Verbosity level')
parseopts.add_option('-D', action='store', dest='outdir', default='',
                    help='Directory in which to output files')
parseopts.add_option('-w', action='store_true',
                    dest='writefiles', default=False,
                    help='Write output to disk instaed of STDOUT')
parseopts.add_option('-d', action='store_true',
                    dest='date_dirs', default=False,
                    help='Write output dated directories within -D dir')

opts, args = parseopts.parse_args()
verbosity = opts.verbosity
writefiles = opts.writefiles
date_dirs = opts.date_dirs

#logging.basicConfig(filename=writefiles, level=logging.INFO)

if writefiles:
    if not opts.outdir:
        print "writefiles option (-w)  also requires outputdir option (-D)."
        parseopts.print_help()
        sys.exit(2) 
    outdir = opts.outdir
    if not os.path.isdir(outdir):
        print '%s does not exist or is not a directory' % outdir
        sys.exit(2)
else:
    outdir = ""
    
reftime = datetime.datetime.utcnow()
reftime = reftime.replace(second=0, microsecond=0,
                        tzinfo=pytz.timezone('UTC'))

if writefiles and outdir and date_dirs:
    date = reftime.strftime('%Y%m%d')
    hour = reftime.strftime('%H')
    if not os.path.exists(os.path.join(outdir, date)):
        os.mkdir(os.path.join(outdir, date))
    if not os.path.exists(os.path.join(outdir, date, hour)):
        os.mkdir(os.path.join(outdir, date, hour))
    outdir = os.path.join(outdir, date, hour)

#
# Create the decoder/encoder objects
decoder = usMD.Decoder()
#encoder = MXE.XMLEncoder(wwCodesFile='/home/ldm/util/metars/data/ww.xml',metarStationInfoFile='/home/ldm/util/metars/data/metarStationInfo.txt')
encoder = MXE.XMLEncoder(wwCodesFile='/home/ldm/util/metars/data/ww.xml',metarStationInfoFile='/home/idp/compare/NOAA/metars/data/metarStationInfo.txt')
#
if len(args) == 0:
    fh = sys.stdin
else:
    fh = open(args[0],'r')
filestr = fh.read()
fh.close()

bulletins = bulletin.findall(filestr)
if len(bulletins) == 0:
    bulletins = [filestr]
for text in bulletins:
  
    if verbosity >= 1:
        print text.replace( '\r', '')\
            .replace( '', '')\
            .replace( '', '')
            
    m = wmo_hdr.match(text)
    if m:
        text = text.replace(m.group(0),'',1)

    m = metar_type.match(text)
    if m is None:
        if 'NIL=' in text:
            continue
        sys.stderr.write("ERROR: Could not find 'METAR' or 'SPECI' identifier.\n")
        continue
    text = text.replace(m.group(0),'',1)
    d = m.groupdict()
    metartype = d['type']

    metars = re.split('=\s*', text )
    for i in range(0,len(metars)):
        stext = metars[i].strip()
        stext = stext.replace( '.', '' )\
            .replace( '','')\
            .replace( ' \r\n ', ' ' )\
            .replace( '\r\n ', ' ' )\
            .replace( ' \r\n', ' ' )\
            .replace( '\r\n', ' ' )\
            .replace( '\r', ' ' )\
            .replace( '\n', ' ' )\
            .replace( '     ', ' ' )\
            .replace( '    ', ' ' )\
            .replace( '   ', ' ' )\
            .replace( '  ', ' ' )
        if re.sub(r'[\s]+', '', stext) == '':
            continue
        if stext[0:5] == metartype:
            station = stext[6:10]
        else:
            station = stext[0:4]
            stext = "%s\n%s=" % (metartype, stext)
            
        if verbosity >= 2:
            print "Starting to parse:'%s'" % stext
                        
        if nill.match(stext):
            print "INFO:Nil found: %s"%stext
            continue
        
       # if not us_metars.match(station):
       #     print "INFO:Non US Metar encountered: %s"%station
       #     continue

        #Compare this station against the us_stations.txt to determine if this is a US station
        if station_util.is_US_station(station):
            print "INFO:US Metar encountered: %s"%station
        else:
            print "INFO:Non-US Metar or unrecognized station encountered: %s"%station
            continue
        
        try:
            # The text *must* begin with METAR or SPECI
            # keyword and end with a '=' indicating EOT. 
            d = decoder(stext)
            #logging.info("DECODING %s"%stext)
            print("DECODING %s")%(stext)
            if d:
                encoder(d,report=stext,allowUSExtensions=True,nameSpaceDeclarations=True,debugComment=False)
                #
                # The second argument is whether to provide output suitable
                # for viewing.
                if writefiles:
                    #Add seconds to hopefully provide more uniqueness to the file name,
                    #this only works if there is a measurable difference in time between
                    #duplicate station reports with resolution of seconds.
                    xmlfile = os.path.join(outdir, "%s_%s_%s.xml" %(reftime.strftime('%Y%m%d_%H%M%S'), station, metartype.lower()))
                else:
                    xmlfile = sys.stdout
                encoder.printXML(xmlfile,True)
                
                if writefiles and verbosity >= 1:
                    print 'Wrote XML file', xmlfile
            
            
        # A KeyError is usually 'station not found'
        except KeyError:
        #    pass
            sys.stderr.write("WARNING: Unknown station '%s'.\n" % station)
        #
        # Something different, probably should halt . . .
        except Exception:
            #pass
            traceback.print_exc()

