from qgis.core import (
    QgsProject,
    QgsRectangle,
    QgsPointXY,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsApplication,
    QgsRasterLayer

)
import os
import sys
import math
import requests

from qgis.analysis import QgsNativeAlgorithms

from qgis import processing

QGIS_PREFIX = "/usr"
sys.path.append(os.path.join(QGIS_PREFIX, "share/qgis/python"))
sys.path.append(os.path.join(QGIS_PREFIX, "share/qgis/python/plugins"))

from processing.core.Processing import Processing



DEM_TYPE = "AW3D30" 
  
radius_fly_m = 5000
API_KEY       = ""
out_dir       = "/tmp"
url = "https://portal.opentopography.org/API/globaldem"

os.makedirs(out_dir, exist_ok=True)

dem_tif  = f"{out_dir}/alos_dem.tif"
clip_tif      = f"{out_dir}/clip_dem.tif"
mask_tif      = f"{out_dir}/mask_dem.tif"
output_png    = f"{out_dir}/dem_filtered.png"


# Supply the path to the qgis install location
QgsApplication.setPrefixPath(QGIS_PREFIX, True)
qgs = QgsApplication([], False)

# load providers
qgs.initQgis()

Processing.initialize()
QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())

while True:
    try:
        print('Введите количество используемых дронов от 1 до 15: ')
        count_drones = int(input())
        if 1<= count_drones <= 15:
            break
        else:
            print('Ошибка, число не входит в диапазон.')
    except ValueError:
        print("Ошибка: введите целое число.")

while True:
    try:
        print('Введите минимальную и максимальную высоту полета над уровнем моря через пробел: ')
        min_altitude, max_altitude = map(float, input().split())
        if min_altitude<max_altitude:
            break
        else:
            print('Ошибка, максимальная высота меньше минимальной.')
    except ValueError:
        print('Ошибка: введите два числа через пробел.')

coordinates = []

for i in range(count_drones):
    while True:
        try:
            print(f'Введите координаты дрона {i+1} по  долготе и  широте через пробел: ')
            lon, lat = map(float, input().split())
            step_altitude = (max_altitude-min_altitude)/count_drones
            if -90 <= lat <= 90 and -180 <= lon <= 180 and step_altitude>=1:
                coordinates.append([lon, lat])
                break
            else:
                print('Ошибка, широта или долгота имеют не возможные значения')
        except ValueError:
            print("Ошибка: введите два числа через пробел.")



for drone_num in range(count_drones):

    lon, lat = coordinates[drone_num]

    #1° lat ≈ 111 000 m
    dlat = radius_fly_m / 111000.0
    # 1° lon ≈ 111 000·cos(lat) m
    dlon = radius_fly_m / (111000.0 * math.cos(math.radians(lat)))

    west, east = lon - dlon, lon + dlon
    south, north= lat - dlat, lat + dlat

    params = {
    "demtype": DEM_TYPE,
    "west":    west,
    "east":    east,
    "south":   south,
    "north":   north,
    "outputFormat": "GTiff",
    "API_Key": API_KEY
    }
    print("Запрашиваем DEM у OpenTopography...", file=sys.stderr)
    r = requests.get(url, params=params, stream=True)
    r.raise_for_status()

    with open(dem_tif, "wb") as f:
        for chunk in r.iter_content(1024*1024):
            f.write(chunk)

    print(f"→ Сохранено {dem_tif}", file=sys.stderr)

    dem_layer = QgsRasterLayer(dem_tif, "alos_dem")
    if not dem_layer.isValid():
        print("Ошибка: DEM слой не загрузился!")
        continue
    #clip square 
    
    crs_src = dem_layer.crs()                         
    crs_m   = QgsCoordinateReferenceSystem("EPSG:3857")
    xform   = QgsCoordinateTransform(crs_src, crs_m, QgsProject.instance())
    pt_m    = xform.transform(QgsPointXY(lon, lat))

    
    rect_m = QgsRectangle(
        pt_m.x() - radius_fly_m,
        pt_m.y() - radius_fly_m,
        pt_m.x() + radius_fly_m,
        pt_m.y() + radius_fly_m
    )

    processing.run(
        "gdal:cliprasterbyextent",
        {
            'INPUT':    dem_layer,
            'PROJWIN':  rect_m,
            'NODATA':   -9999,
            'OUTPUT':   clip_tif
        }
    )

    #filter
    processing.run(
        "gdal:rastercalculator",
        {
            'INPUT_A': clip_tif,
            'BAND_A': 1,
            'FORMULA': f"(A>={min_altitude+drone_num*step_altitude})",
            'NO_DATA': 0,
            'RTYPE':   5,        # Float32
            'OUTPUT':  mask_tif
        }
    )


    processing.run(
        "gdal:translate",
        {
            'INPUT': mask_tif,
            'BANDS': [1],
            'OUTPUT': output_png
        }
    )

    print(" Готово! Итоговое изображение:", output_png)






# Write your code here to load some layers, use processing
# algorithms, etc.

# Finally, exitQgis() is called to remove the
# provider and layer registries from memory
qgs.exitQgis()