
import os, numpy
os.environ['PROJ_LIB'] = 'C:/Users/marsmith/miniconda/envs/delineate/Library/share/proj'
os.environ['GDAL_DATA'] = 'C:/Users/marsmith/miniconda/envs/delineate/Library/share'

from osgeo import ogr, gdal, osr

InputImage = 'C:/NYBackup/GitHub/ss-delineate/data/nhd_fdr.tif'
Shapefile = 'C:/NYBackup/GitHub/ss-delineate/data/OGRGeoJSON.shp'
OutImage = 'C:/NYBackup/GitHub/ss-delineate/data/fdr2.tif'
RasterFormat = 'GTiff'
PixelRes = 30
VectorFormat = 'ESRI Shapefile'

#tif with projections I want
tif = gdal.Open(InputImage)
Projection = tif.GetProjectionRef()
targetprj = osr.SpatialReference(wkt = tif.GetProjection())

VectorDriver = ogr.GetDriverByName(VectorFormat)
VectorDataset = VectorDriver.Open(Shapefile, 0) # 0=Read-only, 1=Read-Write
layer = VectorDataset.GetLayer()
feature = layer[0]
geom = feature.GetGeometryRef() 
sourceprj = layer.GetSpatialRef()

# WGS84 projection reference
sourprjFromEPSG = osr.SpatialReference()
sourprjFromEPSG.ImportFromProj4('+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs ')

# print('1\n', sourceprj.ExportToPrettyWkt())
# print('2\n', sourprjFromEPSG.ExportToPrettyWkt())

transform1 = osr.CoordinateTransformation(sourprjFromEPSG, targetprj)
transform2 = osr.CoordinateTransformation(sourceprj, targetprj)

print('geom before:', geom.GetEnvelope())

print('geom from service:', '[-73.7655, 43.9866, -73.6975, 44.0203]')

minX, maxX, minY, maxY = geom.GetEnvelope()

geom.Transform(transform1)

minX, maxX, minY, maxY = geom.GetEnvelope() # Get bounding box of the shapefile feature

bounds = [minX, minY, maxX, maxY]
print('bounds:', bounds)

OutTile = gdal.Warp(OutImage, InputImage, format=RasterFormat, outputBounds=bounds, xRes=PixelRes, yRes=PixelRes, dstSRS=Projection, resampleAlg=gdal.GRA_NearestNeighbour, options=['COMPRESS=DEFLATE'])
OutTile = None # Close dataset

# Close datasets
Raster = None
VectorDataset.Destroy()
print("Done.")