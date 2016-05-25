import sys
import re
import uuid


if __name__ == "__main__":
    station_entry= []
    outfile = open("./metar_stns.txt", "w")
    with open ( "stations3.txt") as infile:
        uuid = uuid.uuid1()
        for line in infile:
            #split string based on the ',' delimiter
            line_tokens = re.split(',',line) 
            icao_id = line_tokens[0]
            if icao_id == '\N':
               #Don't include station if it doesn't have an icao id
               continue

            latitude = line_tokens[1]
            if latitude == '\N':
                continue  
            else:
                lat = "{:.2f}".format(float(latitude))

            longitude = line_tokens[2]
            if longitude == '\N':
                continue
            else:
                lon = "{:.2f}".format(float(longitude))

            elevation = line_tokens[3]
            if elevation == '\N':
                continue
            else:            
                elev = "{:.2f}".format(float(elevation))

            site_name = line_tokens[4]

            country = line_tokens[5]
            country_match = re.search(r'[A-Z]{2} ',country)
            if country_match:
                pass 
            else:
                continue

            uuid = '3c918d83-618a-450b-a5f3-3f509ea64531'
            print ("%s |%s| %s| %s| %s| %s| %s")%(uuid,icao_id,lat,lon,elev,site_name,country) 
        
            station_entry = [uuid,'|', icao_id, '|', lat,'|', lon,'|', elev,'|', site_name,'|', country,'|MTR']
            # print station_entry
            station_line = ''.join(station_entry)
            outfile.write(station_line+'\n')
    outfile.close()
