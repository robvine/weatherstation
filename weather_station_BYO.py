#! /usr/bin/python3

from gpiozero import Button
import time
import math
import bme280_sensor
import wind_direction_byo
import statistics
import database
from datetime import datetime
from datetime import date
import requests
import paho.mqtt.client as mqtt
import board
import busio
import adafruit_veml6075

wind_count = 0
radius_cm = 9.0
wind_interval = 10
CM_IN_A_KM = 100000.0
SECS_IN_AN_HOUR = 3600
ADJUSTMENT = 1.18
store_speeds = []
store_directions = []
db_interval = 300
BUCKET_SIZE = 0.2794
rain_count = 0
daily_rain_count = 0
hasl = 743
sl_pressure = []
today = date.today()
broker_address="192.168.1.3"
username = "mqttuser"
password = "mqttpass"

# create a string to hold the first part of the URL
WUurl = "https://weatherstation.wunderground.com/weatherstation\
/updateweatherstation.php?"
WU_station_id = "IGOOGO13" # Replace XXXX with your PWS ID
WU_station_pwd = "KotgSBbz" # Replace YYYY with your Password
WUcreds = "ID=" + WU_station_id + "&PASSWORD="+ WU_station_pwd
date_str = "&dateutc=now"
action_str = "&action=updateraw"

#UV Sensor Configuration
i2c = busio.I2C(board.SCL, board.SDA)
veml = adafruit_veml6075.VEML6075(i2c, integration_time=100)

#Every half-rotation, add 1 to count
def spin():
    global wind_count
    wind_count = wind_count + 1
    #print("spin" + str(wind_count))
    
def reset_wind():
    global wind_count
    wind_count = 0
    
#Calculate the wind speed
def calculate_speed(time_sec):
    global wind_count
    circumference_cm = (2 * math.pi) * radius_cm
    rotations = wind_count / 2.0
        
    dist_km = (circumference_cm * rotations) / CM_IN_A_KM
        
    km_per_sec = dist_km / time_sec
    km_per_hour = km_per_sec * SECS_IN_AN_HOUR
        
    return km_per_hour * ADJUSTMENT
    
wind_speed_sensor = Button(5)
wind_speed_sensor.when_pressed = spin

def bucket_tipped():
    global rain_count
    global daily_rain_count
    rain_count = rain_count + 1
    daily_rain_count = daily_rain_count + 1
    print (rain_count * BUCKET_SIZE)
    print (daily_rain_count * BUCKET_SIZE)

def reset_rainfall():
    global rain_count
    rain_count = 0
    
def reset_daily_rainfall():
    global daily_rain_count
    daily_rain_count = 0
    
def hpa_to_inches(pressure_in_hpa):
    pressure_in_inches_of_m = pressure_in_hpa * 0.02953
    return pressure_in_inches_of_m

def mm_to_inches(rainfall_in_mm):
    rainfall_in_inches = rainfall_in_mm * 0.0393701
    return rainfall_in_inches

def degc_to_degf(temperature_in_c):
    temperature_in_f = (temperature_in_c * (9/5.0)) + 32
    return temperature_in_f

def kmh_to_mph(speed_in_kmh):
    speed_in_mph = speed_in_kmh * 0.621371
    return speed_in_mph

def dew_point():
    A = 17.27
    B = 237.7
    alpha = ((A * ambient_temp) / (B + ambient_temp)) + math.log(humidity/100.0)
    dew_calc = (B * alpha) / (A - alpha)
    return dew_calc

rain_sensor = Button(6)
rain_sensor.when_pressed = bucket_tipped

db = database.weather_database()

def on_message(client, userdata, message):
    print("message received " ,str(message.payload.decode("utf-8")))
    print("message topic=",message.topic)
    print("message qos=",message.qos)
    print("message retain flag=",message.retain)
    
def on_log(client, userdata, level, buf):
    print("log: ",buf)

#Loop to measure wind speed and report at 5-second intervals   

