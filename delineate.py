## StreamStats delineation script

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

import argparse
import sys
from osgeo import ogr, osr, gdal
from pysheds.grid import Grid
import folium
import time
import json

#arguments
GLOBAL_GDB_LIST = ['global.GDB','global.gdb']
HUCPOLY_LAYER = 'hucpoly'
HUCPOLY_LAYER_ID = 'NAME'
HUCPOLY_LAYER_JUNCTION_ID = 'JunctionID'
GLOBAL_STREAM_LAYER_LIST = ['streams', 'streams3d']
GLOBAL_STREAM_LAYER_ID = 'HydroID'
HUC_NET_JUNCTIONS_LAYER_LIST = ['Huc_net_Junctions3D','Huc_net_Junctions']
HUC_NET_JUNCTIONS_LAYER_ID_LIST = ['Point2DID', 'HydroID']
CATCHMENT_LAYER = 'Catchment'
CATCHMENT_LAYER_ID = 'GridID'
ADJOINT_CATCHMENT_LAYER = 'AdjointCatchment'
ADJOINT_CATCHMENT_LAYER_ID = 'GridID'
POINT_BUFFER_DISTANCE = 5 # used for searching line features for local and global
POLYGON_BUFFER_DISTANCE = 1 # used for eliminating slivers when merging polygon geometries
FAC_SNAP_THRESHOLD = 900 
OUTPUT_GEOJSON = True

class Results(object):
    def __init__(self, splitCatchment=None, adjointCatchment=None, mergedCatchment=None):
        self.splitCatchment = splitCatchment
        self.adjointCatchment = adjointCatchment
        self.mergedCatchment = mergedCatchment       

