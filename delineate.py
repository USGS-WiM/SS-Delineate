# -----------------------------------------------------
# Martyn Smith USGS
# 09/24/2019
# StreamStats Delineation script
# -----------------------------------------------------

# list of required python packages:
# gdal, pysheds


###### CONDA CREATE ENVIRONMENT COMMAND
#conda create -n delineate python=3.7 gdal pysheds folium jupyter pywin32
###### CONDA CREATE ENVIRONMENT COMMAND

#%%
import argparse
import sys
from osgeo import ogr, osr, gdal
from pysheds.grid import Grid
import folium
import time
import json

#arguments
GLOBAL_GDB = 'global.GDB'
HUCPOLY_LAYER = 'hucpoly'
HUCPOLY_LAYER_ID = 'NAME'
HUCPOLY_LAYER_JUNCTION_ID = 'JunctionID'
GLOBAL_STREAM_LAYER_LIST = ['streams', 'streams3d']
GLOBAL_STREAM_LAYER_ID = 'HydroID'
HUC_NET_JUNCTIONS_LAYER_LIST = ['Huc_net_Junctions3D','Huc_net_Junctions']
HUC_NET_JUNCTIONS_LAYER_ID_LIST = ['Point2DID', 'HydroID']
CATCHMENT_LAYER = 'Catchment'
CATCHMENT_LAYER_ID = 'HydroID'
ADJOINT_CATCHMENT_LAYER = 'AdjointCatchment'
ADJOINT_CATCHMENT_LAYER_ID = 'DrainID'
DRAINAGE_LINE_LAYER = 'DrainageLine'
DRAINAGE_LINE_LAYER_ID = 'DrainID'
POINT_BUFFER_DISTANCE = 50 #in local projection units
OUTPUT_GEOJSON = False

#local
# x = -73.74586
# y = 44.00683

#localGlobal
# x = -73.71348
# y = 44.00431

#global non-nested upstream
# x = -73.82705
# y = 43.29139

#global nested upstream
# x = -73.87555
# y = 42.17209

#hudson river huge
x = -73.89282
y = 41.00155

region = 'ny'
globalDataPath = 'c:/temp/' + region + '/'
globalGDB = globalDataPath + GLOBAL_GDB
huc_net_junction_list = []
upstream_huc_list = []
timeBefore = time.perf_counter()  

print('Script Initialized')

def geomToGeoJSON(in_geom, name, region_ref, webmerc_ref):
    transform = osr.CoordinateTransformation(region_ref, webmerc_ref)
    
    #don't want to affect original geometry
    transform_geom = in_geom.Clone()
    
    #trasnsform geometry from whatever the local projection is to wgs84
    transform_geom.Transform(transform)
    geojson = transform_geom.ExportToJson()

    if OUTPUT_GEOJSON:
        f = open('./' + name + '.geojson','w')
        f.write(geojson)
        f.close()
        print('Exported geojson:', name)
    
    return geojson

def searchUpstreamGeometry(geom, name):

    print('Search upstream geometry:', name)

    #get list of huc_net_junctions using merged catchment geometry
    hucNetJunctionsLayer.SetSpatialFilter(None)
    hucNetJunctionsLayer.SetSpatialFilter(geom)

    #loop over each junction
    for hucNetJunctions_feat in hucNetJunctionsLayer:
        hucNetJunctionsID = hucNetJunctions_feat.GetFieldAsString(hucNetJunctionsIdIndex)
        s = (HUCPOLY_LAYER_JUNCTION_ID + " = " + hucNetJunctionsID + "")
        if s not in huc_net_junction_list:
            huc_net_junction_list.append(s)
            
    #search for upstream connected HUC using huc_net_junctions
    operator = " OR "
    huc_net_junction_string = operator.join(huc_net_junction_list) 
    hucLayer.SetAttributeFilter(None)
    hucLayer.SetAttributeFilter(huc_net_junction_string)

     #loop over upstream HUCs
    for huc_select_feat in hucLayer:
        huc_name = huc_select_feat.GetFieldAsString(hucNameFieldIndex)
        #print('found huc:',huc_name)
        
        if huc_name not in upstream_huc_list:
            upstreamHUC = huc_select_feat.GetGeometryRef()
            upstream_huc_list.append(huc_name)

            #recursive call to search next HUC
            searchUpstreamGeometry(upstreamHUC, huc_name)
            
    return        

