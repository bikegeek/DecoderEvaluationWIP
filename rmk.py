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
          #          print ("{:s} found in {:s}, line number {:d}".format(start_pattern.upper(),path, num+1))
                    #print("Found match in: {:s}".format(path))                   
                    start=num+1
                    #Check for end_pattern
                elif end_pattern.upper() in line.upper():
          #          print ("{:s} found in {:s}, line number {:d}".format(end_pattern.upper(),path, num+1))
                    #print("Found match in: {:s}".format(path))                   
                    end=num+1
                    results[path]=(start,end)
                
    return results


if __name__ == "__main__":
    outputfile_dir= "/home/idp/compare/NOAA/metars/WorkInProgress/20160523/21/20160524/19"
    #Find the output files that contain ORIG_TAC and UNPARSED_TAC
    found_TAC = {}
    found_TAC = grep_d('<!--','-->',outputfile_dir)

    #Iterate over all the output files that have unparsed sections.
    for full_file,start_end in found_TAC.items():
        #The start_end values contain the lines which bracket the 
        #ORIG_TAC and UNPARSED_TAC section of the output file.
        #print("file: {:s} with start line at {:d} and end line at {:d}".format(key, start_end[0], start_end[1]))
        start_line = start_end[0]
        end_line = start_end[1]        
        
         
        #Get the lines between (start_line+1) and (end_line - 1) and combine them into one line.
        #This will make it easier to differentiate between the raw and unparsed text.
        for l in range(start_line+1, end_line):
            print ("file: {:s}, current line: {:s}".format(full_file,linecache.getline(full_file,l)))
             
     
