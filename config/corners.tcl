# MMMC corner infrastructure. Real PVT library files must be supplied by the PDK.
set CORNERS [dict create \
    SS [dict create purpose setup lib "" rc "max"] \
    TT [dict create purpose nominal lib "" rc "typ"] \
    FF [dict create purpose hold lib "" rc "min"]]
