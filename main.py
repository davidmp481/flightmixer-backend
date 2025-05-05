from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import requests
from pydantic import BaseModel
from datetime import datetime, timedelta
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

AMADEUS_CLIENT_ID = os.getenv("AMADEUS_CLIENT_ID")
AMADEUS_CLIENT_SECRET = os.getenv("AMADEUS_CLIENT_SECRET")
TOKEN_URL = "https://test.api.amadeus.com/v1/security/oauth2/token"

class SearchRequest(BaseModel):
    origin: str
    destination: str
    date: str

def get_amadeus_token():
    data = {
        'grant_type': 'client_credentials',
        'client_id': AMADEUS_CLIENT_ID,
        'client_secret': AMADEUS_CLIENT_SECRET
    }
    res = requests.post(TOKEN_URL, data=data)
    return res.json()['access_token']

def parse_time(time_str):
    return datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S")

@app.post("/search")
def search_multi_leg(req: SearchRequest):
    token = get_amadeus_token()
    headers = {"Authorization": f"Bearer {token}"}
    hubs = ["JFK", "ORD", "LHR", "CDG", "AMS", "YYZ"]
    first_legs = []

    for hub in hubs:
        if hub == req.destination or hub == req.origin:
            continue
        res1 = requests.get("https://test.api.amadeus.com/v2/shopping/flight-offers", headers=headers, params={
            "originLocationCode": req.origin,
            "destinationLocationCode": hub,
            "departureDate": req.date,
            "adults": 1,
            "max": 3
        }).json()
        for offer in res1.get("data", []):
            first_legs.append((hub, offer))

    itineraries = []
    for hub, leg1 in first_legs:
        res2 = requests.get("https://test.api.amadeus.com/v2/shopping/flight-offers", headers=headers, params={
            "originLocationCode": hub,
            "destinationLocationCode": req.destination,
            "departureDate": req.date,
            "adults": 1,
            "max": 3
        }).json()

        for leg2 in res2.get("data", []):
            arr1 = parse_time(leg1["itineraries"][0]["segments"][-1]["arrival"]["at"])
            dep2 = parse_time(leg2["itineraries"][0]["segments"][0]["departure"]["at"])
            layover = dep2 - arr1
            if timedelta(hours=1) <= layover <= timedelta(hours=5):
                total_price = float(leg1["price"]["total"]) + float(leg2["price"]["total"])
                all_legs = []
                for segment in leg1["itineraries"][0]["segments"]:
                    all_legs.append({
                        "departure": segment["departure"]["iataCode"],
                        "arrival": segment["arrival"]["iataCode"],
                        "time": segment["departure"]["at"],
                        "carrier": segment["carrierCode"]
                    })
                for segment in leg2["itineraries"][0]["segments"]:
                    all_legs.append({
                        "departure": segment["departure"]["iataCode"],
                        "arrival": segment["arrival"]["iataCode"],
                        "time": segment["departure"]["at"],
                        "carrier": segment["carrierCode"]
                    })
                itineraries.append({
                    "price": round(total_price, 2),
                    "legs": all_legs
                })
    itineraries = sorted(itineraries, key=lambda x: x["price"])[:5]
    return {"itineraries": itineraries}