print('y,x:',y,',',x,'\nRegion:',region,'\nGlobalDataPath:',globalDataPath,'\nGlobalGDB:',globalGDB)

## ---------------------------------------------------------
## START GLOBAL GDB PROCESS
## ---------------------------------------------------------
# use OGR specific exceptions
ogr.UseExceptions()
gdal.UseExceptions()

# get the driver
driver = ogr.GetDriverByName("OpenFileGDB")

# opening the FileGDB
global_gdb = driver.Open(globalGDB, 0)
if global_gdb is None:
    print('ERROR: Missing global gdb for:', region)
    sys.exit()

#get polygon layer to query
hucLayer = global_gdb.GetLayer(HUCPOLY_LAYER)
if hucLayer is None:
    print('ERROR: Missing the hucpoly layer for:', region)
    sys.exit()

#there are at least two possible global stream layer names


# globalStreamsLayer = None
# while globalStreamsLayer is None:
#     try:
#         globalStreamsLayer = global_gdb.GetLayer(globalStreamsLayerName)
#         if globalStreamsLayer is None:
#             raise Error('Missing global streams layer for:', region)
#         print('Global Stream Layer:',globalStreamsLayerName)
#     except:
        
#         print('Missing global streams layer for:', region)
#         sys.exit()
        
for globalStreamsLayerName in GLOBAL_STREAM_LAYER_LIST:
    globalStreamsLayer = global_gdb.GetLayer(globalStreamsLayerName)
    print('checking:',globalStreamsLayerName)
    
    if globalStreamsLayer is None:
        print('checking next global stream layer name')
        continue
        
    #otherwise we have a good layer so bail
    else:
        print('Global Stream Layer:',globalStreamsLayerName)
        break
    
#if its still none, exit the program
if globalStreamsLayer is None:
    print('ERROR: Missing global streams layer for:', region)
    sys.exit()

#looks like there are also multiple possibilities for the huc_net_junctions layerID field
for hucNetJunctionsLayerName in HUC_NET_JUNCTIONS_LAYER_LIST:
    hucNetJunctionsLayer = global_gdb.GetLayer(hucNetJunctionsLayerName)
    
    if hucNetJunctionsLayer is None:
        print('checking next huc_net_junctions layer name')
        continue
        
    #otherwise we have a good layer so bail
    else:
        print('huc_net_junctions layer:',hucNetJunctionsLayerName)
        break
        
if hucNetJunctionsLayer is None:
    print('ERROR: Missing huc_net_junctions layer for:', region)
    sys.exit()

#Put the title of the field you are interested in here
hucNameFieldIndex = hucLayer.GetLayerDefn().GetFieldIndex(HUCPOLY_LAYER_ID)
globalStreamsHydroIdIndex = globalStreamsLayer.GetLayerDefn().GetFieldIndex(GLOBAL_STREAM_LAYER_ID)


#looks like there are also multiple possibilities for the huc_net_junctions layerID field
for hucNetJunctionsLayerID in HUC_NET_JUNCTIONS_LAYER_ID_LIST:
    hucNetJunctionsIdIndex = hucNetJunctionsLayer.GetLayerDefn().GetFieldIndex(hucNetJunctionsLayerID)
    
    if hucNetJunctionsIdIndex is None:
        print('checking next huc_net_junctions layer ID name')
        continue
        
    #otherwise we have a good layer so bail
    else:
        print('huc_net_junctions layer ID:',hucNetJunctionsLayerID )
        break
        
if hucNetJunctionsIdIndex is None:
    print('ERROR: huc_net_junctions ID not found for:', region)
    sys.exit()

#Create a transformation between this and the hucpoly projection
region_ref = hucLayer.GetSpatialRef()
webmerc_ref = osr.SpatialReference()
webmerc_ref.ImportFromEPSG(4326)
ctran = osr.CoordinateTransformation(webmerc_ref,region_ref)

#Transform incoming longitude/latitude to the hucpoly projection
[projectedLng,projectedLat,z] = ctran.TransformPoint(x,y)

#Create a point
inputPointProjected = ogr.Geometry(ogr.wkbPoint)
inputPointProjected.SetPoint_2D(0, projectedLng, projectedLat)

#find the HUC the point is in
hucLayer.SetSpatialFilter(inputPointProjected)

