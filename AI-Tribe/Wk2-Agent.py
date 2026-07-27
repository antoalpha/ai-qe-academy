import requests
from openai import OpenAI

# -----------------------------
# Initialize GPT
# -----------------------------
client = OpenAI()c

# -----------------------------
# Weather Tool
# -----------------------------
def get_weather():

    # Sunnyvale Coordinates
    latitude = 37.3688
    longitude = -122.0363

    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={latitude}"
        f"&longitude={longitude}"
        f"&current=temperature_2m,weather_code"
    )

    response = requests.get(url).json()

    temperature = response["current"]["temperature_2m"]
    weather_code = response["current"]["weather_code"]

    # Convert Weather Code
    weather_lookup = {
        0: "Sunny",
        1: "Mostly Sunny",
        2: "Partly Cloudy",
        3: "Cloudy",
        45: "Fog",
        48: "Fog",
        51: "Light Drizzle",
        61: "Rain",
        63: "Moderate Rain",
        65: "Heavy Rain",
        71: "Snow"
    }

    weather = weather_lookup.get(weather_code, "Unknown")

    return temperature, weather

# -----------------------------
# Agent
# -----------------------------

temperature, weather = get_weather()

print("Weather Tool Output")
print("---------------------")
print(f"Weather in Sunnyvale    : {weather}")
print(f"Temperature : {temperature}°C")


prompt = f"""
You are an intelligent travel assistant.

Current Location:
Sunnyvale, California

Weather:
{weather}

Temperature:
{temperature}°C

Based on the weather, provide:

1. Clothing recommendation

2. Whether to carry an umbrella

3. Driving recommendations

4. Walking recommendations

5. Travel safety tips

6. Health recommendations

Keep the response friendly and practical.
"""

response = client.responses.create(
    model="gpt-5.5",
    input=prompt
)

print("\n")
print("AI Recommendation")
print("---------------------")
print(response.output_text)