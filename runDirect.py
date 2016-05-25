#!/usr/bin/env python
import re
import os
import sys


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
            match = re.match(r'.*(.txt)$',filename)
            if match:
                # Join the two strings to form the full
                # filepath.
                filepath = os.path.join(root,filename)
                file_paths.append(filepath)
            else:
                continue
    return file_paths


                                                                                                                                                           

def mkdir_p(dir):
    """Provides mkdir -p functionality.

       Args:
          dir (string):  Full directory path to be created if it
                         doesn't exist.
       Returns:
          None:  Creates nested subdirs if they don't already
                 exist.

    """
    try:
       os.makedirs(dir)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(dir):
            pass
        else:
            raise


if __name__ == "__main__":
    #Base directory where all output and log files will reside as subdirectories
    working_dir = "/home/idp/compare/NOAA/metars/WorkInProgress/" 
    dir = sys.argv[1]
    full_dir = working_dir + dir
    try:
        os.stat(full_dir)
    except:
        mkdir_p(full_dir)

    files = get_filepaths("/home/idp/compare/data/metars/"+dir )
#    script_cmd = "./Metar2Xml_us.csh /home/idp/compare/NOAA/metars/"+dir
#    script_cmd = "./parse_metar_us.py -vv -d -D /home/idp/compare/NOAA/metars/WorkInProgress/"+dir+" -w >>/home/idp/compare/NOAA/metars/WorkInProgress/"+dir+"/parseMetar.log 2>&1 "
 

    for file in files:
        #cmd = script_cmd + "<" + file
        cmd = "./usMetarDecoder.py " + file
        os.system(cmd)
