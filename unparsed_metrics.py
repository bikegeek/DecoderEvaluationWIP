import os
import sys
import re
import generate_report as gr
import linecache

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
#01234567890
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

#01234567890
       #Create a new dictionary, one that has key=file, value=percent unparsed.
       result[key] = percent_unparsed
 
    return result 
           
if __name__ == "__main__":
#01234567890
    outputfile_dir= "/home/idp/compare/NOAA/metars/WorkInProgress/20160523/21/20160524/19"
    result = get_percent_unparsed(outputfile_dir)
  
    for key,val in result.items():
        print("file: {:s} {:.2f}% unparsed".format(key,val))
