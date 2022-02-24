from os import walk, listdir, path, mkdir
from osgeo import gdal
import json
import sys

state = 'ny'
rootPath = f'C:/Users/ahopkins/streamstats/data/{state}'
archydroPath = f'{rootPath}/archydro'
outPath = f"C:/Users/ahopkins/streamstats/SS-Delineate"
    
    ##### Step 1 
print("Getting State Regions")
regions = []
for dirname in listdir(archydroPath):
    if ".gdb" in dirname.lower():
        continue
    if "corrupt" in dirname.lower():
        continue
    if "hucpoly" in dirname.lower():
        continue
    if "old" in dirname.lower():
        continue
    if "original" in dirname.lower():
        continue
    if "readme" in dirname.lower():
        continue
    if ".aux" in dirname.lower():
        continue
    if ".ini" in dirname.lower():
        continue
    if "export" in dirname.lower():
        continue
    if ".mxd" in dirname.lower():
        continue
    if ".mdb" in dirname.lower():
        continue
    else:
        regions.append(dirname)
        
x = len(regions)
print(f"Found {x} regions:")
# for region in regions:
    # print(region)

print('FDR coverage not complete. Searching for Region FDRs')

fdrPaths = []
regionsWithFDRs = []
regionsWithoutFDRs = []

for region in regions:
    regPath = f"{archydroPath}/{region}"
    for dirname in listdir(regPath):
        if "fdr" == dirname:
            fdrPath = f"{regPath}/fdr/sta.adf"
            fdrPaths.append(fdrPath)
            regionsWithFDRs.append(region)
            break


for region in regions:
    if region not in regionsWithFDRs:
        regionsWithoutFDRs.append(region)
        print("Region ", region, " does not have a FDR")
if len(regionsWithoutFDRs) > 0:
    print('There are not FDRs in each region folder')
    fdrAtRegion = False

if len(regionsWithoutFDRs) == 0:
    fdrAtRegion = True
    print(f"Found FDRs in each region.")


mergedFDR = f"{outPath}/{state}_fdr.tif"    
        # Use GDAL to merge region FDR rasters
gdal.Warp(mergedFDR, fdrPaths, format='GTiff', options=['COMPRESS=LZW', 'TILED=YES'])
print("FDR rasters merged")

