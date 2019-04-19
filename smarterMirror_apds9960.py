#!/usr/bin/python
# -*- coding: cp1252 -*-

# A smarter mirror
#
# RUN: python smarterMirror_apds9960.py
# 
# fetch weather data from OWM
# construct HTML page(s)
# display HTML page in browser
# read sensor to activate / automatically deactivate HDMI display
# display No WiFi page in case of errors
# display browser in full-display mode

import sys
reload(sys)
sys.setdefaultencoding('utf-8')

import datetime
from datetime import timedelta
import time
import dateutil.parser

import pyowm
import json
import pprint

import socket  # for WiFi check
import subprocess

import webbrowser   # for HTML page display

import requests

import signal
from threading import Thread

import os
os.environ['DISPLAY'] = ":0"

import rpi_backlight as bl # screen dim functionality

# start apds9960 config
from apds9960.const import *
from apds9960 import APDS9960
import RPi.GPIO as GPIO
import smbus
from time import sleep

port = 1
bus = smbus.SMBus(port)

apds = APDS9960(bus)

def interuptHandlerAPDS9960(channel):
  print("INTERRUPT APDS9960")

GPIO.setmode(GPIO.BOARD)
GPIO.setup(7, GPIO.IN)
# end apds9960 config


########################CONFIG############################
OWM_APYKEY='theowmapikey'
OWM_ID = theowmid

REMOTE_SERVER = "www.google.com"  # for WiFi check

fileNameSmartMirrorMain='/home/pi/smartmirror/pages/smartMirrorMain.html'
fileNameSmartMirrorNoWiFi='/home/pi/smartmirror/pages/smartMirrorNoWiFi.html'
######################END#CONFIG##########################

flags = None
pageIndex = 0


