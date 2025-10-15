TOKEN='.eJyrVirNTFGyMtJRyslPz8xTslLKTXVIrUjMLchJ1UvOz1XSUUrNTczMwZSoBQA_ghO-.aOkcCg.AmqEgsIjnGsHSuzy2eKmdD5QXLQ'
BASE='http://10.11.12.12:5000'

for id in $(seq 1 10); do
  DATA=$(printf '{"method":"toy-eof","intended_for":"batch-test","secret":"secret-for-doc-%s","key":"my-shared-key"}' "$id")
  curl -s -X POST "$BASE/api/create-watermark/$id" \
       -H "Authorization: Bearer $TOKEN" \
       -H "Content-Type: application/json" \
       -d "$DATA"
  echo
done
