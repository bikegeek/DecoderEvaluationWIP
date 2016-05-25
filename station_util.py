import sys
import os
import re

'''Utilities for extracting information from the us_stations.txt, which
   contains the US stations' icao_code, lat, lon, elevation, site_name, and country.
   Derived from mySQL query on 'aileron':
   select icao_code, lat, lon, elevation, site_name, country from aero_stations where country='US'
   into OUTFILE '/tmp/us_stations.txt'
   FIELDS TERMINATED BY ','
   LINES TERMINATED BY '\n'; 
'''
def get_US_icaos():
    """
        Args: None
        Returns: List of US station icao identifiers.
    """
    us_list = [] 
    with open('./us_stations.txt', 'r') as f:
        for line in f:
            icao_match = re.search(r'(^[A-Z][A-Z0-9]{3})',line)
            if icao_match:
                #only add if not already in the list
                #print ('match: %s')%(icao_match.group(0))
                if icao_match.group(0) in us_list:
                    continue
                else:
                    us_list.append(icao_match.group(0))
    return us_list
         
def is_US_station(station):
    """
       Determines whether a station is a US station
       
    """
    us_stations = get_US_icaos()
    if station in us_stations:
        return True
    else:
        return False  



if __name__ == "__main__":

    #For testing

    #Test get_US_icaos()
    us_only = get_US_icaos()
    test_stations = ['KDEN', 'KQES', 'KQEY', 'KQER', 'KQFV','KHME']
    for station in test_stations:
        if station in us_only:
            print ('Station %s is a recognized US station')%(station)  
        else:
            print ('Station %s is NOT a US station (or unknown)')%(station)


    #Test is_US_station()
    for station in test_stations:
        result = is_US_station(station)
        if station == 'KDEN' and result:
            print ('Test PASSES for KDEN')
                    
        if station != 'KDEN' and not result:
            print ('Test PASSES for unknown or non-US station: %s') %(station)
    
 

