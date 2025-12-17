#----------------------------------------------------------------
# METEO SEARCH TOOL
#----------------------------------------------------------------
import datetime
import requests
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from langchain.tools import tool


class OpenMeteoInput(BaseModel):
    city: Optional[str] = Field(
        None, 
        description="City or location name (e.g., 'Paris', 'Nevada', 'Cracow, 'Fuerteventura')"
    )
    country: Optional[str] = Field(
        None, 
        description="Country name or ISO code (e.g., 'Spain', 'USA', 'Poland', 'ES'). Optional but improves accuracy."
    )
    latitude: Optional[float] = Field(
        None, 
        description="Latitude coordinate. Only use if explicitly provided by user."
    )
    longitude: Optional[float] = Field(
        None, 
        description="Longitude coordinate. Only use if explicitly provided by user."
    )

@tool(args_schema=OpenMeteoInput)
def get_weather_conditions(
    city: Optional[str] = None,
    country: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None
) -> str:
    """
    Get current weather conditions (temperature, precipitation, wind, humidity) for any location.
    Use this whenever you need weather information to answer a question, whether explicitly asked or contextually needed.
    Automatically geocodes city names to coordinates.
    """
    
    # Geocode if coordinates not provided
    if latitude is None or longitude is None:
        if not city:
            return "Error: Please provide either a location name or both latitude and longitude."
        
        location_query = f"{city}, {country}" if country else city
        
        geocode_url = "https://nominatim.openstreetmap.org/search"
        geocode_params = {
            'q': location_query,
            'format': 'json',
            'limit': 1
        }
        headers = {'User-Agent': 'LangChain-Weather-Bot/1.0'}
        
        try:
            geo_response = requests.get(geocode_url, params=geocode_params, headers=headers, timeout=10)
            geo_response.raise_for_status()
            geo_data = geo_response.json()
            
            if not geo_data:
                return f"Error: Could not find coordinates for '{location_query}'."
            
            latitude = float(geo_data[0]['lat'])
            longitude = float(geo_data[0]['lon'])
            location_name = geo_data[0].get('display_name', location_query)
            
        except Exception as e:
            return f"Error geocoding location: {str(e)}"
    else:
        location_name = f"coordinates ({latitude}, {longitude})"
    
    # Fetch weather data
    BASE_URL = "https://api.open-meteo.com/v1/forecast"
    
    params = {
        'latitude': latitude,
        'longitude': longitude,
        'current': 'temperature_2m,relative_humidity_2m,precipitation,rain,weather_code,wind_speed_10m,wind_direction_10m',
        'forecast_days': 1,
        'temperature_unit': 'celsius',
        'wind_speed_unit': 'kmh',
    }
    
    try:
        response = requests.get(BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        results = response.json()
    except Exception as e:
        return f"Error fetching weather data: {str(e)}"
    
    # Parse current weather
    current = results.get('current', {})
    temp = current.get('temperature_2m', 'N/A')
    humidity = current.get('relative_humidity_2m', 'N/A')
    precipitation = current.get('precipitation', 0)
    rain = current.get('rain', 0)
    wind_speed = current.get('wind_speed_10m', 'N/A')
    wind_direction = current.get('wind_direction_10m', 'N/A')
    weather_code = current.get('weather_code', 0)
    
    # Decode weather condition
    weather_descriptions = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Foggy", 48: "Depositing rime fog",
        51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
        61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow", 77: "Snow grains",
        80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
        85: "Slight snow showers", 86: "Heavy snow showers",
        95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
    }
    weather_condition = weather_descriptions.get(weather_code, "Unknown")
    
    # Build report
    report = (
        f"Weather in {location_name}:\n"
        f"Temperature: {temp}°C\n"
        f"Conditions: {weather_condition}\n"
        f"Humidity: {humidity}%\n"
        f"Wind: {wind_speed} km/h from {wind_direction}°\n"
        f"Precipitation: {precipitation} mm (rain: {rain} mm)"
    )
    
    return report