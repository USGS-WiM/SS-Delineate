
import argparse
import sys
from osgeo import ogr, gdal
from pysheds.grid import Grid

parser = argparse.ArgumentParser(description='Delineates a basin from an input lat/lon')
parser.add_argument('region', nargs='?', type=str, help='State/Region of input delineation', default='ny')
parser.add_argument('lat', nargs='?', type=float, help='Latitude of input point', default=44.00683)
parser.add_argument('lng', nargs='?', type=float, help='Longitude of input point', default=-73.74586)
parser.add_argument('dataFolder', nargs='?', type=str, help='Location of input data', default='c:/temp/')

args = parser.parse_args()
print(str(args))

class Point(object):
    def __init__(self,decimalDegreesLat,decimalDegreesLong):
        self.latDD = decimalDegreesLat
        self.lngDD = decimalDegreesLong
        self.projectedLat = None
        self.projectedLng = None
        self.dataPath = ''
        self.globalGDB = ''
        self.localDataPath = ''
        self.localGDB = ''
        self.inputPointProjected = None
        self.dataPath = 'n/a'
        self.hucName = 'n/a'
        self.isGlobal = False
        self.catchmentID = 'n/a'
        self.catchmentLayer = None
        self.adjointCatchment = 'n/a'
    
    #allow for string representation
    def __str__(self):
        return str(self.__class__) + ": " + str(self.__dict__)

    def setDataPaths(self, dataPath, region, globalGDBName):
        self.dataPath = dataPath + region + '/'
        self.region = region
        self.globalGDB = self.dataPath + globalGDBName

    def getGlobalInfo(self, hucLayerName, hucLayerNameField, globalStreamsLayerName, globalStreamsLayerNameField):
        '''
        This function gets global level information for input point
        '''

        # use OGR specific exceptions
        ogr.UseExceptions()

        # get the driver
        driver = ogr.GetDriverByName("OpenFileGDB")

        # opening the FileGDB
        try:
            gdb = driver.Open(self.globalGDB, 0)
        except e:
            print('Check to make sure you have a global gdb for:', self.region)
            sys.exit()

        #get polygon layer to query
        hucLayer = gdb.GetLayer(hucLayerName)
        globalStreamsLayer = gdb.GetLayer(globalStreamsLayerName)

        #Put the title of the field you are interested in here
        hucNameFieldIndex = hucLayer.GetLayerDefn().GetFieldIndex(hucLayerNameField)
        globalStreamsHydroIdIndex = globalStreamsLayer.GetLayerDefn().GetFieldIndex(globalStreamsLayerNameField)

        #The following assumes that the latitude longitude is in WGS84 ("EPSG:4326")
        #We will create a transformation between this and the hucpoly projection
        geo_ref = hucLayer.GetSpatialRef()
        point_ref=ogr.osr.SpatialReference()
        point_ref.ImportFromEPSG(4326)
        ctran=ogr.osr.CoordinateTransformation(point_ref,geo_ref)

        #Transform incoming longitude/latitude to the hucpoly projection
        [lon,lat,z]=ctran.TransformPoint(point.lngDD,point.latDD)

        #store projected coords
        self.projectedLat = lat
        self.projectedLng = lon

        #Create a point
        pt = ogr.Geometry(ogr.wkbPoint)
        pt.SetPoint_2D(0, self.projectedLng, self.projectedLat)

        #store point layer
        self.inputPointProjected = pt

        #Set up a spatial filter such that the only features we see when we
        #loop through "hucLayer" are those which overlap the point defined above
        hucLayer.SetSpatialFilter(pt)

        #Loop through the overlapped features and display the field of interest
        for feat_in in hucLayer:
            intersectPoly = feat_in.GetFieldAsString(hucNameFieldIndex)
            print('found your hucpoly: ',intersectPoly)
            self.hucName = intersectPoly

            #store local path info now that we know it
            self.localDataPath = self.dataPath + point.hucName + '/'
            self.localGDB = self.localDataPath + point.hucName + '.gdb'

        #Set up a spatial filter such that the only features we see when we
        #loop through "hucLayer" are those which overlap the point defined above
        globalStreamsLayer.SetSpatialFilter(pt)

        #Loop through the overlapped features and display the field of interest
        for feat_in in globalStreamsLayer:
            intersectStream = feat_in.GetFieldAsString(globalStreamsHydroIdIndex)
            print('found a global stream:', intersectStream)
            self.isGlobal = True

        # clean close
        del gdb


    def getLocalInfo(self, catchmentLayerName, catchmentLayerNameField, adjointCatchmentLayerName, drainageLineLayerName):
        '''
        This function finds the HUC workspace of the input point
        '''

        # use OGR specific exceptions
        ogr.UseExceptions()

        # get the driver
        driver = ogr.GetDriverByName("OpenFileGDB")

        # opening the FileGDB
        try:
            gdb = driver.Open(self.localGDB, 0)
        except e:
            print('Check to make sure you have a global gdb for:', self.region)
            sys.exit()

        #get polygon layer to query
        catchmentLayer = gdb.GetLayer(catchmentLayerName)
        adjointCatchmentLayer = gdb.GetLayer(adjointCatchmentLayerName)
        drainageLineLayer = gdb.GetLayer(adjointCatchmentLayerName)
        #fdrGrid = 

        #Put the title of the field you are interested in here
        catchmentLayerNameFieldIndex = catchmentLayer.GetLayerDefn().GetFieldIndex(catchmentLayerNameField)

        #since we've already done this we can reuse the stored point layer
        pt = self.inputPointProjected

        #Set up a spatial filter to find features under point
        catchmentLayer.SetSpatialFilter(pt)

        #Loop through the overlapped features and display the field of interest
        for feat_in in catchmentLayer:
            intersectPoly = feat_in.GetFieldAsString(catchmentLayerNameFieldIndex)
            print('found your catchment. HydroID is: ',intersectPoly)
            self.catchmentID = intersectPoly
            self.catchmentLayer = feat_in


        ### ---------------------------------------------------------

        #### CHECK FOR LOCAL GLOBAL USING drainage_line.. get drain ID and use that to accumulate upstream adjointCatchment



        ### ---------------------------------------------------------



        
        # clean close
        del gdb

    def splitCatchment(self):
        '''
        This function computes watershed constrained by current single catchment
        '''

        fdr_grid = self.localDataPath + 'fdr'
        catchmentLayer = self.catchmentLayer

        #gdal in memory files:
        # https://gdal.org/user/virtual_file_systems.html#vsimem-in-memory-files

        #gdal.warp text examples:
        # https://trac.osgeo.org/gdal/browser/trunk/autotest/utilities/test_gdalwarp_lib.py

        #gdalwarp -dstnodata -9999 -cutline catchment265.shp c:/temp/ny/02020001/fdr fdr_265.tif

        #writes an output tiff clipped to a catchment shapefile
        ds = gdal.Warp('c:/temp/ny/fdr265.tif', fdr_grid, cutlineDSName = 'c:/temp/ny/catchment265.shp', cropToCutline = True)

        ds2 = gdal.Warp('c:/temp/ny/dem265.tif', self.localDataPath + 'dem', cutlineDSName = 'c:/temp/ny/catchment265.shp', cropToCutline = True)

        #start pysheds catchment delienation
        grid = Grid.from_raster('c:/temp/ny/dem265.tif', data_name='dem')
        grid.read_raster('c:/temp/ny/fdr265.tif', data_name='dir')
        
        # Delineate the catchment
        x = 600538.3159393527
        y = 4873395.948041559

        grid.catchment(data='dir', x=x, y=y, out_name='catch', recursionlimit=15000, xytype='label')

        # Clip the bounding box to the catchment
        grid.clip_to('catch')

        #write out raster
        out_ras = 'c:/temp/ny/out265.tif'
        grid.to_raster('catch', out_ras)

        singleBandRasterToPolygon(out_ras)

