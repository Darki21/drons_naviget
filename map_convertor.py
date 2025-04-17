from qgis.core import *

# Supply the path to the qgis install location
QgsApplication.setPrefixPath("/usr", True)
qgs = QgsApplication([], False)

# load providers
qgs.initQgis()

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
        print('Введите минимальную и максимальную высоту полета над урвнем моря через пробел: ')
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
            print('Введите координты дрона {i+1} по широте и долготе через пробел: ')
            lat, lon = map(float, input().split())
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                break
            else:
                print('Ошибка, широта или долгота имеют не возможные значения')
        except ValueError:
            print("Ошибка: введите целое число.")










# Write your code here to load some layers, use processing
# algorithms, etc.

# Finally, exitQgis() is called to remove the
# provider and layer registries from memory
qgs.exitQgis()