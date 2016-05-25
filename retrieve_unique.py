import re
import sys



if __name__ == "__main__":
   stn_file = sys.argv[1]
   unique_file = open("unique_stns.txt","w")
   unknowns = []
   with open( stn_file, "r") as f:
       for line in f:
           stn_match = re.search(r'WARN.*([A-Z][A-Z0-9]{3}).',line)
           if stn_match:
               #unique_file.write(stn_match.group(1)+"\n")
               print(stn_match.group(1))
               unknowns.append(stn_match.group(1))
           else:
               print "No match for %s "%line
    
   #now only report the unique stations
   unique_stns = list(set(unknowns))
   for stn in unique_stns:
       unique_file.write(stn+'\n') 
        
   unique_file.close()
