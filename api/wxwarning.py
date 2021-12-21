# Program wxwarning
# by Todd Arbetter (todd.e.arbetter@gmail.com)
# Software Engineer, IXMap, Golden, CO

# collects latests National Weather Service Warnings, Watches, Advisories,
# and Statements, plots shapefiles on an interactive map in various colors.
# The map is able to pan and zoom, and on mouseover will give the type of
# weather statement, start, and expiry.

# created with streamlit and folium

# import some libraries
from sys import float_repr_style
import numpy as np
import pandas as pd
import geopandas as gpd
from requests.models import ChunkedEncodingError
import folium as fl
from folium.plugins import FastMarkerCluster,MarkerCluster,MiniMap
import branca.colormap as cm
import os as os
import pathlib
import re
import random
import json
import requests
import tarfile
import datetime as dt
import time as time
from time import sleep
from flask import Flask, render_template, request, redirect, url_for, send_file, make_response
from functools import wraps, update_wrapper
from datetime import datetime
from pathlib import Path

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.vars = {}

newdata = True  # set True to get new data, draw new map
lastmap = time.mktime((dt.datetime.now()).timetuple())
print ('Now:',lastmap,newdata)

def check_map():
    global newdata, lastmap

    # check to draw map
    thismap = time.mktime((dt.datetime.now()).timetuple())
    nextmap = lastmap + 300.
    if (thismap > nextmap):
        newdata = True
    else:
        newdata = False
    
    print('lastmap',lastmap)
    print('thismap',thismap)
    print('nextmap',nextmap)
    print('newdata',newdata)
        
    return

def get_confirm_token(response):
    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            return value

    return None

def save_response_content(response,destination):
    CHUNK_SIZE=32768
    i = 1
    with open(destination,"wb") as f:
        for chunk in response.iter_content(CHUNK_SIZE):
            if chunk:
#                st.write('Chunk:',i)
                f.write(chunk)
                i += 1


def get_weather_data():
    # We create a downloads directory within the streamlit static asset directory
    # and we write output files to it

    print('getting weather data')

    #get latest wx warnings from NWS
    url='https://tgftp.nws.noaa.gov/SL.us008001/DF.sha/DC.cap/DS.WWA/current_all.tar.gz'

    session = requests.Session()

    response = session.get(url,stream=True)
    token = get_confirm_token(response)

    if token:
        params = {'confirm':token}
        response = session.get(URL,params=params,stream=True)

    #have to set map path - used by template
    dest_path = os.path.join(app.root_path, 'downloads/')
    destination =  str(dest_path)+'current_all.tar.gz'

    save_response_content(response,destination)

    sleep(30)

    print('got weather data')

    return destination,dest_path

def read_weather_data(destination,dest_path):

    print('Destination=',destination)

    wxdata = tarfile.open(name=destination)

    print ('opened tarfile')

    wxdata.list(verbose=True)

    wxdata.extractall(path=str(dest_path)+'/current_all/')

    print('extracted data')

    infile = str(dest_path) + '/current_all/current_all.shp'

    #Read in weather info

    weather_df = gpd.read_file(infile)

    #weather_df = gpd.read_file('current_warnings/current_warnings.shp')

    weather_df = weather_df.drop(columns=['PHENOM','SIG','WFO','EVENT','ONSET','ENDS','CAP_ID','MSG_TYPE','VTEC'])

    print(weather_df.head(10))

    print ('read weather data')

    return weather_df


def render_map(weather_df):
    global lastmap,newdata

    print('drawing map',lastmap,newdata)
    
    # get the current time in UTC (constant reference timezone)
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec='minutes')
    print('timestamp:',timestamp)
    #st.write(timestamp[0:10], timestamp[11:16],'UTC')
    #st.write('DOWNLOADS_PATH',DOWNLOADS_PATH)

#    st.title('Current U.S. Weather Statements')

