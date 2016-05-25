import sys
import os
import re
import station_util
import linecache

"""Reads all METAR txt files (raw data) and keeps count of only the
  report (no header, no prefix (METAR|SPECI).  This is used to 
  determine the number of total reports.
"""

def gather_metrics(file):
    wroteFileMarker = '.xml'
    #USIcao = re.compile(r'.*(?P<icao>(K[0-9A-Z]{3}|P[AH][0-9A-Z]{2}))_(metar|speci).xml', re.DOTALL)
    USIcao = 'INFO:US Metar'
    intl = 'INFO:Non-US Metar'
    unknownStation = 'Unknown station'
    syntacticError = 'SyntacticError'
    startParse = 'Starting to parse'
    metarOrSpeci = 'DECODING'
    nilOb = 'Nil found'

    #print( "Starting to parse "+file.name+" for metrics")
    

    nFilesWritten=0
    nFilesIntl=0
    nFilesUS=0
    nUnknStn=0
    nSynError = 0
    nParse = 0
    metrics = {}
    unk_stations = []
    nMetarSpeci = 0
    nNilFound = 0

    line = file.readline()

    while line:
        line = line.strip()
        if wroteFileMarker in line:
            nFilesWritten+=1
        elif unknownStation in line:
            nUnknStn+=1
            unk_stations.append(line)
        elif syntacticError in line:
            nSynError+=1
        elif startParse in line:
            nParse+=1
        elif metarOrSpeci in line: 
            nMetarSpeci+=1
        elif nilOb in line:
            nNilFound+=1
        elif USIcao in line:
            nFilesUS+=1
        elif intl in line:
            nFilesIntl+=1

        line = file.readline()
    #Get unique unknown stations
    num_unique_unk_stations = get_unique_unknown_stns(unk_stations)

    #Total possible= #XML files created + # unknown stations in log file 
    #which correspond to a file that doesn't get created.
    nPossible = nFilesWritten+nUnknStn
    #Originally output 
    #print( '%d XML files written ' % (nFilesWritten) )
    #print( '    %d Intl  %d US' % (nFilesIntl, nFilesUS))
    #print( '     %d Unknown Station' % nUnknStn)
    #print( ' %d total possible reports (wrote + unknown)' % nPossible)
    #All entries that are due to SyntacticErrors (*Note: a SyntacticError and
    #Unknown station can occur simultaneously.  Thus far, all Unknown station occurrences
    #are accompanied by a SyntacticError).  
    #print( ' %d total sytactic errors' % nSynError)
    

    metrics= {'possibleNumFiles':nPossible,'numFilesWritten':nFilesWritten,'numIntl':nFilesIntl,'numUS':nFilesUS,'numUnknown':nUnknStn, 'numSynErr':nSynError, 'numUniqueUnkStns':num_unique_unk_stations, 'numParsed':nParse, 'numMetarSpeci':nMetarSpeci, 'numNil':nNilFound}
    return metrics
    file.close()
    