while True:
    start_time = time.time()
    print("Collecting data")
    while time.time() - start_time <= db_interval:
        wind_start_time = time.time()
        reset_wind()
        #time.sleep(wind_interval)
        while time.time() - wind_start_time <= wind_interval:
            store_directions.append(wind_direction_byo.get_value())
            
        final_speed = calculate_speed(wind_interval)
        store_speeds.append(final_speed)
    wind_average = wind_direction_byo.get_average(store_directions)
        
    wind_gust = max(store_speeds)
    wind_speed = statistics.mean(store_speeds)
    rainfall = rain_count * BUCKET_SIZE
    daily_rainfall = daily_rain_count * BUCKET_SIZE
    
    humidity, pressure, ambient_temp = bme280_sensor.read_all()
    sl_pressure = pressure + ((pressure * 9.80665 * hasl)/(287 * (273 + ambient_temp + (hasl/400))))
    dew_point_c = dew_point()
    now = datetime.now()

    print("Wind Speed:",wind_speed)
    print("Wind Gust:",wind_gust)
    print("Wind Average:",wind_average)
    print("Humidity:",humidity)
    print("Pressure:",sl_pressure)
    print("Ambient Temp:",ambient_temp)
    print("Dew Point:",dew_point_c)
    print("Rainfall:",rainfall)
    print("Daily Rainfall:",daily_rainfall)
    print("Time:",now)
    print("UV Index:",veml.uv_index)
    print("UV A:",veml.uva)
    print("UV B:",veml.uvb)
    db.insert(ambient_temp, 0, 0, sl_pressure, humidity, wind_average, wind_speed, wind_gust, rainfall, now)
    
    #Formatting for WU
    ambient_temp_str = "{0:.2f}".format(degc_to_degf(ambient_temp))
    dew_point_str = "{0:.2f}".format(degc_to_degf(dew_point_c))
    humidity_str = "{0:.2f}".format(humidity)
    sl_pressure_in_str = "{0:.2f}".format(hpa_to_inches(sl_pressure))
    wind_speed_mph_str = "{0:.2f}".format(kmh_to_mph(wind_speed))
    wind_gust_mph_str = "{0:.2f}".format(kmh_to_mph(wind_gust))
    wind_average_str = str(wind_average)
    rainfall_in_str = "{0:.2f}".format(mm_to_inches(rainfall))
    daily_rainfall_in_str = "{0:.2f}".format(mm_to_inches(daily_rainfall))
    uv_index_str = "{0:.2f}".format(veml.uv_index)

    #Send to WU
    r= requests.get(
    WUurl +
    WUcreds +
    date_str +
    "&humidity=" + humidity_str +
    "&baromin=" + sl_pressure_in_str +
    "&windspeedmph=" + wind_speed_mph_str +
    "&windgustmph=" + wind_gust_mph_str +
    "&tempf=" + ambient_temp_str +
    "&dewptf=" + dew_point_str +
    "&rainin=" + rainfall_in_str +
    "&dailyrainin=" + daily_rainfall_in_str +
    "&winddir=" + wind_average_str +
    "&UV=" + uv_index_str +
    action_str)
    print("Weather Underground Upload " + str(r.text))
    
    #Print the web address
    #print(WUurl +
    #WUcreds +
    #date_str +
    #"&humidity=" + humidity_str +
    #"&baromin=" + sl_pressure_in_str +
    #"&windspeedmph=" + wind_speed_mph_str +
    #"&windgustmph=" + wind_gust_mph_str +
    #"&tempf=" + ambient_temp_str +
    #"&dewptf=" + dew_point_str +
    #"&rainin=" + rainfall_in_str +
    #"&dailyrainin=" + daily_rainfall_in_str +
    #"&winddir=" + wind_average_str +
    #action_str)
    
    #Send to Home Assistant
    client = mqtt.Client("P1") #create new instance
    client.on_message=on_message #attach function to callback
    client.username_pw_set(username=username,password=password)
    client.connect(broker_address) #connect to broker
    client.loop_start() #start the loop
    client.subscribe("house/weather/wind_speed")
    client.subscribe("house/weather/wind_gust")
    client.subscribe("house/weather/wind_average")
    client.subscribe("house/weather/humidity")
    client.subscribe("house/weather/sl_pressure")
    client.subscribe("house/weather/ambient_temp")
    client.subscribe("house/weather/dew_point_c")
    client.subscribe("house/weather/rainfall")
    client.subscribe("house/weather/daily_rainfall")
    client.subscribe("house/weather/uv_index")
    client.subscribe("house/weather/uv_a")
    client.subscribe("house/weather/uv_b")
    client.publish("house/weather/wind_speed",('{:.2f}'.format(wind_speed)))
    client.publish("house/weather/wind_gust",('{:.2f}'.format(wind_gust)))
    client.publish("house/weather/wind_average",('{:.2f}'.format(wind_average)))
    client.publish("house/weather/humidity",('{:.2f}'.format(humidity)))
    client.publish("house/weather/sl_pressure",('{:.2f}'.format(sl_pressure)))
    client.publish("house/weather/ambient_temp",('{:.2f}'.format(ambient_temp)))
    client.publish("house/weather/dew_point_c",('{:.2f}'.format(dew_point_c)))
    client.publish("house/weather/rainfall",('{:.2f}'.format(rainfall)))
    client.publish("house/weather/daily_rainfall",('{:.2f}'.format(daily_rainfall)))
    client.publish("house/weather/uv_index",('{:.2f}'.format(veml.uv_index)))
    client.publish("house/weather/uv_a",('{:.2f}'.format(veml.uva)))
    client.publish("house/weather/uv_b",('{:.2f}'.format(veml.uvb)))
    client.on_log=on_log
    #time.sleep(4) # wait
    client.loop_stop() #stop the loop
    
    store_speeds = []
    store_directions = []
    
    reset_rainfall()
    if today != date.today():
        print ("Resetting")
        reset_daily_rainfall()
        today = date.today()
    
    
#wind_count = 0
#    time.sleep(wind_interval)
#    print( calculate_speed(wind_interval), "km/h")




