from osgeo import ogr, gdal, osr
import os
os.environ['PROJ_LIB'] = 'C:/Users/marsmith/miniconda/envs/delineate/Library/share/proj'
os.environ['GDAL_DATA'] = 'C:/Users/marsmith/miniconda/envs/delineate/Library/share'

InputImage = 'C:/NYBackup/GitHub/ss-delineate/data/nhd_fdrCopy.tif'
Shapefile = 'C:/NYBackup/GitHub/ss-delineate/data/OGRGeoJSON.shp'
OutImage = 'C:/NYBackup/GitHub/ss-delineate/data/fdr2.tif'
RasterFormat = 'GTiff'
PixelRes = 30

#tif with projections I want
tif = gdal.Open(InputImage)
Projection = tif.GetProjectionRef()

driver = ogr.GetDriverByName("ESRI Shapefile")
dataSource =   driver.Open(Shapefile, 1)
layer = dataSource.GetLayer()
feature = layer[0]

#set spatial reference and transformation
sourceprj = layer.GetSpatialRef()
targetprj = osr.SpatialReference(wkt = tif.GetProjection())
transform = osr.CoordinateTransformation(sourceprj, targetprj)

#apply transformation
transformed = feature.GetGeometryRef()
transformed.Transform(transform)
geom = ogr.CreateGeometryFromWkb(transformed.ExportToWkb())

minX, maxX, minY, maxY = geom.GetEnvelope() # Get bounding box of the shapefile feature

bounds1 = [minX, minY, maxX, maxY]
print('bounds1:', bounds1)

# Create raster
OutTile = gdal.Warp(OutImage, InputImage, format=RasterFormat, outputBounds=bounds1, xRes=PixelRes, yRes=PixelRes, dstSRS=Projection, resampleAlg=gdal.GRA_NearestNeighbour, options=['COMPRESS=DEFLATE'])
OutTile = None # Close dataset

# Close datasets
Raster = None
print("Done.")