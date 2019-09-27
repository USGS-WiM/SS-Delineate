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

import sys
from osgeo import ogr, osr, gdal
from pysheds.grid import Grid
import folium
import time
import json

# import argparse
# parser = argparse.ArgumentParser(description='Delineates a basin from an input lat/lon')
# parser.add_argument('region', nargs='?', type=str, help='State/Region of input delineation', default='ny')
# parser.add_argument('lat', nargs='?', type=float, help='Latitude of input point', default=44.00683)
# parser.add_argument('lng', nargs='?', type=float, help='Longitude of input point', default=-73.74586)
# parser.add_argument('dataFolder', nargs='?', type=str, help='Location of input data', default='c:/temp/')
# args = parser.parse_args()

#variables
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

# use OGR specific exceptions
ogr.UseExceptions()
gdal.UseExceptions() 

class watershedPoint(object):
    def __init__(self,decimalDegreesLat,decimalDegreesLong):
        self.latDD = decimalDegreesLat
        self.lngDD = decimalDegreesLong
        self.projectedLat = None
        self.projectedLng = None
        self.mainDataPath = None
        self.localDataPath = None
        self.globalGDB = None
        self.localGDB = None
        self.hucName = None
        self.isLocalGlobal = False
        self.isGlobal = False
        self.catchmentID = None
        self.huc_net_junction_list = []
        self.upstream_huc_list = []
        self.timeBefore = time.perf_counter() 
        self.timeAfter = None
    
    #allow for string representation
    def __str__(self):
        return str(self.__class__) + ": " + str(self.__dict__)

    def setDataPaths(self, dataPath, region):
        self.mainDataPath = dataPath + region + '/'
        self.region = region
        self.globalGDB = self.mainDataPath + GLOBAL_GDB

    def geomToGeoJSON(self, in_geom=None, name=None, in_ref=None, out_ref=None):
        transform = osr.CoordinateTransformation(in_ref, out_ref)
        
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

    def searchUpstreamGeometry(self, geom=None, name=None):

        print('Search upstream geometry:', name)

        #get list of huc_net_junctions using merged catchment geometry
        self.hucNetJunctionsLayer.SetSpatialFilter(None)
        self.hucNetJunctionsLayer.SetSpatialFilter(geom)

        #loop over each junction
        for hucNetJunctions_feat in self.hucNetJunctionsLayer:
            hucNetJunctionsID = hucNetJunctions_feat.GetFieldAsString(self.hucNetJunctionsIdIndex)
            s = (HUCPOLY_LAYER_JUNCTION_ID + " = " + hucNetJunctionsID + "")
            if s not in self.huc_net_junction_list:
                self.huc_net_junction_list.append(s)
                
        #search for upstream connected HUC using huc_net_junctions
        operator = " OR "
        huc_net_junction_string = operator.join(self.huc_net_junction_list) 
        self.hucLayer.SetAttributeFilter(None)
        self.hucLayer.SetAttributeFilter(huc_net_junction_string)

        #loop over upstream HUCs
        for huc_select_feat in self.hucLayer:
            huc_name = huc_select_feat.GetFieldAsString(hucNameFieldIndex)
            #print('found huc:',huc_name)
            
            if huc_name not in upstream_huc_list:
                upstreamHUC = huc_select_feat.GetGeometryRef()
                self.upstream_huc_list.append(huc_name)

                #recursive call to search next HUC
                self.searchUpstreamGeometry(upstreamHUC, huc_name)
                
        return        

    def getUpstreamInfo(self):

        #load fgdb driver
        driver = ogr.GetDriverByName("OpenFileGDB")

        # opening the FileGDB
        global_gdb = driver.Open(self.globalGDB, 0)
        if global_gdb is None:
            print('ERROR: Missing global gdb for:',self.region)
            sys.exit()

        #get polygon layer to query
        self.hucLayer = global_gdb.GetLayer(HUCPOLY_LAYER)
        if self.hucLayer is None:
            print('ERROR: Missing the hucpoly layer for:', self.region)
            sys.exit()

        #there are at least two possible global stream layer names     
        for globalStreamsLayerName in GLOBAL_STREAM_LAYER_LIST:
            self.globalStreamsLayer = global_gdb.GetLayer(globalStreamsLayerName)
            
            if self.globalStreamsLayer is None:
                print('checking next global stream layer name')
                continue
                
            #otherwise we have a good layer so bail
            else:
                print('Global Stream Layer:',globalStreamsLayerName)
                break
            
        #if its still none, exit the program
        if self.globalStreamsLayer is None:
            print('ERROR: Missing global streams layer for:', self.region)
            sys.exit()

        #looks like there are also multiple possibilities for the huc_net_junctions layerID field
        for hucNetJunctionsLayerName in HUC_NET_JUNCTIONS_LAYER_LIST:
            self.hucNetJunctionsLayer = global_gdb.GetLayer(hucNetJunctionsLayerName)
            
            if self.hucNetJunctionsLayer is None:
                print('checking next huc_net_junctions layer name')
                continue
                
            #otherwise we have a good layer so bail
            else:
                break
                
        if self.hucNetJunctionsLayer is None:
            print('ERROR: Missing huc_net_junctions layer for:', self.region)
            sys.exit()

        #Put the title of the field you are interested in here
        hucNameFieldIndex = self.hucLayer.GetLayerDefn().GetFieldIndex(HUCPOLY_LAYER_ID)

        globalStreamsHydroIdIndex = self.globalStreamsLayer.GetLayerDefn().GetFieldIndex(GLOBAL_STREAM_LAYER_ID)

        #looks like there are also multiple possibilities for the huc_net_junctions layerID field
        for hucNetJunctionsLayerID in HUC_NET_JUNCTIONS_LAYER_ID_LIST:
            self.hucNetJunctionsIdIndex = self.hucNetJunctionsLayer.GetLayerDefn().GetFieldIndex(hucNetJunctionsLayerID)

            if self.hucNetJunctionsIdIndex is None:
                print('checking next huc_net_junctions layer ID name')
                continue
                
            #otherwise we have a good layer so bail
            else:
                print('huc_net_junctions layer ID:',hucNetJunctionsLayerID)
                break
                
        if self.hucNetJunctionsIdIndex is None:
            print('ERROR: huc_net_junctions ID not found for:', self.region)
            sys.exit()

        #Create a transformation between this and the hucpoly projection
        self.region_ref = self.hucLayer.GetSpatialRef()
        self.webmerc_ref = osr.SpatialReference()
        self.webmerc_ref.ImportFromEPSG(4326)
        ctran = osr.CoordinateTransformation(self.webmerc_ref,self.region_ref)

        #Transform incoming longitude/latitude to the hucpoly projection
        [self.projectedLng,self.projectedLat,z] = ctran.TransformPoint(self.lngDD,self.latDD)

        #Create a point
        inputPointProjected = ogr.Geometry(ogr.wkbPoint)
        inputPointProjected.SetPoint_2D(0, self.projectedLng, self.projectedLat)

        #find the HUC the point is in
        self.hucLayer.SetSpatialFilter(None)
        self.hucLayer.SetSpatialFilter(inputPointProjected)

        #Loop through the overlapped features and display the field of interest
        for hucpoly_feat in self.hucLayer:
            self.hucName = hucpoly_feat.GetFieldAsString(hucNameFieldIndex)
            print('found your hucpoly: ',self.hucName)

        #store local path info now that we know it
        self.localDataPath = self.mainDataPath + self.hucName + '/'
        self.localGDB = self.localDataPath + self.hucName + '.gdb'

        #search global stream layer with a buffer to determine if point is on global stream
        bufferPoint = inputPointProjected.Buffer(POINT_BUFFER_DISTANCE)
        self.globalStreamsLayer.SetSpatialFilter(bufferPoint)

        #if we have any hit here we know its global
        for stream_feat in self.globalStreamsLayer: 
            self.isGlobal = True

        ## Open local GDB
        local_gdb = driver.Open(self.localGDB, 0)
        if local_gdb is None:
            print('ERROR: Check to make sure you have a local gdb for:', self.region)
            sys.exit()

        #define local data layers
        catchmentLayer = local_gdb.GetLayer(CATCHMENT_LAYER)
        catchmentLayerNameFieldIndex = catchmentLayer.GetLayerDefn().GetFieldIndex(CATCHMENT_LAYER_ID)
        if catchmentLayer is None or catchmentLayerNameFieldIndex is None:
            print('ERROR: issue with local catchment layer for:', self.hucName)
            sys.exit()
            
        adjointCatchmentLayer = local_gdb.GetLayer(ADJOINT_CATCHMENT_LAYER)
        if adjointCatchmentLayer is None:
            print('ERROR: Missing local adjointCatchment layer for:', self.region)
            sys.exit()

        drainageLineLayer = local_gdb.GetLayer(DRAINAGE_LINE_LAYER)
        if drainageLineLayer is None:
            print('ERROR: Missing local drainageLineLayer layer for:', self.region)
            sys.exit()

        #define local layer IDs
        adjointCatchmentLayerNameFieldIndex = adjointCatchmentLayer.GetLayerDefn().GetFieldIndex(ADJOINT_CATCHMENT_LAYER_ID)
        DrainageLineLayerNameFieldIndex = drainageLineLayer.GetLayerDefn().GetFieldIndex(DRAINAGE_LINE_LAYER_ID)

        #Get local catchment
        catchmentLayer.SetSpatialFilter(inputPointProjected)
        for catchment_feat in catchmentLayer:
            self.catchmentID = catchment_feat.GetFieldAsString(catchmentLayerNameFieldIndex)
            print('found your catchment. HydroID is: ',self.catchmentID)

        #Check if we have a 'localGlobal'
        drainageLineLayer.SetSpatialFilter(bufferPoint)
        for drainage_feat in drainageLineLayer:
            self.isLocalGlobal = True
            select_string = (ADJOINT_CATCHMENT_LAYER_ID + " = '" + self.catchmentID + "'")
            adjointCatchmentLayer.SetAttributeFilter(select_string)

            for adjointCatchment_feat in adjointCatchmentLayer:
                print('found upstream adjointCatchment')
                self.adjointCatchmentGeom = adjointCatchment_feat.GetGeometryRef()   

                #for some reason this is coming out as multipolygon
                if self.adjointCatchmentGeom.GetGeometryName() == 'MULTIPOLYGON':
                    for geom_part in self.adjointCatchmentGeom:
                        #print('in multipolygon process', geom_part)
                        self.adjointCatchmentGeom = geom_part

        # clean close
        del local_gdb

        ## split catchment
        fdr = self.localDataPath + 'fdr' 

        #writes an output tif clipped to a catchment shapefile in virtual memory
        ds = gdal.Warp('/vsimem/fdr.tif', fdr, cutlineDSName = self.localGDB, cutlineSQL = 'SELECT * FROM Catchment', cutlineWhere = 'HydroID = ' + self.catchmentID, cropToCutline = True)

        #start pysheds catchment delienation
        grid = Grid.from_raster('/vsimem/fdr.tif', data_name='dir')
        grid.catchment(data='dir', x=self.projectedLng, y=self.projectedLat, out_name='catch', recursionlimit=15000, xytype='label')

        # Clip the bounding box to the catchment
        grid.clip_to('catch')

        #temp write out catchment raster
        grid.to_raster(data_name='catch',file_name='c:/temp/catchment.tif')

        #some sort of strange raster to polygon conversion using rasterio method
        shapes = grid.polygonize()

        #get split Catchment geometry
        print('Split catchment complete')
        self.splitCatchmentGeom = ogr.Geometry(ogr.wkbPolygon)
        for shape in shapes:
            self.splitCatchmentGeom = self.splitCatchmentGeom.Union(ogr.CreateGeometryFromJson(json.dumps(shape[0])))
  
        #get adjoint catchment geometry
        if self.isLocalGlobal:
        
            #apply a small buffer to adjoint catchment to remove sliver
            ## PROBABLY A BETTER WAY TO DO THIS
            self.adjointCatchmentGeom = self.adjointCatchmentGeom.Buffer(1)
            
            #need to merge splitCatchment and adjointCatchment
            self.mergedCatchmentGeom = self.adjointCatchmentGeom.Union(self.splitCatchmentGeom)
            
        if self.isGlobal:
        
            self.searchUpstreamGeometry(self.mergedCatchmentGeom, 'adjointCatchment')
            
            if len(self.upstream_huc_list) > 0:
                print('UPSTREAM HUC LIST:', self.upstream_huc_list)
                
                #make sure filter is clear
                hucLayer.SetAttributeFilter(None)

                #set attribute filter 
                hucLayer.SetAttributeFilter('NAME IN {}'.format(tuple(self.upstream_huc_list)))
                
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
                self.mergedCatchmentGeom = self.mergedCatchmentGeom.Union(mergedWatershed)

            else:
                print('Something went wrong with global HUC aggregation')
                
        # clean close
        del global_gdb

        self.timeAfter = time.perf_counter() 
        totalTime = self.timeAfter - self.timeBefore
        print("Elapsed Time:",totalTime)


    def displayMap(self):
        #initialize map
        m = folium.Map(location=[y, x],zoom_start=8, tiles='Stamen Terrain')

        folium.Marker([y, x], popup='<i>delienation point</i>').add_to(m)

        geojson = self.geomToGeoJSON(self.mergedCatchmentGeom.Simplify(10), 'mergedCatchment', self.region_ref, self.webmerc_ref)
        folium.GeoJson(geojson, name='mergedCatchment').add_to(m)

        geojson = self.geomToGeoJSON(self.adjointCatchmentGeom.Simplify(10), 'adjointCatchment', self.region_ref, self.webmerc_ref)
        folium.GeoJson(geojson, name='adjointCatchment').add_to(m)

        geojson = self.geomToGeoJSON(self.splitCatchmentGeom.Simplify(10), 'splitCatchment', self.region_ref, self.webmerc_ref)
        folium.GeoJson(geojson, name='splitCatchment').add_to(m)

        #add layer control
        folium.LayerControl().add_to(m)

        #display folium map
        m

#%%

if __name__ == "__main__":

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

    args = {"lat": y, "lng": x, "dataFolder": "C:/temp/", "region": "ny" }
    
    #instantiate point object
    point = watershedPoint(args['lat'],args['lng'])

    point.setDataPaths(args['dataFolder'], args['region'])
    point.getUpstreamInfo()
    point.displayMap()

    print(point)

