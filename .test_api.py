import urllib.request
import ssl
import re

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request("https://tophub.today/n/K7GdaMgdQy", headers={'User-Agent': 'Mozilla/5.0'})
try:
    resp = urllib.request.urlopen(req, context=ctx, timeout=20)
    html = resp.read().decode('utf-8')
    table_html = html[html.find('<table'):html.find('</table>')]
    rows = table_html.split('<tr')
    for row in rows[1:5]:
        tds = row.split('<td')
        if len(tds) >= 3:
            print("Row rank TD:", tds[1][:30])
            print("Row title TD:", tds[2][:50])
except Exception as e:
    print("err:", e)
