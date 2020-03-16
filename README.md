# ss-delineate
This application is a fully open source solution to delineating drainage basins using StreamStats data as defined by the ArcHydro data model.

####  Pre-requisites
* [miniconda](https://docs.conda.io/en/latest/miniconda.html) installed


* State/Region ArcHydro data in the following format:
    - \ny\archydro\
        * \ny\archydro\global.gdb [file geodatabase]
        * \ny\archydro\01100005\
            - \ny\archydro\01100005\01100005.gdb [file geodatabase]
            - \ny\archydro\01100005\cat [ESRI raster]
            - \ny\archydro\01100005\dem [ESRI raster]
            - \ny\archydro\01100005\fac [ESRI raster]
            - \ny\archydro\01100005\str [ESRI raster]
            - \ny\archydro\01100005\str900 [ESRI raster]
        * \ny\archydro\02020001\
            - \ny\archydro\02020001\02020001.gdb [file geodatabase]
            - \ny\archydro\02020001\cat [ESRI raster]
            - \ny\archydro\02020001\dem [ESRI raster]
            - \ny\archydro\02020001\fac [ESRI raster]
            - \ny\archydro\02020001\str [ESRI raster]
            - \ny\archydro\02020001\str900 [ESRI raster]

...etc
  

## Application setup
Install required packages
```
conda create -n delineate python=3.7 gdal pysheds
```

##  Get Started
You should now be able to run the script at a predefined sample site by running: 
```
conda activate delineate
python delineate.py
```

##  Flask Setup
Install flask dependecies
```
conda install flasl flask-cors
```

Steps to start flask dev server:

* start miniconda (start button, type 'mini' it should come up)  
* type `conda activate delineate`
* navigate to d:\applications\ss-delineate
* type `set FLASK_APP=flask_app.py`
* run flask app `flask run`
