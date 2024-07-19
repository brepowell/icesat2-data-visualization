# Breanna Powell
# Created: 07/17/2024

# See this great tutorial about writing netCDF files:
# https://unidata.github.io/python-training/workshop/Bonus/netcdf-writing/

import numpy as np
from netCDF4 import Dataset
from datetime import datetime
import os
from utility import *

USER                = os. getlogin()                        #TODO: check if this is ok for Perlmutter
SOURCE              = "SOME PATH NAME TO FILL IN LATER"     #TODO: make this dynamic
NETCDF_FILE_NAME    = "new.nc"                              #TODO: make this dynamic
CELLCOUNT           = 233365 #236853                        #TODO: make this dynamic

FILL_VALUE      = -99999.0
DENSITY_WATER   = 1026
DENSITY_ICE     = 917
DENSITY_SNOW    = 330

#TODO: Make sure the data types are correct; there should be an "f" after many of them.

########################
# OPEN THE NETCDF FILE #
########################

try: ncfile.close()  # just to be safe, make sure dataset is not already open.
except: pass
ncfile = Dataset('new.nc',mode='w',format='NETCDF4_CLASSIC') 

##############
# DIMENSIONS #
##############

# Create the dimensions (nCells is the only dimension needed)
nCells = ncfile.createDimension('nCells', CELLCOUNT)

##############
# ATTRIBUTES #
##############

# Grab the date for the header information
now = datetime.now()
historyString = now.strftime("%d-%B-%Y %H:%M:%S") + ": File created by " + USER

# Set the attributes
ncfile.title        = "Comparison of icesat freeboard with E3SM"
ncfile.source       = SOURCE
ncfile.history      = historyString
ncfile.institution  = "Los Alamos National Laboratory"

#############
# VARIABLES #
#############

def createVariableForNetCDF(shortName, longName, vmax, vmin = 0.0, fillvalue = None, dtype = np.float64):
    """ Add a variable to the netCDF file. 
    It will appear in the header info. """
    variable = ncfile.createVariable(shortName, dtype, ('nCells',))
    variable.long_name = longName
    variable.valid_range = (vmin, vmax)
    if fillvalue != None:
        variable._fillvalue = fillvalue
    return variable

effmf   = createVariableForNetCDF("effmf", "model freeboard effective sample size", 
                        vmax = 29.88248, fillvalue = FILL_VALUE)
effof   = createVariableForNetCDF("effof", "observed freeboard effective sample size", 
                        vmax = 22321.38, vmin = 0.2787585, fillvalue = FILL_VALUE)
meanmf  = createVariableForNetCDF("meanmf", "model freeboard mean", 
                        vmax = 0.9041953, vmin = 0.01583931, fillvalue = FILL_VALUE)
meanof  = createVariableForNetCDF("meanof", "observed freeboard mean", 
                        vmax = 1.14699, vmin = 0.1046828, fillvalue = FILL_VALUE)
samplemf = createVariableForNetCDF("samplemf", "model freeboard sample count", 
                        vmax = 296)
sampleof = createVariableForNetCDF("sampleof", "observed freeboard sample count", 
                        vmax = 46893)
stdmf   = createVariableForNetCDF("stdmf", "model freeboard standard deviation", 
                        vmax = 0.2506092, vmin = 0.005416268, fillvalue = FILL_VALUE)
stdof   = createVariableForNetCDF("stdof", "observed freeboard standard deviation", 
                        vmax = 0.9629242, vmin = 0.01656876, fillvalue = FILL_VALUE)

################
# READ IN DATA #
################

satelliteFileName   = r"\satellite_data_preprocessed\one_day\icesat_E3SM_spring_2008_02_22_16.nc"
satelliteData       = loadData(runDir, satelliteFileName)
freeBoardReadings   = reduceToOneDay(satelliteData, keyVariableToPlot="freeboard")
cellIndicesForAllSamples      = reduceToOneDay(satelliteData, "modcell")
cellIndicesForAllObservations = returnCellIndices(satelliteData)

