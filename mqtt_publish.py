import paho.mqtt.client as mqtt #import the client1
import time

broker_address="192.168.1.3"
username = "mqttuser"
password = "mqttpass"

############
def on_message(client, userdata, message):
    print("message received " ,str(message.payload.decode("utf-8")))
    print("message topic=",message.topic)
    print("message qos=",message.qos)
    print("message retain flag=",message.retain)
    
def on_log(client, userdata, level, buf):
    print("log: ",buf)
########################################
#broker_address="iot.eclipse.org"
print("creating new instance")
client = mqtt.Client("P1") #create new instance
client.on_message=on_message #attach function to callback
client.username_pw_set(username=username,password=password)
print("connecting to broker")
client.connect(broker_address) #connect to broker
client.loop_start() #start the loop
print("Subscribing to topic","house/weather/outsidetemp")
client.subscribe("house/weather/outsidetemp")
print("Publishing message to topic","house/weather/outsidetemp")
client.publish("house/weather/outsidetemp","27")
client.on_log=on_log
time.sleep(4) # wait
client.loop_stop() #stop the loop
