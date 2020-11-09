from osgeo import ogr, gdal, osr
import os, json
os.environ['PROJ_LIB'] = 'C:/Users/marsmith/miniconda/envs/delineate/Library/share/proj'
os.environ['GDAL_DATA'] = 'C:/Users/marsmith/miniconda/envs/delineate/Library/share'

InputImage = 'C:/NYBackup/GitHub/ss-delineate/data/nhd_fdr.tif'
inputBounds = {'minX':-73.7655,'minY': 43.9866,'maxX':-73.6975,'maxY': 44.0203}
geojson = {"type":"FeatureCollection","features":[{"type":"Feature","id":"catchmentsp.70847","geometry":{"type":"MultiPolygon","coordinates":[[[[-73.7531,43.992],[-73.7557,43.9936],[-73.7575,43.9953],[-73.7592,43.9959],[-73.7603,43.9967],[-73.7604,43.9983],[-73.7609,43.9992],[-73.761,44.001],[-73.7626,44.0012],[-73.7632,44.0016],[-73.7646,44.0015],[-73.7651,44.0012],[-73.7653,44.0013],[-73.7655,44.0021],[-73.7653,44.0033],[-73.7634,44.0064],[-73.7608,44.0089],[-73.7596,44.0113],[-73.7602,44.0127],[-73.7578,44.0142],[-73.7565,44.0151],[-73.7537,44.0155],[-73.7513,44.0162],[-73.7501,44.0173],[-73.7502,44.018],[-73.7497,44.0178],[-73.7482,44.0159],[-73.7463,44.0155],[-73.7442,44.017],[-73.7423,44.0197],[-73.7394,44.0203],[-73.7375,44.0196],[-73.7359,44.0188],[-73.7283,44.0172],[-73.7267,44.0157],[-73.7302,44.0139],[-73.73,44.0126],[-73.7233,44.0053],[-73.7191,44.0043],[-73.7181,44.0038],[-73.7165,44.0031],[-73.7158,44.0015],[-73.7154,44.0003],[-73.715,43.9999],[-73.7123,44.0002],[-73.7092,44.0009],[-73.7087,44.0006],[-73.7086,44],[-73.7075,43.9995],[-73.7063,43.9985],[-73.7038,43.9992],[-73.7024,43.9986],[-73.7004,43.9966],[-73.6975,43.9954],[-73.6975,43.9945],[-73.6981,43.9936],[-73.699,43.9934],[-73.7004,43.9923],[-73.7004,43.9912],[-73.7022,43.9907],[-73.7034,43.9899],[-73.7044,43.99],[-73.7059,43.9901],[-73.7073,43.989],[-73.7087,43.9889],[-73.7104,43.9898],[-73.7126,43.989],[-73.714,43.9889],[-73.7154,43.9875],[-73.7167,43.9866],[-73.7187,43.9885],[-73.7212,43.9888],[-73.7223,43.9904],[-73.7264,43.9904],[-73.7282,43.9895],[-73.7294,43.9893],[-73.732,43.9899],[-73.7336,43.9901],[-73.7359,43.9908],[-73.7385,43.9909],[-73.7402,43.9918],[-73.7423,43.9925],[-73.7453,43.9939],[-73.7479,43.9948],[-73.7507,43.9946],[-73.752,43.9933],[-73.7529,43.992],[-73.7531,43.992]]]]},"geometry_name":"the_geom","properties":{"gridcode":1663570,"featureid":22304091,"sourcefc":"NHDFlowline","areasqkm":10.508532,"shape_length":0.180994304773454,"shape_area":0.00117919874683051,"bbox":[-73.7655,43.9866,-73.6975,44.0203]}}],"totalFeatures":1,"numberMatched":1,"numberReturned":1,"timeStamp":"2020-11-03T01:10:06.559Z","crs":{"type":"name","properties":{"name":"urn:ogc:def:crs:EPSG::4326"}},"bbox":[-73.7655,43.9866,-73.6975,44.0203]}
OutImage = 'C:/NYBackup/GitHub/ss-delineate/data/fdr3.tif'
RasterFormat = 'GTiff'
PixelRes = 30

#tif with projections I want
tif = gdal.Open(InputImage)
Projection = tif.GetProjectionRef()
targetprj = osr.SpatialReference(wkt = tif.GetProjection())

# WGS84 projection reference
sourprjFromEPSG = osr.SpatialReference()
sourprjFromEPSG.ImportFromProj4('+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs ')

transform = osr.CoordinateTransformation(sourprjFromEPSG,targetprj)

#grab geom from first feature
gj_geom = json.dumps(geojson['features'][0]['geometry'])
print('test', gj_geom )
polyogr = ogr.CreateGeometryFromJson(gj_geom)
polyogr.Transform(transform)


minX, maxX, minY, maxY = polyogr.GetEnvelope()

# [-73.7655,43.9866,-73.6975,44.0203]
print('bounds:', minX, maxX, minY, maxY)
# 1760643.1007263518 1766141.231241892 2540598.51252413 2543922.278361059  good albers bounds for clip

#print('bounds:', minX, maxX, minY, maxY)

# Create raster
OutTile = gdal.Warp(OutImage,InputImage, format=RasterFormat, outputBounds=[minX, minY, maxX, maxY], xRes=PixelRes, yRes=PixelRes, dstSRS=Projection, resampleAlg=gdal.GRA_NearestNeighbour, options=['COMPRESS=DEFLATE'])
OutTile = None # Close dataset

# Close datasets
Raster = None
#VectorDataset.Destroy()
print("Done.")