class SmartMirror():

  _temperature = 0
  _humidity = 0
  _pressure = 0
  _rain = 0.0
  _weatherCode = 0
  _sunrise = ""
  _sunset = ""

  def run(self):
    print( "A SMARTER MIRROR")
    self._wifi = self.is_connected()

  def is_connected(self):
    try:
      # see if we can resolve the host name -- tells us if there is
      # a DNS listening
      host = socket.gethostbyname(REMOTE_SERVER)
      # connect to the host -- tells us if the host is actually
      # reachable
      s = socket.create_connection((host, 80), 2)
      return True
    except:
      pass
    return False

  def clock(self):
    t = time.strftime("%H:%M")
    #print(str(t))
    return t

  def getWeatherFromOWM(self, summer):
    try:
      owm = pyowm.OWM(OWM_APYKEY, version='2.5')
      # Search for current weather
      print( "Weather @ID")
      obs = owm.weather_at_id(OWM_ID)
      w1 = obs.get_weather()
      print(str( w1.get_status()))

      weatherCondition = 'fair' # 'good', 'fair, 'bad'

      # get general meaning for weather codes https://openweathermap.org/weather-conditions
      self._weatherCode = w1.get_weather_code()
      if self._weatherCode >= 200 and self._weatherCode < 300:
        print( "THUNDERSTORM")
        weatherCondition = 'bad'
      if self._weatherCode >= 300 and self._weatherCode < 400:
        print( "DRIZZLE")
        weatherCondition = 'bad'
      if self._weatherCode >= 500 and self._weatherCode < 600:
        print( "RAIN")
        weatherCondition = 'bad'
      if self._weatherCode >= 600 and self._weatherCode < 700:
        print( "SNOW")
        weatherCondition = 'bad'
      if self._weatherCode >= 700 and self._weatherCode < 800:
        print( "ATMOSPHERE")
        weatherCondition = 'fair'
      if self._weatherCode == 800:
        print( "CLEAR")
        weatherCondition = 'good'
      if self._weatherCode > 800 and self._weatherCode < 900:
        print( "CLOUDS")
        weatherCondition = 'fair'
      if self._weatherCode >= 900:
        print( "EXTREME")
        weatherCondition = 'bad'
        
      print( "Weather code: " + str(self._weatherCode))
      rain = w1.get_rain()
      if 'all' in rain:
        self._rain = rain['all']
      print( "Rain: " + str(self._rain) + ", " + str(rain))

      self._humidity = w1.get_humidity()
      self._pressure = w1.get_pressure()['press']
      print( "Humidity: " + str(self._humidity))
      print( "Pressure: " + str(self._pressure))
      
      #print( "Sunrise: " + w1.get_sunrise_time('iso'))
      #print( "Sunset: " + w1.get_sunset_time('iso'))

      # wintertime, summertime
      delta = 2
      if summer == True:
        delta=2
      else:
        delta = 1
      self._sunrise = dateutil.parser.parse(w1.get_sunrise_time('iso')) + timedelta(hours=delta)
      self._sunrise = self._sunrise.strftime("%H:%M")
      print( "Sunrise: " + self._sunrise)
      self._sunset = dateutil.parser.parse(w1.get_sunset_time('iso')) + timedelta(hours=delta)
      self._sunset = self._sunset.strftime("%H:%M")
      print( "Sunset: " + self._sunset)
      
      self._temperature = w1.get_temperature('celsius')['temp']
      print( "Temperature: " + str(self._temperature) + " °C")
      wCond = self.determineWeatherCondition()
      print( "Determined weather condition: " + str(wCond))
      return wCond
    except Exception as e:
      print( str(e))
    
  ''' example for OWM forecast
  { "weatherData": [{
      "date":"3.6.2016",
      "temperature":"20.3",
      "minTemperature":"15.85",
      "maxTemperature":"20.3",
      "rain":"14.21",
      "clouds":"2.37"
      ...
    },{
      "date":"4.6.2016",
      "temperature":"19.85",
      "minTemperature":"16.09",
      "maxTemperature":"20.62",
      "rain":"NaN",
      "clouds":"1.9"
      ...
    },{
      "date":"5.6.2016",
      "temperature":"22.34",
      "minTemperature":"16.21",
      "maxTemperature":"22.49",
      "rain":"NaN",
      "clouds":"2.91"
      ...
    }]}
  '''

  def determineWeatherCondition(self):
    # simple: judge weather on temperature
    weatherCondition = 'bad'
    if self._rain <= 50.0:
      if float(self._temperature)<=10.0:
        weatherCondition = 'bad'
      if float(self._temperature)>10.0 and float(self._temperature<20.0):
        weatherCondition = 'fair'
      if float(self._temperature)>=20.0 and float(self._temperature<35.0):
        weatherCondition = 'good'
      if float(self._temperature)>=35.0:
        weatherCondition = 'bad'
    else:
      weatherCondition = 'bad'
    return weatherCondition

  # translage weather icon code to icon (must exist in the same directory as the HTML page)
  def getWeatherIconHTMLCode(self, weatherCode, alignment):
    weather_icon_html = ""
    if weatherCode >= 200 and weatherCode < 300:
      print( "THUNDERSTORM")
      weather_icon_html = "<div align=\"" + alignment + "\"><img src=\"storm2_.png\" alt=\"storm\"></div>"
    if weatherCode >= 300 and weatherCode < 400:
      print( "DRIZZLE")
      weather_icon_html = "<div align=\"" + alignment + "\"><img src=\"rain_umbrella_.png\" alt=\"rain\"></div>"
    if weatherCode >= 500 and weatherCode < 600:
      print( "RAIN")
      weather_icon_html = "<div align=\"" + alignment + "\"><img src=\"rain_umbrella_.png\" alt=\"rain\"></div>"
    if weatherCode >= 600 and weatherCode < 700:
      print( "SNOW")
      weather_icon_html = "<div align=\"" + alignment + "\"><img src=\"ice_crystal_.png\" alt=\"snow\"></div>"
    if weatherCode >= 700 and weatherCode < 800:
      print( "ATMOSPHERE")
      weather_icon_html = "<div align=\"" + alignment + "\"><img src=\"cloud_sun_.png\" alt=\"atmosphere\"></div>"
    if weatherCode == 800:
      print( "CLEAR")
      weather_icon_html = "<div align=\"" + alignment + "\"><img src=\"sun_.png\" alt=\"sun\"></div>"
    if weatherCode > 800 and weatherCode < 900:
      print( "CLOUDS")
      weather_icon_html = "<div align=\"" + alignment + "\"><img src=\"cloud_.png\" alt=\"clouds\"></div>"
    if weatherCode >= 900:
      print( "EXTREME")
      weather_icon_html = "<div align=\"" + alignment + "\"><img src=\"storm2_.png\" alt=\"storm\"></div>"
    return weather_icon_html

  # translage weather icon code to icon (must exist in the same directory as the HTML page)
  def getWeatherIconHTMLCodeSmall(self, weatherCode, alignment):
    weather_icon_html = ""
    if weatherCode >= 200 and weatherCode < 300:
      print( "THUNDERSTORM")
      weather_icon_html = "<div align=\"" + alignment + "\"><img src=\"storm2_.png\" alt=\"storm\" width=\"100\" height=\"100\"></div>"
    if weatherCode >= 300 and weatherCode < 400:
      print( "DRIZZLE")
      weather_icon_html = "<div align=\"" + alignment + "\"><img src=\"rain_umbrella_.png\" alt=\"rain\" width=\"100\" height=\"100\"></div>"
    if weatherCode >= 500 and weatherCode < 600:
      print( "RAIN")
      weather_icon_html = "<div align=\"" + alignment + "\"><img src=\"rain_umbrella_.png\" alt=\"rain\" width=\"100\" height=\"100\"></div>"
    if weatherCode >= 600 and weatherCode < 700:
      print( "SNOW")
      weather_icon_html = "<div align=\"" + alignment + "\"><img src=\"ice_crystal_.png\" alt=\"snow\" width=\"100\" height=\"100\"></div>"
    if weatherCode >= 700 and weatherCode < 800:
      print( "ATMOSPHERE")
      weather_icon_html = "<div align=\"" + alignment + "\"><img src=\"cloud_sun_.png\" alt=\"atmosphere\" width=\"100\" height=\"100\"></div>"
    if weatherCode == 800:
      print( "CLEAR")
      weather_icon_html = "<div align=\"" + alignment + "\"><img src=\"sun_.png\" alt=\"sun\" width=\"100\" height=\"100\"></div>"
    if weatherCode > 800 and weatherCode < 900:
      print( "CLOUDS")
      weather_icon_html = "<div align=\"" + alignment + "\"><img src=\"cloud_.png\" alt=\"clouds\" width=\"100\" height=\"100\"></div>"
    if weatherCode >= 900:
      print( "EXTREME")
      weather_icon_html = "<div align=\"" + alignment + "\"><img src=\"storm2_.png\" alt=\"storm\" width=\"100\" height=\"100\"></div>"
    return weather_icon_html

  # HTML pages
  def createNoWiFiHTMLpage(self):
    try:
      f = open(fileNameSmartMirrorNoWiFi,'w')
      #<p align="left"><font size="16" face="verdana" ><b>{theTime}</b></font></p>
      html_page = """<html>
                <head><title>A smarter Mirror</title>
                </head>
                <bod bgcolor="#000000"y>
                <h1><font face="verdana" size="12" color="white">No WiFi</font></h1>
                <div align="center"><img src=\"NOWIFI_.png\" alt=\"No WiFi\"></div>"
                </body></html>"""
      f.write(html_page)
      f.close()
    except Exception as e:
      print(str(e))

  def createMainHTMLpage(self, theDate, theTime, weatherCode, temperature, humidity, pressure, sunrise, sunset):
    try:
      f = open(fileNameSmartMirrorMain,'w')
      #<p align="left"><font size="16" face="verdana" ><b>{theTime}</b></font></p>
      html_page = """<html>
                <head><title>A Smarter Mirror</title>
                </head>
                <body bgcolor="#000000">
                <h1><font face="verdana" color="white">{theDate}</font></h1>
                <h1><font face="verdana" color="white">{theTime}</font></h1>
                <table style="height:30%;width:100%; position: absolute; top: 0; bottom: 0; left: 0; right: 0;">
                <tr style="height: 30%; font-size: 180px; top: 100">
                <td style="height: 30%width: 50%">
                <p align="left"/>
                </td>
                <td style="height: 30%; width: 50%">
                <p align="right"/>
                {weather}
                <div align="right"><font size="8" face="verdana" color="white">{theTemperature} &deg;C</font></br><font face=\"verdana\" size=\"5\" color=\"white\">{humidity} %/ {pressure} bar</font></div>
                <div align="right"><font size="4" face="verdana" color="white"><img src=\"sunrise_.png\" alt=\"sunrise\">{sunrise}&nbsp;&nbsp;&nbsp;<img src=\"sunset_.png\" alt=\"sunset\">{sunset}</font></div>
                </td>
                </tr>
                <tr>
                </tr>
                </table>
                </body></html>"""

      html_page = html_page.replace("{theDate}", str(theDate))
      html_page = html_page.replace("{theTime}", str(theTime))

      # display weather icons
      html_page = html_page.replace("{theTemperature}", str(temperature))
      html_page = html_page.replace("{humidity}", str(humidity))
      html_page = html_page.replace("{pressure}", str(pressure))
      html_page = html_page.replace("{sunrise}", str(sunrise))
      html_page = html_page.replace("{sunset}", str(sunset))

      weather_icon_html = ""
      #print "the weather code " + str(weatherCode)

      weather_icon_html = self.getWeatherIconHTMLCode(weatherCode, "right")
      
      html_page = html_page.replace("{weather}", weather_icon_html)

      #print( html_page)
      f.write(html_page)
      f.close()
    except Exception as e:
      print( str(e))
      print( 'File ' + fileNameSmartMirrorMain + ' could not be written.')


