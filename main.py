
import argparse
import sys
from osgeo import ogr, gdal

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
        self.inputPointProjected = None
        self.hucName = 'n/a'
        self.isGlobal = False
        self.catchment = 'n/a'
        self.adjointCatchment = 'n/a'
    
    #allow for string representation
    def __str__(self):
        return str(self.__class__) + ": " + str(self.__dict__)

    def getGlobalInfo(self, fileGDB, hucLayerName, hucLayerNameField, globalStreamsLayerName, globalStreamsLayerNameField):
        '''
        This function gets global level information for input point
        '''

        # use OGR specific exceptions
        ogr.UseExceptions()

        # get the driver
        driver = ogr.GetDriverByName("OpenFileGDB")

        # opening the FileGDB
        try:
            gdb = driver.Open(fileGDB, 0)
        except e:
            print('Check to make sure you have a global gdb for:', args.region)
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

        #store projected 
        self.projectedLat = lat
        self.projectedLng = lon

        #Create a point
        pt = ogr.Geometry(ogr.wkbPoint)
        pt.SetPoint_2D(0, self.projectedLng, self.projectedLat)

        self.inputPointProjected = pt

        #Set up a spatial filter such that the only features we see when we
        #loop through "hucLayer" are those which overlap the point defined above
        hucLayer.SetSpatialFilter(pt)

        #Loop through the overlapped features and display the field of interest
        for feat_in in hucLayer:
            intersectPoly = feat_in.GetFieldAsString(hucNameFieldIndex)
            print('found your hucpoly: ',intersectPoly)
            self.hucName = intersectPoly

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

    def getLocalInfo(self, fileGDB, catchmentLayerName, catchmentLayerNameField, adjointCatchmentLayerName):
        '''
        This function finds the HUC workspace of the input point
        '''

        # use OGR specific exceptions
        ogr.UseExceptions()

        # get the driver
        driver = ogr.GetDriverByName("OpenFileGDB")

        # opening the FileGDB
        try:
            gdb = driver.Open(fileGDB, 0)
        except e:
            print('Check to make sure you have a global gdb for:', args.region)
            sys.exit()

        #get polygon layer to query
        catchmentLayer = gdb.GetLayer(catchmentLayerName)
        adjointCatchmentLayer = gdb.GetLayer(adjointCatchmentLayerName)

        #Put the title of the field you are interested in here
        catchmentLayerNameFieldIndex = catchmentLayer.GetLayerDefn().GetFieldIndex(catchmentLayerNameField)
        #globalStreamsHydroIdIndex = globalStreamsLayer.GetLayerDefn().GetFieldIndex(adjointCatchmentLayerNameField)

        #since we've already done this we can reuse the stored point layer
        pt = self.inputPointProjected

        #Set up a spatial filter such that the only features we see when we
        #loop through "hucLayer" are those which overlap the point defined above
        catchmentLayer.SetSpatialFilter(pt)

        #Loop through the overlapped features and display the field of interest
        for feat_in in catchmentLayer:
            intersectPoly = feat_in.GetFieldAsString(catchmentLayerNameFieldIndex)
            print('found your catchment. HydroID is: ',intersectPoly)
            self.catchment = intersectPoly
        
        # clean close
        del gdb


def checkMainStem(point, fileGDB, layerName):
    '''
    This function finds out of the input point is on a 'main stem'
    '''
    return False

def accumulateUpstream(Catchment):
    '''
    This function accumulates upstream areas from selected catchment
    '''
    return geom

def splitCatchment(huc, catchment, flowDir):
    '''
    This function computes watershed constrained by current single catchment
    '''
    return geom


if __name__ == "__main__":
    
    point = Point(args.lat,args.lng)
    globalGDB = args.dataFolder + args.region + '/global.GDB'
    point.getGlobalInfo(globalGDB, 'hucpoly', 'NAME', 'streams3d', 'HydroID')
    localGDB = args.dataFolder + args.region + '/' + point.hucName + '/' + point.hucName + '.gdb'
    point.getLocalInfo(localGDB, 'Catchment', 'HydroID', 'AdjointCatchment')
    #print(point)