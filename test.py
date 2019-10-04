from osgeo import gdal

geo_coord = (603174.5282394718, 4876139.116718482)
str_grid = 'C:/Temp/ny/archydro/02020001/str'

dataset = gdal.Open(str_grid)

transform = dataset.GetGeoTransform()
print(transform)
print(dataset)
xOrigin = transform[0]
yOrigin = transform[3]
pixelWidth = transform[1]
pixelHeight = -transform[5]

cols = dataset.RasterXSize
rows = dataset.RasterYSize
band = dataset.GetRasterBand(1)
data = band.ReadAsArray(0, 0, cols, rows)

print(geo_coord[0],xOrigin,pixelWidth)
col = int((geo_coord[0] - xOrigin) / pixelWidth)
row = int((yOrigin - geo_coord[1] ) / pixelHeight)

#transform pixel back to origin coordinates to and get center
outX = ((col * pixelWidth) + xOrigin) + pixelWidth/2
outY = ((row * -pixelHeight) + yOrigin) - pixelHeight/2

print(outX,outY)
print(data[row][col])
