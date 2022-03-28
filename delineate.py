## StreamStats delineation script

# -----------------------------------------------------
# Martyn Smith USGS
# 10/11/2019
# StreamStats Delineation script
# -----------------------------------------------------

# list of required python packages:
# gdal, pysheds

###### CONDA CREATE ENVIRONMENT COMMAND
#conda create -n delineate python=3.6.8 gdal pysheds
###### CONDA CREATE ENVIRONMENT COMMAND

from osgeo import ogr, osr, gdal
from pysheds.grid import Grid
import time
import json

#arguments not dependent on region
CATCHMENT_LAYER = 'Catchment'
CATCHMENT_LAYER_ID = 'GridID'
ADJOINT_CATCHMENT_LAYER = 'AdjointCatchment'
ADJOINT_CATCHMENT_LAYER_ID = 'GridID'
POINT_BUFFER_DISTANCE = 5 # used for searching line features for local and global
POLYGON_BUFFER_DISTANCE = 1 # used for eliminating slivers when merging polygon geometries
FAC_SNAP_THRESHOLD = 900 

class Watershed:
    '''Returns a delineated basin from a query point.'''
    # init() -> get_global() -> get_local() -> retrieve_pixel_value()
    #                                 |------> split_catchment()
    #                                 |------> aggregate_geometries() -> search_upstream_geometry()
    #                                                   |--------------> geom_to_geojson()
    #                                                   |--------------> cleanup()


    ogr.UseExceptions()
    gdal.UseExceptions() 

    def __init__(self, y=None, x=None, region=None, dataPath=None):

        self.x = x
        self.y = y
        self.region = region
        self.dataPath = dataPath
        self.huc_net_junction_list = []
        self.upstream_huc_list = []
        self.splitCatchment = None
        self.adjointCatchment = None
        self.mergedCatchment = None
        self.driver = ogr.GetDriverByName("OpenFileGDB")

        # Set archydro folder names based on inout region (state)
        # Global Geodatabase
        self.global_gdb = 'global.gdb'
        if region in ['ky', 'ms', 'nc', 'ut', 'va']:
            self.global_gdb = 'Global.gdb'
        if region is 'ny':
            self.global_gdb = 'global.GDB'

        # Hucpoly layer:
        self.hucLayer = 'hucpoly'
        if region is 'va':
            self.hucLayer = 'HucPoly'

        self.hucNameFieldIndex = 'Name'
        if region in ['de', 'ia', 'md', 'ny', 'ok']:
            self.hucNameFieldIndex = 'NAME'

        self.hucLayerJunctionID = 'JunctionID'

        # Streams Layer
        self.globalStreamsLayer = 'streams'
        if region in ['oh']:
            self.globalStreamsLayer = 'Streams3d'
        if region in ['ny']:
            self.globalStreamsLayer = 'streams3D'
        if region in ['ar', 'co', 'ct', 'ga', 'ia', 'id', 'il', 'in', 'mn', 'mo', 'ms', 'nd', 'nh', 'nj', 'ok', 'pr', 'ri', 'sc', 'sd', 'tn']:
            self.globalStreamsLayer = 'Streams3D'

        self.globalStreamsHydroIdIndex = 'Line2DID'
        if region in ['ak', 'ks', 'me', 'mt', 'nm', 'pa', 'va', 'wi']:
            self.globalStreamsHydroIdIndex = 'HYDROID'
        if region in ['al', 'az', 'ca', 'de', 'hi', 'ky', 'ma', 'md', 'nc', 'ut', 'vt', 'wa', 'ar', 'co', 'ct', 'pr', 'nd', 'ny']:
            self.globalStreamsHydroIdIndex = 'HydroID'
        
        # Junctions Point layer
        self.hucNetJunctionsLayer = 'Point3D'
        if region in ['tn']:
            self.hucNetJunctionsLayer = 'Junction3D'
        if region in ['ak', 'al', 'az', 'ca', 'de', 'ks', 'ky', 'ma', 'md', 'me', 'mt', 'nm', 'pa', 'ut', 'vt', 'wi', 'ct', 'or']:
            self.hucNetJunctionsLayer = 'huc_net_Junctions'
        if region in ['va']:
            self.hucNetJunctionsLayer = 'Huc_net_Junctions'
        if region in ['wa']:
            self.hucNetJunctionsLayer = 'HUC_Net_Junctions'
        if region in ['ny']:
            self.hucNetJunctionsLayer = 'huc_net_Junctions3D'

        self.hucNetJunctionsIdIndex = 'Point2DID'
        if region in ['ak', 'ks', 'me', 'mt', 'nm', 'pa', 'wi', 'or']:
            self.hucNetJunctionsIdIndex = 'HYDROID'
        if region in ['al', 'az', 'ca', 'de', 'ky', 'ma', 'md', 'ut', 'va', 'vt', 'ct', 'ms']:
            self.hucNetJunctionsIdIndex = 'HydroID'
        if region in ['il']:
            self.hucNetJunctionsIdIndex = 'OID'


        #kick off
        self.get_global() 

    def serialize(self):
        return {
            'splitCatchment': self.splitCatchment, 
            'adjointCatchment': self.adjointCatchment,
            'mergedCatchment': self.mergedCatchment
        }

    def split_catchment(self, flow_dir, geom, x, y): 
        """Returns split_geom"""

        #method to use catchment bounding box instead of exact geom
        minX, maxX, minY, maxY = geom.GetEnvelope()
        # print('HERE', minX, minY, maxX, maxY)
        gdal.Warp('./vsimem/fdr.tif', flow_dir, outputBounds=[minX, minY, maxX, maxY])

        # Instantiate a grid from the clipped fdr raster
        grid = Grid.from_raster('./vsimem/fdr.tif', data_name='dir')

        # Read the fdr raster
        fdr = grid.read_raster('./vsimem/fdr.tif')
        
        # Delineate catchment with pysheds
        catch = grid.catchment(fdir=fdr, x=x, y=y, out_name='catch', recursionlimit=15000, xytype='label')
        
        # Clip the bounding box to the catchment
        grid.clip_to(catch)

        #some sort of strange raster to polygon conversion using rasterio method
        shapes = grid.polygonize()

        # get split Catchment geometry
        print('Split catchment complete')
        split_geom = ogr.Geometry(ogr.wkbPolygon)

        for shape in shapes:
            split_geom = split_geom.Union(ogr.CreateGeometryFromJson(json.dumps(shape[0])))
        
        return split_geom

    def retrieve_pixel_value(self, geo_coord, raster):
        """Returns value of raster, and the coords of the top left of the cell."""

        # Open str900 grid
        dataset = gdal.Open(raster) 
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
        value = data[row][col]

        #pysheds actually wants the top left of pixel, not the center
        outX = ((col * pixelWidth) + xOrigin)
        outY = ((row * -pixelHeight) + yOrigin)

        del dataset #cleanup

        #return value and adjusted x,y
        return(value, outX, outY)

    def geom_to_geojson(self, in_geom, name, simplify_tolerance, in_ref, out_ref, write_output=False):
        in_geom = in_geom.Simplify(simplify_tolerance)
        out_ref.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

        transform = osr.CoordinateTransformation(in_ref, out_ref)
        
        #don't want to affect original geometry
        transform_geom = in_geom.Clone()
        
        #trasnsform geometry from whatever the local projection is to wgs84
        transform_geom.Transform(transform)
        json_text = transform_geom.ExportToJson()

        #add some attributes
        geom_json = json.loads(json_text)

        #get area in local units
        area = in_geom.GetArea()

        print('processing: ' + name + ' area: ' + str(area*0.00000038610))

        geojson_dict = {
            "type": "Feature",
            "geometry": geom_json,
            "properties": {
                "area": area
            }
        }

        if write_output:
            f = open('./' + name + '.geojson','w')
            f.write(json.dumps(geojson_dict))
            f.close()
            print('Exported geojson:', name)
        
        return geojson_dict

    def search_upstream_geometry(self, geom, name):

        print('Search upstream geometry:', name)
        

        #get list of huc_net_junctions using merged catchment geometry
        self.hucNetJunctionsLayer.SetSpatialFilter(None)
        self.hucNetJunctionsLayer.SetSpatialFilter(geom)
        self.hucNetJunctionsFeat = None

        #loop over each junction
        for hucNetJunctions_feat in self.hucNetJunctionsLayer:
            self.hucNetJunctionsID = hucNetJunctions_feat.GetFieldAsString(self.hucNetJunctionsIdIndex)
            self.hucNetJunctionsFeat = hucNetJunctions_feat
            s = (self.hucLayerJunctionID + " = " + self.hucNetJunctionsID + "")
            print('huc search string:',s)
            if s not in self.huc_net_junction_list:
                self.huc_net_junction_list.append(s)

        if not self.hucNetJunctionsFeat:
            print('ERROR: no huc_net_junction features found within the geom:',name)
                
        #print("HUC_net_junction list:",huc_net_junction_list)

        if len(self.huc_net_junction_list) == 0:
            return

        #search for upstream connected HUC using huc_net_junctions
        operator = " OR "
        huc_net_junction_string = operator.join(self.huc_net_junction_list) 
        print('huc_net_junction_string', huc_net_junction_string)
        self.hucLayer.SetAttributeFilter(None)
        self.hucLayer.SetAttributeFilter(huc_net_junction_string)

        #loop over upstream HUCs
        for huc_select_feat in self.hucLayer:
            huc_name = huc_select_feat.GetFieldAsString(self.hucNameFieldIndex)
            print('found huc:',huc_name)
            
            if huc_name not in self.upstream_huc_list:
                upstreamHUC = huc_select_feat.GetGeometryRef()
                self.upstream_huc_list.append(huc_name)

                #recursive call to search next HUC
                self.search_upstream_geometry(upstreamHUC, huc_name)

        return       
    
    def get_global(self):
        """Find the HUC the point falls in and kicks off the get_local function.
        ---------------------------------------------------------------------------
        defines: global_gdb, huclayer, globalStreamsLayer, globalStreamsHydroIdIndex,
        hucNetJunctionsLayer, hucNetJunctionsIdIndex, region_ref, webmerc_ref
        """

        globalDataPath = f'{self.dataPath}{self.region}/archydro/'

        # opening the FileGDB
        globalGDB = globalDataPath + self.global_gdb
        self.global_gdb = self.driver.Open(globalGDB, 0)
            
        if self.global_gdb is None:
            print('ERROR: Missing global gdb for:', self.region)

        print('y,x:',self.y,',',self.x,'\nRegion:',self.region,'\nGlobalDataPath:',globalDataPath,'\nGlobalGDB:',globalGDB)

        # set global HUC layer (should be only one possibility)
        self.hucLayer = self.global_gdb.GetLayer(self.hucLayer)
        if self.hucLayer is None:
            print('ERROR: Missing the hucpoly layer for:', self.region)

        # try:
        #     print('self.hucNameFieldIndex:', self.hucNameFieldIndex, type(self.hucNameFieldIndex))
        #     self.hucNameFieldIndex = self.hucLayer.GetLayerDefn().GetFieldIndex(self.hucNameFieldIndex)
        #     print('self.hucNameFieldIndex:', self.hucNameFieldIndex, type(self.hucNameFieldIndex))
        # except ValueError:
        #     print('ERROR: Missing hucNameFieldIndex:', self.hucNameFieldIndex)

        # set global streams layer (multiple possibilities)
        self.globalStreamsLayer = self.global_gdb.GetLayer(self.globalStreamsLayer)
            
        if self.globalStreamsLayer is None:
            print('ERROR: Missing global streams layer for:', self.region)

        # try:
        #     print('self.globalStreamsHydroIdIndex:', self.globalStreamsHydroIdIndex, type(self.globalStreamsHydroIdIndex))
        #     self.globalStreamsHydroIdIndex = self.globalStreamsLayer.GetLayerDefn().GetFieldIndex(self.globalStreamsHydroIdIndex)
        #     print('self.globalStreamsHydroIdIndex:', self.globalStreamsHydroIdIndex, type(self.globalStreamsHydroIdIndex))
        # except ValueError:
        #     print('ERROR: globalStreamsHydroIdIndex:', self.hucNameFieldIndex)

        # set huc_net_junctions layer 
        self.hucNetJunctionsLayer = self.global_gdb.GetLayer(self.hucNetJunctionsLayer)
        if self.hucNetJunctionsLayer is None:
            print('ERROR: Missing huc_net_junctions layer for:', self.region)

        # #looks like there are also multiple possibilities for the huc_net_junctions layerID field
        # print('self.hucNetJunctionsIdIndex:', self.hucNetJunctionsIdIndex, type(self.hucNetJunctionsIdIndex))
        # self.hucNetJunctionsIdIndex = self.hucNetJunctionsLayer.GetLayerDefn().GetFieldIndex(self.hucNetJunctionsIdIndex)
        # print('self.hucNetJunctionsIdIndex:', self.hucNetJunctionsIdIndex, type(self.hucNetJunctionsIdIndex))
            
        # if self.hucNetJunctionsIdIndex == -1:
        #     print('ERROR: huc_net_junctions ID not found for:', region)

        #Create a transformation between this and the hucpoly projection
        self.region_ref = self.hucLayer.GetSpatialRef()
        self.webmerc_ref = osr.SpatialReference()
        self.webmerc_ref.ImportFromEPSG(4326)

        #gdal 3 changes require this line: https://github.com/OSGeo/gdal/blob/master/gdal/swig/python/samples/ogr2ogr.py
        self.webmerc_ref.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

        ctran = osr.CoordinateTransformation(self.webmerc_ref,self.region_ref)

        #Transform incoming longitude/latitude to the hucpoly projection
        [self.projectedLng,self.projectedLat,z] = ctran.TransformPoint(self.x,self.y)

        print(self.projectedLng,self.projectedLat)

        #Create a point
        inputPointProjected = ogr.Geometry(ogr.wkbPoint)
        inputPointProjected.SetPoint_2D(0, self.projectedLng, self.projectedLat)

        #find the HUC the point is in
        self.hucLayer.SetSpatialFilter(inputPointProjected)

        #Loop through the overlapped features and display the field of interest
        for hucpoly_feat in self.hucLayer:
            hucName = hucpoly_feat.GetFieldAsString(self.hucNameFieldIndex)
            print('found your hucpoly: ',hucName)

            #store local path info now that we know it
            localDataPath = globalDataPath + hucName + '/'
            localGDB = localDataPath + hucName + '.gdb'

        try:
            hucName
        except NameError:
            print('no hucpoly found')

        #clear hucLayer spatial filter
        self.hucLayer.SetSpatialFilter(None)

        #now that we know local huc, get rest of local info
        self.get_local(inputPointProjected, localDataPath, localGDB)

    def get_local(self, inputPointProjected, localDataPath, localGDB):
        """ Opens local catchment gdb. Then runs retrieve_pixel_value, splitcatchment, aggregate_geometries functions.
        ----------------------------------------------------------------
        sets: snappedProjectedX, snappedProjectedY, adjointCatchmentGeom, splitCatchmentGeom

        """
            
        fdr_grid = localDataPath + 'fdr'
        str_grid = localDataPath + 'str'

        #to start assume we have a local
        on_str_grid = False
        self.isLocal = True
        self.isLocalGlobal = False
        self.isGlobal = False

        #query str grid with pixel value
        str_val, self.snappedProjectedX, self.snappedProjectedY = self.retrieve_pixel_value((self.projectedLng, self.projectedLat), str_grid)

        #point is on an str cell
        if str_val == 1:
            on_str_grid = True

        # opening the FileGDB
        try:
            local_gdb = self.driver.Open(localGDB, 0)
        except:
            print('ERROR: Check to make sure you have a local gdb for:', hucName)

        #define local data layers
        catchmentLayer = local_gdb.GetLayer(CATCHMENT_LAYER)
        if catchmentLayer is None:
            print('ERROR: Check to make sure you have a local catchment for:', hucName)

        adjointCatchmentLayer = local_gdb.GetLayer(ADJOINT_CATCHMENT_LAYER)
        if adjointCatchmentLayer is None:
            print('ERROR: Check to make sure you have a local adjoint catchment for:', hucName)

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

        #we know we are on an str cell, so need to check for an adjointCatchment
        if on_str_grid:

            #select adjoint catchment layer using ID from current catchment
            select_string = (ADJOINT_CATCHMENT_LAYER_ID + " = '" + catchmentID + "'")
            print('select string:',select_string)
            adjointCatchmentLayer.SetAttributeFilter(select_string)

            adjointCatchmentFeat = None
            for adjointCatchment_feat in adjointCatchmentLayer:
                print('found upstream adjointCatchment')
                self.adjointCatchmentGeom = adjointCatchment_feat.GetGeometryRef()
                adjointCatchmentFeat = adjointCatchment_feat

                #create multipolygon container for all parts
                mergedAdjointCatchmentGeom = ogr.Geometry(ogr.wkbMultiPolygon)

                #for some reason this is coming out as multipolygon
                if self.adjointCatchmentGeom.GetGeometryName() == 'MULTIPOLYGON':
                    for geom_part in self.adjointCatchmentGeom:
                        mergedAdjointCatchmentGeom.AddGeometry(geom_part)
                        
                    self.adjointCatchmentGeom = mergedAdjointCatchmentGeom.UnionCascaded()

            #there are cases where a point has str cell, but does not have an adjointCatchment
            if adjointCatchmentFeat:
                print('point is a localGlobal')

                self.isLocal = False
                self.isLocalGlobal = True

                #buffer point
                bufferPoint = inputPointProjected.Buffer(POINT_BUFFER_DISTANCE)

                #since we know we are local global, also check if we are global
                self.globalStreamsLayer.SetSpatialFilter(bufferPoint)

                #Loop through the overlapped features and display the field of interest
                for stream_feat in self.globalStreamsLayer:
                    globalStreamID = stream_feat.GetFieldAsString(self.globalStreamsHydroIdIndex)
                    print('input point is type "global" with ID:', globalStreamID)
                    self.isGlobal = True
            else:
                print('point is a local')

        else:
            #no adjoint catchment
            print('No adjoint catchment for this point')

        #print("Time before split catchment:",time.perf_counter() - timeBefore)
        print('Projected X,Y:',self.projectedLng, ',', self.projectedLat)
        print('Center Projected X,Y:',self.snappedProjectedX, ',', self.snappedProjectedY)

        self.splitCatchmentGeom = self.split_catchment(fdr_grid, catchmentGeom, self.snappedProjectedX, self.snappedProjectedY)

        #print("Time after split catchment:",time.perf_counter() - timeBefore)

        #cleanup
        del local_gdb

        self.aggregate_geometries()

    def aggregate_geometries(self):
        """Merges geometries together and return as geosjon."""

        #merge adjoint Catchment geom with split catchment and were done
        if self.isLocalGlobal:
        
            #apply a small buffer to adjoint catchment to remove sliver
            self.adjointCatchmentGeom = self.adjointCatchmentGeom.Buffer(POLYGON_BUFFER_DISTANCE)
            
            #need to merge splitCatchment and adjointCatchment
            mergedCatchmentGeom = self.adjointCatchmentGeom.Union(self.splitCatchmentGeom)
            
        #need to merge all upstream hucs in addition to localGlobal
        if self.isGlobal:
        
            #kick off upstream global search recursive function starting with mergedCatchment
            self.search_upstream_geometry(mergedCatchmentGeom, 'adjointCatchment')
            
            #print("Time before merge:",time.perf_counter() - timeBefore)
            print('UPSTREAM HUC LIST:', self.upstream_huc_list)
            print('self.hucNameFieldIndex:', self.hucNameFieldIndex, type(self.hucNameFieldIndex))
            
            if len(self.upstream_huc_list) > 0:
                
                #make sure filter is clear
                self.hucLayer.SetAttributeFilter(None)

                #set attribute filter 
                if len(self.upstream_huc_list) == 1:
                    self.hucLayer.SetAttributeFilter(self.hucNameFieldIndex + " = '" + self.upstream_huc_list[0] + "'")
                #'in' operator doesnt work with list len of 1
                else:
                    self.hucLayer.SetAttributeFilter(self.hucNameFieldIndex + ' IN {}'.format(tuple(self.upstream_huc_list)))
                
                #create multipolygon container for all watershed parks
                mergedWatershed = ogr.Geometry(ogr.wkbMultiPolygon)
                
                #loop and merge upstream global HUCs
                for huc_select_feat in self.hucLayer:
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

        if self.isLocal:
            #if its a local this is all we want to return
            self.mergedCatchment = self.geom_to_geojson(self.splitCatchmentGeom, 'mergedCatchment', 10, self.region_ref, self.webmerc_ref, False)
        else:
            self.mergedCatchment =  self.geom_to_geojson(mergedCatchmentGeom, 'mergedCatchment', 10, self.region_ref, self.webmerc_ref, False)
            self.adjointCatchment =  self.geom_to_geojson(self.adjointCatchmentGeom, 'adjointCatchment', 10, self.region_ref, self.webmerc_ref, False)
        
        #always write out split catchment
        self.splitCatchment =  self.geom_to_geojson(self.splitCatchmentGeom, 'splitCatchment', 10, self.region_ref, self.webmerc_ref, False)

        self.cleanup()

        return
        
    def cleanup(self):

        # clean close
        del self.global_gdb
        del self.driver
        del self.globalStreamsLayer
        del self.hucLayer
        del self.hucNetJunctionsLayer
        del self.hucLayerJunctionID
        del self.region_ref
        del self.webmerc_ref
        del self.splitCatchmentGeom
        del self.globalStreamsHydroIdIndex
        del self.hucNameFieldIndex
        del self.hucNetJunctionsIdIndex

if __name__=='__main__':

    timeBefore = time.perf_counter()  

    #test site
    point = (44.00683,-73.74586)
    region = 'ny'
    dataPath = 'C:/Users/ahopkins/streamstats/data/'

    #start main program
    delineation = Watershed(point[0],point[1],region,dataPath)
    area = round(delineation.mergedCatchment['properties']['area']*0.00000038610,2)   
    print("mergedCatchment area:",area)

    timeAfter = time.perf_counter() 
    totalTime = timeAfter - timeBefore
    print("Total Time:",totalTime)