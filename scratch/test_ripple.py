import asyncio
import sys
from pathlib import Path

# Setup paths
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine.ripple_engine import RippleEngine
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

async def test_ripple():
    engine = RippleEngine()
    print("Testing Ripple Search for Simulation Engineer at ArcelorMittal...")
    results = await engine.identify_competitors("ArcelorMittal", "Simulation Engineer")
    print("Results:")
    import json
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    asyncio.run(test_ripple())