def singleBandRasterToPolygon(raster):
    '''
    This function converts raster to a shapefile
    '''
    src_ds = gdal.Open(raster)
    if src_ds is None:
        print('Unable to open raster dataset')
        sys.exit()

    try:
        srcband = src_ds.GetRasterBand(1)
    except RuntimeError:
        print('Band not found')
        sys.exit()

    dst_layername = "c:/temp/ny/test"
    drv = ogr.GetDriverByName("ESRI Shapefile")
    dst_ds = drv.CreateDataSource( dst_layername + ".shp" )
    dst_layer = dst_ds.CreateLayer(dst_layername, srs = None )
    gdal.Polygonize( srcband, None, dst_layer, -1, [], callback=None )



if __name__ == "__main__":

    #arguments
    GLOBAL_GDB = 'global.GDB'
    HUCPOLY_LAYER = 'hucpoly'
    HUCPOLY_LAYER_ID = 'NAME'
    GLOBAL_STREAM_LAYER = ['streams3d', 'streams']
    GLOBAL_STREAM_LAYER_ID = 'HydroID'
    CATCHMENT_LAYER = 'Catchment'
    CATCHMENT_LAYER_ID = 'HydroID'
    ADJOINT_CATCHMENT_LAYER = 'AdjointCatchment'
    
    #instantiate point object
    point = Point(args.lat,args.lng)
    point.setDataPaths(args.dataFolder, args.region, 'global.GDB')

    #global streams layer is called 'streams' unless the state implemented 10/85 slope
    # NEED TO ADD CHECK FOR THIS

    point.getGlobalInfo('hucpoly', 'NAME', 'streams3d', 'HydroID')
    point.getLocalInfo('Catchment', 'HydroID', 'AdjointCatchment')
    localBasin = point.splitCatchment()



    print(point)