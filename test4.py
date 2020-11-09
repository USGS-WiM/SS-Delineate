from osgeo import ogr
from osgeo import osr
import os
os.environ['PROJ_LIB'] = 'C:/Users/marsmith/miniconda/envs/delineate/Library/share/proj'
os.environ['GDAL_DATA'] = 'C:/Users/marsmith/miniconda/envs/delineate/Library/share'

source = osr.SpatialReference()
source.ImportFromEPSG(4326)

target = osr.SpatialReference()
target.ImportFromEPSG(5070)

transform = osr.CoordinateTransformation(source, target)

point = ogr.CreateGeometryFromWkt("POINT ( 43.9866 -73.7655)")
point.Transform(transform)

print(point.ExportToWkt())