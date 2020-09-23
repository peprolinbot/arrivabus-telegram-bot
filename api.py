import requests
import json
from datetime import datetime


def makeGetRequest(url):
    headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36'}
    r = requests.get(url , headers=headers)
    if r.status_code == 200:
        return r.json()
    else:
        print("There was an error: Code " + str(r.status_code))

def getStops():
    url = "https://arriva.gal/plataforma/api/Paradas/lists/buscador.json"
    json = makeGetRequest(url)
    data = json['paradas']
    return data

def getStopsForOriginStopId(id):
    url = "https://arriva.gal/plataforma/api/paradas/listPorParadaOrigen/" + str(id) + "/buscador.json"
    json = makeGetRequest(url)
    return json

def nameToStopId(name):
    stops = getStops()
    for stop in stops:
        if stop['nombre'] == name or stop['nom_web'] == name:
            id = stop['parada']
            return id
    raise Exception("Stop not found: " + name)

def stopIdToName(id, nameType="nombre"):
    allowedNameTypes = ["nombre", "nom_web"] #List of allowed values for nameType argument

    if not nameType in allowedNameTypes:
        raise Exception("Invalid nameType: " + nameType)
    stops = getStops()
    for stop in stops:
        if stop['parada'] == id:
            name = stop[nameType]
            return name
    raise Exception("Stop not found: " + str(id))

def getStop(id):
    stops = getStops()
    for stop in stops:
        if stop['parada'] == id:
            return stop
    raise Exception("Stop not found: " + str(id))

def checkStop(id):
    stops = getStops()
    for stop in stops:
        if stop['parada'] == id:
            return stop
    return False

def checkStopByName(name):
    stops = getStops()
    for stop in stops:
        if stop['nombre'] == name or stop['nom_web'] == name:
            return stop
    return False

def getExpeditions(originStopId, destStopId, date = datetime.today()):
    date = "-".join([str(date.day), str(date.month), str(date.year)])
    url = "https://arriva.gal/plataforma/api/buscador/getExpedicionesPorOrigenYDestino/" + str(originStopId) + "/" + str(destStopId) + "/" + date + ".json"
    json = makeGetRequest(url)
    expeditions = json["expediciones"]
    if expeditions["ida"] == [] and expeditions["vuelta"] == []:
        return None
    return json["expediciones"]