print("Shape of freeBoardReadings:             ", freeBoardReadings.shape)
print("Shape of cellIndicesForAllSamples:      ", cellIndicesForAllSamples.shape)
print("Shape of cellIndicesForAllObservations: ", cellIndicesForAllObservations.shape)

############################
# SATELLITE-ONLY VARIABLES #
############################
# These variables are easy to pull directly from the satellite data.

# Sample model freeboard is the # of times that cell was passed over 
# (ex. once in a day) in the full time
samplemf[:] = np.bincount(cellIndicesForAllSamples) # Collect one count of the satellite passing overhead.

# Sample observation freeboard is the # of photon reads per cell over full time
sampleof[:] = np.bincount(cellIndicesForAllObservations) # Collect all photon counts into bins using cell indices.

# Observed freeboard mean is the sum of all photon readings 
# in that cell over all time / sampleof
meanof[:] = np.full(meanof.shape, FILL_VALUE)
for cellIndex in range(CELLCOUNT):
    # Find all the indices that contain freeboard data
    freeBoardIndices = np.where(cellIndicesForAllObservations == cellIndex)[0]
    if len(freeBoardIndices) > 0:
        meanValue = np.mean(freeBoardReadings[freeBoardIndices])
        meanof[cellIndex] = meanValue 

# Observed freeboard mean is the sum of all photon readings 
# in that cell over all time / sampleof
stdof[:] = np.full(stdof.shape, FILL_VALUE)
for cellIndex in range(CELLCOUNT):
    # Find all the indices that contain freeboard data
    freeBoardIndices = np.where(cellIndicesForAllObservations == cellIndex)[0]
    if len(freeBoardIndices) > 0:
        standardDeviation = np.std(freeBoardReadings[freeBoardIndices])
        stdof[cellIndex] = standardDeviation 

###################
# MODEL VARIABLES #
###################

modelDailyDataFile  = r"\output_files\Breanna_D_test_1x05_days.mpassi.hist.am.timeSeriesStatsDaily.0001-01-01.nc"
modelData           = loadData(runDir, modelDailyDataFile)
snowVolumeCells     = reduceToOneDay(modelData, keyVariableToPlot="timeDaily_avg_snowVolumeCell") 
iceVolumeCells      = reduceToOneDay(modelData, keyVariableToPlot="timeDaily_avg_iceVolumeCell")
iceAreaCells        = reduceToOneDay(modelData, keyVariableToPlot="timeDaily_avg_iceAreaCell")

print(snowVolumeCells.shape)
print(iceVolumeCells.shape)
print(iceAreaCells.shape)

# TODO: Future work could be to add the Freeboard variable to E3SM's variables

def getFreeboard(heightIce, heightWater, heightSnow):
    """Formula to calculate freeboard: hf = hi (pw-pi)/pw + hs (pw-ps)/pw.
    Where p means density; h is height, w is water, i is ice, s is snow"""
    return heightIce*(DENSITY_WATER-DENSITY_ICE)/DENSITY_WATER + heightSnow*(DENSITY_WATER-DENSITY_SNOW)/DENSITY_WATER

def getThickness(volume, area):
    """ volume / area of cell = height (thickness) """
    return volume / area
# Model freeboard mean is 

iceHeightCells  = getThickness(iceVolumeCells, iceAreaCells)
snowHeightCells = getThickness(snowVolumeCells, iceAreaCells)
print("Ice Height Cells",  iceHeightCells.shape)
print("Snow Height Cells", snowHeightCells.shape)

# height ice + height snow = height water + height of freeboard
# freeboard = ice thickness + snow height - water height (which is 0?)

# Read data back from variable, print min and max
print("===== SATELLITE VARIABLES ======")
print("Samplemf Min/Max values:", samplemf[:].min(), samplemf[:].max())
print("Sampleof Min/Max values:", sampleof[:].min(), sampleof[:].max())
print("Meanof   Min/Max values:", meanof[:].min(),   meanof[:].max())
print("Stdof    Min/Max values:", stdof[:].min(),    stdof[:].max())
print("\n=====   MODEL VARIABLES   ======")

# close the Dataset
ncfile.close()
print('Dataset is closed!')