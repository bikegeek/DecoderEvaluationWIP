import sys
import re
from subprocess import Popen, PIPE

if __name__ == "__main__":
    grep_cmd = []
    if len(sys.argv) < 2:
        #No logfile was indicated, use the default for now.
        logfile = '/home/idp/compare/NOAA/metars/WorkInProgress/20160512/10/parseMetar.log'
    else:
        logfile = sys.argv[1]

    grep_cmd.extend(['/bin/grep','SyntacticError',logfile])
    
    s = Popen(grep_cmd, stdout=PIPE, stderr=PIPE)
    stdoutdata = s.communicate()[0]
    print stdoutdata