def get_report_counts(datafile_dir, logfilename, outputfile_dir):
    
    #
    #Metrics from the logfile generated by parse_metar_us.py
    #
    with open(logfilename, 'r') as lf:
        metrics = {}
        metrics = gather_metrics(lf)
        #Metrics obtained from parseMetar.log file 
        numFilesWritten = metrics['numFilesWritten']
        numMetarOrSpeciObs = metrics['numMetarSpeci']
        numIntl = metrics['numIntl']
        numUS = metrics['numUS']
        numUnk = metrics['numUnknown']
        numSynErr = metrics['numSynErr']
        numUniqueUnkStns = metrics['numUniqueUnkStns']
        numNil = metrics['numNil']
    #
    #Obtain metrics from the raw data files
    #
    (num_obs, num_rmks_raw) = get_rawdata_metrics(datafile_dir)

    #
    #Obtain metrics from/about the output data 
    #
    actual_numfiles_written = get_actual_xml_files(outputfile_dir)

    #Calculate useful percentages
    #Metrics obtained from raw data and output files 
    percent_decoded = (numFilesWritten*1./num_obs)* 100. 
    percent_raw_rmk = num_rmks_raw*1./num_obs * 100.

   
    # 
    #Metrics calculated from the XML output files.
    #
    #Calculate and report the percent of decoded reports with unparsed sections
    percent_synerr = (numSynErr*1./numFilesWritten)*100
    (count_orig,count_unparsed)=get_unparsed_counts(outputfile_dir)
    percent_with_unparsed = (count_unparsed * 1./numFilesWritten)*100.
     
    #RMK in partially decoded reports
    num_rmk_in_xml = get_rmk_from_xml(outputfile_dir)

    #Unaccounted XML output
    diff_xml = numFilesWritten - actual_numfiles_written 

    #Percent unparsed
    unparsed_reports = get_percent_unparsed(outputfile_dir)
    
    #Create a list of just the percentages, which will then
    #be passed into calc_statistics to get some meaningful values
    unparsed_percentages = []
    for key,val in unparsed_reports.items(): 
        unparsed_percentages.append(val)
    (avg,median) = calc_statistics(unparsed_percentages)    
   
    #Print out the report
    print ('\n\n**************************************************************************')
    print ('Metrics for data at %s and \noutput %s')%(datafile_dir, outputfile_dir)
    print ('******************************************************************************\n')
    print ("{:5d} Requests to write XML files (made by parse_metar_us.py) ".format(numFilesWritten))
    print ("{:5d} XML files that were actually written".format(actual_numfiles_written))
    print ("{:5d} Missing XML output files (overwriting due to duplicate stations?) ".format(diff_xml)) 
    print ("{:5d} Expected observations in raw data ".format(num_obs)) 
    print ("{:5d} METAR or SPECI reports/obs encountered during decoding".format(numMetarOrSpeciObs))
    print ("{:5d} NIL reports encountered in parse_metar_us.py".format(numNil))
    print ("{:5d} Intl observations (or no matching icao identifier found) ".format(numIntl))
    print ("{:5d} US observations".format(numUS)) 
    print ("{:5d} 'Unknown station' error raised by usMetarDecoder.py".format(numUnk))
    print ("{:5d} Unique unknown stations".format(numUniqueUnkStns))
    print ("{:5d} 'SyntacticError' error raised by usMetarDecoder.py".format(numSynErr))
    print ('       !!!CAUTION!!!: SyntacticError can occur in isolation or in combination with Unknown station')
    print ("{a:5d} XML files generated from {b:4d} observations (raw input) => {c:.2f}% of all observations are decoded".format(a=numFilesWritten,b=num_obs,c=percent_decoded))
    print ("{:5d} RMKs found in raw data files, {:4d} raw observations => {:.2f}% of observations contain RMK section ".format(num_rmks_raw,num_obs, percent_raw_rmk))
    print ("{a:5d} Partially decoded reports out of {b:4d} actual XML files written => {c:.2f}% of XML output are partially decoded ".format(a=count_orig, b=actual_numfiles_written, c=percent_with_unparsed))
    print ("{:5d} reports with RMK section in ORIG or UNPARSED TAC ".format(num_rmk_in_xml))

    print ("Output files containing reports that contain unparsed portions:\n:")
    for key,value in unparsed_reports.items():
        print("File: {:s}  {:.2f}% unparsed".format(key,value))

    print ('------------------------------------------------------------------------------\n')
    print("Unparsed Average:{:.2f}%  Unparsed Median:  {:.2f}%  ".format(avg,median))

def calc_statistics(list_of_data):
    sum = 0
    count = 0
    lower = 0
    upper = 0
    for data in list_of_data:
       count +=1
       sum += data 

    #Average
    avg = sum/count

    #Median
    sorted_vals = sorted(list_of_data) 
    if len(list_of_data) % 2 == 1:
        median = list_of_data[((len(list_of_data)+1)/2 ) -1] 
    else:
        lower = list_of_data[(len(list_of_data)/2)-1]
        upper = list_of_data[len(list_of_data)/2]
        median = (float(lower+upper))/2

    return (avg,median)
      
         
    

def get_rawdata_metrics(datafile_dir):
    num_obs = 0
    num_rmks_raw = 0 
    filepaths = get_filepaths(datafile_dir)
    for file in filepaths:
        with open(file, 'r') as f:
            for line in f:
                match = re.match(r'^([A-Z][A-Z0-9]{3})\s+.*',line)
                if match :
                    num_obs += 1
                    rmk_match = re.search(r'.*RMK.*',line)
                    if rmk_match:
                        num_rmks_raw += 1

    return (num_obs, num_rmks_raw)

 
