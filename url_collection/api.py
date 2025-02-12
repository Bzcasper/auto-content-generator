import requests

url = "http://localhost:3002/v0/scrape"

payload = {
    "url": "ebay.com",
    "excludePaths": ["<string>"],
    "includePaths": ["<string>"],
    "maxDepth": 2,
    "ignoreSitemap": False,
    "ignoreQueryParameters": False,
    "limit": 10000,
    "allowBackwardLinks": False,
    "allowExternalLinks": False,
    "webhook": "<string>",
    "scrapeOptions": {
        "formats": ["markdown"],
        "onlyMainContent": True,
        "includeTags": ["<string>"],
        "excludeTags": ["<string>"],
        "headers": {},
        "waitFor": 0,
        "mobile": False,
        "skipTlsVerification": False,
        "timeout": 30000,
        "removeBase64Images": True,
        "blockAds": True,
        "actions": [
            {
                "type": "wait",
                "milliseconds": 2,
                "selector": "#my-element"
            }
        ]
    }
}
headers = {
    "Authorization": "Bearer <token>",
    "Content-Type": "application/json"
}

response = requests.request("POST", url, json=payload, headers=headers)

print(response.text)