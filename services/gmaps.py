import re
import aiohttp
from typing import Tuple, Optional

async def extract_coordinates_from_gmaps(url: str) -> Optional[Tuple[float, float]]:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    expanded_url = url
    
    if "maps.app.goo.gl" in url or "goo.gl" in url:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(url, allow_redirects=True, headers=headers) as resp:
                    expanded_url = str(resp.url)
        except Exception:
            return None
    
    patterns = [
        r'@(-?\d+\.\d+),(-?\d+\.\d+)',
        r'data=.*!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)',
        r'[\?&](?:q|ll)=(-?\d+\.\d+),(-?\d+\.\d+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, expanded_url)
        if match:
            lat, lon = map(float, match.groups())
            return lat, lon
            
    return None