def get_unique_unknown_stns(unknown_stns):
    """ Reads in a list of lines containing the Unknown station error message
        parses out the station name and saves each name in a list.  Remove any
        duplicates, write the unique unknown station names to a file "unique_unknown_stations.txt"
        and return the number of unique stations.


        Args:
            list of lines containing the station name embedded with other text 
        Returns:
            Writes a file with the unique station names
            number of unique station names
    """
    
    unknowns = []
    num_orig = len(unknown_stns)
    #print ('Number of original unknown stations: %s')%(num_orig)
    unique_unknown_stations = open('unique_unknown_stations.txt','w')
    for stn in unknown_stns:
        stn_match = re.search(r'WARN.*([A-Z][A-Z0-9]{3}).',stn)
        if stn_match:
            unknowns.append(stn_match.group(1))
        else:
            print "No station name found"

    #Now only capture the unique station names
    unique_stns = list(set(unknowns))
    for s in unique_stns:
        unique_unknown_stations.write(s+'\n')
    unique_unknown_stations.close()
    return len(unique_stns)

def get_percent_unparsed_TAC(outputfile_dir):
    """ Follows methodology used for sigmets 
        to determine how many ORIG_TAC and 
        UNPARSED_TAC chars exist, then 
        calculate the percent of unparsed 
        characters.
 
        Args:
           outputfile_dir:  File path indicating where the
                            XML output files are saved.
        Returns:
           tuple of numbers of original and unparsed chars, and the 
           percentage of unparsed chars.


    """
    
    #Get the XML files that have ORIG_TAC and UNPARSED_TAC (you will always
    #have both)
    
    #Get all files in the outputdir and open each one,
    #then search for the appropriate patterns.
    files = get_filepaths(outputfile_dir)
    for file in files:
        with open(file,'r') as f:
            for line in f:
                pass 


def get_filepaths(dir):
    """Generates the file names in a directory tree
       by walking the tree either top-down or bottom-up.
       For each directory in the tree rooted at
       the directory top (including top itself), it
       produces a 3-tuple: (dirpath, dirnames, filenames).

    Args:
        dir (string): The base directory from which we
                      begin the search for filenames.
    Returns:
        file_paths (list): A list of the full filepaths
                           of the data to be processed.


    """

    # Create an empty list which will eventually store
    # all the full filenames
    file_paths = []

    # Walk the tree
    for root, directories, files in os.walk(dir):
        for filename in files:
            # add it to the list only if it is a grib file
            match = re.match(r'.*(.txt|.xml)$',filename)
            if match:
                # Join the two strings to form the full
                # filepath.
                filepath = os.path.join(root,filename)
                file_paths.append(filepath)
            else:
                continue
    return file_paths


def grep(pattern,file):
    with open(file, 'r') as f:
        for line in f:
            match = re.search(pattern,line)
            if match: 
                return line
            else:
                return None

def get_unparsed_counts(dir):
    """
        Args:
           dir:  The output directory where XML files are saved after decoding 
                 and encoding to IWXXM is complete.
    """

    files = get_filepaths(dir)

    count_orig = 0 
    count_unparsed = 0
    for file in files:
        with open(file, 'r') as f:
            for line in f:
                match_orig = re.search(r'ORIG_TAC',line) 
                match_unparsed = re.search(r'UNPARSED_TAC',line)
                if match_orig:
                    count_orig += 1
                if match_unparsed:
                    count_unparsed +=1

    return(count_orig, count_unparsed)
 
def get_rmk_from_xml(outputfile_dir):
    """ Obtain the number of occurrences of RMK in the XML output files 
      
        Args:
            outputfile_dir (string): The name of the directory where the XML output files reside

        Returns:
            num_rmks_xml (int):  The number of occurrences of RMK in the XML output files

    """
    files = get_filepaths(outputfile_dir)
    num_rmks_xml = 0
    pattern = 'RMK'
    for file in files:
       with open(file, 'r') as f:
           for line in f:
               match = re.search(r'UNPARSED',line)
               if match:
                   match_rmk = re.search(r'RMK',line)
                   if match_rmk:
                       num_rmks_xml += 1

    return num_rmks_xml


def get_actual_xml_files(outputdata_dir):
    all_files = get_filepaths(outputdata_dir)
    return len(all_files) 



