from qgis.core import (
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
  
radius_fly_m = 5500
API_KEY       = ""
out_dir       = "/tmp"
url = "https://portal.opentopography.org/API/globaldem"

os.makedirs(out_dir, exist_ok=True)




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
            if -90 <= lat <= 90 and -180 <= lon <= 180 and step_altitude>=2:
                coordinates.append([lon, lat])
                break
            else:
                print('Ошибка, широта или долгота имеют не возможные значения  или шаг высоты меньше 2 метров')
        except ValueError:
            print("Ошибка: введите два числа через пробел.")


for drone_num in range(count_drones):

    dem_tif  = f"{out_dir}/alos_dem_drone_num_{drone_num}.tif"
    mask_tif      = f"{out_dir}/mask_dem_drone_num_{drone_num}.tif"
    output_png    = f"{out_dir}/dem_filtered_drone_num_{drone_num}.png"



    lon, lat = coordinates[drone_num]

    #1° lat ≈ 111 000 m
    dlat = radius_fly_m / 111320.0
    # 1° lon ≈ 111 000·cos(lat) m
    dlon = radius_fly_m / (111320.0 * math.cos(math.radians(lat)))

    west, east = lon - dlon, lon + dlon
    south, north= lat - dlat, lat + dlat

    print("Размер области (°):", east - west, "x", north - south)

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
    print("Размер области (°):", east - west, "x", north - south)

    print(f"Сохранено {dem_tif}", file=sys.stderr)

    dem_layer = QgsRasterLayer(dem_tif, "alos_dem")

    if not dem_layer.isValid():
        print("Ошибка: DEM слой не загрузился!")
        continue
    
    #filter
    try:
        processing.run(
            "gdal:rastercalculator",
            {
                'INPUT_A': dem_tif,
                'BAND_A': 1,
                'FORMULA': f"(A>={min_altitude+drone_num*step_altitude})*0+(A<{min_altitude+drone_num*step_altitude})*255",
                'NO_DATA': None,
                'RTYPE':   1,        # byte
                'OUTPUT':  mask_tif
            }
        )
        print("Raster calculator успешно выполнен.")
    except Exception as e:
        print(f"Ошибка выполнения raster calculator: {e}")

    # Определяем UTM-зону (северное или южное полушарие)
    utm_zone = int((lon + 180) / 6) + 1
    utm_epsg = 32600 + utm_zone if lat >= 0 else 32700 + utm_zone
    utm_crs = f"EPSG:{utm_epsg}"

    projected_tif = f"{out_dir}/projected_mask_{drone_num}.tif"
    projected_dem_tif = f"{out_dir}/projected_dem_{drone_num}.tif"

    # Перепроецируем в UTM
    processing.run(
        "gdal:warpreproject",
        {
            'INPUT': dem_tif,
            'SOURCE_CRS': dem_layer.crs().authid(),
            'TARGET_CRS': utm_crs,
            'RESAMPLING': 0,  # Nearest neighbor
            'OUTPUT': projected_dem_tif
        }
    )
    processing.run(
        "gdal:warpreproject",
        {
            'INPUT': mask_tif,
            'SOURCE_CRS': dem_layer.crs().authid(),
            'TARGET_CRS': utm_crs,
            'RESAMPLING': 0,  # Nearest neighbor
            'OUTPUT': projected_tif
        }
    )

    # Читаем размеры перепроецированного растра
    projected_layer = QgsRasterLayer(projected_tif, "utm_projected")
    extent = projected_layer.extent()
    width_m = extent.width()
    height_m = extent.height()
    side = int(max(width_m, height_m) // 10)  # 1 пиксель = 10 метров (можно изменить масштаб)

    output_png = f"{out_dir}/dem_filtered_drone_num_{drone_num}.png"

    # Преобразуем в квадратный PNG
    processing.run(
        "gdal:translate",
        {
            'INPUT': projected_tif,
            'TARGET_SIZE': [side, side],
            'FORMAT': 'PNG',
            'OUTPUT': output_png
        }
    )



qgs.exitQgis()