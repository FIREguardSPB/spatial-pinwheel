#!/bin/bash
echo "--- Smoke Test v1.1.0 ---"

BASE_URL="http://localhost:3000/api/v1" # Local dev port, adjust for docker (3000)

echo "1. Checking /health..."
HEALTH=$(curl -s $BASE_URL/health)
echo $HEALTH
if [[ $HEALTH == *"v1.1.0"* ]]; then
  echo "✅ Version Verified"
else
  echo "❌ Version Mismatch"
fi

echo "2. Checking /candles/TQBR:SBER..."
CANDLES=$(curl -s "$BASE_URL/candles/TQBR:SBER?tf=1m")
# Check if array not empty (simple check)
if [[ $CANDLES == *"[{"* ]]; then
  echo "✅ Candles returned"
else
  echo "⚠️  No candles or error"
fi

echo "3. Testing Stream Connection..."
timeout 3s curl -N -s $BASE_URL/stream > /dev/null
if [ $? -eq 124 ]; then
   echo "✅ Stream connected (timed out as expected)"
else
   echo "❌ Stream failed immediately"
fi

echo "--- Done ---"
