#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Copyright (c) 2016, University Corporation for Atmospheric Research (UCAR)

'''
Gathers metrics from the log file
'''

import re
import os
import sys

def main():
    usage = ("Usage: %s logfile  \n"%os.path.basename(__file__) )

    if len(sys.argv) != 2:
        print usage
        sys.exit( 1 )

    logfilename=sys.argv[1]
    if not os.path.exists(logfilename):
        print "Log file %s does not exist"
        sys.exit( 2 )

    logfile = open(logfilename,'r')
    gather_metrics( logfile )
    logfile.close()
  

def gather_metrics(file):
    wroteFileMarker = '.xml'
    USIcao = re.compile(r'.*(?P<icao>(K[0-9A-Z]{3}|P[AH][0-9A-Z]{2}))_(metar|speci).xml', re.DOTALL)
    unknownStation = 'Unknown station'
    syntacticError = 'SyntacticError'
    
    print( "Starting to parse "+file.name+" for metrics")

    nFilesWritten=0
    nFilesIntl=0
    nFilesUS=0
    nUnknStn=0
    nSynError = 0
    metrics = {}
    
    line = file.readline()

    while line:
        line = line.strip()
        if wroteFileMarker in line:
            nFilesWritten+=1
            m = USIcao.match( line )
            if m:
                nFilesUS+=1
            else:
                print line
                nFilesIntl+=1
        elif unknownStation in line:
            nUnknStn+=1
        elif syntacticError in line:
            nSynError+=1 
            
        line = file.readline()

    nTotal = nFilesWritten+nUnknStn
    print( 'Wrote %d XML files' % (nFilesWritten) )
    print( '    %d Intl  %d US' % (nFilesIntl, nFilesUS))
    print( '     %d Unknown Station' % nUnknStn)
    print( ' %d total  (wrote + unknown)' % nTotal)
    print( ' %d total sytactic errors' % nSynError)
   
    metrics= {'totalFilesWritten':nTotal,'numWritten':nFilesWritten,'numIntl':nFilesIntl,'numUS':nFilesUS,'numUnknown':nUnknStn, 'numSynErr':nSynError}
    return metrics
    file.close()


def strip_non_alpha(str):
    return ' '.join( re.sub(r'[^A-Z0-9\s\/]+', '', str).split() )


if __name__ == '__main__':
    main()
