import requests

query = "ethics"
url = f"https://api.taopulse.io:8000/twitter/get_latest_twitter?searchKey={query}&pageSize=500&pageNumber=1&sortKey=created_at&sortDirect=desc"

payload = {}
headers = {
	'x-api-key': 'r2lenUJ33K3dSUe9kZVkhCySIL4s0mus'
}

response = requests.request("GET", url, headers=headers, data=payload)
res = response.json()
data = []

for x in res['data']:
    if query.lower() in x['text'].lower():
        data.append(x)

print(data[0])
print("=========")
print(res['data'][0])
print("=========")
print(f"----==== took: {res['total_duration']} ====----")
print(f"----==== got {len(res['data'])} tweets ====----")
print(f"----==== returned {len(data)} filtered tweets ====----")
