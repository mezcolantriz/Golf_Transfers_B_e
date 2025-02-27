from flask import Flask, request, jsonify
import json
import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv  # 📌 Cargar variables de entorno desde .env

# 📌 Cargar archivo .env
load_dotenv()

app = Flask(__name__)

# 📌 Configuración de OpenRouteService
ORS_API_KEY = os.getenv("ORS_API_KEY")
ORS_URL = "https://api.openrouteservice.org/v2/matrix/driving-car"

# 📌 Cargar coordenadas desde archivo JSON
def cargar_coordenadas():
    archivo = "data/locations.json"
    if not os.path.exists(archivo):
        print(f"❌ ERROR: No se encontró el archivo {archivo}. Verifica la ruta.")
        return {}

    try:
        with open(archivo, "r", encoding="utf-8") as file:
            datos = json.load(file)
            print("📌 Coordenadas cargadas correctamente:", datos)
            return datos
    except Exception as e:
        print(f"❌ ERROR al leer {archivo}: {str(e)}")
        return {}

# 📌 Cargar las coordenadas de los destinos
coordenadas = cargar_coordenadas()

# 📌 Función para obtener tiempo de viaje en tráfico real
def obtener_tiempo_real(origen, destino):
    if not ORS_API_KEY:
        print("❌ ERROR: API Key no configurada en .env")
        return "Error: API Key no configurada"
    
    if origen not in coordenadas or destino not in coordenadas:
        print(f"❌ ERROR: No hay coordenadas para {origen} o {destino}")
        return "No disponible"

    data = {
        "locations": [
            [coordenadas[origen]["lng"], coordenadas[origen]["lat"]],
            [coordenadas[destino]["lng"], coordenadas[destino]["lat"]]
        ],
        "metrics": ["duration"]
    }

    try:
        print(f"📡 Enviando petición a OpenRouteService: {data}")
        headers = {"Authorization": f"Bearer {ORS_API_KEY}", "Content-Type": "application/json"}
        response = requests.post(ORS_URL, json=data, headers=headers)

        print(f"📡 Respuesta de OpenRouteService: {response.status_code}, {response.text}")

        if response.status_code == 200:
            tiempo_segundos = response.json()["durations"][0][1]
            return round(tiempo_segundos / 60)  # Convertir a minutos
        else:
            return "No disponible"
    except Exception as e:
        print(f"❌ ERROR al obtener tiempo de OpenRouteService: {str(e)}")
        return "No disponible"

# 📌 Función para calcular tiempo de espera en el campo de golf
def calcular_tiempo_espera(numero_pax):
    base_espera = timedelta(hours=5, minutes=15)  # Partida estándar dura 5h 15min
    bloques_adicionales = (numero_pax - 1) // 4  # Cada 4 jugadores, +10 min
    tiempo_adicional = timedelta(minutes=10 * bloques_adicionales)
    return base_espera + tiempo_adicional

# 📌 Función para calcular tiempos según si es un **tee time** o **vuelo**
def calcular_transferencia(data):
    origen = data.get("origen")
    destino = data.get("destino")
    fecha = data.get("fecha")

    # 📌 Si es un TEE TIME (Golf)
    if "tee_time" in data:
        tee_time = data.get("tee_time")
        numero_pax = int(data.get("numero_pax", 4))

        # 📌 Obtener tiempo de transporte real
        tiempo_transporte = obtener_tiempo_real(origen, destino)
        if tiempo_transporte == "No disponible":
            return jsonify({"error": "No se pudo calcular el tiempo de transporte"}), 400

        # 📌 Calcular la hora de salida
        hora_tee_time = datetime.strptime(tee_time, "%H:%M")
        tiempo_transporte_total = tiempo_transporte + 60  # Sumar 1 hora extra
        hora_salida = hora_tee_time - timedelta(minutes=tiempo_transporte_total)

        # 📌 Calcular la hora de regreso
        tiempo_espera = calcular_tiempo_espera(numero_pax)
        hora_regreso = hora_tee_time + tiempo_espera

        return jsonify({
            "fecha": fecha,
            "salida": hora_salida.strftime("%H:%M"),
            "destino": destino,
            "regreso": hora_regreso.strftime("%H:%M"),
            "pasajeros": numero_pax,
            "tiempo_transporte_min": tiempo_transporte
        })

    # 📌 Si es un VUELO
    elif "hora_vuelo" in data:
        hora_vuelo = datetime.strptime(data.get("hora_vuelo"), "%H:%M")

        # 📌 Obtener tiempo de transporte real
        tiempo_transporte = obtener_tiempo_real(origen, destino)
        if tiempo_transporte == "No disponible":
            return jsonify({"error": "No se pudo calcular el tiempo de transporte"}), 400

        # 📌 Si el DESTINO es un aeropuerto (DEPARTURE)
        if destino in ["Alicante Airport", "Murcia Airport"]:
            tiempo_total = tiempo_transporte + 120  # Sumar 2h para llegar con margen
            hora_salida = hora_vuelo - timedelta(minutes=tiempo_total)
            return jsonify({
                "fecha": fecha,
                "salida": hora_salida.strftime("%H:%M"),
                "destino": destino,
                "hora_vuelo": data.get("hora_vuelo"),
                "tipo": "Vuelo de salida",
                "tiempo_transporte_min": tiempo_transporte
            })

        # 📌 Si el ORIGEN es un aeropuerto (ARRIVAL)
        elif origen in ["Alicante Airport", "Murcia Airport"]:
            return jsonify({
                "fecha": fecha,
                "llegada_vuelo": data.get("hora_vuelo"),
                "origen": origen,
                "destino": destino,
                "tipo": "Vuelo de llegada"
            })

    # 📌 Si no es un tee time ni un vuelo, hay un error
    return jsonify({"error": "Datos incorrectos"}), 400

@app.route("/", methods=["GET"])
def home():
    return jsonify({"mensaje": "Bienvenido a Transport Time Calculator API"})

# 📌 Endpoint para calcular transferencia
@app.route("/locations", methods=["GET"])
def get_locations():
    return jsonify({"ubicaciones": list(coordenadas.keys())})

@app.route("/calcular", methods=["POST"])
def calcular():
    data = request.json
    return calcular_transferencia(data)


# 📌 Iniciar Flask
if __name__ == "__main__":
    app.run(debug=True)