def mainPage():
  app = SmartMirror()
  app.run()

  # get date
  date_today = datetime.datetime.now()
  theDate = date_today.strftime("%A %d. %B %Y")
  print( "Date today: " + str(theDate))

  if app._wifi:
    print( "WiFi connection OK.")

    summer = False
    if date_today.month > 3 and date_today.month < 11:
      summer = True

    weatherCondition = app.determineWeatherCondition()
    weatherCondition = app.getWeatherFromOWM(summer)  # debugging
    
    app.createMainHTMLpage(theDate, time_now, app._weatherCode, app._temperature, app._humidity, app._pressure, app._sunrise, app._sunset)
    openBrowser(fileNameSmartMirrorMain)
  else:
    print( "No WiFi connection.")
    app.createNoWiFiHTMLpage()
    openBrowser(fileNameSmartMirrorNoWiFi)

# handle browser display
def openBrowser(url):
  closeBrowser()
  t = Thread(target=openBrowser2, args=(url,))
  t.start()

def openBrowser2(fileName):
  # --kiosk
  # https://peter.sh/experiments/chromium-command-line-switches/
  # https://raspberrypi.stackexchange.com/questions/68734/how-do-i-disable-restore-pages-chromium-didnt-shut-down-correctly-prompt
  chromium_parameters = "--start-fullscreen --disable-infobars --kiosk --noerrordialogs --incognito"
  subprocess.call("chromium-browser " + chromium_parameters + " " + fileName, shell=True)

