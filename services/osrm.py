import math
import aiohttp

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0 # Earth radius in KM
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

async def get_osrm_road_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("routes"):
                        return data["routes"][0]["distance"] / 1000.0
    except Exception:
        pass
    return haversine_distance(lat1, lon1, lat2, lon2)

def calculate_delivery_charge(road_km: float, base_fare: float, base_km: float, extra_per_km: float) -> float:
    if road_km <= base_km:
        return base_fare
    return base_fare + ((road_km - base_km) * extra_per_km)