#    st.header(timestamp[0:10]+' '+timestamp[11:16]+' UTC')

    #Assign an integer value to each unique warning
    #so they will plot in different colors later

    wxwarnings = {}
    k = 0
    for w in weather_df['PROD_TYPE'].unique():
        wxwarnings[w]=k
    #    print(w,k)
        k += 10

    #st.write(wxwarnings)

    #Get min and max values of wxwarning id codes
    all_values = wxwarnings.values()

    max_wxwarnings = max(all_values)
    min_wxwarnings = min(all_values)

    #st.write('wxwarnings:',min_wxwarnings,max_wxwarnings)

    # Now create an column PROD_ID which duplicates PROD_TYPE
    weather_df["PROD_ID"]=weather_df['PROD_TYPE']

    # and fill with values from the dictionary wxwarnings
    weather_df['PROD_ID'].replace(wxwarnings,inplace=True)

    #st.write(weather_df.head())

    #verify no missing/Nan
    weather_df.isnull().sum().sum()

    #explicitly create an index column with each entry having a unique value for indexing
    weather_df['UNIQUE_ID']=weather_df.index

    #st.write(weather_df.head(10))

    # write weather_df to a geoJson file
    #weather_df.to_file("weather_df.geojson", driver='GeoJSON')
    #st.write('wrote GeoJSON file')

    # Use branca.colormap instead of choropleth


    #create a b/w map of CONUS
    mbr = fl.Map(location=[40.0,-95.0],zoom_start=4,tiles="Stamen Toner")

    colormap = cm.linear.Set1_09.scale(min_wxwarnings,max_wxwarnings).to_step(len(set(weather_df['PROD_ID'])))

#    sf.folium_static(colormap)

    #Add weather data to map with mouseover (this will take a few minutes), include tooltip

    fl.GeoJson(weather_df,
               style_function = lambda x: {"weight":0.5, 
                            'color':'red',
                            'fillColor':colormap(x['properties']['PROD_ID']), 
                            'fillOpacity':0.5
               },
           
               highlight_function = lambda x: {'fillColor': '#000000', 
                                'color':'#000000', 
                                'fillOpacity': 0.25, 
                                'weight': 0.1
               },
               
               tooltip=fl.GeoJsonTooltip(
                   fields=['PROD_TYPE','ISSUANCE','EXPIRATION'], 
                   aliases=['Hazard', 'Starts','Expires'],
                   labels=True,
                   localize=True
               ),
              ).add_to(mbr)

    # Add minimap
    MiniMap(tile_layer='stamenterrain',zoom_level_offset=-5).add_to(mbr)

    lastmap = time.mktime((dt.datetime.now()).timetuple())

    print('drew map; lastmap=',lastmap)

    return mbr


def save_map(mbr):

 #   sf.folium_static(mbr)
 #   st.header('Source: National Weather Service, USA')

    #save the map to an HTML file

    if os.path.exists('wxwarning.html'):
        os.remove('wxwarning.html')
    
    mbr.save('wxwarning.html')

    #st.write('Done')
    print('saved map')

    return 'wxwarning.html'



def nocache(view):
    @wraps(view)
    def no_cache(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers['Last-Modified'] = datetime.now()
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
        return response
        
    return update_wrapper(no_cache, view)



@app.route('/maps/map.html')
@nocache
def show_map():
    map_path = os.path('./wxwarning.html')
    print("show map")
    print(map_path)
    map_file = Path(map_path)
    if os.path.exists('wxwarning.html'):
        return send_file(map_path)
    else:
        return render_template('error.html', culprit='map file', details="the map file couldn't be loaded")

    pass

@app.route('/get_logo')
def get_logo():
  logo_path = os.path('./static/img/logo.png' )
  print("show logo")
  print(logo_path)
  logo_file = Path(logo_path)
  if logo_file.exists():
    return send_file(logo_path)
  else:
    return render_template('error.html', culprit='logo file', details="the logo file couldn't be loaded")

  pass


@app.route('/wxwarning.html', methods=['GET'])
def map_driver():
    global newdata

    if request.method == 'GET':
        newdata=True
        
    print('map_driver',newdata)

    if (newdata):

        print('starting newdata=',newdata)
        destination,dest_path = get_weather_data()

        print('Destination:',destination)
        print('Dest_path:',dest_path)
    
    #check that file exists:
 
        if os.path.exists(destination):

            weather_df = read_weather_data(destination,dest_path)

        else:

            print('Error:',destination,'not found')
            exit()

        sleep (15)

        wxmap = render_map(weather_df)

        save_map(wxmap)

        render_template('display.html')

        newdata = False
    
    else:
        
        check_map()
        print('Checked map, newdata:',newdata)
    
    return


@app.route('/')
def main():
    return redirect('/wxwarning.html')


#### main program

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000)

#else:
#    print ('Error, must use newdata=True')
#    exit()