def delineateWatershed(y,x,region,dataPath):

    def splitCatchment(flow_dir, geom, x, y): 

        #method to use catchment bounding box instead of exact geom
        minX, maxX, minY, maxY = geom.GetEnvelope()
        gdal.Warp('/vsimem/fdr.tif', flow_dir, outputBounds=[minX, minY, maxX, maxY])

        #start pysheds catchment delineation
        grid = Grid.from_raster('/vsimem/fdr.tif', data_name='dir')

        #test process 1 --- reading and clipping existing fac grid to snap
        # gdal.Warp('/vsimem/str.tif', str_grid, outputBounds=[minX, minY, maxX, maxY])
        # grid.read_raster('/vsimem/str.tif', data_name='str')
        # in_pnt = (projectedLng,projectedLat)
        # out_pnt = grid.snap_to_mask(grid.str > 0, in_pnt, return_dist=False)

        #test process 2 --- creating new acc grid on the fly for snap
        # grid.accumulation(data='dir', out_name='fac', apply_mask=False)
        # in_pnt = (projectedLng,projectedLat)
        # out_pnt = grid.snap_to_mask(grid.fac > FAC_SNAP_THRESHOLD, in_pnt, return_dist=False)

        #test process 3 --- use the center of the pixel we grabbed in the STR check step
        ### FIGURE THIS OUT

        #test process 4 --- no snapping at all
        grid.catchment(data='dir', x=x, y=y, out_name='catch', recursionlimit=15000, xytype='label')

        # Clip the bounding box to the catchment
        grid.clip_to('catch')

        #some sort of strange raster to polygon conversion using rasterio method
        shapes = grid.polygonize()

        #get split Catchment geometry
        print('Split catchment complete')
        split_geom = ogr.Geometry(ogr.wkbPolygon)

        for shape in shapes:
            split_geom = split_geom.Union(ogr.CreateGeometryFromJson(json.dumps(shape[0])))
        
        return split_geom

    def retrieve_pixel_value(geo_coord, dataset):
        transform = dataset.GetGeoTransform()
        xOrigin = transform[0]
        yOrigin = transform[3]
        pixelWidth = transform[1]
        pixelHeight = -transform[5]

        cols = dataset.RasterXSize
        rows = dataset.RasterYSize
        band = dataset.GetRasterBand(1)
        data = band.ReadAsArray(0, 0, cols, rows)

        col = int((geo_coord[0] - xOrigin) / pixelWidth)
        row = int((yOrigin - geo_coord[1] ) / pixelHeight)

        #transform pixel back to origin coordinates to and get center
        outX = ((col * pixelWidth) + xOrigin) + pixelWidth/2
        outY = ((row * -pixelHeight) + yOrigin) - pixelHeight/2

        return(data[row][col], outX, outY)

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
        hucNetJunctionsFeat = None

        #loop over each junction
        for hucNetJunctions_feat in hucNetJunctionsLayer:
            hucNetJunctionsID = hucNetJunctions_feat.GetFieldAsString(hucNetJunctionsIdIndex)
            hucNetJunctionsFeat = hucNetJunctions_feat
            s = (HUCPOLY_LAYER_JUNCTION_ID + " = " + hucNetJunctionsID + "")
            #print('huc search string:',s)
            if s not in huc_net_junction_list:
                huc_net_junction_list.append(s)

        if not hucNetJunctionsFeat:
            print('ERROR: no huc_net_junction features found within the geom:',name)
                
        #print("HUC_net_junction list:",huc_net_junction_list)

        if len(huc_net_junction_list) == 0:
            return

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
    
    ## START 

    #set paths
    globalDataPath = dataPath + region + '/archydro/'
    global_gdb = None
    huc_net_junction_list = []
    upstream_huc_list = []
    timeBefore = time.perf_counter()  

    ## ---------------------------------------------------------
    ## START GLOBAL GDB PROCESS
    ## ---------------------------------------------------------
    # use OGR specific exceptions
    ogr.UseExceptions()
    gdal.UseExceptions()

    # get the driver
    driver = ogr.GetDriverByName("OpenFileGDB")

    # opening the FileGDB
    for GLOBAL_GDB in GLOBAL_GDB_LIST:
        globalGDB = globalDataPath + GLOBAL_GDB
        global_gdb = driver.Open(globalGDB, 0)
        if global_gdb is None:
            continue    
        break
    if global_gdb is None:
        print('ERROR: Missing global gdb for:', region)
        sys.exit()

    print('y,x:',y,',',x,'\nRegion:',region,'\nGlobalDataPath:',globalDataPath,'\nGlobalGDB:',globalGDB)

    #global HUC layer (should be only one possibility)
    hucLayer = global_gdb.GetLayer(HUCPOLY_LAYER)
    if hucLayer is None:
        print('ERROR: Missing the hucpoly layer for:', region)
        sys.exit()

    try:
        hucNameFieldIndex = hucLayer.GetLayerDefn().GetFieldIndex(HUCPOLY_LAYER_ID)
    except ValueError:
        print('ERROR: Missing hucNameFieldIndex:', HUCPOLY_LAYER_ID)

    #global streams layer (multiple possibilities)     
    for globalStreamsLayerName in GLOBAL_STREAM_LAYER_LIST:
        globalStreamsLayer = global_gdb.GetLayer(globalStreamsLayerName)
        if globalStreamsLayer is None:
            continue    
        break
    if globalStreamsLayer is None:
        print('ERROR: Missing global streams layer for:', region)
        sys.exit()

    try:
        globalStreamsHydroIdIndex = globalStreamsLayer.GetLayerDefn().GetFieldIndex(GLOBAL_STREAM_LAYER_ID)
    except ValueError:
        print('ERROR: globalStreamsHydroIdIndex:', HUCPOLY_LAYER_ID)

    #huc_net_junctions layer (multiple possibilities)
    for hucNetJunctionsLayerName in HUC_NET_JUNCTIONS_LAYER_LIST:
        hucNetJunctionsLayer = global_gdb.GetLayer(hucNetJunctionsLayerName)
        if hucNetJunctionsLayer is None:
            continue
        break
    if hucNetJunctionsLayer is None:
        print('ERROR: Missing huc_net_junctions layer for:', region)
        sys.exit()

    #looks like there are also multiple possibilities for the huc_net_junctions layerID field
    for hucNetJunctionsLayerID in HUC_NET_JUNCTIONS_LAYER_ID_LIST:
        hucNetJunctionsIdIndex = hucNetJunctionsLayer.GetLayerDefn().GetFieldIndex(hucNetJunctionsLayerID)
        if hucNetJunctionsIdIndex == -1:
            continue
        break
    if hucNetJunctionsIdIndex == -1:
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

    ## ---------------------------------------------------------
    ## END GLOBAL GDB PROCESS
    ## ---------------------------------------------------------

    ## ---------------------------------------------------------
    ## START LOCAL GDB PROCESS
    ## ---------------------------------------------------------
    fdr_grid = localDataPath + 'fdr'
    str_grid = localDataPath + 'str'

    #to start assume we have a local
    on_str_grid = False
    isLocal = True
    isLocalGlobal = False
    isGlobal = False

    #query str grid with pixel value
    str_raster = gdal.Open(str_grid)
    str_val, centerProjectedX, centerProjectedY = retrieve_pixel_value((projectedLng, projectedLat), str_raster)

    #point is on an str cell
    if str_val == 1:
        on_str_grid = True

    # get the driver
    driver = ogr.GetDriverByName("OpenFileGDB")

    # opening the FileGDB
    try:
        local_gdb = driver.Open(localGDB, 0)
    except e:
        print('ERROR: Check to make sure you have a local gdb for:', hucName)
        sys.exit()

    #define local data layers
    catchmentLayer = local_gdb.GetLayer(CATCHMENT_LAYER)
    if catchmentLayer is None:
        print('ERROR: Check to make sure you have a local catchment for:', hucName)
        sys.exit()
    adjointCatchmentLayer = local_gdb.GetLayer(ADJOINT_CATCHMENT_LAYER)
    if adjointCatchmentLayer is None:
        print('ERROR: Check to make sure you have a local adjoint catchment for:', hucName)
        sys.exit()

    #Put the title of the field you are interested in here
    catchmentLayerNameFieldIndex = catchmentLayer.GetLayerDefn().GetFieldIndex(CATCHMENT_LAYER_ID)
    adjointCatchmentLayerNameFieldIndex = adjointCatchmentLayer.GetLayerDefn().GetFieldIndex(ADJOINT_CATCHMENT_LAYER_ID)

    #Get local catchment
    catchmentLayer.SetSpatialFilter(inputPointProjected)
    catchmentFeat = None
    for catchment_feat in catchmentLayer:
        catchmentID = catchment_feat.GetFieldAsString(catchmentLayerNameFieldIndex)
        catchmentFeat = catchment_feat
        print('found your catchment. HydroID is: ',catchmentID)

    if catchmentFeat:
        catchmentGeom = catchmentFeat.GetGeometryRef()
    else:
        print('ERROR: A local catchment was not found for your input point')
        sys.exit()

    #we know we are on an str cell, so need to check for an adjointCatchment
    if on_str_grid:

        #select adjoint catchment layer using ID from current catchment
        select_string = (ADJOINT_CATCHMENT_LAYER_ID + " = '" + catchmentID + "'")
        print('select string:',select_string)
        adjointCatchmentLayer.SetAttributeFilter(select_string)

        adjointCatchmentFeat = None
        for adjointCatchment_feat in adjointCatchmentLayer:
            print('found upstream adjointCatchment')
            adjointCatchmentGeom = adjointCatchment_feat.GetGeometryRef()
            adjointCatchmentFeat = adjointCatchment_feat

            #create multipolygon container for all parts
            mergedAdjointCatchmentGeom = ogr.Geometry(ogr.wkbMultiPolygon)

            #for some reason this is coming out as multipolygon
            if adjointCatchmentGeom.GetGeometryName() == 'MULTIPOLYGON':
                for geom_part in adjointCatchmentGeom:
                    mergedAdjointCatchmentGeom.AddGeometry(geom_part)
                    
                adjointCatchmentGeom = mergedAdjointCatchmentGeom.UnionCascaded()

        #there are cases where a point has str cell, but does not have an adjointCatchment
        if adjointCatchmentFeat:
            print('point is a localGlobal')

            isLocal = False
            isLocalGlobal = True

            #buffer point
            bufferPoint = inputPointProjected.Buffer(POINT_BUFFER_DISTANCE)

            #since we know we are local global, also check if we are global
            globalStreamsLayer.SetSpatialFilter(bufferPoint)

            #Loop through the overlapped features and display the field of interest
            for stream_feat in globalStreamsLayer:
                globalStreamID = stream_feat.GetFieldAsString(globalStreamsHydroIdIndex)
                print('input point is type "global" with ID:', globalStreamID)
                isGlobal = True
        else:
            print('point is a local')

    ## ---------------------------------------------------------
    ## END LOCAL GDB PROCESS
    ## ---------------------------------------------------------

    ## ---------------------------------------------------------
    ## START SPLIT CATCHMENT PROCESS
    ## ---------------------------------------------------------

    print("Time before split catchment:",time.perf_counter() - timeBefore)

    splitCatchmentGeom = splitCatchment(fdr_grid, catchmentGeom, centerProjectedX, centerProjectedY)

    print("Time after split catchment:",time.perf_counter() - timeBefore)
    ## ---------------------------------------------------------
    ## END SPLIT CATCHMENT PROCESS
    ## ---------------------------------------------------------


    ## ---------------------------------------------------------
    ## START AGGREGATE GEOMETRIES
    ## ---------------------------------------------------------
    
    #merge adjoint Catchment geom with split catchment and were done
    if isLocalGlobal:
    
        #apply a small buffer to adjoint catchment to remove sliver
        adjointCatchmentGeom = adjointCatchmentGeom.Buffer(POLYGON_BUFFER_DISTANCE)
        
        #need to merge splitCatchment and adjointCatchment
        mergedCatchmentGeom = adjointCatchmentGeom.Union(splitCatchmentGeom)
        
    #need to merge all upstream hucs in addition to localGlobal
    if isGlobal:
    
        #kick off upstream global search recursive function starting with mergedCatchment
        searchUpstreamGeometry(mergedCatchmentGeom, 'adjointCatchment')
        
        print("Time before merge:",time.perf_counter() - timeBefore)
        print('UPSTREAM HUC LIST:', upstream_huc_list)
        
        if len(upstream_huc_list) > 0:
            
            #make sure filter is clear
            hucLayer.SetAttributeFilter(None)

            #set attribute filter 
            if len(upstream_huc_list) == 1:
                hucLayer.SetAttributeFilter(HUCPOLY_LAYER_ID + " = '" + upstream_huc_list[0] + "'")
            #'in' operator doesnt work with list len of 1
            else:
                hucLayer.SetAttributeFilter(HUCPOLY_LAYER_ID + ' IN {}'.format(tuple(upstream_huc_list)))
            
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
            
            mergedCatchmentGeom =  mergedCatchmentGeom.Buffer(POLYGON_BUFFER_DISTANCE)
            mergedCatchmentGeom = mergedCatchmentGeom.Union(mergedWatershed)
            
        else:
            print('Something went wrong with global HUC aggregation')
            
    # clean close
    del global_gdb
    del local_gdb
    del str_raster
    
    ## ---------------------------------------------------------
    ## END AGGREGATE GEOMETRIES
    ## ---------------------------------------------------------

    timeAfter = time.perf_counter() 
    totalTime = timeAfter - timeBefore
    print("Total Time:",totalTime)

    #create outputs
    results = Results()
    if isLocal:
        #if its a local this is all we want to return
        results.mergedCatchment = geomToGeoJSON(splitCatchmentGeom.Simplify(10), 'mergedCatchment', region_ref, webmerc_ref)
    else:
        results.mergedCatchment = geomToGeoJSON(mergedCatchmentGeom.Simplify(10), 'mergedCatchment', region_ref, webmerc_ref)
        results.adjointCatchment = geomToGeoJSON(adjointCatchmentGeom.Simplify(10), 'adjointCatchment', region_ref, webmerc_ref)
    results.splitCatchment = geomToGeoJSON(splitCatchmentGeom.Simplify(10), 'splitCatchment', region_ref, webmerc_ref)
    
    return results