#Loop through the overlapped features and display the field of interest
for hucpoly_feat in hucLayer:
    hucName = hucpoly_feat.GetFieldAsString(hucNameFieldIndex)
    print('found your hucpoly: ',hucName)

    #store local path info now that we know it
    localDataPath = globalDataPath + hucName + '/'
    localGDB = localDataPath + hucName + '.gdb'

#clear hucLayer spatial filter
hucLayer.SetSpatialFilter(None)

####  NEED TO BUFFER INPUT POINTS FOR QUERYING LINES ######
bufferPoint = inputPointProjected.Buffer(POINT_BUFFER_DISTANCE)
globalStreamsLayer.SetSpatialFilter(bufferPoint)

#Loop through the overlapped features and display the field of interest
isGlobal = False
for stream_feat in globalStreamsLayer:
    globalStreamID = stream_feat.GetFieldAsString(globalStreamsHydroIdIndex)
    print('input point is type "global" with ID:', globalStreamID)
    isGlobal = True

## ---------------------------------------------------------
## END GLOBAL GDB PROCESS
## ---------------------------------------------------------

## ---------------------------------------------------------
## START LOCAL GDB PROCESS
## ---------------------------------------------------------
# use OGR specific exceptions
ogr.UseExceptions()

# get the driver
driver = ogr.GetDriverByName("OpenFileGDB")

# opening the FileGDB
try:
    local_gdb = driver.Open(localGDB, 0)
except e:
    print('ERROR: Check to make sure you have a local gdb for:', region)
    sys.exit()

#define local data layers
try:
    catchmentLayer = local_gdb.GetLayer(CATCHMENT_LAYER)
    adjointCatchmentLayer = local_gdb.GetLayer(ADJOINT_CATCHMENT_LAYER)
    drainageLineLayer = local_gdb.GetLayer(DRAINAGE_LINE_LAYER)
except:
    print('ERROR: make sure you have data for the local HUC:', hucName)
    sys.exit()

#Put the title of the field you are interested in here
catchmentLayerNameFieldIndex = catchmentLayer.GetLayerDefn().GetFieldIndex(CATCHMENT_LAYER_ID)
adjointCatchmentLayerNameFieldIndex = adjointCatchmentLayer.GetLayerDefn().GetFieldIndex(ADJOINT_CATCHMENT_LAYER_ID)
DrainageLineLayerNameFieldIndex = drainageLineLayer.GetLayerDefn().GetFieldIndex(DRAINAGE_LINE_LAYER_ID)

#Get local catchment
catchmentLayer.SetSpatialFilter(inputPointProjected)
for catchment_feat in catchmentLayer:
    catchmentID = catchment_feat.GetFieldAsString(catchmentLayerNameFieldIndex)
    print('found your catchment. HydroID is: ',catchmentID)

#Check if we have a 'localGlobal'
isLocalGlobal = False
drainageLineLayer.SetSpatialFilter(bufferPoint)

for drainage_feat in drainageLineLayer:
    isLocalGlobal = True
    select_string = (ADJOINT_CATCHMENT_LAYER_ID + " = '" + catchmentID + "'")
    adjointCatchmentLayer.SetAttributeFilter(select_string)

    for adjointCatchment_feat in adjointCatchmentLayer:
        print('found upstream adjointCatchment')
        adjointCatchmentGeom = adjointCatchment_feat.GetGeometryRef()   

        #for some reason this is coming out as multipolygon
        if adjointCatchmentGeom.GetGeometryName() == 'MULTIPOLYGON':
            for geom_part in adjointCatchmentGeom:
                #print('in multipolygon process', geom_part)
                adjointCatchmentGeom = geom_part


if not isLocalGlobal:
    print('input point is type "local"')

# clean close
del local_gdb

## ---------------------------------------------------------
## START LOCAL GDB PROCESS
## ---------------------------------------------------------

## ---------------------------------------------------------
## START SPLIT CATCHMENT PROCESS
## ---------------------------------------------------------

fdr = localDataPath + 'fdr' 

#writes an output tif clipped to a catchment shapefile in virtual memory
ds = gdal.Warp('/vsimem/fdr.tif', fdr, cutlineDSName = localGDB, cutlineSQL = 'SELECT * FROM Catchment', cutlineWhere = 'HydroID = ' + catchmentID, cropToCutline = True)

#start pysheds catchment delienation
grid = Grid.from_raster('/vsimem/fdr.tif', data_name='dir')
grid.catchment(data='dir', x=projectedLng, y=projectedLat, out_name='catch', recursionlimit=15000, xytype='label')

