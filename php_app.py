#!/usr/bin/python3.6

import sys

try:
    from osgeo import gdal
except ImportError as error:
	# Output expected ImportErrors.
	print(error.__class__.__name__ + ": " + error.message)
except ModuleNotFoundError:
    print('Absolute import failed')
except Exception as exception:
	# Output unexpected Exceptions.
	print(exception, False)
	print(exception.__class__.__name__ + ": " + exception.message)
		
x = sys.argv[1]
y = sys.argv[2]

print('Running script ' + sys.argv[0] + ' with these coords: (' + x + ' , ' + y + ')')
print('Python version: ' + sys.version)
print('GDAL version: ' + gdal.__version__)