if __name__=='__main__':

    # point = (44.00683,-73.74586) #local
    # point = (44.03115617578595 , -73.71244903077174) #on str but still "local"
    # point = (44.00431,-73.71348) #localGlobal
    #point = (43.29139,-73.82705) #global non-nested upstream
    # point = (42.17209,-73.87555) #global nested upstream
    #point = (41.00155,-73.89282) #global 8 huc nested upstream

    #point = (43.45338620107029 , -74.50329065322877) # bad catchment geometry (fixed using bounding box method for fdr clip)
    point = (41.310936704746936 , -74.51668024063112) # bad split catchment result (fixed by adding snap to FAC>50)
    #point = (43.31392194207697 , -73.8442397117614) #weird one was aggregation spatially disconnected HUCs (fixed by limited global line search buffer)
    # point = (42.82741831644657 , -73.93358945846559) #single upstream HUC aggregation issue (fixed by update attributeFilter)


    #testing in MA
    # point = (42.34008482617163, -72.72163867950441)
    # point = (42.24184837786185 , -72.62126059068201) #massachusetts global on connecticut river
 
    region = 'ny'
    dataPath = 'c:/temp/'

    #start main program
    results = delineateWatershed(point[0],point[1],region,dataPath)
    
    #initialize map
    m = folium.Map(location=[point[0], point[1]],zoom_start=8, tiles='Stamen Terrain')
    folium.Marker([point[0], point[1]], popup='<i>delienation point</i>').add_to(m)
    
    #display all available results
    for attr, value in results.__dict__.items():
        if value is not None:
            layer = folium.GeoJson(value, name=attr).add_to(m)
            bounds = layer.get_bounds()

    #add layer control
    folium.LayerControl().add_to(m)
    
    #zoom map
    m.fit_bounds(bounds)

    #display folium map
    #display(m)