def closeBrowser():
  p = subprocess.Popen(['ps', '-A'], stdout=subprocess.PIPE)
  out, err = p.communicate()
  for line in out.splitlines():
    print( line)
    if b'chromium-brows' in line:
      pid = int(line.split(None, 1)[0])
      os.kill(pid, signal.SIGKILL)

def dimDisplay():
  # dim screen smoothly
  bl.set_brightness(255)
  bl.set_brightness(20, smooth=True, duration=3)
  bl.set_power(False)
  displayOff()
  return

def wakeDisplay():
  # wake screen smoothly
  bl.set_brightness(20)
  bl.set_brightness(255, smooth=True, duration=3)
  bl.set_power(True)
  displayOn()

def startTimerToTurnOffDisplay(seconds=10.0):
  sleep(seconds)
  dimDisplay()

def displayOff():
  subprocess.call('XAUTHORITY=~pi/.Xauthority DISPLAY=:0 xset dpms force off', shell=True)

def displayOn():
  subprocess.call('XAUTHORITY=~pi/.Xauthority DISPLAY=:0 xset dpms force on', shell=True)


# read APDS9960
try:
  while True:
    # add interrupt-Event, rising
    GPIO.add_event_detect(7, GPIO.FALLING, callback = interuptHandlerAPDS9960)

    # get time
    time_now = time.strftime("%H:%M")
    print( "Time now: " + str(time_now))
    theTime = time_now.split(":")

    # define off times
    if(int(theTime[0]) >= 22) and (int(theTime[0]) <= 6):
      print("Smart mirror off")
      dimDisplay()
      displayOff()
      sleep(60)
    else:
      print("Switching with APDS9960 Light Sensor")
      print("=================")
      apds.enableLightSensor()
      oval = -1
      while True:
          sleep(0.25)
          val = apds.readAmbientLight()
          if val != oval:
            print("AmbientLight={}".format(val))
            if val < 10:
              # do something
              if pageIndex == 0:
                dimDisplay()
                mainPage()
                wakeDisplay()
                startTimerToTurnOffDisplay(30)
                pageIndex = 1
              elif pageIndex == 1:
                dimDisplay()
                displayOff()
                pageIndex = 0
              oval = val

finally:
    GPIO.cleanup()
    print "Bye."