def grep_d(start_pattern,end_pattern,filepath):
    
    """Returns the full file name and the 
       corresponding line number for a match
       to the start_pattern and end_pattern as a dictionary, with
       key=full file path and value=tuple of line numbers
       where each match was found.
      
    """
    start = 0
    end = 0
    os.chdir(filepath)
    results = {}
    for root,dir,files in os.walk(filepath):
        for file in files:
            path = os.path.join(root,file)
            for num,line in enumerate(open(path)):
                #Check for start_pattern
                if start_pattern.upper() in line.upper():
                    start=num+1
                #Check for end_pattern
                elif end_pattern.upper() in line.upper():
                    end=num+1
                    results[path]=(start,end)
                
    return results

def strip_non_alpha(str,strip_whitespace=True):
    if strip_whitespace:
        return ' '.join( re.sub(r'[^A-Z0-9\/]+', '', str).split() )
    else: 
        return ' '.join( re.sub(r'[^A-Z0-9\s\/]+', '', str).split() )



def get_percent_unparsed(outputfile_dir):
    #Find the output files that contain ORIG_TAC and UNPARSED_TAC
    found_TAC = {}
    found_TAC = grep_d('<!--','-->',outputfile_dir)
    orig_unparsed_TAC = {}
    result = {}

    #Iterate over all the output files that have unparsed sections.
    for full_file,start_end in found_TAC.items():
        #The start_end values contain the lines which bracket the 
        #ORIG_TAC and UNPARSED_TAC section of the output file.
        start_line = start_end[0]
        end_line = start_end[1]        
        
         
        #Get the lines between (start_line+1) and (end_line - 1) and combine them into one line.
        #This will make it easier to differentiate between the raw and unparsed text.
        raw_unparsed = []
        for l in range(start_line+1, end_line):
            raw_unparsed.append(linecache.getline(full_file,l).replace('\n',' '))
        
        
        #Create a new dictionary that has the file as key and the raw/orig and unparsed TAC      
        orig_unparsed_TAC[full_file] = raw_unparsed

    
    #Iterate over the new dictionary of key=file, value=orig +unparsed TAC
    for key,val in orig_unparsed_TAC.items():
       clean_line = ''.join(val)

       #Get the characters that comprise the raw/original TAC and the
       #unparsed TAC (omit any whitespace).
       orig_match = re.search(r"ORIG_TAC='(.*).*UNPARSED_TAC='(.*)'",clean_line)            
       #print("original line: %s")%(clean_line)
       if orig_match:
           orig_TAC = strip_non_alpha(orig_match.group(1),strip_whitespace=True )
           unparsed_TAC = strip_non_alpha(orig_match.group(2),strip_whitespace=True )
           #print('orig_match: %s')%(orig_TAC)
           #print('unparsed_match: %s')%(unparsed_TAC)

           #Now get the number of characters comprising the original and unparsed TAC, and calculate the
           #percent of original TAC that is unparsed. 
           num_orig = len(orig_TAC)
           num_unparsed = len(unparsed_TAC)
           percent_unparsed = num_unparsed*100./num_orig
           #print ("Num orig= %s, num unparsed = %s")%(num_orig,num_unparsed)
           #print ("{:.2f}% of original TAC is unparsed".format(percent_unparsed))
           #print("+++++++++++++++++++++++++++++++++++++++++++++++\n\n\n")

       #Create a new dictionary, one that has key=file, value=percent unparsed.
       result[key] = percent_unparsed
 
    return result 
           

def main(datafile_path, logfilename,outputfile_path):
    get_report_counts(datafile_path,logfilename, outputfile_path)
    

def Usage():
    print('Usage: generate_reports.py datafile_path logfilename outputfile_path')

if __name__ == "__main__":
    if len(sys.argv) != 4:
        Usage()
        sys.exit(1)

    #location of the raw data as input to the parser
    datafile_path = sys.argv[1]

    #location and name of the logfile generated by the parser
    logfilename = sys.argv[2]

    #location of the output data
    outputfile_path = sys.argv[3]

    #Check that files and directories exist before proceeding...
    if not os.path.exists(datafile_path):
        raise IOError('Datafile path does not exist')
    if not os.path.exists(logfilename):
        raise IOError('Log file does not exist')
    if not os.path.exists(outputfile_path):
        raise IOError('Output file directory does not exist')
    
    main(datafile_path, logfilename, outputfile_path)