# Clip the bounding box to the catchment
grid.clip_to('catch')

#temp write out catchment raster
grid.to_raster(data_name='catch',file_name='c:/temp/catchment.tif')

#some sort of strange raster to polygon conversion using rasterio method
shapes = grid.polygonize()

#get split Catchment geometry
print('Split catchment complete')
splitCatchmentGeom = ogr.Geometry(ogr.wkbPolygon)
for shape in shapes:
    splitCatchmentGeom = splitCatchmentGeom.Union(ogr.CreateGeometryFromJson(json.dumps(shape[0])))
    
## ---------------------------------------------------------
## END SPLIT CATCHMENT PROCESS
## ---------------------------------------------------------


## ---------------------------------------------------------
## START AGGREGATE GEOMETRIES
## ---------------------------------------------------------
    
#get adjoint catchment geometry
if isLocalGlobal:
   
    #apply a small buffer to adjoint catchment to remove sliver
    ## PROBABLY A BETTER WAY TO DO THIS
    adjointCatchmentGeom = adjointCatchmentGeom.Buffer(1)
    
    #need to merge splitCatchment and adjointCatchment
    mergedCatchmentGeom = adjointCatchmentGeom .Union(splitCatchmentGeom)
    
if isGlobal:
   
    searchUpstreamGeometry(mergedCatchmentGeom, 'adjointCatchment')
    
    if len(upstream_huc_list) > 0:
        print('UPSTREAM HUC LIST:', upstream_huc_list)
        
        #make sure filter is clear
        hucLayer.SetAttributeFilter(None)

        #set attribute filter 
        hucLayer.SetAttributeFilter('NAME IN {}'.format(tuple(upstream_huc_list)))
        
        #create multipolygon container for all watershed parks
        mergedWatershed = ogr.Geometry(ogr.wkbMultiPolygon)
        
        #loop and merge upstream global HUCs
        for huc_select_feat in hucLayer:
            upstreamHUCgeom = huc_select_feat.GetGeometryRef()
            
            #add polygon parts to container
            if upstreamHUCgeom.GetGeometryName() == 'MULTIPOLYGON':
                for geom_part in upstreamHUCgeom:
                    mergedWatershed.AddGeometry(geom_part)
            else:
                mergedWatershed.AddGeometry(upstreamHUCgeom)
                
        mergedWatershed = mergedWatershed.UnionCascaded()
        mergedCatchmentGeom = mergedCatchmentGeom.Union(mergedWatershed)
        
#         #loop and merge upstream global HUCs
#         for huc_select_feat in hucLayer:
#             print('Merging a HUC now...')
#             upstreamHUCgeom = huc_select_feat.GetGeometryRef()
#             #upstreamHUCgeom = upstreamHUCgeom.Buffer(1)
#             mergedCatchmentGeom = mergedCatchmentGeom.Union(upstreamHUCgeom)
        
    else:
        print('Something went wrong with global HUC aggregation')
        
# clean close
del global_gdb

timeAfter = time.perf_counter() 
totalTime = timeAfter - timeBefore
print("Elapsed Time:",totalTime)

## ---------------------------------------------------------
## END AGGREGATE GEOMETRIES
## ---------------------------------------------------------


## ---------------------------------------------------------
## START DISPLAY
## ---------------------------------------------------------

#initialize map
m = folium.Map(location=[y, x],zoom_start=8, tiles='Stamen Terrain')

folium.Marker([y, x], popup='<i>delienation point</i>').add_to(m)

geojson = geomToGeoJSON(mergedCatchmentGeom.Simplify(10), 'mergedCatchment', region_ref, webmerc_ref)
folium.GeoJson(geojson, name='mergedCatchment').add_to(m)

geojson = geomToGeoJSON(adjointCatchmentGeom.Simplify(10), 'adjointCatchment', region_ref, webmerc_ref)
folium.GeoJson(geojson, name='adjointCatchment').add_to(m)

geojson = geomToGeoJSON(splitCatchmentGeom.Simplify(10), 'splitCatchment', region_ref, webmerc_ref)
folium.GeoJson(geojson, name='splitCatchment').add_to(m)

#add layer control
folium.LayerControl().add_to(m)

#display folium map
m

## ---------------------------------------------------------
## END DISPLAY
## ---------------------------------------------------------